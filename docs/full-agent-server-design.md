# 全套 Agent 服务端详细设计

版本：2026-06-30  
适用范围：`workbench-app/server`  
参考对象：`/Users/daniel/Desktop/code/产品精算/参考项目/claude-code-main`

## 1. 结论

当前服务端已经具备一阶段 Agent Runtime 底座：FastAPI、SQLite、Run、RuntimeEvent、Thread、Message、ToolRegistry、PermissionGate、QueryLoop、Memory、Artifact、SSE 流式输出和 OpenAI-compatible 模型调用。

但它距离“全套 Agent 服务端”还有明确差距。后续目标不是简单补几个接口，而是把服务端升级为可承载企业工作台的 Agent 平台层：

```text
用户消息
  → 会话与上下文装配
  → 意图与任务状态机
  → 工具池 / 插件能力装配
  → 模型调用与工具调用循环
  → 权限 / 数据治理 / 审批
  → 工具执行 / Connector 执行
  → Tool Result 回写模型上下文
  → Artifact / 右侧业务面板数据
  → 运行事件 / 审计 / 成本 / 诊断
  → 流式返回前端 assistant-ui
```

本设计文档用于指导服务端后续实现。任何需要改变前端交互或 assistant-ui 组件结构的内容，必须先向用户列明修改点并获得确认。

## 2. 参考项目映射

`claude-code-main` 是源码快照，不作为直接依赖。参考方式是吸收它的 Agent Runtime 思想，按 Python/FastAPI/SQLite 技术栈重建。

| 参考项目能力 | 参考文件 | 工作台服务端目标 |
| --- | --- | --- |
| 会话级 QueryEngine | `src/QueryEngine.ts` | `AgentSessionRuntime`，每个 thread 维护上下文、工具、权限、usage、abort |
| Agent 主循环 | `src/query.ts` | `AgentLoop` / `QueryLoop`，支持模型输出、tool_use、tool_result、多轮继续 |
| 工具协议 | `src/Tool.ts` | `ToolDefinition`、`ToolInvocation`、`ToolResult`、权限、渲染提示、进度事件 |
| 权限模式 | `src/types/permissions.ts` | `PermissionPolicy`、`PermissionDecision`、`ApprovalRequest`、审批回放 |
| 会话历史 | `src/assistant/sessionHistory.ts` | `Thread`、`Message`、`TranscriptEvent`、分页历史、可恢复运行 |
| 插件系统 | `src/plugins/*`、`src/types/plugin.ts` | 内置插件、业务插件、外部插件、Connector、发布与授权 |
| 记忆系统 | `src/memdir/*` | 用户记忆、工作空间记忆、组织策略记忆、上下文召回 |
| Bridge / Remote | `src/bridge/*`、`src/remote/*` | 远程 Connector、长任务通道、未来企业插件执行网关 |
| 成本与 usage | `src/cost-tracker.ts` | 模型调用、token、耗时、失败率、预算控制 |
| 压缩与上下文管理 | compact / snip 相关模块 | 长会话摘要、上下文窗口预算、历史裁剪 |

## 3. 设计原则

1. 服务端是企业 Agent 平台，不只是 chat API。
2. 工具、插件、Connector 统一纳入一个 Tool Runtime。
3. 所有工具调用必须经过权限、审计、事件流和结果标准化。
4. 业务插件不直接暴露给模型裸调用，必须通过能力声明、权限策略、参数校验和 Connector Runtime。
5. 前端 assistant-ui 只消费标准消息流、工具进度、Artifact 和右侧面板数据，不承载业务执行逻辑。
6. Phase 1 使用 SQLite，不引入 Redis；但数据模型要预留生产数据库迁移边界。
7. 初期模型调用使用 OpenAI-compatible 接口，Provider 抽象必须支持后续多模型。
8. 金融数据访问默认最小权限，超权必须阻断并生成申请流程。
9. 工作台维护自己的账号与权限体系，钉钉、企业微信、自建 SSO 只作为身份源和组织映射来源。
10. 权限模型采用 RBAC + ABAC：RBAC 负责角色权限，ABAC 负责属性权限和数据范围权限。

## 4. 总体架构

