"""Сжатие длинной истории чата в краткую сводку для контекста модели."""

# pyright: reportGeneralTypeIssues=false
# pyright (миксины _ChatEngine): reportGeneralTypeIssues отключён только здесь.
# pylint: disable=too-few-public-methods,too-many-return-statements

from __future__ import annotations

import threading
import time
from typing import TYPE_CHECKING, Any

from ..constants import (
    COMPACT_KEEP_MESSAGES,
    COMPACT_MAX_SOURCE_CHARS,
    COMPACT_MAX_TOKENS,
    COMPACT_MIN_NEW_MESSAGES,
    COMPACT_SYSTEM_PROMPT,
)
from ..logging import _LOGGER

if TYPE_CHECKING:
    from ..plugin import _ChatEngine


class CompactionMixin:
    """Автосжатие истории и команда /compact.

    Исходные сообщения чата не удаляются: для модели формируется сводка
    (chat["summary"]), а покрытые сообщения перестают попадать в контекст
    через chat["summary_count"].
    """

    def _compact_window_tokens(self: "_ChatEngine") -> int:
        """Возвращает размер окна контекста активной модели в токенах."""
        try:
            window = int(self._config.get("context_window", 128000))
        except (TypeError, ValueError):
            window = 128000
        return window if window > 0 else 128000

    def _compact_threshold_tokens(self: "_ChatEngine") -> int:
        """Возвращает порог сжатия в токенах исходя из процента настроек."""
        percent = self._config.get("compact_threshold", 80)
        try:
            percent = int(percent)
        except (TypeError, ValueError):
            percent = 80
        percent = min(max(percent, 10), 100)
        return self._compact_window_tokens() * percent // 100

    def _should_compact(self: "_ChatEngine", chat: dict[str, Any]) -> bool:
        """Проверяет, нужно ли сжать историю перед отправкой запроса."""
        if not self._config.get("compact_enabled", True):
            return False
        if self._chat_context_tokens(chat) < self._compact_threshold_tokens():
            return False
        return self._compact_range(chat) is not None

    def _chat_context_tokens(self: "_ChatEngine", chat: dict[str, Any]) -> int:
        """Оценивает токены контекста истории без учёта системного промпта."""
        return self._estimate_messages_tokens(self._history_messages(chat, 1_000_000))

    def _compact_range(self: "_ChatEngine", chat: dict[str, Any]) -> tuple[int, int] | None:
        """Возвращает границы [start, end) сообщений, которые нужно сжать."""
        msgs = chat.get("msgs", [])
        if not isinstance(msgs, list):
            return None
        start = int(chat.get("summary_count", 0) or 0)
        start = max(start, 0)
        if start > len(msgs):
            start = 0
        end = len(msgs) - COMPACT_KEEP_MESSAGES
        if end <= start:
            return None
        return start, end

    def _compact_transcript(self: "_ChatEngine", chat: dict[str, Any]) -> str:
        """Собирает текст сжимаемых сообщений в одну строку."""
        bounds = self._compact_range(chat)
        if bounds is None:
            return ""
        start, end = bounds
        msgs = chat.get("msgs", [])
        parts: list[str] = []
        total = 0
        for msg in msgs[start:end]:
            if not isinstance(msg, dict):
                continue
            if msg.get("role") not in ("user", "assistant"):
                continue
            if msg.get("error"):
                continue
            text = str(msg.get("text", "") or "")
            if not text:
                text = self._message_text(msg)
            text = text.strip()
            if not text:
                continue
            prefix = "User" if msg.get("role") == "user" else "Assistant"
            line = f"{prefix}: {text}"
            if total + len(line) > COMPACT_MAX_SOURCE_CHARS:
                break
            parts.append(line)
            total += len(line)
        return "\n\n".join(parts)

    def _compact_count(self: "_ChatEngine", chat: dict[str, Any]) -> int:
        """Возвращает число новых сообщений, доступных для сжатия."""
        bounds = self._compact_range(chat)
        if bounds is None:
            return 0
        start, end = bounds
        msgs = chat.get("msgs", [])
        count = 0
        for msg in msgs[start:end]:
            if not isinstance(msg, dict):
                continue
            if msg.get("role") not in ("user", "assistant"):
                continue
            if msg.get("error"):
                continue
            count += 1
        return count

    def _maybe_compact(
        self: "_ChatEngine", chat: dict[str, Any], force: bool = False
    ) -> bool:
        """Сжимает историю в сводку. Возвращает True, если чат изменился.

        force=True используется командой /compact: проверки порога и минимума
        новых сообщений пропускаются, но перекрывать последние сохранённые
        COMPACT_KEEP_MESSAGES сообщений по-прежнему нельзя.
        """
        bounds = self._compact_range(chat)
        if bounds is None:
            return False
        new_count = self._compact_count(chat)
        if new_count < 1:
            return False
        if not force and new_count < COMPACT_MIN_NEW_MESSAGES:
            return False
        transcript = self._compact_transcript(chat)
        if not transcript:
            return False
        previous = str(chat.get("summary", "") or "")
        user_content = transcript
        if previous:
            header = self._t("compact.summary_header")
            user_content = f"{header}\n{previous}\n\n{transcript}"
        messages = [
            {"role": "system", "content": COMPACT_SYSTEM_PROMPT},
            {"role": "user", "content": user_content},
        ]
        try:
            summary = self._call_api_blocking(messages, max_tokens=COMPACT_MAX_TOKENS)
        except Exception as exc:  # pylint: disable=broad-except
            _LOGGER.warning(
                "Не удалось сжать историю чата (провайдер=%s): %s",
                self._config.get("active_provider"),
                exc,
                exc_info=True,
            )
            return False
        summary = summary.strip()
        if not summary:
            _LOGGER.warning("Модель вернула пустую сводку истории чата")
            return False
        start, end = bounds
        chat["summary"] = summary[: COMPACT_MAX_SOURCE_CHARS]
        chat["summary_count"] = end
        chat["summary_at"] = time.time()
        self._save_chats()
        _LOGGER.info("История чата сжата: сообщений покрыто %s", end - start)
        return True

    def _compact_worker(self: "_ChatEngine", chat_id: Any) -> None:
        """Фоновое сжатие истории по команде /compact."""
        chat = self._chat_by_id(chat_id)
        if chat is None:
            self._compacting = False
            return
        try:
            self._toast(self._t("compact.started"), "")
            changed = self._maybe_compact(chat, force=True)
            if changed:
                count = chat.get("summary_count", 0)
                self._toast(self._t("compact.done", n=str(count)), "ok")
            else:
                self._toast(self._t("compact.nothing"), "")
        except Exception as exc:  # pylint: disable=broad-except
            _LOGGER.error("Ошибка сжатия истории чата: %s", exc, exc_info=True)
            self._toast(self._t("compact.failed", err=str(exc)), "err")
        finally:
            self._compacting = False
            self._send_state()

    def _handle_compact(self: "_ChatEngine", message: dict[str, Any]) -> None:
        """Запускает ручное сжатие истории активного чата."""
        if self._gen or self._compacting:
            self._toast(self._t("compact.busy"), "warn")
            return
        chat_id = message.get("chat_id") or self._active
        chat = self._chat_by_id(chat_id)
        if chat is None or self._compact_range(chat) is None:
            self._toast(self._t("compact.nothing"), "")
            return
        self._compacting = True
        thread = threading.Thread(
            target=self._compact_worker,
            args=(chat_id,),
            name="flowslice-compact",
            daemon=True,
        )
        thread.start()
