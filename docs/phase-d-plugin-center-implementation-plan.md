# Phase D Codex-style Plugin Center Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 建设 Codex-style 插件中心，支持插件发布、可见性、授权、启停、升级、能力暴露、Skill 指令和审计。Web 形态用户侧弱化“安装”，以“申请授权 / 启用 / 停用 / 使用”为主。

**Architecture:** 插件分为 `PluginPackage`、`Skill`、`Tool/Capability`、`ConnectorBinding`、`UIRenderer`、`Permission/Approval/Audit` 六层。Phase D 只实现插件中心和能力注册，不实现真实 Connector 调用；Connector Runtime 在 Phase E 接入。

**Tech Stack:** Python 3.11, FastAPI, SQLAlchemy, SQLite, pytest. Frontend uses assistant-ui/shadcn inside the confirmed Codex-style settings page.

---

## 0. Scope Boundary

### In scope

- 插件包、版本、manifest。
- 插件目录 catalog。
- 服务端发布和管理员启用插件。
- 用户侧授权、启停、使用状态机。
- 插件 Skill 文本和工具能力 schema。
- 插件可见性规则和角色/工作空间过滤。
- 插件审计事件。
- 内置 mock 插件：`ask-data`。

### Out of scope

- 插件包真实下载、签名验签、沙箱解压。
- 外部插件市场。
- 真实业务 Connector 执行。
- 插件前端中心 UI 自动开发；已确认 UI 方向为设置页面菜单中的完整页面。

## 1. Target File Structure

### Create

```text
backend/app/plugins/__init__.py
backend/app/plugins/models.py
backend/app/plugins/manifest.py
backend/app/plugins/registry.py
backend/app/plugins/installation.py
backend/app/plugins/authorization.py
backend/app/plugins/release_policy.py
backend/app/plugins/seed.py
backend/app/routes/plugins_admin.py
backend/tests/test_plugin_manifest.py
backend/tests/test_plugin_lifecycle.py
backend/tests/test_plugin_catalog_routes.py
```

### Modify

```text
backend/app/models.py
backend/app/routes/plugins.py
backend/app/main.py
backend/app/agent_runtime.py
backend/app/iam/policy.py
backend/app/audit/service.py
```

## 2. Plugin Manifest Contract

Manifest shape:

```json
{
  "plugin_id": "ask-data",
  "name": "问数插件",
  "version": "0.1.0",
  "plugin_type": "internal_business",
  "description": "查询公司数仓指标",
  "risk_tier": "L1",
  "skills": [
    {
      "skill_id": "ask_data_query_skill",
      "trigger_examples": ["查 2026 年惠民保总保费"],
      "instructions": "当用户询问公司业务指标时，先确认口径和权限，再调用 ask_data.query。"
    }
  ],
  "capabilities": [
    {
      "capability_id": "ask_data.query",
      "tool_id": "ask_data.query",
      "input_schema": {},
      "output_schema": {},
      "risk_tier": "L1",
      "requires_authorization": true,
      "requires_approval": false
    }
  ],
  "connectors": [
    {
      "connector_id": "warehouse.ask-data.mock",
      "binding_required": true
    }
  ],
  "ui_renderers": [
    {
      "renderer_id": "ask_data.result",
      "renderer_hint": "table_metric_chart"
    }
  ]
}
```

## 3. Data Model Contracts

Create:

```text
PluginVersion
PluginEnablement
PluginAuthorization
PluginVisibilityRule
PluginCapability
PluginSkill
PluginUIRenderer
PluginAuditEvent
```

Reuse or extend existing:

```text
PluginPackage
ReleasePolicy
ServerBinding
```

Status values:

```text
published
visible
authorization_required
authorized
enabled
disabled
upgrade_available
deprecated
removed
```

User-visible status:

```text
待授权
已启用
已停用
可升级
不可用
```

## 4. API Contracts

```text
GET    /api/plugins/catalog
GET    /api/plugins/{plugin_id}
POST   /api/plugins/{plugin_id}/authorize
POST   /api/plugins/{plugin_id}/enable
POST   /api/plugins/{plugin_id}/disable
POST   /api/plugins/{plugin_id}/upgrade
GET    /api/plugins/{plugin_id}/audit-events
GET    /api/plugins/admin/packages
POST   /api/plugins/admin/packages
PATCH  /api/plugins/admin/packages/{plugin_id}
```

Catalog query:

```text
tenant_id
workspace_id
user_id
role
```

Catalog response includes:

```json
{
  "plugins": [
    {
      "plugin_id": "ask-data",
      "name": "问数插件",
      "plugin_type": "internal_business",
  "status": "enabled",
      "user_visible_status": "已启用",
      "capabilities": ["ask_data.query"],
      "risk_tier": "L1",
      "requires_authorization": true
    }
  ]
}
```

## 5. Permission Rules

```text
ordinary_user:
  - view visible plugins
  - request authorization
  - enable/disable authorized plugins if allowed
  - use authorized plugins
  - cannot publish or tenant-enable internal business plugins
tenant_admin:
  - tenant-enable plugin released by system/admin
  - authorize tenant plugin
  - enable/disable tenant plugin
system_admin:
  - publish/admin packages
audit_admin:
  - read plugin audit events within authorized scope
```

Every lifecycle operation writes:

```text
plugin.package_created
plugin.tenant_enabled
plugin.authorization_requested
plugin.authorized
plugin.enabled
plugin.disabled
plugin.upgraded
plugin.deprecated
```

## 6. Implementation Tasks

### Task 1: Plugin manifest parser and validation

**Files:**

