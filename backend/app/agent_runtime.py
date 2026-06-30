import json
import os
import re
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.llm import DEFAULT_BASE_URL, DEFAULT_MODEL, load_local_env, model_configured
from app.models import AgentMemory, Artifact, AuditEvent, Message, ModelCall, Run, RuntimeEvent, Thread, ToolInvocation
from app.repositories import append_runtime_event


ModelClient = Callable[[str], dict[str, Any]]
ToolAwareModelClient = Callable[[str, list[dict[str, Any]]], dict[str, Any]]
ModelMessagesClient = Callable[[list[dict[str, Any]], list[dict[str, Any]] | None], dict[str, Any]]
ModelDeltaCallback = Callable[[str], None]
StreamingModelClient = Callable[[str, ModelDeltaCallback], dict[str, Any]]
ToolAwareStreamingModelClient = Callable[[str, list[dict[str, Any]], ModelDeltaCallback], dict[str, Any]]
IntentClassifier = Callable[[str], dict[str, object]]
RuntimeEventCallback = Callable[[RuntimeEvent], None]
CancelChecker = Callable[[], bool]


class RunCancelledError(Exception):
    pass


def classify_text(text: str) -> dict[str, object]:
    if "失败工具" in text or "触发失败" in text:
        return {
            "intent": "tool_failure_test",
            "confidence": 0.99,
            "required_capabilities": ["diagnostic.check"],
            "risk_hint": "L0",
            "needs_clarification": False,
        }
    if "权限" in text or "申请" in text:
        return {
            "intent": "permission_request",
            "confidence": 0.85,
            "required_capabilities": ["approval.request"],
            "risk_hint": "L1",
            "needs_clarification": False,
        }
    if "保费" in text or "惠民保" in text or "数仓" in text or "指标" in text:
        return {
            "intent": "business_plugin_required",
            "confidence": 0.9,
            "required_capabilities": ["plugin.catalog"],
            "risk_hint": "L1",
            "needs_clarification": False,
            "message": "业务插件将在二阶段启用",
        }
    if "读取" in text and ("记忆" in text or "偏好" in text):
        return {
            "intent": "memory_read",
            "confidence": 0.84,
            "required_capabilities": ["memory.read"],
            "risk_hint": "L0",
            "needs_clarification": False,
        }
    if "记住" in text or "偏好" in text:
        return {
            "intent": "memory_write",
            "confidence": 0.82,
            "required_capabilities": ["memory.write"],
            "risk_hint": "L0",
            "needs_clarification": False,
        }
    if "诊断" in text or "检查服务端" in text:
        return {
            "intent": "diagnostic_check",
            "confidence": 0.86,
            "required_capabilities": ["diagnostic.check"],
            "risk_hint": "L0",
            "needs_clarification": False,
        }
    if "设置" in text or "模型配置" in text:
        return {
            "intent": "settings_help",
            "confidence": 0.84,
            "required_capabilities": ["settings.read"],
            "risk_hint": "L0",
            "needs_clarification": False,
        }
    if (
        "本地分析" in text
        or "分析这组" in text
        or "分析数据" in text
        or "统计这组" in text
        or ("平均" in text and "保费" not in text and "惠民保" not in text and "数仓" not in text)
    ):
        return {
            "intent": "local_data_analysis",
            "confidence": 0.83,
            "required_capabilities": ["local_data.analyze"],
            "risk_hint": "L0",
            "needs_clarification": False,
        }
    if "更新" in text and ("产物" in text or "Artifact" in text or "计划" in text):
        return {
            "intent": "artifact_update",
            "confidence": 0.82,
            "required_capabilities": ["artifact.update"],
            "risk_hint": "L0",
            "needs_clarification": False,
        }
    if "读取" in text and "文件" in text:
        return {
            "intent": "workspace_read",
            "confidence": 0.84,
            "required_capabilities": ["workspace.read"],
            "risk_hint": "L0",
            "needs_clarification": False,
        }
    if "工作空间" in text or "文件" in text:
        return {
            "intent": "workspace_file_task",
            "confidence": 0.82,
            "required_capabilities": ["workspace.list"],
            "risk_hint": "L0",
            "needs_clarification": False,
        }
    if "计划" in text or "拆解" in text or "步骤" in text or "验收" in text or "规划" in text:
        return {
            "intent": "plan",
            "confidence": 0.86,
            "required_capabilities": ["plan.update"],
            "risk_hint": "L0",
            "needs_clarification": False,
        }
    if "总结" in text:
        return {
            "intent": "summarize",
            "confidence": 0.8,
            "required_capabilities": ["conversation.respond"],
            "risk_hint": "L0",
            "needs_clarification": False,
        }
    if "改写" in text or "润色" in text:
        return {
            "intent": "rewrite",
            "confidence": 0.8,
            "required_capabilities": ["conversation.respond"],
            "risk_hint": "L0",
            "needs_clarification": False,
        }
    return {
        "intent": "general_chat",
        "confidence": 0.75,
        "required_capabilities": [],
        "risk_hint": "L0",
        "needs_clarification": False,
    }


@dataclass(frozen=True)
class ToolDefinition:
    name: str
    display_name: str
    description: str
    input_schema: dict[str, Any]
    output_schema: dict[str, Any]
    read_only: bool
    destructive: bool
    concurrency_safe: bool
    interrupt_behavior: str
    risk_tier: str
    permission_policy: str
    timeout_seconds: int
    max_result_size_chars: int
    progress_event_schema: dict[str, Any] = field(default_factory=dict)
    artifact_schema: dict[str, Any] = field(default_factory=dict)
    ui_renderer_hint: str | None = None


@dataclass
class AgentRunInput:
    tenant_id: str
    workspace_id: str
    thread_id: str
    user_id: str
    message: str


@dataclass
class ToolExecutionContext:
    session: Session
    request: AgentRunInput
    run_id: str
    intent: str
    cancel_checker: CancelChecker | None = None
    tool_input: dict[str, Any] = field(default_factory=dict)
    memory_context: list[dict[str, Any]] = field(default_factory=list)
    conversation_context: list[dict[str, str]] = field(default_factory=list)

    def raise_if_cancelled(self) -> None:
        if self.cancel_checker is not None and self.cancel_checker():
            raise RunCancelledError


