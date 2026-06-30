# Phase E Connector Runtime Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实现服务端 Connector Runtime，统一治理内部业务系统和外部通用插件调用。

**Architecture:** Connector 融入服务端，不拆独立 Python 服务。插件负责声明能力和 connector binding；Connector Runtime 负责鉴权、凭据、调用、限流、审计、结果标准化。第一版支持标准 Connector、轻改造 Connector、人工/半自动 Connector 三档 mock。

**Tech Stack:** Python 3.11, FastAPI, SQLAlchemy, SQLite, pytest, HTTP client abstraction.

---

## 0. Scope Boundary

### In scope

- ConnectorBinding 配置。
- 服务端凭据引用。
- ConnectorInvocation 记录。
- 标准返回结构。
- ToolPool 动态过滤。
- 三类 mock connector。
- 超权返回 `approval_required`。
- 原始响应通过 `raw_ref` 引用，不直接塞入消息。

### Out of scope

- 核心业务系统 RPA/UI 自动化。
- 真实理赔/投保系统连接。
- 真实数仓连接。
- 分布式限流。
- Redis 队列。

## 1. Target File Structure

### Create

```text
backend/app/connectors/__init__.py
backend/app/connectors/models.py
backend/app/connectors/result.py
backend/app/connectors/auth.py
backend/app/connectors/http_client.py
backend/app/connectors/runtime.py
backend/app/connectors/tool_pool.py
backend/app/connectors/mock_connectors.py
backend/app/routes/connectors.py
backend/tests/test_connector_result.py
backend/tests/test_connector_runtime.py
backend/tests/test_connector_tool_pool.py
backend/tests/test_connector_routes.py
```

### Modify

```text
backend/app/models.py
backend/app/agent_runtime.py
backend/app/plugins/models.py
backend/app/main.py
backend/app/iam/policy.py
backend/app/audit/service.py
```

## 2. Data Model Contracts

Create:

```text
ConnectorBinding
ConnectorCredential
ConnectorInvocation
ConnectorRateLimit
ConnectorAuditPolicy
ConnectorError
```

ConnectorBinding fields:

```text
binding_id
connector_id
plugin_id
tenant_id
environment
base_url
auth_type
credential_ref
allowed_operations_json
data_scope_policy_id
timeout_seconds
retry_policy_json
rate_limit_json
risk_tier
audit_policy_json
enabled
```

ConnectorInvocation fields:

```text
invocation_id
tenant_id
workspace_id
thread_id
run_id
plugin_id
connector_id
operation
status
input_json
result_json
raw_ref
audit_event_id
created_at
completed_at
```

## 3. Standard Result Contract

Create `backend/app/connectors/result.py`:

```json
{
  "status": "completed | failed | partial | blocked | approval_required",
  "summary": "给主对话展示的摘要",
  "data": {},
  "artifacts": [],
  "audit_event_id": "evt_xxx",
  "permission_decision": {},
  "next_actions": [],
  "raw_ref": "raw_xxx"
}
```

Rules:

- `summary` is short and safe for chat display.
- `data` is bounded structured data.
- Large raw responses go to server-side raw store or invocation result reference.
- `approval_required` must include next action with approval scope.

## 4. Connector Types

```text
standard_api:
  Business system provides stable API.
light_adapter:
  Business system provides partial API; connector adapts shapes.
manual_assist:
  No API; connector produces operation guide, deep link, or form draft.
```

Phase E mock connectors:

```text
warehouse.ask-data.mock
claims.lookup.mock
underwriting.submit.manual
```

## 5. ToolPool Filtering Contract

For every Agent run:

```text
tenant
user
role
workspace
plugin visibility
plugin installation
plugin authorization
data permission
risk tier
approval policy
connector binding enabled
```

Only allowed tools are returned to the model. Never expose all tools.

## 6. API Contracts

```text
GET    /api/connectors/bindings
POST   /api/connectors/bindings
PATCH  /api/connectors/bindings/{binding_id}
POST   /api/connectors/{connector_id}/invoke
GET    /api/connectors/invocations/{invocation_id}
GET    /api/connectors/invocations
```

Invoke request:

```json
{
  "tenant_id": "tenant_demo",
  "workspace_id": "workspace_default",
  "thread_id": "thread_001",
  "run_id": "run_001",
  "user_id": "user_demo",
  "plugin_id": "ask-data",
  "operation": "query",
  "input": {"question": "查 2026 年惠民保总保费"}
}
```

## 7. Implementation Tasks

### Task 1: Connector models and result contract

**Files:**

