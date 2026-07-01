# Phase A-G UI/UX 开发映射

版本：v1  
日期：2026-07-01

## 1. 总体开发原则

前端开发顺序必须避免过早自定义通用 Agent UI：

1. 先稳定 assistant-ui 官方 Thread / Composer / ThreadList。
2. 再用 shadcn/ui 和同一技术栈补企业工作台外壳。
3. 最后接入业务 Artifact、设置页和审批等企业能力。

若某项能力 assistant-ui 官方能力无法覆盖，需要输出：

```text
缺口是什么
为什么官方组件覆盖不了
自定义组件的职责边界
是否影响后续 assistant-ui 升级
```

## 2. Phase A：Agent Runtime 完整化

UI 目标：

- 保持现有 assistant-ui 前端可用。
- 支持流式输出。
- 支持本轮执行过程跟随消息展示。
- 支持失败、取消、重试状态。

主要前端触点：

| UI | 后端能力 |
| --- | --- |
| Thread messages | Message / TranscriptEvent |
| Execution process | RuntimeEvent / TranscriptEvent |
| Streaming answer | `/api/agent/run/stream` |
| Retry / cancel | RunStateMachine |
| Usage future display | UsageMeter |

开发边界：

- Phase A 不做完整设置页。
- Phase A 不做插件中心。
- Phase A 不做右侧 Artifact Renderer。
- 如前端必须改，只做兼容性修复。

验收：

- 历史会话可加载。
- 新建任务可创建。
- 输出是流式。
- 执行过程位置正确。
- 失败不假装成功。

## 3. Phase B：IAM / 权限 / 审计

UI 目标：

- 先支撑权限和审计 API。
- 前端可读取当前用户、权限摘要、审计摘要。
- 后续设置页可展示账号权限和审计。

主要前端触点：

| UI | 后端能力 |
| --- | --- |
| 权限不足提示 | PermissionDecision |
| 审计编号 | AuditEvent |
| 明文查看 | sensitive field access |
| 设置页账号权限 | IAM models |
| 审计页 | Audit search/export |

开发边界：

- Phase B 可以先不做账号权限 UI。
- 但所有 API 必须返回 UI 可用的权限结果和审计引用。

验收：

- deny / approval_required / allow 三类权限结果稳定。
- 所有敏感动作有 audit_event_id。
- 审计字段默认脱敏。

## 4. Phase C：模型 Provider 设置

UI 目标：

- 把当前设置弹窗升级为完整设置页面中的“模型”页面。
- 支持 OpenAI-compatible Provider。
- 支持 API Key 脱敏和受控明文查看。

主要屏幕：

```text
设置与模型
→ 模型
  → 当前模型
  → Provider 列表
  → 新增 / 编辑 Provider
  → 测试连接
  → 刷新模型
  → 用量摘要
```

验收：

- 普通用户只能查看授权模型。
- 管理员可新增/编辑 Provider。
- API Key 默认脱敏。
- 明文查看需要权限、确认、审计。
- 连接测试失败显示明确原因。

## 5. Phase D：插件中心

UI 目标：

- 插件中心进入设置页。
- Composer `+` 只展示已授权可用插件。
- 普通用户没有“安装”概念。

主要屏幕：

```text
设置与模型
→ 插件
  → 业务类型筛选
  → 状态筛选
  → 插件卡片
  → 插件详情
  → 申请授权
  → 管理员管理
  → 插件审计
```

验收：

- 问数、理赔、投保等按业务类型展示。
- 未授权插件可申请授权。
- 授权后 Composer + 菜单出现。
- 管理员可配置启用范围。
- 插件操作写审计。

## 6. Phase E：Connector Runtime

UI 目标：

- 前端不直接感知 Connector 内部实现。
- 通过 ToolResult 状态展示工具过程、权限不足、失败和 Artifact。

主要前端触点：

| ConnectorResult | UI |
| --- | --- |
| completed | 主对话摘要 + 可选 Artifact 卡 |
| failed | 错误摘要 + 重试 |
| partial | 部分完成提示 |
| blocked | 阻断原因 |
| approval_required | 审批摘要卡 |

验收：

- 工具调用失败不输出“已完成”。
- 大响应不直接塞进主对话。
- ArtifactRef 可被 Phase G 消费。

## 7. Phase F：审批中心

UI 目标：

- 审批中心进入设置页。
- 主对话只展示审批摘要卡。
- 审批通过后用户手动继续。

主要屏幕：

```text
设置与模型
→ 审批
  → 我的申请
  → 待我审批
  → 已完成
  → 审批详情
```

验收：

- 超权后主对话出现审批卡。
- 点击详情进入设置页审批详情。
- 审批人可通过/拒绝。
- 申请人可继续执行或重新提交。
- 相同内容复用审批时明确提示并写审计。

## 8. Phase G：Artifact Renderer

UI 目标：

- 右侧面板正式变成业务 Artifact Host。
- 主对话结果卡片打开右侧 Tab。
- 动态 UI 受控渲染。

主要屏幕：

```text
主对话
→ 结果卡片
→ 右侧 Artifact Tab
→ Renderer
→ copy / export / download
```

验收：

- 多个查询生成多个卡片和多个 Tab。
- Tab hover 有关闭按钮。
- 关闭 Tab 不删除 Artifact。
- 点击历史卡片可重新打开。
- 未注册 renderer 使用 JSON fallback。
- 复制、导出、下载全部权限判断和审计。

## 9. Phase H：前端 Runtime 迁移评估

待定项：

- 当前先保留 Message/UIMessage 兼容方式。
- 完成服务端 TranscriptEvent 后，再评估是否迁移到更完整的事件驱动前端 runtime。

迁移评估条件：

```text
服务端 TranscriptEvent 稳定
ToolResult / Artifact schema 稳定
assistant-ui 官方 runtime 适配方案明确
现有消息历史可迁移
```

## 10. 开发顺序建议

```text
1. Phase A 后端 Runtime 完整化
2. 修复主对话流式、执行过程、历史会话加载体验
3. Phase B 权限审计底座
4. Phase C 完整设置页和模型设置
5. Phase D 插件中心和 Composer + 授权插件
6. Phase E Connector Runtime
7. Phase F 审批中心和审批摘要卡
8. Phase G 右侧 Artifact Renderer
9. Phase H 前端 runtime 迁移评估
```

## 11. 开发前仍需保持的约束

- 不把设置页放右侧业务面板。
- 不把审批详情放右侧业务面板。
- 不让模型生成的前端代码直接执行。
- 不在 Composer 展示未授权内部业务插件。
- 不让业务结果只存在右侧面板；主对话必须保留结果卡片入口。
- 不绕过权限和审计做导出、复制、下载。