@dataclass
class ToolExecutionResult:
    tool_id: str
    status: str = "completed"
    response_text: str = ""
    output_payload: dict[str, Any] = field(default_factory=dict)
    artifacts: list[Artifact] = field(default_factory=list)
    memory_ids: list[str] = field(default_factory=list)
    audit_event_id: str | None = None
    artifact_event_type: str = "artifact.created"
    include_artifact_invocation: bool = True


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, ToolDefinition] = {}
        self._handlers: dict[str, Callable[[ToolExecutionContext], ToolExecutionResult]] = {}

    def register(
        self,
        definition: ToolDefinition,
        handler: Callable[[ToolExecutionContext], ToolExecutionResult],
    ) -> None:
        self._tools[definition.name] = definition
        self._handlers[definition.name] = handler

    def get(self, tool_id: str) -> ToolDefinition:
        return self._tools[tool_id]

    def handler_for(self, tool_id: str) -> Callable[[ToolExecutionContext], ToolExecutionResult]:
        return self._handlers[tool_id]

    def list_visible(self) -> list[ToolDefinition]:
        return list(self._tools.values())


class PermissionGate:
    def allow(self, definition: ToolDefinition, context: ToolExecutionContext) -> tuple[bool, str]:
        _ = context
        if definition.destructive:
            return False, "destructive_tools_disabled_in_phase_one"
        if definition.risk_tier not in {"L0", "L1"}:
            return False, "risk_tier_not_allowed_in_phase_one"
        return True, "allowed"


class RuntimeEventStream:
    def __init__(
        self,
        session: Session,
        request: AgentRunInput,
        run_id: str,
        on_event: RuntimeEventCallback | None = None,
    ) -> None:
        self.session = session
        self.request = request
        self.run_id = run_id
        self.on_event = on_event

    def append(self, event_type: str, payload: dict[str, Any], *, key_suffix: str | None = None) -> RuntimeEvent:
        suffix = key_suffix or event_type
        event = append_runtime_event(
            self.session,
            tenant_id=self.request.tenant_id,
            workspace_id=self.request.workspace_id,
            thread_id=self.request.thread_id,
            run_id=self.run_id,
            event_type=event_type,
            actor=self.request.user_id,
            payload=payload,
            idempotency_key=f"{self.run_id}:{suffix}",
        )
        if self.on_event is not None:
            self.on_event(event)
        return event


class ArtifactService:
    def create(
        self,
        session: Session,
        request: AgentRunInput,
        run_id: str,
        *,
        artifact_type: str,
        title: str,
        content: dict[str, Any],
    ) -> Artifact:
        artifact = Artifact(
            artifact_id=f"art_{uuid.uuid4().hex}",
            tenant_id=request.tenant_id,
            workspace_id=request.workspace_id,
            thread_id=request.thread_id,
            run_id=run_id,
            artifact_type=artifact_type,
            title=title,
            content_json=json.dumps(content, ensure_ascii=False),
        )
        session.add(artifact)
        session.commit()
        return artifact


class MemoryService:
    def write_preference(self, context: ToolExecutionContext) -> AgentMemory:
        memory = AgentMemory(
            memory_id=f"mem_{uuid.uuid4().hex}",
            tenant_id=context.request.tenant_id,
            workspace_id=context.request.workspace_id,
            memory_type="user_preference",
            content_json=json.dumps({"text": context.request.message.replace("记住：", "").strip()}, ensure_ascii=False),
            data_classification="internal",
        )
        context.session.add(memory)
        context.session.commit()
        return memory

    def read_workspace_memories(self, context: ToolExecutionContext) -> list[dict[str, Any]]:
        return self.read_workspace_memories_for_request(context.session, context.request)

    def read_workspace_memories_for_request(self, session: Session, request: AgentRunInput) -> list[dict[str, Any]]:
        memories = session.scalars(
            select(AgentMemory)
            .where(
                AgentMemory.tenant_id == request.tenant_id,
                AgentMemory.workspace_id == request.workspace_id,
            )
            .order_by(AgentMemory.memory_id.asc())
        ).all()
        return [
            {
                "memory_id": memory.memory_id,
                "memory_type": memory.memory_type,
                "content": json.loads(memory.content_json),
                "data_classification": memory.data_classification,
            }
            for memory in memories[-10:]
        ]


