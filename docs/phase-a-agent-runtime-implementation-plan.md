# Phase A Agent Runtime Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把当前后端从“一阶段可运行 Agent 原型”补齐为可恢复、可回放、可审计、可扩展工具调用的通用 Agent Runtime 底座。

**Architecture:** Phase A 只改后端 Runtime 协议和持久化，不重做前端交互。`Message` 继续作为现有 assistant-ui 前端的兼容数据源，新增 `TranscriptEvent` 作为长期事件流事实源；`RuntimeEvent` 继续承载审计/运行证据，新增 `UsageMeter` 记录模型调用用量。工具调用统一通过 `StandardToolResult` 返回，Run 状态统一由状态机校验。

**Tech Stack:** Python 3.11, FastAPI, SQLAlchemy, SQLite, pytest, OpenAI-compatible model API.

---

## 0. Scope Boundary

### In scope

Phase A 必须完成：

- Thread 可恢复：历史会话仍可通过现有 `GET /api/threads/{thread_id}` 加载。
- Transcript 可回放：新增标准事件流，支持按 Thread 和 Run 查询。
- ToolResult 可回写模型上下文：工具结果不只展示给用户，也能作为后续模型输入。
- Run 状态机可靠：取消、失败、重试、完成等状态必须有合法流转。
- 模型调用可统计：记录 provider、model、token、latency、status。
- 兼容现有前端：不要求前端迁移到 TranscriptEvent，但 API 要为后续迁移预留。

### Out of scope

Phase A 不做：

- 插件中心 UI 和插件市场。
- 审批中心 UI。
- 企业 IAM / RBAC / ABAC 的完整实现。
- 真实业务 Connector Runtime。
- 真实 SQL 数据权限。
- 前端交互重构。

如果实现 Phase A 时发现必须修改前端，只能做兼容性修复；任何新交互、新面板、新 assistant-ui Runtime 迁移都需要先向用户说明修改点并获得确认。

## 1. Current Backend Baseline

当前已有文件：

```text
backend/app/models.py
backend/app/agent_runtime.py
backend/app/routes/agent.py
backend/app/routes/runtime.py
backend/app/routes/threads.py
backend/app/routes/models.py
backend/app/routes/tools.py
backend/tests/test_phase1_agent_runtime.py
backend/tests/test_mvp1_api.py
backend/tests/test_llm.py
```

当前已有模型：

```text
RuntimeEvent
PluginPackage
ServerBinding
ReleasePolicy
AgentMemory
Thread
Message
Artifact
ToolInvocation
ModelCall
Run
RunStep
AuditEvent
```

关键缺口：

```text
TranscriptEvent       缺失，无法可靠回放完整运行过程
UsageMeter            缺失，无法统计模型调用成本和延迟
StandardToolResult    缺失，工具结果协议不够稳定
RunStateMachine       缺失，状态变更可被任意写入
ModelProviderRegistry 缺失，多模型配置没有服务端抽象
```

## 2. Target File Structure

### Create

```text
backend/app/transcripts.py
backend/app/tool_results.py
backend/app/run_state.py
backend/app/model_providers.py
backend/app/usage.py
backend/app/routes/transcripts.py
backend/tests/test_transcript_events.py
backend/tests/test_tool_result_contract.py
backend/tests/test_run_state_machine.py
backend/tests/test_model_provider_usage.py
```

### Modify

```text
backend/app/models.py
backend/app/agent_runtime.py
backend/app/llm.py
backend/app/main.py
backend/app/routes/agent.py
backend/app/routes/runtime.py
backend/app/routes/models.py
backend/tests/test_phase1_agent_runtime.py
backend/tests/test_mvp1_api.py
```

## 3. Data Contracts

### 3.1 TranscriptEvent

Add to `backend/app/models.py`:

```python
class TranscriptEvent(Base):
    __tablename__ = "transcript_event"
    __table_args__ = (
        UniqueConstraint("tenant_id", "thread_id", "sequence", name="uq_transcript_thread_sequence"),
    )

    transcript_event_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(64), index=True)
    workspace_id: Mapped[str] = mapped_column(String(64), index=True)
    thread_id: Mapped[str] = mapped_column(String(64), index=True)
    run_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    sequence: Mapped[int] = mapped_column(Integer, index=True)
    role: Mapped[str] = mapped_column(String(40))
    event_type: Mapped[str] = mapped_column(String(100), index=True)
    content_json: Mapped[str] = mapped_column(Text)
    source_message_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    source_tool_invocation_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    source_runtime_event_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
```

First event types:

```text
user.message
assistant.message.delta
assistant.message.completed
assistant.reasoning
assistant.tool_call
tool.result
system.context_loaded
system.compaction
system.permission_decision
system.run_state_changed
```

Rules:

- `sequence` is per `tenant_id + thread_id`, starting from 1.
- `Message` remains the frontend compatibility projection.
- `TranscriptEvent` becomes the source of truth for replay and future assistant-ui runtime migration.
- Delta events may be compacted later, but Phase A stores them as written.

### 3.2 UsageMeter

Add to `backend/app/models.py`:

```python
class UsageMeter(Base):
    __tablename__ = "usage_meter"

    usage_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(64), index=True)
    workspace_id: Mapped[str] = mapped_column(String(64), index=True)
    user_id: Mapped[str] = mapped_column(String(128), index=True)
    thread_id: Mapped[str] = mapped_column(String(64), index=True)
    run_id: Mapped[str] = mapped_column(String(64), index=True)
    model_call_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    provider_id: Mapped[str] = mapped_column(String(80))
    model_id: Mapped[str] = mapped_column(String(120))
    prompt_tokens: Mapped[int] = mapped_column(Integer, default=0)
    completion_tokens: Mapped[int] = mapped_column(Integer, default=0)
    total_tokens: Mapped[int] = mapped_column(Integer, default=0)
    latency_ms: Mapped[int] = mapped_column(Integer, default=0)
    estimated_cost_json: Mapped[str] = mapped_column(Text, default="{}")
    status: Mapped[str] = mapped_column(String(40), default="completed")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
```

Rules:

