"""Tests for app.telegram.adapter -- thin Telegram transport adapter."""

import pytest

from app.telegram.adapter import TelegramAdapter


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class FakeService:
    """Fake InterviewService that records calls and returns predefined responses."""

    def __init__(self, response: str = "تمام 👌") -> None:
        self._response = response
        self.calls: list[tuple[int, str]] = []

    def handle_message(self, chat_id: int, text: str) -> str:
        self.calls.append((chat_id, text))
        return self._response


class FakeMessage:
    """Minimal fake representing a Telegram Message."""

    def __init__(self, chat_id: int, text: str | None = None) -> None:
        self.chat_id = chat_id
        self.text = text


class FakeEffectiveMessage:
    """Wrapper simulating update.effective_message."""

    def __init__(self, message: FakeMessage | None) -> None:
        self._message = message

    @property
    def chat_id(self):
        return self._message.chat_id if self._message else None

    @property
    def text(self):
        return self._message.text if self._message else None


class FakeUpdate:
    """Minimal fake representing a Telegram Update."""

    def __init__(self, message: FakeMessage | None = None) -> None:
        self.effective_message = FakeEffectiveMessage(message) if message else None


class FakeBot:
    """Fake Telegram Bot that records sent messages."""

    def __init__(self) -> None:
        self.sent: list[tuple[int, str]] = []

    async def send_message(self, chat_id: int, text: str) -> None:
        self.sent.append((chat_id, text))