class ToolExecutionService:
    def __init__(self, registry: ToolRegistry, permission_gate: PermissionGate) -> None:
        self.registry = registry
        self.permission_gate = permission_gate

    def execute(
        self,
        context: ToolExecutionContext,
        event_stream: RuntimeEventStream,
        tool_id: str,
        *,
        call_id: str | None = None,
        tool_input: dict[str, Any] | None = None,
    ) -> ToolExecutionResult:
        context.raise_if_cancelled()
        definition = self.registry.get(tool_id)
        event_suffix = call_id or tool_id
        previous_tool_input = context.tool_input
        context.tool_input = tool_input or {}
        event_stream.append(
            "tool.planned",
            {
                "tool_id": tool_id,
                "input_keys": sorted(context.tool_input.keys()),
                **({"tool_call_id": call_id} if call_id else {}),
            },
            key_suffix=f"tool.planned:{event_suffix}",
        )
        context.raise_if_cancelled()
        validation_error = self._validate_tool_input(definition, context.tool_input)
        if validation_error:
            event_stream.append(
                "tool.failed",
                {
                    "tool_id": tool_id,
                    "reason": "invalid_tool_arguments",
                    "validation_error": validation_error,
                    **({"tool_call_id": call_id} if call_id else {}),
                },
                key_suffix=f"tool.failed:{event_suffix}",
            )
            context.tool_input = previous_tool_input
            return ToolExecutionResult(
                tool_id=tool_id,
                status="failed",
                response_text=f"工具 {tool_id} 参数校验失败：{validation_error}。",
                output_payload={"error": "invalid_tool_arguments", "validation_error": validation_error},
            )
        allowed, reason = self.permission_gate.allow(definition, context)
        if not allowed:
            event_stream.append(
                "policy.denied",
                {"tool_id": tool_id, "reason": reason, **({"tool_call_id": call_id} if call_id else {})},
                key_suffix=f"policy.denied:{event_suffix}",
            )
            context.tool_input = previous_tool_input
            return ToolExecutionResult(
                tool_id=tool_id,
                status="blocked",
                response_text=f"工具 {tool_id} 未通过权限校验：{reason}。",
                output_payload={"reason": reason},
            )

        event_stream.append(
            "tool.started",
            {"tool_id": tool_id, **({"tool_call_id": call_id} if call_id else {})},
            key_suffix=f"tool.started:{event_suffix}",
        )
        context.raise_if_cancelled()
        result = self.registry.handler_for(tool_id)(context)
        context.raise_if_cancelled()
        if result.status == "failed":
            event_stream.append(
                "tool.failed",
                {"tool_id": tool_id, **({"tool_call_id": call_id} if call_id else {}), **result.output_payload},
                key_suffix=f"tool.failed:{event_suffix}",
            )
            context.tool_input = previous_tool_input
            return result

        self._record_invocation(context, tool_id, result)
        event_stream.append(
            "tool.completed",
            {"tool_id": tool_id, **({"tool_call_id": call_id} if call_id else {}), **result.output_payload},
            key_suffix=f"tool.completed:{event_suffix}",
        )
        for artifact in result.artifacts:
            artifact_event = event_stream.append(
                result.artifact_event_type,
                {
                    "artifact_id": artifact.artifact_id,
                    "artifact_type": artifact.artifact_type,
                    **({"revision": 2} if result.artifact_event_type == "artifact.updated" else {}),
                },
                key_suffix=f"{result.artifact_event_type}:{artifact.artifact_id}",
            )
            artifact.source_event_id = artifact_event.event_id
            result.audit_event_id = result.audit_event_id or artifact_event.event_id
        context.session.commit()
        context.tool_input = previous_tool_input
        return result

    def _record_invocation(self, context: ToolExecutionContext, tool_id: str, result: ToolExecutionResult) -> None:
        context.session.add(
            ToolInvocation(
                invocation_id=f"toolinv_{uuid.uuid4().hex}",
                tenant_id=context.request.tenant_id,
                workspace_id=context.request.workspace_id,
                thread_id=context.request.thread_id,
                run_id=context.run_id,
                tool_id=tool_id,
                status=result.status,
                input_json=json.dumps(
                    {"message": context.request.message, "tool_input": context.tool_input},
                    ensure_ascii=False,
                ),
                output_json=json.dumps(result.output_payload, ensure_ascii=False),
            )
        )
        context.session.commit()

    def _validate_tool_input(self, definition: ToolDefinition, tool_input: dict[str, Any]) -> str | None:
        schema = definition.input_schema or {"type": "object"}
        if schema.get("type", "object") != "object":
            return "input_schema_root_must_be_object"
        required = schema.get("required") or []
        if isinstance(required, list):
            for key in required:
                if isinstance(key, str) and key not in tool_input:
                    return f"missing_required_field:{key}"
        properties = schema.get("properties") or {}
        if isinstance(properties, dict):
            for key, value in tool_input.items():
                if key not in properties:
                    if schema.get("additionalProperties") is False:
                        return f"unexpected_field:{key}"
                    continue
                expected = properties[key]
                if isinstance(expected, dict):
                    expected_type = expected.get("type")
                    if expected_type and not self._matches_json_type(value, str(expected_type)):
                        return f"invalid_type:{key}:expected_{expected_type}"
        return None

    def _matches_json_type(self, value: Any, expected_type: str) -> bool:
        if expected_type == "string":
            return isinstance(value, str)
        if expected_type == "integer":
            return isinstance(value, int) and not isinstance(value, bool)
        if expected_type == "number":
            return (isinstance(value, int | float)) and not isinstance(value, bool)
        if expected_type == "boolean":
            return isinstance(value, bool)
        if expected_type == "object":
            return isinstance(value, dict)
        if expected_type == "array":
            return isinstance(value, list)
        return True


class ToolPoolAssembler:
    def __init__(self, registry: ToolRegistry) -> None:
        self.registry = registry

    def tool_for_intent(self, intent: str) -> str | None:
        return {
            "plan": "plan.update",
            "memory_write": "memory.write",
            "memory_read": "memory.read",
            "workspace_file_task": "workspace.list",
            "workspace_read": "workspace.read",
            "settings_help": "settings.read",
            "local_data_analysis": "local_data.analyze",
            "diagnostic_check": "diagnostic.check",
            "tool_failure_test": "diagnostic.check",
            "artifact_update": "artifact.update",
            "business_plugin_required": "plugin.catalog",
        }.get(intent)


