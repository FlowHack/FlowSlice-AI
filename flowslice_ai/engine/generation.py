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

    def _start_generation(
        self: "_ChatEngine", chat_id: int, user_text: str, user_msg_id: int
    ) -> None:
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

    @staticmethod
    def _estimate_messages_tokens(messages: list[dict[str, Any]]) -> int:
        """Оценивает токены запроса по уже собранным сообщениям.

        Тексты считаются грубо (4 символа на токен), изображения — фиксированной
        оценкой: точное число токенов зависит от провайдера.
        """
        total = 0
        for message in messages:
            content = message.get("content")
            if isinstance(content, str):
                total += len(content) // 4
            elif isinstance(content, list):
                for block in content:
                    if not isinstance(block, dict):
                        continue
                    text = block.get("text")
                    if isinstance(text, str):
                        total += len(text) // 4
                    elif block.get("type") in ("image_url", "image"):
                        total += 1100
        return total

    def _active_model_prices(self: "_ChatEngine") -> tuple[float | None, float | None]:
        """Возвращает цены активной модели за 1М токенов (вход, выход)."""
        providers = self._config.get("providers", {})
        provider = providers.get(str(self._config.get("active_provider", "")))
        if not isinstance(provider, dict):
            return None, None
        mdef = provider.get("models", {}).get(str(self._config.get("active_model", "")))
        if not isinstance(mdef, dict):
            return None, None

        def _number(value: Any) -> float | None:
            if isinstance(value, (int, float)) and not isinstance(value, bool) and value >= 0:
                return float(value)
            return None

        return _number(mdef.get("price_in")), _number(mdef.get("price_out"))

    def _estimate_cost(self: "_ChatEngine", in_tokens: int, out_tokens: int) -> float | None:
        """Оценивает стоимость запроса в USD.

        Возвращает None, если цены модели неизвестны: тогда стоимость просто
        не показывается, а не подменяется нулём.
        """
        price_in, price_out = self._active_model_prices()
        if price_in is None and price_out is None:
            return None
        total = in_tokens * (price_in or 0.0) + out_tokens * (price_out or 0.0)
        return total / 1_000_000.0

    def _worker(self: "_ChatEngine", chat_id: int, user_text: str, user_msg_id: int) -> None:
        """Выполняет запрос к API в фоновом потоке и стримит ответ."""
        chat = self._chat_by_id(chat_id)
        if chat is None:
            self._gen = False
            return
        msg_id = self._next_msg_id()
        assistant_msg: dict[str, Any] = {
            "id": msg_id,
            "role": "assistant",
            "text": "",
            "ts": time.time(),
        }
        pending = self._pending_variants.pop(chat_id, None)
        if pending:
            # Предыдущие ответы становятся вариантами; текущий добавится в конце.
            assistant_msg["variants"] = pending
            assistant_msg["variant_index"] = len(pending)
        chat["msgs"].append(assistant_msg)
        self._save_chats()
        # Полный state с пустым ответом ассистента: UI привязывает стрим к нему.
        # Изображения передаются, чтобы только что прикреплённое фото отобразилось.
        self._send_state(include_images=True)
        try:
            if chat.get("context_flags", {}).get("history") and self._should_compact(chat):
                try:
                    if self._maybe_compact(chat):
                        self._send_state()
                except Exception as exc:  # pylint: disable=broad-except
                    _LOGGER.warning(
                        "Автосжатие истории чата не удалось: %s", exc, exc_info=True
                    )
            messages = self._build_messages(chat, user_text)
            in_tokens = self._estimate_messages_tokens(messages)
            full_text, reasoning = self._call_api(messages, chat_id)
            if not full_text.strip():
                full_text = self._t("gen.empty_reply")
            out_tokens = len(full_text) // 4
            cost = self._estimate_cost(in_tokens, out_tokens)
            msg = self._find_msg(chat, msg_id)
            if msg is not None:
                msg["text"] = full_text
                if reasoning:
                    msg["reasoning"] = reasoning
                msg["tokens_in"] = in_tokens
                msg["tokens_out"] = out_tokens
                if cost is not None:
                    msg["cost"] = cost
                variants = msg.get("variants")
                if isinstance(variants, list) and variants:
                    variants.append({"text": full_text, "reasoning": reasoning or ""})
                    msg["variant_index"] = len(variants) - 1
            self._post(
                {
                    "type": "reply",
                    "chat_id": chat_id,
                    "text": full_text,
                    "ok": True,
                    "reasoning": reasoning,
                    "tokens_in": in_tokens,
                    "tokens_out": out_tokens,
                    "cost": cost,
                }
            )
            self._record_usage(user_text, full_text)
        except FlowSliceError as exc:
            if not self._gen:
                # Пользователь нажал «Стоп» во время ожидания повтора:
                # это не ошибка, поэтому не помечаем ответ как сбойный.
                _LOGGER.info(
                    "Генерация прервана пользователем (запрос %s): %s", user_msg_id, exc
                )
                self._finish_stopped(chat, chat_id, msg_id)
            else:
                _LOGGER.warning("Ошибка генерации (запрос %s): %s", user_msg_id, exc)
                self._fail_generation(chat, chat_id, msg_id, str(exc))
        except Exception as exc:
            _LOGGER.error(
                "Необработанная ошибка генерации (запрос %s): %s",
                user_msg_id,
                exc,
                exc_info=True,
            )
            self._fail_generation(chat, chat_id, msg_id, self._t("gen.internal_error"))
        finally:
            with self._gen_lock:
                self._gen = False
            self._save_chats()
            # Полный state: UI получает финальный текст ответа (нужен, например,
            # для экспорта чата, где используется state.chats, а не DOM).
            self._send_state()

    def _finish_stopped(
        self: "_ChatEngine", chat: dict[str, Any], chat_id: int, msg_id: int
    ) -> None:
        """Завершает прерванную пользователем генерацию без пометки об ошибке.

        Если частичный текст уже пришёл, он сохраняется; иначе в сообщение
        записывается отметка об остановке, чтобы не оставалось пустого пузыря.
        """
        msg = self._find_msg(chat, msg_id)
        text = str(msg.get("text", "")) if msg is not None else ""
        if not text.strip():
            text = self._t("gen.stopped")
            if msg is not None:
                msg["text"] = text
        self._post({"type": "reply", "chat_id": chat_id, "text": text, "ok": True})

    def _fail_generation(
        self: "_ChatEngine",
        chat: dict[str, Any],
        chat_id: int,
        msg_id: int,
        text: str,
    ) -> None:
        """Помечает генерацию как ошибочную и уведомляет UI.

        Сообщение пользователя НЕ удаляется: оно остаётся в чате, чтобы было
        видно, какой именно запрос привёл к ошибке.
        """
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

    @staticmethod
    def _message_has_image(msg: dict[str, Any]) -> bool:
        """Проверяет наличие изображения в сообщении (в том числе без data URI)."""
        if isinstance(msg.get("image"), str):
            return True
        attachments = msg.get("attachments")
        if isinstance(attachments, list):
            for att in attachments:
                if not isinstance(att, dict):
                    continue
                if att.get("image") or att.get("kind") == "image":
                    return True
        return False

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

    def _build_messages(
        self: "_ChatEngine", chat: dict[str, Any], user_text: str
    ) -> list[dict[str, Any]]:
        """Собирает список сообщений для запроса к модели."""
        flags = chat.get("context_flags", {})
        modes = chat.get("context_modes", {})
        ctx = self._collect_context(flags, modes)
        # Изображения собираем заранее: от их наличия зависит системный промпт.
        images = self._collect_context_images(chat)
        vision = self._model_supports_images()
        no_vision = False
        if vision is False:
            # Модель без зрения: картинку не отправляем, но просим честно
            # сказать, что анализировать изображения она не умеет.
            no_vision = self._message_has_image(self._last_user_msg(chat) or {})
            images = []
        elif vision is None and images:
            # Возможности модели неизвестны: изображение отправляем, но на
            # всякий случай добавляем подсказку — вдруг модель его не видит.
            no_vision = True
        system = self._build_system_prompt(ctx, has_images=bool(images), no_vision=no_vision)
        summary = str(chat.get("summary", "") or "").strip()
        if summary:
            header = self._t("compact.summary_header")
            system += f"\n\n{header}\n{summary}"
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
        start = int(chat.get("summary_count", 0) or 0)
        if start < 0 or start > len(msgs):
            start = 0
        history = msgs[start:]
        if not include_last_user:
            last_user = self._last_user_msg(chat)
            if last_user is not None:
                try:
                    cut = msgs.index(last_user)
                except ValueError:
                    cut = None
                if cut is not None and cut > start:
                    history = msgs[start:cut]
        result: list[dict[str, Any]] = []
        total = 0
        for msg in reversed(history):
            if msg.get("role") not in ("user", "assistant"):
                continue
            # Технические ошибки не отправляем модели: это не ответ ассистента.
            if msg.get("error"):
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
