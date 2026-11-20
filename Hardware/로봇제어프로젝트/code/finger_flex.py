"""PneuNet 손가락 연속체 모델 (MuJoCo flexcomp, 3차원 사면체 유한요소).

형상은 Hardware/pneunet_gripper/build_cad.py 의 PP 기본값을 그대로 쓴다.
비신장층(종이)은 없다. 몸체·바닥층 모두 Dragon Skin 30.
좌표(손가락 국소): x = 뿌리→손끝, y = 폭, z = 바닥층 바깥면(물체 쪽, z=0) → 등.
공기 방 내벽 면에 압력 f = p·A·n 을 걸어 방이 부풀고 손가락이 −z(물체 쪽)로 굽는다.
"""
from dataclasses import dataclass

import mujoco

import paths  # noqa: F401  (build_cad 경로)
import numpy as np

from build_cad import PP

RHO = 1080.0  # DS30 밀도 [kg/m³]


@dataclass
class _Grid:
    xs: np.ndarray
    ys: np.ndarray
    zs: np.ndarray


def _breaks(pp, sensor_z, res):
    xs = [0.0, 10.0]
    x = pp.root_len
    for i in range(pp.n_ch):
        xs += [x, x + pp.t_in, x + pp.blk - pp.t_in] + ([x + pp.blk / 2] if res == "fine" else [])
        x += pp.blk
        if i < pp.n_ch - 1:
            xs.append(x)
            x += pp.gap
    xs += [x, x + pp.end_add]
    ny = 2 if res == "coarse" else 4
    inner = np.linspace(pp.wall, pp.W - pp.wall, ny + 1)
    ys = [0.0, *inner, pp.W]
    zb, H = pp.t_base, pp.t_base + pp.H
    zs = sorted({0.0, sensor_z, zb, zb + pp.strut_h, H - pp.top_t, H} | ({(zb + pp.strut_h + H - pp.top_t) / 2} if res == "fine" else set()))
    return _Grid(np.array(sorted(set(xs))), np.array(ys), np.array(zs))


