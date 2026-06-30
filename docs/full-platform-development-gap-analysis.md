# 全套平台开发条件缺口清单

版本：2026-06-30  
适用仓库：`daniel5zhang/agent_base`  
关联文档：

- `docs/full-agent-server-design.md`
- `docs/phase1b-development-readiness-review.md`

## 1. 结论

当前文档已经可以支撑 Phase 1B 的 Agent Runtime 开发，但还不能支撑一次性开发完整平台：

```text
全套 Agent 服务端
+ 完整插件中心
+ 审批中心
+ 多模型设置页
+ 右侧业务面板渲染体系
+ 企业权限与审计
```

原因不是方向不清楚，而是以下内容还没有达到“可直接开发”的详细程度：

- 页面与交互没有完整定稿；
- API schema 没有逐接口定义；
- 数据库模型没有字段级定义；
- 权限边界没有按角色和场景落表；
- 状态机没有到事件级；
- 安全策略没有到实现级；
- 测试验收没有按用户路径拆完；
- 阶段边界仍需防止范围失控。

本文档用于补齐“缺口清单”和“需确认项”，后续逐项确认后再进入对应阶段开发计划。

## 2. 缺口总览

| 模块 | 当前状态 | 缺口 | 是否需用户确认 |
| --- | --- | --- | --- |
| Agent Runtime | 架构清楚 | 需要任务级实现计划 | 否 |
| Transcript / Message | 方向已确认 | 字段、投影、双写规则需细化 | 否 |
| ToolResult | 方向已确认 | schema、错误、artifact、model_context 需细化 | 否 |
| Run 状态机 | 方向已确认 | 状态转换表和事件规则需细化 | 否 |
| Model Provider | 选择方案 B | 设置页、密钥安全、授权范围需细化 | 是 |
| 插件中心 | 选择方案 B | 页面结构、角色权限、安装/授权流程需细化 | 是 |
| 审批中心 | 右侧审批 Tab 已确认 | 审批对象、状态、恢复执行流程需细化 | 是 |
| 右侧业务面板 | 分流规则已确认 | renderer 类型、Tab 生命周期、空状态需细化 | 是 |
| 企业账号权限 | 仅有方向 | 用户、角色、租户、组织、数据权限模型需细化 | 是 |
| 审计与监管 | 仅有方向 | 留存、查询、导出、脱敏、不可篡改策略需细化 | 是 |
| Connector Runtime | 仅有方向 | 内部业务插件与外部插件执行协议需细化 | 是 |
| 前端 Runtime 迁移 | 待定 | 服务端完成后再评估 AssistantTransport / AG-UI | 是，后置 |

## 3. 全套 Agent 服务端缺口

### 3.1 TranscriptEvent 字段级设计

当前已有方向：

```text
TranscriptEvent 用于 Agent Runtime、审计、工具回放和上下文恢复。
Message 继续作为前端历史消息来源。
```

仍需补齐：

- 字段级 schema；
- 事件类型枚举；
- sequence 生成规则；
- 与 `Message` 的双写规则；
- 与 `RuntimeEvent` 的边界；
- 与 `AuditEvent` 的边界；
- `TranscriptEvent -> Message/UIMessage` 投影规则；
- 历史压缩如何引用原始事件；
- 失败、取消、重试时的 transcript 记录方式。

是否需要用户确认：否。属于服务端实现细化。

### 3.2 ToolResult 标准

当前已有方向：

```text
ToolResult 包含 response_text、model_context、output_payload、artifacts、audit_event_id。
```

仍需补齐：

- JSON schema；
- 成功、失败、部分成功、权限阻断、审批挂起的统一结构；
- `model_context` 最大长度；
- 大结果如何转 Artifact；
- 结构化结果如何生成 chat summary；
- tool result 如何回写模型 messages；
- tool result 如何映射 assistant-ui tool part；
- 错误码体系。

