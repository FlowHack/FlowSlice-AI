"""Smoke-тесты импорта пакета FlowSlice AI и сборки HTML-страниц."""
from __future__ import annotations

import re

import flowslice_ai
from flowslice_ai.ui import CONFIG_PAGE, HTML_PAGE
from flowslice_ai.version import __version__


def test_version() -> None:
    """Версия пакета — непустая строка вида X.Y.Z."""
    assert isinstance(__version__, str)
    assert __version__
    assert re.fullmatch(r"\d+\.\d+\.\d+", __version__)


def test_html_page_assembled() -> None:
    """HTML_PAGE собран: плейсхолдеры заменены, CONFIG_PAGE содержит заголовок."""
    assert "<!DOCTYPE html>" in HTML_PAGE
    assert "</html>" in HTML_PAGE
    assert "<!--STYLE-->" not in HTML_PAGE
    assert "<!--SCRIPT-->" not in HTML_PAGE
    assert "<h1>FlowSlice AI</h1>" in CONFIG_PAGE


def test_plugin_registered() -> None:
    """Пакет экспортирует точку входа плагина."""
    assert hasattr(flowslice_ai, "FlowSlicePlugin")
