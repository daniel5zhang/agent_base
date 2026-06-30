# Phase B IAM RBAC ABAC Audit Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 建立工作台自有企业账号、组织、角色、权限、数据范围和审计监管底座，第三方 SSO 只作为身份源映射。

**Architecture:** 新增 `iam` 与 `audit` 两个后端子域。`iam` 负责租户、用户、组织、角色、权限、RBAC/ABAC 决策；`audit` 负责审计事件写入、脱敏、查询、导出和 hash chain。Phase B 先提供服务端能力和 API，不新增前端页面；如必须增加设置页入口，需要先确认。

**Tech Stack:** Python 3.11, FastAPI, SQLAlchemy, SQLite, pytest.

---

## 0. Scope Boundary

### In scope

- Workbench 自有租户、用户、组织、部门、团队、角色、权限模型。
- 第三方 SSO 映射模型，先支持通用映射结构，不接真实钉钉/企业微信。
- RBAC + ABAC 权限决策服务。
- deny 优先。
- 权限变更后下一次权限判断立即生效；Phase B 不引入 Redis。
- 审计事件统一服务、敏感字段脱敏、hash chain。
- 审计查询与导出 API。
- 审计访问控制：本人、团队管理员、租户管理员、审计管理员、系统管理员。

### Out of scope

- 真实 SSO 登录协议。
- 真实钉钉组织同步。
- 前端 IAM 管理页。
- 前端审计查询页。
- 生产 WORM/object storage。
- 数据仓库字段级/行级真实执行；Phase B 只设计和记录 `DataScopePolicy`。

## 1. Target File Structure

### Create

```text
backend/app/iam/__init__.py
backend/app/iam/models.py
backend/app/iam/repositories.py
backend/app/iam/policy.py
backend/app/iam/sso_mapping.py
backend/app/iam/seed.py
backend/app/audit/__init__.py
backend/app/audit/service.py
backend/app/audit/hash_chain.py
backend/app/audit/export.py
backend/app/routes/iam.py
backend/app/routes/audit.py
backend/tests/test_iam_policy.py
backend/tests/test_audit_service.py
backend/tests/test_audit_routes.py
```

### Modify

```text
backend/app/models.py
backend/app/main.py
backend/app/agent_runtime.py
backend/app/routes/runtime.py
backend/app/routes/models.py
backend/app/routes/plugins.py
```

## 2. Data Model Contracts

Add to `backend/app/iam/models.py` as SQLAlchemy models using the shared `Base`.

```text
Tenant
User
Organization
Department
Group
Role
Permission
UserRole
UserGroup
UserDepartment
WorkspacePermission
PluginPermission
ModelProviderPermission
DataScopePolicy
PermissionDecision
ExternalIdentityMapping
```

Required fields:

```text
tenant_id, name, status
user_id, tenant_id, display_name, email, mobile_masked, status
department_id, tenant_id, parent_department_id, name, path
role_id, tenant_id, role_key, name, scope
permission_id, tenant_id, permission_key, resource_type, action, effect
data_scope_policy_id, tenant_id, resource_type, scope_json, effect
decision_id, tenant_id, user_id, resource_type, resource_id, action, decision, reason, policy_snapshot_json
external_identity_id, tenant_id, provider, external_user_id, mapped_user_id, raw_profile_json
```

Default roles:

```text
ordinary_user
team_admin
tenant_admin
system_admin
audit_admin
```

Default permission keys:

```text
agent.chat.use
workspace.read
model.use
model_provider.manage
plugin.view
plugin.enable
plugin.manage
connector.invoke
approval.review
audit.own.read
audit.team.read
audit.tenant.read
audit.full.read
audit.export
```

## 3. Permission Decision Contract

Create `backend/app/iam/policy.py`.

Input:

```python
PermissionCheck(
    tenant_id="tenant_demo",
    user_id="user_demo",
    workspace_id="workspace_default",
    resource_type="plugin",
    resource_id="ask-data",
    action="plugin.enable",
    attributes={"risk_tier": "L1", "department_id": "dept_001"},
)
```

Output:

