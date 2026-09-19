"""Тесты диспетчера UI-сообщений, чатовых хендлеров и сжатия истории.

Покрывают ранее непроверенные участки: маршрутизацию `_dispatch_message`,
операции с чатами, перегенерацию/варианты, ручное сжатие и устойчивость
статистики к повреждённому конфигу.
"""
from __future__ import annotations

import time

from flowslice_ai.constants import COMPACT_KEEP_MESSAGES, CONTEXT_OPTIONS


def _posts_of(posts: list[dict], msg_type: str) -> list[dict]:
    """Возвращает все отправленные сообщения указанного типа."""
    return [item for item in posts if item.get("type") == msg_type]


def _fill_msgs(engine, count: int) -> dict:
    """Создаёт чат с count сообщениями (попеременно user/assistant)."""
    chat = engine._active_chat()
    msgs: list[dict] = []
    for index in range(count):
        role = "user" if index % 2 == 0 else "assistant"
        text = f"сообщение {index} " * 3
        msgs.append({"id": index + 1, "role": role, "text": text, "ts": 0})
    chat["msgs"] = msgs
    chat["summary_count"] = 0
    return chat


# ===== Диспетчер =====


def test_dispatch_get_state_posts_state(engine, monkeypatch) -> None:
    """get_state маршрутизируется в _handle_get_state и присылает state."""
    posts: list[dict] = []
    monkeypatch.setattr(engine, "_post", posts.append)
    engine._dispatch_message({"type": "get_state"})
    assert _posts_of(posts, "state")


def test_dispatch_unknown_type_does_not_raise(engine) -> None:
    """Неизвестный тип сообщения логируется, но не роняет движок."""
    engine.handle_message({"type": "definitely-unknown"})


def test_handle_message_swallows_handler_errors(engine, monkeypatch) -> None:
    """Ошибка внутри обработчика логируется и не выходит наружу."""
    def _boom(_message: dict) -> None:
        """Имитация падения обработчика."""
        raise RuntimeError("boom")

    monkeypatch.setattr(engine, "_dispatch_message", _boom)
    engine.handle_message({"type": "chat"})


def test_dispatch_non_dict_message(engine, monkeypatch) -> None:
    """Некорректный по типу payload приводится к строке и не ломает движок."""
    monkeypatch.setattr(engine, "_start_generation", lambda *args: None)
    engine.handle_message({"type": "chat", "text": 123})
    msgs = engine._active_chat()["msgs"]
    assert msgs and msgs[-1]["text"] == "123"


# ===== Чатовые хендлеры =====


def test_new_chat_adds_chat(engine) -> None:
    """new_chat создаёт новый активный чат."""
    before = len(engine._chats)
    engine._handle_new_chat()
    assert len(engine._chats) == before + 1
    assert engine._active == engine._chats[-1]["id"]


def test_new_chat_rejected_while_generating(engine, monkeypatch) -> None:
    """Во время генерации новый чат не создаётся, показывается тост."""
    posts: list[dict] = []
    monkeypatch.setattr(engine, "_post", posts.append)
    engine._gen = True
    before = len(engine._chats)
    engine._handle_new_chat()
    assert len(engine._chats) == before
    assert _posts_of(posts, "toast")


def test_clear_chats_rejected_while_generating(engine) -> None:
    """clear_chats не стирает историю во время генерации."""
    engine._handle_new_chat()
    engine._gen = True
    before = len(engine._chats)
    engine._handle_clear_chats()
    assert len(engine._chats) == before


def test_delete_chat_removes_and_keeps_active(engine) -> None:
    """delete_chat удаляет чат и переключает активный на оставшийся."""
    engine._handle_new_chat()
    victim = engine._active
    keeper = engine._chats[0]["id"]
    engine._handle_new_chat()
    engine._handle_delete_chat({"id": victim})
    assert all(chat["id"] != victim for chat in engine._chats)
    assert engine._active in [chat["id"] for chat in engine._chats]
    assert keeper in [chat["id"] for chat in engine._chats]


def test_delete_last_chat_recreates_empty(engine) -> None:
    """Удаление единственного чата создаёт новый пустой."""
    engine._handle_delete_chat({"id": engine._active})
    assert len(engine._chats) == 1
    assert engine._active_chat()["msgs"] == []


def test_rename_chat_truncates_title(engine) -> None:
    """rename_chat сохраняет заголовок и обрезает его до 60 символов."""
    engine._handle_rename_chat({"id": engine._active, "title": "  " + "x" * 100})
    title = engine._active_chat()["title"]
    assert title.startswith("x")
    assert len(title) <= 60