```text
assistant-ui Frontend
  ├─ /api/chat Next.js Bridge
  ├─ Thread List Adapter
  ├─ Thread History Adapter
  └─ Business Panel Tabs
        │
        ▼
Python FastAPI Agent Server
  ├─ API Layer
  │   ├─ Agent API
  │   ├─ Thread API
  │   ├─ Runtime API
  │   ├─ Plugin API
  │   ├─ Tool API
  │   └─ Approval API
  │
  ├─ Agent Runtime
  │   ├─ AgentSessionRuntime
  │   ├─ AgentLoop
  │   ├─ ContextAssembler
  │   ├─ ToolPoolAssembler
  │   ├─ ModelOrchestrator
  │   ├─ ToolExecutionService
  │   ├─ PermissionService
  │   ├─ MemoryService
  │   ├─ ArtifactService
  │   ├─ UsageBudgetService
  │   └─ RuntimeEventBus
  │
  ├─ Plugin / Connector Runtime
  │   ├─ PluginRegistry
  │   ├─ PluginReleaseService
  │   ├─ InternalBusinessConnector
  │   ├─ ExternalToolConnector
  │   ├─ ConnectorAuthService
  │   └─ ConnectorSandboxPolicy
  │
  ├─ Governance Plane
  │   ├─ IAM / Role Mapping
  │   ├─ RBAC / ABAC
  │   ├─ DataScopePolicy
  │   ├─ ApprovalWorkflow
  │   ├─ AuditRetention
  │   └─ RiskClassifier
  │
  └─ SQLite
      ├─ thread / message / transcript_event
      ├─ run / run_step / runtime_event
      ├─ tool_invocation / model_call
      ├─ artifact / memory
      ├─ plugin_package / connector_binding
      ├─ permission_decision / approval_request
      └─ audit_event / usage_meter
```

## 5. 当前状态与缺口

### 5.1 已具备

当前 `server/app` 已经具备：

- FastAPI 路由层；
- SQLite + SQLAlchemy；
- Thread / Message；
- Run / RunStep；
- RuntimeEvent；
- ToolInvocation；
- ModelCall；
- AuditEvent；
- AgentMemory；
- Artifact；
- ToolRegistry；
- PermissionGate；
- ToolExecutionService；
- ToolPoolAssembler；
- QueryLoop；
- AgentSessionRuntime；
- SSE 流式运行；
- OpenAI-compatible 模型调用；
- 基础 cancel / retry / diagnostics。

### 5.2 缺口

要达到“全套 Agent 服务端”，必须补齐：

- 标准 TranscriptEvent；
- 标准 ToolResult 消息回写；
- 多 Provider 模型抽象；
- token / cost / budget；
- 长上下文压缩；
- 权限决策模型；
- 人工审批流程；
- 插件包生命周期；
- Connector 执行协议；
- 内部业务插件和外部插件的隔离策略；
- MCP / 外部工具协议预留；
- Run 状态机一致性；
- 工具取消与超时治理；
- 审计留存策略；
- 观测指标；
- 完整测试矩阵。

## 6. 核心运行模型

### 6.1 AgentSessionRuntime

职责：

- 接收一次用户输入；
- 确定 tenant、user、workspace、thread；
- 创建或恢复 Run；
- 装配上下文；
- 装配工具池；
- 调用 AgentLoop；
- 持久化 user / assistant / tool transcript；
- 写 RuntimeEvent；
- 写审计；
- 将标准事件流返回给前端。

建议接口：

```python
class AgentSessionRuntime:
    def submit_message(self, request: AgentRunInput) -> AgentRunResult: ...
    def submit_message_stream(self, request: AgentRunInput) -> Iterator[RuntimeStreamEvent]: ...
    def cancel_run(self, run_id: str, user_id: str) -> None: ...
    def retry_run(self, run_id: str, user_id: str) -> AgentRunResult: ...
```

### 6.2 AgentLoop

职责类似 `claude-code-main/src/query.ts`：

```text
while not done:
  1. 构建 model messages
  2. 调用模型
  3. 流式输出 text_delta / reasoning_delta
  4. 捕获 tool_calls
  5. 若无 tool_calls，结束
  6. 校验工具参数
  7. 权限决策
  8. 执行工具
  9. 标准化 tool_result
  10. tool_result 回写下一轮 model messages
  11. 检查 max_turns / budget / cancel / timeout
```

关键要求：

