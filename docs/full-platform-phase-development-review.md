# 全量 Phase A-H 开发前评审

版本：2026-07-01  
范围：Phase A-H  
评审对象：

- `full-platform-implementation-plan.md`
- `full-agent-server-design.md`
- `full-platform-development-gap-analysis.md`
- `phase-a` 至 `phase-g` 详细实施计划
- `phase-a` 至 `phase-g` UI/UX readiness review
- `docs/ui-ux/v1/` 版本化 UI/UX 设计包

## 1. 总体结论

全量 Phase 已经具备“按阶段进入开发”的设计和规划条件，但不应理解为 A-H 可以同时开工。

正确判断是：

```text
Phase A：立即可开工
Phase B：详细设计满足，建议在 A 的 Runtime/Transcript/ToolResult 稳定后开工
Phase C：详细设计满足，可与 B 并行准备，但前端完整设置页需依赖权限边界
Phase D：详细设计满足，需依赖 A/B 的工具池、权限、审计
Phase E：详细设计满足，需依赖 D 的插件/工具定义和 B 的权限审计
Phase F：详细设计满足，需依赖 A/B/E 的 Run、权限和 Connector 阻断机制
Phase G：详细设计满足，需依赖 A/D/E/F 产出的 Artifact、ToolResult、审批与权限
Phase H：作为评估阶段，不应提前开发；等 A-G 协议稳定后再决定是否迁移前端 Runtime
```

因此，当前项目可以进入开发，但开发入口必须是 Phase A，不建议跳到完整插件中心、审批中心或 Artifact Renderer。

## 2. 全量评审总表

| Phase | 主题 | 设计成熟度 | 开发条件 | 是否立即开工 | 主要依赖 | 结论 |
| --- | --- | --- | --- | --- | --- | --- |
| A | Agent Runtime 完整化 | 高 | 满足 | 是 | 当前原型 | 立即开工 |
| B | IAM / RBAC+ABAC / 审计 | 高 | 条件满足 | A 后 | A 的 Run/Thread/ToolResult | A 稳定后开工 |
| C | Model Provider 设置 | 高 | 条件满足 | 可准备，开发排在 B 后或并行后端 | A/B | 后端可准备，前端等设置页 |
| D | 插件中心 | 高 | 条件满足 | 否 | A/B | 等权限和工具池稳定 |
| E | Connector Runtime | 高 | 条件满足 | 否 | B/D | 等插件定义稳定 |
| F | 审批中心 | 高 | 条件满足 | 否 | A/B/E | 等阻断和 resume 机制稳定 |
| G | Artifact Renderer | 高 | 条件满足 | 否 | A/D/E/F | 等 Artifact schema 稳定 |
| H | 前端 Runtime 迁移评估 | 中 | 仅评估，不开发 | 否 | A-G | 后置评估 |

## 3. Phase A 评审：Agent Runtime 完整化

### 3.1 目标

把当前 Agent 原型补齐为可恢复、可回放、可审计、可扩展工具调用的 Runtime 底座。

核心能力：

- Thread 可恢复。
- TranscriptEvent 可回放。
- Run 状态机可靠。
- StandardToolResult 统一工具结果。
- UsageMeter 记录模型调用。
- SSE 兼容 assistant-ui 前端。

### 3.2 开发条件

满足。

依据：

- 详细实施计划已覆盖模型、API、任务、验收。
- UI/UX 已定义主对话、执行过程、流式输出、历史会话加载。
- 当前前端已有 assistant-ui 基础，可做兼容接入。

### 3.3 主要风险

| 风险 | 控制方式 |
| --- | --- |
| TranscriptEvent 和 Message 双写不一致 | 以 Message 保持前端兼容，TranscriptEvent 作为长期事实源 |
| 流式事件格式与前端不匹配 | 先保持现有 `/api/agent/run/stream` 兼容，再逐步增强 |
| Run 状态绕过状态机 | 所有 cancel/retry/fail/complete 统一走 RunStateMachine |
| 工具结果不能回写模型 | StandardToolResult 必须包含 `model_context` |

### 3.4 开发入口

建议按 4 个切片开发：

