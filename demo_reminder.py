#!/usr/bin/env python3
"""
demo_reminder.py
================
Standalone demo -- proves the full reminder flow WITHOUT waiting for a
real cron tick.

Steps performed
---------------
1. Initialise the SQLite database (creates jaldhrishti.db next to this file).
2. Insert a dummy loan whose Q1 due-date is TODAY.
3. Call run_daily_check() with a real Telegram Bot object.
4. A Telegram message should arrive in your chat immediately.

Usage
-----
    set TELEGRAM_TOKEN=123456:ABCDEFG...
    set TELEGRAM_CHAT_ID=987654321
    python demo_reminder.py
"""

import logging
import os
from datetime import date

import telegram

from scheduler.storage import init_db, save_user_loan
from scheduler.reminders import run_daily_check

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
)

TOKEN   = os.environ.get("TELEGRAM_TOKEN",   "REPLACE_ME")
CHAT_ID = int(os.environ.get("TELEGRAM_CHAT_ID", "0"))

if TOKEN == "REPLACE_ME" or CHAT_ID == 0:
    raise SystemExit(
        "ERROR: Set TELEGRAM_TOKEN and TELEGRAM_CHAT_ID env-vars before running."
    )

# 1. DB setup
init_db()
print("OK  Database initialised.")

# 2. Insert loan due today
today = date.today().isoformat()
save_user_loan(
    chat_id=CHAT_ID,
    financial_plan={
        "loan_amount": 50000,
        "annual_interest_rate": 12.0,
        "duration_quarters": 4,
        "repayment_schedule": [
            {"quarter": 1, "emi": 13500.00, "due_date": today},
            {"quarter": 2, "emi": 13500.00, "due_date": "2026-12-07"},
            {"quarter": 3, "emi": 13500.00, "due_date": "2027-03-07"},
            {"quarter": 4, "emi": 13500.00, "due_date": "2027-06-07"},
        ],
    },
    start_date=today,
)
print(f"OK  Loan saved -- Q1 due_date = {today} (today).")

# 3. Fire reminders immediately (no scheduler needed)
bot = telegram.Bot(token=TOKEN)
print(">>  Calling run_daily_check() ...")
run_daily_check(bot)
print("OK  Done. Check your Telegram.")
