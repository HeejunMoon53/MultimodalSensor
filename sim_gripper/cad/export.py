"""STL/STEP 내보내기 + 출력 설정 메모.

python -m sim_gripper.cad.export  →  sim_gripper/cad/out/
"""
from pathlib import Path

from build123d import export_step, export_stl

from sim_gripper.cad.base import make_base
from sim_gripper.cad.finger import FingerCAD, make_finger

OUT = Path(__file__).resolve().parent / "out"

SETTINGS = """# 출력 설정 (Meitani & Nisar 2025, Table 4 — Filaflex 60A)

| 항목 | 값 |
|---|---|
| 프린터 | Prusa MK4, 노즐 0.4 mm |
| 노즐 온도 | 225 °C (70A는 230 °C) |
| 층 높이 / 첫 층 | 0.12 mm / 0.2 mm |
| 외벽(perimeter) | 최소 3, 외벽 먼저 |
| 인필 | 100 % |
| 속도 / 이동 속도 | 20 mm/s / 200 mm/s |
| 압출 배율 | 1.1 |
| 리트랙션 | 끔 |
| 교차 외벽 회피 | 켬 |
| 팬 | 95 % |
| 최대 체적 유량 | 2.5 mm³/s |
| 건조 | 45 °C, 출력 전·중 8 h 이상 |
| 방향 | 손가락을 옆으로 눕혀(32 mm 폭 방향이 Z) 출력 → 서포트 불필요, 심(seam)은 베이스 뒤쪽 |

- 손가락: `finger_60A.stl` × 3. 출력 후 납땜 인두로 루트 윗면에서 Ø4 입구를 뚫어 채널까지 연결 (논문 방식).
- 베이스: `gripper_base.stl`, PLA. 손가락 루트 블록을 아래에서 끼우고 튜브는 위에서.
- 센서 홈: 손가락 안쪽면 원위 3개 벨로즈 구간, 폭 {groove_w} mm × 깊이 {groove_d} mm — EGaIn 센서 부착 위치 (논문에 없는 추가 형상).
- 추정 치수(논문 Table 3에 없음): 바닥층 {backbone_t} mm, 채널 {channel_h} mm, 벨로즈 높이 {bellow_h} mm — 실제 논문 형상과 다를 수 있으니 `FingerCAD` 값을 조정.
"""


def export_all(out_dir=OUT, p=FingerCAD()):
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    finger, base = make_finger(p), make_base(fp=p)
    files = {"finger_stl": out_dir / "finger_60A.stl", "finger_step": out_dir / "finger_60A.step",
             "base_stl": out_dir / "gripper_base.stl", "settings": out_dir / "PRINT_SETTINGS.md"}
    export_stl(finger, str(files["finger_stl"]), tolerance=0.02, angular_tolerance=0.1)
    export_step(finger, str(files["finger_step"]))
    export_stl(base, str(files["base_stl"]), tolerance=0.02, angular_tolerance=0.1)
    files["settings"].write_text(SETTINGS.format(**p.__dict__), encoding="utf-8")
    return files


def render_preview(path=OUT / "finger_preview.png", p=FingerCAD()):
    """옆면·등각 미리보기 (보고서용). matplotlib 삼각망 렌더."""
    import matplotlib
    matplotlib.use("Agg")
    matplotlib.rcParams.update({"font.family": "Malgun Gothic", "axes.unicode_minus": False})
    import matplotlib.pyplot as plt
    from mpl_toolkits.mplot3d.art3d import Poly3DCollection

    finger = make_finger(p)
    verts, tris = finger.tessellate(0.2, 0.2)
    v = [(q.X, q.Y, q.Z) for q in verts]
    polys = [[v[i] for i in t] for t in tris]
    fig = plt.figure(figsize=(10, 5))
    for k, (elev, azim, title) in enumerate([(0, -90, "옆면 (XZ)"), (25, -55, "등각")]):
        ax = fig.add_subplot(1, 2, k + 1, projection="3d")
        ax.add_collection3d(Poly3DCollection(polys, facecolor="#C9C2B8", edgecolor="#6E675F", linewidths=0.05))
        ax.set_xlim(-20, 40), ax.set_ylim(-30, 30), ax.set_zlim(-110, 10)
        ax.set_box_aspect((60, 60, 120))
        ax.view_init(elev=elev, azim=azim)
        ax.set_title(title, fontsize=10)
        ax.set_xlabel("X [mm]"), ax.set_zlabel("Z [mm]")
    fig.suptitle("60A 벨로즈 손가락 CAD (벨로즈 8개, precurve 41°, 폭 32 mm) — 안쪽(+X)면 센서 홈", fontsize=10)
    fig.tight_layout()
    fig.savefig(path, dpi=120)
    plt.close(fig)
    return path


if __name__ == "__main__":
    for k, v in export_all().items():
        print(k, v)
    print("preview", render_preview())