- Provider 不返回 token 时写 0，但仍记录 `provider_id/model_id/status/latency_ms`。
- Phase A 不计算真实费用，`estimated_cost_json` 写 `{}`。
- Phase C 再接入 Provider 级定价配置。

### 3.3 StandardToolResult

Create `backend/app/tool_results.py`:

```python
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

ToolResultStatus = Literal["completed", "failed", "partial", "blocked", "approval_required"]


@dataclass
class ToolArtifactRef:
    artifact_id: str
    artifact_type: str
    title: str
    renderer_hint: str | None = None


@dataclass
class ToolError:
    code: str
    message: str
    retryable: bool = False


@dataclass
class StandardToolResult:
    tool_id: str
    status: ToolResultStatus
    response_text: str
    model_context: list[dict[str, Any]] = field(default_factory=list)
    output_payload: dict[str, Any] = field(default_factory=dict)
    artifacts: list[ToolArtifactRef] = field(default_factory=list)
    audit_event_id: str | None = None
    error: ToolError | None = None

    def to_model_message(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "tool_id": self.tool_id,
            "status": self.status,
            "summary": self.response_text,
            "model_context": self.model_context,
            "output_payload": self.output_payload,
            "artifacts": [artifact.__dict__ for artifact in self.artifacts],
            "audit_event_id": self.audit_event_id,
        }
        if self.error is not None:
            payload["error"] = self.error.__dict__
        return {
            "role": "tool",
            "content": payload,
        }
```

Rules:

- `response_text` is the human-readable summary displayed in the main conversation.
- `model_context` is a controlled payload for the next model turn.
- `output_payload` can contain structured data for artifacts or diagnostics.
- `artifacts` only stores references, not full rendered UI state.
- `error.retryable = true` means the UI may show retry action later.

### 3.4 Run State Machine

Create `backend/app/run_state.py`:

```python
from typing import Literal

RunStatus = Literal[
    "created",
    "queued",
    "running",
    "waiting_approval",
    "completed",
    "failed",
    "cancelled",
]

ALLOWED_RUN_TRANSITIONS: dict[str, set[str]] = {
    "created": {"queued", "running", "cancelled", "failed"},
    "queued": {"running", "cancelled", "failed"},
    "running": {"waiting_approval", "completed", "failed", "cancelled"},
    "waiting_approval": {"running", "failed", "cancelled"},
    "completed": set(),
    "failed": set(),
    "cancelled": set(),
}


class InvalidRunTransition(ValueError):
    pass


def assert_run_transition(current: str, target: str) -> None:
    allowed = ALLOWED_RUN_TRANSITIONS.get(current, set())
    if target not in allowed:
        raise InvalidRunTransition(f"invalid run transition: {current} -> {target}")
```

Rules:

- Terminal states: `completed`, `failed`, `cancelled`。
- Retry creates a new Run; do not mutate terminal Run back to `created/running`。
- Approval resume moves `waiting_approval -> running` only after approval decision is allowed.

## 4. API Contracts

### 4.1 Thread transcript

Create `GET /api/threads/{thread_id}/transcript`.

Request:

```text
tenant_id=tenant_demo
workspace_id=workspace_default
user_id=user_demo
limit=100
after_sequence=0
```

Response:

```json
{
  "thread_id": "thread_001",
  "events": [
    {
      "transcript_event_id": "tev_xxx",
      "sequence": 1,
      "role": "user",
      "event_type": "user.message",
      "content": {"text": "你好"},
      "run_id": "run_xxx",
      "created_at": "2026-06-30T00:00:00+00:00"
    }
  ],
  "next_after_sequence": 1
}
```

### 4.2 Run transcript

Create `GET /api/runs/{run_id}/transcript`.

Response:

```json
{
  "run_id": "run_xxx",
  "events": [
    {
      "sequence": 7,
      "role": "assistant",
      "event_type": "assistant.reasoning",
      "content": {"text": "识别为通用对话"}
    }
  ]
}
```

### 4.3 Run usage

Create `GET /api/runs/{run_id}/usage`.

Response:

```json
{
  "run_id": "run_xxx",
  "usage": [
    {
      "provider_id": "bailian",
      "model_id": "qwen-plus",
      "prompt_tokens": 10,
      "completion_tokens": 20,
      "total_tokens": 30,
      "latency_ms": 1200,
      "status": "completed"
    }
  ]
}
```

### 4.4 Available models

Keep existing model route compatible. If `backend/app/routes/models.py` already returns a model list, extend it without breaking current response keys:

```json
{
  "models": [
    {
      "provider_id": "bailian",
      "model_id": "qwen-plus",
      "display_name": "通义千问 Plus",
      "enabled": true,
      "default": true
    }
  ]
}
```

Phase A does not add the full settings UI. It only gives the backend a stable provider abstraction and available-models response.

## 5. Implementation Tasks

### Task 1: Add TranscriptEvent and UsageMeter models

**Files:**

- Modify: `backend/app/models.py`
- Test: `backend/tests/test_transcript_events.py`
- Test: `backend/tests/test_model_provider_usage.py`

- [ ] **Step 1: Write failing model tests**

Create `backend/tests/test_transcript_events.py`:

```python
import json

from sqlalchemy import select

from app.models import TranscriptEvent
from app.transcripts import TranscriptService


def test_append_transcript_event_assigns_thread_sequence(session):
    service = TranscriptService(session)

    first = service.append_event(
        tenant_id="tenant_demo",
        workspace_id="workspace_default",
        thread_id="thread_001",
        run_id="run_001",
        role="user",
        event_type="user.message",
        content={"text": "你好"},
    )
    second = service.append_event(
        tenant_id="tenant_demo",
        workspace_id="workspace_default",
        thread_id="thread_001",
        run_id="run_001",
        role="assistant",
        event_type="assistant.message.completed",
        content={"text": "你好，我可以帮你处理任务。"},
    )

    rows = session.scalars(
        select(TranscriptEvent).where(TranscriptEvent.thread_id == "thread_001").order_by(TranscriptEvent.sequence)
    ).all()

    assert first.sequence == 1
    assert second.sequence == 2
    assert [row.sequence for row in rows] == [1, 2]
    assert json.loads(rows[0].content_json) == {"text": "你好"}
```

