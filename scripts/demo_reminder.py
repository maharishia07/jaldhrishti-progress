"""Offline reminder-data demo. Never sends Telegram messages or uses the user DB.

Run: python -m scripts.demo_reminder
This checks storage/query/marking only; it does not exercise the legacy sender.
"""

from datetime import date
from pathlib import Path
from tempfile import TemporaryDirectory


def main() -> None:
    from src.services.scheduler import storage
    original = storage.DB_PATH
    try:
        with TemporaryDirectory(prefix="jaldhrishti-demo-") as directory:
            storage.DB_PATH = str(Path(directory) / "demo.db")
            storage.init_db()
            today = date.today().isoformat()
            storage.save_user_loan(1, {"repayment_schedule": [
                {"quarter": 1, "emi": 13500.0, "due_date": today}
            ]}, today)
            due = storage.get_due_today()
            assert len(due) == 1 and due[0]["emi"] == 13500.0
            storage.mark_reminded(1, 1)
            assert storage.get_due_today() == []
            print("PASS: isolated reminder storage demo; no messages sent.")
    finally:
        storage.DB_PATH = original


if __name__ == "__main__":
    main()