```json
{
  "decision": "allow | deny | approval_required",
  "reason": "role_permission_allowed",
  "matched_policies": [],
  "data_scope": {},
  "audit_event_id": "evt_xxx"
}
```

Rules:

- explicit deny wins.
- missing permission returns deny.
- high-risk operation may return `approval_required` if configured.
- every decision writes `PermissionDecision`.
- every decision writes `AuditEvent` through `AuditService`.

## 4. Audit Contract

Use existing `AuditEvent` table if possible, extend it only if necessary. If extending `backend/app/models.py`, keep current fields compatible and add nullable fields:

```text
actor_user_id
workspace_id
thread_id
resource_type
resource_id
operation
risk_tier
result
masked_payload_json
payload_hash
hash_prev
hash_current
```

Audit event types Phase B must support:

```text
auth.login
auth.logout
agent.user_message
agent.prompt
agent.model_output
model.call
tool.call
plugin.call
permission.decision
approval.requested
approval.decided
business.query
data.export
artifact.created
config.changed
plugin.enabled
plugin.disabled
model_provider.changed
audit.export
audit.plaintext_viewed
```

Sensitive field masking:

```text
api_key -> ****last4
mobile -> first3****last4
email -> first2****domain
id_no -> first3********last4
prompt/model output -> kept, but marked sensitivity_level
business result -> masked by policy if sensitive
```

Retention defaults:

```text
general audit: 180 days
high-risk/business data: 365 days
config/security events: 365 days
```

## 5. API Contracts

### IAM

```text
GET  /api/iam/me
GET  /api/iam/users/{user_id}/permissions
POST /api/iam/permission-decisions
GET  /api/iam/roles
GET  /api/iam/departments
```

### Audit

```text
GET  /api/audit/events
POST /api/audit/export
GET  /api/audit/exports/{export_id}
```

Query filters:

```text
start_at
end_at
user_id
plugin_id
tool_id
business_system
approval_id
audit_event_id
risk_tier
operation
limit
```

Export request:

```json
{
  "tenant_id": "tenant_demo",
  "user_id": "audit_admin",
  "format": "csv | json",
  "filters": {
    "operation": "model.call"
  }
}
```

## 6. Implementation Tasks

### Task 1: IAM model and seed baseline

**Files:**

- Create: `backend/app/iam/models.py`
- Create: `backend/app/iam/seed.py`
- Modify: `backend/app/models.py`
- Test: `backend/tests/test_iam_policy.py`

- [ ] Write failing tests for default tenant, user, roles, and deny-wins behavior.
- [ ] Implement IAM SQLAlchemy models.
- [ ] Import models from `backend/app/models.py` or ensure metadata is loaded before `create_all`.
- [ ] Implement `seed_demo_iam(session)` with `tenant_demo`, `user_demo`, `ordinary_user`, `tenant_admin`, `audit_admin`.
- [ ] Run `pytest backend/tests/test_iam_policy.py -q`.
- [ ] Commit: `feat: add iam models and demo seed`.

Required test cases:

```python
def test_seed_demo_iam_creates_default_roles(session): ...
def test_user_can_have_multiple_departments(session): ...
def test_permission_deny_wins(session): ...
```

### Task 2: RBAC/ABAC policy evaluator

**Files:**

- Create: `backend/app/iam/policy.py`
- Create: `backend/app/iam/repositories.py`
- Test: `backend/tests/test_iam_policy.py`

- [ ] Write failing tests for allow, deny, approval_required.
- [ ] Implement `PermissionCheck` and `PermissionDecisionResult` dataclasses.
- [ ] Implement `PermissionService.evaluate(check)`.
- [ ] Persist every decision to `PermissionDecision`.
- [ ] Do not cache permission decisions in Phase B.
- [ ] Run `pytest backend/tests/test_iam_policy.py -q`.
- [ ] Commit: `feat: add rbac abac permission service`.

Required behavior:

```text
ordinary_user + agent.chat.use -> allow
ordinary_user + model_provider.manage -> deny
tenant_admin + plugin.manage -> allow
explicit deny + any allow -> deny
risk_tier L3 + approval policy -> approval_required
```

### Task 3: SSO mapping abstraction

**Files:**

