# Phase F Approval Center Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实现审批申请、审批流转、审批详情、mock 审批、拒绝重提和审批通过后手动恢复执行闭环。

**Architecture:** 审批中心采用 Provider 抽象，优先自建审批，预留钉钉和企业微信 Provider。Phase F 后端实现完整审批状态机和 resume token；前端审批 Tab、主对话审批卡片属于 UI 变更，需要确认后实施。

**Tech Stack:** Python 3.11, FastAPI, SQLAlchemy, SQLite, pytest.

---

## 0. Scope Boundary

### In scope

- 自建审批 Provider。
- 钉钉/企业微信 Provider 抽象和 stub。
- 审批对象：数据权限、插件授权、高风险工具、数据导出、跨机构数据访问。
- 审批状态机。
- 审批通过后不自动恢复，用户点击继续执行。
- 审批拒绝后修改范围重新提交。
- 默认 7 天过期，可配置。
- 审批事件审计。

### Out of scope

- 模型外发敏感数据审批。
- 真实钉钉/企业微信 API 对接。
- 复杂多级审批流设计器。
- 前端审批 Tab 自动开发。

## 1. Target File Structure

### Create

```text
backend/app/approvals/__init__.py
backend/app/approvals/models.py
backend/app/approvals/state.py
backend/app/approvals/service.py
backend/app/approvals/providers/__init__.py
backend/app/approvals/providers/base.py
backend/app/approvals/providers/internal.py
backend/app/approvals/providers/dingtalk.py
backend/app/approvals/providers/wecom.py
backend/app/routes/approvals.py
backend/tests/test_approval_state.py
backend/tests/test_approval_service.py
backend/tests/test_approval_routes.py
```

### Modify

```text
backend/app/models.py
backend/app/connectors/runtime.py
backend/app/plugins/authorization.py
backend/app/agent_runtime.py
backend/app/main.py
backend/app/audit/service.py
```

## 2. Approval Types

```text
data_permission
plugin_authorization
high_risk_tool_call
data_export
cross_org_data_access
```

Required request fields:

```text
approval_id
tenant_id
workspace_id
thread_id
run_id
requester_user_id
approval_type
resource_type
resource_id
requested_scope_json
reason
status
provider
expires_at
created_at
updated_at
```

Decision fields:

```text
decision_id
approval_id
decider_user_id
decision: approved | rejected
comment
approved_scope_json
created_at
```

Resume token:

```text
resume_token_id
approval_id
run_id
tool_invocation_id
resume_payload_json
used
expires_at
```

## 3. State Machine

```text
created -> submitted
submitted -> pending
pending -> approved
pending -> rejected
pending -> expired
pending -> cancelled
rejected -> submitted
approved -> resumed
```

Terminal:

```text
expired
cancelled
resumed
```

Rules:

- approved does not auto-run.
- only `approved -> resumed` when user clicks continue.
- rejected can resubmit with changed scope.
- expired cannot approve.

## 4. API Contracts

```text
POST /api/approvals
GET  /api/approvals/{approval_id}
POST /api/approvals/{approval_id}/approve
POST /api/approvals/{approval_id}/reject
POST /api/approvals/{approval_id}/resubmit
POST /api/approvals/{approval_id}/resume-run
GET  /api/approvals
```

Create request:

```json
{
  "tenant_id": "tenant_demo",
  "workspace_id": "workspace_default",
  "thread_id": "thread_001",
  "run_id": "run_001",
  "requester_user_id": "user_demo",
  "approval_type": "data_permission",
  "resource_type": "warehouse_table",
  "resource_id": "premium_summary",
  "requested_scope": {"region": "全国", "year": "2026"},
  "reason": "查询惠民保总保费"
}
```

Resume response:

```json
{
  "approval_id": "approval_xxx",
  "run_id": "run_new_or_resumed",
  "status": "resumed",
  "message": "已恢复执行"
}
```

## 5. Implementation Tasks

### Task 1: Approval models and state machine

**Files:**

- Create: `backend/app/approvals/models.py`
- Create: `backend/app/approvals/state.py`
- Modify: `backend/app/models.py`
- Test: `backend/tests/test_approval_state.py`

