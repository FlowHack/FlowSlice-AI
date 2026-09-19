"""Тесты вспомогательных методов движка: токены, i18n, slugify, числа, состояние."""
from __future__ import annotations

import time
import types

import pytest

from flowslice_ai.constants import (
    COMPACT_KEEP_MESSAGES,
    MAX_ATTACHMENTS,
    MAX_FILE_CHARS,
    MAX_PERSISTED_FILE_CHARS,
    MAX_TOTAL_FILE_CHARS,
)


def test_estimate_tokens(engine) -> None:
    """_estimate_tokens() оценивает токены как len(text) // 4."""
    assert engine._estimate_tokens("abcd") == 1
    assert engine._estimate_tokens("") == 0


def test_i18n_t(engine) -> None:
    """_t() отдаёт текст на языке из настроек и не различает регистр ключа."""
    engine._config["language"] = "ru"
    ru = engine._t("win.opened")
    engine._config["language"] = "en"
    en = engine._t("win.opened")
    assert ru and en
    assert ru != en


def test_slugify(engine) -> None:
    """_slugify() приводит имя провайдера к нижнему регистру с дефисами."""
    assert engine._slugify("My Provider") == "my-provider"


def test_as_int(engine) -> None:
    """_as_int() парсит число либо возвращает значение по умолчанию."""
    assert engine._as_int("42", 0) == 42
    assert engine._as_int("abc", 7) == 7


def test_collect_preset_data_orca_none(engine, monkeypatch) -> None:
    """_collect_preset_data() при orca=None возвращает единый формат разделов."""
    monkeypatch.setattr("flowslice_ai.engine.slicer_context.orca", None)
    data = engine._collect_preset_data()
    assert set(data) == {"printer", "filament", "print"}
    for section in data.values():
        assert set(section) == {"name", "params"}
        assert section["name"] == ""
        assert section["params"] == {}


def test_collect_preset_data_bundle_none(engine) -> None:
    """_collect_preset_data() при недоступном preset_bundle не падает."""
    data = engine._collect_preset_data()
    assert set(data) == {"printer", "filament", "print"}
    for section in data.values():
        assert set(section) == {"name", "params"}


def test_preset_config_items_skips_metadata(engine) -> None:
    """_preset_config_items() исключает metadata-ключи и пустые значения."""

    class _FakePreset:
        """Заглушка пресета с конфигом."""

        config = {
            "name": "0.20mm Standard",
            "inherits": "0.20mm Standard @MyPrinter",
            "layer_height": 0.2,
            "wall_loops": "",
            "sparse_infill_density": "15%",
            "printer_model": "MyPrinter",
        }

    items = engine._preset_config_items(_FakePreset())
    assert items == {
        "layer_height": 0.2,
        "sparse_infill_density": "15%",
        "printer_model": "MyPrinter",
    }


def test_preset_inheritance_chain(engine) -> None:
    """_preset_inheritance_chain() строит цепочку от корня к текущему."""

    class _FakePreset:
        """Заглушка пресета с именем и конфигом."""

        def __init__(self, name: str, inherits: str = "") -> None:
            self.name = name
            self.config = {"inherits": inherits} if inherits else {}

    class _FakeCollection:
        """Заглушка коллекции пресетов."""

        def __init__(self, presets: dict[str, _FakePreset]) -> None:
            self._presets = presets

        def find_preset(self, name: str):
            """Возвращает пресет по имени."""
            return self._presets.get(name)

    root = _FakePreset("Base @Printer")
    child = _FakePreset("Custom @Printer", "Base @Printer")
    collection = _FakeCollection({"Base @Printer": root, "Custom @Printer": child})
    chain = engine._preset_inheritance_chain(collection, child)
    assert [item.name for item in chain] == ["Custom @Printer", "Base @Printer"]


def test_preset_config_items_uses_public_api(engine) -> None:
    """_preset_config_items() читает ключи через config_keys()/config_value()."""

    class _FakePreset:
        """Заглушка пресета с публичным API плагина Orca."""

        def config_keys(self):
            """Возвращает полный список ключей конфига."""
            return [
                "name",
                "inherits",
                "layer_height",
                "wall_loops",
                "sparse_infill_density",
            ]

        def config_value(self, key: str):
            """Возвращает сериализованное значение ключа."""
            return {
                "name": "0.20mm Standard",
                "inherits": "0.20mm Standard @MyPrinter",
                "layer_height": "0.2",
                "wall_loops": "",
                "sparse_infill_density": "15%",
            }.get(key)

    items = engine._preset_config_items(_FakePreset())
    assert items == {"layer_height": "0.2", "sparse_infill_density": "15%"}


def test_preset_inherits_name_uses_public_api(engine) -> None:
    """_preset_inherits_name() берёт родителя через config_value()."""

    class _FakePreset:
        """Заглушка пресета с config_value()."""

        def config_value(self, key: str):
            """Возвращает имя родителя только для ключа inherits."""
            return "Base @Printer" if key == "inherits" else None

    assert engine._preset_inherits_name(_FakePreset()) == "Base @Printer"


class _Preset:
    """Заглушка пресета с публичным API Orca."""

    def __init__(self, name: str, values: dict) -> None:
        self.name = name
        self._values = values

    def config_keys(self):
        """Возвращает ключи пресета."""
        return list(self._values)

    def config_value(self, key: str):
        """Возвращает значение ключа."""
        return self._values.get(key)


