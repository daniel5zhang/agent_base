# Phase G Business Artifact Renderer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实现右侧业务面板 Artifact Renderer，让插件业务结果、查询计划、图表、表格、表单、审计信息可以从主对话结果卡片打开并按会话隔离。审批中心不放右侧业务面板。

**Architecture:** 后端提供 Artifact、版本、权限、下载申请和 renderer hint；主对话只展示结果链接卡片，右侧业务面板按 `artifact_id` 渲染。前端必须优先使用 assistant-ui 官方 Thread 外壳；右侧业务面板作为外挂区域，使用 assistant-ui/shadcn 技术栈实现。

**Tech Stack:** Backend: Python 3.11, FastAPI, SQLAlchemy, SQLite, pytest. Frontend: Next.js, React, assistant-ui, shadcn/ui, Vitest/Playwright.

---

## 0. Scope Boundary

### In scope

- Artifact 与 Thread/Run/Plugin 绑定。
- 每次业务查询或插件运行生成独立 Artifact。
- 主对话结果链接卡片。
- 点击卡片打开右侧对应 Artifact。
- 多 Tab，Tab 可关闭但不删除 Artifact。
- 通用 fallback renderer。
- 第一批 renderer：Table, Metric, Chart, Form, QueryPlan, AuditInfo, ErrorState。
- 下载、导出、复制权限判断和审计。
- 相同用户、相同 Artifact 内容、相同权限范围、相同操作类型下，已通过的权限审核可以复用，不需要重复审批。

### Out of scope

- 外部分享链接。
- 跨会话共享 Artifact。
- 高级图表编辑器。
- 大文件下载服务。
- 审批中心详情；审批中心属于设置页面。
- 权限外发审批之外的复杂数据脱敏策略；沿用 Phase B/F。

## 1. Target File Structure

### Backend create

```text
backend/app/artifacts/models.py
backend/app/artifacts/service.py
backend/app/artifacts/permissions.py
backend/app/artifacts/downloads.py
backend/app/routes/artifacts_v2.py
backend/tests/test_artifact_service.py
backend/tests/test_artifact_routes.py
backend/tests/test_artifact_permissions.py
```

### Backend modify

```text
backend/app/models.py
backend/app/routes/artifacts.py
backend/app/connectors/runtime.py
backend/app/agent_runtime.py
backend/app/main.py
backend/app/audit/service.py
```

### Frontend create or modify only after confirmation

```text
src/components/business-panel/artifact-panel.tsx
src/components/business-panel/artifact-tabs.tsx
src/components/business-panel/renderers/table-renderer.tsx
src/components/business-panel/renderers/metric-renderer.tsx
src/components/business-panel/renderers/chart-renderer.tsx
src/components/business-panel/renderers/form-renderer.tsx
src/components/business-panel/renderers/query-plan-renderer.tsx
src/components/business-panel/renderers/audit-info-renderer.tsx
src/components/business-panel/renderers/error-state-renderer.tsx
src/components/thread/artifact-link-card.tsx
```

## 2. Backend Data Model Contracts

Extend existing `Artifact` if possible. Add:

```text
ArtifactVersion
ArtifactPermission
ArtifactDownloadRequest
ArtifactRendererHint
```

Artifact required fields:

```text
artifact_id
tenant_id
workspace_id
thread_id
run_id
plugin_id
artifact_type
title
renderer_hint
summary
content_json
audit_event_id
created_at
updated_at
```

ArtifactVersion:

```text
version_id
artifact_id
version_number
content_json
created_by
created_at
```

ArtifactDownloadRequest:

```text
download_request_id
artifact_id
tenant_id
user_id
format
status: allowed | denied | approval_required
permission_decision_id
approval_id
audit_event_id
created_at
```

Permission review cache:

```text
artifact_permission_grant_id
tenant_id
user_id
artifact_id
artifact_content_hash
operation: copy | download | export
permission_scope_hash
approval_id
decision: allowed | denied | approval_required
expires_at
created_at
```

Rules:

```text
1. 首次复制、下载、导出必须进行权限判断。
2. 如果需要审批，则走 Phase F 审批中心。
3. 如果同一用户、同一 Artifact 内容 hash、同一权限范围 hash、同一操作类型已有有效通过记录，则复用，不重复审批。
4. Artifact 内容变更、权限范围变更、操作类型变更、授权过期，必须重新判断。
5. 每次复用授权仍写审计事件，标记 reused_grant_id。
```

