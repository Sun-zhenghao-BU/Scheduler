from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from scheduler_automation.llm.client import LLMClient, get_llm_config, save_llm_config

router = APIRouter(prefix="/api/llm", tags=["llm"])


class ConfigRequest(BaseModel):
    api_key: str
    base_url: str
    model: str


class ConfigResponse(BaseModel):
    base_url: str
    model: str
    has_api_key: bool


@router.get("/config", response_model=ConfigResponse)
def get_config():
    config = get_llm_config()
    return ConfigResponse(
        base_url=config["base_url"],
        model=config["model"],
        has_api_key=bool(config["api_key"]),
    )


@router.post("/config")
def update_config(req: ConfigRequest):
    save_llm_config(req.api_key, req.base_url, req.model)
    return {"status": "ok"}


@router.post("/validate")
async def validate_config():
    config = get_llm_config()
    client = LLMClient(config)
    ok, msg = client.validate_config()
    if not ok:
        return {"valid": False, "message": msg}

    try:
        messages = [
            {"role": "system", "content": "Reply with just 'OK'."},
            {"role": "user", "content": "test"},
        ]
        await client.chat(messages)
        return {"valid": True, "message": "连接测试成功"}
    except Exception as exc:
        return {"valid": False, "message": str(exc)}
