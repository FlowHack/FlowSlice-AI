"""HTTP-клиент и SSE-стриминг движка FlowSlice AI.

Миксин ApiClientMixin выполняет запросы к API провайдеров (OpenAI-совместимые
и нативный Messages API Anthropic), читает SSE-потоки и проверяет API-ключи.
"""
# pyright (миксины _ChatEngine): reportGeneralTypeIssues отключён только здесь.
# pyright: reportGeneralTypeIssues=false
# pylint: disable=too-many-lines,too-many-statements,too-many-branches
# pylint: disable=too-many-locals,too-many-arguments,too-many-positional-arguments
# pylint: disable=too-many-public-methods,too-few-public-methods

import json
import threading
import time
from typing import TYPE_CHECKING, Any
import urllib.error
import urllib.request

if TYPE_CHECKING:
    from flowslice_ai.engine import _ChatEngine

from flowslice_ai.constants import HTTP_HEADERS, STREAM_THROTTLE, TIMEOUT
from flowslice_ai.errors import ApiError, NetworkError
from flowslice_ai.logging import _LOGGER

_OR_MODELS_TTL = 600.0  # секунд: срок жизни кэша списка моделей OpenRouter
_OR_MODELS_TIMEOUT = 6  # секунд: короткий таймаут, чтобы не блокировать UI
_OR_MODELS_URL = "https://openrouter.ai/api/v1/models"

# Провайдеры, у которых поддержку изображений можно узнать запросом к API.
# Провайдеры, отдающие машинно-читаемый признак зрения в списке моделей.
# Cerebras исключён: по официальной доке /v1/models возвращает только
# id/object/created/owned_by, признака модальностей там нет.
_VISION_API_PROVIDERS = ("openrouter", "anthropic", "mistral", "xai")
_VISION_CACHE_TTL = 600.0  # секунд: срок жизни кэша зрения по провайдеру
_VISION_TIMEOUT = 8  # секунд
_ANTHROPIC_VERSION = "2023-06-01"


