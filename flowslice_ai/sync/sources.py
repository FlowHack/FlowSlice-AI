"""Реализации источников метаданных моделей.

Каждый источник знает, для каких провайдеров он применим (``matches``),
умеет получать список моделей, поддержку изображений и/или цены и
возвращает унифицированный :class:`~flowslice_ai.sync.base.SourceResult`.
"""
from __future__ import annotations

import urllib.parse
from typing import Any

from flowslice_ai.constants import HTTP_HEADERS
from flowslice_ai.sync import base
from flowslice_ai.sync.base import (
    FetchedModel,
    MetadataSource,
    SourceContext,
    SourceResult,
)

_ANTHROPIC_VERSION = "2023-06-01"
# Публичный каталог OpenRouter: список моделей, модальности и цены без ключа.
_OPENROUTER_CATALOG_URL = "https://openrouter.ai/api/v1/models"
# Подстроки в идентификаторе модели, по которым отсекаются заведомо
# нетекстовые модели (распознавание речи, эмбеддинги, генерация картинок).
_NON_TEXT_MODEL_HINTS = ("whisper", "tts", "embedding", "dall-e", "moderation", "image")


def vision_from_entry(entry: dict[str, Any]) -> bool | None:
    """Извлекает признак «модель принимает изображения и отвечает текстом».

    Поддерживаются форматы: ``architecture.input/output_modalities``
    (OpenRouter), ``input/output_modalities`` (xAI), ``capabilities.vision``
    (Mistral) и ``capabilities.image_input.supported`` (Anthropic).
    """
    arch = entry.get("architecture")
    inputs = arch.get("input_modalities") if isinstance(arch, dict) else None
    outputs = arch.get("output_modalities") if isinstance(arch, dict) else None
    if not isinstance(inputs, list):
        inputs = entry.get("input_modalities")
    if not isinstance(outputs, list):
        outputs = entry.get("output_modalities")
    if isinstance(inputs, list):
        if "image" not in inputs or "text" not in inputs:
            return False
        if isinstance(outputs, list) and "text" not in outputs:
            return False
        return True
    caps = entry.get("capabilities")
    if isinstance(caps, dict):
        image_input = caps.get("image_input")
        if isinstance(image_input, dict) and isinstance(image_input.get("supported"), bool):
            return image_input["supported"]
        vision = caps.get("vision")
        if isinstance(vision, bool):
            return vision
    return None


