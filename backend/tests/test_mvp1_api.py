from fastapi.testclient import TestClient

from app.main import create_app


def test_health_returns_sqlite_status():
    client = TestClient(create_app())

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": "sqlite"}


def test_cors_allows_web_first_nextjs_dev_origin():
    client = TestClient(create_app())

    response = client.options(
        "/health",
        headers={
            "Origin": "http://127.0.0.1:3001",
            "Access-Control-Request-Method": "GET",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://127.0.0.1:3001"


def test_intent_classifies_mvp1_inputs():
    client = TestClient(create_app())

    premium = client.post("/api/agent/intent", json={"text": "查 2026 年所有惠民保项目总保费"})
    summarize = client.post("/api/agent/intent", json={"text": "帮我总结刚才讨论"})
    permission = client.post("/api/agent/intent", json={"text": "申请查看全国惠民保保费权限"})

    assert premium.status_code == 200
    assert premium.json()["intent"] == "business_plugin_required"
    assert premium.json()["required_capabilities"] == ["plugin.catalog"]
    assert summarize.json()["intent"] == "summarize"
    assert summarize.json()["required_capabilities"] == ["conversation.respond"]
    assert permission.json()["intent"] == "permission_request"
    assert permission.json()["required_capabilities"] == ["approval.request"]


def test_general_chat_requires_model_configuration(monkeypatch):
    monkeypatch.setenv("WORKBENCH_DISABLE_LOCAL_ENV", "1")
    monkeypatch.delenv("BAILIAN_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_COMPATIBLE_API_KEY", raising=False)
    client = TestClient(create_app())

    response = client.post("/api/agent/chat", json={"text": "帮我总结刚才讨论"})

    assert response.status_code == 200
    assert response.json()["provider"] == "not_configured"
    assert "未配置模型服务" in response.json()["message"]


def test_phase_one_chat_contract_is_available_at_api_chat(monkeypatch):
    monkeypatch.setenv("WORKBENCH_DISABLE_LOCAL_ENV", "1")
    monkeypatch.delenv("BAILIAN_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_COMPATIBLE_API_KEY", raising=False)
    client = TestClient(create_app())

    response = client.post("/api/chat", json={"text": "帮我总结刚才讨论"})

    assert response.status_code == 200
    assert response.json()["provider"] == "not_configured"
    assert "未配置模型服务" in response.json()["message"]


def test_general_chat_uses_openai_compatible_model(monkeypatch):
    from app.routes import agent

    captured = {}

    def fake_completion(text: str):
        captured["text"] = text
        return {"message": "这是模型返回", "provider": "aliyun-bailian", "model": "qwen3.7-plus"}

    monkeypatch.setenv("BAILIAN_API_KEY", "test-key")
    monkeypatch.setenv("WORKBENCH_DISABLE_LOCAL_ENV", "1")
    monkeypatch.setattr(agent, "chat_completion", fake_completion)
    client = TestClient(create_app())

    response = client.post("/api/agent/chat", json={"text": "帮我总结刚才讨论"})

    assert response.status_code == 200
    assert response.json() == {"message": "这是模型返回", "provider": "aliyun-bailian", "model": "qwen3.7-plus"}
    assert captured == {"text": "帮我总结刚才讨论"}


def test_plugin_catalog_does_not_publish_business_plugins_in_phase_one():
    client = TestClient(create_app())

    response = client.get(
        "/api/plugins/catalog",
        params={
            "tenant_id": "tenant_demo",
            "workspace_id": "workspace_default",
            "role": "data_analyst",
        },
    )

    assert response.status_code == 200
    assert response.json() == {
        "plugins": [],
        "phase": "phase_one",
        "message": "业务插件将在二阶段启用",
    }


def test_ask_data_query_is_not_available_in_phase_one():
    client = TestClient(create_app())

    response = client.post(
        "/api/ask-data/query",
        json={
            "tenant_id": "tenant_demo",
            "workspace_id": "workspace_default",
            "thread_id": "thread_001",
            "user_id": "user_demo",
            "question": "查 2026 年所有惠民保项目总保费",
            "capability": "ask_data.query",
        },
    )

    body = response.json()
    assert response.status_code == 501
    assert "业务插件将在二阶段启用" in body["detail"]


def test_phase_one_model_catalog_and_connectivity(monkeypatch):
    monkeypatch.setenv("WORKBENCH_DISABLE_LOCAL_ENV", "1")
    monkeypatch.setenv("OPENAI_COMPATIBLE_API_KEY", "test-key")
    monkeypatch.setenv("OPENAI_COMPATIBLE_BASE_URL", "https://example.test/v1")
    monkeypatch.setenv("OPENAI_COMPATIBLE_MODEL", "qwen3.7-plus")
    client = TestClient(create_app())

    catalog = client.get("/api/models")
    assert catalog.status_code == 200
    assert catalog.json() == {
        "models": [
            {
                "model_id": "qwen3.7-plus",
                "provider": "openai-compatible",
                "base_url": "https://example.test/v1",
                "configured": True,
                "capabilities": ["chat", "streaming", "tool_calling"],
            }
        ]
    }

    check = client.post("/api/models/test", json={"model_id": "qwen3.7-plus"})
    assert check.status_code == 200
    assert check.json()["status"] == "configured"


def test_phase_one_run_tool_artifact_and_events():
    client = TestClient(create_app())

    run_response = client.post(
        "/api/runs",
        json={
            "tenant_id": "tenant_demo",
            "workspace_id": "workspace_default",
            "thread_id": "thread_phase1",
            "user_id": "user_demo",
            "message": "帮我制定一阶段验收计划",
        },
    )
    assert run_response.status_code == 200
    run = run_response.json()
    assert run["status"] == "created"
    assert run["run_id"].startswith("run_")

    tool_response = client.post(
        "/api/tools/plan.update/invoke",
        json={
            "tenant_id": "tenant_demo",
            "workspace_id": "workspace_default",
            "thread_id": "thread_phase1",
            "user_id": "user_demo",
            "run_id": run["run_id"],
            "input": {"goal": "帮我制定一阶段验收计划"},
        },
    )
    assert tool_response.status_code == 200
    tool = tool_response.json()
    assert tool["status"] == "completed"
    assert tool["tool_id"] == "plan.update"
    assert tool["artifact"]["title"] == "一阶段验收计划"
    assert tool["artifact"]["artifact_id"].startswith("art_")
    assert tool["audit_event_id"].startswith("evt_")

    artifact = client.get(f"/api/artifacts/{tool['artifact']['artifact_id']}")
    assert artifact.status_code == 200
    assert artifact.json()["title"] == "一阶段验收计划"

    events = client.get(f"/api/runs/{run['run_id']}/events")
    assert events.status_code == 200
    event_types = [event["event_type"] for event in events.json()["events"]]
    assert event_types == [
        "run.created",
        "intent.classified",
        "tool.started",
        "tool.completed",
        "artifact.created",
        "run.completed",
    ]


def test_phase_one_diagnostics_report_core_dependencies():
    client = TestClient(create_app())

    response = client.get("/api/diagnostics")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["phase"] == "phase_one"
    assert body["checks"]["sqlite"] == "ok"
    assert body["checks"]["business_plugins"] == "disabled_until_phase_two"
