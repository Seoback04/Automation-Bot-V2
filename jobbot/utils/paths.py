from __future__ import annotations

from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT_DIR / "data"
CONFIG_DIR = DATA_DIR / "config"
GENERATED_DIR = DATA_DIR / "generated"
LOGS_DIR = DATA_DIR / "logs"
RESUMES_DIR = DATA_DIR / "resumes"
RUNS_DIR = DATA_DIR / "runs"
BROWSER_PROFILE_DIR = DATA_DIR / "browser-profile"


def ensure_data_directories() -> None:
    for path in (
        DATA_DIR,
        CONFIG_DIR,
        GENERATED_DIR,
        LOGS_DIR,
        RESUMES_DIR,
        RUNS_DIR,
        BROWSER_PROFILE_DIR,
    ):
        path.mkdir(parents=True, exist_ok=True)