def is_text_model(model_id: str, entry: dict[str, Any]) -> bool:
    """Проверяет, умеет ли модель отвечать текстом.

    Отсекает распознавание речи, синтез, эмбеддинги и генерацию изображений.
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
    lowered = model_id.lower()
    return not any(hint in lowered for hint in _NON_TEXT_MODEL_HINTS)


def models_headers(provider_id: str, api_key: str) -> dict[str, str]:
    """Собирает заголовки запроса списка моделей с учётом схемы провайдера."""
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


def _payload_items(payload: Any) -> list[Any]:
    """Извлекает список записей из ответа ``data``/``models``."""
    if not isinstance(payload, dict):
        return []
    items = payload.get("data")
    if not isinstance(items, list):
        items = payload.get("models")
    return items if isinstance(items, list) else []


def _entry_id(entry: dict[str, Any], provider_id: str = "") -> str:
    """Возвращает идентификатор модели из записи ответа провайдера."""
    model_id = str(entry.get("id") or entry.get("name") or entry.get("model") or "").strip()
    if provider_id == "google" and model_id.startswith("models/"):
        model_id = model_id[len("models/") :]
    return model_id


def _entry_name(entry: dict[str, Any], model_id: str) -> str | None:
    """Возвращает человекочитаемое имя модели или None, если его нет.

    None означает «имя не сообщено»: для существующих моделей это защищает
    заданные вручную названия от затирания идентификатором.
    """
    display = str(
        entry.get("display_name") or entry.get("displayName") or entry.get("name") or ""
    ).strip()
    if not display or display == model_id or display.startswith("models/"):
        return None
    return display


def _to_float(value: Any, factor: float = 1.0) -> float | None:
    """Приводит значение к float, возвращая None для нечисловых данных."""
    try:
        return round(float(value) * factor, 4)
    except (TypeError, ValueError):
        return None


def _models_from_items(
    items: list[Any], provider_id: str
) -> list[FetchedModel]:
    """Разбирает записи ответа в список моделей с признаком зрения."""
    result: list[FetchedModel] = []
    seen: set[str] = set()
    for entry in items:
        if not isinstance(entry, dict):
            continue
        model_id = _entry_id(entry, provider_id)
        if not model_id or model_id in seen:
            continue
        if not is_text_model(model_id, entry):
            continue
        seen.add(model_id)
        result.append(
            FetchedModel(
                id=model_id,
                name=_entry_name(entry, model_id),
                vision=vision_from_entry(entry),
            )
        )
    return result


class OpenAICompatModelsSource(MetadataSource):
    """Список моделей OpenAI-совместимых провайдеров (кроме Google).

    Отдаёт ``/models`` обычным Bearer-запросом. Цены и зрение, если их нет
    в ответе, дополняются публичными источниками.
    """

    id = "openai_models"
    attributes = frozenset({"models", "vision"})
    priority = 10

    def matches(self, ctx: SourceContext) -> bool:
        """Применим к openai-совместимым провайдерам, кроме Google."""
        return ctx.scheme == "openai" and ctx.provider_id != "google"

    def _fetch(self, ctx: SourceContext) -> SourceResult:
        url = ctx.base_url.rstrip("/") + "/models"
        headers = models_headers(ctx.provider_id, ctx.api_key)
        payload = base.http_json(url, headers, ctx.timeout)
        return SourceResult(models=_models_from_items(_payload_items(payload), ctx.provider_id))


class AnthropicModelsSource(MetadataSource):
    """Нативный список моделей Anthropic Messages API."""

    id = "anthropic_models"
    attributes = frozenset({"models", "vision"})
    priority = 20

    def matches(self, ctx: SourceContext) -> bool:
        """Применим только к Anthropic."""
        return ctx.provider_id == "anthropic"

    def _fetch(self, ctx: SourceContext) -> SourceResult:
        url = ctx.base_url.rstrip("/") + "/models?limit=1000"
        headers = models_headers("anthropic", ctx.api_key)
        payload = base.http_json(url, headers, ctx.timeout)
        return SourceResult(models=_models_from_items(_payload_items(payload), "anthropic"))


class GoogleModelsSource(MetadataSource):
    """Нативный список моделей Google Generative Language API."""

    id = "google_models"
    attributes = frozenset({"models", "vision"})
    priority = 5

    def matches(self, ctx: SourceContext) -> bool:
        """Применим только к Google Gemini."""
        return ctx.provider_id == "google"

    def _fetch(self, ctx: SourceContext) -> SourceResult:
        base_url = ctx.base_url.rstrip("/")
        suffix = "/openai"
        # base_url указывает на OpenAI-совместимый префикс, а список моделей
        # живёт в нативном /v1beta/models.
        if base_url.endswith(suffix):
            base_url = base_url[: -len(suffix)]
        url = base_url + "/models"
        headers = models_headers("google", ctx.api_key)
        payload = base.http_json(url, headers, ctx.timeout)
        return SourceResult(models=_models_from_items(_payload_items(payload), "google"))


class XaiModelsSource(MetadataSource):
    """Список языковых моделей xAI (``/language-models``)."""

    id = "xai_models"
    attributes = frozenset({"models", "vision"})
    priority = 5

    def matches(self, ctx: SourceContext) -> bool:
        """Применим только к xAI."""
        return ctx.provider_id == "xai"

    def _fetch(self, ctx: SourceContext) -> SourceResult:
        url = ctx.base_url.rstrip("/") + "/language-models"
        headers = models_headers(ctx.provider_id, ctx.api_key)
        payload = base.http_json(url, headers, ctx.timeout)
        return SourceResult(models=_models_from_items(_payload_items(payload), "xai"))


class OpenRouterCatalogSource(MetadataSource):
    """Публичный каталог OpenRouter: модели, зрение и цены без ключа."""

    id = "openrouter_catalog"
    attributes = frozenset({"models", "vision", "pricing"})
    priority = 30
    requires_key = False

    def matches(self, ctx: SourceContext) -> bool:
        """Применим только к OpenRouter."""
        return ctx.provider_id == "openrouter"

    def _fetch(self, ctx: SourceContext) -> SourceResult:
        payload = base.http_json(_OPENROUTER_CATALOG_URL, dict(HTTP_HEADERS), ctx.timeout)
        items = _payload_items(payload)
        models = _models_from_items(items, "openrouter")
        prices: dict[str, tuple[float, float]] = {}
        for entry in items:
            if not isinstance(entry, dict):
                continue
            model_id = _entry_id(entry, "openrouter")
            pricing = entry.get("pricing")
            if not model_id or not isinstance(pricing, dict):
                continue
            price_in = _to_float(pricing.get("prompt"), 1_000_000)
            price_out = _to_float(pricing.get("completion"), 1_000_000)
            if price_in is not None and price_out is not None:
                prices[model_id] = (price_in, price_out)
        vision = {model.id: model.vision for model in models if model.vision is not None}
        return SourceResult(models=models, vision=vision, prices=prices)


class NordRouterPricingSource(MetadataSource):
    """Публичный прайс-лист NordRouter (``/auth/pricing``)."""

    id = "nordrouter_pricing"
    attributes = frozenset({"pricing"})
    priority = 40
    requires_key = False

    def matches(self, ctx: SourceContext) -> bool:
        """Применим только к NordRouter."""
        return ctx.provider_id == "nordrouter"

    def _fetch(self, ctx: SourceContext) -> SourceResult:
        parsed = urllib.parse.urlsplit(ctx.base_url)
        if not parsed.scheme or not parsed.netloc:
            return SourceResult(error="models.no_base_url")
        # Цены живут на корне хоста, а base_url заканчивается на /v1.
        url = parsed.scheme + "://" + parsed.netloc + "/auth/pricing"
        payload = base.http_json(url, dict(HTTP_HEADERS), ctx.timeout)
        prices: dict[str, tuple[float, float]] = {}
        for entry in _payload_items(payload):
            if not isinstance(entry, dict):
                continue
            model_id = str(entry.get("id") or "").strip()
            price_in = _to_float(entry.get("in_usd"))
            price_out = _to_float(entry.get("out_usd"))
            if model_id and price_in is not None and price_out is not None:
                prices[model_id] = (price_in, price_out)
        return SourceResult(prices=prices)


class VisionCrossMapSource(MetadataSource):
    """Определяет зрение по совпадению id с публичным каталогом OpenRouter.

    Нужен провайдерам-агрегаторам (например, NordRouter), которые не отдают
    модальности моделей в собственном API. Список провайдеров расширяется
    параметром ``provider_ids``.
    """

    id = "vision_cross_map"
    attributes = frozenset({"vision"})
    priority = 5
    requires_key = False

    def __init__(self, provider_ids: frozenset[str] | None = None) -> None:
        self.provider_ids = provider_ids or frozenset({"nordrouter"})

    def matches(self, ctx: SourceContext) -> bool:
        """Применим к провайдерам из списка ``provider_ids``."""
        return ctx.provider_id in self.provider_ids

    def _fetch(self, ctx: SourceContext) -> SourceResult:
        payload = base.http_json(_OPENROUTER_CATALOG_URL, dict(HTTP_HEADERS), ctx.timeout)
        vision: dict[str, bool] = {}
        for entry in _payload_items(payload):
            if not isinstance(entry, dict):
                continue
            model_id = _entry_id(entry, "openrouter")
            value = vision_from_entry(entry)
            if model_id and value is not None:
                vision[model_id] = value
        return SourceResult(vision=vision)


# Порядок в кортеже не важен: ``sources_for`` сортирует по ``priority``.
SOURCES: tuple[MetadataSource, ...] = (
    VisionCrossMapSource(),
    GoogleModelsSource(),
    XaiModelsSource(),
    OpenAICompatModelsSource(),
    AnthropicModelsSource(),
    OpenRouterCatalogSource(),
    NordRouterPricingSource(),
)


def sources_for(ctx: SourceContext) -> list[MetadataSource]:
    """Возвращает применимые к провайдеру источники по возрастанию приоритета."""
    return sorted(
        (source for source in SOURCES if source.matches(ctx)),
        key=lambda source: source.priority,
    )
