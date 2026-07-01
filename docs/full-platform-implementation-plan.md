# 完整平台任务级实施计划

版本：2026-06-30  
适用仓库：`daniel5zhang/agent_base`  
当前技术栈：前端 Next.js + assistant-ui；后端 Python FastAPI + SQLite  
参考架构：Codex-style Plugin Architecture + 金融企业权限、审批、审计、Connector Runtime

## 1. 目标

把工作台从当前的一阶段 Agent 原型，建设为完整企业 Agent 工作台平台：

```text
通用 Agent Runtime
+ 企业账号权限体系
+ 审计监管底座
+ 多模型 Provider 设置
+ Codex-style 插件中心
+ Connector Runtime
+ 审批中心
+ 右侧业务 Artifact 面板
```

本计划不直接写代码，而是作为进入开发前的任务级拆解依据。

## 2. 总体阶段

```text
Phase A：Agent Runtime 完整化
Phase B：企业账号权限 / RBAC+ABAC / 审计底座
Phase C：Model Provider 设置与密钥管理
Phase D：Codex-style 插件中心
Phase E：Connector Runtime
Phase F：审批中心
Phase G：右侧业务面板 Artifact Renderer
Phase H：前端 Runtime 迁移评估
```

阶段依赖：

```text
A 是底座，必须先做。
B 为权限、审计、审批、插件授权提供基础。
C 可与 D 并行，但密钥安全依赖 B 的权限模型。
D 依赖 A/B 的工具、权限、审计。
E 依赖 D 的插件/工具定义和 B 的权限审计。
F 依赖 A/B/E。
G 依赖 A/D/E/F 产出的 Artifact schema。
H 只能在 A-G 的核心事件协议稳定后评估。
```

## 3. Phase A：Agent Runtime 完整化

### 3.1 目标

实现完整通用 Agent Runtime：

```text
Thread 可恢复
Transcript 可回放
ToolResult 可回写模型
Run 状态机可靠
模型调用可统计
SSE 兼容现有 assistant-ui 前端
```

### 3.2 后端模块

新增或改造：

```text
backend/app/models.py
backend/app/transcript.py
backend/app/tool_result.py
backend/app/run_state.py
backend/app/model_providers.py
backend/app/usage.py
backend/app/agent_runtime.py
backend/app/routes/transcripts.py
backend/app/routes/models.py
backend/app/routes/runtime.py
```

### 3.3 数据模型

#### TranscriptEvent

```text
id
sequence
tenant_id
workspace_id
thread_id
run_id
role: user | assistant | tool | system
event_type
content_json
source_message_id
source_tool_invocation_id
source_runtime_event_id
created_at
```

事件类型第一批：

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

#### UsageMeter

```text
id
tenant_id
user_id
workspace_id
thread_id
run_id
provider_id
model_id
prompt_tokens
completion_tokens
total_tokens
latency_ms
estimated_cost
status
created_at
```

### 3.4 API

```text
GET /api/threads/{thread_id}/transcript
GET /api/runs/{run_id}/transcript
GET /api/runs/{run_id}/usage
```

### 3.5 ToolResult 标准

```json
{
  "tool_id": "ask_data.query",
  "status": "completed | failed | partial | blocked | approval_required",
  "response_text": "给主对话展示的摘要",
  "model_context": [],
  "output_payload": {},
  "artifacts": [],
  "audit_event_id": "evt_xxx",
  "error": null
}
```

### 3.6 验收

- 普通对话能写入 Message 和 TranscriptEvent；
- 工具调用能写入 assistant.tool_call 和 tool.result；
- tool_result 能回写下一轮模型上下文；
- cancel / retry / failed 状态一致；
- 前端历史仍通过 Message/UIMessage 加载；
- 后端测试覆盖 Run 状态机和 Transcript 双写。

## 4. Phase B：企业账号权限 / RBAC+ABAC / 审计底座

### 4.1 目标

建立工作台自有账号权限体系。第三方 SSO 只作为身份源和组织映射来源。

### 4.2 后端模块

```text
backend/app/iam/models.py
backend/app/iam/repositories.py
backend/app/iam/policy.py
backend/app/iam/sso_mapping.py
backend/app/audit/service.py
backend/app/audit/hash_chain.py
backend/app/routes/iam.py
backend/app/routes/audit.py
```

