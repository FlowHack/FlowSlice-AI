"""Движок плагина FlowSlice AI: конфигурация, чаты, генерация, контекст слайсера."""
# pylint: disable=too-few-public-methods

from flowslice_ai.engine.core import CoreMixin
from flowslice_ai.engine.handlers import HandlersMixin
from flowslice_ai.engine.providers import ProvidersMixin
from flowslice_ai.engine.generation import GenerationMixin
from flowslice_ai.engine.api_client import ApiClientMixin
from flowslice_ai.engine.slicer_context import SlicerContextMixin
from flowslice_ai.engine.commands import CommandsMixin


class _ChatEngine(
    CoreMixin,
    HandlersMixin,
    ProvidersMixin,
    GenerationMixin,
    ApiClientMixin,
    SlicerContextMixin,
    CommandsMixin,
):
    """Ядро плагина: единый класс, собранный из миксинов по зонам ответственности."""
