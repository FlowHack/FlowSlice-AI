"""Тесты системы синхронизации метаданных моделей провайдеров."""
from __future__ import annotations

import pytest

from flowslice_ai.sync import (
    FetchedModel,
    SourceContext,
    apply_models,
    fetch_provider_metadata,
    sources_for,
)


# ===== Политика слияния apply_models =====

def test_apply_models_adds_new_model_with_metadata() -> None:
    """Новая модель получает source=provider, зрение и цены."""
    models: dict = {}
    added, updated = apply_models(
        models,
        [
            FetchedModel(
                id="m1", name="Model 1", vision=True, price_in=1.0, price_out=2.5
            )
        ],
        False,
    )
    assert (added, updated) == (1, 0)
    entry = models["m1"]
    assert entry["name"] == "Model 1"
    assert entry["builtin"] is False
    assert entry["source"] == "provider"
    assert entry["temperature"] is None
    assert entry["max_tokens"] is None
    assert entry["reasoning"] is None
    assert entry["vision"] is True
    assert entry["vision_source"] == "provider"
    assert entry["price_in"] == 1.0
    assert entry["price_out"] == 2.5
    assert entry["price_source"] == "provider"


def test_apply_models_new_model_without_metadata() -> None:
    """Без зрения и цен новая модель не получает соответствующих ключей."""
    models: dict = {}
    apply_models(models, [FetchedModel(id="m2")], False)
    entry = models["m2"]
    assert entry["name"] == "m2"
    assert "vision" not in entry
    assert "price_in" not in entry


def test_apply_models_updates_only_missing_vision_and_price() -> None:
    """Обновляются только отсутствующие зрение/цены, настройки не трогаются."""
    models = {
        "m1": {
            "name": "Old",
            "builtin": True,
            "temperature": 0.3,
            "max_tokens": 100,
            "reasoning": True,
            "vision": None,
            "price_in": None,
            "price_out": None,
        }
    }
    added, updated = apply_models(
        models,
        [FetchedModel(id="m1", name="New", vision=False, price_in=1.0, price_out=2.0)],
        False,
    )
    assert (added, updated) == (0, 1)
    entry = models["m1"]
    assert entry["name"] == "New"
    assert entry["name_source"] == "provider"
    assert entry["vision"] is False
    assert entry["vision_source"] == "provider"
    assert entry["price_in"] == 1.0
    assert entry["price_source"] == "provider"
    assert entry["temperature"] == 0.3
    assert entry["max_tokens"] == 100
    assert entry["reasoning"] is True


def test_apply_models_respects_manual_sources() -> None:
    """Ручные имя, зрение и цены синхронизация не перезаписывает."""
    models = {
        "m1": {
            "name": "Keep",
            "name_source": "manual",
            "vision": False,
            "vision_source": "manual",
            "price_in": 9.0,
            "price_out": 9.5,
            "price_source": "manual",
        }
    }
    added, updated = apply_models(
        models,
        [FetchedModel(id="m1", name="Other", vision=True, price_in=1.0, price_out=2.0)],
        True,
    )
    assert (added, updated) == (0, 0)
    entry = models["m1"]
    assert entry["name"] == "Keep"
    assert entry["vision"] is False
    assert entry["price_in"] == 9.0
    assert entry["price_out"] == 9.5


def test_apply_models_user_model_skipped_until_full() -> None:
    """source=user пропускается автосинком и обрабатывается полным."""
    models = {"m1": {"name": "Custom", "source": "user", "vision": None}}
    added, updated = apply_models(models, [FetchedModel(id="m1", name="Vendor", vision=True)], False)
    assert (added, updated) == (0, 0)
    assert models["m1"]["name"] == "Custom"
    assert models["m1"]["vision"] is None
    added, updated = apply_models(models, [FetchedModel(id="m1", name="Vendor", vision=True)], True)
    assert (added, updated) == (0, 1)
    assert models["m1"]["name"] == "Vendor"
    assert models["m1"]["vision"] is True


