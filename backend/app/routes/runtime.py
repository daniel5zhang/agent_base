import json
import uuid

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_session
from app.models import Run, RunStep, RuntimeEvent
from app.repositories import append_runtime_event

router = APIRouter(prefix="/api/runs", tags=["runtime"])


class RunCreateRequest(BaseModel):
    tenant_id: str = Field(min_length=1)
    workspace_id: str = Field(min_length=1)
    thread_id: str = Field(min_length=1)
    user_id: str = Field(min_length=1)
    message: str = Field(min_length=1)


class RunCancelRequest(BaseModel):
    user_id: str = Field(min_length=1)
    reason: str = Field(default="user_cancelled")


class RunRetryRequest(BaseModel):
    user_id: str = Field(min_length=1)


@router.post("")
def create_run(body: RunCreateRequest, session: Session = Depends(get_session)) -> dict[str, object]:
    run_id = f"run_{uuid.uuid4().hex}"
    run = Run(
        run_id=run_id,
        tenant_id=body.tenant_id,
        workspace_id=body.workspace_id,
        thread_id=body.thread_id,
        user_id=body.user_id,
        status="created",
        question=body.message,
    )
    session.add(run)
    session.commit()

    append_runtime_event(
        session,
        tenant_id=body.tenant_id,
        workspace_id=body.workspace_id,
        thread_id=body.thread_id,
        run_id=run_id,
        event_type="run.created",
        actor=body.user_id,
        payload={"message": body.message},
        idempotency_key=f"{run_id}:run.created",
    )
    append_runtime_event(
        session,
        tenant_id=body.tenant_id,
        workspace_id=body.workspace_id,
        thread_id=body.thread_id,
        run_id=run_id,
        event_type="intent.classified",
        actor=body.user_id,
        payload={"intent": "plan" if "计划" in body.message or "验收" in body.message else "general_chat"},
        idempotency_key=f"{run_id}:intent.classified",
    )

    return {
        "run_id": run_id,
        "status": run.status,
        "thread_id": run.thread_id,
        "workspace_id": run.workspace_id,
    }


@router.get("/{run_id}")
def get_run(run_id: str, session: Session = Depends(get_session)) -> dict[str, object]:
    run = session.get(Run, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="run not found")
    events = session.scalars(
        select(RuntimeEvent).where(RuntimeEvent.run_id == run_id).order_by(RuntimeEvent.occurred_at.asc())
    ).all()
    steps = session.scalars(select(RunStep).where(RunStep.run_id == run_id)).all()
    return {
        "run_id": run.run_id,
        "status": run.status,
        "question": run.question,
        "steps": [
            {
                "step_id": step.step_id,
                "step_type": step.step_type,
                "status": step.status,
                "payload": json.loads(step.payload_json),
            }
            for step in steps
        ],
        "events": [
            {
                "event_id": event.event_id,
                "event_type": event.event_type,
                "payload_digest": event.payload_digest,
            }
            for event in events
        ],
    }


@router.get("/{run_id}/events")
def get_run_events(run_id: str, session: Session = Depends(get_session)) -> dict[str, list[dict[str, object]]]:
    run = session.get(Run, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="run not found")
    events = session.scalars(
        select(RuntimeEvent).where(RuntimeEvent.run_id == run_id).order_by(RuntimeEvent.occurred_at.asc())
    ).all()
    return {
        "events": [
            {
                "event_id": event.event_id,
                "event_type": event.event_type,
                "payload_digest": event.payload_digest,
                "occurred_at": event.occurred_at.isoformat(),
            }
            for event in events
        ],
    }


@router.get("/{run_id}/events/stream")
def stream_run_events(run_id: str, session: Session = Depends(get_session)) -> StreamingResponse:
    run = session.get(Run, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="run not found")
    events = session.scalars(
        select(RuntimeEvent).where(RuntimeEvent.run_id == run_id).order_by(RuntimeEvent.occurred_at.asc())
    ).all()

    def event_generator():
        for event in events:
            payload = {
                "event_id": event.event_id,
                "event_type": event.event_type,
                "payload_digest": event.payload_digest,
                "occurred_at": event.occurred_at.isoformat(),
            }
            yield f"event: runtime_event\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"
        yield f"event: stream_end\ndata: {json.dumps({'run_id': run_id, 'event_count': len(events)}, ensure_ascii=False)}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@router.post("/{run_id}/cancel")
def cancel_run(run_id: str, body: RunCancelRequest, session: Session = Depends(get_session)) -> dict[str, object]:
    run = session.get(Run, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="run not found")
    run.status = "cancelled"
    session.add(run)
    session.commit()
    append_runtime_event(
        session,
        tenant_id=run.tenant_id,
        workspace_id=run.workspace_id,
        thread_id=run.thread_id,
        run_id=run.run_id,
        event_type="run.cancelled",
        actor=body.user_id,
        payload={"reason": body.reason},
        idempotency_key=f"{run.run_id}:run.cancelled",
    )
    events = session.scalars(
        select(RuntimeEvent).where(RuntimeEvent.run_id == run_id).order_by(RuntimeEvent.occurred_at.asc())
    ).all()
    return {
        "run_id": run.run_id,
        "status": run.status,
        "events": [event.event_type for event in events],
    }


@router.post("/{run_id}/retry")
def retry_run(run_id: str, body: RunRetryRequest, session: Session = Depends(get_session)) -> dict[str, object]:
    original = session.get(Run, run_id)
    if original is None:
        raise HTTPException(status_code=404, detail="run not found")
    new_run_id = f"run_{uuid.uuid4().hex}"
    retried = Run(
        run_id=new_run_id,
        tenant_id=original.tenant_id,
        workspace_id=original.workspace_id,
        thread_id=original.thread_id,
        user_id=body.user_id,
        status="created",
        question=original.question,
    )
    session.add(retried)
    session.commit()
    append_runtime_event(
        session,
        tenant_id=retried.tenant_id,
        workspace_id=retried.workspace_id,
        thread_id=retried.thread_id,
        run_id=retried.run_id,
        event_type="run.created",
        actor=body.user_id,
        payload={"message": retried.question},
        idempotency_key=f"{retried.run_id}:run.created",
    )
    append_runtime_event(
        session,
        tenant_id=retried.tenant_id,
        workspace_id=retried.workspace_id,
        thread_id=retried.thread_id,
        run_id=retried.run_id,
        event_type="retry_of_run",
        actor=body.user_id,
        payload={"retry_of_run_id": original.run_id},
        idempotency_key=f"{retried.run_id}:retry_of_run:{original.run_id}",
    )
    events = session.scalars(
        select(RuntimeEvent).where(RuntimeEvent.run_id == retried.run_id).order_by(RuntimeEvent.occurred_at.asc())
    ).all()
    return {
        "run_id": retried.run_id,
        "retry_of_run_id": original.run_id,
        "status": retried.status,
        "events": [event.event_type for event in events],
    }