Create `backend/tests/test_model_provider_usage.py`:

```python
from sqlalchemy import select

from app.models import UsageMeter
from app.usage import UsageMeterService


def test_usage_meter_records_model_call_usage(session):
    service = UsageMeterService(session)

    usage = service.record_usage(
        tenant_id="tenant_demo",
        workspace_id="workspace_default",
        user_id="user_demo",
        thread_id="thread_001",
        run_id="run_001",
        model_call_id="model_call_001",
        provider_id="bailian",
        model_id="qwen-plus",
        prompt_tokens=12,
        completion_tokens=34,
        latency_ms=456,
        status="completed",
    )

    row = session.scalar(select(UsageMeter).where(UsageMeter.usage_id == usage.usage_id))
    assert row is not None
    assert row.total_tokens == 46
    assert row.provider_id == "bailian"
    assert row.model_id == "qwen-plus"
```

- [ ] **Step 2: Run tests and verify failure**

Run:

```bash
cd /Users/daniel/Desktop/code/工作台/workbench-app/frontend-v2/backend
pytest tests/test_transcript_events.py tests/test_model_provider_usage.py -q
```

Expected:

```text
ImportError or AttributeError for TranscriptEvent, TranscriptService, UsageMeter, UsageMeterService
```

- [ ] **Step 3: Implement model classes**

Add `TranscriptEvent` and `UsageMeter` exactly after `Message` and `ModelCall` in `backend/app/models.py`.

Key implementation constraints:

- Import already includes `UniqueConstraint`; reuse it.
- Use `utc_now` from the same file.
- No Alembic migration in Phase A; `initialize_database()` already calls `create_all`.

- [ ] **Step 4: Implement service skeletons**

Create `backend/app/transcripts.py`:

```python
import json
import uuid
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import TranscriptEvent


class TranscriptService:
    def __init__(self, session: Session) -> None:
        self.session = session

    def append_event(
        self,
        *,
        tenant_id: str,
        workspace_id: str,
        thread_id: str,
        run_id: str | None,
        role: str,
        event_type: str,
        content: dict[str, Any],
        source_message_id: str | None = None,
        source_tool_invocation_id: str | None = None,
        source_runtime_event_id: str | None = None,
    ) -> TranscriptEvent:
        current_max = self.session.scalar(
            select(func.max(TranscriptEvent.sequence)).where(
                TranscriptEvent.tenant_id == tenant_id,
                TranscriptEvent.thread_id == thread_id,
            )
        )
        next_sequence = int(current_max or 0) + 1
        event = TranscriptEvent(
            transcript_event_id=f"tev_{uuid.uuid4().hex}",
            tenant_id=tenant_id,
            workspace_id=workspace_id,
            thread_id=thread_id,
            run_id=run_id,
            sequence=next_sequence,
            role=role,
            event_type=event_type,
            content_json=json.dumps(content, ensure_ascii=False),
            source_message_id=source_message_id,
            source_tool_invocation_id=source_tool_invocation_id,
            source_runtime_event_id=source_runtime_event_id,
        )
        self.session.add(event)
        self.session.commit()
        self.session.refresh(event)
        return event
```

Create `backend/app/usage.py`:

```python
import json
import uuid

from sqlalchemy.orm import Session

from app.models import UsageMeter


class UsageMeterService:
    def __init__(self, session: Session) -> None:
        self.session = session

    def record_usage(
        self,
        *,
        tenant_id: str,
        workspace_id: str,
        user_id: str,
        thread_id: str,
        run_id: str,
        model_call_id: str | None,
        provider_id: str,
        model_id: str,
        prompt_tokens: int,
        completion_tokens: int,
        latency_ms: int,
        status: str,
    ) -> UsageMeter:
        usage = UsageMeter(
            usage_id=f"usage_{uuid.uuid4().hex}",
            tenant_id=tenant_id,
            workspace_id=workspace_id,
            user_id=user_id,
            thread_id=thread_id,
            run_id=run_id,
            model_call_id=model_call_id,
            provider_id=provider_id,
            model_id=model_id,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=prompt_tokens + completion_tokens,
            latency_ms=latency_ms,
            estimated_cost_json=json.dumps({}, ensure_ascii=False),
            status=status,
        )
        self.session.add(usage)
        self.session.commit()
        self.session.refresh(usage)
        return usage
```

- [ ] **Step 5: Run tests**

Run:

```bash
cd /Users/daniel/Desktop/code/工作台/workbench-app/frontend-v2/backend
pytest tests/test_transcript_events.py tests/test_model_provider_usage.py -q
```

Expected:

```text
2 passed
```

- [ ] **Step 6: Commit**

```bash
git add backend/app/models.py backend/app/transcripts.py backend/app/usage.py backend/tests/test_transcript_events.py backend/tests/test_model_provider_usage.py
git commit -m "feat: add transcript and usage persistence"
```

### Task 2: Add transcript query APIs

**Files:**

- Create: `backend/app/routes/transcripts.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_transcript_events.py`

- [ ] **Step 1: Add failing API tests**

Append to `backend/tests/test_transcript_events.py`:

```python
def test_get_thread_transcript_returns_events(client, session):
    service = TranscriptService(session)
    service.append_event(
        tenant_id="tenant_demo",
        workspace_id="workspace_default",
        thread_id="thread_api",
        run_id="run_api",
        role="user",
        event_type="user.message",
        content={"text": "查一下"},
    )

    response = client.get(
        "/api/threads/thread_api/transcript",
        params={
            "tenant_id": "tenant_demo",
            "workspace_id": "workspace_default",
            "user_id": "user_demo",
            "limit": 20,
            "after_sequence": 0,
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["thread_id"] == "thread_api"
    assert data["next_after_sequence"] == 1
    assert data["events"][0]["event_type"] == "user.message"
    assert data["events"][0]["content"] == {"text": "查一下"}


def test_get_run_transcript_returns_run_events(client, session):
    service = TranscriptService(session)
    service.append_event(
        tenant_id="tenant_demo",
        workspace_id="workspace_default",
        thread_id="thread_api",
        run_id="run_api",
        role="assistant",
        event_type="assistant.reasoning",
        content={"text": "识别任务"},
    )

    response = client.get("/api/runs/run_api/transcript")

    assert response.status_code == 200
    data = response.json()
    assert data["run_id"] == "run_api"
    assert data["events"][0]["event_type"] == "assistant.reasoning"
```

