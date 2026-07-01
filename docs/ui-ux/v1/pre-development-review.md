# UI/UX 开发前评审结论

版本：v1  
日期：2026-07-01  
评审范围：

- `wireframes.md`
- `page-specs.md`
- `development-mapping.md`
- 当前系统截图基线
- Phase A-G 详细实施计划和 readiness review

## 1. 总体结论

UI/UX 设计已经满足进入 Phase A 开发条件。

原因：

1. 页面职责已经闭合：左侧会话、中间对话、右侧业务 Artifact、设置页管理能力。
2. 技术边界已经闭合：assistant-ui 官方能力优先，shadcn/ui 补企业页面，自定义组件只用于业务面板、Artifact、审批卡、权限门禁等必要扩展。
3. Phase A-G 的前端影响已经映射到页面、组件、接口和验收条件。
4. 当前未发现必须继续产品确认的问题。

但开发策略不能一次性做完所有 UI。建议先进入 Phase A，同时修复当前主对话体验问题；Phase C/D/F/G 再按设置页、插件、审批、Artifact 分阶段实现。

## 2. 设计闭合项

| 议题 | 结论 | 状态 |
| --- | --- | --- |
| 工作台总体结构 | 左侧会话 + 中间 Agent + 右侧 Artifact + 设置页 | 已闭合 |
| assistant-ui 使用原则 | 官方 Thread / Composer / ThreadList 优先 | 已闭合 |
| 右侧面板职责 | 只承载业务 Artifact | 已闭合 |
| 设置页职责 | 模型、插件、审批、账号权限、审计、诊断 | 已闭合 |
| 插件中心位置 | 设置页插件菜单 | 已闭合 |
| 审批中心位置 | 设置页审批菜单 | 已闭合 |
| 主对话内容 | 自然语言、执行过程、摘要卡、结果卡、审批卡 | 已闭合 |
| AI 动态 UI | 受控 Artifact schema + renderer 白名单 | 已闭合 |
| 多模型配置 | OpenAI-compatible Provider，完整设置页 | 已闭合 |
| 数据/插件审批 | 自建审批优先，钉钉等作为后续集成 | 已闭合 |

## 3. 开发准入判断

### 3.1 可以立即进入开发的内容

| 内容 | 是否可开发 | 依据 |
| --- | --- | --- |
| Phase A Agent Runtime | 可以 | UI 只需保持兼容并修复流式/执行过程/历史会话体验 |
| 主对话流式输出修复 | 可以 | page-specs 已定义消息状态和验收 |
| 执行过程消息内展示 | 可以 | wireframes 已定义位置，component-state 已定义状态 |
| 历史会话加载稳定性 | 可以 | page-specs 已定义验收 |
| 右侧面板空态和动画修复 | 可以 | screen-design/page-specs 已定义 |

### 3.2 需要依赖后端能力后开发的内容

| 内容 | 依赖 |
| --- | --- |
| 模型 Provider 设置页 | Phase C API |
| 插件中心 | Phase D API |
| 审批中心 | Phase F API |
| 审计页 | Phase B Audit API |
| Artifact Renderer | Phase G Artifact API |
| 复制/导出/下载权限审计 | Phase B + Phase G |

### 3.3 不建议现在开发的内容

| 内容 | 原因 |
| --- | --- |
| 完整插件中心前端 | 需要 Phase B/D 权限和插件 API 稳定 |
| 完整审批中心前端 | 需要 Phase F 审批状态机稳定 |
| 完整 Artifact Renderer | 需要 Artifact schema 和 renderer_hint 稳定 |
| 前端 runtime 迁移 | 需等 TranscriptEvent / ToolResult / Artifact schema 稳定 |

## 4. 当前系统必须优先修复的 UI 问题

这些问题影响一阶段通用 Agent 体验，建议作为 Phase A 前端并行修复项。

| 优先级 | 问题 | 目标 |
| --- | --- | --- |
| P0 | 输出不是稳定流式体验 | assistant 回复必须流式打字机输出 |
| P0 | 执行过程样式和位置偏离 assistant-ui 官方体验 | 执行过程进入对应 assistant 消息，默认折叠，低对比 |
| P0 | 历史会话点击后列表/消息加载体验不稳定 | 会话列表和消息加载解耦 |
| P1 | 右侧面板打开/关闭动画不一致 | 与左侧折叠动画一致 |
| P1 | 右侧面板仍有占位感 | 默认空态只提示从结果卡打开业务内容 |
| P1 | 设置仍是弹窗形态 | Phase C 开始前改为完整设置页面 |

