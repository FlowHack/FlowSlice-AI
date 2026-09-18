"""FlowSlice AI — пакет плагина OrcaSlicer: ИИ-ассистент инженера 3D-печати."""
try:
    import orca
except ImportError:  # pragma: no cover - пакет импортируется вне OrcaSlicer
    orca = None

from flowslice_ai import plugin as _plugin
from flowslice_ai.orca_compat import _PAGES_BASE, _SCRIPT_BASE
from flowslice_ai.version import __version__

__all__ = ["__version__", "FlowSlicePlugin"]


if orca is None:

    class FlowSlicePlugin:  # pylint: disable=too-few-public-methods  # pyright: ignore[reportRedeclaration]
        """Заглушка плагина: позволяет импортировать пакет вне OrcaSlicer."""

        def register_capabilities(self) -> None:
            """Ничего не регистрирует вне OrcaSlicer."""

else:

    @orca.plugin
    class FlowSlicePlugin(orca.base):  # pyright: ignore[reportRedeclaration]
        """Пакет плагина FlowSlice AI: регистрация capability."""

        def register_capabilities(self) -> None:
            """Регистрирует доступную capability в порядке приоритета."""
            host = orca
            if host is None:
                return
            if _PAGES_BASE is not None:
                tab = getattr(_plugin, "FlowSliceTab", None)
                if tab is not None:
                    host.register_capability(tab)
            elif _SCRIPT_BASE is not None:
                window = getattr(_plugin, "FlowSliceWindow", None)
                if window is not None:
                    host.register_capability(window)
