from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

router = APIRouter(prefix="/api/ask-data", tags=["ask-data"])


class AskDataRequest(BaseModel):
    tenant_id: str = Field(min_length=1)
    workspace_id: str = Field(min_length=1)
    thread_id: str = Field(min_length=1)
    user_id: str = Field(min_length=1)
    question: str = Field(min_length=1)
    capability: str = Field(min_length=1)


@router.post("/query")
def query(body: AskDataRequest) -> dict[str, object]:
    _ = body
    raise HTTPException(status_code=501, detail="业务插件将在二阶段启用；一阶段不会返回模拟问数结果。")