## 5. 自定义组件准入清单

自定义组件只允许用于 assistant-ui/shadcn 无法直接覆盖的企业工作台能力。

| 组件 | 是否允许自定义 | 准入理由 |
| --- | --- | --- |
| `BusinessPanelShell` | 允许 | assistant-ui 不提供业务右侧 Artifact 容器 |
| `ArtifactTabs` | 允许 | 需要会话维度、多 Artifact、关闭不删除 |
| `ArtifactRendererHost` | 允许 | 需要 renderer_hint 白名单和安全渲染 |
| `ArtifactLinkCard` | 允许 | 主对话业务结果入口 |
| `ApprovalSummaryCard` | 允许 | 主对话审批入口 |
| `SecretField` | 允许 | 明文查看、脱敏、审计是企业安全需求 |
| `PermissionGate` | 允许 | RBAC/ABAC 权限控制 |
| 通用 Thread / Composer | 不建议自定义 | 应使用 assistant-ui 官方能力 |
| 通用会话列表 | 不建议自定义 | 应使用 assistant-ui 官方 ThreadList |

## 6. Phase A 开发入口建议

Phase A 建议拆成 4 个可验收切片。

### Slice A1：后端 Runtime 状态机和 Transcript

目标：

- Run 状态可靠。
- TranscriptEvent 可追加和回放。
- UsageMeter 可记录。
- Message 继续兼容前端。

验收：

- 普通对话写 Message 和 TranscriptEvent。
- 工具调用写 tool event。
- cancel / retry / failed / completed 状态一致。

### Slice A2：流式输出和 assistant-ui 适配

目标：

- `/api/agent/run/stream` 输出前端可消费的流式事件。
- 前端显示打字机效果。

验收：

- 长文本不是一次性出现。
- 中途取消后 UI 和后端状态一致。

### Slice A3：执行过程展示

目标：

- 执行过程进入对应 assistant 消息。
- 默认折叠。
- 运行中有轻量动态效果。

验收：

- 每轮用户输入下方都有对应执行过程。
- 历史会话回放时执行过程仍归属正确消息。

### Slice A4：历史会话稳定加载

目标：

- 会话列表和消息加载解耦。
- 点击会话不会清空 Composer 或造成页面上下分裂。

验收：

- 点击多个历史会话均可稳定切换。
- 新建任务后可返回历史会话。
- 服务端失败时展示错误，不破坏已有状态。

## 7. Phase A 后是否进入 Phase B/C 的判断

Phase A 完成后，必须满足：

- Thread 可恢复。
- 流式输出稳定。
- 执行过程归属正确。
- ToolResult 基础结构稳定。
- Run 状态机稳定。
- 前端不再有会话切换错位问题。

满足后进入：

```text
Phase B：权限审计底座
Phase C：完整设置页 + 模型 Provider
```

Phase B/C 可以并行，但前端完整设置页建议从 Phase C 开始落地。

## 8. 仍需后续评审的内容

以下不是当前开发阻塞项，但进入对应 Phase 前需要做细化：

| 内容 | 评审时机 |
| --- | --- |
| Artifact schema 具体字段 | Phase G 开发前 |
| 每种 renderer 的视觉细节 | Phase G 开发前 |
| 审批详情字段和风险展示文案 | Phase F 开发前 |
| 插件详情页字段和管理员配置项 | Phase D 开发前 |
| 审计导出格式 | Phase B 审计 API 完成后 |
| 前端 runtime 是否迁移 TranscriptEvent | Phase H |

## 9. 最终判断

```text
UI/UX 设计已满足 Phase A 开发条件。

建议下一步：
1. 开始 Phase A Agent Runtime 开发；
2. 同步修复主对话流式、执行过程、历史会话加载；
3. 不要提前开发完整插件中心、审批中心和 Artifact Renderer；
4. Phase A 完成后再进入 B/C。
```

