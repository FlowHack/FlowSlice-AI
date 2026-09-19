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
from flowslice_ai.logging import _LOGGER
from flowslice_ai.setting_labels import humanize_params


def _labels_lang(config: Any) -> str:
    """Возвращает язык ответа для меток параметров; по умолчанию английский."""
    if isinstance(config, dict):
        return str(config.get("language", "en"))
    return "en"


def _usage_int(value: Any) -> int:
    """Приводит значение счётчика к целому числу, устойчиво к мусору в конфиге."""
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _usage_numbers(day: Any) -> tuple[int, int]:
    """Извлекает пару (сообщения, токены) из дневной записи статистики."""
    if not isinstance(day, dict):
        return 0, 0
    return _usage_int(day.get("msgs")), _usage_int(day.get("tokens"))


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
        elif cmd == "/compact":
            self._handle_compact({})
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
            for field, value in humanize_params(params, _labels_lang(self._config)).items():
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
        lines = [self._t("cmd.context.title")]
        try:
            # Тот же список сообщений, что уходит в запрос на генерацию.
            messages = self._preview_messages()
        except Exception as exc:  # pylint: disable=broad-except
            _LOGGER.warning(
                "Не удалось собрать контекст для /context: %s", exc, exc_info=True
            )
            messages = []
        system_text = ""
        rest: list[dict[str, Any]] = []
        for message in messages:
            if not system_text and message.get("role") == "system":
                system_text = self._preview_content_text(message.get("content"))
            else:
                rest.append(message)
        lines.append(self._t("cmd.context.system_prompt"))
        lines.append(system_text or "  " + self._t("cmd.context.empty"))
        lines.append(self._t("cmd.context.messages"))
        if rest:
            for message in rest:
                lines.append(
                    "  ["
                    + str(message.get("role", ""))
                    + "] "
                    + self._preview_content_text(message.get("content"))
                )
        else:
            lines.append("  " + self._t("cmd.context.empty"))
        lines.append(self._t("cmd.context.checkboxes"))
        for key, value in flags.items():
            lines.append(
                "  "
                + str(key)
                + ": "
                + self._t("cmd.context.on" if value else "cmd.context.off")
            )
        lines.append(
            self._t("cmd.context.tokens", v=str(self._estimate_messages_tokens(messages)))
        )
        self._append_system("\n".join(lines))

    @staticmethod
    def _preview_image_placeholder(data: str, mime: str = "image") -> str:
        """Кратко описывает изображение вместо многомегабайтного base64."""
        size_kb = len(data) * 3 // 4096
        return f"<{mime}, ~{size_kb} КБ base64>"

    def _preview_content_text(self: "_ChatEngine", content: Any) -> str:
        """Преобразует содержимое сообщения в читаемый текст для /context."""
        if isinstance(content, str):
            return content
        if not isinstance(content, list):
            return json.dumps(content, ensure_ascii=False)
        parts: list[str] = []
        for block in content:
            if not isinstance(block, dict):
                parts.append(str(block))
                continue
            block_type = block.get("type")
            if block_type == "text":
                parts.append(str(block.get("text", "")))
            elif block_type == "image_url":
                image_url = block.get("image_url")
                url = (
                    image_url.get("url", "")
                    if isinstance(image_url, dict)
                    else str(image_url)
                )
                base64_part = url.split(",", 1)[1] if "," in url else url
                parts.append(self._preview_image_placeholder(base64_part))
            elif block_type == "image":
                source = block.get("source")
                data = str(source.get("data", "")) if isinstance(source, dict) else ""
                mime = (
                    str(source.get("media_type", "image"))
                    if isinstance(source, dict)
                    else "image"
                )
                parts.append(self._preview_image_placeholder(data, mime))
            else:
                parts.append(json.dumps(block, ensure_ascii=False))
        return "\n".join(part for part in parts if part)

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
        # Сводка прошлой переписки больше не актуальна: без сброса она
        # продолжала бы уходить модели в системном промпте.
        chat["summary"] = ""
        chat["summary_count"] = 0
        chat.pop("summary_at", None)
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
        usage = self._config.get("usage")
        if not isinstance(usage, dict):
            usage = {}
        msgs, tokens = _usage_numbers(usage.get(today))
        usage[today] = {
            "msgs": msgs + 1,
            "tokens": tokens + (len(user_text) + len(answer_text)) // 4,
        }
        self._config["usage"] = usage
        self._persist_config()

    def _usage_snapshot(self: "_ChatEngine", period: str) -> dict[str, Any]:
        """Возвращает сводку использования за выбранный период."""
        usage = self._config.get("usage")
        if not isinstance(usage, dict):
            usage = {}
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
            keys = [
                key
                for key in usage
                if isinstance(key, str) and key.startswith(today[:7])
            ]
        else:
            keys = list(usage)
        msgs = 0
        tokens = 0
        for key in keys:
            day_msgs, day_tokens = _usage_numbers(usage.get(key))
            msgs += day_msgs
            tokens += day_tokens
        return {"period": period, "msgs": msgs, "tokens": tokens}