- [ ] **Step 2: Run tests and verify failure**

Run:

```bash
cd /Users/daniel/Desktop/code/工作台/workbench-app/frontend-v2/backend
pytest tests/test_transcript_events.py -q
```

Expected:

```text
404 Not Found for transcript routes
```

- [ ] **Step 3: Implement routes**

Create `backend/app/routes/transcripts.py`:

```python
import json

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_session
from app.models import TranscriptEvent

thread_router = APIRouter(prefix="/api/threads", tags=["transcripts"])
run_router = APIRouter(prefix="/api/runs", tags=["transcripts"])


def serialize_event(event: TranscriptEvent) -> dict[str, object]:
    return {
        "transcript_event_id": event.transcript_event_id,
        "sequence": event.sequence,
        "role": event.role,
        "event_type": event.event_type,
        "content": json.loads(event.content_json),
        "run_id": event.run_id,
        "source_message_id": event.source_message_id,
        "source_tool_invocation_id": event.source_tool_invocation_id,
        "source_runtime_event_id": event.source_runtime_event_id,
        "created_at": event.created_at.isoformat() if event.created_at else None,
    }


@thread_router.get("/{thread_id}/transcript")
def get_thread_transcript(
    thread_id: str,
    tenant_id: str = Query(min_length=1),
    workspace_id: str = Query(min_length=1),
    user_id: str = Query(min_length=1),
    limit: int = 100,
    after_sequence: int = 0,
    session: Session = Depends(get_session),
) -> dict[str, object]:
    _ = user_id
    bounded_limit = max(1, min(limit, 500))
    events = session.scalars(
        select(TranscriptEvent)
        .where(
            TranscriptEvent.tenant_id == tenant_id,
            TranscriptEvent.workspace_id == workspace_id,
            TranscriptEvent.thread_id == thread_id,
            TranscriptEvent.sequence > after_sequence,
        )
        .order_by(TranscriptEvent.sequence.asc())
        .limit(bounded_limit)
    ).all()
    return {
        "thread_id": thread_id,
        "events": [serialize_event(event) for event in events],
        "next_after_sequence": events[-1].sequence if events else after_sequence,
    }


@run_router.get("/{run_id}/transcript")
def get_run_transcript(run_id: str, session: Session = Depends(get_session)) -> dict[str, object]:
    events = session.scalars(
        select(TranscriptEvent)
        .where(TranscriptEvent.run_id == run_id)
        .order_by(TranscriptEvent.sequence.asc())
    ).all()
    return {
        "run_id": run_id,
        "events": [serialize_event(event) for event in events],
    }
```

Modify `backend/app/main.py`:

```python
from app.routes.transcripts import run_router as transcript_run_router
from app.routes.transcripts import thread_router as transcript_thread_router
```

Inside `create_app()` after `threads_router` and `runtime_router` registration:

```python
app.include_router(transcript_thread_router)
app.include_router(transcript_run_router)
```

- [ ] **Step 4: Run tests**

Run:

```bash
cd /Users/daniel/Desktop/code/工作台/workbench-app/frontend-v2/backend
pytest tests/test_transcript_events.py -q
```

Expected:

```text
3 passed
```

- [ ] **Step 5: Commit**

```bash
git add backend/app/routes/transcripts.py backend/app/main.py backend/tests/test_transcript_events.py
git commit -m "feat: expose transcript query APIs"
```

### Task 3: Add StandardToolResult contract

**Files:**

- Create: `backend/app/tool_results.py`
- Modify: `backend/app/agent_runtime.py`
- Test: `backend/tests/test_tool_result_contract.py`

- [ ] **Step 1: Write failing contract tests**

Create `backend/tests/test_tool_result_contract.py`:

```python
from app.tool_results import StandardToolResult, ToolArtifactRef, ToolError


def test_standard_tool_result_to_model_message_contains_context_and_artifacts():
    result = StandardToolResult(
        tool_id="workspace.list",
        status="completed",
        response_text="已读取 2 个文件",
        model_context=[{"type": "file_list", "files": ["a.md", "b.md"]}],
        output_payload={"count": 2},
        artifacts=[
            ToolArtifactRef(
                artifact_id="artifact_001",
                artifact_type="table",
                title="文件列表",
                renderer_hint="table",
            )
        ],
        audit_event_id="audit_001",
    )

    message = result.to_model_message()

    assert message["role"] == "tool"
    assert message["content"]["tool_id"] == "workspace.list"
    assert message["content"]["status"] == "completed"
    assert message["content"]["model_context"][0]["type"] == "file_list"
    assert message["content"]["artifacts"][0]["artifact_id"] == "artifact_001"


def test_standard_tool_result_error_is_serialized():
    result = StandardToolResult(
        tool_id="diagnostic.check",
        status="failed",
        response_text="诊断失败",
        error=ToolError(code="diagnostic_failed", message="服务不可用", retryable=True),
    )

    message = result.to_model_message()

    assert message["content"]["error"] == {
        "code": "diagnostic_failed",
        "message": "服务不可用",
        "retryable": True,
    }
```

- [ ] **Step 2: Run tests and verify failure**

Run:

```bash
cd /Users/daniel/Desktop/code/工作台/workbench-app/frontend-v2/backend
pytest tests/test_tool_result_contract.py -q
```

Expected:

```text
ImportError for app.tool_results
```

- [ ] **Step 3: Implement `backend/app/tool_results.py`**

Use the code in section `3.3 StandardToolResult`.

- [ ] **Step 4: Add adapter in `agent_runtime.py`**

Modify existing `ToolExecutionResult` dataclass to include:

```python
    model_context: list[dict[str, Any]] = field(default_factory=list)
    error: dict[str, Any] | None = None
```

Add method:

