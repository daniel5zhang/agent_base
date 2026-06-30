# claude-code-main 参考项目分析

检查对象：`/Users/daniel/Desktop/code/产品精算/参考项目/claude-code-main`

检查目的：分析该源码快照中的通用 Agent Runtime、工具系统、插件系统、权限系统、会话/记忆机制，判断哪些设计应吸收到企业 Agent 工作台规划中。

## 重要说明

该目录不是官方 Anthropic 仓库，而是 README 中描述的 Claude Code source snapshot，来源于公开暴露的 sourcemap 快照。当前目录也没有 `package.json`，更像源码研究材料，不是可直接安装运行的工程。

因此，本分析只作为架构参考，不建议直接复制代码或依赖其实现细节。

## 总体结论

相比前面分析的 `claims-agent`，这个项目更接近我们要做的“通用 Agent 工作台”。

它的核心不是某个业务流程，而是完整的 Agent Runtime：

```text
用户输入
  → QueryEngine 维护会话状态
  → 构建 system prompt / user context / memory / tools
  → query loop 调用模型
  → 捕获 tool_use
  → 权限判断
  → 执行工具
  → 写回 tool_result / attachments / progress
  → 继续下一轮模型调用
  → 直到无工具调用、被中断、达到预算或达到 maxTurns
```

对工作台的直接影响：

- 一阶段通用 Agent 能力，应强参考它的 QueryEngine / query loop / Tool 接口。
- 二阶段插件平台，应参考它的 plugin manifest / marketplace / built-in plugin / userConfig / MCP 绑定。
- 金融业务插件不能只做“API 菜单”，应被统一纳入工具权限、执行过程、审计、可观测、插件生命周期。

## 技术栈与产品形态

README 和源码显示：

- Runtime：Bun / TypeScript。
- UI：React + Ink，终端交互。
- 核心：`QueryEngine.ts`、`query.ts`、`Tool.ts`、`tools.ts`。
- 工具：`src/tools/*`，包含 Bash、文件、搜索、MCP、Agent、Skill、任务、计划模式等。
- 插件：`src/plugins`、`src/services/plugins`、`src/utils/plugins`。
- 记忆：`src/memdir`。
- 远程/桥接：`src/remote`、`src/bridge`。
- 命令：`src/commands`。
- 技能：`src/skills`。

它本质上是“Agent 产品 + Agent Runtime + 工具平台 + 插件平台 + 终端 UI”。

## 核心 Agent Runtime

### QueryEngine

`src/QueryEngine.ts` 的核心注释说明：

```text
One QueryEngine per conversation.
Each submitMessage() call starts a new turn within the same conversation.
State persists across turns.
```

它维护：

- `mutableMessages`
- `abortController`
- `permissionDenials`
- `totalUsage`
- `readFileState`
- `discoveredSkillNames`
- `loadedNestedMemoryPaths`

每次 `submitMessage()` 会：

1. 读取当前配置、工具、模型、权限上下文。
2. 构建 system prompt / user context / system context。
3. 注册结构化输出约束。
4. 处理 slash command / 用户输入 / 附件。
5. 调用底层 `query()`。
6. 将内部消息转换成 SDK Message。
7. 持久化 transcript。
8. 统计 usage / cost / permission_denials。

对工作台的启发：

工作台服务端也应该有独立的 `AgentSessionRuntime`，不能把逻辑散落在 API handler 里。

建议抽象：

```text
AgentSessionRuntime
  - session_id
  - workspace_id
  - user_id
  - messages
  - runtime_context
  - tool_pool
  - memory_context
  - model_context
  - permission_context
  - usage
  - abort_controller

submit_message(input)
  → build_prompt_context()
  → run_query_loop()
  → persist_events()
  → emit_stream()
```

## query loop

`src/query.ts` 是真正的 Agent 主循环。

它使用 `while (true)` 执行：

