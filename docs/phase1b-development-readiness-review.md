# Phase A 开发前评估

版本：2026-06-30  
适用仓库：`daniel5zhang/agent_base`  
评估对象：`docs/full-agent-server-design.md`

## 1. 结论

本文档是 Phase A 阶段性评估。完整平台关键产品决策已在 `docs/full-platform-development-gap-analysis.md` 中补齐，完整平台任务级实施计划已在 `docs/full-platform-implementation-plan.md` 中补齐。Phase A/Phase A 仍应作为第一阶段先行开发。

Phase A/Phase A 应聚焦服务端 Agent Runtime 完整化，保持前端现有 assistant-ui / react-ai-sdk / UIMessage 路线不变。前端 Runtime 是否迁移到 AssistantTransport 或 AG-UI 保留待定，等服务端 Runtime 完成后再评估。

## 2. 已确认产品决策

1. `approval.required` 需要在右侧业务面板新增审批 Tab。Phase F 先做 mock 审批闭环，后续审批 provider 优先级为自建审批、钉钉、企业微信。
2. 插件结果按 Artifact 类型和复杂度分流。主对话展示 Agent 对话、过程、摘要和结论；右侧业务面板展示结构化、可操作、可审计、可持续查看的业务结果。内部业务插件默认 `both`。
3. Phase A 不把前端 Thread History 直接切到 `TranscriptEvent`。前端继续使用 `Message` / `UIMessage`；服务端新增 `TranscriptEvent` 和投影能力。
4. 多 Model Provider 采用 UI 可配置方案，但前端设置页开发需单独确认。Phase A 先做后端抽象和配置 API。
5. 插件 catalog 采用完整插件管理界面方案，但插件中心开发需单独确认。Phase A 只做服务端 schema 和基础 API 边界，不做完整前端插件中心。

## 3. Phase A 开发范围

Phase A 的目标是：

```text
完整通用 Agent Runtime：
Thread 可恢复、Transcript 可回放、ToolResult 可回写模型、Run 状态机可靠、模型调用可统计、SSE 兼容现有 assistant-ui 前端。
```

### 3.1 必须做

- 新增 `TranscriptEvent` 数据模型；
- 新增 transcript 写入服务；
- 新增 transcript 查询 API；
- 保持现有 `Message` 作为前端历史消息来源；
- 增加 `TranscriptEvent -> Message/UIMessage` 投影服务；
- 标准化 `ToolResult`；
- 改造 AgentLoop，使 tool result 回写模型上下文；
- 增加 Run 状态机校验；
- 增加 `ModelProvider` 抽象；
- 增加模型配置 API 的后端基础能力；
- 增加 `UsageMeter`；
- 补齐单元测试和集成测试；
- 保持 `/api/agent/run/stream` 和 `/api/chat` 兼容。

### 3.2 可以预留但不展开

- `approval.required` 事件类型；
- `PluginPackage.ui.result_surface` 字段；
- plugin installation / authorization / enable / disable 数据模型草案；
- Model Provider UI 所需字段；
- Artifact renderer hint。

### 3.3 明确不做

- 不做前端 Runtime 迁移；
- 不做右侧审批 Tab；
- 不做完整插件中心；
- 不做真实钉钉、企业微信、自建审批接入；
- 不做真实数仓、理赔、投保系统接入；
- 不做完整多模型设置页 UI；
- 不做 MCP 或外部插件运行时；
- 不做生产级密钥 KMS，只做本地开发可运行的加密/脱敏边界。

## 4. 前端影响评估

Phase A 理论上不需要修改前端主交互。

允许的前端兼容性修改：

- 适配后端模型列表读取接口；
- 保持现有 `Message/UIMessage` 历史加载；
- 保持现有 assistant-ui Thread / Composer / Tool display；
- 如需修改前端，必须先列出变更内容并再次确认。

## 5. 服务端开发条件

具备开发条件。

理由：

- 当前后端已有 FastAPI、SQLite、Run、RuntimeEvent、Thread、Message、ToolInvocation、ModelCall、AuditEvent、AgentMemory、Artifact；
- 当前已有 `AgentSessionRuntime`、`QueryLoop`、`ToolRegistry`、`PermissionGate`、`ToolExecutionService`；
- 现有测试已覆盖 MVP 和部分 Phase 1 Agent Runtime；
- 已确认 Thread History 暂不切换到 TranscriptEvent，降低前端风险；
- 已确认前端 Runtime 迁移待定，降低协议重构风险。

## 6. 主要风险

1. `ToolResult` 回写模型上下文如果设计不清，会导致模型无法基于工具结果继续推理。
2. `TranscriptEvent` 与 `Message` 双写需要保证顺序一致，否则历史恢复会出现错乱。
3. Run 状态机如果散落在 API handler 中，会导致 cancel / retry / failed 状态不一致。
4. Model Provider 配置涉及密钥，必须从一开始避免前端持久化明文。
5. Phase A 如果夹带审批、插件中心、真实业务系统，会导致范围失控。

## 7. 建议下一步

下一步不是直接编码，而是输出 Phase A 任务级实施计划：

```text
docs/phase1b-agent-runtime-implementation-plan.md
```

该计划应按以下任务拆分：

1. TranscriptEvent 模型与 Repository；
2. Transcript 写入服务与 Message 双写；
3. Transcript 查询 API 与 UIMessage 投影；
4. ToolResult 标准化；
5. AgentLoop tool_result 回写；
6. Run 状态机；
7. ModelProvider 抽象与配置 API；
8. UsageMeter；
9. 集成测试与回归测试。

完成计划评审后，再进入开发。
