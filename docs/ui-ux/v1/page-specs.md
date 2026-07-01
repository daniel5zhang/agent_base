# 页面规格与开发约束

版本：v1  
日期：2026-07-01  
用途：把页面设计拆成可开发的组件、数据和验收条件。

## 1. 页面清单

| 页面 / 区域 | 路由建议 | 优先级 | 技术来源 |
| --- | --- | --- | --- |
| App Shell + Thread | `/` | P0 | assistant-ui 官方组件优先 |
| 右侧 Artifact 面板 | `/` 内嵌 | P1 | shadcn/ui + 自定义容器 |
| 设置首页 | `/settings` | P1 | shadcn/ui |
| 模型设置 | `/settings/models` | P1 | shadcn/ui |
| 插件中心 | `/settings/plugins` | P2 | shadcn/ui |
| 审批中心 | `/settings/approvals` | P2 | shadcn/ui |
| 账号与权限 | `/settings/iam` | P3 | shadcn/ui |
| 审计 | `/settings/audit` | P2 | shadcn/ui |
| 诊断 | `/settings/diagnostics` | P3 | shadcn/ui |

说明：

- 如果当前路由结构暂不支持多页面设置，可以先做设置页内部状态路由，但 URL 级路由是目标形态。
- 右侧业务面板不单独路由，除非后续需要可分享 Artifact 深链。

## 2. App Shell 规格

### 2.1 组件组成

| 组件 | 来源 | 说明 |
| --- | --- | --- |
| `ThreadListSidebar` | assistant-ui | 左侧会话列表 |
| `Thread` | assistant-ui | 中间消息流 |
| `Composer` | assistant-ui | 输入框 |
| `SidebarToggle` | assistant-ui / shadcn | 左侧折叠按钮 |
| `BusinessPanel` | 自定义 | 右侧业务 Artifact 容器 |
| `SettingsEntry` | shadcn/ui Button | 设置入口 |

### 2.2 数据需求

```text
GET /api/threads
GET /api/threads/{thread_id}
POST /api/threads
POST /api/agent/run/stream
POST /api/runs/{run_id}/cancel
POST /api/runs/{run_id}/retry
```

### 2.3 验收条件

- 新建任务立即进入空态。
- 点击历史会话加载对应消息。
- 点击历史会话时左侧列表不闪烁、不清空。
- 左侧折叠后 logo 可展开。
- 右侧开关大小和动画与左侧一致。
- 服务端不可用时不清空输入。

## 3. 主对话消息规格

### 3.1 消息类型

| 类型 | 展示 |
| --- | --- |
| `user` | 右侧用户 bubble |
| `assistant.text` | 左侧正文，流式 |
| `assistant.reasoning` | 折叠执行过程 |
| `assistant.tool_call` | 执行过程 step |
| `tool.result` | 摘要、卡片或错误 |
| `approval.summary` | 审批摘要卡 |
| `artifact.link` | 结果卡片 |

### 3.2 组件职责

| 组件 | 职责 |
| --- | --- |
| `ReasoningBlock` | 展示执行过程；默认折叠；低对比 |
| `ArtifactLinkCard` | 主对话结果入口 |
| `ApprovalSummaryCard` | 主对话审批入口 |
| `MessageActions` | 复制、重试、更多 |

### 3.3 验收条件

- 执行过程出现在对应 assistant 消息内。
- 执行过程默认折叠，可展开查看 step。
- 输出是流式，不是一次性大段出现。
- 失败时展示失败状态和重试入口。
- 业务结果不直接在主对话展开大表格。

## 4. 右侧 Artifact 面板规格

### 4.1 组件组成

| 组件 | 职责 |
| --- | --- |
| `BusinessPanelShell` | 右侧滑入面板、宽度、resize |
| `ArtifactTabs` | 多 Tab 管理 |
| `ArtifactTab` | 单 Tab，hover 显示关闭按钮 |
| `ArtifactRendererHost` | renderer 分发 |
| `ArtifactActionBar` | 复制、导出、下载 |
| `ArtifactEmptyState` | 空态 |

### 4.2 数据需求

```text
GET /api/artifacts/{artifact_id}
POST /api/artifacts/{artifact_id}/copy
POST /api/artifacts/{artifact_id}/export
POST /api/artifacts/{artifact_id}/download
```

### 4.3 状态模型

```ts
type BusinessPanelState = {
  isOpen: boolean
  activeThreadId: string
  openTabsByThread: Record<string, ArtifactTabState[]>
  activeArtifactIdByThread: Record<string, string | null>
}
```

### 4.4 验收条件

- 默认关闭。
- 点击结果卡片打开。
- 多次查询生成多个 Tab。
- Tab hover 显示关闭按钮。
- 关闭 Tab 不删除 Artifact。
- 关闭最后一个 Tab 显示空态。
- 空态不出现假数据。
- 导出、复制、下载必须权限判断和审计。

## 5. 设置页面规格

### 5.1 组件组成

| 组件 | 来源 | 职责 |
| --- | --- | --- |
| `SettingsLayout` | shadcn/ui | 设置页整体布局 |
| `SettingsNav` | shadcn/ui | 左侧二级菜单 |
| `SettingsContent` | shadcn/ui | 内容区域 |
| `SettingsHeader` | shadcn/ui | 标题和说明 |
| `PermissionGate` | 自定义 | 权限控制 |

### 5.2 路由和菜单

```text
/settings
/settings/models
/settings/plugins
/settings/approvals
/settings/iam
/settings/audit
/settings/diagnostics
```

### 5.3 验收条件

