# Phase C Model Provider Settings Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实现多 Model Provider 配置、密钥服务端保存、模型列表管理、连通性测试和授权可见模型能力。

**Architecture:** Phase C 在 Phase A 的 `ModelProviderRegistry` 基础上落地持久化 Provider 配置。密钥不进入前端持久化，默认脱敏展示；具备权限的管理员可以切换查看明文，查看明文必须审计。模型设置使用类似 Codex 的完整设置页面，并优先使用 assistant-ui/shadcn 技术栈实现。

**Tech Stack:** Python 3.11, FastAPI, SQLAlchemy, SQLite, pytest, OpenAI-compatible API.

---

## 0. Scope Boundary

### In scope

- Provider CRUD。
- OpenAI-compatible Provider 类型。
- API Key 服务端保存，默认脱敏返回；有权限时可临时查看明文。
- 手动模型列表。
- 支持 provider `/models` 时刷新模型。
- Provider 连通性测试。
- 按用户、团队、租户、系统范围返回可用模型。
- Provider 操作审计。

### Out of scope

- 前端设置页代码不包含在后端任务中；UI 方向已确认，进入前端任务时按本文件第 6 节执行。
- 企业级 KMS/HSM。
- 费用精确计算。
- 非 OpenAI-compatible 私有 SDK；第一版只支持 OpenAI-compatible。
- 模型路由策略、成本优化策略。

## 1. Target File Structure

### Create

```text
backend/app/model_provider/__init__.py
backend/app/model_provider/models.py
backend/app/model_provider/service.py
backend/app/model_provider/credentials.py
backend/app/model_provider/openai_compatible.py
backend/app/routes/model_providers.py
backend/tests/test_model_provider_crud.py
backend/tests/test_model_provider_credentials.py
backend/tests/test_model_provider_routes.py
```

### Modify

```text
backend/app/models.py
backend/app/model_providers.py
backend/app/routes/models.py
backend/app/main.py
backend/app/agent_runtime.py
backend/app/audit/service.py
```

## 2. Data Model Contracts

Create SQLAlchemy models:

```text
ModelProvider
ModelDefinition
ModelProviderCredential
ModelProviderPermission
ModelProviderAuditEvent
```

Required fields:

```text
provider_id
tenant_id
name
provider_type: openai_compatible
base_url
credential_ref
default_model
enabled
scope: user | team | tenant | system
owner_user_id
owner_team_id
created_by
updated_by
created_at
updated_at
```

`ModelDefinition`:

```text
model_definition_id
provider_id
tenant_id
model_id
display_name
capabilities_json
context_window
enabled
source: manual | remote_refresh
```

`ModelProviderCredential`:

```text
credential_id
tenant_id
provider_id
secret_name
secret_ciphertext
secret_last4
created_by
updated_by
```

Phase C SQLite 加密策略：

- 不引入外部 KMS。
- 使用环境变量 `WORKBENCH_SECRET_KEY` 做本地加密 key。
- 如果未配置，开发环境允许 fallback 到固定 dev key，并在 `/health` 标记 `credential_security: dev`.
- API 默认不返回明文 key。
- 明文 key 只能通过独立的受权限控制接口临时返回。
- 每次查看明文 key 必须写入 `model_provider.secret_viewed` 审计事件。

## 3. API Contracts

```text
GET    /api/model-providers
POST   /api/model-providers
GET    /api/model-providers/{provider_id}
PATCH  /api/model-providers/{provider_id}
DELETE /api/model-providers/{provider_id}
POST   /api/model-providers/{provider_id}/test
POST   /api/model-providers/{provider_id}/models:refresh
GET    /api/models/available
```

Create request:

```json
{
  "tenant_id": "tenant_demo",
  "user_id": "tenant_admin",
  "name": "阿里云百炼",
  "provider_type": "openai_compatible",
  "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
  "api_key": "sk-xxx",
  "default_model": "qwen-plus",
  "scope": "tenant",
  "models": [
    {"model_id": "qwen-plus", "display_name": "通义千问 Plus"}
  ]
}
```

Response:

```json
{
  "provider_id": "provider_xxx",
  "name": "阿里云百炼",
  "provider_type": "openai_compatible",
  "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
  "credential": {"secret_last4": "abcd", "configured": true},
  "default_model": "qwen-plus",
  "enabled": true,
  "scope": "tenant",
  "models": []
}
```

## 4. Permission Rules

Use Phase B `PermissionService`:

```text
ordinary_user:
  - can GET /api/models/available
  - cannot create/edit/delete Provider
team_admin:
  - can choose team default among authorized models
tenant_admin:
  - can CRUD tenant Provider
system_admin:
  - can CRUD system Provider
```

Every mutation and connectivity test writes audit event:

```text
model_provider.created
model_provider.updated
model_provider.disabled
model_provider.deleted
model_provider.tested
model_provider.models_refreshed
```

## 5. Implementation Tasks

### Task 1: Persistent provider models

**Files:**