- 工具结果必须回写模型上下文，而不是只给前端展示；
- 一个 assistant turn 可包含多个 tool call；
- `concurrency_safe=true` 的工具可以并发执行；
- 非并发安全、破坏性、高风险工具必须串行；
- 每一轮都生成 `model_call`、`tool_invocation`、`runtime_event`。

### 6.3 Run 状态机

```text
queued
  → running
  → waiting_permission
  → running
  → waiting_approval
  → running
  → completed

running → cancelling → cancelled
running → failed
waiting_permission → denied
waiting_approval → denied
```

状态写入规则：

- 只有 AgentRuntime 可以推进 Run 状态；
- API handler 不直接修改运行状态；
- 每次状态变化必须写 `runtime_event`；
- failed / cancelled / denied 必须有 machine-readable reason。

## 7. 消息与 Transcript 设计

当前 Thread / Message 可以支撑会话列表，但不够支撑完整 Agent 回放。需要新增 `TranscriptEvent`。

### 7.1 TranscriptEvent

字段建议：

```text
id
tenant_id
workspace_id
thread_id
run_id
sequence
role: user | assistant | tool | system
event_type:
  user.message
  assistant.message
  assistant.reasoning
  assistant.tool_call
  tool.result
  system.compaction
  system.permission_decision
content_json
created_at
```

用途：

- 恢复模型上下文；
- assistant-ui 历史消息加载；
- 调试工具调用链；
- 审计回放；
- 长上下文压缩输入。

### 7.2 与 Message 的关系

`Message` 用于会话列表和用户可见内容。  
`TranscriptEvent` 用于 Agent Runtime 完整上下文。

```text
Message = 用户可见摘要层
TranscriptEvent = Agent 可恢复执行层
RuntimeEvent = 运行过程证据层
AuditEvent = 合规审计层
```

## 8. Tool Runtime 设计

### 8.1 ToolDefinition

在当前 `ToolDefinition` 基础上扩展：

```text
name
display_name
description
input_schema
output_schema
read_only
destructive
concurrency_safe
risk_tier
permission_policy
timeout_seconds
max_result_size_chars
requires_user_interaction
requires_network
requires_business_auth
connector_id
plugin_id
ui_renderer_hint
progress_event_schema
artifact_schema
audit_schema
```

### 8.2 ToolResult

所有工具必须返回标准结构：

```json
{
  "tool_id": "workspace.read",
  "status": "completed",
  "response_text": "已读取文件。",
  "model_context": [
    {
      "type": "text",
      "text": "文件内容摘要..."
    }
  ],
  "output_payload": {},
  "artifacts": [],
  "audit_event_id": "evt_xxx",
  "error": null
}
```

关键点：

- `response_text` 给用户看；
- `model_context` 回写模型；
- `output_payload` 给右侧业务面板；
- `artifacts` 给 Artifact 系统；
- `audit_event_id` 给合规追踪。

### 8.3 工具分类

| 类型 | 示例 | 权限 |
| --- | --- | --- |
| 内置通用工具 | plan.update、memory.read、workspace.list | L0/L1 |
| 本地工作空间工具 | workspace.read、local_data.analyze | L0/L1 |
| 内部业务插件工具 | ask_data.query、claims.lookup | L1-L3 |
| 外部通用插件工具 | email.search、calendar.create | L1-L3 |
| 系统级工具 | shell.run、file.write | 默认禁用，后续单独评估 |

## 9. 权限、审批与数据治理

账号与权限体系：

```text
工作台自有账号体系
  ├─ tenant
  ├─ user
  ├─ organization
  ├─ department
  ├─ role
  ├─ group
  └─ permission

第三方身份源
  ├─ 钉钉
  ├─ 企业微信
  └─ 自建 SSO

第三方身份源只负责身份认证和组织映射，不直接作为工作台权限体系。
```

权限模型：

```text
RBAC：角色权限
ABAC：属性权限 / 数据范围权限
```

第一批数据权限粒度：

```text
租户级
组织/部门级
角色级
项目级
地区级
字段级
行级
```

字段级和行级 Phase 1 先完成模型设计，真实执行在接入业务系统或数仓时落地。

### 9.1 PermissionPolicy

权限结果：

```text
allow
deny
ask_user
require_approval
require_reauth
```

权限输入：

```text
tenant_id
user_id
workspace_id
thread_id
tool_id
plugin_id
connector_id
risk_tier
input_payload
data_scope
resource_scope
operation_type
```

### 9.2 权限流程

