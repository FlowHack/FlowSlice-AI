"""Тесты локализованных меток параметров OrcaSlicer."""

from flowslice_ai.setting_labels import (
    humanize_params,
    humanize_presets,
    labels_for,
    param_name,
)


def test_known_setting_translated_to_russian() -> None:
    """Русская метка берётся из словаря переводов OrcaSlicer."""
    assert param_name("ru", "brim_type") == "Тип каймы"


def test_english_labels_available() -> None:
    """Английские метки есть всегда — они исходные в PrintConfig.cpp."""
    assert param_name("en", "layer_height") == "Layer height"


def test_unknown_language_falls_back_to_english() -> None:
    """Для сербского (нет локали в Orca) отдаётся английский словарь."""
    assert labels_for("sr") is labels_for("en")


def test_humanize_params_keeps_unknown_keys() -> None:
    """Неизвестные ключи остаются как есть, известные получают метку."""
    result = humanize_params({"brim_type": "no_brim", "custom_key": 1}, "ru")
    assert result == {"Тип каймы (brim_type)": "no_brim", "custom_key": 1}


def test_humanize_presets_does_not_mutate_source() -> None:
    """Исходный кэшированный контекст не изменяется."""
    source = {"print": {"name": "P", "params": {"brim_type": "no_brim"}}}
    result = humanize_presets(source, "ru")
    assert result["print"]["params"] == {"Тип каймы (brim_type)": "no_brim"}
    assert source["print"]["params"] == {"brim_type": "no_brim"}