class ApiClientMixin:
    """Запросы к API провайдеров, чтение SSE-потоков, проверка ключей."""

    def _api_credentials_for(
        self: "_ChatEngine", provider_id: str, model_id: str = ""
    ) -> tuple[str, str, str, str, str]:
        """Возвращает (provider_id, base_url, api_key, model, scheme) провайдера.

        Учитывает переопределение base_url/api_key на уровне модели.
        Схема API: per-model, затем провайдер, затем "openai".
        """
        prov = self._config.get("providers", {}).get(provider_id)
        if not isinstance(prov, dict):
            prov = {}
        base_url = str(prov.get("base_url", ""))
        api_key = str(prov.get("api_key", ""))
        model = str(model_id or "")
        mdef = prov.get("models", {}).get(model) if model else None
        if isinstance(mdef, dict):
            if mdef.get("base_url"):
                base_url = str(mdef["base_url"])
            if mdef.get("api_key"):
                api_key = str(mdef["api_key"])
        scheme = str(
            (mdef.get("scheme") if isinstance(mdef, dict) else None)
            or prov.get("scheme")
            or "openai"
        )
        return provider_id, base_url, api_key, model, scheme

    def _active_api_credentials(self: "_ChatEngine") -> tuple[str, str, str, str, str]:
        """Возвращает учётные данные активного провайдера и модели."""
        cfg = self._config
        return self._api_credentials_for(
            str(cfg.get("active_provider", "deepseek")),
            str(cfg.get("active_model", "")),
        )

    def _active_scheme(self: "_ChatEngine") -> str:
        """Возвращает схему API активной модели без повторной синхронизации."""
        cfg = self._config
        provider_id = str(cfg.get("active_provider", "deepseek"))
        prov = cfg.get("providers", {}).get(provider_id)
        if not isinstance(prov, dict):
            return "openai"
        mdef = prov.get("models", {}).get(str(cfg.get("active_model", "")))
        if isinstance(mdef, dict):
            return str(mdef.get("scheme") or prov.get("scheme") or "openai")
        return str(prov.get("scheme") or "openai")

    def _openrouter_vision_map(self: "_ChatEngine") -> dict[str, bool]:
        """Возвращает карту «id модели OpenRouter → поддержка изображений».

        Список моделей OpenRouter публичный (без ключа), поэтому кэшируется
        на _OR_MODELS_TTL секунд. При сетевой ошибке возвращается прежний кэш.
        """
        now = time.time()
        cache = self._or_models_cache
        if cache and now - self._or_models_ts < _OR_MODELS_TTL:
            return cache
        result: dict[str, bool] = {}
        try:
            request = urllib.request.Request(_OR_MODELS_URL, headers=HTTP_HEADERS)
            with urllib.request.urlopen(request, timeout=_OR_MODELS_TIMEOUT) as response:
                payload = json.loads(response.read().decode("utf-8", "replace"))
            for entry in payload.get("data", []):
                if not isinstance(entry, dict):
                    continue
                model_id = str(entry.get("id", ""))
                if not model_id:
                    continue
                value = self._vision_from_entry(entry)
                if value is not None:
                    result[model_id] = value
        except (urllib.error.URLError, TimeoutError, ValueError, OSError) as exc:
            _LOGGER.warning("Не удалось получить список моделей OpenRouter: %s", exc)
            result = cache
        if result:
            self._or_models_cache = result
            self._or_models_ts = now
        return result

    def _provider_models_url(self: "_ChatEngine", provider_id: str, base_url: str) -> str:
        """Собирает URL списка моделей для провайдера."""
        base = base_url.rstrip("/")
        if provider_id == "anthropic":
            return base + "/models?limit=1000"
        if provider_id == "xai":
            return base + "/language-models"
        return base + "/models"

    @staticmethod
    def _vision_from_entry(entry: dict[str, Any]) -> bool | None:
        """Извлекает признак «модель принимает изображения и отвечает текстом».

        Нам нужна модель, которая получает на вход текст и изображение, а на
        выходе даёт текст (дополнительно может отдавать изображения — это
        неважно). Поддерживаются форматы: ``architecture.input/output_modalities``
        (OpenRouter), ``input/output_modalities`` (xAI), ``capabilities.vision``
        (Mistral, Cerebras) и ``capabilities.image_input.supported`` (Anthropic).
        """
        arch = entry.get("architecture")
        inputs = arch.get("input_modalities") if isinstance(arch, dict) else None
        outputs = arch.get("output_modalities") if isinstance(arch, dict) else None
        if not isinstance(inputs, list):
            inputs = entry.get("input_modalities")
        if not isinstance(outputs, list):
            outputs = entry.get("output_modalities")
        if isinstance(inputs, list):
            if "image" not in inputs or "text" not in inputs:
                return False
            if isinstance(outputs, list) and "text" not in outputs:
                return False
            return True
        caps = entry.get("capabilities")
        if isinstance(caps, dict):
            image_input = caps.get("image_input")
            if isinstance(image_input, dict) and isinstance(image_input.get("supported"), bool):
                return image_input["supported"]
            vision = caps.get("vision")
            if isinstance(vision, bool):
                return vision
        return None

    def _provider_vision_map(self: "_ChatEngine", provider_id: str) -> dict[str, bool]:
        """Возвращает карту «id модели → поддержка изображений» для провайдера.

        Результат кэшируется на _VISION_CACHE_TTL секунд. При сетевой ошибке
        возвращается прежний кэш (если он был).
        """
        now = time.time()
        cached = self._vision_cache.get(provider_id)
        if cached and now - cached[0] < _VISION_CACHE_TTL:
            return cached[1]
        prov = self._config.get("providers", {}).get(provider_id)
        if not isinstance(prov, dict):
            return {}
        base_url = str(prov.get("base_url", "")).strip()
        if not base_url:
            return {}
        api_key = str(prov.get("api_key", "")).strip()
        headers = dict(HTTP_HEADERS)
        if api_key:
            if provider_id == "anthropic":
                headers["x-api-key"] = api_key
                headers["anthropic-version"] = _ANTHROPIC_VERSION
            else:
                headers["Authorization"] = "Bearer " + api_key
        url = self._provider_models_url(provider_id, base_url)
        result: dict[str, bool] = {}
        try:
            request = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(request, timeout=_VISION_TIMEOUT) as response:
                payload = json.loads(response.read().decode("utf-8", "replace"))
            result = self._parse_vision_payload(payload)
        except (urllib.error.URLError, TimeoutError, ValueError, OSError) as exc:
            _LOGGER.warning("Не удалось получить зрение моделей %s: %s", provider_id, exc)
            result = cached[1] if cached else {}
        if result:
            self._vision_cache[provider_id] = (now, result)
        return result

    def _parse_vision_payload(self: "_ChatEngine", payload: Any) -> dict[str, bool]:
        """Разбирает ответ провайдера в карту «id модели → зрение»."""
        if not isinstance(payload, dict):
            return {}
        items = payload.get("data")
        if not isinstance(items, list):
            items = payload.get("models")
        if not isinstance(items, list):
            return {}
        result: dict[str, bool] = {}
        for entry in items:
            if not isinstance(entry, dict):
                continue
            model_id = str(entry.get("id") or entry.get("name") or "")
            value = self._vision_from_entry(entry)
            if model_id and value is not None:
                result[model_id] = value
        return result

    def _refresh_provider_vision(self: "_ChatEngine", provider_id: str) -> None:
        """Фоновое уточнение зрения моделей провайдера и сохранение в конфиг."""
        if provider_id == "openrouter":
            mapping = self._openrouter_vision_map()
        else:
            mapping = self._provider_vision_map(provider_id)
        if not mapping:
            return
        prov = self._config.get("providers", {}).get(provider_id)
        if not isinstance(prov, dict):
            return
        changed = False
        for mid, mdef in prov.get("models", {}).items():
            if not isinstance(mdef, dict) or mdef.get("vision_source") == "manual":
                continue
            value = mapping.get(mid)
            if value is None:
                continue
            mdef["vision"] = bool(value)
            # Значение подтверждено провайдером.
            mdef["vision_source"] = "provider"
            changed = True
        if changed:
            self._persist_config()
            self._send_state()

    def _refresh_all_vision(self: "_ChatEngine") -> None:
        """Уточняет зрение для всех провайдеров с машинно-читаемым признаком."""
        providers = self._config.get("providers", {})
        for provider_id in _VISION_API_PROVIDERS:
            prov = providers.get(provider_id)
            if not isinstance(prov, dict):
                continue
            # OpenRouter отдаёт список публично; остальным нужен ключ.
            if provider_id != "openrouter" and not str(prov.get("api_key", "")).strip():
                continue
            self._refresh_provider_vision(provider_id)

    def _schedule_vision_refresh(self: "_ChatEngine") -> None:
        """Запускает фоновое уточнение зрения после смены ключей или моделей.

        Обычно зрение определяется один раз при старте UI, поэтому без этого
        вызова ключ, добавленный в текущей сессии, не влиял бы на значки до
        перезапуска плагина.
        """
        if self._post_sink is None:
            return
        threading.Thread(target=self._refresh_all_vision, daemon=True).start()

    def _resolve_vision_for(self: "_ChatEngine", provider_id: str, model_id: str) -> bool | None:
        """Пытается определить поддержку изображений через API провайдера.

        Возвращает True/False, если провайдер отдаёт сведения о модальностях
        модели, иначе None.
        """
        if provider_id == "openrouter":
            return self._openrouter_vision_map().get(model_id)
        if provider_id in _VISION_API_PROVIDERS:
            return self._provider_vision_map(provider_id).get(model_id)
        return None

    def _model_supports_images(self: "_ChatEngine") -> bool | None:
        """Определяет поддержку изображений активной моделью.

        Возвращает True/False, если поддержку удалось определить, иначе None
        (неизвестно — изображения разрешены, решение остаётся за провайдером).
        """
        provider_id, _base_url, _api_key, model, _scheme = self._active_api_credentials()
        if provider_id == "openrouter":
            return self._openrouter_vision_map().get(model)
        prov = self._config.get("providers", {}).get(provider_id)
        if not isinstance(prov, dict):
            return None
        mdef = prov.get("models", {}).get(model)
        if not isinstance(mdef, dict):
            return None
        vision = mdef.get("vision")
        if vision is None:
            vision = prov.get("vision")
        return bool(vision) if vision is not None else None

    def _active_model_id(self: "_ChatEngine") -> str:
        """Возвращает идентификатор активной модели."""
        return str(self._config.get("active_model", ""))

    def _call_api(
        self: "_ChatEngine", messages: list[dict[str, Any]], chat_id: int
    ) -> tuple[str, str]:
        """Выполняет запрос к API и возвращает (текст ответа, размышления)."""
        self._sync_config()
        provider_id, base_url, api_key, model, scheme = self._active_api_credentials()
        if not api_key:
            raise ApiError(self._t("err.api_key_required"))
        cfg = self._config
        # Per-model настройки: None → наследуем глобальные значения.
        prov = cfg.get("providers", {}).get(provider_id)
        mdef = prov.get("models", {}).get(model) if isinstance(prov, dict) else {}
        temperature = mdef.get("temperature")
        if temperature is None:
            temperature = float(cfg.get("temperature", 0.7))
        max_tokens = mdef.get("max_tokens")
        if max_tokens is None:
            max_tokens = int(cfg.get("max_tokens", 4096))
        reasoning = mdef.get("reasoning")
        if reasoning is None:
            reasoning = bool(cfg.get("reasoning", False))
        if scheme == "anthropic":
            return self._call_anthropic(
                messages,
                chat_id,
                base_url,
                api_key,
                model,
                temperature,
                max_tokens,
                reasoning,
            )
        url = base_url.rstrip("/") + "/chat/completions"
        payload: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "stream": True,
            "max_tokens": max_tokens,
        }
        # Reasoning-модели (GPT-5/o-серия) не принимают temperature.
        if not reasoning:
            payload["temperature"] = temperature
        if reasoning:
            if provider_id == "openrouter":
                payload["reasoning"] = {"effort": "high"}
            elif provider_id == "openai":
                payload["reasoning_effort"] = "high"
        request = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={**HTTP_HEADERS, "Authorization": "Bearer " + api_key},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=TIMEOUT) as resp:
                return self._read_sse(resp, chat_id)
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")[:500]
            raise ApiError(
                self._t("err.api", code=str(exc.code), body=body)
            ) from exc
        except urllib.error.URLError as exc:
            raise NetworkError(self._t("err.network", err=str(exc.reason))) from exc
        except TimeoutError as exc:
            raise NetworkError(self._t("err.timeout")) from exc
        except PermissionError as exc:
            raise NetworkError(self._t("err.sandbox")) from exc
        except OSError as exc:
            raise NetworkError(self._t("err.connection", err=str(exc))) from exc

    def _call_anthropic(
        self: "_ChatEngine",
        messages: list[dict[str, Any]],
        chat_id: int,
        base_url: str,
        api_key: str,
        model: str,
        temperature: float,
        max_tokens: int,
        reasoning: bool,
    ) -> tuple[str, str]:
        """Выполняет запрос к нативному Messages API Anthropic.

        Возвращает пару (текст ответа, размышления).
        """
        system = ""
        body_messages = messages
        if messages and messages[0].get("role") == "system":
            system = str(messages[0].get("content", ""))
            body_messages = messages[1:]
        url = base_url.rstrip("/") + "/messages"
        payload: dict[str, Any] = {
            "model": model,
            "max_tokens": max_tokens,
            "system": system,
            "messages": body_messages,
            "stream": True,
        }
        if reasoning:
            budget = min(4096, max(1024, max_tokens // 2))
            payload["thinking"] = {"type": "enabled", "budget_tokens": budget}
        else:
            payload["temperature"] = temperature
        headers = {
            "Content-Type": "application/json",
            "User-Agent": "OrcaSlicer/2.5.0",
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
        }
        request = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers=headers,
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=TIMEOUT) as resp:
                return self._read_sse_anthropic(resp, chat_id)
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")[:500]
            raise ApiError(
                self._t("err.api", code=str(exc.code), body=body)
            ) from exc
        except urllib.error.URLError as exc:
            raise NetworkError(self._t("err.network", err=str(exc.reason))) from exc
        except TimeoutError as exc:
            raise NetworkError(self._t("err.timeout")) from exc
        except PermissionError as exc:
            raise NetworkError(self._t("err.sandbox")) from exc
        except OSError as exc:
            raise NetworkError(self._t("err.connection", err=str(exc))) from exc

    def _read_sse(self: "_ChatEngine", resp: Any, chat_id: int) -> tuple[str, str]:
        """Читает SSE-поток ответа и отправляет инкрементальные куски в UI.

        Возвращает пару (текст ответа, накопленные размышления), чтобы движок
        мог сохранить reasoning_content отдельно от ответа.
        """
        acc = ""
        thought = ""
        sent = 0
        sent_thought = 0
        last_post = 0.0
        for raw in resp:
            if not self._gen:
                break
            line = raw.decode("utf-8", errors="replace").strip()
            if not line.startswith("data:"):
                continue
            data = line[5:].strip()
            if data == "[DONE]":
                break
            try:
                chunk = json.loads(data)
                delta_obj = chunk["choices"][0].get("delta") or {}
                delta = delta_obj.get("content") or ""
                reasoning_delta = delta_obj.get("reasoning_content") or ""
            except (ValueError, KeyError, IndexError, TypeError, AttributeError):
                continue
            if reasoning_delta:
                thought += reasoning_delta
            if delta:
                acc += delta
            if not (reasoning_delta or delta):
                continue
            now = time.monotonic()
            if now - last_post < STREAM_THROTTLE:
                continue
            # Отправляем ВСЁ накопленное с прошлой отправки, а не только текущую
            # дельту: иначе UI теряет пропущенные куски и «досыпает» их в конце.
            if len(thought) > sent_thought:
                self._post(
                    {
                        "type": "thought_delta",
                        "chat_id": chat_id,
                        "text": thought[sent_thought:],
                    }
                )
                sent_thought = len(thought)
            if len(acc) > sent:
                self._post({"type": "delta", "chat_id": chat_id, "text": acc[sent:]})
                sent = len(acc)
            last_post = now
        if len(thought) > sent_thought:
            self._post(
                {
                    "type": "thought_delta",
                    "chat_id": chat_id,
                    "text": thought[sent_thought:],
                }
            )
        if len(acc) > sent:
            self._post({"type": "delta", "chat_id": chat_id, "text": acc[sent:]})
        return acc, thought

    def _read_sse_anthropic(self: "_ChatEngine", resp: Any, chat_id: int) -> tuple[str, str]:
        """Читает SSE-поток Messages API Anthropic и стримит текст в UI.

        Возвращает пару (текст ответа, размышления) с учётом thinking_delta.
        """
        acc = ""
        thought = ""
        sent = 0
        sent_thought = 0
        last_post = 0.0
        for raw in resp:
            if not self._gen:
                break
            line = raw.decode("utf-8", errors="replace").strip()
            if not line.startswith("data:"):
                continue
            data = line[5:].strip()
            if not data:
                continue
            try:
                event = json.loads(data)
            except ValueError:
                continue
            if event.get("type") != "content_block_delta":
                continue
            delta = event.get("delta") or {}
            if delta.get("type") == "thinking_delta":
                text = delta.get("thinking") or ""
                is_thought = True
            else:
                text = delta.get("text") or ""
                is_thought = False
            if not text:
                continue
            if is_thought:
                thought += text
            else:
                acc += text
            now = time.monotonic()
            if now - last_post < STREAM_THROTTLE:
                continue
            # См. _read_sse: отправляем всё накопленное, чтобы не терять куски.
            if len(thought) > sent_thought:
                self._post(
                    {
                        "type": "thought_delta",
                        "chat_id": chat_id,
                        "text": thought[sent_thought:],
                    }
                )
                sent_thought = len(thought)
            if len(acc) > sent:
                self._post({"type": "delta", "chat_id": chat_id, "text": acc[sent:]})
                sent = len(acc)
            last_post = now
        if len(thought) > sent_thought:
            self._post(
                {
                    "type": "thought_delta",
                    "chat_id": chat_id,
                    "text": thought[sent_thought:],
                }
            )
        if len(acc) > sent:
            self._post({"type": "delta", "chat_id": chat_id, "text": acc[sent:]})
        return acc, thought

    def _test_key_worker(
        self: "_ChatEngine", key: str | None = None, provider_id: str | None = None
    ) -> None:
        """Проверяет API-ключ фоновым запросом к провайдеру.

        Если передан непустой ключ, он имеет приоритет над сохранённым.
        Если передан provider_id, проверяется именно он (а не активный
        провайдер) — иначе ключ из формы уходил бы на чужой эндпоинт.
        """
        self._sync_config()
        cfg = self._config
        if not provider_id or provider_id not in cfg.get("providers", {}):
            provider_id = str(cfg.get("active_provider", "deepseek"))
        active_provider = str(cfg.get("active_provider", ""))
        if provider_id == active_provider:
            model = str(cfg.get("active_model", ""))
        else:
            # Для неактивного провайдера берём его первую модель.
            prov = cfg.get("providers", {}).get(provider_id)
            models = prov.get("models", {}) if isinstance(prov, dict) else {}
            model = str(next(iter(models), "")) if isinstance(models, dict) else ""
        _, base_url, api_key, model, scheme = self._api_credentials_for(
            provider_id, model
        )
        if key and key.strip():
            api_key = key.strip()
        if not api_key:
            self._post(
                {"type": "key_test", "ok": False, "text": self._t("key.missing")}
            )
            return
        if not base_url:
            self._post(
                {
                    "type": "key_test",
                    "ok": False,
                    "text": self._t("key.network_error", err="base_url не задан"),
                }
            )
            return
        if scheme == "anthropic":
            url = base_url.rstrip("/") + "/messages"
            payload = {
                "model": model,
                "max_tokens": 1,
                "messages": [{"role": "user", "content": "ping"}],
                "stream": False,
            }
            headers = {
                "Content-Type": "application/json",
                "User-Agent": "OrcaSlicer/2.5.0",
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
            }
        else:
            url = base_url.rstrip("/") + "/chat/completions"
            payload = {
                "model": model,
                "messages": [{"role": "user", "content": "ping"}],
                "max_tokens": 1,
                "stream": False,
            }
            headers = {**HTTP_HEADERS, "Authorization": "Bearer " + api_key}
        request = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers=headers,
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=30) as resp:
                resp.read()
            self._post({"type": "key_test", "ok": True, "text": self._t("key.valid")})
        except urllib.error.HTTPError as exc:
            text = self._t("key.api_error", code=str(exc.code))
            detail = self._http_error_detail(exc)
            if detail:
                text = text + " " + detail
            self._post({"type": "key_test", "ok": False, "text": text})
        except OSError as exc:
            self._post(
                {
                    "type": "key_test",
                    "ok": False,
                    "text": self._t("key.network_error", err=str(exc)),
                }
            )

    @staticmethod
    def _http_error_detail(exc: urllib.error.HTTPError) -> str:
        """Извлекает текст ошибки из тела HTTP-ответа для показа в UI."""
        try:
            raw = exc.read().decode("utf-8", "replace")
        except OSError:
            return ""
        raw = raw.strip()[:300]
        if not raw:
            return ""
        try:
            data = json.loads(raw)
        except (ValueError, TypeError):
            return raw
        if isinstance(data, dict):
            error = data.get("error")
            if isinstance(error, dict) and error.get("message"):
                return str(error["message"])[:300]
            if isinstance(error, str) and error:
                return error[:300]
            if data.get("detail"):
                return str(data["detail"])[:300]
        return raw