```text
tool_call
  → schema validation
  → static risk check
  → user / role / workspace policy
  → data scope policy
  → connector auth check
  → decision
```

如果超过权限：

```text
require_approval
  → 创建 approval_request
  → 返回前端可展示的审批需求
  → 后续对接钉钉 / 企业微信 / 自建审批
  → 审批通过后重放 blocked tool_call
```

### 9.3 金融数据访问

问数、理赔、投保等内部业务插件必须经过：

- 身份映射；
- 角色权限；
- 数据域权限；
- 字段级权限；
- 行级权限；
- 查询目的记录；
- 审计编号；
- 超权申请；
- 结果脱敏；
- 审计留存。

## 10. 插件与 Connector Runtime

### 10.1 插件分类

#### 内部业务插件

用于连接公司业务系统，例如：

- 问数插件；
- 理赔系统插件；
- 投保系统插件；
- 核保系统插件；
- 客户系统插件。

要求：

- 服务端发布；
- 客户端 OTA catalog 可见；
- 服务端执行 Connector；
- 强制权限和审计；
- 支持业务系统接口改造规划；
- 支持无侵入、轻改造、标准 Connector 三种接入等级。

#### 外部通用插件

用于本地文件、办公软件、外部 SaaS 等：

- 文件解析；
- 邮件；
- 日历；
- 通用 HTTP；
- 外部模型服务。

要求：

- 低风险能力可本地执行；
- 涉及企业数据外发必须走策略；
- 后续支持 OAuth / API Key / 企业托管凭据。

### 10.2 PluginPackage

建议字段：

```text
plugin_id
name
version
plugin_type
description
capabilities
tools
connectors
permissions
ui_panels
release_channel
signature
enabled
created_at
updated_at
```

### 10.3 ConnectorBinding

建议字段：

```text
connector_id
plugin_id
tenant_id
environment
base_url
auth_type
credential_ref
timeout_seconds
rate_limit
data_scope_policy_id
enabled
```

### 10.4 Connector 执行流程

```text
model tool_call
  → ToolRuntime
  → PermissionService
  → ConnectorAuthService
  → ConnectorInvoker
  → BusinessSystem API
  → Normalize Result
  → AuditEvent
  → Artifact / ToolResult
```

## 11. 模型服务设计

当前 `llm.py` 是 OpenAI-compatible 单实现。目标是抽象为：

```text
ModelProvider
  ├─ OpenAICompatibleProvider
  ├─ BailianProvider
  ├─ PrivateModelProvider
  └─ MockProvider
```

模型调用必须记录：

- provider；
- model；
- request id；
- latency；
- prompt tokens；
- completion tokens；
- total tokens；
- estimated cost；
- status；
- error type。

后续 settings 中配置的模型应只影响 `ModelProviderRegistry`，不影响 AgentLoop。

## 12. 记忆与上下文

### 12.1 记忆类型

```text
user_memory       用户偏好
workspace_memory  工作空间约定
team_memory       团队规则
policy_memory     公司制度 / 合规说明
tool_memory       插件使用经验
```

### 12.2 上下文装配

```text
ContextAssembler
  → system prompt
  → user profile
  → workspace summary
  → relevant memories
  → recent transcript
  → active artifacts
  → available tools
  → policy hints
```

需要支持：

- relevance scoring；
- token budget；
- memory aging；
- user 可删除；
- 管理员策略不可被用户覆盖。

## 13. 长上下文与压缩

服务端需要引入 CompactionService：

```text
recent transcript
  → token count
  → 超过阈值
  → summarize older transcript
  → 生成 system.compaction TranscriptEvent
  → 后续上下文使用 summary + recent raw events
```

压缩结果必须：

- 可审计；
- 可回放；
- 不覆盖原始 transcript；
- 不作为金融审计事实来源。

## 14. Artifact 与右侧业务面板

Artifact 是业务面板的数据来源，不是单纯聊天附件。

Artifact 类型：

```text
plan
diagnostic
query_result
approval_request
business_form
chart
table
document
runtime_trace
```

字段建议：

```text
artifact_id
thread_id
run_id
tool_invocation_id
artifact_type
title
payload_json
renderer_hint
version
created_at
updated_at
```

前端接入原则：

