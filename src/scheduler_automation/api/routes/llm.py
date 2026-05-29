from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from scheduler_automation.llm.client import LLMClient, get_llm_config, get_llm_profile, save_llm_config

router = APIRouter(prefix="/api/llm", tags=["llm"])


class ConfigRequest(BaseModel):
    api_key: str = ""
    base_url: str
    model: str
    product_manager_model: str = ""
    developer_model: str = ""
    tester_model: str = ""
    codegen_model: str = ""
    product_manager_timeout: int = 120
    developer_timeout: int = 300
    tester_timeout: int = 180
    codegen_timeout: int = 300


class ConfigResponse(BaseModel):
    base_url: str
    model: str
    product_manager_model: str
    developer_model: str
    tester_model: str
    codegen_model: str
    product_manager_timeout: int
    developer_timeout: int
    tester_timeout: int
    codegen_timeout: int
    has_api_key: bool


@router.get("/config", response_model=ConfigResponse)
def get_config():
    config = get_llm_config()
    return ConfigResponse(
        base_url=config["base_url"],
        model=config["model"],
        product_manager_model=config["product_manager_model"],
        developer_model=config["developer_model"],
        tester_model=config["tester_model"],
        codegen_model=config["codegen_model"],
        product_manager_timeout=int(config["product_manager_timeout"]),
        developer_timeout=int(config["developer_timeout"]),
        tester_timeout=int(config["tester_timeout"]),
        codegen_timeout=int(config["codegen_timeout"]),
        has_api_key=bool(config["api_key"]),
    )


@router.post("/config")
def update_config(req: ConfigRequest):
    save_llm_config(
        {
            "api_key": req.api_key,
            "base_url": req.base_url,
            "model": req.model,
            "product_manager_model": req.product_manager_model,
            "developer_model": req.developer_model,
            "tester_model": req.tester_model,
            "codegen_model": req.codegen_model,
            "product_manager_timeout": str(req.product_manager_timeout),
            "developer_timeout": str(req.developer_timeout),
            "tester_timeout": str(req.tester_timeout),
            "codegen_timeout": str(req.codegen_timeout),
        }
    )
    return {"status": "ok"}


@router.post("/validate")
async def validate_config():
    profile = get_llm_profile("product_manager")
    client = LLMClient(profile)
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
