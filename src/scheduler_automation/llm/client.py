from __future__ import annotations

import json
from pathlib import Path
from typing import Any

CONFIG_PATH = Path.home() / ".scheduler" / "llm_config.json"


def get_llm_config() -> dict[str, str]:
    """Load LLM config from user config file."""
    if CONFIG_PATH.exists():
        data = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        return {
            "api_key": data.get("api_key", ""),
            "base_url": data.get("base_url", "https://api.openai.com/v1"),
            "model": data.get("model", "gpt-4"),
        }
    return {
        "api_key": "",
        "base_url": "https://api.openai.com/v1",
        "model": "gpt-4",
    }


def save_llm_config(api_key: str, base_url: str, model: str) -> None:
    existing_api_key = ""
    if CONFIG_PATH.exists():
        existing_api_key = get_llm_config().get("api_key", "")
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    CONFIG_PATH.write_text(
        json.dumps({"api_key": api_key or existing_api_key, "base_url": base_url, "model": model}, indent=2),
        encoding="utf-8",
    )


class LLMClient:
    """Unified LLM client using openai-compatible API."""

    def __init__(self, config: dict[str, str] | None = None):
        self.config = config or get_llm_config()
        self._client: Any | None = None

    def _get_client(self) -> Any:
        if self._client is None:
            from openai import AsyncOpenAI
            self._client = AsyncOpenAI(
                api_key=self.config["api_key"],
                base_url=self.config["base_url"],
            )
        return self._client

    async def chat(self, messages: list[dict[str, str]], stream: bool = False):
        """Send chat messages and return response."""
        client = self._get_client()
        response = await client.chat.completions.create(
            model=self.config["model"],
            messages=messages,
            stream=stream,
            temperature=0.7,
        )
        if stream:
            return response  # async generator
        return response.choices[0].message.content

    async def chat_stream(self, messages: list[dict[str, str]]):
        """Stream chat responses."""
        client = self._get_client()
        async for chunk in await client.chat.completions.create(
            model=self.config["model"],
            messages=messages,
            stream=True,
            temperature=0.7,
        ):
            if chunk.choices and chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content

    def validate_config(self) -> tuple[bool, str]:
        if not self.config.get("api_key"):
            return False, "请先填写 API 密钥"
        return True, "配置可用"
