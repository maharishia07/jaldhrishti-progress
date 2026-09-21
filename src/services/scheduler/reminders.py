"""
scheduler/reminders.py
=======================
Daily reminder engine for the Jaldhrishti loan-repayment bot.

Public API
----------
run_daily_check(bot)
    Query instalments due today, send Telegram messages, mark reminded.
    Can be called DIRECTLY for a live demo without waiting for the cron.

start_scheduler(bot) -> BackgroundScheduler
    Wire run_daily_check into APScheduler (daily 08:00 IST).
    Returns the scheduler so callers can .shutdown() it later.

Demo (standalone)
-----------------
    from src.services.scheduler.storage import init_db, save_user_loan
    from src.services.scheduler.reminders import run_daily_check
    import telegram, datetime

    bot = telegram.Bot(token="YOUR_TOKEN")
    init_db()
    today = datetime.date.today().isoformat()
    save_user_loan(
        chat_id=123456789,
        financial_plan={
            "repayment_schedule": [
                {"quarter": 1, "emi": 5000.0, "due_date": today}
            ]
        },
        start_date=today,
    )
    run_daily_check(bot)   # message arrives in Telegram immediately
"""

import logging

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from src.services.scheduler.storage import get_due_today, mark_reminded, init_db

logger = logging.getLogger(__name__)

# Telegram MarkdownV2 reminder template.
# MarkdownV2 requires escaping: ! . ( ) - + = | { } # with backslash.
_TEMPLATE = (
    "\U0001f4b0 *Jaldhrishti Loan Reminder*\n\n"
    "Namaste\\! Your quarterly EMI is due today\\.\n\n"
    "\U0001f4c5 *Due Date:* {due_date}\n"
    "\U0001f4b3 *Quarter:* {quarter}\n"
    "\U0001f4b8 *Amount:* \u20b9{emi:,.2f}\n\n"
    "Please ensure timely repayment to maintain a good credit record\\."
)


def run_daily_check(bot) -> None:
    """
    Core reminder function.

    1. Calls get_due_today() -- fetches all unreminded instalments due today.
    2. Sends a Telegram MarkdownV2 message to each chat_id.
    3. Calls mark_reminded() so the instalment is never double-sent.

    Parameters
    ----------
    bot : telegram.Bot
        An authenticated python-telegram-bot Bot instance.

    Notes
    -----
    * Callable at any time -- does NOT depend on APScheduler.
    * On send failure the error is logged and mark_reminded() is NOT called,
      so the reminder will be retried on the next call.
    """
    init_db()
    due_loans = get_due_today()

    if not due_loans:
        logger.info("[reminders] No EMIs due today.")
        return

    logger.info("[reminders] %d instalment(s) due today.", len(due_loans))

    for loan in due_loans:
        chat_id  = loan["chat_id"]
        quarter  = loan["quarter"]
        emi      = loan["emi"]
        due_date = loan["due_date"]

        def _escape(text: str) -> str:
            """Escape special chars for Telegram MarkdownV2."""
            for ch in r"\_*[]()~`>#+-=|{}.!":
                text = text.replace(ch, f"\\{ch}")
            return text

        text = _TEMPLATE.format(
            due_date=_escape(due_date),
            quarter=_escape(str(quarter)),
            emi=f"{emi:,.2f}",
        )
        try:
            bot.send_message(chat_id=chat_id, text=text, parse_mode="MarkdownV2")
            mark_reminded(chat_id, quarter)
            logger.info(
                "[reminders] Sent  chat_id=%s  quarter=%s  emi=%.2f",
                chat_id, quarter, emi,
            )
        except Exception as exc:  # noqa: BLE001
            logger.error(
                "[reminders] FAILED  chat_id=%s  quarter=%s: %s",
                chat_id, quarter, exc,
            )


def start_scheduler(bot) -> BackgroundScheduler:
    """
    Create and start a BackgroundScheduler that fires run_daily_check
    every day at 08:00 IST.

    Parameters
    ----------
    bot : telegram.Bot

    Returns
    -------
    BackgroundScheduler
        Call .shutdown() to stop gracefully when the process exits.

    Example
    -------
        scheduler = start_scheduler(bot)
        # ... rest of bot setup ...
        scheduler.shutdown()
    """
    scheduler = BackgroundScheduler(timezone="Asia/Kolkata")
    scheduler.add_job(
        func=run_daily_check,
        trigger=CronTrigger(hour=8, minute=0, timezone="Asia/Kolkata"),
        args=[bot],
        id="daily_emi_reminder",
        name="Daily EMI Reminder",
        replace_existing=True,
        misfire_grace_time=3600,   # fire even if delayed up to 1 h (e.g. restart)
    )
    scheduler.start()
    logger.info("[reminders] APScheduler started -- daily EMI reminders at 08:00 IST.")
    return scheduler
