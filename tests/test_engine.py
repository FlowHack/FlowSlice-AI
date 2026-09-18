"""Тесты вспомогательных методов движка: токены, i18n, slugify, числа, состояние."""
from __future__ import annotations

import time
import types


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
    """Без флага vision поддержка изображений считается неизвестной."""
    engine._config["active_provider"] = "openai"
    engine._config["active_model"] = "gpt-4o"
    assert engine._model_supports_images() is None


def test_attach_image_blocked_without_vision(engine) -> None:
    """_handle_attach_file() отклоняет изображение без поддержки vision."""
    engine._config["active_provider"] = "deepseek"
    engine._config["active_model"] = "deepseek-chat"
    posted: list[dict] = []
    engine._post = posted.append  # type: ignore[method-assign]
    engine._handle_attach_file({"kind": "image", "name": "a.jpg", "data": "data:x"})
    assert engine._pending_attachments == []
    assert posted and posted[-1]["kind"] == "err"


def test_build_messages_sends_images_over_openai(engine, monkeypatch) -> None:
    """Для OpenAI-совместимой схемы изображения уходят как image_url."""
    engine._config["active_provider"] = "deepseek"
    engine._config["active_model"] = "deepseek-chat"
    monkeypatch.setattr(engine, "_collect_context", lambda flags, modes=None: {})
    monkeypatch.setattr(engine, "_build_system_prompt", lambda ctx, **kwargs: "sys")
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