class _PresetCollection:
    """Заглушка коллекции пресетов с выбранным пресетом."""

    def __init__(self, presets: dict, selected: _Preset) -> None:
        self._presets = presets
        self._selected = selected

    def get_selected_preset_name(self) -> str:
        """Возвращает имя выбранного пресета."""
        return self._selected.name

    def get_selected_preset(self):
        """Возвращает выбранный пресет."""
        return self._selected

    def find_preset(self, name: str):
        """Возвращает пресет по имени."""
        return self._presets.get(name)


class _PresetBundle:
    """Заглушка бандла с тремя коллекциями и объединённым конфигом."""

    def __init__(self, collection: _PresetCollection) -> None:
        self.printers = collection
        self.filaments = collection
        self.prints = collection

    def full_config_value(self, key: str):
        """Объединённый конфиг в заглушке пуст."""
        return None


def _preset_bundle(base_values: dict, user_values: dict) -> _PresetBundle:
    """Собирает бандл из базового и пользовательского пресетов."""
    base = _Preset("Base @P", base_values)
    user = _Preset("User @P", user_values)
    collection = _PresetCollection({"Base @P": base, "User @P": user}, user)
    return _PresetBundle(collection)


def test_collect_preset_data_all_differs_from_changed(engine, monkeypatch) -> None:
    """Режим "all" отдаёт унаследованные ключи, режим "changed" — только свои."""
    bundle = _preset_bundle(
        {"printer_model": "MyPrinter", "nozzle_diameter": "0.4"},
        {"inherits": "Base @P", "printable_height": "390"},
    )
    monkeypatch.setattr(
        "flowslice_ai.engine.slicer_context.orca",
        types.SimpleNamespace(
            host=types.SimpleNamespace(preset_bundle=lambda: bundle)
        ),
    )

    changed = engine._collect_preset_data({"printer": "changed"})
    full = engine._collect_preset_data({"printer": "all"})
    assert changed["printer"]["params"] == {"printable_height": "390"}
    assert full["printer"]["params"] == {
        "printer_model": "MyPrinter",
        "nozzle_diameter": "0.4",
        "printable_height": "390",
    }


def test_collect_preset_data_changed_filters_inherited(engine, monkeypatch) -> None:
    """Режим "changed" оставляет только отличия от разрешённого конфига предков."""
    bundle = _preset_bundle(
        {"printer_model": "MyPrinter", "nozzle_diameter": "0.4"},
        {
            "inherits": "Base @P",
            "printer_model": "MyPrinter",
            "nozzle_diameter": "0.6",
        },
    )
    monkeypatch.setattr(
        "flowslice_ai.engine.slicer_context.orca",
        types.SimpleNamespace(
            host=types.SimpleNamespace(preset_bundle=lambda: bundle)
        ),
    )

    changed = engine._collect_preset_data({"printer": "changed"})
    assert changed["printer"]["params"] == {"nozzle_diameter": "0.6"}


def test_model_supports_images_static(engine) -> None:
    """_model_supports_images() читает статический флаг vision у модели."""
    engine._config["active_provider"] = "deepseek"
    engine._config["active_model"] = "deepseek-chat"
    assert engine._model_supports_images() is False


def test_model_supports_images_unknown(engine) -> None:
    """Неизвестное значение vision означает неизвестную поддержку изображений."""
    engine._config["active_provider"] = "openai"
    engine._config["active_model"] = "gpt-4o"
    engine._config["providers"]["openai"]["models"]["gpt-4o"]["vision"] = None
    assert engine._model_supports_images() is None


def test_model_supports_images_defaults(engine) -> None:
    """Зрение встроенных моделей берётся из каталога провайдеров."""
    engine._config["active_provider"] = "google"
    engine._config["active_model"] = "gemini-2.5-flash"
    assert engine._model_supports_images() is True
    engine._config["active_provider"] = "deepseek"
    engine._config["active_model"] = "deepseek-chat"
    assert engine._model_supports_images() is False


def test_attach_image_blocked_without_vision(engine) -> None:
    """Модель без зрения: изображение отклоняется с пояснением."""
    engine._config["active_provider"] = "deepseek"
    engine._config["active_model"] = "deepseek-chat"
    engine._handle_attach_file({"kind": "image", "name": "a.jpg", "data": "data:x"})
    assert engine._pending_attachments == []


def test_vision_lookup_worker_marks_provider(engine, monkeypatch) -> None:
    """Результат запроса к провайдеру сохраняется с источником provider."""
    engine._config["providers"]["openrouter"]["models"]["openrouter/auto"]["vision"] = None
    monkeypatch.setattr(engine, "_resolve_vision_for", lambda provider, model: True)
    engine._vision_lookup_worker("openrouter", "openrouter/auto")
    model = engine._config["providers"]["openrouter"]["models"]["openrouter/auto"]
    assert model["vision"] is True
    assert model["vision_source"] == "provider"


def test_update_model_sets_manual_vision(engine) -> None:
    """Ручная установка зрения помечается источником manual."""
    engine._handle_update_model(
        {"provider": "deepseek", "model_id": "deepseek-chat", "vision": True}
    )
    model = engine._config["providers"]["deepseek"]["models"]["deepseek-chat"]
    assert model["vision"] is True
    assert model["vision_source"] == "manual"


