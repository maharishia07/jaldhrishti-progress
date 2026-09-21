"""Project paths and explicit startup configuration; importing has no side effects."""

import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
INPUT_DIR = PROJECT_ROOT / "data" / "input"
OUTPUT_DIR = PROJECT_ROOT / "data" / "output"
SCHEME_RULES_PATH = PROJECT_ROOT / "src" / "services" / "engine" / "scheme_rules.json"


def load_environment() -> None:
    """Read only this checkout's .env; never overwrite exported credentials."""
    from dotenv import load_dotenv
    load_dotenv(PROJECT_ROOT / ".env", override=False)


def database_path() -> str:
    """Preserve explicit paths and existing legacy data without moving private files.

    Relative JALDHRISHTI_DB values retain their original current-directory meaning.
    For a fresh checkout, private runtime data belongs under data/output.
    """
    configured = os.environ.get("JALDHRISHTI_DB")
    if configured:
        return configured
    legacy = PROJECT_ROOT / "scheduler" / "jaldhrishti.db"
    if legacy.exists():
        return str(legacy)
    return str(OUTPUT_DIR / "jaldhrishti.db")