- Create: `backend/app/plugins/manifest.py`
- Test: `backend/tests/test_plugin_manifest.py`

- [ ] Write failing tests for valid manifest and missing required fields.
- [ ] Implement Pydantic models for manifest.
- [ ] Validate plugin id, version, capability ids, connector ids, renderer hints.
- [ ] Reject duplicate capability ids.
- [ ] Run tests.
- [ ] Commit: `feat: add plugin manifest validation`.

### Task 2: Plugin persistence models

**Files:**

- Create: `backend/app/plugins/models.py`
- Modify: `backend/app/models.py`
- Test: `backend/tests/test_plugin_lifecycle.py`

- [ ] Write failing tests for package/version/installation/authorization rows.
- [ ] Implement SQLAlchemy models.
- [ ] Ensure metadata loads.
- [ ] Run tests.
- [ ] Commit: `feat: add plugin lifecycle models`.

### Task 3: Plugin registry and seed ask-data

**Files:**

- Create: `backend/app/plugins/registry.py`
- Create: `backend/app/plugins/seed.py`
- Test: `backend/tests/test_plugin_lifecycle.py`

- [ ] Write tests for registering `ask-data` from manifest.
- [ ] Implement `PluginRegistry.publish_package`.
- [ ] Implement seed package `ask-data`.
- [ ] Persist capabilities, skills, renderers.
- [ ] Run tests.
- [ ] Commit: `feat: add plugin registry and ask data seed`.

### Task 4: Enablement and authorization service

**Files:**

- Create: `backend/app/plugins/installation.py`
- Create: `backend/app/plugins/authorization.py`
- Test: `backend/tests/test_plugin_lifecycle.py`

- [ ] Write tests for tenant enablement, user authorization request, authorize, enable, disable, upgrade.
- [ ] Enforce status transitions.
- [ ] Enforce Phase B permissions.
- [ ] Write audit events.
- [ ] Run tests.
- [ ] Commit: `feat: add plugin enablement authorization service`.

### Task 5: Catalog filtering

**Files:**

- Create: `backend/app/plugins/release_policy.py`
- Modify: `backend/app/routes/plugins.py`
- Test: `backend/tests/test_plugin_catalog_routes.py`

- [ ] Write tests: `data_analyst` sees `ask-data`, non-matching role does not.
- [ ] Filter by tenant, workspace, role, tenant enablement, authorization, enabled status.
- [ ] Do not expose unauthorized internal business plugin in `+` menu.
- [ ] Preserve current `/api/plugins/catalog` compatibility.
- [ ] Run tests.
- [ ] Commit: `feat: filter plugin catalog by visibility and authorization`.

### Task 6: Plugin admin routes

**Files:**

- Create: `backend/app/routes/plugins_admin.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_plugin_catalog_routes.py`

- [ ] Write tests for package list/create/patch.
- [ ] Implement admin routes with permission checks.
- [ ] Register router.
- [ ] Run tests.
- [ ] Commit: `feat: expose plugin admin APIs`.

### Task 7: Runtime tool pool integration

**Files:**

- Modify: `backend/app/agent_runtime.py`
- Test: `backend/tests/test_plugin_lifecycle.py`

- [ ] Before each run, load enabled plugin capabilities for tenant/user/workspace.
- [ ] Add plugin Skill text to model context only for visible enabled plugins.
- [ ] Expose plugin capability to ToolPool only if authorized.
- [ ] If capability requires approval, return `approval_required` with a deterministic payload: `approval_type`, `resource_type`, `resource_id`, `requested_scope`, and `reason`; Phase F will consume this payload to create the approval request.
- [ ] Run backend regression.
- [ ] Commit: `feat: integrate plugin catalog with runtime tool pool`.

## 7. Frontend Impact Gate

Plugin center UI decision is confirmed:

```text
1. 插件中心作为设置页面里的一个菜单，打开完整页面，形态类似 Codex。
2. 插件主视图按业务类型组织，例如问数、理赔、投保、查询、办公、本地文件、外部通用。
3. 全部插件、已授权、待授权、可升级、已停用、管理员管理、审计记录作为筛选条件，不作为主分区。
4. Web 形态普通用户不显示“安装”，只显示“申请授权 / 启用 / 停用 / 使用”。
5. 管理员管理和审计记录第一版展示。
```

Frontend implementation can proceed under these constraints. If the UI needs偏离设置页完整页面或 Codex-style，需要重新确认。

Implementation notes:

```text
1. Backend can keep `PluginInstallation` table name if already implemented, but user-facing wording must be `授权/启用/使用`.
2. API can keep admin installation semantics internally, but frontend must not expose install to ordinary web users.
```

## 8. Acceptance Checklist

- [ ] `ask-data` plugin seeded.
- [ ] Catalog filters by tenant/workspace/role/authorization.
- [ ] Unauthorized plugin not shown in `+` menu.
- [ ] Tenant admin can tenant-enable internal business plugin released by admin/system.
- [ ] Ordinary user cannot tenant-enable or publish plugin.
- [ ] Enable/disable writes audit.
- [ ] Plugin Skill can be loaded into runtime context.
- [ ] Plugin capabilities can be converted into ToolPool entries.
- [ ] Existing Phase A-C tests pass.

## 9. Validation Commands

```bash
cd /Users/daniel/Desktop/code/工作台/workbench-app/frontend-v2/backend
pytest tests/test_plugin_manifest.py tests/test_plugin_lifecycle.py tests/test_plugin_catalog_routes.py -q
pytest -q
cd ..
python3 -m py_compile backend/app/*.py backend/app/routes/*.py backend/app/plugins/*.py
```
