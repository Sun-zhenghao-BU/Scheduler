from __future__ import annotations

import json
from pathlib import Path
from typing import Any

CONFIG_PATH = Path.home() / ".scheduler" / "llm_config.json"
ROLE_KEYS = ("product_manager", "developer", "tester", "codegen")
DEFAULT_TIMEOUT_SECONDS = {
    "default": 180,
    "product_manager": 120,
    "developer": 300,
    "tester": 180,
    "codegen": 300,
}


def get_llm_config() -> dict[str, str]:
    defaults = {
        "api_key": "",
        "base_url": "https://api.openai.com/v1",
        "model": "gpt-4",
        "product_manager_model": "",
        "developer_model": "",
        "tester_model": "",
        "codegen_model": "",
        "product_manager_timeout": str(DEFAULT_TIMEOUT_SECONDS["product_manager"]),
        "developer_timeout": str(DEFAULT_TIMEOUT_SECONDS["developer"]),
        "tester_timeout": str(DEFAULT_TIMEOUT_SECONDS["tester"]),
        "codegen_timeout": str(DEFAULT_TIMEOUT_SECONDS["codegen"]),
    }
    if CONFIG_PATH.exists():
        data = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        merged = {**defaults}
        for key in merged:
            if key in data:
                merged[key] = str(data.get(key, merged[key]))
        return merged
    return defaults


def save_llm_config(config: dict[str, str]) -> None:
    existing = get_llm_config()
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    payload = {**existing, **config}
    if not payload.get("api_key"):
        payload["api_key"] = existing.get("api_key", "")
    CONFIG_PATH.write_text(
        json.dumps(payload, indent=2),
        encoding="utf-8",
    )


def get_llm_profile(role: str, config: dict[str, str] | None = None) -> dict[str, str | int]:
    resolved = config or get_llm_config()
    model = resolved.get(f"{role}_model", "").strip() or resolved.get("model", "gpt-4")
    timeout_value = resolved.get(f"{role}_timeout", str(DEFAULT_TIMEOUT_SECONDS.get(role, DEFAULT_TIMEOUT_SECONDS["default"])))
    try:
        timeout_seconds = int(timeout_value)
    except (TypeError, ValueError):
        timeout_seconds = DEFAULT_TIMEOUT_SECONDS.get(role, DEFAULT_TIMEOUT_SECONDS["default"])
    return {
        "api_key": resolved.get("api_key", ""),
        "base_url": resolved.get("base_url", "https://api.openai.com/v1"),
        "model": model,
        "timeout_seconds": timeout_seconds,
    }


class LLMClient:
    def __init__(self, config: dict[str, str | int] | None = None):
        self.config = config or get_llm_config()
        self._client: Any | None = None
        self._timeout_seconds = int(self.config.get("timeout_seconds", DEFAULT_TIMEOUT_SECONDS["default"]))

    def _get_client(self) -> Any:
        if self._client is None:
            from openai import AsyncOpenAI

            self._client = AsyncOpenAI(
                api_key=self.config["api_key"],
                base_url=self.config["base_url"],
                timeout=self._timeout_seconds,
            )
        return self._client

    async def chat(self, messages: list[dict[str, str]], stream: bool = False):
        client = self._get_client()
        response = await client.chat.completions.create(
            model=self.config["model"],
            messages=messages,
            stream=stream,
            temperature=0.7,
            timeout=self._timeout_seconds,
        )
        if stream:
            return response
        return response.choices[0].message.content

    async def chat_stream(self, messages: list[dict[str, str]]):
        client = self._get_client()
        async for chunk in await client.chat.completions.create(
            model=self.config["model"],
            messages=messages,
            stream=True,
            temperature=0.7,
            timeout=self._timeout_seconds,
        ):
            if chunk.choices and chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content

    def validate_config(self) -> tuple[bool, str]:
        if not self.config.get("api_key"):
            return False, "请先填写 API 密钥"
        return True, "配置可用"