- assistant-ui 对话区负责 Agent 对话、过程、摘要和结论；
- 右侧业务面板负责业务 Artifact、审批、表格、图表、表单、审计和可操作业务对象；
- 插件结果不一刀切进入右侧面板，必须按 Artifact 类型和复杂度分流；
- 简短文本结果在主对话展示；
- 结构化、可操作、可审计、可持续查看的结果进入右侧业务 Tab；
- 内部业务插件默认 `both`：主对话显示摘要，右侧面板展示完整业务结果；
- Artifact 必须跟随会话区分，不同会话的业务结果不能混用；
- 每次业务查询或插件运行需要在主对话中生成结果链接卡片，卡片关联具体 `artifact_id`；
- 用户点击主对话结果卡片后，右侧业务面板打开或切换到对应 Artifact；
- 同一会话内多次查询应形成多条结果记录，不能简单覆盖；第一次查询、第二次调整条件查询都应保留对应卡片和 Artifact；
- Artifact 下载按数据级别和权限分级控制：普通文本/小表格允许复制，业务查询结果下载需要权限判断和审计，敏感数据/明细数据默认不允许下载且需审批；
- 如果新增 Artifact 类型需要新 UI renderer，必须先与用户确认前端修改内容。

建议插件 manifest 增加 UI 分流声明：

```json
{
  "ui": {
    "result_surface": "chat_inline | right_panel | both",
    "renderer": "ask_data_result",
    "open_policy": "auto | manual | never",
    "summary_in_chat": true
  }
}
```

## 15. API 设计

### 15.1 Agent API

```text
POST /api/agent/run
POST /api/agent/run/stream
POST /api/agent/intent
POST /api/chat
```

### 15.2 Thread API

```text
GET    /api/threads
POST   /api/threads
GET    /api/threads/{thread_id}
PATCH  /api/threads/{thread_id}
DELETE /api/threads/{thread_id}
GET    /api/threads/{thread_id}/transcript
```

### 15.3 Runtime API

```text
POST /api/runs
GET  /api/runs/{run_id}
GET  /api/runs/{run_id}/events
GET  /api/runs/{run_id}/events/stream
POST /api/runs/{run_id}/cancel
POST /api/runs/{run_id}/retry
```

### 15.4 Tool API

```text
GET  /api/tools/catalog
POST /api/tools/{tool_id}/invoke
GET  /api/tools/{tool_id}/schema
```

### 15.5 Plugin API

```text
GET  /api/plugins/catalog
GET  /api/plugins/{plugin_id}
POST /api/plugins/{plugin_id}/authorize
POST /api/plugins/{plugin_id}/revoke
GET  /api/plugins/{plugin_id}/tools
```

### 15.6 Approval API

```text
POST /api/approvals
GET  /api/approvals/{approval_id}
POST /api/approvals/{approval_id}/callback
POST /api/approvals/{approval_id}/resume-run
```

## 16. SSE 事件协议

前端 `/api/chat` Bridge 应消费以下事件：

```text
run.started
context.loaded
model.started
model.delta
model.completed
tool.started
tool.progress
tool.completed
tool.failed
permission.required
approval.required
artifact.created
run.completed
run.failed
run.cancelled
```

事件结构：

```json
{
  "event": "tool.completed",
  "run_id": "run_xxx",
  "step_id": "step_xxx",
  "sequence": 12,
  "timestamp": "2026-06-30T12:00:00Z",
  "payload": {}
}
```

## 17. 数据模型增量设计

在现有 SQLAlchemy 模型基础上，建议新增：

```text
TranscriptEvent
PermissionDecision
ApprovalRequest
ConnectorBinding
ConnectorCredentialRef
PluginInstallation
PluginRelease
UsageMeter
ContextSnapshot
CompactionSummary
```

SQLite 阶段继续 `create_all`，进入试点前引入 Alembic。

## 18. 测试策略

### 18.1 单元测试

- Tool schema validation；
- Permission decision；
- AgentLoop max turns；
- ToolResult 回写；
- Run 状态机；
- cancel / retry；
- compaction；
- model provider mock。

### 18.2 集成测试

- 普通对话；
- 工具调用；
- 工具失败；
- 权限阻断；
- 审批挂起；
- 审批通过后恢复；
- 插件 catalog；
- Artifact 创建；
- Thread history 恢复；
- SSE 流式输出。

### 18.3 前端联调测试

任何需要前端修改的能力先输出变更说明，确认后再做：

