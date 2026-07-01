# UI/UX 设计版本记录

## v1 - 2026-07-01

首个开发前 UI/UX 设计基线。

范围：

- 当前系统 UI 状态审计。
- Phase A-G 目标体验地图。
- 核心屏幕设计规格。
- 核心交互流程。
- 组件状态矩阵。
- Phase A-G 开发映射。

关键约定：

- assistant-ui 官方能力优先。
- 右侧面板只承载业务 Artifact。
- 设置、插件、审批、权限、审计进入完整设置页面。
- 主对话保留自然语言上下文、执行过程、审批摘要、Artifact 结果卡片。
- AI 动态 UI 采用受控 Artifact schema，不执行模型生成 JS。

### v1 补充 - 页面级设计细化

新增：

- `wireframes.md`：页面级低保真线框。
- `page-specs.md`：页面规格、组件拆分、数据接口和验收条件。
- `pre-development-review.md`：UI/UX 开发前评审结论、开发准入、优先级和暂缓项。

用途：

- 支撑开发前 UI/UX 评审。
- 明确哪些区域用 assistant-ui 官方能力，哪些区域使用 shadcn/ui 或自定义组件。
- 明确 Phase A 可以开工，以及哪些能力必须暂缓到对应 Phase。

### v1 补充 - 全量 Phase 评审

新增：

- `../full-platform-phase-development-review.md`：Phase A-H 全量开发前评审。

用途：

- 明确每个 Phase 的开发成熟度、依赖、风险和开工条件。
- 避免把“设计满足”误解为 A-H 可以同时开工。
