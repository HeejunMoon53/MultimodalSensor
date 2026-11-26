"""사진형 단계 비교 (시뮬레이션): 사람이 쥔 망치 → (1) 금속 자루 잡기 (도체) vs (2) 손목 잡기 (인체).

S7 과 같은 폐루프 (C F-LQG + RLS, 감독기, TDM·MoE·TENG). 소품은 보이기만 함 (photo_scene).
단계 사진: 탐지 (APPROACH 진입) · 접근 · 접촉 (첫 접촉) · 파지 유지 (도체 t = 6.5 s) | 상호작용 (인체: t ≥ 5 s 첫 SAFETY).
실행: C:/ml_env/Scripts/python.exe run_photo.py → out/photo_{mat}_{k}.png, params results_photo
"""
import numpy as np

import paths  # noqa: F401
from paths import OUT, load_params, save_params
from plant import Plant, Scenario
from run_compare import CTRL9, TS, approach_path, make_grasp_ctrl, make_sup

CASES = (("conductor", "hammer"), ("human", "wrist"))
PHASES = ("탐지 · 식별", "접근", "접촉", "파지 · 유지")
C_NAME = "C F-LQG + RLS 스케줄"


def run(P, mat, scene, seconds=7.0, t_hold=6.5, t_grasp=4.5, w=800, h=600):
    import imageio.v2 as imageio
    spec = CTRL9[C_NAME]
    pl = Plant(Scenario(material=mat, obj_path=approach_path(mat), photo=scene), seed=21)
    ctr = [make_grasp_ctrl(P, spec) for _ in range(2)]
    sup = [make_sup(P, mat, spec["kind"]) for _ in range(2)]
    u, shots, t_app = np.zeros(2), {}, None
    for k in range(int(seconds / TS)):
        o = pl.step(u); tr = pl.truth()
        cmd = "grasp" if pl.t > t_grasp else "approach"
        for i in range(2):
            Fh = o.val_hat[i] if o.contact[i] else 0.0
            sup[i].step(dict(d_hat=o.val_hat[i] if not o.contact[i] else 0.0, F_hat=Fh, contact=o.contact[i],
                             eps_hat=o.eps_hat[i]), mat, cmd)
            if sup[i].state == "OPEN":
                u[i] = 0.0; ctr[i].reset()
            else:
                u[i] = ctr[i].u(o.p_mon[i], o.eps_hat[i], Fh, sup[i])
        st = {s.state for s in sup}
        info = dict(t=round(pl.t, 2), state="/".join(sorted(st)), d_mm=float(tr.d_mm.min()), F_N=float(tr.F_N.max()), u_kPa=float(u.mean()))
        hold = pl.t >= t_hold if mat != "human" else (pl.t >= 5.0 and "SAFETY" in st)  # 인체: 반사·SAFETY 가 동작한 순간
        if t_app is None and sup[0].state != "OPEN":
            t_app = pl.t
            shots[0] = info
        elif t_app is not None and 1 not in shots and pl.t >= t_app + 0.6 * (4.0 - t_app):
            shots[1] = info
        elif 1 in shots and 2 not in shots and o.contact.any():
            shots[2] = info
        elif 2 in shots and 3 not in shots and hold:
            shots[3] = info
        else:
            continue
        j = max(shots)
        imageio.imwrite(OUT / f"photo_{mat}_{j}.png", pl.frames(cam="photo", w=w, h=h))
    return [shots.get(j, {}) for j in range(4)]


def main():
    P = load_params()
    res = {mat: run(P, mat, scene) for mat, scene in CASES}
    for mat, sh in res.items():
        print(mat, sh, flush=True)
    save_params("results_photo", res)


if __name__ == "__main__":
    main()
