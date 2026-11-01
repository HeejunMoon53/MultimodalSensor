"""시뮬 렌더용 메시: 60A 벨로즈 CAD를 벨로즈 단위로 잘라 MuJoCo 세그먼트 좌표계로 옮겨 저장.

python -m sim_gripper.cad.visual  → sim_gripper/model/assets/ (커밋됨, build123d 없이 시뮬 실행 가능)

세그먼트 j 좌표계 (gripper.BellowsParams.finger_xml과 동일): 원점 = hinge = 안쪽면(센서면) 위 현(chord) 시작점,
−Z = 현 방향, +X = 곡률 중심(그리퍼 중심) 쪽. CAD에서 현 j는 P(j·Δ)에서 시작해 각 (j+½)Δ 방향.
"""
import math
from pathlib import Path

from build123d import Box, Pos, Rot, export_stl

from sim_gripper.cad.base import make_base
from sim_gripper.cad.finger import FingerCAD, _sector, _solidify, make_finger

ASSETS = Path(__file__).resolve().parents[1] / "model" / "assets"


def export_visual_meshes(out_dir=ASSETS, p=FingerCAD()):
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    finger, rho, pitch = make_finger(p), p.rho(), p.theta() / p.n_bellows
    files = []
    for j in range(p.n_bellows):
        piece = finger & _solidify(_sector(p, -2.0, p.bellow_h + 5, j * pitch, (j + 1) * pitch), p.depth + 4)
        a0, a = j * pitch, (j + 0.5) * pitch
        px, pz = rho - rho * math.cos(a0), -rho * math.sin(a0)
        local = Rot(0, math.degrees(a), 0) * (Pos(-px, 0, -pz) * piece)
        files.append(out_dir / f"bellows_seg{j}.stl")
        export_stl(local, str(files[-1]), tolerance=0.05, angular_tolerance=0.2)
    root = finger & Pos(0, 0, p.root_len / 2 + 0.01) * Box(60, p.depth + 4, p.root_len)
    files.append(out_dir / "bellows_root.stl")
    export_stl(root, str(files[-1]), tolerance=0.05, angular_tolerance=0.2)
    files.append(out_dir / "base_60A.stl")
    export_stl(make_base(fp=p), str(files[-1]), tolerance=0.05, angular_tolerance=0.2)
    return files


if __name__ == "__main__":
    for f in export_visual_meshes():
        print(f, f.stat().st_size)
