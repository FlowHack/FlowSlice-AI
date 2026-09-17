"""Стаб orca.script для локального QA."""

from . import ExecutionResult, PythonPluginBase


class ScriptPluginCapabilityBase(PythonPluginBase):
    """База script-капабилити (запуск через Plugins -> Run)."""

    def get_name(self) -> str:
        """Имя capability."""
        return ""

    def execute(self) -> ExecutionResult:
        """Точка входа script-плагина."""
        return ExecutionResult.success()