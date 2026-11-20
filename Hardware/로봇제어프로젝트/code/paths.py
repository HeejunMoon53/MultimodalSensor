"""경로 상수와 sys.path 설정 (스크립트·테스트 공통)."""
import json
import sys
from pathlib import Path

CODE = Path(__file__).resolve().parent
PROJECT = CODE.parent
ROOT = CODE.parents[2]
OUT = PROJECT / "out"
PARAMS = CODE / "params.json"
for _p in (CODE, ROOT, ROOT / "Hardware" / "pneunet_gripper"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))


def load_params(path=PARAMS):
    return json.loads(Path(path).read_text(encoding="utf-8")) if Path(path).exists() else {}


def save_params(section, value, path=PARAMS):
    p = load_params(path)
    p[section] = value
    Path(path).write_text(json.dumps(p, indent=1, ensure_ascii=False), encoding="utf-8")
