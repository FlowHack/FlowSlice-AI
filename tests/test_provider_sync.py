"""Тесты системы синхронизации метаданных моделей провайдеров."""
from __future__ import annotations

import time

import pytest

from flowslice_ai.sync import (
    FetchedModel,
    SourceContext,
    SourceResult,
    apply_models,
    fetch_provider_metadata,
    sources_for,
    update_model,
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


# ===== Зрение из OpenRouter как общий фолбэк =====

def _fresh_openrouter_cache(engine, mapping: dict[str, bool]) -> None:
    """Кладёт в движок свежий кэш каталога OpenRouter."""
    engine._or_models_cache = dict(mapping)
    engine._or_models_ts = time.time()


def test_apply_openrouter_vision_sets_only_unknown(engine) -> None:
    """Зрение из каталога OpenRouter проставляется только неизвестным моделям."""
    _fresh_openrouter_cache(engine, {"vendor/chat": True, "vendor/text": False})
    models = [
        FetchedModel(id="vendor/chat"),
        FetchedModel(id="vendor/text"),
        FetchedModel(id="vendor/known", vision=True),
        FetchedModel(id="vendor/missing"),
    ]
    result = engine._apply_openrouter_vision(models)
    assert [item.vision for item in result] == [True, False, True, None]
    # Исходные объекты (frozen dataclass) не мутируются.
    assert [item.vision for item in models] == [None, None, True, None]


def test_ui_models_from_fetched_uses_openrouter_fallback(engine) -> None:
    """UI-список берёт зрение из каталога OpenRouter, если провайдер его не дал."""
    _fresh_openrouter_cache(engine, {"vendor/chat": True})
    fetched = SourceResult(models=[FetchedModel(id="vendor/chat", name="Chat")])
    models = engine._ui_models_from_fetched("deepseek", fetched)
    assert models[0]["vision"] is True


def test_ui_models_from_fetched_keeps_known_vision(engine) -> None:
    """Известное зрение провайдера не перезаписывается данными OpenRouter."""
    _fresh_openrouter_cache(engine, {"vendor/chat": False})
    fetched = SourceResult(models=[FetchedModel(id="vendor/chat", vision=True)])
    models = engine._ui_models_from_fetched("deepseek", fetched)
    assert models[0]["vision"] is True


def test_resolve_vision_for_non_openrouter_uses_catalog(engine) -> None:
    """Для провайдера без собственной карты зрение берётся из каталога OpenRouter."""
    _fresh_openrouter_cache(engine, {"vendor/chat": True})
    assert engine._resolve_vision_for("deepseek", "vendor/chat") is True
    assert engine._resolve_vision_for("deepseek", "vendor/absent") is None


def test_resolve_vision_for_provider_map_none_falls_back(engine, monkeypatch) -> None:
    """Пустая карта провайдера с модальностями уступает каталогу OpenRouter."""
    _fresh_openrouter_cache(engine, {"vendor/chat": True})
    monkeypatch.setattr(engine, "_provider_vision_map", lambda _provider: {})
    assert engine._resolve_vision_for("mistral", "vendor/chat") is True


def test_model_supports_images_uses_cached_catalog_no_network(
    engine, monkeypatch
) -> None:
    """Фолбэк зрения берётся из свежего кэша OpenRouter, сеть не дёргается."""
    engine._config["active_provider"] = "deepseek"
    engine._config["active_model"] = "vendor/chat"
    engine._config["providers"]["deepseek"]["models"]["vendor/chat"] = {"name": "Chat"}
    _fresh_openrouter_cache(engine, {"vendor/chat": True})

    def fail_urlopen(*_args, **_kwargs):
        raise AssertionError("сеть не должна вызываться")

    monkeypatch.setattr(
        "flowslice_ai.engine.api_client.urllib.request.urlopen", fail_urlopen
    )
    assert engine._model_supports_images() is True
    # Просроченный кэш не используется и не обновляется на UI-потоке.
    engine._or_models_ts = 0.0
    assert engine._model_supports_images() is None


# ===== Автообновление провайдеров =====

def test_all_provider_sync_worker_disabled(engine, monkeypatch) -> None:
    """При auto_sync_providers=False автосинк не делает ни одного вызова."""
    engine._config["auto_sync_providers"] = False
    calls: list[tuple] = []

    def fake_sync(provider_id, full=False):
        calls.append((provider_id, full))
        return 0, 0, ""

    monkeypatch.setattr(engine, "_sync_provider_metadata", fake_sync)
    engine._all_provider_sync_worker()
    assert calls == []


def _prepare_save_settings(engine, monkeypatch, calls: list[str]) -> None:
    """Готовит движок к вызову сохранения настроек с перехватом фоновых запусков."""
    monkeypatch.setattr(engine, "_post", lambda _message: None)
    monkeypatch.setattr(engine, "_post_settings", lambda: None)
    monkeypatch.setattr(engine, "_send_state", lambda include_images=False: None)
    monkeypatch.setattr(
        engine, "_start_provider_sync", lambda provider_id, full=False: calls.append("sync")
    )
    monkeypatch.setattr(
        engine, "_schedule_vision_refresh", lambda: calls.append("vision")
    )


def test_save_settings_skips_sync_when_disabled(engine, monkeypatch) -> None:
    """Сохранение ключа не запускает автосинк при выключенном флаге."""
    calls: list[str] = []
    _prepare_save_settings(engine, monkeypatch, calls)
    engine._handle_save_settings(
        {"settings": {"auto_sync_providers": False, "api_key": "sk-test"}}
    )
    assert calls == []


def test_save_settings_starts_sync_when_enabled(engine, monkeypatch) -> None:
    """Сохранение ключа запускает автосинк при включённом флаге."""
    calls: list[str] = []
    _prepare_save_settings(engine, monkeypatch, calls)
    engine._config["auto_sync_providers"] = True
    engine._handle_save_settings(
        {"settings": {"auto_sync_providers": True, "api_key": "sk-test"}}
    )
    assert calls == ["sync"]


# ===== Точечное обновление метаданных добавленной модели =====

def test_update_model_wrapper_delegates() -> None:
    """update_model обновляет известные поля и сообщает об изменении."""
    mdef: dict = {"name": "Old", "vision": None}
    assert update_model(mdef, FetchedModel(id="m1", vision=True)) is True
    assert mdef["vision"] is True


def test_model_metadata_worker_updates_from_provider(engine, monkeypatch) -> None:
    """Данные модели берутся из ответа провайдера и пишутся в конфиг."""
    engine._config["providers"]["deepseek"]["models"]["deepseek-chat"] = {
        "name": "Chat",
        "source": "user",
    }
    messages: list[dict] = []
    monkeypatch.setattr(engine, "_post", messages.append)
    monkeypatch.setattr(
        engine,
        "_fetch_provider_models",
        lambda provider, force=False: (
            [
                {
                    "id": "deepseek-chat",
                    "name": "DeepSeek Chat v2",
                    "vision": True,
                    "price_in": 0.1,
                    "price_out": 0.2,
                }
            ],
            "",
        ),
    )
    engine._model_metadata_worker("deepseek", "deepseek-chat")
    mdef = engine._config["providers"]["deepseek"]["models"]["deepseek-chat"]
    assert mdef["name"] == "DeepSeek Chat v2"
    assert mdef["vision"] is True
    assert mdef["vision_source"] == "provider"
    assert mdef["price_in"] == 0.1
    assert mdef["price_out"] == 0.2
    assert mdef["price_source"] == "provider"
    toasts = [msg for msg in messages if msg.get("type") == "toast"]
    assert toasts and "DeepSeek Chat v2" in toasts[0]["text"]


def test_model_metadata_worker_respects_manual(engine, monkeypatch) -> None:
    """Ручные имя, зрение и цены воркер не перетирает."""
    engine._config["providers"]["deepseek"]["models"]["deepseek-chat"] = {
        "name": "Manual",
        "name_source": "manual",
        "vision": False,
        "vision_source": "manual",
        "price_in": 9.0,
        "price_out": 9.5,
        "price_source": "manual",
    }
    messages: list[dict] = []
    monkeypatch.setattr(engine, "_post", messages.append)
    monkeypatch.setattr(
        engine,
        "_fetch_provider_models",
        lambda provider, force=False: (
            [
                {
                    "id": "deepseek-chat",
                    "name": "Vendor",
                    "vision": True,
                    "price_in": 0.1,
                    "price_out": 0.2,
                }
            ],
            "",
        ),
    )
    engine._model_metadata_worker("deepseek", "deepseek-chat")
    mdef = engine._config["providers"]["deepseek"]["models"]["deepseek-chat"]
    assert mdef["name"] == "Manual"
    assert mdef["vision"] is False
    assert mdef["price_in"] == 9.0
    assert not [msg for msg in messages if msg.get("type") == "toast"]


def test_model_metadata_worker_falls_back_to_openrouter(engine, monkeypatch) -> None:
    """Если провайдер не отдал модель, зрение берётся из каталога OpenRouter."""
    engine._config["providers"]["deepseek"]["models"]["vendor/chat"] = {
        "name": "Chat",
        "source": "user",
    }
    _fresh_openrouter_cache(engine, {"vendor/chat": True})
    monkeypatch.setattr(engine, "_post", lambda _message: None)
    monkeypatch.setattr(
        engine, "_fetch_provider_models", lambda provider, force=False: ([], "")
    )
    engine._model_metadata_worker("deepseek", "vendor/chat")
    mdef = engine._config["providers"]["deepseek"]["models"]["vendor/chat"]
    assert mdef["vision"] is True
    assert mdef["vision_source"] == "provider"


# ===== Сопоставление id с каталогом OpenRouter =====

def test_resolve_vision_matches_provider_prefix() -> None:
    """Модель провайдера сопоставляется с префиксом каталога OpenRouter."""
    from flowslice_ai.sync import resolve_vision

    catalog = {"openai/gpt-5.4": True, "google/gemini-3.1-pro": False}
    assert resolve_vision("openai", "gpt-5.4", catalog) is True
    assert resolve_vision("google", "gemini-3.1-pro", catalog) is False


def test_resolve_vision_normalizes_dots_and_case() -> None:
    """Точки, подчёркивания и регистр не мешают сопоставлению."""
    from flowslice_ai.sync import resolve_vision

    catalog = {"anthropic/claude-sonnet-4.6": True}
    assert resolve_vision("anthropic", "claude-sonnet-4-6", catalog) is True
    assert resolve_vision("anthropic", "Claude_Sonnet_4.6", catalog) is True


def test_resolve_vision_no_cross_provider_false_positive() -> None:
    """Без префикса провайдера чужие модели не подставляются."""
    from flowslice_ai.sync import resolve_vision

    catalog = {"openai/gpt-5.4": True}
    assert resolve_vision("groq", "gpt-5.4", catalog) is None
    assert resolve_vision("openai", "absent", catalog) is None


def test_builtin_vision_defaults_unknown_is_none() -> None:
    """Неизвестное зрение встроенных моделей — None, известное — True/False."""
    from flowslice_ai.providers_data import DEFAULT_PROVIDERS

    groq_models = DEFAULT_PROVIDERS["groq"]["models"].values()
    assert all(model["vision"] is None for model in groq_models)
    assert all(
        model["vision"] is None for model in DEFAULT_PROVIDERS["cerebras"]["models"].values()
    )
    assert DEFAULT_PROVIDERS["deepseek"]["models"]["deepseek-chat"]["vision"] is False
    assert DEFAULT_PROVIDERS["google"]["models"]["gemini-2.5-flash"]["vision"] is True