## 3. Renderer Payload Contracts

### Metric

```json
{
  "renderer_hint": "metric",
  "title": "2026 年惠民保总保费",
  "metrics": [
    {"label": "总保费", "value": 1236000000, "display": "12.36 亿元", "unit": "CNY"}
  ],
  "audit_event_id": "evt_xxx"
}
```

### Table

```json
{
  "renderer_hint": "table",
  "columns": [{"key": "project", "label": "项目"}, {"key": "premium", "label": "保费"}],
  "rows": [{"project": "A", "premium": 100}],
  "row_count": 1
}
```

### QueryPlan

```json
{
  "renderer_hint": "query_plan",
  "subject": "惠民保项目",
  "metric": "总保费",
  "period": "2026",
  "aggregation": "sum",
  "permission_scope": {}
}
```

Fallback:

```json
{
  "renderer_hint": "json",
  "content": {}
}
```

## 4. API Contracts

```text
GET  /api/artifacts/{artifact_id}
GET  /api/threads/{thread_id}/artifacts
POST /api/artifacts/{artifact_id}/download-request
GET  /api/artifacts/{artifact_id}/versions
```

Artifact response:

```json
{
  "artifact_id": "artifact_xxx",
  "thread_id": "thread_001",
  "run_id": "run_001",
  "title": "2026 年惠民保总保费",
  "renderer_hint": "metric",
  "summary": "2026 年惠民保项目总保费为 12.36 亿元",
  "content": {},
  "audit_event_id": "evt_xxx",
  "permissions": {
    "can_view": true,
    "can_copy": true,
    "can_download": false,
    "download_requires_approval": true
  }
}
```

## 5. Main Chat Card Contract

Backend Runtime should add assistant message part or metadata:

```json
{
  "type": "artifact_link",
  "artifact_id": "artifact_xxx",
  "title": "2026 年惠民保总保费",
  "summary": "12.36 亿元",
  "renderer_hint": "metric",
  "audit_event_id": "evt_xxx"
}
```

Current frontend may not support parts. If not, Phase G backend can include a markdown-safe link text in `Message.content`, while frontend migration to rich card requires confirmation.

## 5.1 Controlled AI Dynamic UI Strategy

The frontend framework must support AI-driven dynamic UI through controlled Artifact schemas, not arbitrary model-generated React code.

Approved approach:

```text
Model / Plugin / Connector
  -> structured Artifact schema
  -> backend validates schema and permission
  -> backend returns renderer_hint
  -> frontend maps renderer_hint to whitelisted renderer
  -> right business panel renders UI
```

Allowed dynamic UI:

```text
metric
table
chart
form
query_plan
audit_info
error_state
json_fallback
```

Not allowed in Phase G:

```text
AI-generated React/JS code execution
AI-generated arbitrary HTML with scripts
Unregistered renderer_hint
Client-side permission bypass
```

If a renderer is not registered:

```text
1. Show fallback JSON/table renderer.
2. Display renderer_hint and artifact_id for diagnostics.
3. Do not execute arbitrary code.
```

## 6. Implementation Tasks

### Task 1: Backend artifact models and service

**Files:**

- Create: `backend/app/artifacts/models.py`
- Create: `backend/app/artifacts/service.py`
- Modify: `backend/app/models.py`
- Test: `backend/tests/test_artifact_service.py`

- [ ] Write tests for create artifact, create new version, list thread artifacts.
- [ ] Implement models.
- [ ] Implement `ArtifactService.create_artifact`.
- [ ] Ensure every create writes audit event.
- [ ] Run tests.
- [ ] Commit: `feat: add artifact service and versions`.

### Task 2: Artifact permissions and download requests

**Files:**

- Create: `backend/app/artifacts/permissions.py`
- Create: `backend/app/artifacts/downloads.py`
- Test: `backend/tests/test_artifact_permissions.py`

- [ ] Write tests for copy allowed, download denied, download approval_required.
- [ ] Use Phase B PermissionService.
- [ ] Use Phase F ApprovalService for approval_required.
- [ ] Write audit for every download request.
- [ ] Run tests.
- [ ] Commit: `feat: add artifact permission and download requests`.

### Task 3: Artifact routes

**Files:**

- Create: `backend/app/routes/artifacts_v2.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_artifact_routes.py`