class QueryLoop:
    def __init__(
        self,
        tool_pool: ToolPoolAssembler,
        tool_executor: ToolExecutionService,
        model_client: ModelClient,
        model_tool_client: ToolAwareModelClient | None = None,
        model_messages_client: ModelMessagesClient | None = None,
        model_stream_client: StreamingModelClient | None = None,
        model_stream_tool_client: ToolAwareStreamingModelClient | None = None,
        max_turns: int = 8,
    ) -> None:
        self.tool_pool = tool_pool
        self.tool_executor = tool_executor
        self.model_client = model_client
        self.model_tool_client = model_tool_client
        self.model_messages_client = model_messages_client
        self.model_stream_client = model_stream_client
        self.model_stream_tool_client = model_stream_tool_client
        self.max_turns = max_turns

    def run(self, context: ToolExecutionContext, event_stream: RuntimeEventStream) -> dict[str, Any]:
        context.raise_if_cancelled()
        tool_invocations = ["intent.classify"]
        artifacts: list[dict[str, object]] = []
        memory_ids: list[str] = []
        status = "completed"
        audit_event_id: str | None = None

        tool_id = self.tool_pool.tool_for_intent(context.intent)
        if tool_id:
            try:
                result = self.tool_executor.execute(context, event_stream, tool_id)
            except RunCancelledError:
                return {
                    "status": "cancelled",
                    "response_text": "运行已取消。",
                    "tool_invocations": tool_invocations,
                    "artifacts": artifacts,
                    "memory_ids": memory_ids,
                    "audit_event_id": audit_event_id,
                }
            status = result.status
            response_text = result.response_text
            tool_invocations.append(tool_id)
            if result.artifacts and result.include_artifact_invocation:
                tool_invocations.append("artifact.create")
            artifacts = [
                {
                    "artifact_id": artifact.artifact_id,
                    "artifact_type": artifact.artifact_type,
                    "title": artifact.title,
                }
                for artifact in result.artifacts
            ]
            memory_ids = result.memory_ids
            audit_event_id = result.audit_event_id
        else:
            context.raise_if_cancelled()
            event_stream.append("model.selected", {"router": "openai-compatible"}, key_suffix="model.selected")
            event_stream.append(
                "model.started",
                {"message_length": len(context.request.message)},
                key_suffix="model.started",
            )
            model_input = self._build_model_input(context)
            try:
                if self.model_stream_client is not None or self.model_stream_tool_client is not None:
                    def emit_delta(delta: str) -> None:
                        context.raise_if_cancelled()
                        event_stream.append(
                            "model.delta",
                            {"delta": delta},
                            key_suffix=f"model.delta:{uuid.uuid4().hex}",
                        )
                        context.raise_if_cancelled()

                    if self.model_stream_tool_client is not None:
                        model_result = self.model_stream_tool_client(model_input, self._model_tool_specs(), emit_delta)
                    else:
                        model_result = self.model_stream_client(model_input, emit_delta)  # type: ignore[misc]
                else:
                    context.raise_if_cancelled()
                    if self.model_tool_client is not None:
                        model_result = self.model_tool_client(model_input, self._model_tool_specs())
                    else:
                        model_result = self.model_client(model_input)
                context.raise_if_cancelled()
            except RunCancelledError:
                return {
                    "status": "cancelled",
                    "response_text": "运行已取消。",
                    "tool_invocations": tool_invocations,
                    "artifacts": artifacts,
                    "memory_ids": memory_ids,
                    "audit_event_id": audit_event_id,
                }
            self._record_model_call(context, model_result, input_text=model_input)
            tool_calls = self._extract_tool_calls(model_result)
            if tool_calls:
                tool_loop_result = self._run_model_tool_calls(
                    context,
                    event_stream,
                    model_input,
                    model_result,
                    tool_calls,
                    tool_invocations,
                )
                status = str(tool_loop_result["status"])
                response_text = str(tool_loop_result["response_text"])
                artifacts = list(tool_loop_result["artifacts"])
                memory_ids = list(tool_loop_result["memory_ids"])
                audit_event_id = tool_loop_result["audit_event_id"]
            else:
                response_text = str(model_result["message"])
            event_stream.append(
                "model.completed",
                {"provider": model_result.get("provider"), "model": model_result.get("model")},
                key_suffix="model.completed",
            )

        return {
            "status": status,
            "response_text": response_text,
            "tool_invocations": tool_invocations,
            "artifacts": artifacts,
            "memory_ids": memory_ids,
            "audit_event_id": audit_event_id,
        }

    def _run_model_tool_calls(
        self,
        context: ToolExecutionContext,
        event_stream: RuntimeEventStream,
        model_input: str,
        model_result: dict[str, Any],
        tool_calls: list[dict[str, Any]],
        tool_invocations: list[str],
    ) -> dict[str, Any]:
        artifacts: list[dict[str, object]] = []
        memory_ids: list[str] = []
        audit_event_id: str | None = None
        current_model_result = model_result
        current_tool_calls = tool_calls
        followup_messages: list[dict[str, Any]] | None = None

        for turn_index in range(self.max_turns):
            event_stream.append(
                "model.tool_calls.requested",
                {
                    "turn_index": turn_index,
                    "tool_count": len(current_tool_calls),
                    "tool_ids": [str(tool_call["name"]) for tool_call in current_tool_calls],
                },
                key_suffix=f"model.tool_calls.requested:{turn_index}",
            )

            tool_results: list[dict[str, Any]] = []
            status = "completed"
            stop_current_turn = False
            for batch_index, batch in enumerate(self._partition_tool_calls(current_tool_calls)):
                batch_mode = "concurrent_safe" if self._is_concurrency_safe_batch(batch) else "serial"
                batch_id = f"{turn_index}:{batch_index}"
                event_stream.append(
                    "tool.batch.started",
                    {
                        "turn_index": turn_index,
                        "batch_index": batch_index,
                        "execution_mode": batch_mode,
                        "tool_count": len(batch),
                        "tool_ids": [str(tool_call["name"]) for tool_call in batch],
                    },
                    key_suffix=f"tool.batch.started:{batch_id}",
                )
                for index, tool_call in enumerate(batch):
                    context.raise_if_cancelled()
                    tool_id = str(tool_call["name"])
                    call_id = str(tool_call.get("id") or f"toolcall_{turn_index + 1}_{batch_index + 1}_{index + 1}")
                    try:
                        result = self.tool_executor.execute(
                            context,
                            event_stream,
                            tool_id,
                            call_id=call_id,
                            tool_input=tool_call.get("arguments") if isinstance(tool_call.get("arguments"), dict) else {},
                        )
                    except KeyError:
                        status = "failed"
                        tool_results.append(
                            {
                                "tool_call_id": call_id,
                                "tool_id": tool_id,
                                "status": "failed",
                                "output": {"error": "unknown_tool"},
                            }
                        )
                        event_stream.append(
                            "tool.failed",
                            {"tool_id": tool_id, "tool_call_id": call_id, "error": "unknown_tool"},
                            key_suffix=f"tool.failed:{call_id}",
                        )
                        stop_current_turn = True
                        break
                    tool_invocations.append(tool_id)
                    if result.artifacts and result.include_artifact_invocation and "artifact.create" not in tool_invocations:
                        tool_invocations.append("artifact.create")
                    artifacts.extend(self._artifact_summaries(result.artifacts))
                    memory_ids.extend(result.memory_ids)
                    audit_event_id = audit_event_id or result.audit_event_id
                    status = result.status
                    tool_results.append(
                        {
                            "tool_call_id": call_id,
                            "tool_id": tool_id,
                            "status": result.status,
                            "output": result.output_payload,
                            "response_text": result.response_text,
                        }
                    )
                    if result.status in {"failed", "blocked"}:
                        stop_current_turn = True
                        break
                event_stream.append(
                    "tool.batch.completed",
                    {
                        "turn_index": turn_index,
                        "batch_index": batch_index,
                        "execution_mode": batch_mode,
                        "status": status,
                        "tool_result_count": len(tool_results),
                    },
                    key_suffix=f"tool.batch.completed:{batch_id}",
                )
                if stop_current_turn:
                    break

            event_stream.append(
                "model.tool_results.appended",
                {"turn_index": turn_index, "tool_result_count": len(tool_results), "status": status},
                key_suffix=f"model.tool_results.appended:{turn_index}",
            )
            if status in {"failed", "blocked"}:
                fallback_text = tool_results[-1].get("response_text") if tool_results else ""
                return {
                    "status": status,
                    "response_text": fallback_text or "工具调用未完成。",
                    "artifacts": artifacts,
                    "memory_ids": memory_ids,
                    "audit_event_id": audit_event_id,
                }

            if followup_messages is None:
                followup_messages = self._build_tool_result_followup_messages(
                    model_input=model_input,
                    model_result=current_model_result,
                    tool_calls=current_tool_calls,
                    tool_results=tool_results,
                )
            else:
                self._append_tool_result_followup_messages(
                    followup_messages,
                    model_result=current_model_result,
                    tool_calls=current_tool_calls,
                    tool_results=tool_results,
                )
            context.raise_if_cancelled()
            if self.model_messages_client is not None:
                followup_result = self.model_messages_client(followup_messages, None)
                followup_input: str | list[dict[str, Any]] = followup_messages
            else:
                followup_input = self._build_tool_result_followup_input(
                    model_input=model_input,
                    model_result=current_model_result,
                    tool_results=tool_results,
                )
                followup_result = self.model_client(followup_input)
            context.raise_if_cancelled()
            self._record_model_call(context, followup_result, input_text=followup_input)
            next_tool_calls = self._extract_tool_calls(followup_result)
            if not next_tool_calls:
                return {
                    "status": "completed",
                    "response_text": str(followup_result.get("message") or "工具已执行，但模型未返回最终回复。"),
                    "artifacts": artifacts,
                    "memory_ids": memory_ids,
                    "audit_event_id": audit_event_id,
                }
            current_model_result = followup_result
            current_tool_calls = next_tool_calls

        return {
            "status": "failed",
            "response_text": f"工具调用超过最大轮次 {self.max_turns}，已中止。",
            "artifacts": artifacts,
            "memory_ids": memory_ids,
            "audit_event_id": audit_event_id,
        }

    def _partition_tool_calls(self, tool_calls: list[dict[str, Any]]) -> list[list[dict[str, Any]]]:
        batches: list[list[dict[str, Any]]] = []
        for tool_call in tool_calls:
            if self._is_concurrency_safe_tool_call(tool_call) and batches and self._is_concurrency_safe_batch(batches[-1]):
                batches[-1].append(tool_call)
            else:
                batches.append([tool_call])
        return batches

    def _is_concurrency_safe_batch(self, tool_calls: list[dict[str, Any]]) -> bool:
        return bool(tool_calls) and all(self._is_concurrency_safe_tool_call(tool_call) for tool_call in tool_calls)

    def _is_concurrency_safe_tool_call(self, tool_call: dict[str, Any]) -> bool:
        try:
            definition = self.tool_pool.registry.get(str(tool_call["name"]))
        except KeyError:
            return False
        return definition.read_only and definition.concurrency_safe and not definition.destructive

    def _extract_tool_calls(self, model_result: dict[str, Any]) -> list[dict[str, Any]]:
        raw_tool_calls = model_result.get("tool_calls")
        if not isinstance(raw_tool_calls, list):
            return []
        tool_calls: list[dict[str, Any]] = []
        for index, raw_call in enumerate(raw_tool_calls):
            if not isinstance(raw_call, dict):
                continue
            name = raw_call.get("name") or raw_call.get("tool_id")
            if not isinstance(name, str) or not name:
                continue
            name = self._api_tool_name_to_tool_id(name)
            arguments = raw_call.get("arguments")
            tool_calls.append(
                {
                    "id": raw_call.get("id") or f"toolcall_{index + 1}",
                    "name": name,
                    "arguments": arguments if isinstance(arguments, dict) else {},
                }
            )
        return tool_calls

    def _build_tool_result_followup_input(
        self,
        *,
        model_input: str,
        model_result: dict[str, Any],
        tool_results: list[dict[str, Any]],
    ) -> str:
        return (
            model_input
            + "\n\n模型已请求工具调用。请根据以下工具调用结果生成最终回复，不要编造未返回的数据。\n"
            + "模型工具调用说明："
            + str(model_result.get("message") or "")
            + "\n工具调用结果："
            + json.dumps(tool_results, ensure_ascii=False)
        )

    def _build_tool_result_followup_messages(
        self,
        *,
        model_input: str,
        model_result: dict[str, Any],
        tool_calls: list[dict[str, Any]],
        tool_results: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        assistant_tool_calls = []
        for tool_call in tool_calls:
            assistant_tool_calls.append(
                {
                    "id": str(tool_call.get("id") or f"toolcall_{len(assistant_tool_calls) + 1}"),
                    "type": "function",
                    "function": {
                        "name": self._tool_id_to_api_tool_name(str(tool_call["name"])),
                        "arguments": json.dumps(tool_call.get("arguments") or {}, ensure_ascii=False),
                    },
                }
            )
        messages: list[dict[str, Any]] = [
            {
                "role": "system",
                "content": "你是公司工作台 Agent。根据工具返回结果生成最终回复；不得编造未返回的数据。",
            },
            {"role": "user", "content": model_input},
            {
                "role": "assistant",
                "content": str(model_result.get("message") or ""),
                "tool_calls": assistant_tool_calls,
            },
        ]
        for tool_result in tool_results:
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": str(tool_result["tool_call_id"]),
                    "name": self._tool_id_to_api_tool_name(str(tool_result["tool_id"])),
                    "content": json.dumps(tool_result, ensure_ascii=False),
                }
            )
        return messages

    def _append_tool_result_followup_messages(
        self,
        messages: list[dict[str, Any]],
        *,
        model_result: dict[str, Any],
        tool_calls: list[dict[str, Any]],
        tool_results: list[dict[str, Any]],
    ) -> None:
        assistant_tool_calls = []
        for tool_call in tool_calls:
            assistant_tool_calls.append(
                {
                    "id": str(tool_call.get("id") or f"toolcall_{len(assistant_tool_calls) + 1}"),
                    "type": "function",
                    "function": {
                        "name": self._tool_id_to_api_tool_name(str(tool_call["name"])),
                        "arguments": json.dumps(tool_call.get("arguments") or {}, ensure_ascii=False),
                    },
                }
            )
        messages.append(
            {
                "role": "assistant",
                "content": str(model_result.get("message") or ""),
                "tool_calls": assistant_tool_calls,
            }
        )
        for tool_result in tool_results:
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": str(tool_result["tool_call_id"]),
                    "name": self._tool_id_to_api_tool_name(str(tool_result["tool_id"])),
                    "content": json.dumps(tool_result, ensure_ascii=False),
                }
            )

    def _artifact_summaries(self, artifacts: list[Artifact]) -> list[dict[str, object]]:
        return [
            {
                "artifact_id": artifact.artifact_id,
                "artifact_type": artifact.artifact_type,
                "title": artifact.title,
            }
            for artifact in artifacts
        ]

    def _model_tool_specs(self) -> list[dict[str, Any]]:
        specs: list[dict[str, Any]] = []
        for tool in self.tool_pool.registry.list_visible():
            specs.append(
                {
                    "type": "function",
                    "function": {
                        "name": self._tool_id_to_api_tool_name(tool.name),
                        "description": tool.description,
                        "parameters": tool.input_schema or {"type": "object"},
                    },
                }
            )
        return specs

    def _tool_id_to_api_tool_name(self, tool_id: str) -> str:
        return tool_id.replace(".", "__")

    def _api_tool_name_to_tool_id(self, api_name: str) -> str:
        if api_name in {tool.name for tool in self.tool_pool.registry.list_visible()}:
            return api_name
        candidate = api_name.replace("__", ".")
        if candidate in {tool.name for tool in self.tool_pool.registry.list_visible()}:
            return candidate
        return api_name

    def _build_model_input(self, context: ToolExecutionContext) -> str:
        if not context.memory_context and not context.conversation_context:
            return context.request.message
        sections: list[str] = []

        memory_lines = []
        for memory in context.memory_context:
            content = memory.get("content")
            text = content.get("text") if isinstance(content, dict) else None
            if text:
                memory_lines.append(f"- {memory.get('memory_type', 'memory')}: {text}")
        if memory_lines:
            sections.append(
                "以下是当前工作空间的受控记忆上下文，只用于改善回答风格和连续性；"
                "不得把它当作业务系统事实或权限依据。\n"
                + "\n".join(memory_lines)
            )

        conversation_lines = []
        for message in context.conversation_context:
            role = message.get("role", "message")
            content = message.get("content", "")
            if content:
                conversation_lines.append(f"- {role}: {content[:800]}")
        if conversation_lines:
            sections.append(
                "以下是同一会话的近期上下文，只用于理解连续对话；"
                "如与当前用户请求冲突，以当前请求为准。\n"
                + "\n".join(conversation_lines)
            )

        if not sections:
            return context.request.message
        return "\n\n".join(sections) + "\n\n用户请求：" + context.request.message

    def _record_model_call(self, context: ToolExecutionContext, model_result: dict[str, Any], *, input_text: str | list[dict[str, Any]] | None = None) -> None:
        context.session.add(
            ModelCall(
                model_call_id=f"modelcall_{uuid.uuid4().hex}",
                tenant_id=context.request.tenant_id,
                workspace_id=context.request.workspace_id,
                thread_id=context.request.thread_id,
                run_id=context.run_id,
                provider=model_result.get("provider", "unknown"),
                model=model_result.get("model", "unknown"),
                status="completed",
                input_json=json.dumps({"message": input_text or context.request.message}, ensure_ascii=False),
                output_json=json.dumps(model_result, ensure_ascii=False),
            )
        )
        context.session.commit()


