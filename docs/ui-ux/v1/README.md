# UI/UX 设计包 v1

版本：v1  
日期：2026-07-01  
适用范围：企业 Agent 工作台 Phase A-G 开发前 UI/UX 设计基线  
当前系统：`frontend-v2`，Next.js + assistant-ui + shadcn/ui  
设计优先级：assistant-ui 官方能力优先；业务工作台能力作为外挂扩展；无法用官方能力覆盖时再做自定义组件。

## 1. 版本目标

v1 的目标是把已经确认的 Phase A-G 平台能力，落成开发前可执行的 UI/UX 设计约定：

```text
当前系统状态
→ 目标信息架构
→ 核心屏幕规格
→ 核心交互流程
→ 组件状态矩阵
→ Phase A-G 开发映射
```

该版本不是视觉稿终稿，也不是代码实现稿。它是进入开发前的产品交互基线，用于减少开发中反复纠正页面结构、右侧面板用途、设置页归属和业务 Artifact 展示方式。

## 2. 版本产物

| 文件 | 用途 |
| --- | --- |
| `current-state-audit.md` | 当前系统 UI 状态审计，记录现有页面能力、偏差和截图证据 |
| `target-experience-map.md` | 目标体验地图，定义工作台整体信息架构和页面职责 |
| `screen-design-spec.md` | 核心屏幕设计规格，定义左侧、主对话、右侧业务面板、设置页 |
| `interaction-flows.md` | 核心交互流程，覆盖通用对话、模型配置、插件授权、审批、Artifact |
| `component-state-spec.md` | 组件状态矩阵，定义加载、空态、错误、权限、审计等状态 |
| `development-mapping.md` | Phase A-G 到 UI/UX 的开发映射和验收边界 |

## 3. 当前页面证据

以下截图由本地运行的当前系统生成，用于作为 v1 设计对照基线。

| 截图 | 说明 |
| --- | --- |
| ![当前空态](/Users/daniel/Desktop/code/工作台/workbench-app/frontend-v2/docs/ui-ux/v1/assets/current-empty-state.png) | 当前主对话空态、左侧会话列表、右侧面板关闭状态 |
| ![当前右侧面板打开](/Users/daniel/Desktop/code/工作台/workbench-app/frontend-v2/docs/ui-ux/v1/assets/current-business-panel-open.png) | 当前右侧业务面板打开状态 |
| ![当前设置弹窗](/Users/daniel/Desktop/code/工作台/workbench-app/frontend-v2/docs/ui-ux/v1/assets/current-settings-dialog.png) | 当前设置入口仍是弹窗/轻量设置形态，后续应演进为完整设置页面 |

## 4. 关键设计结论

1. 前端主体验继续以 assistant-ui 官方 Thread / Composer / ThreadList 为核心，不重新自研通用聊天框架。
2. 左侧是会话导航，不放业务插件、工作空间占位或复杂管理内容。
3. 中间是 Agent 对话和运行过程，承载自然语言上下文、执行摘要、审批摘要卡、Artifact 结果卡片。
4. 右侧只承载业务 Artifact，不承载设置、插件中心、审批中心、诊断中心。
5. 设置与模型是完整设置页面，承载模型 Provider、插件中心、审批中心、账号权限、审计和诊断。
6. AI 动态 UI 采用受控 Artifact schema + renderer 白名单，不执行模型生成的 React/JS。
7. 所有下载、导出、复制、明文查看、业务查询等高风险操作必须经过权限判断和审计。

## 5. 版本管理规则

后续 UI/UX 变更按版本目录管理：

```text
docs/ui-ux/v1/  当前开发前基线
docs/ui-ux/v2/  下一次系统性交互调整
docs/ui-ux/CHANGELOG.md  版本变化摘要
```

单点修订可以先在 v1 内追加“修订记录”。如果修订改变页面职责、核心流程或组件边界，应升级到 v2。

## 6. 开发准入判断

从 UI/UX 角度，Phase A-G 可以进入开发，但必须遵守以下准入条件：

- Phase A 可先做后端 Runtime，不强制前端重构。
- Phase B/E 可先做服务端能力，不强制新增页面。
- Phase C/D/F/G 涉及前端页面和交互时，必须先按本设计包实现信息架构和状态规则。
- 如果实现中发现 assistant-ui 官方组件无法覆盖核心交互，必须先说明缺口、替代组件设计和对用户体验的影响，再进入自定义实现。

