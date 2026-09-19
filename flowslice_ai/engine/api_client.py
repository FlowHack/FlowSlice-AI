"""HTTP-клиент и SSE-стриминг движка FlowSlice AI.

Миксин ApiClientMixin выполняет запросы к API провайдеров (OpenAI-совместимые
и нативный Messages API Anthropic), читает SSE-потоки и проверяет API-ключи.
"""
# pyright (миксины _ChatEngine): reportGeneralTypeIssues отключён только здесь.
# pyright: reportGeneralTypeIssues=false
# pylint: disable=too-many-lines,too-many-statements,too-many-branches
# pylint: disable=too-many-locals,too-many-arguments,too-many-positional-arguments
# pylint: disable=too-many-public-methods,too-few-public-methods

import json
import threading
import time
from dataclasses import replace
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import TYPE_CHECKING, Any
import urllib.error
import urllib.request

if TYPE_CHECKING:
    from flowslice_ai.engine import _ChatEngine

from flowslice_ai.constants import (
    HTTP_HEADERS,
    MAX_REPLY_CHARS,
    MAX_THOUGHT_CHARS,
    STREAM_THROTTLE,
    TIMEOUT,
)
from flowslice_ai.engine.net import normalize_base_url
from flowslice_ai.errors import ApiError, ConfigError, NetworkError, StreamError
from flowslice_ai.logging import _LOGGER
from flowslice_ai.sync.base import SourceContext, SourceResult
from flowslice_ai.sync.fetch import fetch_provider_metadata, resolve_vision
from flowslice_ai.sync.merge import apply_models
from flowslice_ai.sync.sources import vision_from_entry

_OR_MODELS_TTL = 600.0  # секунд: срок жизни кэша списка моделей OpenRouter
_OR_MODELS_TIMEOUT = 6  # секунд: короткий таймаут, чтобы не блокировать UI
_OR_MODELS_URL = "https://openrouter.ai/api/v1/models"

# Провайдеры, у которых поддержку изображений можно узнать запросом к API.
# Провайдеры, отдающие машинно-читаемый признак зрения в списке моделей.
# Cerebras исключён: по официальной доке /v1/models возвращает только
# id/object/created/owned_by, признака модальностей там нет.
_VISION_API_PROVIDERS = ("openrouter", "anthropic", "mistral", "xai")
_VISION_CACHE_TTL = 600.0  # секунд: срок жизни кэша зрения по провайдеру
_VISION_TIMEOUT = 8  # секунд
_ANTHROPIC_VERSION = "2023-06-01"

# Повторы временных сбоев: количество попыток и паузы между ними (секунды).
_RETRY_ATTEMPTS = 3
_RETRY_BACKOFF = (1.0, 2.0)
_RETRY_STATUSES = (429, 500, 502, 503, 504)
_RETRY_MAX_WAIT = 15.0

# Подгрузка реального списка моделей провайдера в UI.
_MODELS_CACHE_TTL = 600.0  # секунд: срок жизни кэша списка моделей провайдера
_MODELS_TIMEOUT = 10  # секунд: запрос списка моделей не должен блокировать UI
# Подстроки в идентификаторе модели, по которым отсекаются заведомо
# нетекстовые модели (распознавание речи, эмбеддинги, генерация картинок).
_NON_TEXT_MODEL_HINTS = ("whisper", "tts", "embedding", "dall-e", "moderation", "image")


