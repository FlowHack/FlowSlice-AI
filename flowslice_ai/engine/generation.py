"""Генерация и стриминг ответов движка FlowSlice AI.

Миксин GenerationMixin запускает фоновый поток генерации, собирает
сообщения для запроса (системный промпт, история, вложения) и обрабатывает
ошибки генерации.
"""
# pyright (миксины _ChatEngine): reportGeneralTypeIssues отключён только здесь.
# pyright: reportGeneralTypeIssues=false
# pylint: disable=too-many-lines,too-many-branches,too-many-statements,broad-exception-caught
# pylint: disable=too-many-public-methods,too-few-public-methods

import threading
import time
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from flowslice_ai.engine import _ChatEngine

from flowslice_ai.constants import MAX_CONTEXT_CHARS, MAX_IMAGES_IN_HISTORY, MAX_IMAGES_IN_REQUEST
from flowslice_ai.errors import FlowSliceError
from flowslice_ai.logging import _LOGGER


class GenerationMixin:
    """Запуск генерации, сборка сообщений и обработка ошибок."""

    def _start_generation(self: "_ChatEngine", chat_id: int, user_text: str, user_msg_id: int) -> None:
        """Запускает генерацию ответа в фоновом потоке."""
        with self._gen_lock:
            if self._gen:
                self._post(
                    {
                        "type": "toast",
                        "text": self._t("gen.already"),
                        "kind": "err",
                    }
                )
                return
            self._gen = True
        threading.Thread(
            target=self._worker, args=(chat_id, user_text, user_msg_id), daemon=True
        ).start()

    def _worker(self: "_ChatEngine", chat_id: int, user_text: str, user_msg_id: int) -> None:
        """Выполняет запрос к API в фоновом потоке и стримит ответ."""
        chat = self._chat_by_id(chat_id)
        if chat is None:
            self._gen = False
            return
        msg_id = self._next_msg_id()
        chat["msgs"].append(
            {"id": msg_id, "role": "assistant", "text": "", "ts": time.time()}
        )
        self._save_chats()
        # Полный state с пустым ответом ассистента: UI привязывает стрим к нему.
        self._send_state()
        try:
            messages = self._build_messages(chat, user_text)
            full_text, reasoning = self._call_api(messages, chat_id)
            if not full_text.strip():
                full_text = self._t("gen.empty_reply")
            msg = self._find_msg(chat, msg_id)
            if msg is not None:
                msg["text"] = full_text
                if reasoning:
                    msg["reasoning"] = reasoning
            self._post(
                {
                    "type": "reply",
                    "chat_id": chat_id,
                    "text": full_text,
                    "ok": True,
                    "reasoning": reasoning,
                }
            )
            self._record_usage(user_text, full_text)
        except FlowSliceError as exc:
            self._fail_generation(chat, chat_id, user_msg_id, msg_id, str(exc))
        except Exception as exc:
            _LOGGER.error("Необработанная ошибка генерации: %s", exc, exc_info=True)
            self._fail_generation(
                chat, chat_id, user_msg_id, msg_id, self._t("gen.internal_error")
            )
        finally:
            with self._gen_lock:
                self._gen = False
            self._save_chats()
            # Полный state: UI получает финальный текст ответа (нужен, например,
            # для экспорта чата, где используется state.chats, а не DOM).
            self._send_state()

    def _fail_generation(
        self: "_ChatEngine",
        chat: dict[str, Any],
        chat_id: int,
        user_msg_id: int,
        msg_id: int,
        text: str,
    ) -> None:
        """Помечает генерацию как ошибочную и уведомляет UI."""
        self._remove_msg(chat, user_msg_id)
        msg = self._find_msg(chat, msg_id)
        if msg is not None:
            msg["text"] = text
            msg["error"] = True
        self._post({"type": "reply", "chat_id": chat_id, "text": text, "ok": False})

    def _find_msg(self: "_ChatEngine", chat: dict[str, Any], msg_id: int) -> dict[str, Any] | None:
        """Возвращает сообщение чата по идентификатору либо None."""
        for msg in chat.get("msgs", []):
            if msg.get("id") == msg_id:
                return msg
        return None

    def _remove_msg(self: "_ChatEngine", chat: dict[str, Any], msg_id: int) -> None:
        """Удаляет сообщение из чата по идентификатору."""
        msgs = chat.get("msgs", [])
        for index, msg in enumerate(msgs):
            if msg.get("id") == msg_id:
                del msgs[index]
                return

    @staticmethod
    def _message_images(msg: dict[str, Any]) -> list[str]:
        """Возвращает data URI изображений одного сообщения (включая legacy-поле)."""
        images: list[str] = []
        image = msg.get("image")
        if isinstance(image, str) and image.startswith("data:"):
            images.append(image)
        attachments = msg.get("attachments")
        if isinstance(attachments, list):
            for att in attachments:
                data = att.get("image") if isinstance(att, dict) else None
                if isinstance(data, str) and data.startswith("data:"):
                    images.append(data)
        return images

    def _collect_context_images(self: "_ChatEngine", chat: dict[str, Any]) -> list[str]:
        """Собирает изображения: все из текущего запроса + ограниченно из истории."""
        images: list[str] = []
        history_count = 0
        current_seen = False
        for msg in reversed(chat.get("msgs", [])):
            candidates = self._message_images(msg)
            if not candidates:
                continue
            is_current = not current_seen and msg.get("role") == "user"
            if is_current:
                current_seen = True
                images.extend(candidates)
            else:
                for data in candidates:
                    if history_count >= MAX_IMAGES_IN_HISTORY:
                        break
                    images.append(data)
                    history_count += 1
            if len(images) >= MAX_IMAGES_IN_REQUEST:
                break
        return images[:MAX_IMAGES_IN_REQUEST]

    def _build_messages(self: "_ChatEngine", chat: dict[str, Any], user_text: str) -> list[dict[str, Any]]:
        """Собирает список сообщений для запроса к модели."""
        flags = chat.get("context_flags", {})
        modes = chat.get("context_modes", {})
        ctx = self._collect_context(flags, modes)
        # Изображения собираем заранее: от их наличия зависит системный промпт.
        images = self._collect_context_images(chat)
        system = self._build_system_prompt(ctx, has_images=bool(images))
        if len(system) > MAX_CONTEXT_CHARS:
            system = system[:MAX_CONTEXT_CHARS]
        messages: list[dict[str, Any]] = [{"role": "system", "content": system}]
        if flags.get("history"):
            messages.extend(self._history_messages(chat, MAX_CONTEXT_CHARS))
        user_content = user_text
        last_user = self._last_user_msg(chat)
        if last_user is not None:
            for file_info in self._collect_files(last_user):
                user_content += self._render_file(file_info)
        scheme = self._active_scheme()
        if images and scheme == "anthropic":
            # Нативный Messages API: изображения как base64-блоки.
            content: list[dict[str, Any]] = [{"type": "text", "text": user_content}]
            for img in images:
                b64 = img.split(",", 1)[1] if "," in img else img
                content.append(
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": self._image_media_type(img),
                            "data": b64,
                        },
                    }
                )
            messages.append({"role": "user", "content": content})
        elif images:
            content = [{"type": "text", "text": user_content}]
            content.extend(
                {"type": "image_url", "image_url": {"url": img}} for img in images
            )
            messages.append({"role": "user", "content": content})
        else:
            messages.append({"role": "user", "content": user_content})
        return messages

    @staticmethod
    def _image_media_type(data_uri: str) -> str:
        """Определяет MIME-тип изображения из data URI (по умолчанию JPEG)."""
        if data_uri.startswith("data:"):
            header = data_uri[5:].split(";", 1)[0].split(",", 1)[0]
            if header.startswith("image/"):
                return header
        return "image/jpeg"

    def _last_user_msg(self: "_ChatEngine", chat: dict[str, Any]) -> dict[str, Any] | None:
        """Возвращает последнее сообщение пользователя в чате."""
        for msg in reversed(chat.get("msgs", [])):
            if msg.get("role") == "user":
                return msg
        return None

    def _collect_files(self: "_ChatEngine", msg: dict[str, Any]) -> list[dict[str, Any]]:
        """Возвращает файловые вложения сообщения (включая legacy-поле file)."""
        files: list[dict[str, Any]] = []
        legacy = msg.get("file")
        if isinstance(legacy, dict):
            files.append(legacy)
        attachments = msg.get("attachments")
        if isinstance(attachments, list):
            for att in attachments:
                if isinstance(att, dict) and isinstance(att.get("file"), dict):
                    files.append(att["file"])
        return files

    def _history_messages(
        self: "_ChatEngine",
        chat: dict[str, Any],
        max_chars: int,
        include_last_user: bool = False,
    ) -> list[dict[str, Any]]:
        """Собирает историю сообщений для контекста, отбрасывая старые.

        При include_last_user=True (команда /context) включается и последнее
        сообщение пользователя — для полного дампа истории.
        """
        msgs = chat.get("msgs", [])
        history = msgs
        if not include_last_user:
            last_user = self._last_user_msg(chat)
            if last_user is not None:
                history = msgs[: msgs.index(last_user)]
        result: list[dict[str, Any]] = []
        total = 0
        for msg in reversed(history):
            if msg.get("role") not in ("user", "assistant"):
                continue
            text = str(msg.get("text", ""))
            if msg.get("image"):
                text += self._t("chat.photo_marker")
            legacy_file = msg.get("file")
            if isinstance(legacy_file, dict):
                text += self._render_file(legacy_file)
            attachments = msg.get("attachments")
            if isinstance(attachments, list):
                for att in attachments:
                    if not isinstance(att, dict):
                        continue
                    if att.get("image"):
                        text += self._t("chat.photo_marker")
                    elif isinstance(att.get("file"), dict):
                        text += self._render_file(att["file"])
            if total + len(text) > max_chars:
                break
            result.append({"role": msg["role"], "content": text})
            total += len(text)
        result.reverse()
        return result

    def _render_file(self: "_ChatEngine", file_info: dict[str, Any]) -> str:
        """Формирует текстовый блок файла для истории сообщений.

        Блок явно ограничен заголовком и меткой конца, чтобы модель понимала:
        это содержимое файла, а не ссылка на недоступное вложение.
        """
        name = str(file_info.get("name", self._t("attach.default_name")))
        content = str(file_info.get("text", ""))
        if not content:
            return self._t("chat.file_marker", name=name)
        block = self._t("prompt.file", name=name, text=content)
        if file_info.get("truncated"):
            block += self._t("prompt.file_truncated")
        return block + self._t("prompt.file_footer")
