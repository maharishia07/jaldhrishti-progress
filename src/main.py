"""
main.py
-------
Jaldhrishti - Bot Entry Point
-------------------------------
Sets up logging, reads secrets from the environment / .env, initialises the
database, builds the Telegram Application, registers conversation handlers,
starts the daily EMI-reminder scheduler, and starts polling.

Usage:
    copy .env.example to .env and fill in BOT_TOKEN + GEMINI_API_KEY
    python -m src.main
"""

import logging
import os

from telegram.ext import Application

from src.config.settings import load_environment


def main() -> None:
    load_environment()
    # Load storage after .env so an explicit database path is honoured.
    from src.bot.handlers import register_handlers
    from src.services.scheduler.storage import init_db
    from src.services.scheduler.reminders import start_scheduler

    logging.basicConfig(
        format="%(asctime)s | %(levelname)-8s | %(name)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        level=logging.INFO,
    )
    logger = logging.getLogger(__name__)

    token = os.getenv("BOT_TOKEN")
    if not token:
        raise RuntimeError(
            "BOT_TOKEN environment variable is not set.\n"
            "Copy .env.example to .env and fill it in, or export it directly."
        )

    logger.info("Initialising database...")
    init_db()

    logger.info("Starting Jaldhrishti bot...")
    app = Application.builder().token(token).build()
    register_handlers(app)

    logger.info("Starting daily EMI reminder scheduler...")
    scheduler = start_scheduler(app.bot)

    try:
        # run_polling blocks until Ctrl-C
        app.run_polling(allowed_updates=["message"])
    finally:
        scheduler.shutdown()


if __name__ == "__main__":
    main()