- Create: `backend/app/iam/sso_mapping.py`
- Test: `backend/tests/test_iam_policy.py`

- [ ] Write failing tests for DingTalk-like and WeCom-like external user mapping.
- [ ] Implement `ExternalIdentityMappingService.map_external_user(...)`.
- [ ] Store provider, external user id, mapped user id, raw profile JSON.
- [ ] Do not implement real OAuth.
- [ ] Run tests.
- [ ] Commit: `feat: add external identity mapping abstraction`.

### Task 4: Audit service and hash chain

**Files:**

- Create: `backend/app/audit/service.py`
- Create: `backend/app/audit/hash_chain.py`
- Modify: `backend/app/models.py`
- Test: `backend/tests/test_audit_service.py`

- [ ] Write failing tests for audit append, masking, hash chain.
- [ ] Implement `mask_sensitive_payload(payload)`.
- [ ] Implement `AuditService.append_event(...)`.
- [ ] Compute `payload_hash`, `hash_prev`, `hash_current`.
- [ ] Store masked payload in query-visible field.
- [ ] Run `pytest backend/tests/test_audit_service.py -q`.
- [ ] Commit: `feat: add audit service with hash chain`.

Required tests:

```python
def test_audit_masks_api_key_and_mobile(session): ...
def test_audit_hash_chain_links_events(session): ...
def test_plaintext_view_creates_audit_event(session): ...
```

### Task 5: IAM and audit routes

**Files:**

- Create: `backend/app/routes/iam.py`
- Create: `backend/app/routes/audit.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_audit_routes.py`

- [ ] Write failing API tests.
- [ ] Implement `GET /api/iam/me`.
- [ ] Implement `POST /api/iam/permission-decisions`.
- [ ] Implement `GET /api/audit/events`.
- [ ] Implement `POST /api/audit/export`.
- [ ] Implement `GET /api/audit/exports/{export_id}`.
- [ ] Register routers in `main.py`.
- [ ] Run route tests.
- [ ] Commit: `feat: expose iam and audit APIs`.

### Task 6: Integrate permission and audit into runtime baseline

**Files:**

- Modify: `backend/app/agent_runtime.py`
- Modify: `backend/app/routes/runtime.py`
- Modify: `backend/app/routes/models.py`
- Test: `backend/tests/test_phase1_agent_runtime.py`
- Test: `backend/tests/test_audit_service.py`

- [ ] Before model call, evaluate `model.use`.
- [ ] Before tool call, evaluate `connector.invoke` or tool-specific permission.
- [ ] Write audit for user message, prompt, model output, model call, tool call, permission decision.
- [ ] If permission result is deny, return blocked response.
- [ ] If permission result is approval_required, return `approval_required` status but Phase F will create actual approval.
- [ ] Run backend regression.
- [ ] Commit: `feat: integrate iam audit with agent runtime`.

## 7. Acceptance Checklist

- [ ] Demo IAM seed creates tenant/user/roles/permissions.
- [ ] RBAC allow/deny works.
- [ ] ABAC attributes are accepted and persisted in decision snapshot.
- [ ] deny wins.
- [ ] Permission changes affect next decision without Redis.
- [ ] Audit event is written for every permission decision.
- [ ] Sensitive fields are masked by default.
- [ ] Plaintext view writes audit event.
- [ ] Audit hash chain links events.
- [ ] Audit export is permission-checked and audited.
- [ ] Existing Phase A tests still pass.

## 8. Frontend Impact

No frontend implementation in Phase B.

Allowed backend-compatible additions:

- Existing frontend may call `GET /api/iam/me` later.
- Existing frontend behavior must not break if it ignores IAM routes.

Not allowed without confirmation:

- Add settings page.
- Add audit page.
- Change model selector authorization UI.
- Change thread list behavior.

## 9. Validation Commands

```bash
cd /Users/daniel/Desktop/code/工作台/workbench-app/frontend-v2/backend
pytest tests/test_iam_policy.py tests/test_audit_service.py tests/test_audit_routes.py -q
pytest -q
cd ..
python3 -m py_compile backend/app/*.py backend/app/routes/*.py backend/app/iam/*.py backend/app/audit/*.py
```

