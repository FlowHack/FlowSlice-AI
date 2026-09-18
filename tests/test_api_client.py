"""Тесты потокового разбора SSE, выбора media_type и защиты от гонок генерации."""
from __future__ import annotations

import json

import pytest


def _sse(payload: dict) -> bytes:
    """Собирает строку SSE с полезной нагрузкой в кодировке UTF-8."""
    return ("data: " + json.dumps(payload) + "\n").encode("utf-8")


@pytest.fixture
def captured(engine, monkeypatch):
    """Перехватывает сообщения, отправляемые движком в UI."""
    messages: list[dict] = []
    monkeypatch.setattr(engine, "_post", messages.append)
    engine._gen = True
    return messages


def test_read_sse_collects_text_and_reasoning(engine, captured) -> None:
    """_read_sse() возвращает текст и reasoning_content, не падая на delta=None."""
    stream = [
        _sse({"choices": [{"delta": {"content": "Привет"}}]}),
        _sse({"choices": [{"delta": {"reasoning_content": "думаю"}}]}),
        _sse({"choices": [{"delta": None}]}),
        b"data: [DONE]\n",
    ]
    text, thought = engine._read_sse(iter(stream), 1)
    assert text == "Привет"
    assert thought == "думаю"


def test_read_sse_posts_contiguous_chunks(engine, captured, monkeypatch) -> None:
    """Между отправками копится ВСЁ: UI не получает куски вразнобой.

    При троттлинге пропущенные дельты должны уходить вместе со следующей
    отправкой, а не отдельным «хвостом» в конце — иначе текст в чате
    перемешивается и «досыпается» одним куском после завершения.
    """
    ticks = iter([1.0, 1.05, 1.16])
    monkeypatch.setattr(
        "flowslice_ai.engine.api_client.time.monotonic", lambda: next(ticks)
    )
    stream = [
        _sse({"choices": [{"delta": {"content": "A"}}]}),
        _sse({"choices": [{"delta": {"content": "B"}}]}),
        _sse({"choices": [{"delta": {"content": "C"}}]}),
        b"data: [DONE]\n",
    ]
    text, _ = engine._read_sse(iter(stream), 1)
    deltas = [m["text"] for m in captured if m.get("type") == "delta"]
    assert text == "ABC"
    assert deltas == ["A", "BC"]


def test_read_sse_tolerates_broken_chunks(engine, captured) -> None:
    """_read_sse() пропускает битые строки и завершает поток целиком."""
    stream = [
        b"data: {not json}\n",
        _sse({"choices": []}),
        _sse({"choices": [{"delta": {"content": "Хвост"}}]}),
        b"data: [DONE]\n",
    ]
    text, thought = engine._read_sse(iter(stream), 1)
    assert text == "Хвост"
    assert thought == ""


def test_read_sse_anthropic_reasoning_and_text(engine, captured) -> None:
    """_read_sse_anthropic() разделяет thinking_delta и обычный текст."""
    stream = [
        _sse(
            {
                "type": "content_block_delta",
                "delta": {"type": "thinking_delta", "thinking": "разбор"},
            }
        ),
        _sse(
            {
                "type": "content_block_delta",
                "delta": {"type": "text_delta", "text": "ответ"},
            }
        ),
    ]
    text, thought = engine._read_sse_anthropic(iter(stream), 1)
    assert text == "ответ"
    assert thought == "разбор"


def test_image_media_type_detects_data_uri(engine) -> None:
    """_image_media_type() берёт MIME из data-URI и иначе даёт image/jpeg."""
    assert engine._image_media_type("data:image/png;base64,AAAA") == "image/png"
    assert engine._image_media_type("data:image/webp;base64,AAAA") == "image/webp"
    assert engine._image_media_type("data:application/octet-stream;base64,AA") == "image/jpeg"
    assert engine._image_media_type("https://example.com/a.jpg") == "image/jpeg"


def test_start_generation_guards_against_race(engine, monkeypatch) -> None:
    """_start_generation() не запускает второй поток, если генерация уже идёт."""
    started: list[int] = []
    monkeypatch.setattr(
        "flowslice_ai.engine.generation.threading.Thread",
        lambda *args, **kwargs: type(
            "T", (), {"start": lambda self: started.append(1)}
        )(),
    )
    posts: list[dict] = []
    monkeypatch.setattr(engine, "_post", posts.append)
    engine._gen = True
    engine._start_generation(1, "привет", 1)
    assert not started
    assert posts and posts[0]["type"] == "toast"


def test_worker_stores_reasoning(engine, monkeypatch) -> None:
    """_worker() сохраняет reasoning в сообщении и в reply-payload."""
    engine._create_chat()
    chat = engine._active_chat()
    assert chat is not None
    posts: list[dict] = []
    monkeypatch.setattr(engine, "_post", posts.append)
    monkeypatch.setattr(engine, "_build_messages", lambda chat, text: [])
    monkeypatch.setattr(engine, "_call_api", lambda messages, chat_id: ("ответ", "мысль"))

    engine._worker(chat["id"], "вопрос", -1)

    saved = chat["msgs"][-1]
    assert saved["role"] == "assistant"
    assert saved["text"] == "ответ"
    assert saved["reasoning"] == "мысль"
    reply = [m for m in posts if m.get("type") == "reply"]
    assert reply and reply[0]["reasoning"] == "мысль"
    # В конце воркер шлёт полный state: экспорт чата читает текст из state.chats,
    # а не из DOM, поэтому финальный ответ обязан быть в свежем снимке.
    states = [m for m in posts if m.get("type") == "state"]
    assert states, "воркер обязан отправить state после генерации"
    sent_chat = next(c for c in states[-1]["chats"] if c["id"] == chat["id"])
    assert sent_chat["msgs"][-1]["text"] == "ответ"