class ApiClientMixin:
    """Запросы к API провайдеров, чтение SSE-потоков, проверка ключей."""

    def _api_credentials_for(
        self: "_ChatEngine", provider_id: str, model_id: str = ""
    ) -> tuple[str, str, str, str, str]:
        """Возвращает (provider_id, base_url, api_key, model, scheme) провайдера.

        URL, ключ и схема задаются ТОЛЬКО на уровне провайдера: у всех его
        моделей один и тот же эндпоинт и один и тот же ключ доступа.
        """
        prov = self._config.get("providers", {}).get(provider_id)
        if not isinstance(prov, dict):
            prov = {}
        base_url = str(prov.get("base_url", ""))
        api_key = str(prov.get("api_key", ""))
        model = str(model_id or "")
        scheme = str(prov.get("scheme") or "openai")
        return provider_id, base_url, api_key, model, scheme

    def _active_api_credentials(self: "_ChatEngine") -> tuple[str, str, str, str, str]:
        """Возвращает учётные данные активного провайдера и модели."""
        cfg = self._config
        return self._api_credentials_for(
            str(cfg.get("active_provider", "deepseek")),
            str(cfg.get("active_model", "")),
        )

    def _active_scheme(self: "_ChatEngine") -> str:
        """Возвращает схему API активного провайдера без повторной синхронизации."""
        cfg = self._config
        provider_id = str(cfg.get("active_provider", "deepseek"))
        prov = cfg.get("providers", {}).get(provider_id)
        if not isinstance(prov, dict):
            return "openai"
        return str(prov.get("scheme") or "openai")

    def _validated_base_url(self: "_ChatEngine", base_url: str) -> str:
        """Проверяет base_url перед запросом и переводит ошибку на язык UI."""
        try:
            return normalize_base_url(base_url)
        except ConfigError as exc:
            raise ConfigError(self._t(str(exc))) from exc

    def _openrouter_vision_map(
        self: "_ChatEngine", refresh: bool = False
    ) -> dict[str, bool]:
        """Возвращает карту «id модели OpenRouter → поддержка изображений».

        Список моделей OpenRouter публичный (без ключа), поэтому кэшируется
        на _OR_MODELS_TTL секунд. При сетевой ошибке возвращается прежний кэш.
        Без refresh сеть не запрашивается — метод безопасен для UI-потока.
        """
        now = time.time()
        cache = self._or_models_cache
        if cache and now - self._or_models_ts < _OR_MODELS_TTL:
            return cache
        if not refresh:
            # Без разрешения на сеть отдаём только актуальный кэш: метод
            # вызывается из UI-потока, где блокирующий запрос недопустим.
            return cache
        result: dict[str, bool] = {}
        try:
            request = urllib.request.Request(_OR_MODELS_URL, headers=HTTP_HEADERS)
            with urllib.request.urlopen(request, timeout=_OR_MODELS_TIMEOUT) as response:
                payload = json.loads(response.read().decode("utf-8", "replace"))
            for entry in payload.get("data", []):
                if not isinstance(entry, dict):
                    continue
                model_id = str(entry.get("id", ""))
                if not model_id:
                    continue
                value = self._vision_from_entry(entry)
                if value is not None:
                    result[model_id] = value
        except (urllib.error.URLError, TimeoutError, ValueError, OSError) as exc:
            _LOGGER.warning("Не удалось получить список моделей OpenRouter: %s", exc)
            result = cache
        if result:
            self._or_models_cache = result
            self._or_models_ts = now
        return result

    def _cached_openrouter_vision(self: "_ChatEngine") -> dict[str, bool]:
        """Возвращает карту зрения OpenRouter только из свежего кэша, без сети.

        Используется на UI-потоке, где блокирующий запрос недопустим: если
        кэш пуст или просрочен, возвращается пустой словарь.
        """
        now = time.time()
        if self._or_models_cache and now - self._or_models_ts < _OR_MODELS_TTL:
            return self._or_models_cache
        return {}

    def _apply_openrouter_vision(
        self: "_ChatEngine",
        models: list[Any],
        refresh: bool = False,
        provider_id: str = "",
    ) -> list[Any]:
        """Проставляет зрение моделей по публичному каталогу OpenRouter.

        Данные каталога запрашиваются один раз (с учётом кэша _OR_MODELS_TTL).
        Идентификатор модели сопоставляется с каталогом с учётом префикса
        провайдера. Модели, у которых зрение уже известно, и исходные объекты
        не меняются: возвращается новый список, а обновлённые элементы — через
        :func:`dataclasses.replace`.
        """
        mapping = self._openrouter_vision_map(refresh=refresh)
        if not mapping:
            return models
        result: list[Any] = []
        for model in models:
            if model.vision is None:
                value = resolve_vision(provider_id, model.id, mapping)
                if value is not None:
                    result.append(replace(model, vision=bool(value)))
                    continue
            result.append(model)
        return result

    def _provider_models_url(self: "_ChatEngine", provider_id: str, base_url: str) -> str:
        """Собирает URL списка моделей для провайдера."""
        base = base_url.rstrip("/")
        if provider_id == "anthropic":
            return base + "/models?limit=1000"
        if provider_id == "xai":
            return base + "/language-models"
        if provider_id == "google":
            # base_url указывает на OpenAI-совместимый префикс, а список
            # моделей живёт в нативном /v1beta/models.
            suffix = "/openai"
            if base.endswith(suffix):
                base = base[: -len(suffix)]
            return base + "/models"
        return base + "/models"

    def _provider_models_headers(
        self: "_ChatEngine", provider_id: str, api_key: str
    ) -> dict[str, str]:
        """Возвращает заголовки запроса списка моделей с учётом схемы провайдера."""
        headers = dict(HTTP_HEADERS)
        if not api_key:
            return headers
        if provider_id == "anthropic":
            headers["x-api-key"] = api_key
            headers["anthropic-version"] = _ANTHROPIC_VERSION
        elif provider_id == "google":
            headers["x-goog-api-key"] = api_key
        else:
            headers["Authorization"] = "Bearer " + api_key
        return headers

    @staticmethod
    def _vision_from_entry(entry: dict[str, Any]) -> bool | None:
        """Извлекает признак «модель принимает изображения и отвечает текстом».

        Делегирует в общую реализацию пакета синхронизации, чтобы правила
        разбора модальностей были едины для UI и фонового синка.
        """
        return vision_from_entry(entry)

    def _provider_vision_map(self: "_ChatEngine", provider_id: str) -> dict[str, bool]:
        """Возвращает карту «id модели → поддержка изображений» для провайдера.

        Результат кэшируется на _VISION_CACHE_TTL секунд. При сетевой ошибке
        возвращается прежний кэш (если он был).
        """
        now = time.time()
        cached = self._vision_cache.get(provider_id)
        if cached and now - cached[0] < _VISION_CACHE_TTL:
            return cached[1]
        prov = self._config.get("providers", {}).get(provider_id)
        if not isinstance(prov, dict):
            return {}
        base_url = str(prov.get("base_url", "")).strip()
        if not base_url:
            return {}
        try:
            base_url = normalize_base_url(base_url)
        except ConfigError as exc:
            _LOGGER.warning("Некорректный base_url провайдера %s: %s", provider_id, exc)
            return cached[1] if cached else {}
        api_key = str(prov.get("api_key", "")).strip()
        headers = self._provider_models_headers(provider_id, api_key)
        url = self._provider_models_url(provider_id, base_url)
        result: dict[str, bool] = {}
        try:
            request = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(request, timeout=_VISION_TIMEOUT) as response:
                payload = json.loads(response.read().decode("utf-8", "replace"))
            result = self._parse_vision_payload(payload)
        except (urllib.error.URLError, TimeoutError, ValueError, OSError) as exc:
            _LOGGER.warning("Не удалось получить зрение моделей %s: %s", provider_id, exc)
            result = cached[1] if cached else {}
        if result:
            self._vision_cache[provider_id] = (now, result)
        return result

    def _parse_vision_payload(self: "_ChatEngine", payload: Any) -> dict[str, bool]:
        """Разбирает ответ провайдера в карту «id модели → зрение»."""
        if not isinstance(payload, dict):
            return {}
        items = payload.get("data")
        if not isinstance(items, list):
            items = payload.get("models")
        if not isinstance(items, list):
            return {}
        result: dict[str, bool] = {}
        for entry in items:
            if not isinstance(entry, dict):
                continue
            model_id = str(entry.get("id") or entry.get("name") or "")
            value = self._vision_from_entry(entry)
            if model_id and value is not None:
                result[model_id] = value
        return result

    @staticmethod
    def _is_text_model(provider_id: str, entry: dict[str, Any]) -> bool:
        """Проверяет, умеет ли модель отвечать текстом.

        Отсекает распознавание речи, синтез, эмбеддинги и генерацию изображений,
        чтобы в списке выбора не было заведомо непригодных моделей.
        """
        arch = entry.get("architecture")
        outputs = arch.get("output_modalities") if isinstance(arch, dict) else None
        if isinstance(outputs, list):
            return "text" in outputs
        caps = entry.get("capabilities")
        if isinstance(caps, dict) and isinstance(caps.get("completion_chat"), bool):
            return bool(caps["completion_chat"])
        methods = entry.get("supportedGenerationMethods")
        if isinstance(methods, list):
            return "generateContent" in methods
        model_id = str(entry.get("id") or entry.get("name") or entry.get("model") or "").lower()
        return not any(hint in model_id for hint in _NON_TEXT_MODEL_HINTS)

    @staticmethod
    def _model_price(
        provider_id: str, entry: dict[str, Any]
    ) -> tuple[float | None, float | None]:
        """Возвращает (цена ввода, цена вывода) за 1M токенов.

        Цена есть только у OpenRouter (в поле ``pricing`` она указана за токен).
        Для остальных провайдеров возвращается (None, None).
        """
        if provider_id != "openrouter":
            return None, None
        pricing = entry.get("pricing")
        if not isinstance(pricing, dict):
            return None, None

        def _per_million(value: Any) -> float | None:
            try:
                return round(float(value) * 1_000_000, 4)
            except (TypeError, ValueError):
                return None

        return _per_million(pricing.get("prompt")), _per_million(pricing.get("completion"))

    @staticmethod
    def _model_display_name(entry: dict[str, Any], model_id: str) -> str:
        """Возвращает человекочитаемое имя модели из ответа провайдера."""
        display = str(
            entry.get("display_name")
            or entry.get("displayName")
            or entry.get("name")
            or ""
        ).strip()
        # У Google поле name содержит "models/...", а не название.
        if not display or display == model_id or display.startswith("models/"):
            return model_id
        return display

    def _parse_models_payload(
        self: "_ChatEngine", provider_id: str, payload: Any
    ) -> list[dict[str, Any]]:
        """Разбирает ответ провайдера в список моделей для UI."""
        if not isinstance(payload, dict):
            return []
        items = payload.get("data")
        if not isinstance(items, list):
            items = payload.get("models")
        if not isinstance(items, list):
            return []
        result: list[dict[str, Any]] = []
        seen: set[str] = set()
        for entry in items:
            if not isinstance(entry, dict):
                continue
            model_id = str(
                entry.get("id") or entry.get("name") or entry.get("model") or ""
            ).strip()
            if provider_id == "google" and model_id.startswith("models/"):
                model_id = model_id[len("models/") :]
            if not model_id or model_id in seen:
                continue
            if not self._is_text_model(provider_id, entry):
                continue
            seen.add(model_id)
            price_in, price_out = self._model_price(provider_id, entry)
            result.append(
                {
                    "id": model_id,
                    "name": self._model_display_name(entry, model_id),
                    "vision": self._vision_from_entry(entry),
                    "price_in": price_in,
                    "price_out": price_out,
                }
            )
        result.sort(key=lambda item: str(item.get("name", "")).lower())
        return result

    def _fetch_provider_models(
        self: "_ChatEngine", provider_id: str, force: bool = False
    ) -> tuple[list[dict[str, Any]], str]:
        """Загружает список моделей провайдера.

        Возвращает (список моделей, текст ошибки). Результат кэшируется на
        _MODELS_CACHE_TTL секунд; при сбое возвращается прежний кэш (если был),
        а вторым элементом — понятное пользователю описание ошибки.
        """
        now = time.time()
        cached = self._api_models_cache.get(provider_id)
        if cached and not force and now - cached[0] < _MODELS_CACHE_TTL:
            return cached[1], ""
        prov = self._config.get("providers", {}).get(provider_id)
        if not isinstance(prov, dict):
            return [], self._t("models.provider_missing")
        base_url = str(prov.get("base_url", "")).strip()
        if not base_url:
            return [], self._t("models.no_base_url")
        try:
            base_url = normalize_base_url(base_url)
        except ConfigError as exc:
            _LOGGER.warning("Некорректный base_url провайдера %s: %s", provider_id, exc)
            return (cached[1] if cached else []), self._t("models.fetch_failed")
        stale = cached[1] if cached else []
        ctx = SourceContext(
            provider_id=provider_id,
            base_url=base_url,
            api_key=str(prov.get("api_key", "")).strip(),
            scheme=str(prov.get("scheme") or "openai"),
            timeout=_MODELS_TIMEOUT,
        )
        # Список, зрение и цены берутся из единой системы источников, чтобы
        # выпадающий список и кнопка «Обновить от провайдера» показывали одни
        # и те же данные (включая публичные каталоги вроде NordRouter).
        fetched = fetch_provider_metadata(ctx)
        if not fetched.models and fetched.error:
            if fetched.error.startswith("models."):
                return stale, self._t(fetched.error)
            _LOGGER.warning(
                "Не удалось получить список моделей %s: %s", provider_id, fetched.error
            )
            return stale, self._t("models.fetch_failed")
        models = self._ui_models_from_fetched(provider_id, fetched)
        if models:
            self._api_models_cache[provider_id] = (now, models)
        return models, ""

    def _handle_refresh_models(self: "_ChatEngine", message: dict) -> None:
        """Запускает фоновую загрузку списка моделей провайдера по запросу UI."""
        provider_id = str(message.get("provider", ""))
        if not provider_id:
            return
        force = bool(message.get("force", False))
        if self._post_sink is None:
            return
        self._post({"type": "models_loading", "provider": provider_id, "loading": True})
        threading.Thread(
            target=self._models_refresh_worker,
            args=(provider_id, force),
            daemon=True,
        ).start()

    def _models_refresh_worker(
        self: "_ChatEngine", provider_id: str, force: bool
    ) -> None:
        """Фоновая загрузка списка моделей провайдера и отправка его в UI."""
        models, error = self._fetch_provider_models(provider_id, force=force)
        self._post(
            {
                "type": "api_models",
                "provider": provider_id,
                "models": models,
                "error": error,
            }
        )

    def _sync_provider_metadata(
        self: "_ChatEngine", provider_id: str, full: bool = False
    ) -> tuple[int, int, str]:
        """Синхронизирует метаданные моделей провайдера с внешними источниками.

        Возвращает (добавлено, обновлено, текст ошибки). Ошибка пуста, если
        данные получены и применены. Кэш UI-списка моделей обновляется, чтобы
        кнопка «Обновить» сразу показала актуальные цены и значки зрения.
        """
        prov = self._config.get("providers", {}).get(provider_id)
        if not isinstance(prov, dict):
            return 0, 0, self._t("provider.not_found")
        base_url = str(prov.get("base_url", "")).strip()
        if not base_url:
            return 0, 0, self._t("models.no_base_url")
        try:
            base_url = normalize_base_url(base_url)
        except ConfigError as exc:
            _LOGGER.warning("Некорректный base_url провайдера %s: %s", provider_id, exc)
            return 0, 0, self._t("models.fetch_failed")
        ctx = SourceContext(
            provider_id=provider_id,
            base_url=base_url,
            api_key=str(prov.get("api_key", "")).strip(),
            scheme=str(prov.get("scheme") or "openai"),
        )
        fetched = fetch_provider_metadata(ctx)
        if not fetched.models and fetched.error:
            known = fetched.error.startswith("models.")
            error_key = fetched.error if known else "models.fetch_failed"
            return 0, 0, self._t(error_key)
        # Зрение берём из каталога OpenRouter для моделей без собственного
        # признака; кэш каталога обновляется фоновым уточнением зрения.
        fetched.models = self._apply_openrouter_vision(
            fetched.models, provider_id=provider_id
        )
        models = prov.setdefault("models", {})
        added, updated = apply_models(models, fetched.models, full, allow_add=False)
        self._api_models_cache[provider_id] = (
            time.time(),
            self._ui_models_from_fetched(provider_id, fetched),
        )
        if added or updated:
            self._config = self._normalize_config(self._config)
            self._persist_config()
        return added, updated, ""

    def _ui_models_from_fetched(
        self: "_ChatEngine", provider_id: str, fetched: SourceResult
    ) -> list[dict[str, Any]]:
        """Собирает UI-список моделей из результатов синхронизации."""
        prov = self._config.get("providers", {}).get(provider_id)
        configured = prov.get("models", {}) if isinstance(prov, dict) else {}
        if not isinstance(configured, dict):
            configured = {}
        # Каталог OpenRouter — общий фолбэк зрения; берём его один раз до цикла.
        or_vision = self._openrouter_vision_map()
        result: list[dict[str, Any]] = []
        for model in fetched.models:
            mdef = configured.get(model.id)
            if not isinstance(mdef, dict):
                mdef = {}
            vision = model.vision if model.vision is not None else mdef.get("vision")
            if vision is None:
                vision = resolve_vision(provider_id, model.id, or_vision)
            price_in = model.price_in if model.price_in is not None else mdef.get("price_in")
            price_out = model.price_out if model.price_out is not None else mdef.get("price_out")
            result.append(
                {
                    "id": model.id,
                    "name": str(mdef.get("name") or model.name or model.id),
                    "vision": vision,
                    "price_in": price_in,
                    "price_out": price_out,
                }
            )
        result.sort(key=lambda item: str(item.get("name", "")).lower())
        return result

    def _handle_sync_provider(self: "_ChatEngine", message: dict) -> None:
        """Запускает фоновую синхронизацию метаданных провайдера по запросу UI."""
        provider_id = str(message.get("provider", ""))
        full = bool(message.get("full", False))
        if provider_id not in self._config.get("providers", {}):
            self._post(
                {"type": "toast", "text": self._t("provider.not_found"), "kind": "err"}
            )
            return
        if self._post_sink is None:
            return
        self._post({"type": "models_loading", "provider": provider_id, "loading": True})
        threading.Thread(
            target=self._provider_sync_worker,
            args=(provider_id, full),
            name="flowslice-provider-sync",
            daemon=True,
        ).start()

    def _provider_sync_worker(self: "_ChatEngine", provider_id: str, full: bool) -> None:
        """Фоновая синхронизация метаданных и отправка результата в UI."""
        try:
            added, updated, error = self._sync_provider_metadata(provider_id, full)
        except Exception as exc:  # pylint: disable=broad-except
            _LOGGER.exception("Ошибка синхронизации провайдера %s: %s", provider_id, exc)
            self._post(
                {
                    "type": "toast",
                    "text": self._t("sync.failed", err=str(exc)),
                    "kind": "err",
                }
            )
            return
        cached = self._api_models_cache.get(provider_id)
        models = cached[1] if cached else []
        self._post(
            {
                "type": "api_models",
                "provider": provider_id,
                "models": models,
                "error": error,
            }
        )
        if error:
            self._post(
                {"type": "toast", "text": self._t("sync.failed", err=error), "kind": "err"}
            )
        elif added == 0 and updated == 0:
            self._post({"type": "toast", "text": self._t("sync.nothing"), "kind": "ok"})
        else:
            self._post(
                {
                    "type": "toast",
                    "text": self._t("sync.done", added=str(added), updated=str(updated)),
                    "kind": "ok",
                }
            )
        if added or updated:
            self._send_state()

    def _start_provider_sync(
        self: "_ChatEngine", provider_id: str, full: bool = False
    ) -> None:
        """Запускает синхронизацию из фоновых мест (после ввода ключа, при старте)."""
        if self._post_sink is None:
            return
        self._handle_sync_provider({"provider": provider_id, "full": full})

    def _start_all_provider_sync(self: "_ChatEngine") -> None:
        """Запускает автосинхронизацию доступных провайдеров в одном потоке."""
        threading.Thread(
            target=self._all_provider_sync_worker,
            name="flowslice-provider-sync",
            daemon=True,
        ).start()

    def _all_provider_sync_worker(self: "_ChatEngine") -> None:
        """Автосинхронизация: провайдеры с ключом плюс публичные каталоги."""
        # Автообновление отключено пользователем: молча выходим. Явный ручной
        # синк по кнопке и загрузка списка моделей работают независимо.
        if self._config.get("auto_sync_providers") is False:
            return
        providers = self._config.get("providers", {})
        changed = False
        for provider_id, pdef in providers.items():
            if not isinstance(pdef, dict):
                continue
            has_key = bool(str(pdef.get("api_key", "")).strip())
            if not has_key and provider_id not in ("openrouter", "nordrouter"):
                continue
            try:
                added, updated, _error = self._sync_provider_metadata(provider_id, full=False)
            except Exception as exc:  # pylint: disable=broad-except
                _LOGGER.exception(
                    "Ошибка автосинхронизации провайдера %s: %s", provider_id, exc
                )
                continue
            if added or updated:
                changed = True
        if changed:
            self._send_state()

    def _refresh_provider_vision(self: "_ChatEngine", provider_id: str) -> None:
        """Фоновое уточнение зрения моделей провайдера и сохранение в конфиг."""
        if provider_id == "openrouter":
            mapping = self._openrouter_vision_map(refresh=True)
        else:
            mapping = self._provider_vision_map(provider_id)
        if not mapping:
            return
        prov = self._config.get("providers", {}).get(provider_id)
        if not isinstance(prov, dict):
            return
        changed = False
        for mid, mdef in prov.get("models", {}).items():
            if not isinstance(mdef, dict) or mdef.get("vision_source") == "manual":
                continue
            value = mapping.get(mid)
            if value is None:
                continue
            mdef["vision"] = bool(value)
            # Значение подтверждено провайдером.
            mdef["vision_source"] = "provider"
            changed = True
        if changed:
            self._persist_config()
            self._send_state()

    def _refresh_all_vision(self: "_ChatEngine") -> None:
        """Уточняет зрение для всех провайдеров с машинно-читаемым признаком."""
        providers = self._config.get("providers", {})
        for provider_id in _VISION_API_PROVIDERS:
            prov = providers.get(provider_id)
            if not isinstance(prov, dict):
                continue
            # OpenRouter отдаёт список публично; остальным нужен ключ.
            if provider_id != "openrouter" and not str(prov.get("api_key", "")).strip():
                continue
            self._refresh_provider_vision(provider_id)

    def _schedule_vision_refresh(self: "_ChatEngine") -> None:
        """Запускает фоновое уточнение зрения после смены ключей или моделей.

        Обычно зрение определяется один раз при старте UI, поэтому без этого
        вызова ключ, добавленный в текущей сессии, не влиял бы на значки до
        перезапуска плагина.
        """
        if self._post_sink is None:
            return
        threading.Thread(target=self._refresh_all_vision, daemon=True).start()

    def _resolve_vision_for(self: "_ChatEngine", provider_id: str, model_id: str) -> bool | None:
        """Определяет поддержку изображений по провайдеру и каталогу OpenRouter.

        Сначала используется собственная карта провайдера (если он отдаёт
        модальности), затем — общий фолбэк по публичному каталогу OpenRouter.
        Возвращает True/False либо None, если данных нигде нет.
        """
        if provider_id == "openrouter":
            return resolve_vision(provider_id, model_id, self._openrouter_vision_map())
        if provider_id in _VISION_API_PROVIDERS:
            value = self._provider_vision_map(provider_id).get(model_id)
            if value is not None:
                return value
        return resolve_vision(provider_id, model_id, self._openrouter_vision_map())

    def _model_supports_images(
        self: "_ChatEngine", refresh: bool = False
    ) -> bool | None:
        """Определяет поддержку изображений активной моделью.

        True/False — если признак известен, None — если данных нет
        (неизвестно — изображения разрешены, решение остаётся за провайдером).
        Сеть запрашивается только при refresh=True (фоновые потоки); фолбэк по
        каталогу OpenRouter берётся исключительно из свежего кэша.
        """
        provider_id, _base_url, _api_key, model, _scheme = self._active_api_credentials()
        if provider_id == "openrouter":
            return self._openrouter_vision_map(refresh=refresh).get(model)
        prov = self._config.get("providers", {}).get(provider_id)
        if not isinstance(prov, dict):
            return None
        mdef = prov.get("models", {}).get(model)
        if not isinstance(mdef, dict):
            return None
        vision = mdef.get("vision")
        if vision is None:
            vision = prov.get("vision")
        if vision is not None:
            return bool(vision)
        # Последняя попытка — свежий кэш каталога OpenRouter, без выхода в сеть.
        cached = self._cached_openrouter_vision()
        value = resolve_vision(provider_id, model, cached)
        if value is not None:
            return bool(value)
        if refresh:
            # Фоновый поток имеет право обновить каталог и повторить поиск.
            fetched = self._openrouter_vision_map(refresh=True)
            value = resolve_vision(provider_id, model, fetched)
            if value is not None:
                return bool(value)
        return None

    def _active_model_id(self: "_ChatEngine") -> str:
        """Возвращает идентификатор активной модели."""
        return str(self._config.get("active_model", ""))

    @staticmethod
    def _retry_backoff(attempt: int) -> float:
        """Возвращает паузу перед повтором по номеру попытки (0 — первая)."""
        index = min(attempt, len(_RETRY_BACKOFF) - 1)
        return _RETRY_BACKOFF[index]

    @staticmethod
    def _retry_after_seconds(exc: urllib.error.HTTPError) -> float:
        """Читает заголовок Retry-After (число секунд или HTTP-дату)."""
        try:
            value = exc.headers.get("Retry-After") if exc.headers else None
        except (AttributeError, TypeError):
            return 0.0
        if not value:
            return 0.0
        raw = str(value).strip()
        try:
            return max(0.0, float(raw))
        except (TypeError, ValueError):
            # Не число: возможно, провайдер прислал HTTP-дату — разбираем ниже.
            _LOGGER.debug("Retry-After не является числом: %r", raw)
        # Некоторые провайдеры присылают Retry-After как HTTP-дату.
        try:
            parsed = parsedate_to_datetime(raw)
        except (TypeError, ValueError, OverflowError):
            return 0.0
        if parsed is None:
            return 0.0
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return max(0.0, (parsed - datetime.now(timezone.utc)).total_seconds())

    def _notify_retry(
        self: "_ChatEngine", provider_id: str, attempt: int, wait: float, reason: str
    ) -> None:
        """Сообщает в лог и UI о повторной попытке запроса."""
        _LOGGER.warning(
            "Повтор запроса к %s (попытка %d из %d) через %.1f с: %s",
            provider_id,
            attempt,
            _RETRY_ATTEMPTS,
            wait,
            reason,
        )
        self._post(
            {
                "type": "toast",
                "text": self._t("gen.retry", sec=str(int(round(wait)))),
                "kind": "warn",
            }
        )

    def _wait_retry(self: "_ChatEngine", wait: float) -> None:
        """Пауза перед повтором с возможностью прервать ожидание кнопкой «Стоп»."""
        remaining = max(0.0, wait)
        if remaining <= 0:
            return
        # Ждём на событии: «Стоп» разбудит поток мгновенно, без опроса.
        self._cancel_event.wait(remaining)

    def _open_with_retry(
        self: "_ChatEngine", request: urllib.request.Request, provider_id: str
    ) -> Any:
        """Открывает соединение, повторяя временные сбои (сеть, 429, 5xx).

        Повтор выполняется только до чтения потока, поэтому частично
        полученный ответ никогда не дублируется. Ошибки аутентификации,
        неверного запроса и песочницы не повторяются.
        """
        attempt = 0
        while True:
            if not self._net_active():
                raise StreamError(self._t("gen.stopped"))
            try:
                return urllib.request.urlopen(request, timeout=TIMEOUT)
            except urllib.error.HTTPError as exc:
                if exc.code not in _RETRY_STATUSES or attempt >= _RETRY_ATTEMPTS - 1:
                    raise
                wait = self._retry_after_seconds(exc) or self._retry_backoff(attempt)
                reason = "HTTP " + str(exc.code)
                # Тело ответа при повторе не читаем — закрываем соединение.
                exc.close()
            except PermissionError:
                # Песочница Orca: повтор не поможет.
                raise
            except (urllib.error.URLError, TimeoutError, ConnectionError, OSError) as exc:
                if attempt >= _RETRY_ATTEMPTS - 1:
                    raise
                wait = self._retry_backoff(attempt)
                reason = str(exc)
            wait = min(wait, _RETRY_MAX_WAIT)
            attempt += 1
            self._notify_retry(provider_id, attempt, wait, reason)
            self._wait_retry(wait)

    def _call_api(
        self: "_ChatEngine", messages: list[dict[str, Any]], chat_id: int
    ) -> tuple[str, str]:
        """Выполняет запрос к API и возвращает (текст ответа, размышления)."""
        self._sync_config()
        self._last_usage = None
        provider_id, base_url, api_key, model, scheme = self._active_api_credentials()
        base_url = self._validated_base_url(base_url)
        if not api_key:
            raise ApiError(self._t("err.api_key_required"))
        cfg = self._config
        # Per-model настройки: None → наследуем глобальные значения.
        prov = cfg.get("providers", {}).get(provider_id)
        mdef = prov.get("models", {}).get(model) if isinstance(prov, dict) else {}
        temperature = mdef.get("temperature")
        if temperature is None:
            temperature = float(cfg.get("temperature", 0.7))
        max_tokens = mdef.get("max_tokens")
        if max_tokens is None:
            max_tokens = int(cfg.get("max_tokens", 4096))
        reasoning = mdef.get("reasoning")
        if reasoning is None:
            reasoning = bool(cfg.get("reasoning", False))
        if scheme == "anthropic":
            return self._call_anthropic(
                messages,
                chat_id,
                provider_id,
                base_url,
                api_key,
                model,
                temperature,
                max_tokens,
                reasoning,
            )
        url = base_url.rstrip("/") + "/chat/completions"
        payload: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "stream": True,
            "max_tokens": max_tokens,
        }
        # Reasoning-модели (GPT-5/o-серия) не принимают temperature.
        if not reasoning:
            payload["temperature"] = temperature
        # OpenRouter умеет присылать точный usage последним чанком потока.
        if provider_id == "openrouter":
            payload["stream_options"] = {"include_usage": True}
        if reasoning:
            if provider_id == "openrouter":
                payload["reasoning"] = {"effort": "high"}
            elif provider_id == "openai":
                payload["reasoning_effort"] = "high"
        request = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={**HTTP_HEADERS, "Authorization": "Bearer " + api_key},
            method="POST",
        )
        try:
            resp = self._open_with_retry(request, provider_id)
            with resp:
                return self._read_sse(resp, chat_id)
        except urllib.error.HTTPError as exc:
            body = self._http_error_detail(exc)
            raise ApiError(
                self._t("err.api", code=str(exc.code), body=body)
            ) from exc
        except urllib.error.URLError as exc:
            raise NetworkError(self._t("err.network", err=str(exc.reason))) from exc
        except TimeoutError as exc:
            raise NetworkError(self._t("err.timeout")) from exc
        except PermissionError as exc:
            raise NetworkError(self._t("err.sandbox")) from exc
        except OSError as exc:
            raise NetworkError(self._t("err.connection", err=str(exc))) from exc

    def _call_anthropic(
        self: "_ChatEngine",
        messages: list[dict[str, Any]],
        chat_id: int,
        provider_id: str,
        base_url: str,
        api_key: str,
        model: str,
        temperature: float,
        max_tokens: int,
        reasoning: bool,
    ) -> tuple[str, str]:
        """Выполняет запрос к нативному Messages API Anthropic.

        Возвращает пару (текст ответа, размышления).
        """
        system = ""
        body_messages = messages
        if messages and messages[0].get("role") == "system":
            system = str(messages[0].get("content", ""))
            body_messages = messages[1:]
        url = base_url.rstrip("/") + "/messages"
        payload: dict[str, Any] = {
            "model": model,
            "max_tokens": max_tokens,
            "system": system,
            "messages": body_messages,
            "stream": True,
        }
        if reasoning:
            budget = min(4096, max(1024, max_tokens // 2))
            payload["thinking"] = {"type": "enabled", "budget_tokens": budget}
        else:
            payload["temperature"] = temperature
        headers = {
            "Content-Type": "application/json",
            "User-Agent": "OrcaSlicer/2.5.0",
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
        }
        request = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers=headers,
            method="POST",
        )
        try:
            resp = self._open_with_retry(request, provider_id)
            with resp:
                return self._read_sse_anthropic(resp, chat_id)
        except urllib.error.HTTPError as exc:
            body = self._http_error_detail(exc)
            raise ApiError(
                self._t("err.api", code=str(exc.code), body=body)
            ) from exc
        except urllib.error.URLError as exc:
            raise NetworkError(self._t("err.network", err=str(exc.reason))) from exc
        except TimeoutError as exc:
            raise NetworkError(self._t("err.timeout")) from exc
        except PermissionError as exc:
            raise NetworkError(self._t("err.sandbox")) from exc
        except OSError as exc:
            raise NetworkError(self._t("err.connection", err=str(exc))) from exc

    def _call_api_blocking(
        self: "_ChatEngine", messages: list[dict[str, Any]], max_tokens: int = 2048
    ) -> str:
        """Выполняет нестриминговый запрос к API и возвращает текст ответа.

        Используется служебными задачами (сжатие истории), где потоковый
        вывод не нужен. Ошибки транслируются в ApiError/NetworkError.
        """
        self._sync_config()
        provider_id, base_url, api_key, model, scheme = self._active_api_credentials()
        base_url = self._validated_base_url(base_url)
        if not api_key:
            raise ApiError(self._t("err.api_key_required"))
        if scheme == "anthropic":
            return self._call_anthropic_blocking(
                messages, provider_id, base_url, api_key, model, max_tokens
            )
        url = base_url.rstrip("/") + "/chat/completions"
        payload: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "stream": False,
            "max_tokens": max_tokens,
            "temperature": 0.3,
        }
        request = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={**HTTP_HEADERS, "Authorization": "Bearer " + api_key},
            method="POST",
        )
        data = self._send_blocking_request(request, provider_id)
        choices = data.get("choices")
        if not isinstance(choices, list) or not choices:
            return ""
        message = choices[0].get("message") if isinstance(choices[0], dict) else None
        if not isinstance(message, dict):
            return ""
        return self._content_to_text(message.get("content"))

    def _call_anthropic_blocking(
        self: "_ChatEngine",
        messages: list[dict[str, Any]],
        provider_id: str,
        base_url: str,
        api_key: str,
        model: str,
        max_tokens: int,
    ) -> str:
        """Нестриминговый запрос к нативному Messages API Anthropic."""
        system = ""
        body_messages = messages
        if messages and messages[0].get("role") == "system":
            system = str(messages[0].get("content", ""))
            body_messages = messages[1:]
        url = base_url.rstrip("/") + "/messages"
        payload: dict[str, Any] = {
            "model": model,
            "max_tokens": max_tokens,
            "system": system,
            "messages": body_messages,
            "stream": False,
            "temperature": 0.3,
        }
        headers = {
            "Content-Type": "application/json",
            "User-Agent": "OrcaSlicer/2.5.0",
            "x-api-key": api_key,
            "anthropic-version": _ANTHROPIC_VERSION,
        }
        request = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers=headers,
            method="POST",
        )
        data = self._send_blocking_request(request, provider_id)
        content = data.get("content")
        if not isinstance(content, list):
            return ""
        parts = [
            str(block.get("text", ""))
            for block in content
            if isinstance(block, dict) and block.get("type") == "text"
        ]
        return "".join(parts)

    def _send_blocking_request(
        self: "_ChatEngine", request: urllib.request.Request, provider_id: str
    ) -> dict[str, Any]:
        """Отправляет запрос и разбирает JSON-ответ, транслируя ошибки."""
        try:
            resp = self._open_with_retry(request, provider_id)
            with resp:
                raw = resp.read().decode("utf-8", errors="replace")
        except urllib.error.HTTPError as exc:
            body = self._http_error_detail(exc)
            raise ApiError(
                self._t("err.api", code=str(exc.code), body=body)
            ) from exc
        except urllib.error.URLError as exc:
            raise NetworkError(self._t("err.network", err=str(exc.reason))) from exc
        except TimeoutError as exc:
            raise NetworkError(self._t("err.timeout")) from exc
        except PermissionError as exc:
            raise NetworkError(self._t("err.sandbox")) from exc
        except OSError as exc:
            raise NetworkError(self._t("err.connection", err=str(exc))) from exc
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ApiError(self._t("err.bad_json")) from exc
        if not isinstance(data, dict):
            raise ApiError(self._t("err.bad_json"))
        return data

    @staticmethod
    def _content_to_text(content: Any) -> str:
        """Приводит поле content ответа к строке (поддерживает список блоков)."""
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            return "".join(
                str(block.get("text", ""))
                for block in content
                if isinstance(block, dict) and block.get("text")
            )
        return ""

    def _read_sse(self: "_ChatEngine", resp: Any, chat_id: int) -> tuple[str, str]:
        """Читает SSE-поток ответа и отправляет инкрементальные куски в UI.

        Возвращает пару (текст ответа, накопленные размышления), чтобы движок
        мог сохранить reasoning_content отдельно от ответа.
        """
        acc = ""
        thought = ""
        sent = 0
        sent_thought = 0
        last_post = 0.0
        last_finish = ""
        for raw in resp:
            if not self._gen:
                break
            if len(acc) >= MAX_REPLY_CHARS or len(thought) >= MAX_THOUGHT_CHARS:
                _LOGGER.warning(
                    "Ответ модели превысил лимит (%s/%s символов) — чтение остановлено",
                    len(acc),
                    len(thought),
                )
                break
            line = raw.decode("utf-8", errors="replace").strip()
            if not line.startswith("data:"):
                continue
            data = line[5:].strip()
            if data == "[DONE]":
                break
            try:
                chunk = json.loads(data)
            except ValueError:
                continue
            if not isinstance(chunk, dict):
                continue
            # Провайдер может прислать ошибку прямо внутри потока (HTTP уже 200).
            error = chunk.get("error")
            if error:
                detail = error.get("message") if isinstance(error, dict) else error
                raise ApiError(str(detail) if detail else self._t("gen.empty_reply"))
            choices = chunk.get("choices")
            # Провайдер присылает usage отдельным чанком без choices.
            usage = chunk.get("usage")
            if isinstance(usage, dict):
                self._last_usage = usage
            if not isinstance(choices, list) or not choices or not isinstance(choices[0], dict):
                continue
            choice = choices[0]
            finish = choice.get("finish_reason")
            if finish:
                last_finish = str(finish)
            delta_obj = choice.get("delta")
            if not isinstance(delta_obj, dict):
                delta_obj = {}
            delta = delta_obj.get("content") or ""
            # OpenRouter отдаёт размышления в поле reasoning, DeepSeek — в reasoning_content.
            reasoning_delta = delta_obj.get("reasoning_content") or delta_obj.get("reasoning") or ""
            if reasoning_delta:
                thought += reasoning_delta
            if delta:
                acc += delta
            if not (reasoning_delta or delta):
                continue
            now = time.monotonic()
            if now - last_post < STREAM_THROTTLE:
                continue
            # Отправляем ВСЁ накопленное с прошлой отправки, а не только текущую
            # дельту: иначе UI теряет пропущенные куски и «досыпает» их в конце.
            if len(thought) > sent_thought:
                self._post(
                    {
                        "type": "thought_delta",
                        "chat_id": chat_id,
                        "text": thought[sent_thought:],
                    }
                )
                sent_thought = len(thought)
            if len(acc) > sent:
                self._post({"type": "delta", "chat_id": chat_id, "text": acc[sent:]})
                sent = len(acc)
            last_post = now
        if len(thought) > sent_thought:
            self._post(
                {
                    "type": "thought_delta",
                    "chat_id": chat_id,
                    "text": thought[sent_thought:],
                }
            )
        if len(acc) > sent:
            self._post({"type": "delta", "chat_id": chat_id, "text": acc[sent:]})
        if not acc:
            _LOGGER.warning(
                "Пустой ответ модели в потоке: finish_reason=%s, размышлений=%s символов",
                last_finish or "нет",
                len(thought),
            )
        return acc, thought

    def _read_sse_anthropic(self: "_ChatEngine", resp: Any, chat_id: int) -> tuple[str, str]:
        """Читает SSE-поток Messages API Anthropic и стримит текст в UI.

        Возвращает пару (текст ответа, размышления) с учётом thinking_delta.
        """
        acc = ""
        thought = ""
        sent = 0
        sent_thought = 0
        last_post = 0.0
        last_finish = ""
        for raw in resp:
            if not self._gen:
                break
            if len(acc) >= MAX_REPLY_CHARS or len(thought) >= MAX_THOUGHT_CHARS:
                _LOGGER.warning(
                    "Ответ модели превысил лимит (%s/%s символов) — чтение остановлено",
                    len(acc),
                    len(thought),
                )
                break
            line = raw.decode("utf-8", errors="replace").strip()
            if not line.startswith("data:"):
                continue
            data = line[5:].strip()
            if not data:
                continue
            try:
                event = json.loads(data)
            except ValueError:
                continue
            if not isinstance(event, dict):
                continue
            if event.get("type") == "error":
                error = event.get("error")
                detail = error.get("message") if isinstance(error, dict) else error
                raise ApiError(str(detail) if detail else self._t("gen.empty_reply"))
            if event.get("type") == "message_delta":
                stop = (event.get("delta") or {}).get("stop_reason")
                if stop:
                    last_finish = str(stop)
                continue
            if event.get("type") != "content_block_delta":
                continue
            delta = event.get("delta") or {}
            if delta.get("type") == "thinking_delta":
                text = delta.get("thinking") or ""
                is_thought = True
            else:
                text = delta.get("text") or ""
                is_thought = False
            if not text:
                continue
            if is_thought:
                thought += text
            else:
                acc += text
            now = time.monotonic()
            if now - last_post < STREAM_THROTTLE:
                continue
            # См. _read_sse: отправляем всё накопленное, чтобы не терять куски.
            if len(thought) > sent_thought:
                self._post(
                    {
                        "type": "thought_delta",
                        "chat_id": chat_id,
                        "text": thought[sent_thought:],
                    }
                )
                sent_thought = len(thought)
            if len(acc) > sent:
                self._post({"type": "delta", "chat_id": chat_id, "text": acc[sent:]})
                sent = len(acc)
            last_post = now
        if len(thought) > sent_thought:
            self._post(
                {
                    "type": "thought_delta",
                    "chat_id": chat_id,
                    "text": thought[sent_thought:],
                }
            )
        if len(acc) > sent:
            self._post({"type": "delta", "chat_id": chat_id, "text": acc[sent:]})
        if not acc:
            _LOGGER.warning(
                "Пустой ответ модели в потоке: finish_reason=%s, размышлений=%s символов",
                last_finish or "нет",
                len(thought),
            )
        return acc, thought

    def _test_key_worker(
        self: "_ChatEngine", key: str | None = None, provider_id: str | None = None
    ) -> None:
        """Проверяет API-ключ фоновым запросом к провайдеру.

        Если передан непустой ключ, он имеет приоритет над сохранённым.
        Если передан provider_id, проверяется именно он (а не активный
        провайдер) — иначе ключ из формы уходил бы на чужой эндпоинт.
        """
        self._sync_config()
        cfg = self._config
        if not provider_id or provider_id not in cfg.get("providers", {}):
            provider_id = str(cfg.get("active_provider", "deepseek"))
        active_provider = str(cfg.get("active_provider", ""))
        if provider_id == active_provider:
            model = str(cfg.get("active_model", ""))
        else:
            # Для неактивного провайдера берём его первую модель.
            prov = cfg.get("providers", {}).get(provider_id)
            models = prov.get("models", {}) if isinstance(prov, dict) else {}
            model = str(next(iter(models), "")) if isinstance(models, dict) else ""
        _, base_url, api_key, model, scheme = self._api_credentials_for(
            provider_id, model
        )
        if key and key.strip():
            api_key = key.strip()
        if not api_key:
            self._post(
                {"type": "key_test", "ok": False, "text": self._t("key.missing")}
            )
            return
        try:
            base_url = normalize_base_url(base_url)
        except ConfigError as exc:
            self._post(
                {
                    "type": "key_test",
                    "ok": False,
                    "text": self._t(str(exc)),
                }
            )
            return
        if scheme == "anthropic":
            url = base_url.rstrip("/") + "/messages"
            payload = {
                "model": model,
                "max_tokens": 1,
                "messages": [{"role": "user", "content": "ping"}],
                "stream": False,
            }
            headers = {
                "Content-Type": "application/json",
                "User-Agent": "OrcaSlicer/2.5.0",
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
            }
        else:
            url = base_url.rstrip("/") + "/chat/completions"
            payload = {
                "model": model,
                "messages": [{"role": "user", "content": "ping"}],
                "max_tokens": 1,
                "stream": False,
            }
            headers = {**HTTP_HEADERS, "Authorization": "Bearer " + api_key}
        request = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers=headers,
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=30) as resp:
                resp.read()
            self._post({"type": "key_test", "ok": True, "text": self._t("key.valid")})
        except urllib.error.HTTPError as exc:
            text = self._t("key.api_error", code=str(exc.code))
            detail = self._http_error_detail(exc)
            if detail:
                text = text + " " + detail
            self._post({"type": "key_test", "ok": False, "text": text})
        except OSError as exc:
            self._post(
                {
                    "type": "key_test",
                    "ok": False,
                    "text": self._t("key.network_error", err=str(exc)),
                }
            )

    @staticmethod
    def _http_error_detail(exc: urllib.error.HTTPError) -> str:
        """Извлекает понятный текст ошибки из тела HTTP-ответа для UI.

        Помимо самого сообщения добавляет провайдера и подсказку из блока
        ``metadata`` (OpenRouter), чтобы причина (например, перегрузка
        upstream-провайдера) была видна прямо в чате.
        """
        try:
            raw = exc.read().decode("utf-8", "replace")
        except OSError:
            return ""
        raw = raw.strip()
        if not raw:
            return ""
        text = raw[:300]
        try:
            data = json.loads(raw)
        except (ValueError, TypeError):
            return text
        if not isinstance(data, dict):
            return text
        error = data.get("error")
        parts: list[str] = []
        meta: dict[str, Any] = {}
        if isinstance(error, dict):
            if error.get("message"):
                parts.append(str(error["message"]))
            if isinstance(error.get("metadata"), dict):
                meta = error["metadata"]
        elif isinstance(error, str) and error:
            parts.append(error)
        elif data.get("detail"):
            parts.append(str(data["detail"]))
        if not parts:
            return text
        provider = meta.get("provider_name")
        if provider:
            parts.append("[" + str(provider) + "]")
        hint = meta.get("remedy_hint") or meta.get("raw")
        if hint:
            parts.append(str(hint))
        return " ".join(parts)[:300]