```python
    def to_standard_result(self) -> StandardToolResult:
        artifact_refs = [
            ToolArtifactRef(
                artifact_id=artifact.artifact_id,
                artifact_type=artifact.artifact_type,
                title=artifact.title,
                renderer_hint=None,
            )
            for artifact in self.artifacts
        ]
        tool_error = None
        if self.error is not None:
            tool_error = ToolError(
                code=str(self.error.get("code", "tool_error")),
                message=str(self.error.get("message", self.response_text or "工具执行失败")),
                retryable=bool(self.error.get("retryable", False)),
            )
        return StandardToolResult(
            tool_id=self.tool_id,
            status=self.status,
            response_text=self.response_text,
            model_context=self.model_context,
            output_payload=self.output_payload,
            artifacts=artifact_refs,
            audit_event_id=self.audit_event_id,
            error=tool_error,
        )
```

Also import:

```python
from app.tool_results import StandardToolResult, ToolArtifactRef, ToolError
```

- [ ] **Step 5: Add adapter test**

Append to `backend/tests/test_tool_result_contract.py`:

```python
from app.agent_runtime import ToolExecutionResult


def test_tool_execution_result_adapts_to_standard_result():
    result = ToolExecutionResult(
        tool_id="local_data.analyze",
        status="completed",
        response_text="平均值是 20",
        output_payload={"average": 20},
        model_context=[{"metric": "average", "value": 20}],
    )

    standard = result.to_standard_result()

    assert standard.tool_id == "local_data.analyze"
    assert standard.status == "completed"
    assert standard.to_model_message()["content"]["model_context"] == [{"metric": "average", "value": 20}]
```

- [ ] **Step 6: Run tests**

Run:

```bash
cd /Users/daniel/Desktop/code/工作台/workbench-app/frontend-v2/backend
pytest tests/test_tool_result_contract.py -q
```

Expected:

```text
3 passed
```

- [ ] **Step 7: Commit**

```bash
git add backend/app/tool_results.py backend/app/agent_runtime.py backend/tests/test_tool_result_contract.py
git commit -m "feat: standardize tool result contract"
```

### Task 4: Add Run state machine and integrate runtime routes

**Files:**

- Create: `backend/app/run_state.py`
- Modify: `backend/app/routes/runtime.py`
- Modify: `backend/app/agent_runtime.py`
- Test: `backend/tests/test_run_state_machine.py`

- [ ] **Step 1: Write failing state-machine tests**

Create `backend/tests/test_run_state_machine.py`:

```python
import pytest

from app.run_state import InvalidRunTransition, assert_run_transition


def test_run_state_allows_normal_execution_path():
    assert_run_transition("created", "running")
    assert_run_transition("running", "completed")


def test_run_state_allows_approval_pause_and_resume():
    assert_run_transition("running", "waiting_approval")
    assert_run_transition("waiting_approval", "running")


def test_run_state_rejects_terminal_mutation():
    with pytest.raises(InvalidRunTransition):
        assert_run_transition("completed", "running")

    with pytest.raises(InvalidRunTransition):
        assert_run_transition("cancelled", "running")
```

- [ ] **Step 2: Run tests and verify failure**

Run:

```bash
cd /Users/daniel/Desktop/code/工作台/workbench-app/frontend-v2/backend
pytest tests/test_run_state_machine.py -q
```

Expected:

```text
ImportError for app.run_state
```

- [ ] **Step 3: Implement `backend/app/run_state.py`**

Use the code in section `3.4 Run State Machine`.

- [ ] **Step 4: Add route-level transition helper**

In `backend/app/routes/runtime.py`, import:

```python
from app.run_state import InvalidRunTransition, assert_run_transition
```

Add helper:

```python
def set_run_status(run: Run, target: str) -> None:
    try:
        assert_run_transition(run.status, target)
    except InvalidRunTransition as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    run.status = target
```

Replace direct mutations:

```python
run.status = "cancelled"
```

with:

```python
set_run_status(run, "cancelled")
```

For retry:

- Do not mutate original Run.
- Create a new Run with status `created`.
- Add RuntimeEvent `retry_of_run`.

- [ ] **Step 5: Add API regression test**

Append to `backend/tests/test_run_state_machine.py`:

```python
from app.models import Run


def test_cancel_completed_run_is_rejected(client, session):
    run = Run(
        run_id="run_done",
        tenant_id="tenant_demo",
        workspace_id="workspace_default",
        thread_id="thread_001",
        user_id="user_demo",
        status="completed",
        question="你好",
    )
    session.add(run)
    session.commit()

    response = client.post("/api/runs/run_done/cancel", json={"user_id": "user_demo", "reason": "test"})

    assert response.status_code == 409
    assert "completed -> cancelled" in response.json()["detail"]
```

- [ ] **Step 6: Run tests**

Run:

```bash
cd /Users/daniel/Desktop/code/工作台/workbench-app/frontend-v2/backend
pytest tests/test_run_state_machine.py tests/test_mvp1_api.py -q
```

Expected:

```text
all tests passed
```

- [ ] **Step 7: Commit**

```bash
git add backend/app/run_state.py backend/app/routes/runtime.py backend/app/agent_runtime.py backend/tests/test_run_state_machine.py
git commit -m "feat: enforce run state transitions"
```

### Task 5: Dual-write Message and TranscriptEvent in Agent Runtime

**Files:**

- Modify: `backend/app/agent_runtime.py`
- Test: `backend/tests/test_phase1_agent_runtime.py`
- Test: `backend/tests/test_transcript_events.py`

- [ ] **Step 1: Add failing runtime transcript test**

Append to `backend/tests/test_transcript_events.py`:

```python
from sqlalchemy import select

from app.agent_runtime import AgentRunInput, AgentSessionRuntime
from app.models import Message, TranscriptEvent


def test_agent_runtime_dual_writes_message_and_transcript(session):
    runtime = AgentSessionRuntime(session)
    result = runtime.run_once(
        AgentRunInput(
            tenant_id="tenant_demo",
            workspace_id="workspace_default",
            thread_id="thread_runtime",
            user_id="user_demo",
            message="你好",
        )
    )

    messages = session.scalars(
        select(Message).where(Message.thread_id == "thread_runtime").order_by(Message.created_at.asc())
    ).all()
    transcript_events = session.scalars(
        select(TranscriptEvent)
        .where(TranscriptEvent.thread_id == "thread_runtime")
        .order_by(TranscriptEvent.sequence.asc())
    ).all()

    assert result["run_id"].startswith("run_")
    assert [message.role for message in messages] == ["user", "assistant"]
    assert [event.event_type for event in transcript_events] == [
        "user.message",
        "assistant.reasoning",
        "assistant.message.completed",
    ]
```