- Create: `backend/app/model_provider/models.py`
- Modify: `backend/app/models.py`
- Test: `backend/tests/test_model_provider_crud.py`

- [ ] Write failing tests for create/list/get Provider and model definitions.
- [ ] Implement SQLAlchemy models.
- [ ] Ensure metadata loads in `create_all`.
- [ ] Run `pytest backend/tests/test_model_provider_crud.py -q`.
- [ ] Commit: `feat: add model provider persistence models`.

Required tests:

```python
def test_create_provider_with_manual_models(session): ...
def test_disabled_provider_is_not_available(session): ...
```

### Task 2: Credential storage and masking

**Files:**

- Create: `backend/app/model_provider/credentials.py`
- Test: `backend/tests/test_model_provider_credentials.py`

- [ ] Write failing tests for encrypt/decrypt and mask.
- [ ] Implement `CredentialService.store_secret`.
- [ ] Implement `CredentialService.get_secret`.
- [ ] Implement `mask_secret(secret) -> ****last4`.
- [ ] Ensure API layer never serializes `secret_ciphertext`.
- [ ] Run credential tests.
- [ ] Commit: `feat: add model provider credential storage`.

### Task 3: Provider service

**Files:**

- Create: `backend/app/model_provider/service.py`
- Modify: `backend/app/model_providers.py`
- Test: `backend/tests/test_model_provider_crud.py`

- [ ] Write failing tests for CRUD service.
- [ ] Implement create/update/disable/delete/list.
- [ ] Enforce scope rules using Phase B permission service.
- [ ] Write audit events for mutations.
- [ ] Preserve Phase A `default_model_provider_registry()` behavior by reading DB first and env fallback second.
- [ ] Run tests.
- [ ] Commit: `feat: add model provider service`.

### Task 4: OpenAI-compatible connectivity and model refresh

**Files:**

- Create: `backend/app/model_provider/openai_compatible.py`
- Test: `backend/tests/test_model_provider_crud.py`

- [ ] Write tests with fake HTTP client for `/chat/completions` test call.
- [ ] Write tests with fake HTTP client for `/models` refresh.
- [ ] Implement `OpenAICompatibleProviderClient.test_connection`.
- [ ] Implement `OpenAICompatibleProviderClient.list_models`.
- [ ] Store refreshed models as `source=remote_refresh`.
- [ ] Run tests.
- [ ] Commit: `feat: add openai compatible provider checks`.

### Task 5: Provider routes

**Files:**

- Create: `backend/app/routes/model_providers.py`
- Modify: `backend/app/routes/models.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_model_provider_routes.py`

- [ ] Write failing API tests for CRUD, test, refresh, available models.
- [ ] Implement routes.
- [ ] Register router.
- [ ] Keep existing `/api/models/available` response compatible.
- [ ] Run route tests.
- [ ] Commit: `feat: expose model provider APIs`.

### Task 6: Runtime model selection

**Files:**

- Modify: `backend/app/agent_runtime.py`
- Test: `backend/tests/test_model_provider_routes.py`

- [ ] Add request field support for selected `provider_id/model_id` if current API already accepts model selection; otherwise only use default provider.
- [ ] Validate selected model is available to the user.
- [ ] Record `ModelCall.provider/model` from selected provider.
- [ ] Record `UsageMeter` provider/model consistently.
- [ ] Run backend regression.
- [ ] Commit: `feat: use configured model provider in runtime`.

## 6. Frontend Impact Gate

Phase C UI decision is confirmed:

```text
1. 使用完整设置页面，形态类似 Codex。
2. 入口为左下角“设置与模型”。
3. 普通用户可以看到 Provider 配置，但只能查看授权范围内字段，不能新增或编辑未授权配置。
4. API Key 默认脱敏展示。
5. 具备权限的管理员可以切换脱敏/非脱敏。
6. 查看 API Key 明文必须写审计事件。
7. 第一版只支持 OpenAI-compatible Provider，不做专有 SDK。
```

Frontend implementation can proceed under these constraints. If the concrete UI needs偏离 Codex-style 完整设置页，再重新确认。

## 7. Acceptance Checklist

- [ ] API Key does not appear in normal GET responses.
- [ ] API Key plaintext view requires explicit permission and writes audit.
- [ ] API Key stored server-side only.
- [ ] Manual model list works.
- [ ] `/models` refresh works with fake provider.
- [ ] Connectivity test records audit.
- [ ] Ordinary user cannot create Provider.
- [ ] Tenant admin can create tenant Provider.
- [ ] Available models are filtered by scope and permission.
- [ ] Runtime uses selected/default Provider.
- [ ] Existing Phase A/B tests pass.

## 8. Validation Commands

```bash
cd /Users/daniel/Desktop/code/工作台/workbench-app/frontend-v2/backend
pytest tests/test_model_provider_crud.py tests/test_model_provider_credentials.py tests/test_model_provider_routes.py -q
pytest -q
cd ..
python3 -m py_compile backend/app/*.py backend/app/routes/*.py backend/app/model_provider/*.py
```