1. 从上次 compact boundary 后取消息。
2. 注入 memory / skill discovery / queued commands。
3. 执行 microcompact / autocompact / context collapse。
4. 构建完整 system prompt。
5. 调用模型流式输出。
6. 捕获 assistant message 中的 `tool_use`。
7. 如果没有 tool use，则结束。
8. 如果有 tool use，则执行工具。
9. 将 `tool_result`、附件、记忆、队列消息加入上下文。
10. 刷新工具池。
11. 检查 maxTurns / abort / token budget。
12. 进入下一轮。

这就是通用 Agent 的关键闭环。

建议工作台一阶段服务端按这个模型重构，而不是只做：

```text
用户消息 → 模型回复
```

更合理的是：

```text
用户消息
  → AgentLoop
  → ModelCall
  → ToolUseDetected
  → PermissionGate
  → ToolExecution
  → ToolResult
  → NextModelCall
  → FinalResponse
```

## Tool 接口设计

`src/Tool.ts` 的 `Tool` 类型非常完整。

一个工具不只是 function schema，而包含：

- `name`
- `aliases`
- `searchHint`
- `inputSchema`
- `inputJSONSchema`
- `outputSchema`
- `call()`
- `description()`
- `validateInput()`
- `checkPermissions()`
- `isEnabled()`
- `isReadOnly()`
- `isDestructive()`
- `isConcurrencySafe()`
- `isSearchOrReadCommand()`
- `isOpenWorld()`
- `requiresUserInteraction()`
- `shouldDefer`
- `alwaysLoad`
- `maxResultSizeChars`
- `prompt()`
- `userFacingName()`
- `getToolUseSummary()`
- `getActivityDescription()`
- `toAutoClassifierInput()`
- `mapToolResultToToolResultBlockParam()`
- UI 渲染相关方法：
  - `renderToolUseMessage`
  - `renderToolResultMessage`
  - `renderToolUseProgressMessage`
  - `renderToolUseRejectedMessage`
  - `renderToolUseErrorMessage`
  - `renderGroupedToolUse`

这对我们当前插件标准有直接修正价值。

工作台插件能力不应只定义：

```json
{
  "capability": "ask_data.query",
  "input_schema": {},
  "output_schema": {}
}
```

而应补充：

```json
{
  "tool": {
    "name": "ask_data.query",
    "display_name": "问数查询",
    "description": "查询授权范围内的数仓指标",
    "input_schema": {},
    "output_schema": {},
    "risk_tier": "L2",
    "read_only": true,
    "destructive": false,
    "concurrency_safe": true,
    "requires_user_interaction": false,
    "max_result_size_chars": 20000,
    "permission_policy": {},
    "progress_schema": {},
    "artifact_schema": {},
    "ui": {
      "activity_description": "查询数仓指标",
      "result_renderer": "ask_data_result",
      "progress_renderer": "query_plan_progress"
    }
  }
}
```

## 工具池与 MCP 合并

`src/tools.ts` 是内置工具注册中心。

它做了几件重要的事：

1. 注册所有内置工具。
2. 根据环境开关加载可选工具。
3. 根据权限 deny rules 过滤工具。
4. 将内置工具和 MCP 工具合并。
5. 去重，内置工具优先。
6. 为 prompt cache 稳定性排序。

关键函数：

- `getAllBaseTools()`
- `getTools(permissionContext)`
- `assembleToolPool(permissionContext, mcpTools)`
- `getMergedTools(permissionContext, mcpTools)`

对工作台的启发：

工作台也需要“工具池组装器”，而不是前端 `+` 菜单和服务端工具列表各管各的。

建议：

```text
ToolRegistry
  - built_in_tools
  - plugin_tools
  - mcp_tools
  - internal_business_tools

ToolPoolAssembler
  input:
    user
    workspace
    tenant
    role
    permission_context
    plugin_catalog
    policy_rules
  output:
    visible_tools_for_model
    visible_tools_for_ui
    denied_tools_with_reason
```

## 权限模型

权限相关主要在：

- `src/hooks/useCanUseTool.tsx`
- `src/hooks/toolPermission/*`
- `src/utils/permissions/permissions.ts`