- 点击“设置与模型”进入完整页面，不打开小弹窗。
- 设置页可返回主对话。
- 菜单选中态清晰。
- 没有权限的菜单项禁用或隐藏，策略需统一。

## 6. 模型设置页面规格

### 6.1 组件

| 组件 | 职责 |
| --- | --- |
| `CurrentModelCard` | 当前默认模型 |
| `ProviderList` | Provider 列表 |
| `ProviderForm` | 新增/编辑 Provider |
| `SecretField` | 脱敏/明文查看 |
| `ConnectionTestResult` | 连通性测试结果 |
| `UsageSummary` | 用量摘要 |

### 6.2 数据需求

```text
GET /api/model-providers
POST /api/model-providers
PATCH /api/model-providers/{id}
POST /api/model-providers/{id}/test
POST /api/model-providers/{id}/models/refresh
POST /api/model-providers/{id}/secret/reveal
GET /api/runs/{run_id}/usage
```

### 6.3 验收条件

- 支持 OpenAI-compatible Provider。
- API Key 默认脱敏。
- 明文查看需要权限、确认、短时展示和审计。
- 测试连接失败展示具体错误。
- 普通用户只看授权模型。

## 7. 插件中心页面规格

### 7.1 组件

| 组件 | 职责 |
| --- | --- |
| `PluginCategoryFilter` | 业务类型筛选 |
| `PluginStatusFilter` | 状态筛选 |
| `PluginCard` | 插件卡片 |
| `PluginDetailPanel` | 插件详情 |
| `PluginAuthorizationAction` | 申请授权 |
| `PluginAdminSection` | 管理员管理 |
| `PluginAuditTable` | 插件审计 |

### 7.2 数据需求

```text
GET /api/plugins/catalog
GET /api/plugins/{plugin_id}
POST /api/plugins/{plugin_id}/enable
POST /api/plugins/{plugin_id}/disable
POST /api/plugins/{plugin_id}/authorization-requests
GET /api/plugins/{plugin_id}/audit
```

### 7.3 验收条件

- 按业务类型展示，不按技术类型作为主分组。
- 状态是筛选条件。
- 普通用户不看到“安装”。
- 未授权只能申请授权。
- 已启用插件进入 Composer `+` 菜单。

## 8. 审批中心页面规格

### 8.1 组件

| 组件 | 职责 |
| --- | --- |
| `ApprovalTabs` | 我的申请 / 待我审批 / 已完成 |
| `ApprovalList` | 审批列表 |
| `ApprovalDetail` | 审批详情 |
| `ApprovalActionBar` | 通过 / 拒绝 / 重新提交 |
| `ApprovalResumeCard` | 主对话继续执行 |

### 8.2 数据需求

```text
GET /api/approvals
GET /api/approvals/{approval_id}
POST /api/approvals/{approval_id}/approve
POST /api/approvals/{approval_id}/reject
POST /api/approvals/{approval_id}/resubmit
POST /api/runs/{run_id}/resume
```

### 8.3 验收条件

- 审批中心在设置页。
- 主对话只展示审批摘要卡。
- 审批详情不进右侧业务面板。
- 审批通过后用户手动继续执行。
- 相同内容复用审批时有提示并写审计。

## 9. 审计页面规格

### 9.1 组件

| 组件 | 职责 |
| --- | --- |
| `AuditFilterBar` | 过滤条件 |
| `AuditTable` | 审计列表 |
| `AuditDetailDrawer` | 审计详情 |
| `MaskedValue` | 脱敏字段 |
| `AuditExportAction` | 导出 |

### 9.2 数据需求

```text
GET /api/audit/events
GET /api/audit/events/{event_id}
POST /api/audit/events/{event_id}/reveal
POST /api/audit/export
```

### 9.3 验收条件

- 默认脱敏。
- 查看明文需要权限和审计。
- 审计导出本身也写审计。
- 可按用户、会话、Run、插件、动作类型筛选。

## 10. 自定义组件清单

必须自定义或半自定义：

| 组件 | 原因 | 约束 |
| --- | --- | --- |
| `BusinessPanelShell` | assistant-ui 不负责业务右侧面板 | 动画/尺寸与左侧一致 |
| `ArtifactTabs` | 业务 Artifact 多 Tab | 关闭不删除数据 |
| `ArtifactRendererHost` | 企业业务 schema 渲染 | 白名单 renderer |
| `ArtifactLinkCard` | 主对话业务结果入口 | 不塞大表格 |
| `ApprovalSummaryCard` | 主对话审批入口 | 详情跳设置页 |
| `SecretField` | 明文查看审计 | 禁止持久化明文 |
| `PermissionGate` | 企业权限控制 | deny 优先 |

应优先使用 assistant-ui 官方能力：

| 范围 | 官方能力 |
| --- | --- |
| Thread 消息流 | assistant-ui Thread |
| Composer | assistant-ui Composer |
| Thread List | assistant-ui ThreadList |
| 消息 action | assistant-ui message action 模式 |
| Reasoning / Tool 展示 | assistant-ui 官方或官方兼容模式 |

## 11. 开发前问题闭合状态

| 问题 | 状态 |
| --- | --- |
| 右侧面板承载什么 | 已闭合：只承载业务 Artifact |
| 设置页形态 | 已闭合：完整页面，非弹窗 |
| 插件中心位置 | 已闭合：设置页 |
| 审批中心位置 | 已闭合：设置页 |
| 主对话展示什么 | 已闭合：自然语言、执行过程、摘要卡、结果卡 |
| AI 动态 UI | 已闭合：受控 schema，不执行 JS |
| 多模型 | 已闭合：OpenAI-compatible Provider |
| 审批优先级 | 已闭合：自建审批优先 |

