"""Классы ошибок плагина FlowSlice AI."""


class FlowSliceError(Exception):
    """Базовая ошибка плагина FlowSlice AI."""


class ConfigError(FlowSliceError):
    """Ошибка чтения, нормализации или сохранения конфигурации."""


class ApiError(FlowSliceError):
    """Ошибка ответа внешнего ИИ-провайдера."""


class NetworkError(FlowSliceError):
    """Ошибка сетевого взаимодействия."""


class StreamError(FlowSliceError):
    """Ошибка потоковой передачи ответа модели."""


class ContextError(FlowSliceError):
    """Ошибка сбора контекста слайсера."""