权限决策流程：

```text
tool_use
  → validateInput
  → hasPermissionsToUseTool
  → allow / deny / ask
  → 如果 ask:
      - coordinator 自动判断
      - swarm worker 代理处理
      - classifier 自动判断
      - interactive permission dialog
  → 用户允许/拒绝/中断
  → 记录 permission decision
```

它还区分：

- 默认权限。
- Plan mode 权限。
- Bypass permissions。
- Auto mode。
- always allow / always deny / always ask。
- managed settings / enterprise policy。
- 工具级权限。
- 命令级权限。
- 子代理权限。

对工作台的启发：

金融工作台需要类似结构，但要替换为企业权限/监管策略：

```text
ToolPermissionContext
  - tenant_id
  - user_id
  - workspace_id
  - roles
  - data_permissions
  - plugin_permissions
  - approval_policies
  - risk_tier_rules
  - org_managed_rules
  - session_overrides

PermissionDecision
  - allow
  - deny
  - ask_user
  - require_approval
  - require_data_permission_application
```

对于问数插件，应扩展为：

```text
ask_data.query
  → 检查插件可见性
  → 检查指标权限
  → 检查维度权限
  → 检查数据范围
  → 检查是否跨机构/跨部门/敏感字段
  → allow / block / apply_permission
```

## 工具执行与并发

工具执行在：

- `src/services/tools/toolOrchestration.ts`
- `src/services/tools/StreamingToolExecutor.ts`
- `src/services/tools/toolExecution.ts`

设计要点：

- 工具按 `isConcurrencySafe()` 分组。
- 只读/搜索类工具可并发执行。
- 非并发安全工具串行执行。
- 最大并发数可配置，默认类似 10。
- 流式工具执行可在模型输出 tool_use 后立即开始。
- 工具执行中可持续发 progress。
- 一个并发工具出错时，可取消兄弟工具。
- 中断行为由工具定义：
  - `cancel`
  - `block`

对工作台的启发：

一阶段至少需要：

- 工具运行状态。
- 可取消。
- 可串行/并行。
- progress event。
- error event。

二阶段内部业务插件需要：

- 高风险业务默认串行。
- 只读分析工具可以并行。
- 写操作、审批、业务系统变更必须串行且强审计。

建议新增：

```text
ToolExecutionPolicy
  - concurrency_safe
  - read_only
  - destructive
  - interrupt_behavior
  - max_runtime_seconds
  - retry_policy
  - result_size_policy
```

## ToolSearch / Deferred Tools

Tool 接口中有：

- `shouldDefer`
- `alwaysLoad`
- `searchHint`

`ToolSearchTool` 用于延迟加载工具。这样模型初始上下文不需要塞入所有工具 schema。

对工作台非常重要。

企业工作台后续插件会很多：问数、理赔、投保、保全、客服、财务、人事、文件、本地工具、外部 SaaS。不能每次对话都把所有插件 schema 塞进模型。

建议工作台采用三层工具可见性：

```text
Always Loaded
  - 当前会话必要基础工具
  - 例如 diagnostics、workspace、plugin_search

Deferred / Searchable
  - 大部分业务插件
  - 模型先通过 tool_search / capability_search 找到

Hidden / Not Authorized
  - 用户无权限
  - 工作空间不可见
  - 管理员禁用
```

这会显著降低 token 成本，也能减少模型误调用。

## AgentTool 与多代理

`src/tools/AgentTool/AgentTool.tsx` 实现了子代理能力。

输入包括：

- `description`
- `prompt`
- `subagent_type`
- `model`
- `run_in_background`
- `name`
- `team_name`
- `mode`
- `isolation`
- `cwd`

支持：

- 前台子代理。
- 后台 Agent 任务。
- worktree 隔离。
- remote Agent。
- teammate / swarm 模式。
- 任务进度。
- 子代理权限模式。

对工作台的启发：

当前一阶段可以不做复杂多代理，但架构应预留：