def test_rename_unknown_chat_is_ignored(engine) -> None:
    """rename_chat по несуществующему id ничего не меняет."""
    engine._handle_rename_chat({"id": 99999, "title": "нет"})
    assert engine._active_chat().get("title", "") == ""


def test_toggle_pin(engine) -> None:
    """toggle_pin инвертирует признак закрепления."""
    assert not engine._active_chat().get("pinned", False)
    engine._handle_toggle_pin({"id": engine._active})
    assert engine._active_chat()["pinned"] is True
    engine._handle_toggle_pin({"id": engine._active})
    assert engine._active_chat()["pinned"] is False


def test_pick_chat_switches_active(engine) -> None:
    """pick_chat переключает активный чат по id."""
    engine._handle_new_chat()
    first = engine._chats[0]["id"]
    engine._handle_pick_chat({"id": first})
    assert engine._active == first


def test_stop_resets_generation_state(engine, monkeypatch) -> None:
    """stop сбрасывает генерацию/сжатие, будит поток и шлёт пустой статус."""
    posts: list[dict] = []
    monkeypatch.setattr(engine, "_post", posts.append)
    engine._gen = True
    engine._compacting = True
    engine._cancel_event.clear()
    engine._handle_stop()
    assert engine._gen is False
    assert engine._compacting is False
    assert engine._cancel_event.is_set()
    statuses = _posts_of(posts, "status")
    assert statuses and statuses[-1]["text"] == ""


def test_context_flags_normalized(engine) -> None:
    """set_context_flags оставляет только известные ключи и режимы."""
    engine._handle_context_flags(
        {
            "flags": {"filament": False, "bogus": True},
            "modes": {"printer": "all", "print": "unknown", "model": "deep"},
        }
    )
    chat = engine._active_chat()
    assert set(chat["context_flags"]) == set(CONTEXT_OPTIONS)
    assert chat["context_flags"]["filament"] is False
    assert chat["context_modes"]["printer"] == "all"
    assert chat["context_modes"]["print"] == "changed"
    assert chat["context_modes"]["model"] == "deep"
    assert engine._config["context"]["flags"]["filament"] is False


def test_context_flags_ignores_non_dict(engine) -> None:
    """Некорректные flags не меняют состояние чата."""
    before = dict(engine._active_chat()["context_flags"])
    engine._handle_context_flags({"flags": "broken"})
    assert engine._active_chat()["context_flags"] == before


# ===== Перегенерация и варианты =====


def test_regenerate_collects_variants(engine, monkeypatch) -> None:
    """regenerate сохраняет прошлые ответы как варианты и убирает их из истории."""
    calls: list[tuple] = []
    monkeypatch.setattr(engine, "_start_generation", lambda *args: calls.append(args))
    chat = _fill_msgs(engine, 4)
    chat["msgs"][3]["text"] = "прошлый ответ"
    engine._handle_regenerate()
    assert len(chat["msgs"]) == 3
    assert chat["msgs"][-1]["role"] == "user"
    assert engine._pending_variants[chat["id"]][0]["text"] == "прошлый ответ"
    assert calls and calls[0][1] == chat["msgs"][-1]["text"]


def test_switch_variant_changes_text(engine) -> None:
    """switch_variant подменяет текст и reasoning по индексу варианта."""
    chat = engine._active_chat()
    chat["msgs"] = [
        {"id": 1, "role": "user", "text": "вопрос", "ts": 0},
        {
            "id": 2,
            "role": "assistant",
            "text": "вариант A",
            "ts": 0,
            "variants": [
                {"text": "вариант A", "reasoning": "мысль A"},
                {"text": "вариант B", "reasoning": "мысль B"},
            ],
            "variant_index": 0,
        },
    ]
    engine._handle_switch_variant({"chat_id": chat["id"], "index": 1})
    msg = chat["msgs"][1]
    assert msg["text"] == "вариант B"
    assert msg["reasoning"] == "мысль B"
    assert msg["variant_index"] == 1
    engine._handle_switch_variant({"chat_id": chat["id"], "index": 99})
    assert chat["msgs"][1]["text"] == "вариант B"


def test_switch_variant_no_target(engine) -> None:
    """Без сообщений с вариантами switch_variant ничего не делает."""
    engine._handle_switch_variant({"chat_id": engine._active, "index": 0})


# ===== Сжатие истории =====