```text
A1 Runtime 状态机 + TranscriptEvent + UsageMeter
A2 流式输出和 assistant-ui 适配
A3 执行过程归属到消息内
A4 历史会话稳定加载
```

### 3.5 结论

```text
Phase A 立即可开工。
```

## 4. Phase B 评审：企业账号权限 / RBAC+ABAC / 审计底座

### 4.1 目标

建立工作台自有账号权限体系，第三方 SSO 仅作为身份源和组织映射来源。

核心能力：

- Tenant / User / Org / Role / Permission。
- RBAC + ABAC 决策。
- DataScopePolicy。
- PermissionDecision。
- AuditEvent。
- Hash chain。
- 脱敏、明文查看、导出审计。

### 4.2 开发条件

条件满足，但建议在 Phase A 的 Run、Thread、ToolResult、Transcript 基础稳定后开工。

原因：

- 权限和审计需要绑定 Thread、Run、ToolResult、Artifact 等对象。
- 如果 Phase A 对象还未稳定，Phase B 审计字段容易返工。

### 4.3 UI/UX 条件

满足。

已明确：

- 无权限展示申请入口。
- 审计字段默认脱敏。
- 明文查看必须审计。
- 审计页后续放设置页面。

### 4.4 主要风险

| 风险 | 控制方式 |
| --- | --- |
| 权限模型过早复杂化 | 第一版坚持 deny 优先、最小 RBAC+ABAC |
| 审计字段不统一 | 统一 AuditEvent schema 和 object_ref |
| 明文查看走普通 GET | 必须使用独立 reveal endpoint |
| 审计导出未审计 | 导出动作本身写审计 |

### 4.5 结论

```text
Phase B 设计满足开发条件。
建议在 Phase A 核心对象稳定后开工。
```

## 5. Phase C 评审：Model Provider 设置与密钥管理

### 5.1 目标

实现类似 Codex 的完整模型设置能力，第一版支持 OpenAI-compatible Provider。

核心能力：

- Provider 持久化。
- API Key 安全存储。
- 默认脱敏展示。
- 有权限短时明文查看。
- 连通性测试。
- 刷新模型列表。
- Runtime 模型选择。

### 5.2 开发条件

条件满足。

后端可在 Phase A 后启动；前端完整设置页建议在 Phase B 权限边界明确后启动。

### 5.3 UI/UX 条件

满足。

已明确：

- 设置是完整页面，不是弹窗。
- 模型是设置页面菜单。
- API Key 默认脱敏。
- 明文查看需要权限、确认、审计。
- 只做 OpenAI-compatible，不做专有云模型特殊接口。

### 5.4 主要风险

| 风险 | 控制方式 |
| --- | --- |
| API Key 泄漏到前端持久化 | 前端只接收脱敏值；明文短时内存展示 |
| Provider 权限和模型权限混淆 | 区分 provider admin 权限与 model use 权限 |
| 连接测试错误不可诊断 | 返回结构化错误码和可读错误 |

### 5.5 结论

```text
Phase C 设计满足开发条件。
后端可在 A 后准备；前端完整设置页建议和 B 权限体系对齐后实现。
```

## 6. Phase D 评审：Codex-style 插件中心

### 6.1 目标

建立 Codex-style 插件中心和插件目录，支持内部业务插件和外部/本地通用插件。

核心能力：

- Plugin manifest。
- 插件包/版本/发布策略。
- 插件授权。
- 插件启用/停用。
- Catalog 可见性过滤。
- Composer `+` 菜单只展示已授权插件。
- 管理员管理和插件审计。

### 6.2 开发条件

条件满足，但不建议在 A/B 前开工。

原因：

- 插件可见性依赖权限。
- 工具池依赖 Agent Runtime。
- 插件操作需要审计。

### 6.3 UI/UX 条件

满足。

已明确：

- 插件中心在设置页。
- 插件按业务类型组织。
- 状态作为筛选条件。
- Web 用户无“安装”概念，只有申请授权、启用、停用、使用。
- Composer `+` 不展示未授权内部业务插件。

### 6.4 主要风险

