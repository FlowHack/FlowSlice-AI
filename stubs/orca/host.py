"""Стаб orca.host для локального QA."""

from typing import Any


class ui:
    """Стаб orca.host.ui."""

    @staticmethod
    def create_window(
        html: str = "",
        title: str = "",
        on_message: Any = None,
        on_close: Any = None,
    ) -> Any:
        """Создание окна."""
        return None


class host:
    """Стаб orca.host."""

    @staticmethod
    def model() -> Any:
        """Снимок модели на столе."""
        return None

    @staticmethod
    def preset_bundle() -> Any:
        """Снимок пресетов."""
        return None

    @staticmethod
    def plater() -> Any:
        """Снимок платера."""
        return None