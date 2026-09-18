"""Тесты управления чатами движка: создание, обрезка, заголовки, сохранение."""
from __future__ import annotations

from flowslice_ai.constants import MAX_CHAT_MESSAGES


def test_create_chat(engine) -> None:
    """_create_chat() создаёт чат с id/title/msgs и делает его активным."""
    chat = engine._create_chat()
    assert "id" in chat
    assert "title" in chat
    assert "msgs" in chat
    assert engine._active_chat()["id"] == chat["id"]


def test_trim_chat(engine) -> None:
    """_trim_chat() обрезает историю до MAX_CHAT_MESSAGES."""
    chat = engine._create_chat()
    chat["msgs"] = [{"id": i, "role": "user", "text": "x"} for i in range(250)]
    engine._trim_chat(chat)
    assert len(chat["msgs"]) <= MAX_CHAT_MESSAGES


def test_auto_title(engine) -> None:
    """_auto_title() усекает длинный текст до 40 символов."""
    title = engine._auto_title("Длинный текст" * 20)
    assert len(title) <= 40


def test_chat_by_id(engine) -> None:
    """_chat_by_id() находит активный чат по его id."""
    chat_id = engine._active_chat()["id"]
    assert engine._chat_by_id(chat_id) is not None


def test_save_load_chats(engine) -> None:
    """_save_chats() пишет файл chats.json во временное хранилище."""
    from flowslice_ai.engine.core import CHATS_FILE

    engine._save_chats()
    assert CHATS_FILE.exists()