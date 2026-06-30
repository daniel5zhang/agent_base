import json
import queue
import threading
import uuid
from typing import Any

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.agent_runtime import AgentRunInput, AgentSessionRuntime, classify_text
from app.db import SessionLocal, get_session
from app.llm import (
    chat_completion,
    chat_completion_messages,
    chat_completion_stream,
    chat_completion_stream_with_tools,
    chat_completion_with_tools,
)
from app.models import Run, RuntimeEvent

router = APIRouter(prefix="/api/agent", tags=["agent"])
compat_router = APIRouter(prefix="/api", tags=["agent"])


class IntentRequest(BaseModel):
    text: str = Field(min_length=1)


class ChatRequest(BaseModel):
    text: str = Field(min_length=1)


class AgentRunRequest(BaseModel):
    tenant_id: str = Field(min_length=1)
    workspace_id: str = Field(min_length=1)
    thread_id: str = Field(min_length=1)
    user_id: str = Field(min_length=1)
    message: str = Field(min_length=1)


@router.post("/intent")
def classify_intent(body: IntentRequest) -> dict[str, object]:
    return classify_text(body.text)


@router.post("/chat")
def chat(body: ChatRequest) -> dict[str, str]:
    return chat_completion(body.text)


@compat_router.post("/chat")
def chat_compat(body: ChatRequest) -> dict[str, str]:
    return chat(body)


@router.post("/run")
def run_agent(body: AgentRunRequest, session: Session = Depends(get_session)) -> dict[str, object]:
    runtime = AgentSessionRuntime(
        session,
        intent_classifier=classify_text,
        model_client=chat_completion,
        model_tool_client=chat_completion_with_tools,
        model_messages_client=chat_completion_messages,
    )
    return runtime.run(
        AgentRunInput(
            tenant_id=body.tenant_id,
            workspace_id=body.workspace_id,
            thread_id=body.thread_id,
            user_id=body.user_id,
            message=body.message,
        )
    )


def _sse(event: str, data: dict[str, Any]) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


def _runtime_event_payload(event: RuntimeEvent) -> dict[str, Any]:
    return {
        "event_id": event.event_id,
        "event_type": event.event_type,
        "run_id": event.run_id,
        "thread_id": event.thread_id,
        "workspace_id": event.workspace_id,
        "payload_digest": event.payload_digest,
        "occurred_at": event.occurred_at.isoformat(),
        "payload": json.loads(event.payload_json),
    }


@router.post("/run/stream")
def stream_agent_run(body: AgentRunRequest) -> StreamingResponse:
    messages: queue.Queue[tuple[str, dict[str, Any]] | None] = queue.Queue()
    run_id = f"run_{uuid.uuid4().hex}"

    def worker() -> None:
        with SessionLocal() as session:
            try:
                def is_cancelled() -> bool:
                    session.expire_all()
                    run = session.get(Run, run_id)
                    return run is not None and run.status == "cancelled"

                runtime = AgentSessionRuntime(
                    session,
                    intent_classifier=classify_text,
                    model_client=chat_completion,
                    model_tool_client=chat_completion_with_tools,
                    model_messages_client=chat_completion_messages,
                    model_stream_client=chat_completion_stream,
                    model_stream_tool_client=chat_completion_stream_with_tools,
                )
                result = runtime.run(
                    AgentRunInput(
                        tenant_id=body.tenant_id,
                        workspace_id=body.workspace_id,
                        thread_id=body.thread_id,
                        user_id=body.user_id,
                        message=body.message,
                    ),
                    on_event=lambda event: messages.put(
                        (
                            "model_delta" if event.event_type == "model.delta" else "runtime_event",
                            _runtime_event_payload(event),
                        )
                    ),
                    run_id=run_id,
                    cancel_checker=is_cancelled,
                )
                messages.put(("final_result", result))
            except Exception as error:
                messages.put(("run_error", {"message": error.__class__.__name__}))
            finally:
                messages.put(None)

    def event_generator():
        thread = threading.Thread(target=worker, daemon=True)
        thread.start()
        while True:
            item = messages.get()
            if item is None:
                break
            event_name, payload = item
            yield _sse(event_name, payload)
        yield _sse("stream_end", {"status": "closed"})

    return StreamingResponse(event_generator(), media_type="text/event-stream")
