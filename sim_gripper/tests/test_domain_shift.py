import pytest

from sim_gripper.experiments.domain_shift import DEFAULT_SHIFT, adapt, collect_sim_data, evaluate
from sim_gripper.sensor.forward import DomainShift


@pytest.fixture(scope="module")
def shifted():
    return collect_sim_data(DEFAULT_SHIFT, 8000, seed=0), collect_sim_data(DEFAULT_SHIFT, 3000, seed=50)


def test_shift_degrades_v4(models):
    clean = evaluate(models, collect_sim_data(DomainShift(), 3000, seed=50))
    shifted = evaluate(models, collect_sim_data(DEFAULT_SHIFT, 3000, seed=50))
    assert shifted["strain_r2"] < clean["strain_r2"]


def test_finetune_recovers(models, shifted):
    train, test = shifted
    assert evaluate(adapt("finetune", models, train), test)["strain_r2"] > evaluate(models, test)["strain_r2"]


def test_adapt_keeps_architecture(models, shifted):
    new = adapt("finetune", models, shifted[0])
    n = 0
    for k in ("gate", "expert_a", "expert_b"):
        assert new[k].hidden_layer_sizes == models[k].hidden_layer_sizes
        for a, b in zip(new[k].coefs_ + new[k].intercepts_, models[k].coefs_ + models[k].intercepts_):
            assert a.shape == b.shape
            n += a.size
    assert n == 1413


def test_finetuned_gate_keeps_noncontact(models, shifted):
    """그리퍼 데이터는 접촉 행이 다수 → 균형 없이 게이트를 fine-tune하면 개방 상태도 접촉으로 판정."""
    train, test = shifted
    m = adapt("finetune", models, train)
    free = test[test.contact == 0]
    assert evaluate(m, free)["gate_acc"] >= 0.9