class FlexFinger:
    def __init__(self, young_pa=1.0e6, poisson=0.3, sensor_z_mm=2.0, res="coarse", damping=0.002, pp=None,
                 selfcollide="none"):
        self.selfcollide = selfcollide
        self.pp = pp or PP()
        self.young, self.poisson, self.damping = young_pa, poisson, damping
        self.sensor_z = sensor_z_mm
        self._build_mesh(res)

    # ---------- 메시 ----------
    def _cell_kind(self, cx, cy, cz):
        """0 = 고체, 1 = 공기 방(압력), 2 = 바깥 공기(틈)."""
        pp = self.pp
        zb, H = pp.t_base, pp.t_base + pp.H
        if cz < zb:
            return 0
        if cx < pp.root_len:
            return 0
        x = cx - pp.root_len
        i = int(x // (pp.blk + pp.gap))
        xr = x - i * (pp.blk + pp.gap)
        if i >= pp.n_ch:
            return 0  # 끝벽 덧살
        if xr >= pp.blk:  # 방 사이 틈
            return 0 if cz < zb + pp.strut_h else 2
        inside_x = pp.t_in < xr < pp.blk - pp.t_in
        inside_y = pp.wall < cy < pp.W - pp.wall
        if inside_x and inside_y and cz < H - pp.top_t:
            return 1
        return 0

    def _build_mesh(self, res):
        g = _breaks(self.pp, self.sensor_z, res)
        nx, ny, nz = len(g.xs), len(g.ys), len(g.zs)
        nid = lambda i, j, k: (i * ny + j) * nz + k
        kind = np.zeros((nx - 1, ny - 1, nz - 1), int)
        for i in range(nx - 1):
            for j in range(ny - 1):
                for k in range(nz - 1):
                    c = (g.xs[i] + g.xs[i + 1]) / 2, (g.ys[j] + g.ys[j + 1]) / 2, (g.zs[k] + g.zs[k + 1]) / 2
                    kind[i, j, k] = self._cell_kind(*c)
        tets, faces = [], []
        for i in range(nx - 1):
            for j in range(ny - 1):
                for k in range(nz - 1):
                    if kind[i, j, k] != 0:
                        continue
                    v = [nid(i + a, j + b, k + c) for a in (0, 1) for b in (0, 1) for c in (0, 1)]
                    v0, v1, v2, v3, v4, v5, v6, v7 = v
                    tets += [(v0, v1, v3, v7), (v0, v1, v5, v7), (v0, v2, v3, v7),
                             (v0, v2, v6, v7), (v0, v4, v5, v7), (v0, v4, v6, v7)]
        # 방 내벽 면: 공기 방 칸과 맞닿은 고체 칸의 공유 사각형. 꼭짓점 순서는 법선이 방→고체.
        for i in range(nx - 1):
            for j in range(ny - 1):
                for k in range(nz - 1):
                    if kind[i, j, k] != 1:
                        continue
                    for ax, s in ((0, -1), (0, 1), (1, -1), (1, 1), (2, -1), (2, 1)):
                        n = [i, j, k]; n[ax] += s
                        if kind[tuple(n)] != 0:
                            continue
                        f = [i, j, k]; f[ax] += (1 if s > 0 else 0)
                        a1, a2 = [q for q in range(3) if q != ax]
                        quad = []
                        for da, db in ((0, 0), (1, 0), (1, 1), (0, 1)):
                            p = list(f); p[a1] += da; p[a2] += db
                            quad.append(nid(*p))
                        faces.append((quad, ax, s))
        pts = np.array([[x, y, z] for x in g.xs for y in g.ys for z in g.zs]) * 1e-3
        used = np.unique(np.array(tets).ravel())
        remap = -np.ones(len(pts), int); remap[used] = np.arange(len(used))
        self.P0 = pts[used]
        self.tets = remap[np.array(tets)]
        self.faces = []
        for quad, ax, s in faces:
            q = remap[quad]
            a = 0.5 * np.cross(self.P0[q[2]] - self.P0[q[0]], self.P0[q[3]] - self.P0[q[1]])
            self.faces.append(q if a[ax] * s > 0 else q[::-1])
        self.faces = np.array(self.faces)
        self.pins = np.where(self.P0[:, 0] < self.pp.root_len * 1e-3 * 0.67)[0]
        sz = self.sensor_z * 1e-3
        ymid = g.ys[np.argmin(abs(g.ys - self.pp.W / 2))] * 1e-3
        x1 = (self.pp.root_len + self.pp.n_ch * self.pp.blk + (self.pp.n_ch - 1) * self.pp.gap
              + self.pp.end_add - self.pp.sensor_tip_gap) * 1e-3
        x0 = x1 - self.pp.sensor[0] * 1e-3
        on = np.where((abs(self.P0[:, 2] - sz) < 1e-9) & (abs(self.P0[:, 1] - ymid) < 1e-9)
                      & (self.P0[:, 0] >= x0 - 2e-3) & (self.P0[:, 0] <= x1 + 2e-3))[0]
        self.sensor_ids = on[np.argsort(self.P0[on, 0])]
        cl = np.where((self.P0[:, 2] < 1e-9) & (abs(self.P0[:, 1] - ymid) < 1e-9))[0]
        self.center_ids = cl[np.argsort(self.P0[cl, 0])]
        vol = 0.0
        for t in self.tets:
            a, b, c, d = self.P0[t]
            vol += abs(np.dot(b - a, np.cross(c - a, d - a))) / 6
        self.mass = RHO * vol

    # ---------- MJCF ----------
    def mjcf(self, name, pos=(0, 0, 0), quat=(1, 0, 0, 0)):
        self.name, self.pos, self.quat = name, np.array(pos, float), np.array(quat, float)
        pt = " ".join(f"{v:.6g}" for v in self.P0.ravel())
        el = " ".join(map(str, self.tets.ravel()))
        return (f'<flexcomp name="{name}" type="direct" dim="3" mass="{self.mass:.6g}" radius="0.0005" '
                f'pos="{" ".join(map(str, pos))}" quat="{" ".join(map(str, quat))}" rgba="0.85 0.55 0.45 1" '
                f'point="{pt}" element="{el}">'
                f'<elasticity young="{self.young:.6g}" poisson="{self.poisson}" damping="{self.damping}"/>'
                f'<contact condim="3" selfcollide="{self.selfcollide}" solref="0.005 1"/>'
                f'<pin id="{" ".join(map(str, self.pins))}"/></flexcomp>')

    def attach(self, model, data, name=None):
        name = name or self.name
        fid = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_FLEX, name)
        self.fid = fid
        self.vadr = model.flex_vertadr[fid]
        self.vbody = model.flex_vertbodyid[self.vadr:self.vadr + model.flex_vertnum[fid]].copy()
        R = np.zeros(9); mujoco.mju_quat2Mat(R, self.quat / np.linalg.norm(self.quat))
        self.R = R.reshape(3, 3)

    def _X(self, data):
        return data.flexvert_xpos[self.vadr:self.vadr + len(self.P0)]

    def _local(self, data):
        return (self._X(data) - self.pos) @ self.R

    # ---------- 압력·측정 ----------
    def apply_pressure(self, data, p_kpa):
        X = self._X(data)
        q = self.faces
        A = 0.5 * np.cross(X[q[:, 2]] - X[q[:, 0]], X[q[:, 3]] - X[q[:, 1]])  # 방→고체 면적 벡터
        F = np.repeat(A * (max(p_kpa, 0.0) * 1e3 / 4.0), 4, axis=0)
        ids = self.vbody[q.ravel()]
        data.xfrc_applied[self.vbody, :3] = 0.0
        np.add.at(data.xfrc_applied[:, :3], ids, F)
        data.xfrc_applied[0, :3] = 0.0  # 고정 정점(world) 몫은 버린다

    def chamber_volume(self, data):
        """발산 정리: V = (1/3)Σ (c·A), 법선이 방 바깥(고체 쪽). [mm³]"""
        X = self._X(data) * 1e3
        q = self.faces
        v = 0.0
        for t in ((0, 1, 2), (0, 2, 3)):
            a, b, c = X[q[:, t[0]]], X[q[:, t[1]]], X[q[:, t[2]]]
            v += np.einsum("ij,ij->", a, np.cross(b, c)) / 6.0
        return v

    def sensor_strain(self, data):
        L = self._local(data)[self.sensor_ids]
        L0 = self.P0[self.sensor_ids]
        seg = lambda P: np.linalg.norm(np.diff(P, axis=0), axis=1).sum()
        return 100.0 * (seg(L) / seg(L0) - 1.0)

    def centerline(self, data):
        return self._local(data)[self.center_ids]

    def sensor_point(self, data):
        return self._X(data)[self.sensor_ids[len(self.sensor_ids) // 2]].copy()

    def tip_point(self, data):
        return self._X(data)[self.center_ids[-1]].copy()

    @property
    def tip_body(self):
        return self.vbody[self.center_ids[-1]]

    def tip_angle(self, data):
        """바닥면 중심선 접선의 누적 회전 [deg]. 물체 쪽(−z)으로 굽으면 양수."""
        P = self.centerline(data)
        dv = np.diff(P[:, [0, 2]], axis=0)
        th = np.unwrap(np.arctan2(dv[:, 1], dv[:, 0]))
        return float(-np.degrees(th[-1] - th[0]))


def build_single(finger, dt=1e-3, gravity=False):
    g = "0 0 -9.81" if gravity else "0 0 0"
    xml = (f'<mujoco><option timestep="{dt}" gravity="{g}" solver="Newton" integrator="discrete"/>'
           f'<worldbody><light pos="0 0 1"/>{finger.mjcf("finger")}</worldbody></mujoco>')
    m = mujoco.MjModel.from_xml_string(xml)
    d = mujoco.MjData(m)
    finger.attach(m, d)
    mujoco.mj_forward(m, d)
    return m, d
