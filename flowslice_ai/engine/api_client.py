# pyright: ignore[reportGeneralTypeIssues]
"""HTTP-клиент и SSE-стриминг движка FlowSlice AI.

Миксин ApiClientMixin выполняет запросы к API провайдеров (OpenAI-совместимые
и нативный Messages API Anthropic), читает SSE-потоки и проверяет API-ключи.
"""
# pylint: disable=too-many-lines,too-many-statements,too-many-branches
# pylint: disable=too-many-locals,too-many-arguments,too-many-positional-arguments
# pylint: disable=too-many-public-methods,too-few-public-methods

import json
import time
from typing import TYPE_CHECKING, Any
import urllib.error
import urllib.request

if TYPE_CHECKING:
    from flowslice_ai.engine import _ChatEngine

from flowslice_ai.constants import HTTP_HEADERS, STREAM_THROTTLE, TIMEOUT
from flowslice_ai.errors import ApiError, NetworkError


class ApiClientMixin:
    """Запросы к API провайдеров, чтение SSE-потоков, проверка ключей."""

    def _active_api_credentials(self: "_ChatEngine") -> tuple[str, str, str, str, str]:
        """Возвращает (provider_id, base_url, api_key, model, scheme).

        Учитывает переопределение base_url/api_key на уровне выбранной модели.
        Схема API: per-model, затем провайдер, затем "openai".
        """
        cfg = self._config
        provider_id = str(cfg.get("active_provider", "deepseek"))
        providers = cfg.get("providers", {})
        prov = providers.get(provider_id)
        if not isinstance(prov, dict):
            prov = {}
        base_url = str(prov.get("base_url", ""))
        api_key = str(prov.get("api_key", ""))
        model = str(cfg.get("active_model", ""))
        mdef = prov.get("models", {}).get(model)
        if isinstance(mdef, dict):
            if mdef.get("base_url"):
                base_url = str(mdef["base_url"])
            if mdef.get("api_key"):
                api_key = str(mdef["api_key"])
        scheme = str(mdef.get("scheme") or prov.get("scheme") or "openai")
        return provider_id, base_url, api_key, model, scheme

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

    def _call_api(self: "_ChatEngine", messages: list[dict[str, Any]], chat_id: int) -> str:
        """Выполняет запрос к API провайдера и возвращает полный текст ответа."""
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
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
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
    ) -> str:
        """Выполняет запрос к нативному Messages API Anthropic."""
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
            "temperature": temperature,
            "stream": True,
        }
        if reasoning:
            budget = min(4096, max(1024, max_tokens // 2))
            payload["thinking"] = {"type": "enabled", "budget_tokens": budget}
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

    def _read_sse(self: "_ChatEngine", resp: Any, chat_id: int) -> str:
        """Читает SSE-поток ответа и отправляет инкрементальные куски в UI."""
        acc = ""
        sent = ""
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
                delta = chunk["choices"][0]["delta"].get("content", "")
            except (ValueError, KeyError, IndexError, TypeError):
                continue
            if not delta:
                continue
            acc += delta
            now = time.monotonic()
            if now - last_post >= STREAM_THROTTLE:
                self._post({"type": "delta", "chat_id": chat_id, "text": delta})
                last_post = now
                sent += delta
        if acc and sent != acc:
            self._post({"type": "delta", "chat_id": chat_id, "text": acc[len(sent) :]})
        return acc

    def _read_sse_anthropic(self: "_ChatEngine", resp: Any, chat_id: int) -> str:
        """Читает SSE-поток Messages API Anthropic и стримит текст в UI."""
        acc = ""
        sent = ""
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
            delta = event.get("delta", {})
            text = delta.get("text", "")
            if not text:
                continue
            acc += text
            now = time.monotonic()
            if now - last_post >= STREAM_THROTTLE:
                self._post({"type": "delta", "chat_id": chat_id, "text": text})
                last_post = now
                sent += text
        if acc and sent != acc:
            self._post({"type": "delta", "chat_id": chat_id, "text": acc[len(sent) :]})
        return acc

    def _test_key_worker(self: "_ChatEngine", key: str | None = None) -> None:
        """Проверяет API-ключ фоновым запросом к провайдеру.

        Если передан непустой ключ, он имеет приоритет над сохранённым.
        """
        self._sync_config()
        _, base_url, api_key, model, scheme = self._active_api_credentials()
        if key and key.strip():
            api_key = key.strip()
        if not api_key:
            self._post(
                {"type": "key_test", "ok": False, "text": self._t("key.missing")}
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
            self._post(
                {
                    "type": "key_test",
                    "ok": False,
                    "text": self._t("key.api_error", code=str(exc.code)),
                }
            )
        except OSError as exc:
            self._post(
                {
                    "type": "key_test",
                    "ok": False,
                    "text": self._t("key.network_error", err=str(exc)),
                }
            )