class AgentSessionRuntime:
    def __init__(
        self,
        session: Session,
        *,
        intent_classifier: IntentClassifier,
        model_client: ModelClient,
        model_tool_client: ToolAwareModelClient | None = None,
        model_messages_client: ModelMessagesClient | None = None,
        model_stream_client: StreamingModelClient | None = None,
        model_stream_tool_client: ToolAwareStreamingModelClient | None = None,
        registry: ToolRegistry | None = None,
    ) -> None:
        self.session = session
        self.intent_classifier = intent_classifier
        self.registry = registry or create_default_tool_registry()
        self.memory_service = MemoryService()
        self.query_loop = QueryLoop(
            ToolPoolAssembler(self.registry),
            ToolExecutionService(self.registry, PermissionGate()),
            model_client,
            model_tool_client=model_tool_client,
            model_messages_client=model_messages_client,
            model_stream_client=model_stream_client,
            model_stream_tool_client=model_stream_tool_client,
        )

    def run(
        self,
        request: AgentRunInput,
        on_event: RuntimeEventCallback | None = None,
        *,
        run_id: str | None = None,
        cancel_checker: CancelChecker | None = None,
    ) -> dict[str, object]:
        self._ensure_thread(request)
        run_id = run_id or f"run_{uuid.uuid4().hex}"
        run = Run(
            run_id=run_id,
            tenant_id=request.tenant_id,
            workspace_id=request.workspace_id,
            thread_id=request.thread_id,
            user_id=request.user_id,
            status="running",
            question=request.message,
        )
        self.session.add(run)
        self.session.commit()

        event_stream = RuntimeEventStream(self.session, request, run_id, on_event=on_event)
        event_stream.append("run.created", {"message": request.message}, key_suffix="run.created")
        self._record_message(request, run_id, "user", request.message)
        event_stream.append(
            "message.received",
            {"message_length": len(request.message)},
            key_suffix="message.received",
        )

        intent_result = self.intent_classifier(request.message)
        intent = str(intent_result["intent"])
        event_stream.append("intent.classified", intent_result, key_suffix="intent.classified")
        memory_context: list[dict[str, Any]] = []
        conversation_context: list[dict[str, str]] = []
        if self.query_loop.tool_pool.tool_for_intent(intent) is None:
            memory_context = self.memory_service.read_workspace_memories_for_request(self.session, request)
            if memory_context:
                event_stream.append(
                    "memory.context.loaded",
                    {
                        "memory_count": len(memory_context),
                        "memory_scope": "workspace",
                        "memory_types": sorted({str(memory.get("memory_type")) for memory in memory_context}),
                    },
                    key_suffix="memory.context.loaded",
                )
            conversation_context = self._read_recent_thread_messages(request, run_id)
            if conversation_context:
                event_stream.append(
                    "conversation.context.loaded",
                    {
                        "message_count": len(conversation_context),
                        "thread_id": request.thread_id,
                    },
                    key_suffix="conversation.context.loaded",
                )
        event_stream.append(
            "context.built",
            {
                "workspace_id": request.workspace_id,
                "memory_scope": "workspace",
                "memory_count": len(memory_context),
                "conversation_message_count": len(conversation_context),
            },
            key_suffix="context.built",
        )

        context = ToolExecutionContext(
            self.session,
            request,
            run_id,
            intent,
            cancel_checker=cancel_checker,
            memory_context=memory_context,
            conversation_context=conversation_context,
        )
        loop_result = self.query_loop.run(context, event_stream)
        status = str(loop_result["status"])
        response_text = str(loop_result["response_text"])

        self._record_message(request, run_id, "assistant", response_text)
        run.status = status
        self.session.add(run)
        self.session.add(
            AuditEvent(
                audit_event_id=str(loop_result["audit_event_id"] or f"evt_{uuid.uuid4().hex}"),
                tenant_id=request.tenant_id,
                run_id=run_id,
                event_type=f"phase_one.agent.{status}",
                payload_json=json.dumps(
                    {"intent": intent, "tools": loop_result["tool_invocations"]},
                    ensure_ascii=False,
                ),
            )
        )
        self.session.commit()

        if status == "failed":
            final_event_type = "run.failed"
        elif status == "cancelled":
            final_event_type = "run.cancelled"
        else:
            final_event_type = "run.completed"
        completed_event = event_stream.append(final_event_type, {"status": status}, key_suffix=final_event_type)
        audit_event_id = str(loop_result["audit_event_id"] or completed_event.event_id)
        events = self.session.scalars(
            select(RuntimeEvent).where(RuntimeEvent.run_id == run_id).order_by(RuntimeEvent.occurred_at.asc())
        ).all()

        return {
            "run_id": run_id,
            "thread_id": request.thread_id,
            "workspace_id": request.workspace_id,
            "status": status,
            "intent": intent,
            "response": response_text,
            "tool_invocations": loop_result["tool_invocations"],
            "artifacts": loop_result["artifacts"],
            "memory_ids": loop_result["memory_ids"],
            "audit_event_id": audit_event_id,
            "events": [event.event_type for event in events],
        }

    def _ensure_thread(self, request: AgentRunInput) -> Thread:
        thread = self.session.get(Thread, request.thread_id)
        if thread is not None:
            return thread
        thread = Thread(
            thread_id=request.thread_id,
            tenant_id=request.tenant_id,
            workspace_id=request.workspace_id,
            user_id=request.user_id,
            title=request.message[:40],
        )
        self.session.add(thread)
        self.session.commit()
        return thread

    def _record_message(self, request: AgentRunInput, run_id: str, role: str, content: str) -> Message:
        message = Message(
            message_id=f"msg_{uuid.uuid4().hex}",
            tenant_id=request.tenant_id,
            workspace_id=request.workspace_id,
            thread_id=request.thread_id,
            run_id=run_id,
            role=role,
            content=content,
        )
        self.session.add(message)
        self.session.commit()
        return message

    def _read_recent_thread_messages(
        self,
        request: AgentRunInput,
        current_run_id: str,
        *,
        limit: int = 8,
    ) -> list[dict[str, str]]:
        messages = self.session.scalars(
            select(Message)
            .where(
                Message.tenant_id == request.tenant_id,
                Message.workspace_id == request.workspace_id,
                Message.thread_id == request.thread_id,
                Message.run_id != current_run_id,
            )
            .order_by(Message.created_at.asc())
        ).all()
        return [
            {"role": message.role, "content": message.content}
            for message in messages[-limit:]
        ]


