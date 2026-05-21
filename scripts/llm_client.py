from __future__ import annotations

import json
from typing import Any, Protocol
from urllib import error, request

from scripts.config import LlmProviderConfig


class HttpTransport(Protocol):
    def post_json(
        self,
        url: str,
        headers: dict[str, str],
        payload: dict[str, Any],
        timeout: int,
    ) -> dict[str, Any]:
        ...


class UrllibTransport:
    def post_json(
        self,
        url: str,
        headers: dict[str, str],
        payload: dict[str, Any],
        timeout: int,
    ) -> dict[str, Any]:
        body = json.dumps(payload).encode("utf-8")
        req = request.Request(url, data=body, headers=headers, method="POST")
        with request.urlopen(req, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))


class LlmError(RuntimeError):
    pass


class LlmClient:
    def __init__(
        self,
        providers: list[LlmProviderConfig],
        *,
        timeout_seconds: int,
        transport: HttpTransport | None = None,
    ) -> None:
        self.providers = providers
        self.timeout_seconds = timeout_seconds
        self.transport = transport or UrllibTransport()

    def chat(self, messages: list[dict[str, str]]) -> str:
        errors: list[str] = []
        for provider in self.providers:
            if not provider.api_key:
                continue

            url = provider.base_url.rstrip("/") + "/chat/completions"
            payload = {"model": provider.model, "messages": messages, "temperature": 0.1}
            headers = {"Authorization": f"Bearer {provider.api_key}", "Content-Type": "application/json"}
            try:
                data = self.transport.post_json(url, headers, payload, self.timeout_seconds)
                return str(data["choices"][0]["message"]["content"])
            except (KeyError, IndexError, TypeError, error.URLError, TimeoutError, OSError) as exc:
                errors.append(f"{provider.name}: {exc}")

        raise LlmError("所有 LLM providers 均失败：" + "; ".join(errors))
