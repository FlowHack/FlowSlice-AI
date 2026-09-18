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


def test_collect_context_images_keeps_all_current(engine) -> None:
    """Все изображения текущего сообщения отправляются, история — ограниченно."""
    chat = {
        "msgs": [
            {
                "role": "user",
                "text": "старое",
                "attachments": [{"image": "data:image/jpeg;base64,OLD"}],
            },
            {"role": "assistant", "text": "ок"},
            {
                "role": "user",
                "text": "новое",
                "attachments": [
                    {"image": "data:image/jpeg;base64,A"},
                    {"image": "data:image/jpeg;base64,B"},
                    {"image": "data:image/jpeg;base64,C"},
                ],
            },
        ]
    }
    result = engine._collect_context_images(chat)
    assert result[:3] == [
        "data:image/jpeg;base64,A",
        "data:image/jpeg;base64,B",
        "data:image/jpeg;base64,C",
    ]
    assert "data:image/jpeg;base64,OLD" in result
    assert len(result) == 4


def test_build_messages_adds_image_hints(engine, monkeypatch) -> None:
    """При наличии изображения промпт требует разбор дефектов печати."""
    chat = engine._active_chat()
    engine._config["language"] = "en"
    monkeypatch.setattr(engine, "_model_supports_images", lambda: True)
    chat["msgs"] = [
        {
            "id": 1,
            "role": "user",
            "text": "что не так с печатью?",
            "ts": 0,
            "attachments": [{"image": "data:image/jpeg;base64,AAAA", "name": "a.jpg"}],
        }
    ]
    messages = engine._build_messages(chat, "что не так с печатью?")
    system = messages[0]["content"]
    assert "Visually analyze the defects" in system
    assert "cannot process images" not in system


def test_build_messages_unknown_vision_adds_both_hints(engine, monkeypatch) -> None:
    """Если зрение модели неизвестно, картинка уходит, но добавляется обе подсказки."""
    chat = engine._active_chat()
    engine._config["language"] = "en"
    monkeypatch.setattr(engine, "_model_supports_images", lambda: None)
    chat["msgs"] = [
        {
            "id": 1,
            "role": "user",
            "text": "что не так?",
            "ts": 0,
            "attachments": [{"image": "data:image/jpeg;base64,AAAA", "name": "a.jpg"}],
        }
    ]
    messages = engine._build_messages(chat, "что не так?")
    system = messages[0]["content"]
    assert "Visually analyze the defects" in system
    assert "cannot process images" in system
    user = messages[-1]["content"]
    assert isinstance(user, list)


def test_build_messages_no_vision_model_skips_images(engine) -> None:
    """Модель без зрения: картинки не уходят, промпт просит честно об этом сказать."""
    chat = engine._active_chat()
    engine._config["language"] = "en"
    # deepseek-chat по умолчанию помечен vision: false.
    assert engine._model_supports_images() is False
    chat["msgs"] = [
        {
            "id": 1,
            "role": "user",
            "text": "что не так с печатью?",
            "ts": 0,
            "attachments": [{"image": "data:image/jpeg;base64,AAAA", "name": "a.jpg"}],
        }
    ]
    messages = engine._build_messages(chat, "что не так с печатью?")
    system = messages[0]["content"]
    assert "cannot process images" in system
    assert "Visually analyze the defects" not in system
    user = messages[-1]["content"]
    user_text = user if isinstance(user, str) else json.dumps(user, ensure_ascii=False)
    assert "data:image/jpeg;base64,AAAA" not in user_text


def test_build_messages_without_images_has_no_hints(engine) -> None:
    """Без изображений подсказки про анализ дефектов в промпт не попадают."""
    chat = engine._active_chat()
    engine._config["language"] = "en"
    chat["msgs"] = [{"id": 1, "role": "user", "text": "привет", "ts": 0}]
    messages = engine._build_messages(chat, "привет")
    system = messages[0]["content"]
    assert "Visually analyze the defects" not in system
    assert "cannot process images" not in system


def test_parse_vision_payload_formats(engine) -> None:
    """Разбор ответов провайдеров во всех известных форматах признака зрения."""
    payload = {
        "data": [
            {"id": "a", "architecture": {"input_modalities": ["text", "image"]}},
            {"id": "b", "input_modalities": ["text"]},
            {"id": "c", "capabilities": {"vision": True}},
            {"id": "d", "capabilities": {"image_input": {"supported": False}}},
            {"id": "e"},
        ]
    }
    result = engine._parse_vision_payload(payload)
    assert result == {"a": True, "b": False, "c": True, "d": False}


def test_parse_vision_payload_xai_models_key(engine) -> None:
    """xAI отдаёт список в поле models, а не data."""
    result = engine._parse_vision_payload(
        {"models": [{"id": "grok-3", "input_modalities": ["text", "image"]}]}
    )
    assert result == {"grok-3": True}


def test_test_key_worker_uses_selected_provider(engine, monkeypatch) -> None:
    """Проверка ключа уходит на эндпоинт выбранного провайдера, а не активного."""
    engine._config["active_provider"] = "deepseek"
    engine._config["active_model"] = "deepseek-chat"
    calls = []

    class _Resp:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def read(self):
            return b"{}"

    def fake_urlopen(request, timeout=0):
        calls.append(request)
        return _Resp()

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    engine._test_key_worker("test-key", "openrouter")
    assert len(calls) == 1
    assert calls[0].full_url.startswith("https://openrouter.ai/api/v1/")
    assert calls[0].get_header("Authorization") == "Bearer test-key"
    body = json.loads(calls[0].data.decode("utf-8"))
    assert body["model"] in engine._config["providers"]["openrouter"]["models"]


def test_vision_requires_text_output(engine) -> None:
    """Зрение = image+text на входе и text на выходе; image-генерация не мешает."""
    payload = {
        "data": [
            # Гибрид: умеет и рисовать, но и отвечает текстом — подходит.
            {
                "id": "hybrid",
                "architecture": {
                    "input_modalities": ["image", "text"],
                    "output_modalities": ["image", "text"],
                },
            },
            # Отдаёт только изображения — для анализа не подходит.
            {
                "id": "image-only",
                "architecture": {
                    "input_modalities": ["image", "text"],
                    "output_modalities": ["image"],
                },
            },
            # Без приёма текста промпт отправить нечем.
            {
                "id": "image-in-only",
                "architecture": {
                    "input_modalities": ["image"],
                    "output_modalities": ["text"],
                },
            },
        ]
    }
    result = engine._parse_vision_payload(payload)
    assert result == {"hybrid": True, "image-only": False, "image-in-only": False}


def test_http_error_detail_extracts_message(engine) -> None:
    """Текст ошибки HTTP извлекается из тела ответа для показа в UI."""
    import io
    import urllib.error

    def make(body: bytes) -> urllib.error.HTTPError:
        return urllib.error.HTTPError("u", 403, "Forbidden", {}, io.BytesIO(body))

    assert engine._http_error_detail(
        make(b'{"error":{"message":"Access denied by security policy."}}')
    ) == "Access denied by security policy."
    assert engine._http_error_detail(make(b'{"error":"nope"}')) == "nope"
    assert engine._http_error_detail(make(b"plain text")) == "plain text"
    assert engine._http_error_detail(make(b"")) == ""
