import os

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.llm import DEFAULT_BASE_URL, DEFAULT_MODEL, load_local_env, model_configured

router = APIRouter(prefix="/api/models", tags=["models"])


class ModelTestRequest(BaseModel):
    model_id: str = Field(min_length=1)


@router.get("")
def list_models() -> dict[str, list[dict[str, object]]]:
    load_local_env()
    return {
        "models": [
            {
                "model_id": os.getenv("OPENAI_COMPATIBLE_MODEL", DEFAULT_MODEL),
                "provider": "openai-compatible",
                "base_url": os.getenv("OPENAI_COMPATIBLE_BASE_URL", DEFAULT_BASE_URL),
                "configured": model_configured(),
                "capabilities": ["chat", "streaming", "tool_calling"],
            }
        ]
    }


@router.post("/test")
def test_model(body: ModelTestRequest) -> dict[str, str]:
    load_local_env()
    return {
        "model_id": body.model_id,
        "status": "configured" if model_configured() else "not_configured",
    }