def test_chat_send_drops_pending_image_without_vision(engine) -> None:
    """Если модель сменилась на модель без зрения, картинка не отправляется."""
    engine._config["active_provider"] = "google"
    engine._config["active_model"] = "gemini-2.5-flash"
    engine._handle_attach_file({"kind": "image", "name": "a.jpg", "data": "data:x"})
    assert len(engine._pending_attachments) == 1
    engine._config["active_provider"] = "deepseek"
    engine._config["active_model"] = "deepseek-chat"
    engine._handle_chat({"text": "смотри"})
    chat = engine._active_chat()
    assert engine._pending_attachments == []
    assert all(not msg.get("attachments") for msg in chat["msgs"])


def test_providers_snapshot_includes_vision_source(engine) -> None:
    """Снимок провайдеров отдаёт зрение модели и его источник."""
    providers = engine._providers_snapshot()
    openai = next(p for p in providers if p["id"] == "openai")
    gpt = next(m for m in openai["models"] if m["id"] == "gpt-4o")
    assert gpt["vision"] is True
    assert gpt["vision_source"] == "default"


def test_build_messages_sends_images_over_openai(engine, monkeypatch) -> None:
    """Для OpenAI-совместимой схемы изображения уходят как image_url."""
    engine._config["active_provider"] = "deepseek"
    engine._config["active_model"] = "deepseek-chat"
    monkeypatch.setattr(engine, "_collect_context", lambda flags, modes=None: {})
    monkeypatch.setattr(engine, "_build_system_prompt", lambda ctx, **kwargs: "sys")
    monkeypatch.setattr(engine, "_model_supports_images", lambda **_kwargs: True)
    chat = {
        "msgs": [
            {"role": "user", "text": "hi", "image": "data:image/jpeg;base64,AAA"}
        ]
    }
    messages = engine._build_messages(chat, "hi")
    content = messages[-1]["content"]
    assert isinstance(content, list)
    assert content[1]["type"] == "image_url"


def test_pending_attachments_multiple(engine) -> None:
    """Несколько вложений подряд не перезаписывают друг друга."""
    engine._config["active_provider"] = "openai"
    engine._config["active_model"] = "gpt-4o"
    engine._handle_attach_file({"kind": "image", "name": "a.jpg", "data": "data:x"})
    engine._handle_attach_file({"kind": "image", "name": "b.jpg", "data": "data:y"})
    assert len(engine._pending_attachments) == 2


def test_usage_snapshot_today(engine) -> None:
    """Период "today" из UI учитывает только сегодняшние записи."""
    today = time.strftime("%Y-%m-%d")
    engine._config["usage"] = {
        today: {"msgs": 3, "tokens": 30},
        "2000-01-01": {"msgs": 9, "tokens": 90},
    }
    snap = engine._usage_snapshot("today")
    assert snap["msgs"] == 3
    assert snap["tokens"] == 30


def test_settings_snapshot_hides_api_key(engine) -> None:
    """Снапшот настроек отдаёт только признак наличия ключа."""
    engine._config["providers"]["deepseek"]["api_key"] = "secret-key"
    snap = engine._settings_snapshot()
    assert "api_key" not in snap
    assert snap["has_api_key"] is True


def test_providers_snapshot_hides_api_keys(engine) -> None:
    """Снапшот провайдеров не раскрывает ни один API-ключ."""
    engine._config["providers"]["deepseek"]["api_key"] = "secret-key"
    snap = engine._providers_snapshot()
    for prov in snap:
        assert "api_key" not in prov
    deepseek = next(p for p in snap if p["id"] == "deepseek")
    assert deepseek["has_key"] is True


def test_save_settings_sends_fresh_providers(engine, monkeypatch) -> None:
    """После сохранения ключа UI получает state с обновлённым has_key."""
    posts = []
    monkeypatch.setattr(engine, "_post", posts.append)
    engine._handle_save_settings(
        {"settings": {"active_provider": "openrouter", "api_key": "sk-test"}}
    )
    states = [p for p in posts if p.get("type") == "state"]
    assert states, "state не отправлен после сохранения настроек"
    openrouter = next(p for p in states[-1]["providers"] if p["id"] == "openrouter")
    assert openrouter["has_key"] is True


def test_send_state_includes_donation_options(engine, monkeypatch) -> None:
    """Состояние содержит реквизиты донатов из единой константы."""
    posts = []
    monkeypatch.setattr(engine, "_post", posts.append)
    engine._send_state()
    states = [p for p in posts if p.get("type") == "state"]
    assert states, "state не отправлен"
    donate = states[-1]["donate"]
    assert len(donate) == 3
    values = {item["id"]: item["value"] for item in donate}
    assert values["yoomoney"] == "4100119569298015"
    assert values["usdt"] == "TJRUKLwmYk8DpjFCyakQxWzXeJL6hrFTxZ"
    assert values["btc"] == "15f1swAtj7T1yVaXGEGWyLrfxSmDn1NKiY"


def test_cmd_reset_chats_requires_confirmation(engine) -> None:
    """`/reset chats` очищает историю только после подтверждения."""
    before = len(engine._chats)
    engine._cmd_reset("/reset chats")
    assert len(engine._chats) == before
    engine._cmd_reset("/reset chats")
    assert len(engine._chats) == 1


