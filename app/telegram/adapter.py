"""Thin Telegram adapter bridging Telegram Bot API to InterviewService.

This module is ONLY a transport adapter. It contains NO business logic,
NO profile extraction, NO conflict detection, NO LLM calls.

It receives Telegram updates, extracts chat_id + text, calls
InterviewService.handle_message(), and sends the response back.
"""

import logging
from typing import Optional

from telegram import Update
from telegram.ext import ContextTypes

from app.interview.service import InterviewService

logger = logging.getLogger(__name__)


class TelegramAdapter:
    """Thin adapter between Telegram Bot API and InterviewService.

    Responsibilities:
    - Extract chat_id and text from Telegram Update
    - Call InterviewService.handle_message(chat_id, text)
    - Send the returned response back to the same chat
    - Handle errors gracefully without crashing the bot
    """

    def __init__(self, service: InterviewService) -> None:
        self._service = service

    async def handle_message(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
    ) -> None:
        """Handle an incoming Telegram text message.

        Extracts chat_id and text, calls the service, and sends the response.
        Never raises — catches exceptions and sends a friendly error message.
        """
        if update.effective_message is None:
            return

        message = update.effective_message
        chat_id = message.chat_id
        text = message.text

        if text is None or not text.strip():
            return

        try:
            response = self._service.handle_message(chat_id, text)
        except Exception:
            logger.exception("Error processing message from chat %s", chat_id)
            response = "حصل مشكلة. جرب تاني."

        try:
            await context.bot.send_message(
                chat_id=chat_id,
                text=response,
            )
        except Exception:
            logger.exception("Failed to send message to chat %s", chat_id)

    async def handle_start(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
    ) -> None:
        """Handle the /start command.

        Sends a welcome message without initializing any profile fields.
        The actual onboarding begins with the user's first text message.
        """
        if update.effective_message is None:
            return

        chat_id = update.effective_message.chat_id
        welcome = "أهلاً بيك 👋 خلينا نبدأ، عرفني عن سنك ونوعك."

        try:
            await context.bot.send_message(
                chat_id=chat_id,
                text=welcome,
            )
        except Exception:
            logger.exception("Failed to send /start response to chat %s", chat_id)