```text
AgentRun
  - parent_run_id
  - child_run_id
  - agent_type
  - model
  - workspace
  - isolation_mode
  - permission_mode
  - status
```

内部业务场景也会需要：

- 主 Agent 负责意图识别和对话。
- 问数 Agent 负责生成查询计划。
- 理赔 Agent 负责审核流程。
- 风控 Agent 负责规则解释。

## SkillTool 与技能系统

`src/tools/SkillTool/SkillTool.ts` 把技能作为“可调用能力”执行。

关键点：

- Skill 是 markdown / prompt 定义。
- 通过 frontmatter 定义描述、模型、allowed tools、when_to_use、hooks、context、agent。
- Skill 可以在 forked sub-agent 中执行。
- Skill 可以来自：
  - bundled skills
  - user skills
  - project skills
  - managed policy skills
  - plugin skills
  - MCP skills

这与我们之前讨论的结论一致：

```text
Skill 告诉模型怎么做。
Tool / Connector 负责真正执行。
Plugin 负责打包和发布 skill + tools + MCP/Connector + UI/配置。
```

工作台应采用这个分层。

例如问数插件：

```text
plugin: ask-data
  skill:
    - 什么时候应该使用问数
    - 如何澄清口径
    - 如何解释指标结果
  tool:
    - ask_data.query
    - ask_data.describe_metric
    - ask_data.request_permission
  connector:
    - 服务端数仓查询适配器
  ui:
    - 查询计划 Tab
    - 数据结果 Tab
    - 权限申请 Tab
```

## 插件系统

插件相关文件很多，核心包括：

- `src/utils/plugins/schemas.ts`
- `src/utils/plugins/pluginLoader.ts`
- `src/plugins/builtinPlugins.ts`
- `src/services/plugins/PluginInstallationManager.ts`
- `src/utils/plugins/mcpbHandler.ts`
- `src/utils/plugins/pluginPolicy.ts`

插件 Manifest 支持：

- metadata：
  - `name`
  - `version`
  - `description`
  - `author`
  - `homepage`
  - `repository`
  - `license`
  - `keywords`
  - `dependencies`
- components：
  - `commands`
  - `agents`
  - `skills`
  - `hooks`
  - `outputStyles`
  - `mcpServers`
  - `lspServers`
  - `channels`
  - `settings`
  - `userConfig`

插件来源：

1. session-only plugins，本地 `--plugin-dir`。
2. marketplace plugins。
3. built-in plugins。

加载优先级：

```text
session plugins
  > marketplace plugins
  > builtin plugins
```

但 managed settings / enterprise policy 可以锁定插件，阻止本地覆盖。

对工作台的启发：

我们的插件标准需要从“插件 = 一个接口”升级为：

```text
PluginPackage
  - manifest
  - skills
  - tools
  - server_bindings
  - mcp_servers
  - ui_panels
  - hooks
  - user_config
  - permissions
  - release_policy
  - dependencies
```

并且需要定义插件来源优先级：

```text
org-managed built-in plugin
  > tenant-managed internal plugin
  > marketplace/external plugin
  > local/session dev plugin
```

金融企业场景下，管理员策略必须优先于本地调试版本。

## userConfig 与敏感配置

插件 Manifest 中的 `userConfig` 设计值得参考。

它允许插件声明需要用户配置的值：

- `type`
- `title`
- `description`
- `required`
- `default`
- `multiple`
- `sensitive`
- `min`
- `max`

敏感值进入 secure storage，非敏感值进入 settings。

工作台应采用同类设计：

```json
{
  "user_config": {
    "warehouse_env": {
      "type": "string",
      "title": "数仓环境",
      "required": true,
      "sensitive": false
    },
    "api_token": {
      "type": "string",
      "title": "访问令牌",
      "required": true,
      "sensitive": true
    }
  }
}
```

不过内部业务插件一般不应让个人用户配置 token，而应通过企业 IAM / SSO / 服务端密钥管理统一注入。

## 内置工具清单参考

源码中内置工具包括：

