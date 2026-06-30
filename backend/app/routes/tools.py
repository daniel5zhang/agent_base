import json
import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.db import get_session
from app.models import Artifact, AuditEvent, Run, ToolInvocation
from app.repositories import append_runtime_event

router = APIRouter(prefix="/api/tools", tags=["tools"])


class ToolInvokeRequest(BaseModel):
    tenant_id: str = Field(min_length=1)
    workspace_id: str = Field(min_length=1)
    thread_id: str = Field(min_length=1)
    user_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    input: dict[str, Any] = Field(default_factory=dict)


@router.post("/{tool_id}/invoke")
def invoke_tool(tool_id: str, body: ToolInvokeRequest, session: Session = Depends(get_session)) -> dict[str, object]:
    if tool_id != "plan.update":
        raise HTTPException(status_code=404, detail="tool not found")

    run = session.get(Run, body.run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="run not found")

    append_runtime_event(
        session,
        tenant_id=body.tenant_id,
        workspace_id=body.workspace_id,
        thread_id=body.thread_id,
        run_id=body.run_id,
        event_type="tool.started",
        actor=body.user_id,
        payload={"tool_id": tool_id},
        idempotency_key=f"{body.run_id}:tool.started:{tool_id}",
    )

    artifact_id = f"art_{uuid.uuid4().hex}"
    artifact_content = {
        "steps": [
            "通用对话",
            "模型配置",
            "内置工具调用",
            "Runtime Event 与 Artifact 验证",
        ],
        "goal": body.input.get("goal", ""),
    }
    artifact = Artifact(
        artifact_id=artifact_id,
        tenant_id=body.tenant_id,
        workspace_id=body.workspace_id,
        thread_id=body.thread_id,
        run_id=body.run_id,
        artifact_type="plan",
        title="一阶段验收计划",
        content_json=json.dumps(artifact_content, ensure_ascii=False),
    )
    session.add(artifact)

    invocation = ToolInvocation(
        invocation_id=f"toolinv_{uuid.uuid4().hex}",
        tenant_id=body.tenant_id,
        workspace_id=body.workspace_id,
        thread_id=body.thread_id,
        run_id=body.run_id,
        tool_id=tool_id,
        status="completed",
        input_json=json.dumps(body.input, ensure_ascii=False),
        output_json=json.dumps({"artifact_id": artifact_id}, ensure_ascii=False),
    )
    session.add(invocation)
    session.commit()

    completed_event = append_runtime_event(
        session,
        tenant_id=body.tenant_id,
        workspace_id=body.workspace_id,
        thread_id=body.thread_id,
        run_id=body.run_id,
        event_type="tool.completed",
        actor=body.user_id,
        payload={"tool_id": tool_id, "artifact_id": artifact_id},
        idempotency_key=f"{body.run_id}:tool.completed:{tool_id}",
    )
    artifact_event = append_runtime_event(
        session,
        tenant_id=body.tenant_id,
        workspace_id=body.workspace_id,
        thread_id=body.thread_id,
        run_id=body.run_id,
        event_type="artifact.created",
        actor=body.user_id,
        payload={"artifact_id": artifact_id, "artifact_type": "plan"},
        idempotency_key=f"{body.run_id}:artifact.created:{artifact_id}",
    )
    artifact.source_event_id = artifact_event.event_id
    run.status = "completed"
    session.add(
        AuditEvent(
            audit_event_id=artifact_event.event_id,
            tenant_id=body.tenant_id,
            run_id=body.run_id,
            event_type="phase_one.tool.completed",
            payload_json=json.dumps({"tool_id": tool_id, "artifact_id": artifact_id}, ensure_ascii=False),
        )
    )
    session.commit()

    append_runtime_event(
        session,
        tenant_id=body.tenant_id,
        workspace_id=body.workspace_id,
        thread_id=body.thread_id,
        run_id=body.run_id,
        event_type="run.completed",
        actor=body.user_id,
        payload={"status": "completed"},
        idempotency_key=f"{body.run_id}:run.completed",
    )

    return {
        "status": "completed",
        "tool_id": tool_id,
        "artifact": {
            "artifact_id": artifact_id,
            "title": artifact.title,
            "artifact_type": artifact.artifact_type,
        },
        "audit_event_id": completed_event.event_id,
    }
