"""Тесты конфигурации движка: загрузка, сохранение, сброс, нормализация."""
from __future__ import annotations

from flowslice_ai.config import DEFAULT_CONFIG


def test_default_config(engine) -> None:
    """load_config() содержит все ключи DEFAULT_CONFIG."""
    loaded = engine.load_config()
    assert set(DEFAULT_CONFIG) <= set(loaded)


def test_save_config_roundtrip(engine) -> None:
    """save_config() возвращает True, load_config() — нормализованный словарь."""
    assert engine.save_config({"a": 1}) is True
    loaded = engine.load_config()
    assert isinstance(loaded, dict)
    assert loaded["a"] == 1


def test_reset_config(engine) -> None:
    """reset_config() возвращает конфигурацию, равную нормализованному дефолту."""
    engine.save_config({"temperature": 1.5, "notes": "мусор"})
    assert engine.reset_config() == engine._normalize_config(DEFAULT_CONFIG.copy())


def test_normalize_invalid_numbers(engine) -> None:
    """Недопустимые числа заменяются безопасными значениями по умолчанию."""
    result = engine._normalize_config(
        {
            "temperature": 99,
            "max_tokens": -5,
            "font_size": 999,
            "compact_threshold": 0,
            "context_window": 1,
        }
    )
    assert result["temperature"] == 0.7
    assert result["max_tokens"] == 4096
    assert result["font_size"] == 14
    assert result["compact_threshold"] == 80
    assert result["context_window"] == 128000


def test_normalize_string_bools(engine) -> None:
    """Строковые значения флагов приводятся к bool."""
    result = engine._normalize_config({"compact_enabled": "off", "reasoning": "on"})
    assert result["compact_enabled"] is False
    assert result["reasoning"] is True


def test_normalize_active_model_fallback(engine) -> None:
    """Неизвестная активная модель заменяется первой доступной у провайдера."""
    result = engine._normalize_config(
        {"active_provider": "deepseek", "active_model": "несуществующая"}
    )
    assert result["active_provider"] == "deepseek"
    model_ids = result["providers"]["deepseek"]["models"]
    assert result["active_model"] in model_ids
    assert result["default_model"].startswith("deepseek::")


def test_normalize_theme_and_language(engine) -> None:
    """Недопустимые тема и язык заменяются на auto/en."""
    result = engine._normalize_config({"theme": "neon", "language": "de"})
    assert result["theme"] == "auto"
    assert result["language"] == "en"


def test_normalize_invalid_default_model(engine) -> None:
    """Битый default_model заменяется связкой активного провайдера и модели."""
    result = engine._normalize_config({"default_model": "нет::такой"})
    assert "::" in result["default_model"]
    assert result["default_model"] != "нет::такой"


def test_normalize_context_block(engine) -> None:
    """Блок context нормализуется до словарей flags/modes."""
    result = engine._normalize_config({"context": "мусор"})
    assert result["context"] == {"flags": {}, "modes": {}}
