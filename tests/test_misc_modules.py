"""Тесты служебных модулей: ошибки, логирование, иконка и сборка HTML."""
from __future__ import annotations

import logging
import xml.etree.ElementTree as ET

from flowslice_ai import assets
from flowslice_ai.errors import (
    ApiError,
    ConfigError,
    ContextError,
    FlowSliceError,
    NetworkError,
    StreamError,
)
from flowslice_ai.logging import _LOGGER
from flowslice_ai.ui import HTML_PAGE


def test_error_hierarchy() -> None:
    """Все доменные ошибки наследуются от FlowSliceError и от Exception."""
    for error_cls in (ConfigError, ApiError, NetworkError, StreamError, ContextError):
        assert issubclass(error_cls, FlowSliceError)
    assert issubclass(FlowSliceError, Exception)


def test_error_carries_message() -> None:
    """Сообщение ошибки сохраняется без искажений."""
    error = ApiError("провайдер вернул 500")
    assert str(error) == "провайдер вернул 500"


def test_logger_configured() -> None:
    """Логгер модуля пишет в stderr с уровнем INFO и без propagation."""
    assert _LOGGER.name == "flowslice_ai"
    assert _LOGGER.level == logging.INFO
    assert _LOGGER.propagate is False
    assert any(isinstance(handler, logging.StreamHandler) for handler in _LOGGER.handlers)


def test_tab_icon_is_valid_svg_with_accent() -> None:
    """Иконка вкладки — валидный SVG с фирменным акцентным цветом."""
    root = ET.fromstring(assets._TAB_ICON_SVG)
    assert root.tag.endswith("svg")
    assert assets._TAB_ICON_SVG.count("#d9534f") >= 1
    assert "#fff" not in assets._TAB_ICON_SVG


def test_html_page_has_inlined_assets() -> None:
    """HTML_PAGE содержит подставленные стили и скрипт без плейсхолдеров."""
    assert "<!--STYLE-->" not in HTML_PAGE
    assert "<!--SCRIPT-->" not in HTML_PAGE
    assert "<style" in HTML_PAGE
    assert "<script" in HTML_PAGE
    # Плейсхолдер подставляется ровно один раз (несколько вхождений сломали бы HTML).
    assert HTML_PAGE.count("--orca-accent") >= 1
