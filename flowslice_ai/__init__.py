"""FlowSlice AI — пакет плагина OrcaSlicer: ИИ-ассистент инженера 3D-печати."""
import orca

from flowslice_ai.orca_compat import _PAGES_BASE, _SCRIPT_BASE
from flowslice_ai.plugin import FlowSliceTab, FlowSliceWindow
from flowslice_ai.version import __version__

__all__ = ["__version__", "FlowSlicePlugin"]


@orca.plugin
class FlowSlicePlugin(orca.base):
    """Пакет плагина FlowSlice AI: регистрация capability."""

    def register_capabilities(self) -> None:
        """Регистрирует доступную capability в порядке приоритета."""
        if _PAGES_BASE is not None:
            orca.register_capability(FlowSliceTab)
        elif _SCRIPT_BASE is not None:
            orca.register_capability(FlowSliceWindow)