- [ ] Write tests for get artifact, list thread artifacts, versions, download request.
- [ ] Implement routes.
- [ ] Register router without breaking existing `routes/artifacts.py`.
- [ ] Run tests.
- [ ] Commit: `feat: expose artifact renderer APIs`.

### Task 4: Connector/Runtime artifact creation integration

**Files:**

- Modify: `backend/app/connectors/runtime.py`
- Modify: `backend/app/agent_runtime.py`
- Test: `backend/tests/test_artifact_service.py`

- [ ] ConnectorResult artifacts create persistent Artifact rows.
- [ ] Assistant response includes artifact link metadata.
- [ ] Multiple queries in same thread create multiple artifacts.
- [ ] Closing a UI tab must not delete backend artifact.
- [ ] Run backend regression.
- [ ] Commit: `feat: create artifacts from connector results`.

### Task 5: Frontend implementation checkpoint

Phase G UI decision is confirmed:

```text
1. 右侧面板只承载业务 Artifact，属于前端框架中的业务嵌入区域。
2. 主对话结果卡片点击后打开右侧 Artifact。
3. 多次查询每次生成独立 Artifact 和独立卡片。
4. Tab 关闭只关闭显示，不删除 Artifact。
5. 下载、导出、复制都需要权限判断和审计。
6. 相同内容、相同用户、相同权限范围、相同操作类型可复用已通过审核，不重复审核。
7. AI 动态 UI 使用受控 Artifact schema + renderer_hint 白名单，不允许 AI 直接生成并执行 React 代码。
```

Frontend implementation can proceed under these constraints.

### Task 6: Frontend artifact link card

**Files:**

- Create: `src/components/thread/artifact-link-card.tsx`
- Modify: current thread message rendering file after locating it with `rg "Thread" src`
- Test: frontend test file to be identified by current test layout

- [ ] Write component test for click event.
- [ ] Render artifact card from message metadata or fallback marker.
- [ ] On click, call business panel open function with `artifact_id`.
- [ ] Run `npm test -- --run`.
- [ ] Commit: `feat: add artifact link cards`.

### Task 7: Frontend business panel tabs and renderers

**Files:**

- Create renderer files listed in section 1.
- Modify existing business panel component.

- [ ] Implement tabs with close button on hover.
- [ ] Fetch artifact by id.
- [ ] Render by `renderer_hint`.
- [ ] Implement fallback JSON renderer.
- [ ] Reject unregistered renderer hints and fall back safely.
- [ ] Show audit id top meta and bottom audit area.
- [ ] Handle error state with retry and audit/event id.
- [ ] Run frontend tests and Playwright smoke.
- [ ] Commit: `feat: render business artifacts in side panel`.

## 7. Acceptance Checklist

- [ ] Artifact belongs to thread and session.
- [ ] Every plugin/business query creates a new Artifact.
- [ ] Main conversation shows result link card.
- [ ] Clicking card opens right panel.
- [ ] Multiple cards open multiple tabs.
- [ ] Tab close does not delete Artifact.
- [ ] Renderer fallback works.
- [ ] Audit id is visible.
- [ ] Download request is permissioned and audited.
- [ ] Export and copy requests are permissioned and audited.
- [ ] Same-content permission review can be reused with audit.
- [ ] Permission insufficient state shows application entry.
- [ ] Existing Phase A-F tests pass.

## 8. Frontend Implementation Rule

Phase G includes frontend. The priority order remains:

```text
1. assistant-ui official shell and components
2. shadcn/ui components
3. custom components only for business panel gaps
```

Do not replace assistant-ui Thread shell.

Do not allow AI-generated arbitrary frontend code execution. Dynamic UI must be rendered through whitelisted Artifact Renderer components.

## 9. Validation Commands

Backend:

```bash
cd /Users/daniel/Desktop/code/工作台/workbench-app/frontend-v2/backend
pytest tests/test_artifact_service.py tests/test_artifact_routes.py tests/test_artifact_permissions.py -q
pytest -q
```

Frontend after confirmed UI implementation:

```bash
cd /Users/daniel/Desktop/code/工作台/workbench-app/frontend-v2
npm test -- --run
npm run lint
```

Playwright smoke after frontend:

```text
1. Start backend
2. Start frontend
3. Send business query
4. Verify main chat card
5. Click card
6. Verify right panel artifact
7. Close tab
8. Click card again
9. Verify artifact reopens
```