def create_default_tool_registry() -> ToolRegistry:
    artifact_service = ArtifactService()
    memory_service = MemoryService()
    registry = ToolRegistry()

    def definition(name: str, display_name: str, description: str, *, risk_tier: str = "L0") -> ToolDefinition:
        return ToolDefinition(
            name=name,
            display_name=display_name,
            description=description,
            input_schema={"type": "object"},
            output_schema={"type": "object"},
            read_only=name not in {"memory.write", "artifact.update", "plan.update"},
            destructive=False,
            concurrency_safe=True,
            interrupt_behavior="cancel",
            risk_tier=risk_tier,
            permission_policy="phase_one_builtin",
            timeout_seconds=30,
            max_result_size_chars=20000,
            progress_event_schema={"event": "tool.progress"},
            artifact_schema={"type": "object"},
            ui_renderer_hint="runtime_panel",
        )

    def plan_update(context: ToolExecutionContext) -> ToolExecutionResult:
        artifact = artifact_service.create(
            context.session,
            context.request,
            context.run_id,
            artifact_type="plan",
            title="一阶段验收计划",
            content={
                "steps": [
                    {"title": "通用对话", "status": "pending"},
                    {"title": "模型配置", "status": "pending"},
                    {"title": "内置工具调用", "status": "pending"},
                    {"title": "Runtime Event 与 Artifact 验证", "status": "pending"},
                ],
                "goal": context.request.message,
            },
        )
        return ToolExecutionResult(
            tool_id="plan.update",
            response_text="已生成一阶段验收计划。",
            output_payload={"artifact_id": artifact.artifact_id},
            artifacts=[artifact],
        )

    def memory_write(context: ToolExecutionContext) -> ToolExecutionResult:
        memory = memory_service.write_preference(context)
        return ToolExecutionResult(
            tool_id="memory.write",
            response_text="已写入受控记忆。",
            output_payload={"memory_id": memory.memory_id},
            memory_ids=[memory.memory_id],
        )

    def memory_read(context: ToolExecutionContext) -> ToolExecutionResult:
        memories = memory_service.read_workspace_memories(context)
        artifact = artifact_service.create(
            context.session,
            context.request,
            context.run_id,
            artifact_type="memory_snapshot",
            title="受控记忆快照",
            content={"memories": memories},
        )
        return ToolExecutionResult(
            tool_id="memory.read",
            response_text=f"已读取受控记忆，共 {len(memories)} 条。",
            output_payload={"artifact_id": artifact.artifact_id, "memory_count": len(memories)},
            artifacts=[artifact],
        )

    def workspace_list(context: ToolExecutionContext) -> ToolExecutionResult:
        files = _workspace_listing()
        artifact = artifact_service.create(
            context.session,
            context.request,
            context.run_id,
            artifact_type="workspace_listing",
            title="工作空间文件列表",
            content={"files": files},
        )
        return ToolExecutionResult(
            tool_id="workspace.list",
            response_text=f"已列出当前工作空间文件，共 {len(files)} 个条目。",
            output_payload={"artifact_id": artifact.artifact_id, "files": files},
            artifacts=[artifact],
        )

    def workspace_read(context: ToolExecutionContext) -> ToolExecutionResult:
        preview = _read_workspace_markdown(context.request.message)
        artifact = artifact_service.create(
            context.session,
            context.request,
            context.run_id,
            artifact_type="file_preview",
            title=f"文件预览：{preview['filename']}",
            content=preview,
        )
        return ToolExecutionResult(
            tool_id="workspace.read",
            response_text=f"已读取工作空间文件：{preview['filename']}。",
            output_payload={"artifact_id": artifact.artifact_id, "filename": preview["filename"]},
            artifacts=[artifact],
        )

    def settings_read(context: ToolExecutionContext) -> ToolExecutionResult:
        settings = _settings_snapshot(context.request.workspace_id)
        artifact = artifact_service.create(
            context.session,
            context.request,
            context.run_id,
            artifact_type="settings_snapshot",
            title="设置快照",
            content=settings,
        )
        return ToolExecutionResult(
            tool_id="settings.read",
            response_text="已读取当前模型、工作空间和阶段设置。",
            output_payload={"artifact_id": artifact.artifact_id, "configured": settings["model"]["configured"]},
            artifacts=[artifact],
        )

    def local_data_analyze(context: ToolExecutionContext) -> ToolExecutionResult:
        analysis = _local_data_analysis(context.request.message)
        artifact = artifact_service.create(
            context.session,
            context.request,
            context.run_id,
            artifact_type="local_data_analysis",
            title="本地数据分析",
            content=analysis,
        )
        return ToolExecutionResult(
            tool_id="local_data.analyze",
            response_text=f"已完成本地数据分析：共 {analysis['count']} 个值，合计 {analysis['sum']}，平均 {analysis['average']}。",
            output_payload={"artifact_id": artifact.artifact_id, "count": analysis["count"]},
            artifacts=[artifact],
        )

    def diagnostic_check(context: ToolExecutionContext) -> ToolExecutionResult:
        if context.intent == "tool_failure_test":
            return ToolExecutionResult(
                tool_id="diagnostic.check",
                status="failed",
                response_text="工具执行失败：diagnostic.check 返回 phase_one_failure_test。请重试或查看运行事件。",
                output_payload={"error": "phase_one_failure_test"},
            )
        report = _diagnostic_report()
        artifact = artifact_service.create(
            context.session,
            context.request,
            context.run_id,
            artifact_type="diagnostic_report",
            title="诊断报告",
            content=report,
        )
        return ToolExecutionResult(
            tool_id="diagnostic.check",
            response_text="诊断完成：服务端、SQLite、模型配置和一阶段工具状态已记录。",
            output_payload={"artifact_id": artifact.artifact_id, "status": report["status"]},
            artifacts=[artifact],
        )

    def artifact_update(context: ToolExecutionContext) -> ToolExecutionResult:
        artifact = artifact_service.create(
            context.session,
            context.request,
            context.run_id,
            artifact_type="updated_artifact",
            title="更新后的一阶段计划",
            content={"revision": 1, "changes": [], "source": context.request.message},
        )
        content = json.loads(artifact.content_json)
        content["revision"] = 2
        content["changes"].append("取消和重试检查")
        artifact.content_json = json.dumps(content, ensure_ascii=False)
        context.session.add(artifact)
        context.session.commit()
        return ToolExecutionResult(
            tool_id="artifact.update",
            response_text=f"已更新 Artifact：{artifact.title}。",
            output_payload={"artifact_id": artifact.artifact_id, "revision": 2},
            artifacts=[artifact],
            artifact_event_type="artifact.updated",
            include_artifact_invocation=False,
        )

    def conversation_respond(context: ToolExecutionContext) -> ToolExecutionResult:
        return ToolExecutionResult(
            tool_id="conversation.respond",
            response_text="已进入通用对话回复流程。",
            output_payload={"mode": "general_conversation"},
            include_artifact_invocation=False,
        )

    def intent_classify(context: ToolExecutionContext) -> ToolExecutionResult:
        classification = classify_text(context.request.message)
        return ToolExecutionResult(
            tool_id="intent.classify",
            response_text="已完成意图识别。",
            output_payload={"classification": classification},
            include_artifact_invocation=False,
        )

    def plugin_catalog(context: ToolExecutionContext) -> ToolExecutionResult:
        _ = context
        return ToolExecutionResult(
            tool_id="plugin.catalog",
            status="blocked",
            response_text="该请求需要业务插件能力，业务插件将在二阶段启用。一阶段不会返回模拟业务数据。",
            output_payload={"plugins": [], "phase": "phase_one"},
            include_artifact_invocation=False,
        )

    registry.register(definition("conversation.respond", "通用回复", "通用回答、澄清、总结和解释"), conversation_respond)
    registry.register(definition("intent.classify", "意图识别", "识别用户意图、实体、风险和候选工具"), intent_classify)
    registry.register(definition("plan.update", "更新计划", "生成或更新一阶段计划"), plan_update)
    registry.register(definition("memory.write", "写入记忆", "写入受控用户偏好"), memory_write)
    registry.register(definition("memory.read", "读取记忆", "读取受控工作空间记忆"), memory_read)
    registry.register(definition("workspace.list", "列出工作空间", "列出授权工作空间文件"), workspace_list)
    registry.register(definition("workspace.read", "读取工作空间文件", "读取授权 Markdown 文件"), workspace_read)
    registry.register(definition("settings.read", "读取设置", "读取模型和工作空间设置"), settings_read)
    registry.register(definition("local_data.analyze", "本地数据分析", "分析用户输入的小型本地数据"), local_data_analyze)
    registry.register(definition("diagnostic.check", "诊断检查", "检查一阶段运行状态"), diagnostic_check)
    registry.register(definition("artifact.update", "更新 Artifact", "更新已有或新建 Artifact"), artifact_update)
    registry.register(definition("plugin.catalog", "插件目录", "查询当前阶段可用业务插件", risk_tier="L1"), plugin_catalog)
    return registry