- AgentTool
- SkillTool
- BashTool
- PowerShellTool
- FileReadTool
- FileWriteTool
- FileEditTool
- NotebookEditTool
- GlobTool
- GrepTool
- WebFetchTool
- WebSearchTool
- MCPTool
- ListMcpResourcesTool
- ReadMcpResourceTool
- LSPTool
- TodoWriteTool
- TaskCreateTool
- TaskGetTool
- TaskUpdateTool
- TaskListTool
- TaskOutputTool
- TaskStopTool
- AskUserQuestionTool
- EnterPlanModeTool
- ExitPlanModeTool
- EnterWorktreeTool
- ExitWorktreeTool
- ToolSearchTool
- ConfigTool
- RemoteTriggerTool
- CronCreateTool / CronDeleteTool / CronListTool
- SendMessageTool
- TeamCreateTool / TeamDeleteTool

工作台一阶段不需要全部实现，但建议基础内置工具分三批：

### 一阶段必要

- `workspace.read`
- `workspace.search`
- `workspace.write` 或先限制为只读
- `shell.run` 或本地分析命令，先强权限
- `tool.search`
- `memory.read`
- `memory.write`
- `plan.update`
- `ask_user`
- `artifact.create`
- `diagnostic.check`

### 一阶段可选

- `web.fetch`
- `web.search`
- `model.config`
- `file.diff`
- `todo.write`
- `task.status`

### 二阶段

- `mcp.invoke`
- `plugin.install`
- `plugin.refresh`
- `agent.spawn`
- `agent.message`
- `approval.request`
- `business.run`
- `business.trace`
- `cron.create`
- `remote.agent`

## 记忆系统

`src/memdir` 包含：

- `findRelevantMemories.ts`
- `memoryScan.ts`
- `memoryAge.ts`
- `paths.ts`
- `teamMemPaths.ts`
- `teamMemPrompts.ts`

`query.ts` 中每轮会启动 `startRelevantMemoryPrefetch()`，并在工具执行后将相关 memory 作为 attachment 注入上下文。

对工作台的启发：

记忆不应简单作为“每次全量拼 prompt”。

建议：

```text
MemoryService
  - profile memory
  - workspace memory
  - project memory
  - plugin memory
  - team memory

每轮：
  - 根据当前消息异步预取相关记忆
  - 去重
  - 只注入相关片段
  - 记录记忆来源
```

这对长期工作台会话很重要。

## 会话持久化与 SDK 消息

QueryEngine 将内部消息转换为 SDK Message：

- assistant
- user
- system/init
- compact_boundary
- tool_progress
- tool_use_summary
- result
- api_retry

并持久化 transcript。

工作台应该标准化自己的运行事件协议：

```text
agent.message.user
agent.message.assistant.delta
agent.message.assistant.completed
agent.tool.started
agent.tool.progress
agent.tool.completed
agent.tool.failed
agent.permission.requested
agent.permission.allowed
agent.permission.denied
agent.compact.started
agent.compact.completed
agent.result.completed
```

前端不要直接依赖模型 provider 的原始事件。

## 与 claims-agent 的关系

两个参考项目定位不同：

| 项目 | 定位 | 对工作台的价值 |
|---|---|---|
| `claude-code-main` | 通用 Agent Runtime / 工具平台 / 插件平台 | 一阶段通用 Agent 架构强参考 |
| `claims-agent` | 特药理赔业务 Agent 流水线 | 二阶段内部业务插件强参考 |

推荐组合：

```text
工作台通用 Agent Runtime
  参考 claude-code-main

内部业务插件运行标准
  参考 claims-agent

金融审计、权限、Trace、人审
  两者结合，claims-agent 更强
```

## 对当前工作台规划的调整建议

### 1. 一阶段目标应明确为“通用 Agent Runtime 闭环”

一阶段不只是 UI 对话，而要形成：

```text
AgentSessionRuntime
ToolRegistry
ToolPoolAssembler
PermissionGate
ToolExecutionService
RuntimeEventStream
MemoryService
ArtifactService
ModelProviderRegistry
```

