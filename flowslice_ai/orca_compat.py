"""Совместимость с API Orca Slicer: динамический импорт capability-баз."""
import importlib

try:
    import numpy as _np
    _HAS_NUMPY = _np is not None
except ImportError:
    _np = None
    _HAS_NUMPY = False

try:
    _PAGES_BASE = getattr(
        importlib.import_module("orca.pages"), "PagesPluginCapabilityBase", None
    )
except (ImportError, AttributeError):
    _PAGES_BASE = None

try:
    _SCRIPT_BASE = getattr(
        importlib.import_module("orca.script"), "ScriptPluginCapabilityBase", None
    )
except (ImportError, AttributeError):
    _SCRIPT_BASE = None
