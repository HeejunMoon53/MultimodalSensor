"""실험 시나리오 (E1~E4). 물체는 테이블 위, 높이 ≤ 80 mm (베이스 z=90 mm 아래)."""
from dataclasses import dataclass, field, replace

from sim_gripper.model.gripper import ObjectSpec

EVENTS = [(0.5, "approach"), (4.0, "lift"), (8.0, "release")]


@dataclass
class Scenario:
    name: str
    obj: ObjectSpec
    t_end: float = 10.0
    events: list = field(default_factory=lambda: list(EVENTS))
    disturbance: tuple | None = None    # (t_start, t_end, (fx, fy, fz) [N])


_METAL = ObjectSpec("metal", "cylinder", (0.025, 0.04), 0.2, "conductor")

SCENARIOS = {s.name: s for s in [
    Scenario("E1_metal", _METAL),
    Scenario("E2_hand", ObjectSpec("hand", "capsule", (0.02, 0.02), 0.3, "dielectric", soft=True)),
    Scenario("E2_egg", ObjectSpec("egg", "sphere", (0.022,), 0.06, "dielectric", fragile_F_N=3.5)),
    Scenario("E3_sponge", ObjectSpec("sponge", "cylinder", (0.025, 0.04), 0.02, "dielectric", soft=True)),
    Scenario("E3_small", replace(_METAL, name="metal_small", size=(0.015, 0.04), mass_kg=0.1)),
    Scenario("E3_large", replace(_METAL, name="metal_large", size=(0.035, 0.04), mass_kg=0.3)),
    Scenario("E4_disturb", _METAL, disturbance=(6.0, 7.0, (3.0, 0.0, 0.0))),
    # 논문 Fig.11(e) 실 스풀 1297 g 대용: 원통 지름 60 mm, 1.3 kg, 플라스틱(유전체)
    Scenario("E5_spool", ObjectSpec("spool", "cylinder", (0.03, 0.035), 1.3, "dielectric")),
]}