| 风险 | 控制方式 |
| --- | --- |
| 后端内部 installation 命名影响前端概念 | 前端文案统一为授权/启用/使用 |
| 未授权插件进入 ToolPool | 每次 Run 动态过滤 ToolPool |
| 插件 manifest 不稳定 | 先固定 MVP 字段，再扩展 |
| 内外部插件边界混乱 | 明确 internal_business 与 external/local 类型 |

### 6.5 结论

```text
Phase D 设计满足开发条件。
建议在 Phase A/B 后开工。
```

## 7. Phase E 评审：Connector Runtime

### 7.1 目标

把 Connector Runtime 融入服务端，作为插件真正调用业务系统或外部工具的执行层。

核心能力：

- Connector models。
- ConnectorResult。
- Credential resolver。
- HTTP client abstraction。
- Runtime invocation service。
- Mock connectors。
- ToolPool assembler。
- Connector routes。

### 7.2 开发条件

条件满足，但依赖 Phase B/D。

原因：

- Connector 调用必须经过权限判断。
- Connector 来源于插件和 ToolPool。
- Connector 结果要写审计。

### 7.3 UI/UX 条件

满足。

前端不直接感知 Connector 内部，只通过 ToolResult 状态展示：

- completed
- failed
- partial
- blocked
- approval_required

### 7.4 主要风险

| 风险 | 控制方式 |
| --- | --- |
| 原始响应塞进对话导致性能/审计风险 | 大响应只保存 raw_ref |
| ConnectorResult 不稳定影响 Artifact | 固定标准结果结构 |
| 凭据泄漏到客户端 | Connector 凭据只在服务端 |
| 权限绕过 | ToolPool 过滤 + invoke 前再次检查 |

### 7.5 结论

```text
Phase E 设计满足开发条件。
建议在 Phase B/D 后开工。
```

## 8. Phase F 评审：审批中心

### 8.1 目标

实现自建审批优先的审批中心，预留钉钉、企业微信等 Provider。

核心能力：

- ApprovalRequest。
- Approval state machine。
- Internal approval provider。
- Resume token。
- blocked run 集成。
- 审批操作审计。
- 审批中心设置页。
- 主对话审批摘要卡。

### 8.2 开发条件

条件满足，但依赖 A/B/E。

原因：

- 审批需要阻断和恢复 Run。
- 审批需要权限和审计。
- 业务审批触发点通常来自 Connector 或数据权限判断。

### 8.3 UI/UX 条件

满足。

已明确：

- 审批中心在设置页。
- 审批详情不放右侧面板。
- 主对话只放审批摘要卡。
- 审批通过不自动继续，用户手动继续。
- 相同内容可复用审批，但复用写审计。

### 8.4 主要风险

| 风险 | 控制方式 |
| --- | --- |
| 审批通过后自动继续 | 必须由用户点击继续执行 |
| 审批详情进入右侧面板 | 统一跳设置页审批详情 |
| resume token 可被滥用 | token 绑定 user/thread/run/scope/expiry |
| 重复审批体验差 | 相同内容允许复用并审计 |

### 8.5 结论

```text
Phase F 设计满足开发条件。
建议在 Phase A/B/E 后开工。
```

## 9. Phase G 评审：右侧业务面板 Artifact Renderer

### 9.1 目标

把右侧面板正式建设成业务 Artifact Host，承载查询结果、图表、报表、业务表单和受控动态 UI。

核心能力：

- Artifact。
- Artifact version。
- Artifact permission。
- Download/export/copy request。
- renderer_hint。
- 主对话 Artifact Link Card。
- 右侧 Artifact Tabs。
- Renderer whitelist。
- JSON fallback。

### 9.2 开发条件

条件满足，但依赖 A/D/E/F。

原因：

- Artifact 由 ToolResult/Connector 产生。
- 打开权限依赖 B。
- 导出/下载/复制依赖审批和审计。
- 动态 UI 安全依赖 renderer schema 固定。

### 9.3 UI/UX 条件

满足。

已明确：