def test_apply_models_does_not_clear_prices() -> None:
    """Отсутствующая у источника цена не удаляет уже сохранённую."""
    models = {"m1": {"name": "M", "price_in": 5.0, "price_out": 6.0, "price_source": "provider"}}
    added, updated = apply_models(models, [FetchedModel(id="m1", name=None)], False)
    assert (added, updated) == (0, 0)
    assert models["m1"]["price_in"] == 5.0
    assert models["m1"]["price_out"] == 6.0


def test_apply_models_counts_mixed_changes() -> None:
    """added/updated считают добавления и реальные изменения раздельно."""
    models = {"m1": {"name": "M1", "vision": None}, "m2": {"name": "M2"}}
    added, updated = apply_models(
        models,
        [
            FetchedModel(id="m1", vision=True),
            FetchedModel(id="m2"),
            FetchedModel(id="m3", name="M3"),
        ],
        False,
    )
    assert (added, updated) == (1, 1)


# ===== Источники и оркестрация =====

def _ctx(provider_id: str, scheme: str = "openai", api_key: str = "") -> SourceContext:
    """Собирает контекст опроса для тестов."""
    return SourceContext(
        provider_id=provider_id,
        base_url="https://nordrouter.com/v1",
        api_key=api_key,
        scheme=scheme,
    )


def test_sources_for_orders_by_priority() -> None:
    """sources_for сортирует применимые источники по возрастанию priority."""
    ctx = _ctx("nordrouter")
    ids = [source.id for source in sources_for(ctx)]
    assert ids == ["vision_cross_map", "openai_models", "nordrouter_pricing"]


def test_nordrouter_pricing_without_key(monkeypatch: pytest.MonkeyPatch) -> None:
    """Публичный прайс NordRouter доступен без ключа, цена попадает в модель."""
    calls: list[str] = []

    def fake_http_json(url, headers=None, timeout=10):
        calls.append(url)
        return {"models": [{"id": "vendor/a", "in_usd": 0.25, "out_usd": 1.5}]}

    monkeypatch.setattr("flowslice_ai.sync.base.http_json", fake_http_json)
    result = fetch_provider_metadata(_ctx("nordrouter"))
    assert "https://nordrouter.com/auth/pricing" in calls
    assert result.prices["vendor/a"] == (0.25, 1.5)
    model = next(item for item in result.models if item.id == "vendor/a")
    assert model.price_in == 0.25
    assert model.price_out == 1.5


def test_openrouter_catalog_prices_and_vision(monkeypatch: pytest.MonkeyPatch) -> None:
    """Публичный каталог OpenRouter даёт модели, зрение и цены без ключа."""

    def fake_http_json(url, headers=None, timeout=10):
        return {
            "data": [
                {
                    "id": "vendor/chat",
                    "name": "Vendor Chat",
                    "architecture": {
                        "input_modalities": ["text", "image"],
                        "output_modalities": ["text"],
                    },
                    "pricing": {"prompt": "0.0000005", "completion": "0.0000015"},
                },
                {"id": "vendor/embedding", "name": "Embedding"},
            ]
        }

    monkeypatch.setattr("flowslice_ai.sync.base.http_json", fake_http_json)
    result = fetch_provider_metadata(_ctx("openrouter"))
    assert [model.id for model in result.models] == ["vendor/chat"]
    assert result.models[0].vision is True
    assert result.models[0].price_in == 0.5
    assert result.models[0].price_out == 1.5


def test_vision_cross_map_for_nordrouter(monkeypatch: pytest.MonkeyPatch) -> None:
    """Карта зрения NordRouter строится по каталогу OpenRouter."""

    def fake_http_json(url, headers=None, timeout=10):
        return {
            "data": [
                {
                    "id": "x-ai/grok-4.5",
                    "architecture": {
                        "input_modalities": ["text", "image"],
                        "output_modalities": ["text"],
                    },
                },
                {
                    "id": "deepseek/deepseek-v4-pro",
                    "architecture": {
                        "input_modalities": ["text"],
                        "output_modalities": ["text"],
                    },
                },
            ]
        }

    monkeypatch.setattr("flowslice_ai.sync.base.http_json", fake_http_json)
    result = fetch_provider_metadata(_ctx("nordrouter"))
    assert result.vision["x-ai/grok-4.5"] is True
    assert result.vision["deepseek/deepseek-v4-pro"] is False