是否需要用户确认：否。属于服务端实现细化。

### 3.3 AgentLoop 与 Run 状态机

仍需补齐：

- `queued/running/waiting_permission/waiting_approval/completed/failed/cancelled` 的严格转换表；
- 每个状态允许的 API 操作；
- cancel / retry / resume 的一致性规则；
- 并发 tool call 的 step 记录规则；
- max turns、timeout、budget exceeded 的终止规则；
- SSE 事件顺序；
- 前端中断后服务端 run 的处理方式。

是否需要用户确认：否。属于服务端实现细化。

## 4. 多模型设置页缺口

已确认：

```text
采用方案 B：设置页支持多 Model Provider 配置。
```

仍需补齐：

### 4.1 页面结构

需要确认：

- 设置页是放在左下角“设置与模型”中，还是作为右侧业务面板 Tab 打开；已确认：放在左下角“设置与模型”。
- 是否区分“个人模型配置”和“企业模型配置”；已确认：需要区分普通用户、团队管理员、租户管理员、系统管理员的不同配置权限。
- 普通用户是否可以新增 Provider；已确认：普通用户不能新增 Provider，只能选择已授权模型。
- 管理员配置的 Provider 是否可以被普通用户覆盖；已确认：普通用户不能覆盖管理员配置；团队管理员可设置团队默认模型，租户管理员可管理租户级 Provider，系统管理员可管理全局 Provider。
- 模型列表是手动填写，还是支持从 Provider 拉取；已确认：两者都支持。允许手动填写；如果 Provider 支持 `/models`，可点击“拉取模型列表”。

### 4.2 权限边界

需要确认角色：

```text
普通用户
团队管理员
租户管理员
系统管理员
```

已确认角色权限：

```text
普通用户：只能选择已授权模型，不能新增 Provider，不能查看 API Key。
团队管理员：可为团队设置默认模型。
租户管理员：可新增、编辑、禁用租户级 Provider。
系统管理员：可管理全局 Provider 和系统默认模型。
```

以及每个角色是否允许：

- 查看 Provider；
- 新增 Provider；
- 编辑 Base URL；
- 编辑 API Key；
- 测试连通性；
- 设置默认模型；
- 禁用 Provider；
- 删除 Provider。

### 4.3 安全实现

需要补齐：

- API Key 加密策略；
- 脱敏展示策略；
- 前端是否允许复制 key；
- key 轮换；
- 连接测试审计；
- 配置变更审计；
- provider 级别的可用范围。

是否需要用户确认：是。

## 5. 插件中心缺口

已确认：

```text
采用方案 B：前端增加完整插件管理界面。
```

仍需补齐：

### 5.1 页面结构

需要确认插件中心入口：

- 左侧“插件”入口；已确认：采用左侧栏“插件”入口，点击后打开插件中心。
- 设置页里的“插件管理”；已确认：不作为主入口，可作为设置页辅助入口。
- 右侧业务面板 Tab；已确认：不作为插件中心主入口，右侧面板用于承载具体插件业务界面。
- 独立全屏管理页；已确认：暂不作为主形态。

需要确认页面分区：

- 已安装；
- 可安装；
- 待授权；
- 已停用；
- 管理员发布；
- 审计记录。

### 5.2 插件生命周期

需要补齐状态机：

```text
published
visible
installed
enabled
authorization_required
authorized
disabled
upgrade_available
deprecated
removed
```

已确认采用上述状态机。用户可见的简化状态为：

```text
可安装
待授权
已启用
已停用
可升级
不可用
```

### 5.3 插件权限模型

需要确认：