- [ ] **Step 2: Run tests and verify failure**

Run:

```bash
cd /Users/daniel/Desktop/code/工作台/workbench-app/frontend-v2/backend
pytest tests/test_transcript_events.py::test_agent_runtime_dual_writes_message_and_transcript -q
```

Expected:

```text
TranscriptEvent assertions fail because runtime only writes Message/RuntimeEvent
```

- [ ] **Step 3: Integrate TranscriptService**

In `backend/app/agent_runtime.py`, import:

```python
from app.transcripts import TranscriptService
```

Inside `AgentSessionRuntime.run_once(...)`:

- After user `Message` is persisted, call:

```python
TranscriptService(self.session).append_event(
    tenant_id=request.tenant_id,
    workspace_id=request.workspace_id,
    thread_id=request.thread_id,
    run_id=run_id,
    role="user",
    event_type="user.message",
    content={"text": request.message},
    source_message_id=user_message.message_id,
)
```

- After intent classification, call:

```python
TranscriptService(self.session).append_event(
    tenant_id=request.tenant_id,
    workspace_id=request.workspace_id,
    thread_id=request.thread_id,
    run_id=run_id,
    role="assistant",
    event_type="assistant.reasoning",
    content={
        "intent": intent_result.get("intent"),
        "confidence": intent_result.get("confidence"),
        "required_capabilities": intent_result.get("required_capabilities", []),
    },
)
```

- After final assistant `Message` is persisted, call:

```python
TranscriptService(self.session).append_event(
    tenant_id=request.tenant_id,
    workspace_id=request.workspace_id,
    thread_id=request.thread_id,
    run_id=run_id,
    role="assistant",
    event_type="assistant.message.completed",
    content={"text": assistant_text},
    source_message_id=assistant_message.message_id,
)
```

Use the existing local variable names in `run_once`; if names differ, adapt only the variable names, not the event contract.

- [ ] **Step 4: Add tool transcript writes**

When a tool is invoked:

```python
TranscriptService(self.session).append_event(
    tenant_id=request.tenant_id,
    workspace_id=request.workspace_id,
    thread_id=request.thread_id,
    run_id=run_id,
    role="assistant",
    event_type="assistant.tool_call",
    content={"tool_id": tool_id, "input": tool_input},
    source_tool_invocation_id=invocation.invocation_id,
)
```

When a tool result is available:

```python
standard_result = tool_result.to_standard_result()
TranscriptService(self.session).append_event(
    tenant_id=request.tenant_id,
    workspace_id=request.workspace_id,
    thread_id=request.thread_id,
    run_id=run_id,
    role="tool",
    event_type="tool.result",
    content=standard_result.to_model_message()["content"],
    source_tool_invocation_id=invocation.invocation_id,
)
```

- [ ] **Step 5: Run regression tests**

Run:

```bash
cd /Users/daniel/Desktop/code/工作台/workbench-app/frontend-v2/backend
pytest tests/test_transcript_events.py tests/test_phase1_agent_runtime.py -q
```

Expected:

```text
all tests passed
```

- [ ] **Step 6: Commit**

```bash
git add backend/app/agent_runtime.py backend/tests/test_transcript_events.py backend/tests/test_phase1_agent_runtime.py
git commit -m "feat: dual write runtime transcript events"
```

### Task 6: Record model usage from model calls

**Files:**

- Modify: `backend/app/llm.py`
- Modify: `backend/app/agent_runtime.py`
- Create: `backend/app/model_providers.py`
- Modify: `backend/app/routes/models.py`
- Test: `backend/tests/test_model_provider_usage.py`
- Test: `backend/tests/test_llm.py`

- [ ] **Step 1: Add provider abstraction test**

Append to `backend/tests/test_model_provider_usage.py`:

```python
from app.model_providers import ModelProviderConfig, ModelProviderRegistry


def test_model_provider_registry_returns_default_provider():
    registry = ModelProviderRegistry(
        [
            ModelProviderConfig(
                provider_id="bailian",
                display_name="阿里云百炼",
                base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
                api_key_env="BAILIAN_API_KEY",
                default_model="qwen-plus",
                enabled=True,
            )
        ]
    )

    provider = registry.default_provider()

    assert provider.provider_id == "bailian"
    assert provider.default_model == "qwen-plus"
```

- [ ] **Step 2: Run tests and verify failure**

Run:

```bash
cd /Users/daniel/Desktop/code/工作台/workbench-app/frontend-v2/backend
pytest tests/test_model_provider_usage.py::test_model_provider_registry_returns_default_provider -q
```

Expected:

```text
ImportError for app.model_providers
```

- [ ] **Step 3: Implement provider registry**

Create `backend/app/model_providers.py`:

```python
from dataclasses import dataclass


@dataclass(frozen=True)
class ModelProviderConfig:
    provider_id: str
    display_name: str
    base_url: str
    api_key_env: str
    default_model: str
    enabled: bool = True


class ModelProviderRegistry:
    def __init__(self, providers: list[ModelProviderConfig]) -> None:
        self.providers = [provider for provider in providers if provider.enabled]

    def default_provider(self) -> ModelProviderConfig:
        if not self.providers:
            raise RuntimeError("no enabled model provider")
        return self.providers[0]

    def list_models(self) -> list[dict[str, object]]:
        return [
            {
                "provider_id": provider.provider_id,
                "model_id": provider.default_model,
                "display_name": provider.default_model,
                "enabled": provider.enabled,
                "default": index == 0,
            }
            for index, provider in enumerate(self.providers)
        ]
```

- [ ] **Step 4: Add default registry helper**