def test_estimate_context_tokens_grows_with_history(engine) -> None:
    """Оценка токенов учитывает реальный промпт и историю чата."""
    base = engine._estimate_context_tokens({"history": False}, {})
    assert base > 0
    chat = engine._active_chat()
    chat["msgs"] = [
        {"id": 1, "role": "user", "text": "вопрос " * 40, "ts": 0},
        {"id": 2, "role": "assistant", "text": "ответ " * 40, "ts": 0},
        {"id": 3, "role": "user", "text": "уточнение", "ts": 0},
    ]
    with_history = engine._estimate_context_tokens({"history": True}, {})
    assert with_history > base


def test_system_prompt_has_parameter_and_language_rules(engine) -> None:
    """База промпта — английская (роль и правила), язык ответа локализован."""
    engine._config["language"] = "ru"
    prompt_ru = engine._build_system_prompt({})
    assert "senior 3D-printing engineer" in prompt_ru
    assert "human-readable label" in prompt_ru
    assert "Отвечай строго на русском языке." in prompt_ru
    # Шум окружения (версия Python) в промпт больше не попадает.
    assert "Python 3" not in prompt_ru
    engine._config["language"] = "en"
    prompt_en = engine._build_system_prompt({})
    assert "Answer strictly in English." in prompt_en


def test_chat_message_accepts_inline_attachments(engine, monkeypatch) -> None:
    """Вложения из payload chat доходят до сообщения и до промпта модели."""
    monkeypatch.setattr(engine, "_collect_context", lambda flags, modes=None: {})
    monkeypatch.setattr(engine, "_start_generation", lambda *args, **kwargs: None)
    engine._config["language"] = "en"
    engine.handle_message(
        {
            "type": "chat",
            "text": "посмотри файл",
            "attachments": [
                {"kind": "text", "name": "a.txt", "data": "СЕКРЕТ_ФАЙЛА"}
            ],
        }
    )
    chat = engine._active_chat()
    user_msg = chat["msgs"][-1]
    assert user_msg["role"] == "user"
    assert user_msg["attachments"][0]["file"]["text"] == "СЕКРЕТ_ФАЙЛА"
    messages = engine._build_messages(chat, "посмотри файл")
    content = messages[-1]["content"]
    text = content if isinstance(content, str) else content[0]["text"]
    assert "СЕКРЕТ_ФАЙЛА" in text
    assert "<source>a.txt</source>" in text
    assert "<document_content>" in text


def test_chat_with_only_attachment_keeps_text_empty(engine, monkeypatch) -> None:
    """Сообщение без текста с вложением отправляется, текст не подменяется."""
    monkeypatch.setattr(engine, "_start_generation", lambda *args, **kwargs: None)
    engine._config["language"] = "en"
    engine.handle_message(
        {
            "type": "chat",
            "text": "",
            "attachments": [{"kind": "text", "name": "a.txt", "data": "СЕКРЕТ"}],
        }
    )
    chat = engine._active_chat()
    user_msg = chat["msgs"][-1]
    assert user_msg["role"] == "user"
    # Пользователь не писал метку — текст остаётся пустым, вложение хранится отдельно.
    assert user_msg["text"] == ""
    assert user_msg["attachments"][0]["file"]["name"] == "a.txt"
    # Заголовок чата при этом формируется по имени вложения.
    assert "a.txt" in chat["title"]
    # Содержимое вложения попадает в запрос к модели.
    messages = engine._build_messages(chat, user_msg["text"])
    content = str(messages[-1]["content"])
    assert "СЕКРЕТ" in content


def test_checked_attachment_rejects_large_file(engine) -> None:
    """Слишком большой текстовый файл отклоняется, нормальный — принимается."""
    engine._config["language"] = "en"
    assert engine._checked_attachment("text", "big.txt", "x" * (MAX_FILE_CHARS + 1)) is None
    assert engine._checked_attachment("text", "ok.txt", "hello") == {
        "file": {"name": "ok.txt", "text": "hello"}
    }


def test_accept_attachments_limits_count(engine) -> None:
    """Число принимаемых вложений ограничено MAX_ATTACHMENTS."""
    engine._config["language"] = "en"
    items = [
        {"kind": "text", "name": f"f{i}.txt", "data": "x"}
        for i in range(MAX_ATTACHMENTS + 3)
    ]
    accepted = engine._accept_attachments(items)
    assert accepted == MAX_ATTACHMENTS
    assert len(engine._pending_attachments) == MAX_ATTACHMENTS


def test_accept_attachments_total_text_budget(engine) -> None:
    """Суммарный объём текстовых вложений ограничен."""
    engine._config["language"] = "en"
    chunk = "x" * MAX_FILE_CHARS
    items = [
        {"kind": "text", "name": f"f{i}.txt", "data": chunk} for i in range(6)
    ]
    accepted = engine._accept_attachments(items)
    assert accepted == MAX_TOTAL_FILE_CHARS // MAX_FILE_CHARS
    total = sum(len(a["file"]["text"]) for a in engine._pending_attachments)
    assert total <= MAX_TOTAL_FILE_CHARS