- 右侧面板只承载业务 Artifact。
- 主对话保留结果卡片。
- 多次查询生成多个结果卡片和多个 Tab。
- 关闭 Tab 不删除 Artifact。
- 下载/导出/复制全部权限判断和审计。
- 不执行模型生成 React/JS。

### 9.4 主要风险

| 风险 | 控制方式 |
| --- | --- |
| AI 生成前端代码执行 | 只允许受控 schema + renderer_hint |
| Artifact schema 频繁变化 | Phase G 开发前冻结首批 renderer schema |
| 右侧面板被设置/审批污染 | 明确右侧只放业务 Artifact |
| 主对话没有结果入口 | 每个 Artifact 必须有主对话卡片 |

### 9.5 结论

```text
Phase G 设计满足开发条件。
建议在 Phase A/D/E/F 形成稳定 Artifact 生产链路后开工。
```

## 10. Phase H 评审：前端 Runtime 迁移评估

### 10.1 目标

评估前端是否从当前 Message/UIMessage 兼容模式迁移到更完整的事件驱动 TranscriptEvent Runtime。

### 10.2 当前判断

Phase H 不是开发阶段，而是评估阶段。

当前不应提前做：

- 不迁移 assistant-ui runtime。
- 不替换现有消息存储。
- 不重做 Thread 渲染。

原因：

- A-G 的核心事件协议尚未全部稳定。
- ToolResult、Artifact、Approval、Audit 的最终关联结构还需开发验证。
- assistant-ui 官方能力可能继续变化，提前迁移风险较高。

### 10.3 评估条件

只有满足以下条件后才进入 Phase H：

```text
TranscriptEvent 稳定
ToolResult 稳定
Artifact schema 稳定
Approval/Permission/Audit 事件稳定
历史 Message 可迁移或可双读
assistant-ui 官方 runtime 适配方案明确
```

### 10.4 结论

```text
Phase H 当前仅保留评估入口，不进入开发。
```

## 11. 推荐开发顺序

### 11.1 严格顺序

```text
1. Phase A：Agent Runtime
2. Phase B：IAM + Audit
3. Phase C：Model Provider
4. Phase D：Plugin Center
5. Phase E：Connector Runtime
6. Phase F：Approval Center
7. Phase G：Artifact Renderer
8. Phase H：Frontend Runtime Migration Review
```

### 11.2 可并行准备

| 可并行内容 | 前提 |
| --- | --- |
| Phase B 数据模型设计与 Phase A 后期并行 | A 的 Thread/Run id 结构稳定 |
| Phase C 后端 Provider 与 Phase B 并行 | 权限接口先用 stub，后续接 B |
| Phase D manifest/schema 设计与 Phase B 并行 | 不接 Runtime ToolPool |
| Phase G renderer schema 草案与 Phase E/F 并行 | 不实现前端正式渲染 |

## 12. 一次性补齐缺口前的最终清单

进入开发前已经补齐：

- [x] 总体平台任务级计划。
- [x] 全套 Agent 服务端设计。
- [x] Phase A-G 详细实施计划。
- [x] Phase A-G UI/UX readiness review。
- [x] UI/UX v1 版本化设计包。
- [x] 页面线框。
- [x] 页面规格。
- [x] 组件状态矩阵。
- [x] 开发前 UI/UX 评审。
- [x] 全量 Phase A-H 开发前评审。

仍需在对应 Phase 开发前细化，不阻塞 Phase A：

| 内容 | 阶段 |
| --- | --- |
| 审计导出具体文件格式 | Phase B |
| 模型设置页最终字段顺序和错误文案 | Phase C |
| 插件详情字段和管理员配置项 | Phase D |
| Connector mock 数据集和错误码 | Phase E |
| 审批详情风险文案 | Phase F |
| Artifact renderer 首批 schema 字段冻结 | Phase G |
| TranscriptEvent 前端迁移方案 | Phase H |

## 13. 最终判断

```text
全量 Phase A-H 已完成开发前评审。

可以进入开发，但入口必须是 Phase A。

不要一次性同时开发：
- 完整插件中心
- 完整审批中心
- 完整 Artifact Renderer
- 前端 Runtime 迁移

这些内容设计已满足，但要按依赖顺序开发。
```

