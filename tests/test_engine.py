"""Тесты вспомогательных методов движка: токены, i18n, slugify, числа, состояние."""
from __future__ import annotations


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