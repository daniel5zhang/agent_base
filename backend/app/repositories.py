import hashlib
import json
import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import RunStep, RuntimeEvent


def json_dump(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def digest_payload(payload: dict[str, Any]) -> str:
    return hashlib.sha256(json_dump(payload).encode("utf-8")).hexdigest()


def append_runtime_event(
    session: Session,
    *,
    tenant_id: str,
    workspace_id: str,
    thread_id: str,
    run_id: str,
    event_type: str,
    actor: str,
    payload: dict[str, Any],
    idempotency_key: str,
) -> RuntimeEvent:
    existing = session.scalar(
        select(RuntimeEvent).where(
            RuntimeEvent.tenant_id == tenant_id,
            RuntimeEvent.idempotency_key == idempotency_key,
        )
    )
    if existing is not None:
        _append_run_step_for_event(session, existing)
        return existing

    previous = session.scalars(
        select(RuntimeEvent)
        .where(RuntimeEvent.tenant_id == tenant_id, RuntimeEvent.run_id == run_id)
        .order_by(RuntimeEvent.occurred_at.desc())
        .limit(1)
    ).first()
    event = RuntimeEvent(
        event_id=f"evt_{uuid.uuid4().hex}",
        tenant_id=tenant_id,
        workspace_id=workspace_id,
        thread_id=thread_id,
        run_id=run_id,
        event_type=event_type,
        actor=actor,
        payload_json=json_dump(payload),
        payload_digest=digest_payload(payload),
        previous_event_digest=previous.payload_digest if previous else None,
        idempotency_key=idempotency_key,
    )
    session.add(event)
    session.commit()
    session.refresh(event)
    _append_run_step_for_event(session, event)
    return event


def _append_run_step_for_event(session: Session, event: RuntimeEvent) -> RunStep | None:
    mapped = _map_event_to_run_step(event)
    if mapped is None:
        return None
    step_id = f"step_{event.event_id.removeprefix('evt_')}"
    existing = session.get(RunStep, step_id)
    if existing is not None:
        return existing
    step = RunStep(
        step_id=step_id,
        run_id=event.run_id,
        step_type=mapped["step_type"],
        status=mapped["status"],
        payload_json=event.payload_json,
    )
    session.add(step)
    session.commit()
    return step


def _map_event_to_run_step(event: RuntimeEvent) -> dict[str, str] | None:
    payload = json.loads(event.payload_json)
    event_type = event.event_type
    if event_type == "run.created":
        return {"step_type": "run", "status": "running"}
    if event_type == "message.received":
        return {"step_type": "message", "status": "completed"}
    if event_type == "intent.classified":
        return {"step_type": "intent", "status": "completed"}
    if event_type == "context.built":
        return {"step_type": "context", "status": "completed"}
    if event_type == "model.selected":
        return {"step_type": "model", "status": "planned"}
    if event_type == "model.started":
        return {"step_type": "model", "status": "running"}
    if event_type == "model.completed":
        return {"step_type": "model", "status": "completed"}
    if event_type == "tool.batch.started":
        batch_index = payload.get("batch_index", "unknown")
        return {"step_type": f"tool_batch:{batch_index}", "status": "running"}
    if event_type == "tool.batch.completed":
        batch_index = payload.get("batch_index", "unknown")
        return {"step_type": f"tool_batch:{batch_index}", "status": str(payload.get("status") or "completed")}
    if event_type.startswith("tool."):
        tool_id = str(payload.get("tool_id") or "unknown")
        if event_type == "tool.planned":
            return {"step_type": f"tool:{tool_id}", "status": "planned"}
        if event_type == "tool.started":
            return {"step_type": f"tool:{tool_id}", "status": "running"}
        if event_type == "tool.completed":
            return {"step_type": f"tool:{tool_id}", "status": "completed"}
        if event_type == "tool.failed":
            return {"step_type": f"tool:{tool_id}", "status": "failed"}
    if event_type in {"artifact.created", "artifact.updated"}:
        artifact_type = str(payload.get("artifact_type") or "artifact")
        return {"step_type": f"artifact:{artifact_type}", "status": "completed"}
    if event_type == "memory.context.loaded":
        return {"step_type": "memory_context", "status": "completed"}
    if event_type == "conversation.context.loaded":
        return {"step_type": "conversation_context", "status": "completed"}
    if event_type == "run.completed":
        return {"step_type": "run", "status": "completed"}
    if event_type == "run.failed":
        return {"step_type": "run", "status": "failed"}
    if event_type == "run.cancelled":
        return {"step_type": "run", "status": "cancelled"}
    return None
