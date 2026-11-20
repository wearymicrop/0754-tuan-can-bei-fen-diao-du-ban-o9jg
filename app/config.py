import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TITLE = "团餐备份调度板"
PROJECT = "gb-0754"
RULESET = "gb-0754/1.0"
SIGNATURE_TITLE = "交接签单"
SAMPLES = {"dirty": "现场样例", "clean": "干净样例"}
MAX_ROWS = 2500


def database_path():
    return Path(os.getenv("WORKBENCH_DB", ROOT / "instance" / "workbench.sqlite3"))
