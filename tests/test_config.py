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


def test_normalize_unknown_keys(engine) -> None:
    """Нормализация неизвестных ключей не падает и возвращает dict."""
    result = engine._normalize_config({"unknown_key": 1})
    assert isinstance(result, dict)