def test_fetch_requires_key_without_public_source(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Без ключа и без публичных источников возвращается models.need_key."""
    def fake_http_json(url, headers=None, timeout=10):
        raise AssertionError("сеть не должна вызываться без ключа")

    monkeypatch.setattr("flowslice_ai.sync.base.http_json", fake_http_json)
    result = fetch_provider_metadata(_ctx("deepseek"))
    assert result.error == "models.need_key"
    assert result.models == []


# ===== Интеграция с движком =====

def test_provider_sync_worker_updates_config(engine, monkeypatch) -> None:
    """Воркер синка переносит цены/зрение в конфиг и постит api_models."""
    engine._config["providers"]["nordrouter"]["api_key"] = "sk-test"
    messages: list[dict] = []
    monkeypatch.setattr(engine, "_post", messages.append)

    def fake_http_json(url, headers=None, timeout=10):
        if url.endswith("/auth/pricing"):
            return {"models": [{"id": "deepseek/deepseek-v4-flash", "in_usd": 0.5, "out_usd": 1.5}]}
        if "openrouter.ai" in url:
            return {
                "data": [
                    {
                        "id": "deepseek/deepseek-v4-flash",
                        "architecture": {
                            "input_modalities": ["text", "image"],
                            "output_modalities": ["text"],
                        },
                    }
                ]
            }
        return {"data": [{"id": "deepseek/deepseek-v4-flash"}]}

    monkeypatch.setattr("flowslice_ai.sync.base.http_json", fake_http_json)
    engine._provider_sync_worker("nordrouter", True)

    mdef = engine._config["providers"]["nordrouter"]["models"]["deepseek/deepseek-v4-flash"]
    assert mdef["name"] == "DeepSeek V4 Flash"
    assert mdef["vision"] is True
    assert mdef["vision_source"] == "provider"
    assert mdef["price_in"] == 0.5
    assert mdef["price_out"] == 1.5
    assert mdef["price_source"] == "provider"

    api_msgs = [msg for msg in messages if msg.get("type") == "api_models"]
    assert api_msgs
    assert api_msgs[0]["provider"] == "nordrouter"
    assert api_msgs[0]["error"] == ""
    assert any(item["id"] == "deepseek/deepseek-v4-flash" for item in api_msgs[0]["models"])


def test_provider_sync_worker_reports_missing_key(engine, monkeypatch) -> None:
    """Без ключа синк отдаёт понятную ошибку, а не падает."""
    messages: list[dict] = []
    monkeypatch.setattr(engine, "_post", messages.append)
    engine._provider_sync_worker("deepseek", False)
    toasts = [msg for msg in messages if msg.get("type") == "toast"]
    assert toasts and toasts[0]["kind"] == "err"
    assert engine._t("models.need_key") in toasts[0]["text"]


def test_handle_sync_provider_starts_worker(engine, monkeypatch) -> None:
    """_handle_sync_provider показывает loading и запускает воркер."""
    messages: list[dict] = []
    monkeypatch.setattr(engine, "_post", messages.append)
    monkeypatch.setattr(
        engine,
        "_provider_sync_worker",
        lambda provider_id, full: messages.append(
            {"type": "worker", "provider": provider_id, "full": full}
        ),
    )

    class _FakeThread:
        """Поток-заглушка, выполняющий цель синхронно."""

        def __init__(self, target, args=(), name="", daemon=False):
            self._target = target
            self._args = args

        def start(self):
            """Запускает цель в текущем потоке."""
            self._target(*self._args)

    monkeypatch.setattr("flowslice_ai.engine.api_client.threading.Thread", _FakeThread)
    engine._post_sink = lambda payload: None
    engine._handle_sync_provider({"provider": "nordrouter", "full": True})
    assert messages[0] == {"type": "models_loading", "provider": "nordrouter", "loading": True}
    assert messages[1] == {"type": "worker", "provider": "nordrouter", "full": True}


def test_handle_sync_provider_rejects_unknown(engine, monkeypatch) -> None:
    """Неизвестный провайдер не запускает синхронизацию."""
    messages: list[dict] = []
    monkeypatch.setattr(engine, "_post", messages.append)
    engine._handle_sync_provider({"provider": "nope"})
    assert messages and messages[0]["kind"] == "err"