def test_compact_range_none_when_short(engine) -> None:
    """Короткая история не сжимается."""
    chat = _fill_msgs(engine, COMPACT_KEEP_MESSAGES)
    assert engine._compact_range(chat) is None


def test_compact_range_bounds(engine) -> None:
    """Границы сжатия не заходят в последние сохранённые сообщения."""
    chat = _fill_msgs(engine, COMPACT_KEEP_MESSAGES + 3)
    assert engine._compact_range(chat) == (0, 3)


def test_compact_range_respects_summary_count(engine) -> None:
    """Уже покрытые сводкой сообщения повторно не сжимаются."""
    chat = _fill_msgs(engine, COMPACT_KEEP_MESSAGES + 6)
    chat["summary_count"] = 2
    assert engine._compact_range(chat) == (2, 6)


def test_compact_count_and_transcript(engine) -> None:
    """Счётчик и транскрипт учитывают только user/assistant без ошибок."""
    chat = engine._active_chat()
    chat["msgs"] = [
        {"id": 1, "role": "user", "text": "вопрос один", "ts": 0},
        {"id": 2, "role": "assistant", "text": "ответ один", "ts": 0},
        {"id": 3, "role": "assistant", "text": "сбой", "error": True, "ts": 0},
        {"id": 4, "role": "system", "text": "служебное", "ts": 0},
    ] + [{"id": i, "role": "user", "text": f"хвост {i}", "ts": 0} for i in range(5, 9)]
    chat["summary_count"] = 0
    assert engine._compact_count(chat) == 2
    transcript = engine._compact_transcript(chat)
    assert "User: вопрос один" in transcript
    assert "Assistant: ответ один" in transcript
    assert "служебное" not in transcript
    assert "сбой" not in transcript


def test_maybe_compact_success(engine, monkeypatch) -> None:
    """Успешное сжатие записывает сводку и границу покрытия."""
    calls: list[dict] = []

    def _fake_call(messages, max_tokens=None):  # noqa: ANN001, ANN202
        """Заглушка вызова модели, возвращающая сводку."""
        calls.append({"messages": messages, "max_tokens": max_tokens})
        return "  краткая сводка  "

    monkeypatch.setattr(engine, "_call_api_blocking", _fake_call)
    chat = _fill_msgs(engine, COMPACT_KEEP_MESSAGES + 4)
    assert engine._maybe_compact(chat, force=True) is True
    assert chat["summary"] == "краткая сводка"
    assert chat["summary_count"] == 4
    assert calls and calls[0]["max_tokens"] > 0


def test_maybe_compact_empty_summary(engine, monkeypatch) -> None:
    """Пустая сводка не сохраняется."""
    monkeypatch.setattr(engine, "_call_api_blocking", lambda *a, **k: "   ")
    chat = _fill_msgs(engine, COMPACT_KEEP_MESSAGES + 4)
    assert engine._maybe_compact(chat, force=True) is False
    assert chat.get("summary", "") == ""


def test_maybe_compact_provider_error(engine, monkeypatch) -> None:
    """Ошибка провайдера при сжатии не роняет движок и не портит чат."""

    def _boom(*_args, **_kwargs):
        """Имитация сетевой ошибки."""
        raise RuntimeError("network down")

    monkeypatch.setattr(engine, "_call_api_blocking", _boom)
    chat = _fill_msgs(engine, COMPACT_KEEP_MESSAGES + 4)
    assert engine._maybe_compact(chat, force=True) is False
    assert chat.get("summary", "") == ""


def test_maybe_compact_respects_min_new_messages(engine, monkeypatch) -> None:
    """Без force сжатие требует минимум новых сообщений."""
    monkeypatch.setattr(engine, "_call_api_blocking", lambda *a, **k: "сводка")
    chat = _fill_msgs(engine, COMPACT_KEEP_MESSAGES + 2)
    assert engine._maybe_compact(chat) is False


def test_should_compact_disabled(engine, monkeypatch) -> None:
    """Отключённая автокомпакция не срабатывает даже на большой истории."""
    engine._config["compact_enabled"] = False
    chat = _fill_msgs(engine, COMPACT_KEEP_MESSAGES + 20)
    engine._config["context_window"] = 1
    assert engine._should_compact(chat) is False


def test_should_compact_over_threshold(engine) -> None:
    """При превышении порога автокомпакция включает сжатие."""
    engine._config["compact_enabled"] = True
    engine._config["context_window"] = 1
    engine._config["compact_threshold"] = 10
    chat = _fill_msgs(engine, COMPACT_KEEP_MESSAGES + 20)
    assert engine._should_compact(chat) is True


