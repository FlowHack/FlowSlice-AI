"""Capability-классы плагина FlowSlice AI: вкладка и окно."""
# pylint: disable=too-many-lines,protected-access

from typing import Any

import orca

from flowslice_ai.assets import _TAB_ICON_SVG
from flowslice_ai.config import DEFAULT_CONFIG
from flowslice_ai.engine import _ChatEngine
from flowslice_ai.logging import _LOGGER
from flowslice_ai.orca_compat import _PAGES_BASE, _SCRIPT_BASE
from flowslice_ai.paths import ICON_FILE
from flowslice_ai.ui import CONFIG_PAGE, HTML_PAGE


class _ConfigMixin:
    """Общие методы конфигурации для вкладки и окна плагина."""

    def get_default_config(self) -> dict:
        """Возвращает дефолтную конфигурацию плагина."""
        return DEFAULT_CONFIG.copy()

    def get_config(self) -> str:
        """Возвращает конфигурацию базового capability либо пустой JSON."""
        getter: Any = getattr(super(), "get_config", None)
        if getter is not None:
            return str(getter())
        return "{}"

    def save_config(self, config: str) -> bool:
        """Сохраняет конфигурацию через базовый capability."""
        setter: Any = getattr(super(), "save_config", None)
        if setter is not None:
            return bool(setter(config))
        return False

    def has_config_ui(self) -> bool:
        """Сообщает хосту о наличии кастомной страницы настроек."""
        return True

    def get_config_ui(self) -> str:
        """Возвращает HTML-страницу настроек."""
        return CONFIG_PAGE

    def _ensure_engine(self) -> _ChatEngine:
        """Лениво создаёт общий движок плагина и подключает sink."""
        engine = getattr(self, "_engine", None)
        if engine is None:
            engine = _ChatEngine(self)
            engine.set_post_sink(self._make_post_sink())
            self._engine = engine
        return engine

    def _t(self, key: str, **params: str) -> str:
        """Локализует строку через движок (язык берётся из конфигурации)."""
        return self._ensure_engine()._t(key, **params)

    def _make_post_sink(self) -> Any:
        """Возвращает callable для доставки payload в UI."""
        if _PAGES_BASE is not None and isinstance(self, _PAGES_BASE):
            return getattr(self, "post_message", self._window_post)
        return self._window_post

    def _window_post(self, payload: dict) -> None:
        """Отправляет payload в открытое окно ассистента."""
        win = getattr(self, "_win", None)
        if win is not None and win.is_open():
            win.post(payload)


if _PAGES_BASE is not None:

    class FlowSliceTab(_ConfigMixin, _PAGES_BASE):
        """Вкладка FlowSlice AI в главном окне OrcaSlicer."""

        def get_name(self) -> str:
            """Имя вкладки."""
            return "FlowSlice AI"

        def get_type(self) -> Any:
            """Тип capability — страница (вкладка) интерфейса OrcaSlicer.

            Явное значение нужно потому, что встроенная база страниц в некоторых
            сборках OrcaSlicer возвращает ``Unknown``, из-за чего в диалоге
            плагинов в колонке «Types» отображается ``unknown`` вместо ``Pages``.
            """
            for name in ("Pages", "Page"):
                value: Any = getattr(orca.PluginType, name, None)
                if value is not None:
                    return value
            getter: Any = getattr(super(), "get_type", None)
            if getter is not None:
                return getter()
            return orca.PluginType.Unknown

        def get_ui(self) -> str:
            """HTML-содержимое вкладки."""
            self._ensure_engine()
            return HTML_PAGE

        def get_icon(self) -> str:
            """Записывает иконку вкладки и возвращает путь к файлу."""
            try:
                ICON_FILE.write_text(_TAB_ICON_SVG, encoding="utf-8")
                return str(ICON_FILE)
            except OSError as exc:
                _LOGGER.error("Не удалось записать иконку вкладки: %s", exc)
                return ""

        def on_message(self, message: dict) -> None:
            """Обрабатывает сообщение из пользовательского интерфейса вкладки."""
            self._ensure_engine().handle_message(message)


if _SCRIPT_BASE is not None:

    class FlowSliceWindow(_ConfigMixin, _SCRIPT_BASE):
        """Оконная (script) capability FlowSlice AI."""

        _win: Any = None

        def get_name(self) -> str:
            """Имя capability."""
            return "FlowSlice AI"

        def execute(self) -> orca.ExecutionResult:
            """Открывает окно ассистента либо сообщает, что оно уже открыто."""
            self._ensure_engine()
            win = getattr(self, "_win", None)
            if win is not None and win.is_open():
                return orca.ExecutionResult.success(self._t("win.already_open"))
            self._win = orca.host.ui.create_window(
                html=HTML_PAGE,
                title="FlowSlice AI",
                on_message=self._on_message,
                on_close=self._on_close,
            )
            return orca.ExecutionResult.success(self._t("win.opened"))

        def _on_message(self, message: dict) -> None:
            """Обрабатывает сообщение из окна ассистента."""
            self._ensure_engine().handle_message(message)

        def _on_close(self, *_args: Any) -> None:
            """Сбрасывает ссылку на закрытое окно."""
            self._win = None