def test_flatten_keeps_file_content_and_no_markers(engine, monkeypatch) -> None:
    """При сохранении текст сообщения не засоряется метками, файл сохраняется."""
    monkeypatch.setattr(engine, "_start_generation", lambda *args, **kwargs: None)
    engine._config["language"] = "en"
    engine.handle_message(
        {
            "type": "chat",
            "text": "смотри файл",
            "attachments": [{"kind": "text", "name": "a.txt", "data": "ТЕЛО"}],
        }
    )
    flat = engine._flatten_chats()
    flat_msg = flat[0]["msgs"][-1]
    assert flat_msg["text"] == "смотри файл"
    assert "[file:" not in flat_msg["text"]
    assert flat_msg["attachments"][0]["file"]["text"] == "ТЕЛО"


def test_strip_legacy_markers_removes_file_and_photo_marks(engine) -> None:
    """Миграция убирает старые метки вложений из текста сообщений."""
    assert engine._strip_legacy_markers("текст [file: a.txt]") == "текст"
    assert engine._strip_legacy_markers("текст [файл: b.gcode]") == "текст"
    assert engine._strip_legacy_markers("текст [fajl: c.txt]") == "текст"
    assert engine._strip_legacy_markers("текст [фото] [photo]") == "текст"
    assert engine._strip_legacy_markers("обычный текст") == "обычный текст"


def test_attachment_content_survives_reload(engine, monkeypatch) -> None:
    """После перезагрузки чатов содержимое файла остаётся доступным модели."""
    monkeypatch.setattr(engine, "_start_generation", lambda *args, **kwargs: None)
    engine._config["language"] = "en"
    engine.handle_message(
        {
            "type": "chat",
            "text": "смотри файл",
            "attachments": [{"kind": "text", "name": "a.txt", "data": "ТЕЛО_ФАЙЛА"}],
        }
    )
    engine._save_chats()
    engine._load_chats()
    user = engine._active_chat()["msgs"][-1]
    assert user["text"] == "смотри файл"
    assert "[file:" not in user["text"]
    files = engine._collect_files(user)
    assert files and files[0]["text"] == "ТЕЛО_ФАЙЛА"
    messages = engine._build_messages(engine._active_chat(), user["text"])
    assert "ТЕЛО_ФАЙЛА" in str(messages[-1]["content"])


def test_attachment_truncation_is_marked(engine, monkeypatch) -> None:
    """Усечённое при сохранении вложение помечается для модели."""
    monkeypatch.setattr(engine, "_start_generation", lambda *args, **kwargs: None)
    engine._config["language"] = "en"
    long_text = "x" * (MAX_PERSISTED_FILE_CHARS + 5)
    engine._accept_attachments([{"kind": "text", "name": "big.txt", "data": long_text}])
    user_msg = {"role": "user", "text": "файл", "attachments": engine._pending_attachments}
    engine._pending_attachments = []
    rendered = engine._render_file(engine._flatten_attachments(user_msg["attachments"])[0]["file"])
    assert MAX_PERSISTED_FILE_CHARS <= rendered.count("x") < len(long_text)
    assert "beginning is shown" in rendered


def test_normalize_price_validates_bounds(engine) -> None:
    """Нормализация цены отсекает пустые, отрицательные и завышенные значения."""
    assert engine._normalize_price(None) is None
    assert engine._normalize_price("abc") is None
    assert engine._normalize_price(-1) is None
    assert engine._normalize_price(100001) is None
    assert engine._normalize_price("2.5") == 2.5
    assert engine._normalize_price(0.123456) == 0.1235


def test_update_model_sets_manual_price(engine) -> None:
    """Ручная цена модели помечается источником manual."""
    engine._handle_update_model(
        {"provider": "deepseek", "model_id": "deepseek-chat", "price_in": 1.5, "price_out": 2.0}
    )
    model = engine._config["providers"]["deepseek"]["models"]["deepseek-chat"]
    assert model["price_in"] == 1.5
    assert model["price_out"] == 2.0
    assert model["price_source"] == "manual"


def test_update_model_price_keeps_untouched_field(engine) -> None:
    """Обновление только входной цены не затирает выходную."""
    engine._handle_update_model(
        {"provider": "deepseek", "model_id": "deepseek-chat", "price_in": 1.0, "price_out": 2.0}
    )
    engine._handle_update_model(
        {"provider": "deepseek", "model_id": "deepseek-chat", "price_in": 3.0}
    )
    model = engine._config["providers"]["deepseek"]["models"]["deepseek-chat"]
    assert model["price_in"] == 3.0
    assert model["price_out"] == 2.0


def test_update_model_clears_price(engine) -> None:
    """Сброс обеих цен удаляет их и источник."""
    engine._handle_update_model(
        {"provider": "deepseek", "model_id": "deepseek-chat", "price_in": 1.0, "price_out": 2.0}
    )
    engine._handle_update_model(
        {"provider": "deepseek", "model_id": "deepseek-chat", "price_in": None, "price_out": None}
    )
    model = engine._config["providers"]["deepseek"]["models"]["deepseek-chat"]
    assert "price_in" not in model
    assert "price_out" not in model
    assert "price_source" not in model


def test_estimate_messages_tokens_counts_text_and_images(engine) -> None:
    """Оценка токенов считает текст и добавляет фиксированную оценку за изображение."""
    messages = [
        {"role": "user", "content": "abcd" * 25},
        {
            "role": "user",
            "content": [
                {"type": "text", "text": "abcd" * 25},
                {"type": "image_url", "image_url": {"url": "data:image/png;base64,AAA"}},
            ],
        },
    ]
    assert engine._estimate_messages_tokens(messages) == 25 + 25 + 1100