def test_handle_compact_starts_thread(engine, monkeypatch) -> None:
    """Ручная компакция запускает фоновый воркер и сбрасывает cancel_event."""
    started: list[tuple] = []

    class _FakeThread:
        """Заглушка потока: не запускает воркер, только фиксирует аргументы."""

        def __init__(self, target=None, args=(), **kwargs):  # noqa: ANN001, ANN202
            started.append((target, args, kwargs))

        def start(self) -> None:
            """Имитация запуска потока."""

    monkeypatch.setattr("flowslice_ai.engine.compaction.threading.Thread", _FakeThread)
    engine._cancel_event.set()
    _fill_msgs(engine, COMPACT_KEEP_MESSAGES + 4)
    engine._handle_compact({"chat_id": engine._active})
    assert engine._compacting is True
    assert not engine._cancel_event.is_set()
    assert started and started[0][1] == (engine._active,)


def test_handle_compact_busy_during_generation(engine, monkeypatch) -> None:
    """Ручная компакция не запускается во время генерации."""
    posts: list[dict] = []
    monkeypatch.setattr(engine, "_post", posts.append)
    engine._gen = True
    engine._handle_compact({})
    assert engine._compacting is False
    assert _posts_of(posts, "toast")


# ===== Статистика и настройки-сбросы =====


def test_usage_snapshot_survives_garbage(engine) -> None:
    """Повреждённые записи статистики не ломают снимок использования."""
    today = time.strftime("%Y-%m-%d")
    engine._config["usage"] = {
        today: {"msgs": "2", "tokens": "не число"},
        "2020-01-01": "мусор",
        5: None,
    }
    snap = engine._usage_snapshot("all")
    assert snap["msgs"] == 2
    assert snap["tokens"] == 0
    assert isinstance(engine._usage_snapshot("day")["msgs"], int)
    assert isinstance(engine._usage_snapshot("week")["tokens"], int)
    assert isinstance(engine._usage_snapshot("month")["msgs"], int)


def test_usage_snapshot_handles_non_dict_usage(engine) -> None:
    """Если usage в конфиге не словарь, снимок возвращает нули."""
    engine._config["usage"] = "сломано"
    snap = engine._usage_snapshot("all")
    assert snap == {"period": "all", "msgs": 0, "tokens": 0}


def test_record_usage_repairs_garbage(engine) -> None:
    """Запись статистики восстанавливает словарь и учитывает сообщение."""
    engine._config["usage"] = "сломано"
    engine._record_usage("вопрос", "ответ")
    today = time.strftime("%Y-%m-%d")
    assert isinstance(engine._config["usage"], dict)
    assert engine._config["usage"][today]["msgs"] == 1


def test_reset_settings_unknown_scope_toast(engine, monkeypatch) -> None:
    """Неизвестная область сброса не меняет настройки и показывает ошибку."""
    posts: list[dict] = []
    monkeypatch.setattr(engine, "_post", posts.append)
    engine._config["theme"] = "dark"
    engine._handle_reset_settings({"scope": "bogus"})
    assert engine._config["theme"] == "dark"
    toasts = _posts_of(posts, "toast")
    assert toasts and toasts[-1]["kind"] == "err"


def test_reset_settings_appearance_scope(engine) -> None:
    """Сброс вкладки appearance возвращает тему к значению по умолчанию."""
    engine._config["theme"] = "dark"
    engine._handle_reset_settings({"scope": "appearance"})
    assert engine._config["theme"] == "auto"


def test_reset_custom_models_removes_custom_only(engine) -> None:
    """Сброс пользовательских моделей удаляет не-builtin провайдеров."""
    engine._config["providers"]["myprov"] = {
        "name": "My Provider",
        "builtin": False,
        "base_url": "https://example.com/v1",
        "models": {},
    }
    engine._handle_reset_custom_models()
    assert "myprov" not in engine._config["providers"]
    assert "deepseek" in engine._config["providers"]


def test_handle_command_unknown_returns_false(engine) -> None:
    """Неизвестная slash-команда не обрабатывается движком."""
    assert engine._handle_command("/totally-unknown") is False


def test_handle_command_help_returns_true(engine, monkeypatch) -> None:
    """/help распознаётся как известная команда."""
    posts: list[dict] = []
    monkeypatch.setattr(engine, "_post", posts.append)
    assert engine._handle_command("/help") is True
    assert posts