- 普通用户能否安装插件；已确认：普通用户可以查看自己可用插件，但不能安装内部业务插件到租户。
- 普通用户能否启停插件；已确认：普通用户可以启用/停用个人插件，不能卸载或停用管理员强制分配的插件。
- 插件安装是用户级、团队级、租户级，还是系统级；已确认：支持用户级、团队级、租户级、系统级分层。
- 内部业务插件是否必须管理员安装；已确认：内部业务插件由租户管理员或系统管理员安装/分配。
- 外部通用插件是否允许个人安装；已确认：允许个人安装，但涉及企业数据外发时必须走授权和策略。
- 插件授权失败时是否生成审批；已确认：需要生成授权/权限申请。
- 插件升级是否需要用户确认；已确认：个人插件升级可由用户确认；管理员分配插件由管理员或发布策略控制。

已确认角色权限：

```text
普通用户：
  - 查看自己可用的插件
  - 启用/停用个人插件
  - 对需要授权的插件发起授权/权限申请
  - 不能安装内部业务插件到租户
  - 不能卸载管理员分配的插件

团队管理员：
  - 为团队启用/停用插件
  - 查看团队插件授权状态

租户管理员：
  - 安装、启用、停用租户级插件
  - 管理插件授权
  - 配置插件可见范围

系统管理员：
  - 发布、下架、升级内置插件和全局插件
```

### 5.4 插件详情页

需要补齐字段：

- 插件名称；
- 类型；
- 版本；
- 发布方；
- 风险等级；
- 能力列表；
- 工具列表；
- 数据权限；
- 连接状态；
- 授权状态；
- 审计记录；
- 版本记录；
- 启停操作；
- 卸载操作；
- 申请权限。

是否需要用户确认：是。

## 6. 审批中心缺口

已确认：

```text
approval.required 需要在右侧业务面板新增审批申请 Tab。
```

仍需补齐：

### 6.1 审批对象

需要确认审批类型：

- 数据权限申请；已确认：第一批支持。
- 插件授权申请；已确认：第一批支持。
- 高风险工具调用申请；已确认：第一批支持。
- 数据导出申请；已确认：第一批支持。
- 跨机构数据访问申请；已确认：第一批支持。
- 模型外发敏感数据申请；已确认：暂不纳入第一批，后续依赖数据分类分级和 DLP 策略再加入。

### 6.2 审批流程

需要确认：

- Phase 1C mock 审批是“本地模拟通过/拒绝”，还是只创建申请记录；已确认：本地模拟审批通过/拒绝，并支持恢复原 Agent run。
- 审批通过后是否自动恢复原 run；已确认：默认不自动恢复，需要用户点击“继续执行”。
- 审批拒绝后是否允许修改范围后重新提交；待确认。
- 审批过期时间；待确认。
- 审批记录是否在聊天中可见；待确认。
- 审批记录是否进入右侧业务面板长期保留；待确认。

Phase 1C mock 审批闭环：

```text
超权
  → 创建审批申请
  → 右侧审批 Tab 展示申请
  → 本地模拟通过/拒绝
  → 通过后显示“继续执行”
  → 用户点击继续执行
  → 恢复原 blocked tool_call
  → 继续 Agent run
```

### 6.3 三方审批接入

需要确认优先级：

- 钉钉；
- 企业微信；
- 自建审批；
- 仅预留 provider。

是否需要用户确认：是。

## 7. 右侧业务面板与 Artifact Renderer 缺口

已确认：

```text
主对话展示摘要和过程。
右侧面板展示结构化、可操作、可审计、可持续查看的业务结果。
```

仍需补齐：

- Tab 打开策略；已确认：Artifact 需要跟随会话区分，主对话内生成结果链接卡片，点击卡片后在右侧业务面板打开或切换到对应 Artifact。
- Tab 关闭策略；待确认。
- 同一插件多次运行时是否复用 Tab；已确认：不能简单覆盖。每次查询都应形成当前会话内的结果记录，并在主对话中生成独立结果卡片。右侧面板根据用户点击的卡片展示对应结果。
- Artifact 是否可版本化；已确认：需要版本化或记录化。第一次查询、第二次调整条件查询都应保留对应记录；主对话结果卡片是进入对应记录的入口。
- Artifact 是否可下载；已确认：分级控制。普通文本/小表格允许复制；业务查询结果下载需要权限判断和审计；敏感数据/明细数据默认不允许下载，需审批。
- Artifact 是否可分享；
- renderer 注册机制；
- 空面板状态；
- 错误状态；
- 审计编号展示位置；
- 业务表格、图表、表单、审批的默认组件规范。