- Create: `backend/app/connectors/models.py`
- Create: `backend/app/connectors/result.py`
- Modify: `backend/app/models.py`
- Test: `backend/tests/test_connector_result.py`

- [ ] Write failing tests for result serialization and binding persistence.
- [ ] Implement models.
- [ ] Implement `ConnectorResult` dataclass.
- [ ] Run tests.
- [ ] Commit: `feat: add connector models and result contract`.

### Task 2: Credential and auth resolver

**Files:**

- Create: `backend/app/connectors/auth.py`
- Test: `backend/tests/test_connector_runtime.py`

- [ ] Write tests for system credential, user OAuth credential reference record, and API key credential ref.
- [ ] Implement `ConnectorAuthResolver.resolve(binding, user_id)`.
- [ ] Ensure secrets are never returned to API response.
- [ ] Run tests.
- [ ] Commit: `feat: add connector auth resolver`.

### Task 3: HTTP client abstraction

**Files:**

- Create: `backend/app/connectors/http_client.py`
- Test: `backend/tests/test_connector_runtime.py`

- [ ] Write tests with fake client.
- [ ] Implement timeout, retry count, status normalization.
- [ ] Do not add external dependency if stdlib/fake is enough for tests.
- [ ] Run tests.
- [ ] Commit: `feat: add connector http client abstraction`.

### Task 4: Runtime invocation service

**Files:**

- Create: `backend/app/connectors/runtime.py`
- Test: `backend/tests/test_connector_runtime.py`

- [ ] Write tests for allowed invocation, denied invocation, approval_required invocation.
- [ ] Load binding.
- [ ] Evaluate Phase B permission.
- [ ] Resolve credential.
- [ ] Invoke connector handler.
- [ ] Persist `ConnectorInvocation`.
- [ ] Write audit event.
- [ ] Return `ConnectorResult`.
- [ ] Run tests.
- [ ] Commit: `feat: add connector runtime invocation service`.

### Task 5: Mock connectors

**Files:**

- Create: `backend/app/connectors/mock_connectors.py`
- Test: `backend/tests/test_connector_runtime.py`

- [ ] Implement `warehouse.ask-data.mock` returning metric/table artifact payload.
- [ ] Implement `claims.lookup.mock` returning fake claim summary.
- [ ] Implement `underwriting.submit.manual` returning form draft and manual next action.
- [ ] Register mocks in runtime.
- [ ] Run tests.
- [ ] Commit: `feat: add mock connector implementations`.

### Task 6: ToolPool assembler

**Files:**

- Create: `backend/app/connectors/tool_pool.py`
- Modify: `backend/app/agent_runtime.py`
- Test: `backend/tests/test_connector_tool_pool.py`

- [ ] Write tests that unauthorized connector is filtered out.
- [ ] Write tests that disabled binding is filtered out.
- [ ] Write tests that approval_required connector is exposed with approval marker or blocked based on policy.
- [ ] Integrate with plugin capabilities.
- [ ] Ensure runtime sees only filtered tool list.
- [ ] Run tests.
- [ ] Commit: `feat: assemble runtime tool pool from connectors`.

### Task 7: Connector routes

**Files:**

- Create: `backend/app/routes/connectors.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_connector_routes.py`

- [ ] Implement binding CRUD routes.
- [ ] Implement invoke route.
- [ ] Implement invocation query route.
- [ ] Enforce permission checks.
- [ ] Register router.
- [ ] Run tests.
- [ ] Commit: `feat: expose connector runtime APIs`.

## 8. Acceptance Checklist

- [ ] Connector credentials only stored server-side.
- [ ] ToolPool filters unauthorized tools.
- [ ] Connector invocation writes audit.
- [ ] Over-permission request returns `approval_required`.
- [ ] `raw_ref` is returned for raw response reference.
- [ ] Standard, light adapter, manual connector all have mock examples.
- [ ] Existing Phase A-D tests pass.

## 9. Frontend Impact

No direct frontend changes in Phase E.

Frontend changes later:

- Connector result cards in main chat.
- Right-side Artifact rendering in Phase G.
- Approval required card in Phase F.

Do not implement those in Phase E without confirmation.

## 10. Validation Commands

```bash
cd /Users/daniel/Desktop/code/工作台/workbench-app/frontend-v2/backend
pytest tests/test_connector_result.py tests/test_connector_runtime.py tests/test_connector_tool_pool.py tests/test_connector_routes.py -q
pytest -q
cd ..
python3 -m py_compile backend/app/*.py backend/app/routes/*.py backend/app/connectors/*.py
```
