from fastapi.testclient import TestClient
from sqlalchemy import select
import uuid

from app.db import SessionLocal
from app.main import create_app
from app.agent_runtime import AgentRunInput, AgentSessionRuntime, PermissionGate, ToolExecutionContext, create_default_tool_registry
from app.models import AgentMemory, Artifact, Message, ModelCall, Run, RunStep, Thread
from app.repositories import append_runtime_event


def test_agent_run_plan_uses_server_runtime_and_records_events():
    client = TestClient(create_app())

    response = client.post(
        "/api/agent/run",
        json={
            "tenant_id": "tenant_demo",
            "workspace_id": "workspace_default",
            "thread_id": "thread_runtime_plan",
            "user_id": "user_demo",
            "message": "帮我制定一阶段验收计划",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "completed"
    assert body["intent"] == "plan"
    assert body["run_id"].startswith("run_")
    assert body["thread_id"] == "thread_runtime_plan"
    assert body["tool_invocations"] == ["intent.classify", "plan.update", "artifact.create"]
    assert body["artifacts"][0]["artifact_type"] == "plan"
    assert body["artifacts"][0]["title"] == "一阶段验收计划"
    assert body["audit_event_id"].startswith("evt_")
    assert body["events"] == [
        "run.created",
        "message.received",
        "intent.classified",
        "context.built",
        "tool.planned",
        "tool.started",
        "tool.completed",
        "artifact.created",
        "run.completed",
    ]

    events = client.get(f"/api/runs/{body['run_id']}/events").json()["events"]
    assert [event["event_type"] for event in events] == [
        "run.created",
        "message.received",
        "intent.classified",
        "context.built",
        "tool.planned",
        "tool.started",
        "tool.completed",
        "artifact.created",
        "run.completed",
    ]

    with SessionLocal() as session:
        thread = session.get(Thread, "thread_runtime_plan")
        messages = session.scalars(select(Message).where(Message.run_id == body["run_id"])).all()
        artifact = session.get(Artifact, body["artifacts"][0]["artifact_id"])
        steps = session.scalars(select(RunStep).where(RunStep.run_id == body["run_id"])).all()

    assert thread is not None
    assert [message.role for message in messages] == ["user", "assistant"]
    assert artifact is not None
    assert [(step.step_type, step.status) for step in steps] == [
        ("run", "running"),
        ("message", "completed"),
        ("intent", "completed"),
        ("context", "completed"),
        ("tool:plan.update", "planned"),
        ("tool:plan.update", "running"),
        ("tool:plan.update", "completed"),
        ("artifact:plan", "completed"),
        ("run", "completed"),
    ]

    run_detail = client.get(f"/api/runs/{body['run_id']}").json()
    assert [step["step_type"] for step in run_detail["steps"]] == [step.step_type for step in steps]
    assert run_detail["steps"][-1]["status"] == "completed"


def test_thread_list_returns_recent_workspace_conversations():
    client = TestClient(create_app())
    suffix = uuid.uuid4().hex
    workspace_id = f"workspace_threads_{suffix}"

    first = client.post(
        "/api/agent/run",
        json={
            "tenant_id": "tenant_demo",
            "workspace_id": workspace_id,
            "thread_id": f"thread_first_{suffix}",
            "user_id": "user_demo",
            "message": "帮我制定一阶段验收计划",
        },
    )
    second = client.post(
        "/api/agent/run",
        json={
            "tenant_id": "tenant_demo",
            "workspace_id": workspace_id,
            "thread_id": f"thread_second_{suffix}",
            "user_id": "user_demo",
            "message": "读取 mvp-stage-plan.md 文件",
        },
    )

    assert first.status_code == 200
    assert second.status_code == 200

    response = client.get(f"/api/threads?tenant_id=tenant_demo&workspace_id={workspace_id}&user_id=user_demo")

    assert response.status_code == 200
    threads = response.json()["threads"]
    assert threads == [
        {
            "thread_id": f"thread_second_{suffix}",
            "title": "读取 mvp-stage-plan.md 文件",
            "workspace_id": workspace_id,
            "status": "regular",
            "last_message": "已读取工作空间文件：mvp-stage-plan.md。",
            "last_message_at": threads[0]["last_message_at"],
            "message_count": 2,
        },
        {
            "thread_id": f"thread_first_{suffix}",
            "title": "帮我制定一阶段验收计划",
            "workspace_id": workspace_id,
            "status": "regular",
            "last_message": "已生成一阶段验收计划。",
            "last_message_at": threads[1]["last_message_at"],
            "message_count": 2,
        },
    ]
    assert threads[0]["last_message_at"]
    assert threads[1]["last_message_at"]


def test_thread_management_updates_status_and_deletes_thread():
    client = TestClient(create_app())
    suffix = uuid.uuid4().hex
    workspace_id = f"workspace_thread_manage_{suffix}"
    thread_id = f"thread_manage_{suffix}"

    run = client.post(
        "/api/agent/run",
        json={
            "tenant_id": "tenant_demo",
            "workspace_id": workspace_id,
            "thread_id": thread_id,
            "user_id": "user_demo",
            "message": "帮我制定一阶段验收计划",
        },
    )
    assert run.status_code == 200

    archive = client.patch(
        f"/api/threads/{thread_id}?tenant_id=tenant_demo&workspace_id={workspace_id}&user_id=user_demo",
        json={"title": "已归档测试会话", "status": "archived"},
    )
    assert archive.status_code == 200
    assert archive.json()["title"] == "已归档测试会话"
    assert archive.json()["status"] == "archived"

    listed = client.get(f"/api/threads?tenant_id=tenant_demo&workspace_id={workspace_id}&user_id=user_demo")
    assert listed.status_code == 200
    assert listed.json()["threads"][0]["status"] == "archived"

    delete_response = client.delete(
        f"/api/threads/{thread_id}?tenant_id=tenant_demo&workspace_id={workspace_id}&user_id=user_demo",
    )
    assert delete_response.status_code == 200
    assert delete_response.json() == {"thread_id": thread_id, "deleted": True}

    missing = client.get(
        f"/api/threads/{thread_id}?tenant_id=tenant_demo&workspace_id={workspace_id}&user_id=user_demo",
    )
    assert missing.status_code == 404


def test_thread_detail_returns_ordered_messages():
    client = TestClient(create_app())
    suffix = uuid.uuid4().hex
    workspace_id = f"workspace_thread_detail_{suffix}"
    thread_id = f"thread_detail_{suffix}"

    run = client.post(
        "/api/agent/run",
        json={
            "tenant_id": "tenant_demo",
            "workspace_id": workspace_id,
            "thread_id": thread_id,
            "user_id": "user_demo",
            "message": "读取 mvp-stage-plan.md 文件",
        },
    )
    assert run.status_code == 200

    response = client.get(
        f"/api/threads/{thread_id}?tenant_id=tenant_demo&workspace_id={workspace_id}&user_id=user_demo",
    )

    assert response.status_code == 200
    body = response.json()
    assert body["thread"]["thread_id"] == thread_id
    assert body["thread"]["title"] == "读取 mvp-stage-plan.md 文件"
    assert [message["role"] for message in body["messages"]] == ["user", "assistant"]
    assert body["messages"][0]["content"] == "读取 mvp-stage-plan.md 文件"
    assert body["messages"][1]["content"] == "已读取工作空间文件：mvp-stage-plan.md。"
    assert body["messages"][1]["run_id"] == run.json()["run_id"]


def test_agent_run_memory_and_workspace_builtin_tools():
    client = TestClient(create_app())

    memory_response = client.post(
        "/api/agent/run",
        json={
            "tenant_id": "tenant_demo",
            "workspace_id": "workspace_default",
            "thread_id": "thread_runtime_memory",
            "user_id": "user_demo",
            "message": "记住：我偏好简洁输出",
        },
    )

    assert memory_response.status_code == 200
    memory_body = memory_response.json()
    assert memory_body["intent"] == "memory_write"
    assert "memory.write" in memory_body["tool_invocations"]
    assert memory_body["memory_ids"][0].startswith("mem_")

    with SessionLocal() as session:
        memory = session.get(AgentMemory, memory_body["memory_ids"][0])

    assert memory is not None
    assert "简洁输出" in memory.content_json

    memory_read_response = client.post(
        "/api/agent/run",
        json={
            "tenant_id": "tenant_demo",
            "workspace_id": "workspace_default",
            "thread_id": "thread_runtime_memory",
            "user_id": "user_demo",
            "message": "读取我的记忆偏好",
        },
    )

    assert memory_read_response.status_code == 200
    memory_read_body = memory_read_response.json()
    assert memory_read_body["intent"] == "memory_read"
    assert memory_read_body["tool_invocations"] == ["intent.classify", "memory.read", "artifact.create"]
    assert memory_read_body["artifacts"][0]["artifact_type"] == "memory_snapshot"
    assert "已读取受控记忆" in memory_read_body["response"]

    workspace_response = client.post(
        "/api/agent/run",
        json={
            "tenant_id": "tenant_demo",
            "workspace_id": "workspace_default",
            "thread_id": "thread_runtime_workspace",
            "user_id": "user_demo",
            "message": "列出当前工作空间文件",
        },
    )

    assert workspace_response.status_code == 200
    workspace_body = workspace_response.json()
    assert workspace_body["intent"] == "workspace_file_task"
    assert workspace_body["tool_invocations"] == ["intent.classify", "workspace.list", "artifact.create"]
    assert workspace_body["artifacts"][0]["artifact_type"] == "workspace_listing"


def test_agent_run_workspace_read_creates_file_preview_artifact():
    client = TestClient(create_app())

    response = client.post(
        "/api/agent/run",
        json={
            "tenant_id": "tenant_demo",
            "workspace_id": "workspace_default",
            "thread_id": "thread_runtime_workspace_read",
            "user_id": "user_demo",
            "message": "读取 mvp-stage-plan.md 文件",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "completed"
    assert body["intent"] == "workspace_read"
    assert body["tool_invocations"] == ["intent.classify", "workspace.read", "artifact.create"]
    assert body["artifacts"][0]["artifact_type"] == "file_preview"
    assert "已读取工作空间文件" in body["response"]
    assert body["events"] == [
        "run.created",
        "message.received",
        "intent.classified",
        "context.built",
        "tool.planned",
        "tool.started",
        "tool.completed",
        "artifact.created",
        "run.completed",
    ]


def test_agent_run_settings_and_diagnostic_builtin_tools():
    client = TestClient(create_app())

    settings_response = client.post(
        "/api/agent/run",
        json={
            "tenant_id": "tenant_demo",
            "workspace_id": "workspace_default",
            "thread_id": "thread_runtime_settings",
            "user_id": "user_demo",
            "message": "查看当前模型和工作空间设置",
        },
    )

    assert settings_response.status_code == 200
    settings_body = settings_response.json()
    assert settings_body["intent"] == "settings_help"
    assert settings_body["tool_invocations"] == ["intent.classify", "settings.read", "artifact.create"]
    assert settings_body["artifacts"][0]["artifact_type"] == "settings_snapshot"

    diagnostic_response = client.post(
        "/api/agent/run",
        json={
            "tenant_id": "tenant_demo",
            "workspace_id": "workspace_default",
            "thread_id": "thread_runtime_diagnostic",
            "user_id": "user_demo",
            "message": "运行诊断检查服务端模型和工具状态",
        },
    )

    assert diagnostic_response.status_code == 200
    diagnostic_body = diagnostic_response.json()
    assert diagnostic_body["intent"] == "diagnostic_check"
    assert diagnostic_body["tool_invocations"] == ["intent.classify", "diagnostic.check", "artifact.create"]
    assert diagnostic_body["artifacts"][0]["artifact_type"] == "diagnostic_report"
    assert "诊断完成" in diagnostic_body["response"]


def test_agent_run_local_data_analysis_creates_artifact_without_business_connector():
    client = TestClient(create_app())

    response = client.post(
        "/api/agent/run",
        json={
            "tenant_id": "tenant_demo",
            "workspace_id": "workspace_default",
            "thread_id": "thread_runtime_local_analysis",
            "user_id": "user_demo",
            "message": "本地分析 10 20 30 的平均值",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["intent"] == "local_data_analysis"
    assert body["tool_invocations"] == ["intent.classify", "local_data.analyze", "artifact.create"]
    assert body["artifacts"][0]["artifact_type"] == "local_data_analysis"
    assert "已完成本地数据分析" in body["response"]
    assert "connector.invoked" not in body["events"]

    artifact = client.get(f"/api/artifacts/{body['artifacts'][0]['artifact_id']}").json()
    assert artifact["content"]["scope"] == "local_input_only"
    assert artifact["content"]["count"] == 3
    assert artifact["content"]["average"] == 20


def test_agent_run_artifact_update_records_update_event():
    client = TestClient(create_app())

    response = client.post(
        "/api/agent/run",
        json={
            "tenant_id": "tenant_demo",
            "workspace_id": "workspace_default",
            "thread_id": "thread_runtime_artifact_update",
            "user_id": "user_demo",
            "message": "更新一阶段计划产物，加入取消和重试检查",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["intent"] == "artifact_update"
    assert body["tool_invocations"] == ["intent.classify", "artifact.update"]
    assert body["artifacts"][0]["artifact_type"] == "updated_artifact"
    assert "已更新 Artifact" in body["response"]
    assert "artifact.updated" in body["events"]

    artifact = client.get(f"/api/artifacts/{body['artifacts'][0]['artifact_id']}").json()
    assert artifact["content"]["revision"] == 2
    assert "取消和重试检查" in artifact["content"]["changes"][0]


def test_agent_run_blocks_business_plugin_without_mock_result():
    client = TestClient(create_app())

    response = client.post(
        "/api/agent/run",
        json={
            "tenant_id": "tenant_demo",
            "workspace_id": "workspace_default",
            "thread_id": "thread_runtime_business",
            "user_id": "user_demo",
            "message": "查 2026 年所有惠民保项目总保费",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "blocked"
    assert body["intent"] == "business_plugin_required"
    assert body["tool_invocations"] == ["intent.classify", "plugin.catalog"]
    assert body["artifacts"] == []
    assert "业务插件将在二阶段启用" in body["response"]
    assert "12.36" not in body["response"]

    events = client.get(f"/api/runs/{body['run_id']}/events").json()["events"]
    assert [event["event_type"] for event in events][-2:] == ["tool.completed", "run.completed"]


def test_agent_run_tool_failure_projects_failed_run_steps():
    client = TestClient(create_app())

    response = client.post(
        "/api/agent/run",
        json={
            "tenant_id": "tenant_demo",
            "workspace_id": f"workspace_failure_steps_{uuid.uuid4().hex}",
            "thread_id": f"thread_failure_steps_{uuid.uuid4().hex}",
            "user_id": "user_demo",
            "message": "触发失败工具测试",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "failed"
    assert body["events"][-2:] == ["tool.failed", "run.failed"]

    run_detail = client.get(f"/api/runs/{body['run_id']}")

    assert run_detail.status_code == 200
    steps = run_detail.json()["steps"]
    assert ("tool:diagnostic.check", "failed") in [
        (step["step_type"], step["status"]) for step in steps
    ]
    assert steps[-1]["step_type"] == "run"
    assert steps[-1]["status"] == "failed"


def test_agent_run_general_chat_records_model_events(monkeypatch):
    from app.routes import agent

    def fake_completion(text: str):
        assert text == "用一句话介绍工作台"
        return {"message": "这是模型回答", "provider": "test-provider", "model": "test-model"}

    monkeypatch.setattr(agent, "chat_completion", fake_completion)
    monkeypatch.setattr(agent, "chat_completion_with_tools", lambda text, tools: fake_completion(text))
    client = TestClient(create_app())
    thread_id = f"thread_runtime_general_{uuid.uuid4().hex}"

    response = client.post(
        "/api/agent/run",
        json={
            "tenant_id": "tenant_demo",
            "workspace_id": "workspace_general_model",
            "thread_id": thread_id,
            "user_id": "user_demo",
            "message": "用一句话介绍工作台",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "completed"
    assert body["intent"] == "general_chat"
    assert body["response"] == "这是模型回答"
    assert body["events"] == [
        "run.created",
        "message.received",
        "intent.classified",
        "context.built",
        "model.selected",
        "model.started",
        "model.completed",
        "run.completed",
    ]

    with SessionLocal() as session:
        model_calls = session.scalars(select(ModelCall).where(ModelCall.run_id == body["run_id"])).all()

    assert len(model_calls) == 1
    assert model_calls[0].provider == "test-provider"
    assert model_calls[0].model == "test-model"


def test_agent_run_summarize_and_rewrite_use_model_path(monkeypatch):
    from app.routes import agent

    calls = []

    def fake_completion(text: str):
        calls.append(text)
        return {"message": f"模型处理：{text}", "provider": "test-provider", "model": "test-model"}

    monkeypatch.setattr(agent, "chat_completion", fake_completion)
    monkeypatch.setattr(agent, "chat_completion_with_tools", lambda text, tools: fake_completion(text))
    client = TestClient(create_app())
    suffix = uuid.uuid4().hex

    summarize = client.post(
        "/api/agent/run",
        json={
            "tenant_id": "tenant_demo",
            "workspace_id": f"workspace_model_path_{suffix}",
            "thread_id": f"thread_runtime_summarize_{suffix}",
            "user_id": "user_demo",
            "message": "帮我总结刚才讨论",
        },
    ).json()
    rewrite = client.post(
        "/api/agent/run",
        json={
            "tenant_id": "tenant_demo",
            "workspace_id": f"workspace_model_path_{suffix}",
            "thread_id": f"thread_runtime_rewrite_{suffix}",
            "user_id": "user_demo",
            "message": "改写这段说明，让它更简洁",
        },
    ).json()

    assert summarize["intent"] == "summarize"
    assert rewrite["intent"] == "rewrite"
    assert summarize["response"] == "模型处理：帮我总结刚才讨论"
    assert rewrite["response"] == "模型处理：改写这段说明，让它更简洁"
    assert calls == ["帮我总结刚才讨论", "改写这段说明，让它更简洁"]


def test_agent_run_model_path_injects_workspace_memory_context(monkeypatch):
    from app.routes import agent

    calls = []

    def fake_completion(text: str):
        calls.append(text)
        return {"message": "已按你的偏好简洁回答。", "provider": "test-provider", "model": "test-model"}

    monkeypatch.setattr(agent, "chat_completion", fake_completion)
    monkeypatch.setattr(agent, "chat_completion_with_tools", lambda text, tools: fake_completion(text))
    client = TestClient(create_app())
    workspace_id = "workspace_memory_context"

    memory_response = client.post(
        "/api/agent/run",
        json={
            "tenant_id": "tenant_demo",
            "workspace_id": workspace_id,
            "thread_id": "thread_runtime_memory_context_write",
            "user_id": "user_demo",
            "message": "记住：我偏好简洁输出",
        },
    )
    assert memory_response.status_code == 200

    response = client.post(
        "/api/agent/run",
        json={
            "tenant_id": "tenant_demo",
            "workspace_id": workspace_id,
            "thread_id": "thread_runtime_memory_context_chat",
            "user_id": "user_demo",
            "message": "请回答：这个工作台是什么？",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["intent"] == "general_chat"
    assert body["response"] == "已按你的偏好简洁回答。"
    assert "memory.context.loaded" in body["events"]
    assert len(calls) == 1
    assert "受控记忆上下文" in calls[0]
    assert "我偏好简洁输出" in calls[0]
    assert "用户请求：请回答：这个工作台是什么？" in calls[0]


def test_agent_run_model_path_injects_recent_thread_context(monkeypatch):
    from app.routes import agent

    calls = []

    def fake_completion(text: str):
        calls.append(text)
        if len(calls) == 1:
            return {"message": "第一轮回答：工作台用于通用 Agent 协作。", "provider": "test-provider", "model": "test-model"}
        return {"message": "第二轮回答：已根据刚才讨论总结。", "provider": "test-provider", "model": "test-model"}

    monkeypatch.setattr(agent, "chat_completion", fake_completion)
    monkeypatch.setattr(agent, "chat_completion_with_tools", lambda text, tools: fake_completion(text))
    client = TestClient(create_app())
    suffix = uuid.uuid4().hex
    workspace_id = f"workspace_conversation_context_{suffix}"
    thread_id = f"thread_runtime_conversation_context_{suffix}"

    first = client.post(
        "/api/agent/run",
        json={
            "tenant_id": "tenant_demo",
            "workspace_id": workspace_id,
            "thread_id": thread_id,
            "user_id": "user_demo",
            "message": "第一条：工作台用于通用 Agent 协作",
        },
    )
    assert first.status_code == 200

    second = client.post(
        "/api/agent/run",
        json={
            "tenant_id": "tenant_demo",
            "workspace_id": workspace_id,
            "thread_id": thread_id,
            "user_id": "user_demo",
            "message": "帮我总结刚才讨论",
        },
    )

    assert second.status_code == 200
    body = second.json()
    assert body["intent"] == "summarize"
    assert body["response"] == "第二轮回答：已根据刚才讨论总结。"
    assert "conversation.context.loaded" in body["events"]
    assert len(calls) == 2
    assert calls[0] == "第一条：工作台用于通用 Agent 协作"
    assert "同一会话的近期上下文" in calls[1]
    assert "user: 第一条：工作台用于通用 Agent 协作" in calls[1]
    assert "assistant: 第一轮回答：工作台用于通用 Agent 协作。" in calls[1]
    assert "用户请求：帮我总结刚才讨论" in calls[1]


def test_agent_run_model_can_request_builtin_tool_and_receive_tool_result():
    calls = []

    def fake_model(text: str):
        calls.append(text)
        if len(calls) == 1:
            return {
                "message": "需要调用诊断工具确认运行状态。",
                "provider": "test-provider",
                "model": "test-model",
                "tool_calls": [
                    {
                        "id": "toolcall_diag_1",
                        "name": "diagnostic.check",
                        "arguments": {},
                    }
                ],
            }
        assert "工具调用结果" in text
        assert "diagnostic.check" in text
        assert "artifact_id" in text
        return {"message": "诊断工具已完成，服务端状态正常。", "provider": "test-provider", "model": "test-model"}

    with SessionLocal() as session:
        runtime = AgentSessionRuntime(
            session,
            intent_classifier=lambda _: {
                "intent": "general_chat",
                "confidence": 0.75,
                "required_capabilities": [],
                "risk_hint": "L0",
                "needs_clarification": False,
            },
            model_client=fake_model,
        )
        result = runtime.run(
            AgentRunInput(
                tenant_id="tenant_demo",
                workspace_id=f"workspace_model_tool_loop_{uuid.uuid4().hex}",
                thread_id=f"thread_model_tool_loop_{uuid.uuid4().hex}",
                user_id="user_demo",
                message="检查一下工作台运行状态",
            )
        )
        model_calls = session.scalars(select(ModelCall).where(ModelCall.run_id == result["run_id"])).all()

    assert result["status"] == "completed"
    assert result["response"] == "诊断工具已完成，服务端状态正常。"
    assert result["tool_invocations"] == ["intent.classify", "diagnostic.check", "artifact.create"]
    assert result["artifacts"][0]["artifact_type"] == "diagnostic_report"
    assert "model.tool_calls.requested" in result["events"]
    assert "tool.completed" in result["events"]
    assert "model.tool_results.appended" in result["events"]
    assert len(calls) == 2
    assert len(model_calls) == 2


def test_agent_run_model_tool_followup_uses_openai_tool_role_messages():
    captured_messages = []

    def initial_model(text: str):
        return {
            "message": "需要调用诊断工具确认运行状态。",
            "provider": "test-provider",
            "model": "test-model",
            "tool_calls": [
                {
                    "id": "toolcall_diag_messages_1",
                    "name": "diagnostic.check",
                    "arguments": {},
                }
            ],
        }

    def messages_model(messages, tools=None):
        captured_messages.extend(messages)
        assert tools is None
        return {"message": "已根据标准工具消息生成最终回复。", "provider": "test-provider", "model": "test-model"}

    with SessionLocal() as session:
        runtime = AgentSessionRuntime(
            session,
            intent_classifier=lambda _: {
                "intent": "general_chat",
                "confidence": 0.75,
                "required_capabilities": [],
                "risk_hint": "L0",
                "needs_clarification": False,
            },
            model_client=initial_model,
            model_messages_client=messages_model,
        )
        result = runtime.run(
            AgentRunInput(
                tenant_id="tenant_demo",
                workspace_id=f"workspace_model_messages_{uuid.uuid4().hex}",
                thread_id=f"thread_model_messages_{uuid.uuid4().hex}",
                user_id="user_demo",
                message="检查一下工作台运行状态",
            )
        )

    assert result["status"] == "completed"
    assert result["response"] == "已根据标准工具消息生成最终回复。"
    assert [message["role"] for message in captured_messages] == ["system", "user", "assistant", "tool"]
    assistant_message = captured_messages[2]
    assert assistant_message["tool_calls"][0]["id"] == "toolcall_diag_messages_1"
    assert assistant_message["tool_calls"][0]["type"] == "function"
    assert assistant_message["tool_calls"][0]["function"]["name"] == "diagnostic__check"
    tool_message = captured_messages[3]
    assert tool_message["tool_call_id"] == "toolcall_diag_messages_1"
    assert tool_message["name"] == "diagnostic__check"
    assert "artifact_id" in tool_message["content"]


def test_agent_run_model_tool_loop_can_continue_until_no_more_tool_calls():
    message_calls = []

    def initial_model(text: str):
        return {
            "message": "先检查服务端诊断状态。",
            "provider": "test-provider",
            "model": "test-model",
            "tool_calls": [
                {
                    "id": "toolcall_diag_loop_1",
                    "name": "diagnostic.check",
                    "arguments": {},
                }
            ],
        }

    def messages_model(messages, tools=None):
        message_calls.append(messages)
        assert tools is None
        if len(message_calls) == 1:
            assert [message["role"] for message in messages][-1] == "tool"
            return {
                "message": "还需要读取当前设置。",
                "provider": "test-provider",
                "model": "test-model",
                "tool_calls": [
                    {
                        "id": "toolcall_settings_loop_2",
                        "name": "settings__read",
                        "arguments": {},
                    }
                ],
            }
        assert [message["role"] for message in messages][-2:] == ["assistant", "tool"]
        return {
            "message": "诊断和设置读取均已完成。",
            "provider": "test-provider",
            "model": "test-model",
        }

    with SessionLocal() as session:
        runtime = AgentSessionRuntime(
            session,
            intent_classifier=lambda _: {
                "intent": "general_chat",
                "confidence": 0.75,
                "required_capabilities": [],
                "risk_hint": "L0",
                "needs_clarification": False,
            },
            model_client=initial_model,
            model_messages_client=messages_model,
        )
        result = runtime.run(
            AgentRunInput(
                tenant_id="tenant_demo",
                workspace_id=f"workspace_model_multi_tool_loop_{uuid.uuid4().hex}",
                thread_id=f"thread_model_multi_tool_loop_{uuid.uuid4().hex}",
                user_id="user_demo",
                message="完整检查一下工作台运行状态",
            )
        )

    assert result["status"] == "completed"
    assert result["response"] == "诊断和设置读取均已完成。"
    assert result["tool_invocations"] == [
        "intent.classify",
        "diagnostic.check",
        "artifact.create",
        "settings.read",
    ]
    assert [artifact["artifact_type"] for artifact in result["artifacts"]] == [
        "diagnostic_report",
        "settings_snapshot",
    ]
    assert len(message_calls) == 2


def test_agent_run_validates_model_tool_arguments_before_execution():
    handler_called = False
    registry = create_default_tool_registry()
    registry.register(
        registry.get("diagnostic.check").__class__(
            name="weather.lookup",
            display_name="天气查询",
            description="按城市查询天气",
            input_schema={
                "type": "object",
                "properties": {"city": {"type": "string"}},
                "required": ["city"],
                "additionalProperties": False,
            },
            output_schema={"type": "object"},
            read_only=True,
            destructive=False,
            concurrency_safe=True,
            interrupt_behavior="cancel",
            risk_tier="L0",
            permission_policy="phase_one_builtin",
            timeout_seconds=30,
            max_result_size_chars=20000,
        ),
        lambda context: _mark_weather_handler_called(context),
    )

    def _model(text: str):
        return {
            "message": "需要查天气。",
            "provider": "test-provider",
            "model": "test-model",
            "tool_calls": [
                {
                    "id": "toolcall_weather_invalid",
                    "name": "weather.lookup",
                    "arguments": {"city": 123},
                }
            ],
        }

    def _mark_weather_handler_called(context):
        nonlocal handler_called
        handler_called = True
        return context

    with SessionLocal() as session:
        runtime = AgentSessionRuntime(
            session,
            intent_classifier=lambda _: {
                "intent": "general_chat",
                "confidence": 0.75,
                "required_capabilities": [],
                "risk_hint": "L0",
                "needs_clarification": False,
            },
            model_client=_model,
            registry=registry,
        )
        result = runtime.run(
            AgentRunInput(
                tenant_id="tenant_demo",
                workspace_id=f"workspace_model_tool_arg_validation_{uuid.uuid4().hex}",
                thread_id=f"thread_model_tool_arg_validation_{uuid.uuid4().hex}",
                user_id="user_demo",
                message="查一下天气",
            )
        )

    assert result["status"] == "failed"
    assert "参数校验失败" in result["response"]
    assert not handler_called
    assert "tool.failed" in result["events"]


def test_agent_run_groups_read_only_concurrency_safe_tool_calls_into_one_batch():
    def initial_model(text: str):
        return {
            "message": "需要同时读取诊断和设置。",
            "provider": "test-provider",
            "model": "test-model",
            "tool_calls": [
                {
                    "id": "toolcall_batch_diag",
                    "name": "diagnostic.check",
                    "arguments": {},
                },
                {
                    "id": "toolcall_batch_settings",
                    "name": "settings.read",
                    "arguments": {},
                },
            ],
        }

    def messages_model(messages, tools=None):
        return {"message": "诊断和设置均已读取。", "provider": "test-provider", "model": "test-model"}

    with SessionLocal() as session:
        runtime = AgentSessionRuntime(
            session,
            intent_classifier=lambda _: {
                "intent": "general_chat",
                "confidence": 0.75,
                "required_capabilities": [],
                "risk_hint": "L0",
                "needs_clarification": False,
            },
            model_client=initial_model,
            model_messages_client=messages_model,
        )
        result = runtime.run(
            AgentRunInput(
                tenant_id="tenant_demo",
                workspace_id=f"workspace_model_tool_batch_{uuid.uuid4().hex}",
                thread_id=f"thread_model_tool_batch_{uuid.uuid4().hex}",
                user_id="user_demo",
                message="检查服务端并读取设置",
            )
        )

    assert result["status"] == "completed"
    assert result["response"] == "诊断和设置均已读取。"
    assert result["tool_invocations"] == [
        "intent.classify",
        "diagnostic.check",
        "artifact.create",
        "settings.read",
    ]
    assert "tool.batch.started" in result["events"]
    assert "tool.batch.completed" in result["events"]


def test_agent_run_tool_failure_records_failed_events():
    client = TestClient(create_app())

    response = client.post(
        "/api/agent/run",
        json={
            "tenant_id": "tenant_demo",
            "workspace_id": "workspace_default",
            "thread_id": "thread_runtime_failure",
            "user_id": "user_demo",
            "message": "触发失败工具测试",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "failed"
    assert body["intent"] == "tool_failure_test"
    assert body["tool_invocations"] == ["intent.classify", "diagnostic.check"]
    assert body["artifacts"] == []
    assert "工具执行失败" in body["response"]
    assert body["events"] == [
        "run.created",
        "message.received",
        "intent.classified",
        "context.built",
        "tool.planned",
        "tool.started",
        "tool.failed",
        "run.failed",
    ]


def test_cancel_run_records_cancelled_event():
    client = TestClient(create_app())
    created = client.post(
        "/api/runs",
        json={
            "tenant_id": "tenant_demo",
            "workspace_id": "workspace_default",
            "thread_id": "thread_runtime_cancel",
            "user_id": "user_demo",
            "message": "需要取消的运行",
        },
    ).json()

    response = client.post(
        f"/api/runs/{created['run_id']}/cancel",
        json={"user_id": "user_demo", "reason": "用户取消"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["run_id"] == created["run_id"]
    assert body["status"] == "cancelled"
    assert "run.cancelled" in body["events"]


def test_retry_run_creates_new_run_with_retry_event():
    client = TestClient(create_app())
    original = client.post(
        "/api/agent/run",
        json={
            "tenant_id": "tenant_demo",
            "workspace_id": "workspace_default",
            "thread_id": "thread_runtime_retry",
            "user_id": "user_demo",
            "message": "触发失败工具测试",
        },
    ).json()

    response = client.post(
        f"/api/runs/{original['run_id']}/retry",
        json={"user_id": "user_demo"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["run_id"].startswith("run_")
    assert body["run_id"] != original["run_id"]
    assert body["retry_of_run_id"] == original["run_id"]
    assert body["status"] == "created"
    assert body["events"] == ["run.created", "retry_of_run"]


def test_run_events_endpoint_and_sse_stream_expose_ordered_runtime_events():
    client = TestClient(create_app())
    run = client.post(
        "/api/agent/run",
        json={
            "tenant_id": "tenant_demo",
            "workspace_id": "workspace_default",
            "thread_id": "thread_runtime_event_stream",
            "user_id": "user_demo",
            "message": "帮我制定一阶段验收计划",
        },
    ).json()

    events = client.get(f"/api/runs/{run['run_id']}/events")
    assert events.status_code == 200
    event_rows = events.json()["events"]
    assert [event["event_type"] for event in event_rows] == run["events"]
    assert event_rows[0]["event_id"].startswith("evt_")
    assert "occurred_at" in event_rows[0]

    with client.stream("GET", f"/api/runs/{run['run_id']}/events/stream") as response:
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/event-stream")
        body = response.read().decode("utf-8")

    assert "event: runtime_event" in body
    assert "event: stream_end" in body
    assert "tool.completed" in body
    assert run["run_id"] in body


def test_agent_run_stream_pushes_runtime_events_before_final_result():
    client = TestClient(create_app())

    with client.stream(
        "POST",
        "/api/agent/run/stream",
        json={
            "tenant_id": "tenant_demo",
            "workspace_id": "workspace_default",
            "thread_id": "thread_runtime_live_stream",
            "user_id": "user_demo",
            "message": "帮我制定一阶段验收计划",
        },
    ) as response:
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/event-stream")
        body = response.read().decode("utf-8")

    assert "event: runtime_event" in body
    assert "event: final_result" in body
    assert "event: stream_end" in body
    assert body.index("event: runtime_event") < body.index("event: final_result")
    assert '"event_type": "run.created"' in body
    assert '"event_type": "tool.started"' in body
    assert '"status": "completed"' in body


def test_agent_run_stream_pushes_model_delta_for_general_chat(monkeypatch):
    from app.routes import agent

    def fake_stream(text, on_delta):
        assert text == "用一句话介绍工作台"
        on_delta("这是")
        on_delta("模型回答")
        return {"message": "这是模型回答", "provider": "test-provider", "model": "test-model"}

    monkeypatch.setattr(agent, "chat_completion_stream", fake_stream)
    monkeypatch.setattr(agent, "chat_completion_stream_with_tools", lambda text, tools, on_delta: fake_stream(text, on_delta))
    client = TestClient(create_app())
    thread_id = f"thread_runtime_model_delta_{uuid.uuid4().hex}"

    with client.stream(
        "POST",
        "/api/agent/run/stream",
        json={
            "tenant_id": "tenant_demo",
            "workspace_id": "workspace_stream_model_delta",
            "thread_id": thread_id,
            "user_id": "user_demo",
            "message": "用一句话介绍工作台",
        },
    ) as response:
        assert response.status_code == 200
        body = response.read().decode("utf-8")

    assert "event: model_delta" in body
    assert '"delta": "这是"' in body
    assert '"delta": "模型回答"' in body
    assert body.index('"event_type": "model.started"') < body.index('"event_type": "model.delta"')
    assert body.index('"event_type": "model.delta"') < body.index('"event_type": "model.completed"')
    assert "event: final_result" in body
    assert '"response": "这是模型回答"' in body


def test_agent_run_stream_stops_model_delta_when_run_is_cancelled(monkeypatch):
    from app.routes import agent

    thread_id = f"thread_runtime_model_cancel_{uuid.uuid4().hex}"

    def fake_stream(text, on_delta):
        assert text == "请持续输出一段通用说明"
        on_delta("第一段")
        with SessionLocal() as session:
            run = session.scalars(select(Run).where(Run.thread_id == thread_id).order_by(Run.created_at.desc())).first()
            assert run is not None
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
                actor="user_demo",
                payload={"reason": "test_cancelled_while_streaming"},
                idempotency_key=f"{run.run_id}:run.cancelled",
            )
        on_delta("第二段不应出现")
        return {"message": "第一段第二段不应出现", "provider": "test-provider", "model": "test-model"}

    monkeypatch.setattr(agent, "chat_completion_stream", fake_stream)
    monkeypatch.setattr(agent, "chat_completion_stream_with_tools", lambda text, tools, on_delta: fake_stream(text, on_delta))
    client = TestClient(create_app())

    with client.stream(
        "POST",
        "/api/agent/run/stream",
        json={
            "tenant_id": "tenant_demo",
            "workspace_id": "workspace_stream_cancel",
            "thread_id": thread_id,
            "user_id": "user_demo",
            "message": "请持续输出一段通用说明",
        },
    ) as response:
        assert response.status_code == 200
        body = response.read().decode("utf-8")

    assert '"delta": "第一段"' in body
    assert "第二段不应出现" not in body
    assert '"status": "cancelled"' in body
    assert '"response": "运行已取消。"' in body
    assert '"event_type": "run.cancelled"' in body
    assert '"event_type": "model.completed"' not in body


def test_agent_run_stream_can_execute_model_requested_tool(monkeypatch):
    from app.routes import agent

    def fake_stream_with_tools(text, tools, on_delta):
        assert text == "检查一下工作台运行状态"
        function_names = [tool["function"]["name"] for tool in tools]
        assert "diagnostic__check" in function_names
        return {
            "message": "",
            "provider": "test-provider",
            "model": "test-model",
            "tool_calls": [
                {
                    "id": "toolcall_stream_diag_1",
                    "name": "diagnostic__check",
                    "arguments": {},
                }
            ],
        }

    def fake_completion_messages(messages, tools=None):
        assert tools is None
        assert [message["role"] for message in messages] == ["system", "user", "assistant", "tool"]
        assert messages[2]["tool_calls"][0]["function"]["name"] == "diagnostic__check"
        assert messages[3]["name"] == "diagnostic__check"
        return {"message": "流式诊断工具已完成。", "provider": "test-provider", "model": "test-model"}

    monkeypatch.setattr(agent, "chat_completion_messages", fake_completion_messages)
    monkeypatch.setattr(agent, "chat_completion_stream_with_tools", fake_stream_with_tools, raising=False)
    client = TestClient(create_app())

    with client.stream(
        "POST",
        "/api/agent/run/stream",
        json={
            "tenant_id": "tenant_demo",
            "workspace_id": f"workspace_stream_tool_loop_{uuid.uuid4().hex}",
            "thread_id": f"thread_stream_tool_loop_{uuid.uuid4().hex}",
            "user_id": "user_demo",
            "message": "检查一下工作台运行状态",
        },
    ) as response:
        assert response.status_code == 200
        body = response.read().decode("utf-8")

    assert '"event_type": "model.tool_calls.requested"' in body
    assert '"event_type": "tool.completed"' in body
    assert '"event_type": "model.tool_results.appended"' in body
    assert "流式诊断工具已完成。" in body


def test_tool_registry_definitions_expose_phase_one_execution_contract():
    registry = create_default_tool_registry()
    tools = {tool.name: tool for tool in registry.list_visible()}

    assert set(tools) == {
        "conversation.respond",
        "intent.classify",
        "plan.update",
        "memory.write",
        "memory.read",
        "workspace.list",
        "workspace.read",
        "settings.read",
        "local_data.analyze",
        "diagnostic.check",
        "artifact.update",
        "plugin.catalog",
    }
    assert tools["workspace.read"].read_only is True
    assert tools["artifact.update"].read_only is False
    assert tools["plugin.catalog"].risk_tier == "L1"
    assert tools["diagnostic.check"].interrupt_behavior == "cancel"


def test_model_tool_specs_use_openai_compatible_function_names():
    with SessionLocal() as session:
        runtime = AgentSessionRuntime(
            session,
            intent_classifier=lambda _: {
                "intent": "general_chat",
                "confidence": 0.75,
                "required_capabilities": [],
                "risk_hint": "L0",
                "needs_clarification": False,
            },
            model_client=lambda text: {"message": text, "provider": "test-provider", "model": "test-model"},
        )
        specs = runtime.query_loop._model_tool_specs()

    function_names = [spec["function"]["name"] for spec in specs]
    assert "diagnostic__check" in function_names
    assert "diagnostic.check" not in function_names
    assert runtime.query_loop._api_tool_name_to_tool_id("diagnostic__check") == "diagnostic.check"


def test_permission_gate_blocks_destructive_tool_definitions():
    registry = create_default_tool_registry()
    definition = registry.get("artifact.update")
    object.__setattr__(definition, "destructive", True)
    gate = PermissionGate()

    with SessionLocal() as session:
        allowed, reason = gate.allow(
            definition,
            ToolExecutionContext(
                session=session,
                request=AgentRunInput(
                    tenant_id="tenant_demo",
                    workspace_id="workspace_default",
                    thread_id="thread_permission_gate",
                    user_id="user_demo",
                    message="更新产物",
                ),
                run_id="run_permission_gate",
                intent="artifact_update",
            ),
        )

    assert allowed is False
    assert reason == "destructive_tools_disabled_in_phase_one"


def test_agent_session_runtime_can_run_without_route_layer():
    with SessionLocal() as session:
        runtime = AgentSessionRuntime(
            session,
            intent_classifier=lambda _: {
                "intent": "general_chat",
                "confidence": 0.75,
                "required_capabilities": [],
                "risk_hint": "L0",
                "needs_clarification": False,
            },
            model_client=lambda text: {"message": f"runtime:{text}", "provider": "test-provider", "model": "test-model"},
        )
        result = runtime.run(
            AgentRunInput(
                tenant_id="tenant_demo",
                workspace_id="workspace_direct_runtime",
                thread_id=f"thread_direct_runtime_{uuid.uuid4().hex}",
                user_id="user_demo",
                message="直接运行 runtime",
            )
        )

    assert result["status"] == "completed"
    assert result["response"] == "runtime:直接运行 runtime"
    assert result["events"] == [
        "run.created",
        "message.received",
        "intent.classified",
        "context.built",
        "model.selected",
        "model.started",
        "model.completed",
        "run.completed",
    ]