已确认的 Artifact 展示交互：

```text
会话 A
  ├─ 用户第一次查询
  │   ├─ 主对话生成“查询结果卡片 1”
  │   └─ 点击卡片 1 → 右侧业务面板展示 Artifact 1
  ├─ 用户调整条件后第二次查询
  │   ├─ 主对话生成“查询结果卡片 2”
  │   └─ 点击卡片 2 → 右侧业务面板展示 Artifact 2
  └─ Artifact 1 / Artifact 2 均属于会话 A，不与其他会话混用
```

是否需要用户确认：是。

## 8. 企业账号、权限与数据治理缺口

当前只明确：

```text
工作台本身要有全套账号、权限体系。
钉钉、企业微信、自建 SSO 作为三方映射。
```

已确认：

```text
工作台维护自己的 tenant、user、role、department、group、permission。
钉钉、企业微信、自建 SSO 只作为身份源和组织映射来源。
钉钉不是权限体系本身，只是外部身份来源。
权限模型采用 RBAC + ABAC。
RBAC 负责角色权限，ABAC 负责属性权限和数据范围权限。
```

仍需补齐：

- tenant 模型；
- user 模型；
- organization 模型；
- department 模型；
- role 模型；
- group 模型；
- workspace 权限；
- plugin 权限；
- model provider 权限；
- data scope 权限；
- field-level 权限；
- row-level 权限；
- SSO 账号映射；
- 权限缓存与失效策略。

第一批数据权限粒度已确认：

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

是否需要用户确认：是。尤其是角色体系和组织权限粒度。

## 9. 审计与监管缺口

仍需补齐：

- 哪些事件必须审计；已确认：第一批必须审计登录/登出、模型调用、用户消息、工具调用、插件调用、权限判断、审批申请、审批结果、业务数据查询、数据导出、Artifact 创建、配置变更、插件启停、模型 Provider 变更。
- 审计字段；待细化。
- 审计留存周期；已确认：可配置。默认 180 天，高风险/业务数据访问默认 1 年，监管或公司制度要求可配置更长。
- 是否支持导出；待确认。
- 是否支持检索；待确认。
- 是否需要防篡改；已确认：需要预留防篡改。每条审计事件记录 hash，按批次生成 hash chain；Phase 1 先写 SQLite，生产阶段接入对象存储/WORM/日志审计平台。
- 是否记录 prompt；已确认：全部记录。
- 是否记录模型输出；已确认：全部记录。
- 是否记录业务结果；已确认：全部记录，但查询、导出等业务数据操作必须进行权限处理。
- 敏感字段如何脱敏；待细化。审计记录需要支持明文受控留存、脱敏展示和权限控制查看。
- 管理员查看审计的权限边界；待细化。

已确认审计记录原则：

```text
所有用户输入、prompt、模型输出、工具调用、业务结果都进入审计。
业务查询、数据导出、敏感数据访问等操作必须先经过权限处理。
审计查看需要权限控制，普通用户不能查看超出自身权限的数据。
```

是否需要用户确认：是。涉及监管和公司数据治理口径。

## 10. Connector Runtime 缺口

已确认插件体系主参考：

```text
以 Codex 插件体系作为主参考。
MCP 作为外部工具协议参考。
Dify 作为插件市场、OAuth、工具配置参考。
claude-code-main 作为 Agent Runtime 和工具执行细节参考。
```

工作台不直接照搬 Codex，而是采用金融企业增强版：