def _workspace_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _workspace_listing() -> list[dict[str, object]]:
    docs = sorted((_workspace_root() / "docs").glob("*.md")) if (_workspace_root() / "docs").exists() else []
    return [{"name": path.name, "kind": "file"} for path in docs[:20]]


def _requested_markdown_filename(message: str) -> str:
    for token in message.replace("，", " ").replace(",", " ").split():
        if token.endswith(".md"):
            return Path(token).name
    return "mvp-stage-plan.md"


def _read_workspace_markdown(message: str) -> dict[str, str]:
    filename = _requested_markdown_filename(message)
    docs_root = (_workspace_root() / "docs").resolve()
    path = (docs_root / filename).resolve()
    if docs_root not in path.parents or path.suffix != ".md" or not path.exists():
        return {
            "filename": filename,
            "content": "未找到授权范围内的 Markdown 文件。",
        }
    return {
        "filename": filename,
        "content": path.read_text(encoding="utf-8")[:4000],
    }


def _settings_snapshot(workspace_id: str) -> dict[str, object]:
    load_local_env()
    return {
        "workspace_id": workspace_id,
        "model": {
            "model_id": os.getenv("OPENAI_COMPATIBLE_MODEL", DEFAULT_MODEL),
            "provider": "openai-compatible",
            "base_url": os.getenv("OPENAI_COMPATIBLE_BASE_URL", DEFAULT_BASE_URL),
            "configured": model_configured(),
        },
        "phase": "phase_one",
        "business_plugins": "disabled_until_phase_two",
    }


def _diagnostic_report() -> dict[str, object]:
    load_local_env()
    return {
        "status": "ok",
        "phase": "phase_one",
        "checks": {
            "sqlite": "ok",
            "model": "configured" if model_configured() else "not_configured",
            "business_plugins": "disabled_until_phase_two",
            "tools": "phase_one_builtin_tools_enabled",
        },
    }


def _local_data_analysis(message: str) -> dict[str, object]:
    values = [float(value) for value in re.findall(r"[-+]?\d+(?:\.\d+)?", message)]
    if not values:
        values = [12.0, 18.0, 24.0]
    total = sum(values)
    average = total / len(values)
    return {
        "scope": "local_input_only",
        "metric": "descriptive_statistics",
        "count": len(values),
        "sum": total,
        "average": average,
        "minimum": min(values),
        "maximum": max(values),
        "note": "仅分析用户输入或默认示例数字，不连接企业数仓或业务系统。",
    }
