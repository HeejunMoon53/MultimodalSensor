"""3지 PLA 베이스: 손가락 루트 블록이 아래에서 끼워지는 소켓 3개(120°), 공기 튜브 구멍, 장착 구멍."""
import math

from build123d import Box, Cylinder, Pos, Rot

from sim_gripper.cad.finger import FingerCAD


def make_base(R=76.0, thickness=12.0, clearance=0.2, fp=FingerCAD()):
    """R: 손가락 안쪽면(센서면) 반경 [mm]. 루트 블록은 R..R+band 바깥쪽으로 놓인다."""
    band = fp.backbone_t + fp.channel_h + fp.wall
    base = Pos(0, 0, thickness / 2) * Cylinder(R + band + 12, thickness)
    for i in range(3):
        phi = 120 * i
        sock = Pos(R + band / 2, 0, fp.root_len / 2) * Box(band + 2 * clearance, fp.depth + 2 * clearance,
                                                         fp.root_len + 0.01)
        tube = Pos(R + fp.backbone_t + fp.channel_h / 2, 0, thickness / 2) * Cylinder(2.6, thickness + 1)
        base -= Rot(0, 0, phi) * (sock + tube)
    base -= Pos(0, 0, thickness / 2) * Cylinder(5.0, thickness + 1)                    # 중앙 장착 구멍
    for k in range(4):                                                               # M4 나사 4개
        a = math.radians(45 + 90 * k)
        base -= Pos(20 * math.cos(a), 20 * math.sin(a), thickness / 2) * Cylinder(2.2, thickness + 1)
    return base
