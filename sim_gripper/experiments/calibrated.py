"""그리퍼 보정 MoE: v4와 같은 구조(1,413 파라미터)를 60A 벨로즈 그리퍼 시뮬 데이터로 mixed fine-tune.

논문 그림의 메인 추정기. 시뮬레이션 내 보정이며, 실물에서는 같은 절차를 그리퍼 장착 실측 데이터로 수행한다.
python -m sim_gripper.experiments.calibrated  →  sim_gripper/out/moe_gripper.pkl
"""
import pickle

from sim_gripper.experiments.domain_shift import adapt, collect_sim_data, load_flat
from sim_gripper.experiments.run_all import OUT
from sim_gripper.perception.moe import DEFAULT_PKL
from sim_gripper.sensor.forward import DomainShift

CAL_SCENARIOS = ("E1_metal", "E2_hand", "E2_egg", "E3_small")
CACHE = OUT / "moe_gripper.pkl"


def make_gripper_moe(n=20000, seed=0, base=None, cache=CACHE):
    if cache is not None and cache.exists():
        return pickle.loads(cache.read_bytes())
    if base is None:
        base = pickle.loads(DEFAULT_PKL.read_bytes())
    data = collect_sim_data(DomainShift(), n, seed, finger="bellows60a", scenarios=CAL_SCENARIOS, models=base)
    model = adapt("mixed", base, data, load_flat()[0])
    if cache is not None:
        cache.parent.mkdir(parents=True, exist_ok=True)
        cache.write_bytes(pickle.dumps(model))
    return model


if __name__ == "__main__":
    make_gripper_moe(cache=CACHE)
    print(CACHE)
