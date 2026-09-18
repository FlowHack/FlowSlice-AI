"""Тесты вспомогательных методов движка: токены, i18n, slugify, числа, состояние."""
from __future__ import annotations

import time
import types

from flowslice_ai.constants import (
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
    """_t() возвращает непустую строку для существующего ключа."""
    assert engine._t("win.opened")


def test_slugify(engine) -> None:
    """_slugify() приводит имя провайдера к нижнему регистру с дефисами."""
    assert engine._slugify("My Provider") == "my-provider"


def test_random_suffix(engine) -> None:
    """_random_suffix() возвращает строку длины 4."""
    assert len(engine._random_suffix()) == 4


def test_as_int(engine) -> None:
    """_as_int() парсит число либо возвращает значение по умолчанию."""
    assert engine._as_int("42", 0) == 42
    assert engine._as_int("abc", 7) == 7


def test_handle_get_state(engine) -> None:
    """_handle_get_state() не падает без установленного sink."""
    engine._handle_get_state()


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


def test_collect_preset_data_all_differs_from_changed(engine, monkeypatch) -> None:
    """Режим "all" отдаёт унаследованные ключи, режим "changed" — только свои."""

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

    class _Collection:
        """Заглушка коллекции пресетов с выбранным пресетом."""

        def __init__(self, presets: dict[str, _Preset], selected: _Preset) -> None:
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

    class _Bundle:
        """Заглушка бандла с тремя коллекциями и объединённым конфигом."""

        def __init__(self, collection: _Collection) -> None:
            self.printers = collection
            self.filaments = collection
            self.prints = collection

        def full_config_value(self, key: str):
            """Объединённый конфиг в заглушке пуст."""
            return None

    base = _Preset("Base @P", {"printer_model": "MyPrinter", "nozzle_diameter": "0.4"})
    user = _Preset("User @P", {"inherits": "Base @P", "printable_height": "390"})
    bundle = _Bundle(_Collection({"Base @P": base, "User @P": user}, user))
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

    class _Preset:
        """Заглушка пресета, чей config уже содержит унаследованные ключи."""

        def __init__(self, name: str, values: dict) -> None:
            self.name = name
            self._values = values

        def config_keys(self):
            """Возвращает ключи пресета."""
            return list(self._values)

        def config_value(self, key: str):
            """Возвращает значение ключа."""
            return self._values.get(key)

    class _Collection:
        """Заглушка коллекции пресетов с выбранным пресетом."""

        def __init__(self, presets: dict[str, _Preset], selected: _Preset) -> None:
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

    class _Bundle:
        """Заглушка бандла с тремя коллекциями."""

        def __init__(self, collection: _Collection) -> None:
            self.printers = collection
            self.filaments = collection
            self.prints = collection

        def full_config_value(self, key: str):
            """Объединённый конфиг в заглушке пуст."""
            return None

    base = _Preset("Base @P", {"printer_model": "MyPrinter", "nozzle_diameter": "0.4"})
    user = _Preset(
        "User @P",
        {
            "inherits": "Base @P",
            "printer_model": "MyPrinter",
            "nozzle_diameter": "0.6",
        },
    )
    bundle = _Bundle(_Collection({"Base @P": base, "User @P": user}, user))
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
    monkeypatch.setattr(engine, "_model_supports_images", lambda: True)
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
