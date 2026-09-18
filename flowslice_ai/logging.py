"""Настройка логгера плагина FlowSlice AI."""
import logging
import sys

_LOGGER = logging.getLogger("flowslice_ai")
if not _LOGGER.handlers:
    _STREAM_HANDLER = logging.StreamHandler(sys.stderr)
    _STREAM_HANDLER.setFormatter(
        logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
    )
    _LOGGER.addHandler(_STREAM_HANDLER)
    _LOGGER.setLevel(logging.INFO)