- assistant-ui 是否能渲染新增事件；
- 右侧业务面板是否需要新增 tab renderer；
- Thread adapter 是否需要读 transcript；
- composer 是否需要新增权限确认入口。

## 19. 分阶段实施路线

### Phase 1A：工程收敛

- 删除旧 Vite/Tauri 前端；
- 明确 `frontend-v2` 为唯一前端；
- 补本文档；
- 不改前端交互。

### Phase 1B：Agent Runtime 完整化

- 新增 TranscriptEvent；
- 标准化 ToolResult；
- 改造 AgentLoop，使 tool_result 回写模型上下文；
- 增加 Run 状态机；
- 增加 UsageMeter；
- 增加 ModelProvider 抽象；
- 补 Runtime 测试。

### Phase 1C：权限与审批底座

- 新增 PermissionDecision；
- 新增 ApprovalRequest；
- PermissionGate 升级为 PermissionService；
- 超权返回 `approval.required`；
- 审批通过后支持 resume-run；
- 初期审批 provider 用 mock。

### Phase 1D：插件 / Connector 底座

- PluginPackage 扩展为完整 manifest；
- 新增 ConnectorBinding；
- 内部业务插件和外部插件分类型；
- 问数插件迁移到标准 Connector；
- 插件工具进入 ToolRegistry；
- 所有业务工具强制审计。

### Phase 1E：上下文与记忆

- ContextAssembler；
- MemoryService 分层；
- CompactionService；
- token budget；
- thread transcript 恢复。

### Phase 2：业务插件建设

- 问数插件真实数仓接入；
- 理赔系统插件；
- 投保系统插件；
- 钉钉 / 企业微信 / 自建 SSO 映射；
- 数据权限、审批、审计留存进入真实流程。

## 20. 前端接入边界

当前文档阶段不直接改前端。

后续可能需要前端确认的点：

1. `TranscriptEvent` 是否替代当前 Thread History message 加载；
2. `approval.required` 是否需要右侧业务面板新增审批 tab；
3. 插件工具执行结果是否新增业务 tab renderer；
4. assistant-ui reasoning / tool-call 展示是否需要使用官方组件扩展；
5. 多模型 Provider 设置是否需要调整“设置与模型”界面。

在用户确认前，服务端实现必须保持现有 `/api/agent/run/stream` 和 `/api/chat` 兼容。

## 21. 验收标准

达到“全套 Agent 服务端”阶段的最低验收：

- 同一 thread 可恢复完整上下文；
- 模型可连续调用多个工具并基于工具结果继续回答；
- 工具调用有 schema、权限、审计、事件；
- 运行可取消、可重试、可诊断；
- 超权可阻断并进入审批；
- 插件能力通过服务端 catalog 发布；
- Connector 由服务端执行；
- Artifact 可驱动右侧业务面板；
- usage / cost / latency 可查询；
- 长对话可压缩且保留原始审计；
- assistant-ui 前端无需承载业务执行逻辑。

## 22. 开发条件 Review

### 22.1 判定

本文档已经满足“启动服务端能力建设”的开发条件，但还不满足“直接按文档一次性实现全套 Agent 服务端”的条件。

原因：

- 架构边界、核心模块、数据模型方向、API 方向、事件协议、权限审批、插件 Connector、上下文记忆和阶段路线已经明确；
- 可以据此拆分 Phase 1B / 1C / 1D 的开发任务；
- 但全套 Agent 服务端跨度大，仍需要在每个阶段开工前补充更细的任务级实施计划、接口 schema、迁移脚本和测试用例。

### 22.2 可以立即开工的范围

可以直接进入开发的范围：

1. 新增 `TranscriptEvent` 模型和查询 API；
2. 标准化 `ToolExecutionResult` / `ToolResult`；
3. 改造 AgentLoop，使 tool result 回写模型上下文；
4. 增加 Run 状态机校验；
5. 增加 ModelProvider 抽象；
6. 增加 UsageMeter；
7. 补齐上述能力的单元测试和集成测试。

这些任务不会要求前端改变交互形态，可以在保持现有 `/api/agent/run/stream` 和 `/api/chat` 兼容的前提下开发。

### 22.3 开工前需要再确认的范围

以下内容会影响前端或业务交互，需要单独确认后开发：