- [ ] Write tests for valid and invalid transitions.
- [ ] Implement SQLAlchemy models.
- [ ] Implement `assert_approval_transition`.
- [ ] Run tests.
- [ ] Commit: `feat: add approval models and state machine`.

### Task 2: Provider abstraction and internal provider

**Files:**

- Create: `backend/app/approvals/providers/base.py`
- Create: `backend/app/approvals/providers/internal.py`
- Create: `backend/app/approvals/providers/dingtalk.py`
- Create: `backend/app/approvals/providers/wecom.py`
- Test: `backend/tests/test_approval_service.py`

- [ ] Write tests for provider selection priority: internal, dingtalk, wecom.
- [ ] Implement base provider interface.
- [ ] Implement internal provider submit/approve/reject as local DB operations.
- [ ] Implement DingTalk/WeCom stubs returning unsupported in Phase F.
- [ ] Run tests.
- [ ] Commit: `feat: add approval provider abstraction`.

### Task 3: Approval service

**Files:**

- Create: `backend/app/approvals/service.py`
- Test: `backend/tests/test_approval_service.py`

- [ ] Write tests for create, approve, reject, resubmit, expire.
- [ ] Implement expiration default 7 days.
- [ ] Implement scope mutation on resubmit.
- [ ] Write audit events for every transition.
- [ ] Run tests.
- [ ] Commit: `feat: add approval service`.

### Task 4: Resume token and blocked run integration

**Files:**

- Modify: `backend/app/connectors/runtime.py`
- Modify: `backend/app/agent_runtime.py`
- Modify: `backend/app/approvals/service.py`
- Test: `backend/tests/test_approval_service.py`

- [ ] When connector returns `approval_required`, create approval and resume token.
- [ ] Mark run as `waiting_approval`.
- [ ] Do not auto-resume after approval.
- [ ] On `resume-run`, validate approval approved and token unused.
- [ ] Mark token used.
- [ ] Resume tool call or create retry run according to Phase A Run state rules.
- [ ] Run tests.
- [ ] Commit: `feat: support approval gated run resume`.

### Task 5: Approval routes

**Files:**

- Create: `backend/app/routes/approvals.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_approval_routes.py`

- [ ] Write route tests for create/list/detail/approve/reject/resubmit/resume.
- [ ] Enforce Phase B permission checks.
- [ ] Register router.
- [ ] Run route tests.
- [ ] Commit: `feat: expose approval APIs`.

### Task 6: Audit and permission integration

**Files:**

- Modify: `backend/app/iam/policy.py`
- Modify: `backend/app/audit/service.py`
- Test: `backend/tests/test_approval_service.py`

- [ ] PermissionService returns `approval_required` with approval type and requested scope.
- [ ] ApprovalService writes `approval.requested`, `approval.approved`, `approval.rejected`, `approval.resumed`.
- [ ] Audit query can filter by `approval_id`.
- [ ] Run backend regression.
- [ ] Commit: `feat: integrate approval with permission and audit`.

## 6. Frontend Impact Gate

Before UI implementation, confirm:

```text
1. 主对话审批摘要卡片样式
2. 右侧审批 Tab 内容结构
3. 审批通过后“继续执行”按钮位置
4. 拒绝后重新提交表单字段
5. 审批列表是否进入插件中心/设置页/独立入口
```

No frontend changes without confirmation.

## 7. Acceptance Checklist

- [ ] Over-permission operation creates approval request.
- [ ] Internal mock approval can approve/reject.
- [ ] Approved request does not auto-resume.
- [ ] User clicks resume-run and execution resumes.
- [ ] Rejected request can resubmit with changed scope.
- [ ] Expired request cannot approve.
- [ ] Every approval transition writes audit.
- [ ] DingTalk/WeCom provider stubs exist.
- [ ] Existing Phase A-E tests pass.

## 8. Validation Commands

```bash
cd /Users/daniel/Desktop/code/工作台/workbench-app/frontend-v2/backend
pytest tests/test_approval_state.py tests/test_approval_service.py tests/test_approval_routes.py -q
pytest -q
cd ..
python3 -m py_compile backend/app/*.py backend/app/routes/*.py backend/app/approvals/*.py backend/app/approvals/providers/*.py
```

