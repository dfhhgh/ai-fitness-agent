"""Minimal Telegram bot entry point.

Constructs all dependencies, registers handlers, and starts polling.
Do NOT create new service/store instances per message.
"""

import logging
import os
import sys

from dotenv import load_dotenv

load_dotenv()


def main() -> None:
    """Initialize and run the Telegram bot."""
    # --- Logging configuration (must run before any imports that create loggers) ---
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        stream=sys.stderr,
    )
    # Keep third-party loggers at INFO to avoid noise
    logging.getLogger("httpx").setLevel(logging.INFO)
    logging.getLogger("httpcore").setLevel(logging.INFO)
    logging.getLogger("telegram").setLevel(logging.INFO)

    from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters

    from app.interview.controller import InterviewController
    from app.interview.service import InterviewService
    from app.llm.config import create_llm_client
    from app.llm.extractor import ProfileExtractor
    from app.storage.memory import InMemoryConversationStore
    from app.telegram.adapter import TelegramAdapter

    # --- Configuration ---
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    if not bot_token:
        print(
            "ERROR: TELEGRAM_BOT_TOKEN environment variable is required.\n"
            "Set it in your environment or .env file.",
            file=sys.stderr,
        )
        sys.exit(1)

    # --- Build dependency graph (shared for bot lifetime) ---
    llm_client = create_llm_client()
    extractor = ProfileExtractor(llm_client)
    controller = InterviewController(extractor)
    store = InMemoryConversationStore()
    service = InterviewService(controller, store)
    adapter = TelegramAdapter(service)

    # --- Build Telegram Application ---
    app = ApplicationBuilder().token(bot_token).build()

    app.add_handler(CommandHandler("start", adapter.handle_start))
    app.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, adapter.handle_message)
    )

    print("Bot started. Press Ctrl+C to stop.")
    app.run_polling()


if __name__ == "__main__":
    main()