def test_estimate_cost_unknown_price_returns_none(engine) -> None:
    """Без цен стоимость не подменяется нулём — возвращается None."""
    engine._config["active_provider"] = "deepseek"
    engine._config["active_model"] = "deepseek-chat"
    engine._config["providers"]["deepseek"]["models"]["deepseek-chat"].pop("price_in", None)
    engine._config["providers"]["deepseek"]["models"]["deepseek-chat"].pop("price_out", None)
    assert engine._estimate_cost(1000, 500) is None


def test_estimate_cost_calculates_usd(engine) -> None:
    """При известных ценах стоимость считается из токенов за 1М."""
    engine._config["active_provider"] = "deepseek"
    engine._config["active_model"] = "deepseek-chat"
    model = engine._config["providers"]["deepseek"]["models"]["deepseek-chat"]
    model["price_in"] = 1.0
    model["price_out"] = 2.0
    assert engine._estimate_cost(1_000_000, 500_000) == 2.0


def test_update_model_from_api_marks_provider_price(engine) -> None:
    """Скопированная из API цена помечается источником provider."""
    info = {"name": "Test", "vision": True, "price_in": 0.5, "price_out": 1.5}
    assert engine._ensure_model_from_api("deepseek", "deepseek-new", info) is True
    model = engine._config["providers"]["deepseek"]["models"]["deepseek-new"]
    assert model["price_source"] == "provider"
    assert model["price_in"] == 0.5


def _compact_chat(count: int) -> dict:
    """Создаёт чат с чередованием реплик для проверки сжатия."""
    msgs = []
    for i in range(count):
        role = "user" if i % 2 == 0 else "assistant"
        msgs.append({"role": role, "text": f"msg-{i}"})
    return {"msgs": msgs, "context_flags": {"history": True}}


def test_history_messages_skips_compacted(engine) -> None:
    """Сжатые сообщения не попадают в контекст модели."""
    chat = _compact_chat(5)
    chat["summary_count"] = 2
    history = engine._history_messages(chat, 100_000)
    texts = [item["content"] for item in history]
    assert "msg-0" not in texts
    assert "msg-1" not in texts
    assert "msg-2" in texts


def test_maybe_compact_saves_summary(engine, monkeypatch) -> None:
    """Сжатие сохраняет сводку и помечает покрытые сообщения."""
    chat = _compact_chat(10)
    monkeypatch.setattr(
        engine, "_call_api_blocking", lambda messages, max_tokens=2048: "SUMMARY"
    )
    assert engine._maybe_compact(chat) is True
    assert chat["summary"] == "SUMMARY"
    assert chat["summary_count"] == 10 - COMPACT_KEEP_MESSAGES
    assert len(chat["msgs"]) == 10


def test_maybe_compact_without_new_messages(engine, monkeypatch) -> None:
    """Повторное сжатие без новых сообщений ничего не делает."""
    chat = _compact_chat(10)
    chat["summary_count"] = 10 - COMPACT_KEEP_MESSAGES
    monkeypatch.setattr(
        engine, "_call_api_blocking", lambda messages, max_tokens=2048: "SUMMARY"
    )
    assert engine._maybe_compact(chat) is False


def test_maybe_compact_failure_keeps_state(engine, monkeypatch) -> None:
    """Ошибка сжатия не портит чат и не создаёт пустую сводку."""

    def _boom(messages, max_tokens=2048):
        raise RuntimeError("network down")

    monkeypatch.setattr(engine, "_call_api_blocking", _boom)
    chat = _compact_chat(10)
    assert engine._maybe_compact(chat) is False
    assert "summary" not in chat
    assert "summary_count" not in chat


def test_build_messages_includes_summary(engine, monkeypatch) -> None:
    """Сводка добавляется в системный промпт запроса."""
    monkeypatch.setattr(engine, "_collect_context", lambda flags, modes=None: {})
    monkeypatch.setattr(engine, "_build_system_prompt", lambda ctx, **kwargs: "sys")
    monkeypatch.setattr(engine, "_model_supports_images", lambda **_kwargs: False)
    chat = {
        "msgs": [{"role": "user", "text": "hi"}],
        "summary": "Old context summary",
        "summary_count": 0,
        "context_flags": {},
    }
    messages = engine._build_messages(chat, "hi")
    assert "Old context summary" in messages[0]["content"]


def test_regenerate_preserves_previous_answer(engine, monkeypatch) -> None:
    """Регенерация сохраняет прежний ответ как вариант, а не удаляет его."""
    captured: dict = {}
    monkeypatch.setattr(
        engine,
        "_start_generation",
        lambda chat_id, text, msg_id: captured.update(
            {"chat_id": chat_id, "text": text, "msg_id": msg_id}
        ),
    )
    chat = {
        "id": 7,
        "msgs": [
            {"id": 1, "role": "user", "text": "hi"},
            {"id": 2, "role": "assistant", "text": "first", "reasoning": "r1"},
        ],
        "context_flags": {},
    }
    engine._chats = [chat]
    engine._active = 7
    engine._handle_regenerate()
    assert len(chat["msgs"]) == 1
    assert engine._pending_variants[7] == [{"text": "first", "reasoning": "r1"}]
    assert captured["chat_id"] == 7
    assert captured["text"] == "hi"


