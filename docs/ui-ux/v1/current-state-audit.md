# 当前系统 UI 状态审计

版本：v1  
日期：2026-07-01  
审计对象：`http://127.0.0.1:3001/` 当前本地运行页面  
截图来源：Playwright 页面截图

## 1. 总体判断

当前前端已经完成从旧 Vite/Tauri 原型向 Next.js + assistant-ui 方向迁移，主对话区域已经接近 assistant-ui Base 的基本形态，但仍处在“通用 Agent 原型 + 工作台外壳草稿”阶段。

当前系统适合作为 Phase A 后端 Runtime 对接前端的基础，但不适合直接承载 Phase C-G 的完整设置、插件、审批和业务 Artifact 功能。进入后续开发前，需要明确页面职责边界。

## 2. 当前可保留能力

### 2.1 左侧会话栏

当前状态：

- 已有品牌区。
- 已有新建任务入口。
- 已有会话列表。
- 已有折叠按钮。
- 已有底部“设置与模型”入口。

保留方向：

- 左侧继续作为官方 ThreadList / 会话导航。
- 折叠态保留图标导航。
- 品牌区只承担产品识别和展开入口，不作为复杂首页。

需要调整：

- 会话列表刷新必须避免点击会话时联动清空或重新加载整个列表。
- 折叠态 logo 点击应展开左侧栏。
- 当前会话列表需要稳定选中态、加载态、空态和删除后的 fallback 行为。

## 3. 当前主对话区域

当前空态截图：

![当前空态](/Users/daniel/Desktop/code/工作台/workbench-app/frontend-v2/docs/ui-ux/v1/assets/current-empty-state.png)

当前状态：

- 空态文案已经较简洁。
- Composer 位于中间区域下方。
- 已有 `+` 插件能力按钮和附件按钮。
- 右侧面板开关位于主对话边缘。

保留方向：

- 主对话继续使用 assistant-ui Thread / Composer。
- 空态保留一个短标题，不放大量占位说明。
- Composer 保留 `+` 能力入口。

需要调整：

- 执行过程必须使用 assistant-ui 原生或最接近官方样式的 reasoning/tool-call 展示，而不是自定义大块卡片。
- 模型输出必须支持流式打字机效果。
- 每次执行过程必须跟随对应消息显示，不能浮到顶部或脱离消息上下文。
- 主对话只展示自然语言结果、执行摘要、审批摘要、Artifact 链接卡片，不直接堆复杂业务表格。

## 4. 当前右侧业务面板

当前右侧面板截图：

![当前右侧面板打开](/Users/daniel/Desktop/code/工作台/workbench-app/frontend-v2/docs/ui-ux/v1/assets/current-business-panel-open.png)

当前状态：

- 右侧面板已能打开和折叠。
- 已有拖拽宽度的基础能力。
- 已有 Tab 雏形。
- 当前面板内容为空或偏占位。

保留方向：

- 右侧面板作为业务 Artifact 容器。
- 面板支持多 Tab。
- 面板支持拖拽宽度。

需要调整：

- 去掉“业务面板”标题头的占位感，保留轻量工具栏即可。
- Tab 需要支持 hover 关闭按钮。
- Tab 关闭只关闭视图，不删除 Artifact。
- 空态只提示“从对话中的结果卡片打开业务内容”，不显示假数据。
- 右侧打开/关闭动画应与左侧折叠动画一致。
- 右侧打开按钮大小、视觉权重应与左侧面板按钮一致。

## 5. 当前设置入口

当前设置形态截图：

![当前设置弹窗](/Users/daniel/Desktop/code/工作台/workbench-app/frontend-v2/docs/ui-ux/v1/assets/current-settings-dialog.png)

当前状态：

- 已有“设置与模型”入口。
- 当前形态更接近轻量弹窗或简单设置。

目标偏差：

- 用户已确认设置应是 Codex-style 完整页面。
- 模型、插件、审批、账号权限、审计、诊断都应进入设置页面，而不是弹窗。

后续调整：

- 点击“设置与模型”进入完整设置页面。
- 设置页面左侧二级菜单承载模型、插件、审批、账号权限、审计、诊断。
- 设置页内容区使用 shadcn/ui 表单、表格、Tabs、Dialog、Toast 等组件。

## 6. 当前系统与 Phase A-G 的差距

| 范围 | 当前状态 | 目标状态 | 开发阶段 |
| --- | --- | --- | --- |
| Agent Runtime | 已有基础对话和运行 | 可恢复 Thread、Transcript、ToolResult、UsageMeter | Phase A |
| 权限审计 | UI 暂无完整展示 | 权限判断、审计检索、明文查看审计 | Phase B |
| 模型配置 | 简单设置入口 | 完整 Provider 设置页 | Phase C |
| 插件中心 | Composer 有 `+` 入口 | 设置页插件中心 + Composer 授权插件快捷入口 | Phase D |
| Connector | 前端不直接体现 | 后端 ToolPool + ConnectorResult + Artifact | Phase E |
| 审批中心 | 暂无完整页面 | 设置页审批中心 + 主对话审批摘要卡 | Phase F |
| Artifact Renderer | 右侧空面板/占位 | 右侧业务 Artifact 多 Tab 渲染 | Phase G |

## 7. 开发前风险

1. 如果直接在当前右侧面板加入设置、插件、审批，会破坏“右侧只放业务 Artifact”的已确认原则。
2. 如果继续自定义主对话消息结构，会偏离 assistant-ui 官方体验，后续维护成本高。
3. 如果设置页继续做弹窗，会无法承载模型、插件、审批、审计等企业级功能。
4. 如果业务 Artifact 没有统一 schema，后续问数、理赔、投保等插件会各自写 UI，无法形成平台能力。

