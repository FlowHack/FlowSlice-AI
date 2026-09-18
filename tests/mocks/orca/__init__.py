"""Мок-модуль orca для запуска тестов вне Orca Slicer."""
from __future__ import annotations


class _Base:
    """Заглушка orca.base."""


class ExecutionResult:
    """Заглушка orca.ExecutionResult."""

    @staticmethod
    def success(message: str = "") -> tuple[str, str]:
        """Возвращает успешный результат."""
        return ("success", message)


def plugin(cls):
    """Заглушка декоратора orca.plugin."""
    return cls


def register_capability(cls):
    """Заглушка orca.register_capability."""
    return cls


class _Model:
    """Заглушка модели со стола: без объектов."""

    def objects(self) -> list:
        """Пустой список объектов."""
        return []


class _Host:
    """Заглушка orca.host."""

    @staticmethod
    def model() -> _Model:
        """Возвращает пустую модель."""
        return _Model()

    @staticmethod
    def preset_bundle():
        """Возвращает None (пресеты недоступны в тестах)."""
        return None

    class ui:
        """Заглушка orca.host.ui."""

        @staticmethod
        def create_window(**_kwargs):
            """Возвращает None."""
            return None


base = _Base
host = _Host()