def test_switch_variant_changes_active_text(engine) -> None:
    """Переключение варианта подменяет активный текст ответа."""
    msg = {
        "id": 2,
        "role": "assistant",
        "text": "second",
        "variants": [{"text": "first", "reasoning": "r1"}, {"text": "second", "reasoning": ""}],
        "variant_index": 1,
    }
    chat = {"id": 7, "msgs": [{"id": 1, "role": "user", "text": "hi"}, msg], "context_flags": {}}
    engine._chats = [chat]
    engine._active = 7
    engine._handle_switch_variant({"chat_id": 7, "index": 0})
    assert msg["text"] == "first"
    assert msg["variant_index"] == 0
    assert msg["reasoning"] == "r1"
    # Некорректный индекс не меняет состояние.
    engine._handle_switch_variant({"chat_id": 7, "index": 5})
    assert msg["text"] == "first"


class _FakeBBox:
    """Тестовый BoundingBox с полями min/max/size/center."""

    def __init__(self, low, high) -> None:
        self.min = low
        self.max = high
        self.size = tuple(high[i] - low[i] for i in range(3))
        self.center = tuple((high[i] + low[i]) / 2 for i in range(3))


class _FakeMesh:
    """Тестовый меш с габаритами, объёмом и числом треугольников."""

    def __init__(self, low, high, volume, triangles, manifold=True) -> None:
        self.bounding_box = _FakeBBox(low, high)
        self.volume = volume
        self.is_manifold = manifold
        self.triangle_count = triangles


class _FakeVolume:
    """Тестовый объём объекта с именем и мешем."""

    def __init__(self, name, mesh) -> None:
        self.name = name
        self.mesh = mesh


class _FakeModelObject:
    """Тестовый объект модели, возвращающий список объёмов."""

    def __init__(self, volumes) -> None:
        self._volumes = volumes

    def volumes(self):
        """Возвращает объёмы объекта."""
        return self._volumes


def _fake_orca_with_model(objects):
    """Собирает минимальный стенд orca.host.model() для теста контекста."""
    model = types.SimpleNamespace(objects=lambda: objects)
    host = types.SimpleNamespace(model=lambda: model)
    return types.SimpleNamespace(host=host)


def test_collect_model_brief_aggregates_scene(engine, monkeypatch) -> None:
    """Краткий режим отдаёт сводку по сцене без деталей по объектам."""
    mesh_a = _FakeMesh((0.0, 0.0, 0.0), (10.0, 20.0, 30.0), 1000.0, 12)
    mesh_b = _FakeMesh((5.0, 0.0, 0.0), (15.0, 10.0, 40.0), 1000.0, 20, manifold=False)
    objects = [
        _FakeModelObject([_FakeVolume("a", mesh_a)]),
        _FakeModelObject([_FakeVolume("b", mesh_b)]),
    ]
    monkeypatch.setattr(
        "flowslice_ai.engine.slicer_context.orca", _fake_orca_with_model(objects)
    )
    data = engine._collect_model_data("brief")
    assert data["objects_count"] == 2
    assert data["volume_cm3"] == 2.0
    assert data["triangles"] == 32
    assert data["manifold"] is False
    assert data["overall_bbox_mm"] == (15.0, 20.0, 40.0)
    assert "objects" not in data


def test_collect_context_model_brief(engine, monkeypatch) -> None:
    """_collect_context_uncached() учитывает режим brief для раздела модели."""
    mesh = _FakeMesh((0.0, 0.0, 0.0), (10.0, 10.0, 10.0), 500.0, 12)
    objects = [_FakeModelObject([_FakeVolume("part", mesh)])]
    monkeypatch.setattr(
        "flowslice_ai.engine.slicer_context.orca", _fake_orca_with_model(objects)
    )
    ctx = engine._collect_context_uncached({"model": True}, {"model": "brief"})
    assert ctx["model"]["objects_count"] == 1
    assert ctx["model"]["volume_cm3"] == 0.5


def test_collect_context_model_full(engine, monkeypatch) -> None:
    """Полный режим сохраняет детализацию по каждому объекту."""
    mesh = _FakeMesh((0.0, 0.0, 0.0), (10.0, 10.0, 10.0), 500.0, 12)
    objects = [_FakeModelObject([_FakeVolume("part", mesh)])]
    monkeypatch.setattr(
        "flowslice_ai.engine.slicer_context.orca", _fake_orca_with_model(objects)
    )
    ctx = engine._collect_context_uncached({"model": True}, {"model": "full"})
    assert len(ctx["model"]["objects"]) == 1
    assert ctx["model"]["objects"][0]["name"] == "part"


class _InstancedMesh:
    """Меш с вершинами и треугольниками (куб) для проверки глубинных метрик."""

    def __init__(self, np) -> None:
        self.bounding_box = _FakeBBox((0.0, 0.0, 0.0), (10.0, 10.0, 10.0))
        self.volume = 1000.0
        self.is_manifold = True
        self.triangle_count = 12
        self.vertices = np.array(
            [
                [0.0, 0.0, 0.0],
                [10.0, 0.0, 0.0],
                [10.0, 10.0, 0.0],
                [0.0, 10.0, 0.0],
                [0.0, 0.0, 10.0],
                [10.0, 0.0, 10.0],
                [10.0, 10.0, 10.0],
                [0.0, 10.0, 10.0],
            ]
        )
        self.triangles = np.array(
            [
                [0, 2, 1], [0, 3, 2],
                [4, 5, 6], [4, 6, 7],
                [0, 1, 5], [0, 5, 4],
                [1, 2, 6], [1, 6, 5],
                [2, 3, 7], [2, 7, 6],
                [3, 0, 4], [3, 4, 7],
            ]
        )


