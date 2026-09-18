"""Тесты управления чатами движка: создание, обрезка, заголовки, сохранение."""
from __future__ import annotations

from flowslice_ai.constants import MAX_CHAT_MESSAGES


def test_create_chat(engine) -> None:
    """_create_chat() наполняет чат пустой историей и делает его активным."""
    chat = engine._create_chat()
    assert chat in engine._chats
    assert chat["msgs"] == []
    assert chat["title"] == ""
    assert engine._active_chat() is chat


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
    """_chat_by_id() возвращает именно запрошенный чат и None для чужого id."""
    chat = engine._active_chat()
    assert engine._chat_by_id(chat["id"]) is chat
    assert engine._chat_by_id(chat["id"] + 10_000) is None


def test_save_load_chats(engine) -> None:
    """_save_chats() пишет JSON, который _load_chats() читает обратно."""
    import json

    from flowslice_ai.engine.core import CHATS_FILE

    chat = engine._active_chat()
    chat["msgs"] = [{"id": 1, "role": "user", "text": "сохрани меня", "ts": 0}]
    engine._save_chats()

    payload = json.loads(CHATS_FILE.read_text(encoding="utf-8"))
    assert payload["active"] == chat["id"]
    assert payload["chats"][0]["msgs"][-1]["text"] == "сохрани меня"

    engine._chats = []
    engine._load_chats()
    restored = engine._active_chat()
    assert restored is not None
    assert restored["msgs"][-1]["text"] == "сохрани меня"


def test_fail_generation_keeps_user_message(engine) -> None:
    """_fail_generation() не удаляет запрос пользователя, помечая ответ ошибкой."""
    chat = engine._create_chat()
    chat["msgs"] = [
        {"id": 1, "role": "user", "text": "почему 429?"},
        {"id": 2, "role": "assistant", "text": ""},
    ]
    engine._fail_generation(chat, chat["id"], 2, "Ошибка API 429")
    users = [m for m in chat["msgs"] if m["role"] == "user"]
    assert len(users) == 1
    assert users[0]["text"] == "почему 429?"
    assistant = [m for m in chat["msgs"] if m["role"] == "assistant"][0]
    assert assistant["error"] is True
    assert assistant["text"] == "Ошибка API 429"


def test_history_skips_error_messages(engine) -> None:
    """_history_messages() не отправляет модели технические ошибки."""
    chat = engine._create_chat()
    chat["msgs"] = [
        {"id": 1, "role": "user", "text": "вопрос"},
        {"id": 2, "role": "assistant", "text": "Ошибка API 429", "error": True},
        {"id": 3, "role": "assistant", "text": "нормальный ответ"},
    ]
    history = engine._history_messages(chat, 100000, include_last_user=True)
    texts = [m["content"] for m in history]
    assert "Ошибка API 429" not in texts
    assert "нормальный ответ" in texts