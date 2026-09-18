"""Тесты настроек: области сброса, персональные провайдеры и модели."""
from __future__ import annotations

from flowslice_ai.config import DEFAULT_CONFIG
from flowslice_ai.providers_data import DEFAULT_PROVIDERS


def test_save_settings_drops_preset_context(engine) -> None:
    """Устаревший ключ preset_context не попадает в конфигурацию."""
    engine._handle_save_settings(
        {"settings": {"theme": "dark", "language": "ru", "preset_context": "all"}}
    )
    assert engine._config["theme"] == "dark"
    assert engine._config["language"] == "ru"
    assert "preset_context" not in engine._config


def test_reset_appearance_keeps_general(engine) -> None:
    """Сброс вкладки «Оформление» не трогает общие значения."""
    engine._handle_save_settings({"settings": {"theme": "dark", "temperature": 1.5}})
    engine._handle_reset_settings({"scope": "appearance"})
    assert engine._config["theme"] == DEFAULT_CONFIG["theme"]
    assert engine._config["temperature"] == 1.5


def test_reset_general_keeps_appearance(engine) -> None:
    """Сброс вкладки «Общие значения» не трогает оформление."""
    engine._handle_save_settings({"settings": {"theme": "dark", "temperature": 1.5}})
    engine._handle_reset_settings({"scope": "general"})
    assert engine._config["temperature"] == DEFAULT_CONFIG["temperature"]
    assert engine._config["theme"] == "dark"


def test_reset_settings_unknown_scope(engine) -> None:
    """Неизвестная область сброса ничего не меняет."""
    engine._handle_save_settings({"settings": {"theme": "dark"}})
    engine._handle_reset_settings({"scope": "models"})
    assert engine._config["theme"] == "dark"


def test_add_provider_with_first_model(engine) -> None:
    """Персональный провайдер создаётся вместе с первой моделью и становится активным."""
    engine._handle_add_provider(
        {
            "name": "My API",
            "base_url": "https://api.example.com/v1",
            "api_key": "sk-test",
            "scheme": "openai",
            "model_id": "my-model",
            "label": "My Model",
        }
    )
    providers = engine._config["providers"]
    custom = [pid for pid, pdef in providers.items() if not pdef.get("builtin")]
    assert len(custom) == 1
    pid = custom[0]
    assert "my-model" in providers[pid]["models"]
    assert providers[pid]["models"]["my-model"]["name"] == "My Model"
    assert engine._config["active_provider"] == pid
    assert engine._config["active_model"] == "my-model"


def test_reset_models_keeps_api_key(engine) -> None:
    """Сброс моделей сохраняет введённый API-ключ встроенного провайдера."""
    engine._config["providers"]["deepseek"]["api_key"] = "sk-keep"
    engine._handle_reset_models()
    assert engine._config["providers"]["deepseek"]["api_key"] == "sk-keep"


def test_reset_custom_models_removes_custom(engine) -> None:
    """Сброс персональных моделей удаляет всех пользовательских провайдеров."""
    engine._handle_add_provider({"name": "My API", "model_id": "m1"})
    engine._handle_reset_custom_models()
    providers = engine._config["providers"]
    assert all(pdef.get("builtin") for pdef in providers.values())
    for pid in DEFAULT_PROVIDERS:
        assert pid in providers
