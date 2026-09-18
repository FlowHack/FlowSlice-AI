"""Slash-команды и статистика использования движка FlowSlice AI.

Миксин CommandsMixin обрабатывает служебные команды (/context, /clear,
/model, /printer, /stats, /help, /reset) с двухшаговым подтверждением
деструктивных операций и ведёт статистику использования.
"""
# pyright (миксины _ChatEngine): reportGeneralTypeIssues отключён только здесь.
# pyright: reportGeneralTypeIssues=false
# pylint: disable=too-many-lines,too-many-branches,too-many-statements
# pylint: disable=too-many-public-methods,too-few-public-methods

import datetime
import json
import time
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from flowslice_ai.engine import _ChatEngine

from flowslice_ai.config import COMMANDS, DEFAULT_CONFIG
from flowslice_ai.constants import MAX_CONTEXT_CHARS


class CommandsMixin:
    """Slash-команды, подтверждения и статистика использования."""

    def _handle_command(self: "_ChatEngine", text: str) -> bool:
        """Обрабатывает служебные команды, начинающиеся со слэша."""
        stripped = text.strip()
        if not stripped:
            return False
        cmd = stripped.split()[0].lower()
        if cmd == "/context":
            self._cmd_context()
        elif cmd == "/clear":
            self._cmd_clear()
        elif cmd == "/model":
            self._cmd_model()
        elif cmd == "/printer":
            self._cmd_printer()
        elif cmd == "/stats":
            self._cmd_stats()
        elif cmd == "/help":
            self._cmd_help()
        elif cmd == "/reset":
            self._cmd_reset(stripped)
        else:
            return False
        return True

    def _cmd_help(self: "_ChatEngine") -> None:
        """Выводит список доступных команд."""
        lines = [self._t("cmd.help.title")]
        for cmd, _desc in COMMANDS:
            lines.append(cmd + " — " + self._t("cmd." + cmd.lstrip("/") + ".desc"))
        self._append_system("\n".join(lines))

    def _cmd_model(self: "_ChatEngine") -> None:
        """Формирует отчёт о модели на столе."""
        data = self._collect_model_data()
        objects = data.get("objects", [])
        if not objects:
            self._append_system(self._t("cmd.model.empty"))
            return
        lines = [self._t("cmd.model.title")]
        for obj in objects:
            lines.append("• " + str(obj.get("name", self._t("cmd.model.unnamed"))))
            lines.append(self._t("cmd.model.bbox", v=str(obj.get("local_bbox_mm", "—"))))
            lines.append(self._t("cmd.model.volume", v=str(obj.get("volume_cm3", "—"))))
            lines.append(
                self._t("cmd.model.surface", v=str(obj.get("surface_area_cm2", "—")))
            )
            lines.append(self._t("cmd.model.triangles", v=str(obj.get("triangles", "—"))))
            lines.append(
                self._t(
                    "cmd.model.manifold",
                    v=self._t("cmd.yes" if obj.get("manifold") else "cmd.no"),
                )
            )
            for inst in obj.get("instances", []):
                line = self._t("cmd.model.instance", v=str(inst.get("index", "—")))
                if inst.get("mirrored"):
                    line += self._t("cmd.model.mirrored")
                lines.append(line)
        self._append_system("\n".join(lines))

    def _cmd_printer(self: "_ChatEngine") -> None:
        """Формирует сводку профилей печати."""
        chat = self._active_chat()
        data = self._collect_preset_data(chat.get("context_modes", {}))
        lines = [self._t("cmd.printer.title")]
        sections = (
            ("printer", self._t("cmd.printer.section_printer")),
            ("filament", self._t("cmd.printer.section_filament")),
            ("print", self._t("cmd.printer.section_print")),
        )
        for key, label in sections:
            section = data.get(key, {})
            params = section.get("params", {}) if isinstance(section, dict) else {}
            if not params:
                lines.append("• " + self._t("cmd.printer.unavailable", label=label))
                continue
            lines.append("• " + label + ":")
            name = section.get("name")
            if name:
                lines.append("  " + self._t("cmd.printer.profile", name=str(name)))
            for field, value in params.items():
                lines.append("  " + str(field) + ": " + str(value))
        self._append_system("\n".join(lines))

    def _cmd_stats(self: "_ChatEngine") -> None:
        """Выводит статистику использования ассистента."""
        snap = self._usage_snapshot("all")
        self._append_system(
            self._t("cmd.stats.line", msgs=str(snap["msgs"]), tokens=str(snap["tokens"]))
        )

    def _cmd_context(self: "_ChatEngine") -> None:
        """Выводит полный дамп контекста слайсера."""
        chat = self._active_chat()
        flags = chat.get("context_flags", {})
        modes = chat.get("context_modes", {})
        ctx = self._collect_context(flags, modes)
        lines = [self._t("cmd.context.title")]
        lines.append(self._t("cmd.context.system_prompt"))
        lines.append(self._build_system_prompt(ctx, include_data=False))
        lines.append(self._t("cmd.context.checkboxes"))
        for key, value in flags.items():
            lines.append(
                "  "
                + str(key)
                + ": "
                + self._t("cmd.context.on" if value else "cmd.context.off")
            )
        lines.append(self._t("cmd.context.data"))
        if any(flags.get(key) for key in ("filament", "printer", "print", "model")):
            lines.append(json.dumps(ctx, ensure_ascii=False, indent=2))
        else:
            lines.append("  " + self._t("cmd.context.disabled"))
        lines.append(self._t("cmd.context.history"))
        if not flags.get("history"):
            lines.append("  " + self._t("cmd.context.disabled"))
        else:
            history = self._history_messages(
                chat, MAX_CONTEXT_CHARS, include_last_user=True
            )
            if history:
                for item in history:
                    lines.append("  [" + item["role"] + "] " + item["content"][:200])
            else:
                lines.append("  " + self._t("cmd.context.empty"))
        lines.append(
            self._t("cmd.context.tokens", v=str(self._estimate_context_tokens(flags, modes)))
        )
        self._append_system("\n".join(lines))

    def _confirm_command(self: "_ChatEngine", cmd: str) -> bool:
        """Реализует двухшаговое подтверждение деструктивной команды."""
        if self._pending_confirm != cmd:
            self._pending_confirm = cmd
            self._append_system(self._t("cmd.confirm", cmd=cmd))
            return False
        self._pending_confirm = None
        return True

    def _cmd_clear(self: "_ChatEngine") -> None:
        """Очищает историю чата с двухшаговым подтверждением."""
        if not self._confirm_command("/clear"):
            return
        chat = self._active_chat()
        chat["msgs"] = []
        chat["title"] = ""
        chat["updated"] = time.time()
        self._ctx_tokens = 0
        self._save_chats()
        self._append_system(self._t("cmd.clear.done"))

    def _cmd_reset(self: "_ChatEngine", text: str) -> None:
        """Сбрасывает настройки либо историю чатов с двухшаговым подтверждением."""
        parts = text.split()
        clear_chats = len(parts) > 1 and parts[1].lower() == "chats"
        target = "/reset chats" if clear_chats else "/reset"
        if not self._confirm_command(target):
            return
        if clear_chats:
            self._chats = []
            self._active = 0
            self._create_chat()
            self._save_chats()
            self._send_state()
            self._append_system(self._t("cmd.reset_chats.done"))
            return
        self._config = self._normalize_config(DEFAULT_CONFIG.copy())
        self._persist_config()
        self._send_state()
        self._append_system(self._t("cmd.reset.done"))

    # ===== Статистика использования =====

    def _record_usage(self: "_ChatEngine", user_text: str, answer_text: str) -> None:
        """Учитывает сообщение и токены в статистике использования."""
        today = time.strftime("%Y-%m-%d")
        usage = self._config.setdefault("usage", {})
        day = usage.setdefault(today, {"msgs": 0, "tokens": 0})
        day["msgs"] += 1
        day["tokens"] += (len(user_text) + len(answer_text)) // 4
        self._persist_config()

    def _usage_snapshot(self: "_ChatEngine", period: str) -> dict[str, Any]:
        """Возвращает сводку использования за выбранный период."""
        usage = self._config.get("usage", {})
        today = time.strftime("%Y-%m-%d")
        # UI исторически присылает "today", старый код ждал "day" — принимаем оба.
        if period in ("day", "today"):
            keys = [today]
        elif period == "week":
            keys = [
                (datetime.date.today() - datetime.timedelta(days=i)).isoformat()
                for i in range(7)
            ]
        elif period == "month":
            keys = [key for key in usage if key.startswith(today[:7])]
        else:
            keys = list(usage)
        msgs = sum(usage.get(key, {}).get("msgs", 0) for key in keys)
        tokens = sum(usage.get(key, {}).get("tokens", 0) for key in keys)
        return {"period": period, "msgs": msgs, "tokens": tokens}
