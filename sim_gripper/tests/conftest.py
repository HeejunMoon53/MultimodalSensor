import pickle
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

NEW_DIR = ROOT / "nn_decoupling" / "test0909_realtime" / "new"
PKL = NEW_DIR / "stm32_deploy_moe_v4" / "models.pkl"
BOARD_CSV = NEW_DIR / "moe_monitor_20260910_010437_test.csv"


@pytest.fixture(scope="session")
def models():
    with open(PKL, "rb") as f:
        return pickle.load(f)