In `backend/app/model_providers.py`, add:

```python
import os

from app.llm import DEFAULT_BASE_URL, DEFAULT_MODEL


def default_model_provider_registry() -> ModelProviderRegistry:
    provider_id = os.getenv("MODEL_PROVIDER_ID", "openai_compatible")
    display_name = os.getenv("MODEL_PROVIDER_NAME", "OpenAI Compatible")
    api_key_env = os.getenv("MODEL_API_KEY_ENV", "OPENAI_COMPATIBLE_API_KEY")
    return ModelProviderRegistry(
        [
            ModelProviderConfig(
                provider_id=provider_id,
                display_name=display_name,
                base_url=os.getenv("OPENAI_COMPATIBLE_BASE_URL", DEFAULT_BASE_URL),
                api_key_env=api_key_env,
                default_model=os.getenv("OPENAI_COMPATIBLE_MODEL", DEFAULT_MODEL),
                enabled=True,
            )
        ]
    )
```

- [ ] **Step 5: Extend model route**

Modify `backend/app/routes/models.py` so available model list comes from `default_model_provider_registry().list_models()` while preserving any existing response keys used by frontend.

Required response includes:

```python
{
    "models": default_model_provider_registry().list_models(),
}
```

- [ ] **Step 6: Record usage after model call**

In `backend/app/agent_runtime.py`, after `ModelCall` is persisted and model response is known:

```python
usage_payload = model_response.get("usage", {}) if isinstance(model_response, dict) else {}
UsageMeterService(self.session).record_usage(
    tenant_id=request.tenant_id,
    workspace_id=request.workspace_id,
    user_id=request.user_id,
    thread_id=request.thread_id,
    run_id=run_id,
    model_call_id=model_call.model_call_id,
    provider_id=model_call.provider,
    model_id=model_call.model,
    prompt_tokens=int(usage_payload.get("prompt_tokens", 0) or 0),
    completion_tokens=int(usage_payload.get("completion_tokens", 0) or 0),
    latency_ms=int(model_response.get("latency_ms", 0) or 0),
    status=model_call.status,
)
```

Import:

```python
from app.usage import UsageMeterService
```

- [ ] **Step 7: Add runtime usage regression test**

Append to `backend/tests/test_model_provider_usage.py`:

```python
from sqlalchemy import select

from app.agent_runtime import AgentRunInput, AgentSessionRuntime
from app.models import UsageMeter


def test_runtime_records_usage_when_model_returns_usage(session):
    def fake_model_client(prompt: str):
        assert "你好" in prompt
        return {
            "content": "你好，我可以帮你。",
            "usage": {"prompt_tokens": 3, "completion_tokens": 5},
            "latency_ms": 42,
            "provider": "fake",
            "model": "fake-model",
        }

    runtime = AgentSessionRuntime(session, model_client=fake_model_client)
    runtime.run_once(
        AgentRunInput(
            tenant_id="tenant_demo",
            workspace_id="workspace_default",
            thread_id="thread_usage",
            user_id="user_demo",
            message="你好",
        )
    )

    usage = session.scalar(select(UsageMeter).where(UsageMeter.thread_id == "thread_usage"))
    assert usage is not None
    assert usage.prompt_tokens == 3
    assert usage.completion_tokens == 5
    assert usage.total_tokens == 8
```

- [ ] **Step 8: Run tests**

Run:

```bash
cd /Users/daniel/Desktop/code/工作台/workbench-app/frontend-v2/backend
pytest tests/test_model_provider_usage.py tests/test_llm.py -q
```

Expected:

```text
all tests passed
```

- [ ] **Step 9: Commit**

```bash
git add backend/app/model_providers.py backend/app/routes/models.py backend/app/agent_runtime.py backend/app/usage.py backend/tests/test_model_provider_usage.py backend/tests/test_llm.py
git commit -m "feat: add model provider registry and usage metering"
```

### Task 7: Add usage query API

**Files:**

- Modify: `backend/app/routes/transcripts.py`
- Test: `backend/tests/test_model_provider_usage.py`

- [ ] **Step 1: Add failing API test**

Append to `backend/tests/test_model_provider_usage.py`:

```python
from app.usage import UsageMeterService


def test_get_run_usage_returns_usage_rows(client, session):
    UsageMeterService(session).record_usage(
        tenant_id="tenant_demo",
        workspace_id="workspace_default",
        user_id="user_demo",
        thread_id="thread_001",
        run_id="run_usage_api",
        model_call_id="model_call_001",
        provider_id="bailian",
        model_id="qwen-plus",
        prompt_tokens=10,
        completion_tokens=20,
        latency_ms=300,
        status="completed",
    )

    response = client.get("/api/runs/run_usage_api/usage")

    assert response.status_code == 200
    data = response.json()
    assert data["run_id"] == "run_usage_api"
    assert data["usage"][0]["total_tokens"] == 30
    assert data["usage"][0]["provider_id"] == "bailian"
```

- [ ] **Step 2: Run tests and verify failure**

Run:

```bash
cd /Users/daniel/Desktop/code/工作台/workbench-app/frontend-v2/backend
pytest tests/test_model_provider_usage.py::test_get_run_usage_returns_usage_rows -q
```

Expected:

```text
404 Not Found for /api/runs/{run_id}/usage
```

- [ ] **Step 3: Implement route**

In `backend/app/routes/transcripts.py`, import:

```python
from app.models import TranscriptEvent, UsageMeter
```

Add:

```python
@run_router.get("/{run_id}/usage")
def get_run_usage(run_id: str, session: Session = Depends(get_session)) -> dict[str, object]:
    rows = session.scalars(
        select(UsageMeter).where(UsageMeter.run_id == run_id).order_by(UsageMeter.created_at.asc())
    ).all()
    return {
        "run_id": run_id,
        "usage": [
            {
                "usage_id": row.usage_id,
                "provider_id": row.provider_id,
                "model_id": row.model_id,
                "prompt_tokens": row.prompt_tokens,
                "completion_tokens": row.completion_tokens,
                "total_tokens": row.total_tokens,
                "latency_ms": row.latency_ms,
                "status": row.status,
                "created_at": row.created_at.isoformat() if row.created_at else None,
            }
            for row in rows
        ],
    }
```

