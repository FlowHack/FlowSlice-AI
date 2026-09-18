"""Smoke-тесты capability-классов плагина (flowslice_ai/plugin.py)."""
from __future__ import annotations

import pathlib

import pytest

from flowslice_ai.config import DEFAULT_CONFIG
from flowslice_ai.plugin import FlowSliceTab, FlowSliceWindow
from flowslice_ai.ui import config_page


@pytest.fixture
def tab(tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch) -> FlowSliceTab:
    """Создаёт вкладку с изолированным хранилищем чатов и иконки."""
    monkeypatch.setattr("flowslice_ai.engine.core.CHATS_FILE", tmp_path / "chats.json")
    monkeypatch.setattr("flowslice_ai.plugin.ICON_FILE", tmp_path / "tab_icon.svg")
    return FlowSliceTab()


def test_tab_metadata(tab: FlowSliceTab) -> None:
    """Вкладка отдаёт имя, HTML-интерфейс и страницу настроек."""
    assert tab.get_name() == "FlowSlice AI"
    ui = tab.get_ui()
    assert "<!DOCTYPE html>" in ui
    assert "</html>" in ui
    page = tab.get_config_ui()
    assert "FlowSlice AI" in page
    assert "<!--" not in page


def test_tab_default_config_is_copy(tab: FlowSliceTab) -> None:
    """get_default_config() возвращает копию, а не сам DEFAULT_CONFIG."""
    result = tab.get_default_config()
    assert result == DEFAULT_CONFIG
    assert result is not DEFAULT_CONFIG


def test_tab_icon_written(tab: FlowSliceTab, tmp_path: pathlib.Path) -> None:
    """get_icon() записывает SVG и возвращает путь к нему."""
    path = tab.get_icon()
    assert path
    assert pathlib.Path(path).is_file()
    assert "<svg" in (tmp_path / "tab_icon.svg").read_text(encoding="utf-8")


def test_tab_on_message_does_not_crash(tab: FlowSliceTab) -> None:
    """on_message() с запросом состояния не падает без открытого окна."""
    tab.on_message({"type": "get_state"})


def test_window_execute_already_open(tab: FlowSliceTab) -> None:
    """Повторный запуск сообщает, что окно уже открыто."""
    window = FlowSliceWindow()

    class _FakeWin:
        """Открытое окно-заглушка."""

        @staticmethod
        def is_open() -> bool:
            """Окно считается открытым."""
            return True

    window._win = _FakeWin()
    result = window.execute()
    assert result[0] == "success"
    assert result[1]


def test_window_on_close_resets(tab: FlowSliceTab) -> None:
    """_on_close() сбрасывает ссылку на окно."""
    window = FlowSliceWindow()
    window._win = object()
    window._on_close()
    assert window._win is None


def test_config_page_localized() -> None:
    """Страница настроек локализуется, неизвестный язык падает в английский."""
    assert "Настройки" in config_page("ru")
    assert "Podešavanja" in config_page("sr")
    assert "Settings" in config_page("en")
    assert config_page("xx") == config_page("en")
