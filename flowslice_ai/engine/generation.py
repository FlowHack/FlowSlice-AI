"""Генерация и стриминг ответов движка FlowSlice AI.

Миксин GenerationMixin запускает фоновый поток генерации, собирает
сообщения для запроса (системный промпт, история, вложения) и обрабатывает
ошибки генерации.
"""
# pyright (миксины _ChatEngine): reportGeneralTypeIssues отключён только здесь.
# pyright: reportGeneralTypeIssues=false
# pylint: disable=too-many-lines,too-many-branches,too-many-statements,broad-exception-caught
# pylint: disable=too-many-public-methods,too-few-public-methods

import hashlib
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
            self._cancel_event.clear()
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
        # Нужны обе цены: при частично загруженных данных оценка вводила бы
        # в заблуждение (недостающая цена считалась бы нулевой).
        if price_in is None or price_out is None:
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
        # Снимок модели текущего запроса: ответ должен ссылаться на неё,
        # даже если пользователь переключит модель во время генерации.
        prov_id, model_id, model_name = self._active_model_info()
        if model_id:
            chat["model"] = prov_id + "::" + model_id
        assistant_msg: dict[str, Any] = {
            "id": msg_id,
            "role": "assistant",
            "text": "",
            "ts": time.time(),
            "provider": prov_id,
            "model": model_id,
            "model_name": model_name,
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
            if self._cancel_event.is_set():
                # Пользователь нажал «Стоп»: не выдаём пустой ответ модели,
                # а честно помечаем генерацию прерванной.
                _LOGGER.info("Генерация прервана пользователем (запрос %s)", user_msg_id)
                self._finish_stopped(chat, chat_id, msg_id)
                return
            if not full_text.strip():
                full_text = self._t("gen.empty_reply")
            out_tokens = len(full_text) // 4
            cost = self._estimate_cost(in_tokens, out_tokens)
            # Если провайдер прислал точный usage (OpenRouter) — берём его.
            usage = self._last_usage
            if isinstance(usage, dict):
                real_in = usage.get("prompt_tokens")
                real_out = usage.get("completion_tokens")
                if isinstance(real_in, int) and real_in > 0:
                    in_tokens = real_in
                if isinstance(real_out, int) and real_out >= 0:
                    out_tokens = real_out
                real_cost = usage.get("cost")
                if isinstance(real_cost, (int, float)):
                    cost = float(real_cost)
                else:
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
            if self._cancel_event.is_set() or not self._gen:
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

    @staticmethod
    def _image_hash(data_uri: str) -> str:
        """Возвращает хеш содержимого изображения для поиска дублей."""
        return hashlib.sha1(data_uri.encode("utf-8", "ignore")).hexdigest()

    def _current_message_images(self: "_ChatEngine", chat: dict[str, Any]) -> list[str]:
        """Возвращает изображения последнего сообщения пользователя.

        Фотографии из истории в запрос не примешиваются: они остаются в своих
        сообщениях (см. _history_messages), поэтому модель понимает, какое фото
        к какому сообщению относится.
        """
        last_user = self._last_user_msg(chat)
        if last_user is None:
            return []
        return self._message_images(last_user)[:MAX_IMAGES_IN_REQUEST]

    def _history_image_limit(self: "_ChatEngine") -> int:
        """Сколько изображений из истории разрешено отправлять (настройка)."""
        raw = self._config.get("max_history_images", MAX_IMAGES_IN_HISTORY)
        try:
            value = int(raw)
        except (TypeError, ValueError):
            value = MAX_IMAGES_IN_HISTORY
        return max(0, min(value, MAX_IMAGES_IN_REQUEST))

    def _image_block(self: "_ChatEngine", data_uri: str, scheme: str) -> dict[str, Any]:
        """Формирует блок изображения под схему активного провайдера."""
        if scheme == "anthropic":
            b64 = data_uri.split(",", 1)[1] if "," in data_uri else data_uri
            return {
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": self._image_media_type(data_uri),
                    "data": b64,
                },
            }
        return {"type": "image_url", "image_url": {"url": data_uri}}

    def _build_messages(
        self: "_ChatEngine",
        chat: dict[str, Any],
        user_text: str,
        refresh_vision: bool = True,
    ) -> list[dict[str, Any]]:
        """Собирает список сообщений для запроса к модели.

        При refresh_vision=False сведения о зрении модели берутся только из
        кэша (без сети) — это нужно команде /context, работающей в UI-потоке.
        """
        flags = chat.get("context_flags", {})
        modes = chat.get("context_modes", {})
        ctx = self._collect_context(flags, modes)
        # Изображения текущего сообщения: от их наличия зависит системный промпт.
        images = self._current_message_images(chat)
        vision = self._model_supports_images(refresh=refresh_vision)
        scheme = self._active_scheme()
        no_vision = False
        allow_images = True
        if vision is False:
            # Модель без зрения: картинки не отправляем, но просим честно
            # сказать, что анализировать изображения она не умеет.
            no_vision = self._message_has_image(self._last_user_msg(chat) or {})
            images = []
            allow_images = False
        elif vision is None and images:
            # Возможности модели неизвестны: изображение отправляем, но на
            # всякий случай добавляем подсказку — вдруг модель его не видит.
            no_vision = True
        last_user = self._last_user_msg(chat)
        last_files = self._collect_files(last_user) if last_user is not None else []
        history: list[dict[str, Any]] = []
        if flags.get("history"):
            # Фото истории идут в своих сообщениях; дубли текущего запроса
            # (то же изображение приложено повторно) повторно не отправляются.
            history = self._history_messages(
                chat,
                MAX_CONTEXT_CHARS,
                include_images=allow_images,
                max_images=self._history_image_limit(),
                skip_hashes={self._image_hash(data) for data in images},
                scheme=scheme,
            )
        # Вложения могут прийти и в истории, поэтому ищем <document> в обоих местах.
        has_files = bool(last_files) or any(
            "<document>" in self._message_text(m) for m in history
        )
        system = self._build_system_prompt(
            ctx,
            has_images=bool(images),
            no_vision=no_vision,
            has_files=has_files,
        )
        summary = str(chat.get("summary", "") or "").strip()
        if summary:
            header = self._t("compact.summary_header")
            system += f"\n\n{header}\n{summary}"
        if len(system) > MAX_CONTEXT_CHARS:
            system = system[:MAX_CONTEXT_CHARS]
        messages: list[dict[str, Any]] = [{"role": "system", "content": system}]
        messages.extend(history)
        user_content = user_text
        for file_info in last_files:
            user_content += self._render_file(file_info)
        if images:
            # Изображения текущего сообщения: текстовый блок, затем блоки фото.
            content: list[dict[str, Any]] = [{"type": "text", "text": user_content}]
            for img in images:
                content.append(self._image_block(img, scheme))
            messages.append({"role": "user", "content": content})
        else:
            messages.append({"role": "user", "content": user_content})
        return messages

    def _preview_messages(self: "_ChatEngine") -> list[dict[str, Any]]:
        """Собирает точный список сообщений, который уйдёт модели.

        Берётся последнее сообщение пользователя из активного чата, поэтому
        результат совпадает с реальным запросом на генерацию. Сеть не
        запрашивается: сведения о зрении берутся из кэша.
        """
        chat = self._active_chat()
        last_user = self._last_user_msg(chat)
        user_text = str(last_user.get("text", "")) if last_user else ""
        return self._build_messages(chat, user_text, refresh_vision=False)

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
        include_images: bool = False,
        max_images: int = 0,
        skip_hashes: set[str] | None = None,
        scheme: str = "openai",
    ) -> list[dict[str, Any]]:
        """Собирает историю сообщений для контекста, отбрасывая старые.

        При include_last_user=True (команда /context) включается и последнее
        сообщение пользователя — для полного дампа истории. При
        include_images=True фото из истории остаются в своих сообщениях (не
        больше max_images за весь запрос); изображения, чей хеш есть в
        skip_hashes (то же фото приложено повторно в текущем сообщении), не
        отправляются второй раз — вместо блока остаётся маркер.
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
        images_left = max(0, max_images)
        skip = skip_hashes if isinstance(skip_hashes, set) else set()
        seen = set(skip)
        for msg in reversed(history):
            if msg.get("role") not in ("user", "assistant"):
                continue
            # Технические ошибки не отправляем модели: это не ответ ассистента.
            if msg.get("error"):
                continue
            text = str(msg.get("text", ""))
            has_photo = bool(msg.get("image"))
            if has_photo:
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
                        has_photo = True
                        text += self._t("chat.photo_marker")
                    elif isinstance(att.get("file"), dict):
                        text += self._render_file(att["file"])
            if total + len(text) > max_chars:
                # Свежее сообщение включаем всегда (при необходимости усекая):
                # иначе при одном длинном сообщении модель получила бы пустую историю.
                if not result and max_chars > 0:
                    result.append({"role": msg["role"], "content": text[:max_chars]})
                break
            content: Any = text
            if include_images and has_photo and images_left > 0:
                blocks: list[dict[str, Any]] = [{"type": "text", "text": text}]
                added = 0
                for data in self._message_images(msg):
                    digest = self._image_hash(data)
                    if digest in seen:
                        continue
                    seen.add(digest)
                    blocks.append(self._image_block(data, scheme))
                    added += 1
                    images_left -= 1
                    if images_left <= 0:
                        break
                if added:
                    content = blocks
            result.append({"role": msg["role"], "content": content})
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