1. `approval.required` 是否在右侧业务面板新增审批 Tab；已确认：需要。Phase 1C 先做 mock 审批 Tab，后续接钉钉、企业微信或自建审批。第一批审批对象包括数据权限申请、插件授权申请、高风险工具调用申请、数据导出申请、跨机构数据访问申请；模型外发敏感数据申请暂不纳入第一批，后续依赖数据分类分级和 DLP 策略再加入。Phase 1C mock 审批需要本地模拟通过/拒绝，并支持恢复原 Agent run；审批通过后默认不自动恢复，需要用户点击“继续执行”。
2. 插件运行结果是否需要新增业务 Tab renderer；已确认：按 Artifact 类型和复杂度分流。主对话展示摘要和过程，右侧业务面板展示结构化、可操作、可审计、可持续查看的业务结果。内部业务插件默认 `both`，由 plugin manifest 的 `ui.result_surface`、`ui.renderer`、`ui.open_policy` 控制。
3. Thread History 是否从 `Message` 切换为 `TranscriptEvent`；已确认：Phase 1B 不切换。当前前端继续使用 assistant-ui `react-ai-sdk` / `UIMessage` 路线，`Message` 继续作为前端历史消息来源。服务端新增 `TranscriptEvent`，用于 Agent Runtime、审计、工具回放和上下文恢复，并提供 `TranscriptEvent -> Message/UIMessage` 投影能力。前端 Runtime 是否迁移到 `AssistantTransport` 或 `AG-UI` 保留待定，等服务端能力完成后再评估。
4. 设置页是否要暴露多 Model Provider 配置；已确认：采用 UI 可配置方案。入口放在左下角“设置与模型”。设置页需要支持新增、编辑、禁用、删除多个 Model Provider，字段包括 provider 名称、provider 类型、OpenAI-compatible base URL、API Key、模型列表、默认模型、启用状态和适用范围。角色权限为：普通用户只能选择已授权模型，不能新增 Provider，不能查看 API Key；团队管理员可为团队设置默认模型；租户管理员可新增、编辑、禁用租户级 Provider；系统管理员可管理全局 Provider 和系统默认模型。模型列表支持手动填写；如果 Provider 支持 `/models`，可拉取模型列表。API Key 只能提交给服务端保存，前端不得持久化明文密钥；服务端需要提供密钥加密、脱敏展示、连通性测试、租户级/用户级授权和审计记录。Phase 1B 先实现后端 `ModelProvider` 抽象和配置 API，前端设置页改动需单独列出方案并再次确认后开发。
5. 插件 catalog 是否要在前端增加安装、授权、启停管理界面；已确认：采用完整插件管理界面方案。插件中心主入口放在左侧栏“插件”，右侧业务面板只承载具体插件业务界面。前端需要建设“插件中心 / 插件管理”能力，支持插件列表、插件详情、安装、授权、启用/停用、版本信息、风险等级、能力列表、权限申请和审计记录。插件状态机采用 `published / visible / installed / authorization_required / authorized / enabled / disabled / upgrade_available / deprecated / removed`，用户可见简化状态为“可安装、待授权、已启用、已停用、可升级、不可用”。普通用户可查看自己可用插件、启停个人插件、发起授权/权限申请，但不能安装内部业务插件到租户，也不能卸载管理员分配的插件；团队管理员可为团队启停插件并查看团队授权状态；租户管理员可安装、启停租户级插件、管理授权、配置可见范围；系统管理员可发布、下架、升级内置插件和全局插件。服务端需要提供插件 catalog、installation、authorization、enable/disable、release policy、tenant/user visibility、audit API。该能力涉及明确前端 UI 改动和服务端插件平台 API，开发前需要单独输出界面结构、接口 schema、权限边界和阶段实施方案并再次确认。

### 22.4 建议的下一份开发计划

下一份计划应命名为：

```text
docs/phase1b-agent-runtime-implementation-plan.md
```

计划应只覆盖 Phase 1B，不要把权限审批、插件 Connector、真实业务系统接入混在同一轮实现。

Phase 1B 推荐目标：

```text
完整通用 Agent Runtime：
Thread 可恢复、Transcript 可回放、ToolResult 可回写模型、Run 状态机可靠、模型调用可统计、SSE 兼容现有 assistant-ui 前端。
```

Phase 1B 完成后，再进入：

- Phase 1C：权限与审批底座；
- Phase 1D：插件与 Connector 底座；
- Phase 1E：上下文、记忆和压缩。