### 2. 插件标准需要拆为三层

```text
Plugin Package
  负责发布、安装、版本、依赖、配置、组件贡献。

Tool / Capability
  负责模型可调用能力、schema、权限、并发、风险、结果。

Connector Binding
  负责服务端实际连接业务系统、执行工具、审计。
```

### 3. Skill 应成为插件的一等组件

插件不仅提供接口，还要提供“如何使用这个能力”的说明。

```text
plugin
  - skill: model instructions
  - tool: callable operation
  - connector: server execution
  - ui: panel renderer
```

### 4. 工具执行过程必须产品化

不是简单显示“思考中”。

要显示：

- 正在调用哪个工具。
- 是否需要权限。
- 权限来自哪里。
- 工具输入摘要。
- 工具进度。
- 工具结果摘要。
- 是否被折叠。
- 是否产生 artifact。

这也解释了为什么之前前端如果只靠 assistant-ui 会不够：assistant-ui 解决聊天 UI，不解决完整 Agent Runtime 事件语义。

### 5. 插件 OTA 应支持 cache-only startup

Claude Code 的插件加载区分：

- cache-only：启动时不阻塞。
- full refresh：用户明确刷新或后台更新。

工作台也应采用：

```text
启动：
  读取本地缓存 catalog + manifest
  后台检查服务端插件发布状态
  如果有更新，提示或自动刷新

显式刷新：
  拉取最新 catalog
  下载/校验 manifest
  更新本地缓存
  重建 ToolPool
```

### 6. 高风险业务插件必须进入 PermissionGate

所有内部业务 Connector 必须走统一权限决策：

```text
模型提出 tool_use
  → ToolPool 中存在
  → schema 校验
  → plugin 可见性
  → 用户权限
  → 数据权限
  → 风险策略
  → 审批状态
  → 执行
```

不能允许业务插件绕过 Agent Runtime 直接执行。

## 推荐下一步

建议更新以下工作台设计文档：

1. `product-architecture.md`

补充：

- `AgentSessionRuntime`
- `QueryLoop`
- `ToolRegistry`
- `ToolExecutionService`
- `PermissionGate`
- `EventStream`

2. `plugin-standard.md`

补充：

- Plugin Package / Tool / Connector 三层标准。
- Skill 作为一等组件。
- ToolExecutionPolicy。
- userConfig / sensitive config。
- deferred tools / tool search。
- plugin source precedence。

3. `mvp-stage-plan.md`

调整一阶段开发任务：

- 从“页面 + mock 通用 Agent”升级为“可运行 Agent Loop”。
- 一阶段至少实现：
  - 模型调用。
  - tool use 解析。
  - 内置工具执行。
  - 权限门禁。
  - tool_result 回填。
  - 执行过程事件。
  - 记忆最小闭环。

4. 后续实现顺序建议：

```text
Step 1: AgentSessionRuntime + QueryLoop
Step 2: Tool 接口与内置工具注册
Step 3: PermissionGate
Step 4: EventStream / RuntimeEvent
Step 5: Memory attachment
Step 6: PluginPackage manifest v2
Step 7: 问数插件迁移到新 Tool/Connector 标准
```

## 总体判断

`claude-code-main` 是目前最接近工作台一阶段目标的参考项目。

但要注意：

- 它是代码开发 Agent，不是企业金融工作台。
- 它的权限模型偏本地开发工具，工作台要替换成企业 IAM + 数据权限 + 审批策略。
- 它的插件系统偏本地/marketplace/CLI，工作台要改为服务端发布 + 客户端 OTA + 企业策略控制。
- 它的 UI 是终端 Ink，不能直接复用到 Web，但执行事件语义值得复用。

最终建议：

```text
一阶段通用 Agent Runtime：
  强参考 claude-code-main。

二阶段内部业务插件：
  强参考 claims-agent。

工作台插件平台：
  用 claude-code-main 的插件组件模型
  + claims-agent 的业务流水线/审计/人审模型
  + 金融监管权限和数据治理要求。
```