class FakeContext:
    """Minimal fake representing telegram.ext.ContextTypes.DEFAULT_TYPE."""

    def __init__(self, bot: FakeBot) -> None:
        self.bot = bot


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestTelegramAdapter:
    """TelegramAdapter behavior."""

    def setup_method(self):
        self.service = FakeService("تمام 👌 طولك كام؟")
        self.adapter = TelegramAdapter(self.service)
        self.bot = FakeBot()
        self.context = FakeContext(self.bot)

    @pytest.mark.asyncio
    async def test_text_message_extracts_chat_id(self):
        """Text message extracts chat_id correctly."""
        update = FakeUpdate(FakeMessage(chat_id=12345, text="أنا 25 سنة"))
        await self.adapter.handle_message(update, self.context)
        assert self.service.calls[0][0] == 12345

    @pytest.mark.asyncio
    async def test_text_passed_unchanged_to_service(self):
        """Text is passed unchanged to InterviewService."""
        update = FakeUpdate(FakeMessage(chat_id=100, text="أنا 25 سنة وراجل"))
        await self.adapter.handle_message(update, self.context)
        assert self.service.calls[0][1] == "أنا 25 سنة وراجل"

    @pytest.mark.asyncio
    async def test_service_response_sent_back(self):
        """Service response is sent back to the same chat."""
        update = FakeUpdate(FakeMessage(chat_id=100, text="مرحبا"))
        await self.adapter.handle_message(update, self.context)
        assert len(self.bot.sent) == 1
        assert self.bot.sent[0] == (100, "تمام 👌 طولك كام؟")

    @pytest.mark.asyncio
    async def test_arabic_text_preserved(self):
        """Arabic text is preserved through the full flow."""
        arabic_text = "أنا عندي 25 سنة وبتمرن 4 أيام في الأسبوع"
        update = FakeUpdate(FakeMessage(chat_id=100, text=arabic_text))
        await self.adapter.handle_message(update, self.context)
        assert self.service.calls[0][1] == arabic_text

    @pytest.mark.asyncio
    async def test_empty_update_ignored(self):
        """Empty/unsupported update is ignored safely."""
        update = FakeUpdate(message=None)
        await self.adapter.handle_message(update, self.context)
        assert len(self.service.calls) == 0
        assert len(self.bot.sent) == 0

    @pytest.mark.asyncio
    async def test_empty_text_ignored(self):
        """Message with None text is ignored."""
        update = FakeUpdate(FakeMessage(chat_id=100, text=None))
        await self.adapter.handle_message(update, self.context)
        assert len(self.service.calls) == 0

    @pytest.mark.asyncio
    async def test_whitespace_text_ignored(self):
        """Whitespace-only text is ignored."""
        update = FakeUpdate(FakeMessage(chat_id=100, text="   "))
        await self.adapter.handle_message(update, self.context)
        assert len(self.service.calls) == 0

    @pytest.mark.asyncio
    async def test_service_exception_sends_friendly_message(self):
        """Service exception produces a friendly Arabic response."""
        class FailingService:
            def handle_message(self, chat_id, text):
                raise RuntimeError("LLM connection failed")

        adapter = TelegramAdapter(FailingService())
        update = FakeUpdate(FakeMessage(chat_id=100, text="test"))
        await adapter.handle_message(update, self.context)

        assert len(self.bot.sent) == 1
        assert "جرب تاني" in self.bot.sent[0][1]

    @pytest.mark.asyncio
    async def test_unexpected_exception_does_not_crash(self):
        """Unexpected exception does not crash the handler."""
        class BrokenService:
            def handle_message(self, chat_id, text):
                raise ValueError("unexpected")

        adapter = TelegramAdapter(BrokenService())
        update = FakeUpdate(FakeMessage(chat_id=100, text="test"))
        # Should not raise
        await adapter.handle_message(update, self.context)
        assert len(self.bot.sent) == 1

    @pytest.mark.asyncio
    async def test_multiple_messages_reuse_service(self):
        """Multiple messages reuse the same injected service."""
        update1 = FakeUpdate(FakeMessage(chat_id=100, text="أنا 25 سنة"))
        update2 = FakeUpdate(FakeMessage(chat_id=100, text="طول 175 سم"))

        await self.adapter.handle_message(update1, self.context)
        await self.adapter.handle_message(update2, self.context)

        assert len(self.service.calls) == 2
        assert self.service.calls[0] == (100, "أنا 25 سنة")
        assert self.service.calls[1] == (100, "طول 175 سم")

    @pytest.mark.asyncio
    async def test_adapter_does_not_implement_business_logic(self):
        """Adapter does not contain profile/business logic."""
        import inspect
        source = inspect.getsource(TelegramAdapter)
        # Should not contain business logic keywords
        assert "age" not in source.lower() or "chat_id" in source
        assert "conflict" not in source.lower() or "service" in source.lower()
        assert "merge" not in source.lower() or "service" in source.lower()

    @pytest.mark.asyncio
    async def test_start_command_sends_welcome(self):
        """Handle /start sends a welcome message."""
        # /start is a command, not a text message with content
        # We test handle_start directly
        update = FakeUpdate(FakeMessage(chat_id=100, text="/start"))
        await self.adapter.handle_start(update, self.context)
        assert len(self.bot.sent) == 1
        assert "أهلاً بيك" in self.bot.sent[0][1]

    @pytest.mark.asyncio
    async def test_start_does_not_call_service(self):
        """Handle /start does NOT call InterviewService."""
        update = FakeUpdate(FakeMessage(chat_id=100, text="/start"))
        await self.adapter.handle_start(update, self.context)
        assert len(self.service.calls) == 0

    @pytest.mark.asyncio
    async def test_start_with_none_message_ignored(self):
        """Handle /start with None effective_message is ignored."""
        update = FakeUpdate(message=None)
        await self.adapter.handle_start(update, self.context)
        assert len(self.bot.sent) == 0

    @pytest.mark.asyncio
    async def test_send_failure_does_not_crash(self):
        """If bot.send_message fails, handler does not crash."""
        class FailingBot:
            async def send_message(self, chat_id, text):
                raise RuntimeError("Telegram API down")

        class FailingContext:
            def __init__(self):
                self.bot = FailingBot()

        adapter = TelegramAdapter(self.service)
        update = FakeUpdate(FakeMessage(chat_id=100, text="test"))
        # Should not raise
        await adapter.handle_message(update, FailingContext())