class _FakeInstance:
    """Экземпляр объекта с мировой матрицей (без зеркалирования)."""

    def __init__(self, matrix) -> None:
        self.matrix = matrix
        self.is_left_handed = False


class _InstancedObject:
    """Объект модели со списком экземпляров."""

    def __init__(self, volume, instances) -> None:
        self._volume = volume
        self.instances = instances

    def volumes(self):
        """Возвращает список объёмов."""
        return [self._volume]


def _instanced_stand():
    """Собирает стенд orca для меша с вершинами и матрицами."""
    np = pytest.importorskip("numpy")
    mesh = _InstancedMesh(np)
    volume = _FakeVolume("cube", mesh)
    volume.matrix = np.eye(4)
    obj = _InstancedObject(volume, [_FakeInstance(np.eye(4))])
    return _fake_orca_with_model([obj]), np


def test_collect_model_deep_geometry(engine, monkeypatch) -> None:
    """Глубокий режим добавляет метрики основания, нависаний и заполнения."""
    stand, np = _instanced_stand()
    monkeypatch.setattr("flowslice_ai.engine.slicer_context.orca", stand)
    data = engine._collect_model_data("deep")
    assert data["deep"] is True
    instance = data["objects"][0]["instances"][0]
    assert instance["height_mm"] == pytest.approx(10.0)
    assert instance["base_area_cm2"] == pytest.approx(1.0)
    assert instance["overhang_area_cm2"] == pytest.approx(0.0)
    assert instance["bbox_fill_ratio"] == pytest.approx(1.0)
    assert instance["surface_area_cm2"] == pytest.approx(6.0)


def test_collect_model_full_has_no_deep_metrics(engine, monkeypatch) -> None:
    """Полный режим не добавляет глубинных метрик и не помечается как deep."""
    stand, _np = _instanced_stand()
    monkeypatch.setattr("flowslice_ai.engine.slicer_context.orca", stand)
    data = engine._collect_model_data("full")
    assert data["deep"] is False
    instance = data["objects"][0]["instances"][0]
    assert "base_area_cm2" not in instance
    assert "overhang_area_cm2" not in instance


def test_context_flags_preserve_model_mode(engine) -> None:
    """Смена флагов контекста не теряет выбранный режим модели."""
    chat = {
        "id": 7,
        "msgs": [],
        "context_flags": {"model": True},
        "context_modes": {"model": "deep"},
    }
    engine._chats = [chat]
    engine._active = 7
    engine._handle_context_flags({"flags": {"model": True}, "modes": {"filament": "all"}})
    assert chat["context_flags"]["model"] is True
    assert chat["context_flags"]["history"] is True
    assert chat["context_modes"]["model"] == "deep"
    assert chat["context_modes"]["filament"] == "all"


def test_context_flags_reject_non_dict(engine) -> None:
    """Некорректные flags не меняют состояние чата."""
    chat = {"id": 7, "msgs": [], "context_flags": {"model": False}}
    engine._chats = [chat]
    engine._active = 7
    engine._handle_context_flags({"flags": "wrong"})
    assert chat["context_flags"] == {"model": False}


def test_normalize_config_drops_legacy_keys(engine) -> None:
    """_normalize_config() вычищает легаси-ключи и фиксирует версию схемы."""
    from flowslice_ai.config import CONFIG_VERSION

    data = {
        "provider": "deepseek",
        "base_url": "https://old.example",
        "api_key": "secret",
        "model": "old",
    }
    result = engine._normalize_config(data)
    for key in ("provider", "base_url", "api_key", "model"):
        assert key not in result
    assert result["config_version"] == CONFIG_VERSION


def test_normalize_config_drops_per_model_credentials(engine) -> None:
    """Креды моделей удаляются: URL и ключ живут только у провайдера."""
    data = {
        "providers": {
            "deepseek": {
                "models": {
                    "deepseek-chat": {
                        "base_url": "https://evil.example",
                        "api_key": "leak",
                        "scheme": "anthropic",
                    }
                }
            }
        }
    }
    result = engine._normalize_config(data)
    model = result["providers"]["deepseek"]["models"]["deepseek-chat"]
    for key in ("base_url", "api_key", "scheme"):
        assert key not in model


def test_openrouter_vision_without_refresh_uses_cache(engine, monkeypatch) -> None:
    """Без refresh карта зрения берётся из кэша, сеть не дёргается."""
    engine._or_models_cache = {"some/model": True}
    engine._or_models_ts = 0.0  # кэш просрочен, но refresh не разрешён

    def fail_urlopen(*args, **kwargs):
        raise AssertionError("сеть не должна вызываться при refresh=False")

    monkeypatch.setattr(
        "flowslice_ai.engine.api_client.urllib.request.urlopen", fail_urlopen
    )
    assert engine._openrouter_vision_map(refresh=False) == {"some/model": True}