- [ ] **Step 4: Run tests**

Run:

```bash
cd /Users/daniel/Desktop/code/工作台/workbench-app/frontend-v2/backend
pytest tests/test_model_provider_usage.py -q
```

Expected:

```text
all tests passed
```

- [ ] **Step 5: Commit**

```bash
git add backend/app/routes/transcripts.py backend/tests/test_model_provider_usage.py
git commit -m "feat: expose run usage API"
```

### Task 8: Final backend regression and readiness update

**Files:**

- Modify: `docs/phase1b-development-readiness-review.md`
- Modify: `docs/full-platform-development-gap-analysis.md`

- [ ] **Step 1: Run backend regression**

Run:

```bash
cd /Users/daniel/Desktop/code/工作台/workbench-app/frontend-v2/backend
pytest -q
```

Expected:

```text
all tests passed
```

- [ ] **Step 2: Run Python compile check**

Run:

```bash
cd /Users/daniel/Desktop/code/工作台/workbench-app/frontend-v2
python3 -m py_compile backend/app/*.py backend/app/routes/*.py
```

Expected:

```text
no output and exit code 0
```

- [ ] **Step 3: Run frontend smoke test without code changes**

Run:

```bash
cd /Users/daniel/Desktop/code/工作台/workbench-app/frontend-v2
npm test -- --run
```

Expected:

```text
all frontend tests passed
```

If frontend tests fail because of unrelated existing test drift, do not modify frontend automatically. Record the exact failure and ask for confirmation before changing frontend code.

- [ ] **Step 4: Update readiness documents**

In `docs/phase1b-development-readiness-review.md`, mark Phase A backend prerequisites as implemented:

```text
Agent Runtime 完整化：已具备开发验收基础
TranscriptEvent：已实现
ToolResult 标准：已实现
Run 状态机：已实现
UsageMeter：已实现
```

In `docs/full-platform-development-gap-analysis.md`, move these Phase A items from gap list to completed baseline.

- [ ] **Step 5: Commit**

```bash
git add docs/phase1b-development-readiness-review.md docs/full-platform-development-gap-analysis.md
git commit -m "docs: mark phase a runtime baseline complete"
```

## 6. Phase A Acceptance Checklist

Phase A is complete only if all checks pass:

- [ ] `pytest -q` passes under `backend/`.
- [ ] `python3 -m py_compile backend/app/*.py backend/app/routes/*.py` passes.
- [ ] Existing frontend history loading still uses `Message` and is not broken.
- [ ] A new Agent run creates:
  - [ ] one `Run`
  - [ ] one user `Message`
  - [ ] one assistant `Message`
  - [ ] at least three `TranscriptEvent` rows: `user.message`, `assistant.reasoning`, `assistant.message.completed`
  - [ ] relevant `RuntimeEvent` rows
- [ ] A tool run creates:
  - [ ] `assistant.tool_call`
  - [ ] `tool.result`
  - [ ] `ToolInvocation`
  - [ ] `StandardToolResult.to_model_message()` compatible payload
- [ ] A model-backed run creates one `UsageMeter` row.
- [ ] Cancelling a completed Run returns HTTP 409.
- [ ] Retrying a Run creates a new Run and does not mutate the original terminal Run.

## 7. Frontend Impact Assessment

Phase A should not require frontend changes.

Known frontend compatibility rules:

- Keep `GET /api/threads` response shape unchanged.
- Keep `GET /api/threads/{thread_id}` response shape unchanged.
- Keep `/api/agent/run/stream` behavior compatible with current assistant-ui page.
- Do not migrate frontend to TranscriptEvent in Phase A.
- Do not change right-side business panel behavior in Phase A.

If frontend changes become necessary, stop and report:

```text
1. 哪个现有接口不兼容
2. 需要改哪个前端文件
3. 用户会看到什么变化
4. 是否可以后端兼容避免前端修改
```

Only proceed after confirmation.

## 8. Development Readiness Review

### Meets development conditions

Phase A is ready for implementation because:

- Existing backend has FastAPI, SQLAlchemy, SQLite, pytest foundation.
- Existing tables already cover Thread, Message, Run, RuntimeEvent, ModelCall, ToolInvocation.
- Missing pieces are additive and can be implemented without destructive migration.
- Frontend can remain on current Message projection while backend adds TranscriptEvent.
- The task can be split into independently testable commits.

### Risks

| Risk | Impact | Mitigation |
| --- | --- | --- |
| SQLite concurrent sequence assignment may race | Low in local MVP; Medium later | Phase A single-user/local acceptable; Phase B/C can add DB lock or sequence table |
| Dual-write inconsistency between Message and TranscriptEvent | Medium | Write tests for every run path; keep Message as projection until migration |
| Model provider returns different usage schema | Medium | Treat missing usage as 0; normalize provider-specific usage later |
| Runtime route direct status mutation may remain in unreviewed paths | Medium | Add tests for cancel/retry/complete/fail |
| Frontend may later need TranscriptEvent projection | Medium | Defer to Phase H after backend event contract stabilizes |

### Not in development conditions for Phase A

These are intentionally excluded and must not block Phase A:

- Full plugin center.
- Self-built approval center.
- Enterprise SSO/IAM.
- Business connector permissions.
- Right-side Artifact renderer migration.
- Frontend assistant-ui runtime migration.

## 9. Recommended Commit Order

```text
feat: add transcript and usage persistence
feat: expose transcript query APIs
feat: standardize tool result contract
feat: enforce run state transitions
feat: dual write runtime transcript events
feat: add model provider registry and usage metering
feat: expose run usage API
docs: mark phase a runtime baseline complete
```

## 10. Execution Handoff

Implementation should use inline execution in this thread unless the user explicitly asks for subagents.

Recommended next command sequence before starting implementation:

```bash
cd /Users/daniel/Desktop/code/工作台/workbench-app/frontend-v2
git status --short
cd backend
pytest -q
```

If the baseline tests fail before implementation, fix or document the baseline failure first. Do not start Phase A changes on top of a failing baseline without recording the failure.