### 4.3 数据模型

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
AuditEvent
AuditHashChainBatch
```

### 4.4 默认角色

```text
普通用户
团队管理员
租户管理员
系统管理员
审计管理员
```

### 4.5 权限规则

```text
RBAC：角色权限
ABAC：属性权限 / 数据范围权限
权限冲突：deny 优先
权限缓存：权限变更后立即失效；登录态可继续，但下一次权限判断必须读最新权限
```

### 4.6 审计范围

第一批必须审计：

```text
登录 / 登出
模型调用
用户消息
prompt
模型输出
工具调用
插件调用
权限判断
审批申请
审批结果
业务数据查询
数据导出
Artifact 创建
配置变更
插件启停
模型 Provider 变更
```

### 4.7 审计检索与导出

```text
GET  /api/audit/events
POST /api/audit/export
GET  /api/audit/exports/{export_id}
```

检索条件：

```text
时间范围、用户、插件、工具、业务系统、审批单号、审计编号、风险等级、操作类型
```

导出：

```text
CSV
JSON
```

导出本身必须权限判断和审计。

### 4.8 验收

- 普通用户只能看自己的审计摘要；
- 团队管理员只能看团队范围；
- 审计管理员按授权范围看完整审计；
- 敏感字段默认脱敏；
- 查看明文会产生审计；
- AuditEvent 写入 hash。

## 5. Phase C：Model Provider 设置与密钥管理

### 5.1 目标

设置页支持多 Model Provider 配置。

入口：左下角“设置与模型”。

### 5.2 后端模块

```text
backend/app/model_provider/models.py
backend/app/model_provider/service.py
backend/app/model_provider/credentials.py
backend/app/routes/model_providers.py
```

### 5.3 数据模型

```text
ModelProvider
ModelDefinition
ModelProviderCredential
ModelProviderPermission
ModelProviderAuditEvent
```

字段：

```text
provider_id
tenant_id
name
provider_type
base_url
credential_ref
models_json
default_model
enabled
scope: user | team | tenant | system
created_by
updated_by
created_at
updated_at
```

### 5.4 API

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

### 5.5 前端页面

页面形态：

```text
完整设置页面，类似 Codex。
入口：左下角“设置与模型”。
第一版只支持 OpenAI-compatible Provider，不做专有 SDK。
```

设置页分区：

```text
当前模型
可用模型
Provider 列表
新增 Provider
连通性测试
模型列表管理
权限范围
审计记录入口
```

角色：

```text
普通用户：可以看到 Provider 配置，但只能查看授权字段，不能新增/编辑未授权配置。
团队管理员：可为团队设置默认模型。
租户管理员：可新增、编辑、禁用租户级 Provider。
系统管理员：可管理全局 Provider 和系统默认模型。
```

API Key 展示：

```text
默认脱敏展示。
有权限的管理员可切换脱敏/非脱敏。
查看明文必须写审计事件。
```

### 5.6 验收

- API Key 不进入前端持久化；
- 前端默认展示脱敏 key；
- 有权限查看明文时必须审计；
- 可手动填写模型；
- Provider 支持 `/models` 时可拉取模型列表；
- 连接测试产生审计；
- 普通用户不能新增 Provider。

## 6. Phase D：Codex-style 插件中心

### 6.1 目标

建设完整插件中心。Codex 插件体系作为主参考，增强金融企业权限、审批、审计和 Connector Runtime。

### 6.2 插件分层

```text
Plugin Package：发布、租户级启用、授权、启停、版本、依赖、UI、配置。
Skill：告诉 Agent 什么时候使用能力、如何澄清、如何解释结果。
Tool / Capability：模型可调用能力、schema、风险、权限、结果。
Connector：服务端实际连接业务系统或外部系统的执行层。
UI Renderer：右侧业务面板的业务 Artifact 渲染器。
Permission / Approval / Audit：金融企业场景必须内置。
```

### 6.3 后端模块

```text
backend/app/plugins/models.py
backend/app/plugins/registry.py
backend/app/plugins/installation.py
backend/app/plugins/authorization.py
backend/app/plugins/release_policy.py
backend/app/routes/plugins.py
```

### 6.4 数据模型

```text
PluginPackage
PluginVersion
PluginEnablement
PluginAuthorization
PluginReleasePolicy
PluginVisibilityRule
PluginCapability
PluginSkill
PluginUIRenderer
PluginAuditEvent
```

状态机：

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

### 6.5 API

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

### 6.6 前端页面

```text
插件中心作为设置页面里的一个菜单，打开完整页面，形态类似 Codex。
插件主视图按业务类型组织，例如问数、理赔、投保、查询、办公、本地文件、外部通用。
全部插件、已授权、待授权、可升级、已停用、管理员管理、审计记录作为筛选条件。
Web 形态普通用户不显示“安装”，只显示“申请授权 / 启用 / 停用 / 使用”。
管理员管理和审计记录第一版展示。
```

### 6.7 验收

- 左侧栏“插件”打开插件中心；
- 普通用户可启停个人插件；
- 普通用户不能发布或租户级启用内部业务插件；
- 租户管理员可租户级启用内部业务插件；
- 插件启停产生审计；
- 待授权插件可发起授权/权限申请。

## 7. Phase E：Connector Runtime

### 7.1 目标

实现服务端 Connector Runtime，统一治理内部业务系统和外部通用插件调用。

### 7.2 三档接入

```text
标准 Connector：业务系统提供标准 API，工作台服务端直接调用。
轻改造 Connector：业务系统提供有限 API，工作台做适配层。
人工/半自动 Connector：系统暂未开放 API，只生成操作指引、跳转、表单草稿，不做自动操作。
```

第一阶段不支持核心业务系统 RPA / UI 自动化。

### 7.3 后端模块

```text
backend/app/connectors/models.py
backend/app/connectors/runtime.py
backend/app/connectors/auth.py
backend/app/connectors/http_client.py
backend/app/connectors/result.py
backend/app/connectors/tool_pool.py
backend/app/routes/connectors.py
```

### 7.4 数据模型

```text
ConnectorBinding
ConnectorCredential
ConnectorInvocation
ConnectorRateLimit
ConnectorAuditPolicy
ConnectorError
```

Connector Binding 字段：

```text
connector_id
plugin_id
tenant_id
environment
base_url
auth_type
credential_ref
allowed_operations
data_scope_policy_id
timeout_seconds
retry_policy
rate_limit
risk_tier
audit_policy
enabled
```

### 7.5 统一返回结构

```json
{
  "status": "completed | failed | partial | blocked | approval_required",
  "summary": "给主对话展示的摘要",
  "data": {},
  "artifacts": [],
  "audit_event_id": "evt_xxx",
  "permission_decision": {},
  "next_actions": [],
  "raw_ref": "原始响应引用"
}
```

### 7.6 ToolPool 动态过滤

每次 Agent run 前，根据以下因素生成模型可见工具：

```text
tenant
user
role
workspace
plugin visibility
authorization status
data permission
risk tier
approval policy
```

不把系统全部工具一次性暴露给模型。

### 7.7 验收

- Connector 凭据只在服务端保存；
- ToolPool 会过滤未授权工具；
- Connector 调用产生审计；
- 超权返回 `approval_required`；
- `raw_ref` 引用原始响应，不把大响应直接塞进消息；
- 标准 Connector、轻改造 Connector、人工/半自动 Connector 都有 mock 示例。

## 8. Phase F：审批中心

### 8.1 目标

实现审批申请、审批状态、审批恢复执行闭环。

### 8.2 审批对象

第一批支持：

```text
数据权限申请
插件授权申请
高风险工具调用申请
数据导出申请
跨机构数据访问申请
```

暂不纳入第一批：

```text
模型外发敏感数据申请
```

### 8.3 provider 优先级

```text
自建审批
钉钉
企业微信
```

保留 provider 抽象。

### 8.4 后端模块

```text
backend/app/approvals/models.py
backend/app/approvals/service.py
backend/app/approvals/providers/base.py
backend/app/approvals/providers/internal.py
backend/app/approvals/providers/dingtalk.py
backend/app/approvals/providers/wecom.py
backend/app/routes/approvals.py
```

### 8.5 数据模型

```text
ApprovalRequest
ApprovalDecision
ApprovalProviderBinding
ApprovalResumeToken
ApprovalAuditEvent
```

状态机：

```text
created
submitted
pending
approved
rejected
expired
cancelled
resumed
```

### 8.6 API

```text
POST /api/approvals
GET  /api/approvals/{approval_id}
POST /api/approvals/{approval_id}/approve
POST /api/approvals/{approval_id}/reject
POST /api/approvals/{approval_id}/resubmit
POST /api/approvals/{approval_id}/resume-run
GET  /api/approvals
```

### 8.7 前端交互

```text
主对话展示审批摘要卡片。
审批中心集成在设置页面中，形态类似 Codex。
审批详情不放右侧业务面板。
主对话审批摘要卡片点击后进入设置页审批详情。
审批通过后默认不自动恢复，需要用户点击“继续执行”。
审批拒绝后允许修改范围重新提交。
审批默认 7 天过期，可配置。
```

### 8.8 验收

- 超权能创建审批申请；
- 设置页审批中心展示详情；
- mock 审批能通过/拒绝；
- 审批通过后点击继续执行能恢复 blocked tool_call；
- 审批拒绝后可修改范围重新提交；
- 审批事件全部审计。

## 9. Phase G：右侧业务面板 Artifact Renderer

### 9.1 目标

实现插件业务结果、查询计划、图表、表格、表单的右侧展示体系。审批中心不放右侧业务面板。

### 9.2 核心规则

```text
Artifact 必须跟随会话区分。
每次业务查询或插件运行，在主对话生成结果链接卡片。
卡片关联 artifact_id。
点击卡片后右侧打开或切换到对应 Artifact。
同一会话内多次查询形成多条结果记录，不能简单覆盖。
Tab 关闭不删除 Artifact。
下载、导出、复制都需要权限判断和审计。
相同内容、相同用户、相同权限范围、相同操作类型可复用已通过审核，不重复审批。
```

### 9.3 后端模型

```text
Artifact
ArtifactVersion
ArtifactPermission
ArtifactDownloadRequest
ArtifactRendererHint
```

### 9.4 前端组件

默认组件第一批：

```text
Table
Metric
Chart
Form
QueryPlan
AuditInfo
ErrorState
```

### 9.5 renderer 机制

```text
插件 manifest 声明 renderer。
服务端返回 renderer_hint。
前端根据 renderer_hint 找业务组件。
找不到 renderer 时展示通用 JSON / 表格 fallback。
AI 动态 UI 使用受控 Artifact schema + renderer_hint 白名单。
不允许 AI 直接生成并执行 React/JS 代码。
```

### 9.6 下载规则

```text
普通文本 / 小表格：允许复制。
业务查询结果：下载需要权限判断和审计。
敏感数据 / 明细数据：默认不允许下载，需审批。
相同用户、相同 Artifact 内容、相同权限范围、相同操作类型已有有效通过记录时，可以复用审核结果。
```

### 9.7 验收

- 主对话结果卡片能打开右侧 Artifact；
- 多次查询保留多张卡片；
- Tab 关闭后可从卡片重新打开；
- 找不到 renderer 时 fallback 可用；
- 审计编号在顶部元信息区和底部审计区展示；
- 权限不足展示申请入口。

## 10. Phase H：前端 Runtime 迁移评估

### 10.1 目标

服务端能力完成后，评估是否从当前 `assistant-ui + react-ai-sdk + UIMessage` 迁移到 `AssistantTransport` 或 `AG-UI`。

### 10.2 评估触发条件

```text
右侧业务面板需要和 Agent state 实时同步。
审批 / human-in-the-loop 复杂度升高。
插件运行状态需要跨 Tab 管理。
Thread History 需要完整工具过程回放。
需要和其他 Agent 框架兼容。
```

### 10.3 当前策略

```text
Phase A-G 不迁移。
继续保持 Message/UIMessage 前端历史加载。
服务端保留 TranscriptEvent -> UIMessage 投影。
RuntimeEvent 设计向 AssistantTransport/AG-UI 兼容。
```

## 11. 跨阶段测试策略

### 11.1 后端测试

```text
pytest backend/tests
```

必须覆盖：

```text
Transcript 双写
ToolResult 回写
Run 状态机
PermissionDecision
AuditEvent
ModelProvider
Plugin lifecycle
Connector invocation
Approval resume
Artifact permission
```

### 11.2 前端测试

```text
npm test -- --run
npm run lint
```

必须覆盖：

```text
Thread history
模型设置页
插件中心
设置页审批中心
Artifact 卡片
右侧 renderer fallback
权限不足状态
```

### 11.3 端到端验收

最小完整路径：

```text
用户登录
选择模型
打开插件中心
启用问数插件
发起问数查询
权限允许 → 执行 Connector → 生成 Artifact → 主对话卡片 → 右侧展示结果 → 写审计
权限不足 → 创建审批 → 设置页审批中心 → mock 通过 → 用户点击继续执行 → 生成结果 → 写审计
```

## 12. 开发前最终门槛

进入开发前需要满足：

```text
本计划确认完成。
每个 Phase 有独立任务清单。
UI/UX 交互设计已确认，并能映射到开发任务。
先执行 Phase A，不并行夹带完整插件中心或审批中心。
每个 Phase 完成后运行后端和前端测试。
涉及前端主交互变更时先确认 UI 方案。
```

## 13. 建议下一步

下一步输出 Phase A 的实施计划：

```text
docs/phase-a-agent-runtime-implementation-plan.md
```

Phase A 计划需要细化到：

```text
具体文件
模型字段
API schema
测试用例
迁移/初始化策略
兼容性要求
验收命令
```