```text
Enterprise Plugin Architecture
  = Codex Plugin model
  + Enterprise IAM
  + RBAC / ABAC
  + Data Permission
  + Approval Workflow
  + Audit / Retention
  + Connector Runtime
  + Business Artifact Renderer
```

插件标准分层已确认：

```text
Plugin Package：发布、安装、授权、启停、版本、依赖、UI、配置。
Skill：告诉 Agent 什么时候使用能力、如何澄清、如何解释结果。
Tool / Capability：模型可调用能力、schema、风险、权限、结果。
Connector：服务端实际连接业务系统或外部系统的执行层。
UI Renderer：右侧业务面板的业务 Artifact 渲染器。
Permission / Approval / Audit：金融企业场景必须内置，不能作为可选能力。
```

仍需补齐：

- 内部业务 Connector 协议；已确认：支持标准 Connector、轻改造 Connector、人工/半自动 Connector 三档。
- 外部通用 Connector 协议；已确认：外部通用插件优先服务端执行，低风险本地文件能力允许本地执行；MCP Server 作为外部工具协议适配层接入，但必须经过 ToolRuntime 和 PermissionService。
- Connector 鉴权方式；已确认：第一批支持服务端托管凭据、用户 OAuth/SSO 授权、企业 IdP 集中授权、系统账号 + 用户身份透传、API Key/Secret、Custom Headers；所有凭据由服务端保存，前端不保存密钥。
- Connector 超时和重试；已确认：Connector Binding 必须包含 `timeout_seconds` 和 `retry_policy`。
- Connector 并发限制；已确认：Connector Binding 必须包含 `rate_limit`，执行时由 ToolRuntime 统一治理。
- Connector 结果标准化；已确认：统一返回 `status`、`summary`、`data`、`artifacts`、`audit_event_id`、`permission_decision`、`next_actions`、`raw_ref`。
- Connector 审计；已确认：Connector Binding 必须包含 `audit_policy`，每次执行必须生成审计事件。
- Connector 错误码；待细化。
- 现有业务系统低改造接入规范；已确认：支持轻改造 Connector，由工作台服务端做适配层。
- 无接口系统的接入边界；已确认：采用人工/半自动 Connector，只生成操作指引、跳转、表单草稿，不做自动操作。

已确认第一阶段不支持核心业务系统 RPA / UI 自动化。

Connector 统一返回结构：

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

Connector Binding 必备治理字段：

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

ToolPool 动态过滤已确认：

```text
每次 Agent run 前，根据 tenant、user、role、workspace、plugin visibility、authorization status、data permission、risk tier、approval policy 生成模型可见工具。
不把系统全部工具一次性暴露给模型。
```

是否需要用户确认：是。尤其是内部业务系统改造标准。

## 11. 建议逐项确认顺序

为了避免范围失控，建议按以下顺序逐项确认：

1. 多模型设置页：入口、角色、密钥安全；
2. 插件中心：入口、角色、生命周期；
3. 审批中心：审批对象、流程、三方优先级；
4. 右侧业务面板：Tab 与 Artifact renderer 规则；
5. 企业账号权限：租户、组织、角色、数据权限；
6. 审计监管：记录范围、留存、脱敏；
7. Connector Runtime：内部业务系统接入标准。

以上确认完成后，才能评估是否可以开发完整平台。否则只能先开发 Phase 1B。

## 12. 当前开发建议

即使补全文档，也不建议一次性开发全套平台。正确做法是：

```text
先开发 Phase 1B Agent Runtime
→ 再开发多模型配置和插件中心的服务端底座
→ 再开发审批中心
→ 再开发业务插件和 Connector
→ 最后评估前端 Runtime 是否迁移
```

原因：

- Agent Runtime 是所有能力的底座；
- 插件中心、审批、多模型都依赖统一 Run / Tool / Audit / Artifact；
- 先做 UI 会导致后端协议反复返工；
- 先做业务插件会导致权限和审计模型不稳定。
