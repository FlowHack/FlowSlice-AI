"""Оркестрация опроса источников и слияние их результатов.

``fetch_provider_metadata`` последовательно обходит применимые источники,
берёт список моделей у первого подходящего, а зрение и цены — у всех,
после чего обогащает модели этими сведениями.
"""
from __future__ import annotations

from dataclasses import replace

from flowslice_ai.logging import _LOGGER
from flowslice_ai.sync.base import FetchedModel, SourceContext, SourceResult
from flowslice_ai.sync.sources import is_text_model, sources_for


def _synthesize_models(
    vision: dict[str, bool], prices: dict[str, tuple[float, float]]
) -> list[FetchedModel]:
    """Строит модели из карты цен, если список моделей не получен.

    Опираемся только на цены: источник цен знает именно каталог своего
    провайдера. Карта зрения может прийти из внешнего каталога-агрегатора
    (кросс-маппинг OpenRouter) и содержит чужие модели — их в список
    провайдера подмешивать нельзя. Зрение подставляется по совпадению id.
    """
    models: list[FetchedModel] = []
    for model_id in prices:
        if not is_text_model(model_id, {}):
            continue
        price = prices[model_id]
        models.append(
            FetchedModel(
                id=model_id,
                vision=vision.get(model_id),
                price_in=price[0],
                price_out=price[1],
            )
        )
    return models


def _merge_metadata(
    models: list[FetchedModel],
    vision: dict[str, bool],
    prices: dict[str, tuple[float, float]],
) -> list[FetchedModel]:
    """Обогащает модели зрением и ценами из карт всех источников."""
    merged: list[FetchedModel] = []
    for model in models:
        value = model.vision if model.vision is not None else vision.get(model.id)
        price = prices.get(model.id)
        price_in = model.price_in
        if price_in is None and price is not None:
            price_in = price[0]
        price_out = model.price_out
        if price_out is None and price is not None:
            price_out = price[1]
        merged.append(
            replace(model, vision=value, price_in=price_in, price_out=price_out)
        )
    return merged


def fetch_provider_metadata(ctx: SourceContext) -> SourceResult:
    """Собирает метаданные моделей провайдера из всех применимых источников.

    Список моделей берётся у первого источника с атрибутом ``models``, а
    зрение и цены домешиваются от всех остальных. Без ключа опрашиваются
    только публичные источники; если таких нет, возвращается ошибка
    ``models.need_key``.
    """
    sources = sources_for(ctx)
    result = SourceResult()
    errors: list[str] = []
    if not ctx.api_key:
        public = [source for source in sources if not source.requires_key]
        if not public:
            return SourceResult(error="models.need_key")
    models_taken = False
    for source in sources:
        if source.requires_key and not ctx.api_key:
            continue
        source_result = source.fetch(ctx)
        if source_result.error:
            errors.append(source_result.error)
            _LOGGER.warning(
                "Источник %s не дал метаданных для %s: %s",
                source.id,
                ctx.provider_id,
                source_result.error,
            )
        if "models" in source.attributes and source_result.models and not models_taken:
            result.models = list(source_result.models)
            models_taken = True
        result.vision.update(source_result.vision)
        result.prices.update(source_result.prices)
    if not result.models:
        result.models = _synthesize_models(result.vision, result.prices)
    result.models = _merge_metadata(result.models, result.vision, result.prices)
    if not result.models and not result.vision and not result.prices:
        result.error = errors[0] if errors else "models.fetch_failed"
    return result
