# 核心交互流程

版本：v1  
日期：2026-07-01

## 1. 通用 Agent 对话

```mermaid
sequenceDiagram
  participant U as 用户
  participant UI as 前端 Thread
  participant API as Agent Runtime
  participant LLM as Model Provider

  U->>UI: 输入消息并发送
  UI->>API: 创建 Run / stream
  API->>UI: run.started
  API->>UI: reasoning / model.started
  API->>LLM: 调用模型
  LLM-->>API: streaming delta
  API-->>UI: assistant.message.delta
  API->>UI: assistant.message.completed
  API->>UI: run.completed
```

UI 要求：

- 用户消息立即显示。
- 执行过程显示在本轮 assistant 消息上方，默认折叠。
- 模型输出流式显示。
- 完成后 action bar 可复制、重试。
- 失败时显示明确错误，不展示成功文案。

## 2. 新建任务和历史会话

```mermaid
flowchart TD
  A["点击新建任务"] --> B["创建空 Thread"]
  B --> C["中间显示空态"]
  C --> D["右侧业务面板默认关闭"]

  E["点击历史会话"] --> F["加载 Thread Messages"]
  F --> G["左侧列表保持稳定"]
  G --> H["主对话滚动到最近消息"]
  H --> I["按会话恢复右侧已打开 Artifact 或保持关闭"]
```

约束：

- 点击历史会话不能导致左侧列表消失或 skeleton 长时间残留。
- 会话列表刷新和消息加载分离。
- 当前 Thread 的右侧打开 Tab 可按会话维度保存。

## 3. 模型 Provider 配置

```mermaid
flowchart TD
  A["设置与模型"] --> B["完整设置页面"]
  B --> C["模型"]
  C --> D["新增 Provider"]
  D --> E["填写 OpenAI-compatible base_url / api_key / default_model"]
  E --> F["测试连接"]
  F -->|成功| G["保存"]
  F -->|失败| H["展示失败原因"]
  G --> I["写入审计"]
```

明文查看流程：

```mermaid
flowchart TD
  A["点击显示 API Key"] --> B["权限判断"]
  B -->|允许| C["二次确认"]
  C --> D["短时显示明文"]
  D --> E["自动恢复脱敏"]
  E --> F["写审计"]
  B -->|拒绝| G["提示无权限"]
```

UI 要求：

- API Key 默认脱敏。
- 明文展示不进入本地持久化。
- 查看明文必须产生审计。

## 4. 插件授权和使用

```mermaid
flowchart TD
  A["设置与模型"] --> B["插件"]
  B --> C["按业务类型筛选"]
  C --> D["打开插件详情"]
  D --> E{"是否已授权"}
  E -->|是| F["启用 / 停用 / 使用"]
  E -->|否| G["申请授权"]
  G --> H["进入审批或授权流程"]
  H --> I["授权通过"]
  I --> J["Composer + 菜单出现插件"]
```

Composer 使用流程：

```mermaid
flowchart TD
  A["点击 Composer +"] --> B["展示已授权插件"]
  B --> C["选择问数插件"]
  C --> D["本轮 Run 附带 capability"]
  D --> E["Agent 调用对应工具"]
```

约束：

- 普通用户不看到“安装”概念。
- 未授权内部业务插件不在 Composer 快捷菜单出现。
- 自然语言触发未授权能力时，在主对话展示申请授权卡。

## 5. 业务查询和 Artifact

```mermaid
sequenceDiagram
  participant U as 用户
  participant UI as 主对话
  participant API as Agent Runtime
  participant CON as Connector Runtime
  participant ART as Artifact Store
  participant PANEL as 右侧面板

  U->>UI: 查询 2026 年惠民保总保费
  UI->>API: 创建 Run
  API->>CON: 调用问数 Connector
  CON-->>API: ToolResult + ArtifactRef
  API->>ART: 保存 Artifact
  API-->>UI: 摘要 + Artifact Link Card
  U->>UI: 点击结果卡片
  UI->>PANEL: 打开对应 Artifact Tab
  PANEL->>ART: 加载 Artifact 数据
```

UI 要求：

- 主对话显示摘要和结果卡片。
- 右侧打开结构化结果。
- 第二次调整条件会生成新的结果卡片和新的 Artifact。
- 多个 Artifact 可在右侧多 Tab 切换。

## 6. 权限不足和审批

```mermaid
flowchart TD
  A["用户发起业务操作"] --> B["权限判断"]
  B -->|允许| C["执行 Connector"]
  B -->|超权| D["主对话展示审批摘要卡"]
  D --> E["提交申请"]
  E --> F["设置页审批详情"]
  F --> G{"审批结果"}
  G -->|通过| H["主对话显示继续执行"]
  H --> I["用户点击继续执行"]
  I --> C
  G -->|拒绝| J["用户修改范围重新提交"]
```

约束：

- 自建审批优先。
- 审批通过不自动继续。
- 同一用户、同一内容、同一权限范围、同一动作已审核通过时，可复用审批，但复用必须写审计。

## 7. Artifact 导出 / 复制 / 下载

```mermaid
flowchart TD
  A["点击导出 / 复制 / 下载"] --> B["权限判断"]
  B -->|允许| C["执行操作"]
  C --> D["写审计"]
  B -->|需要审批| E["生成审批申请"]
  E --> F["主对话或设置页提示"]
  B -->|拒绝| G["提示无权限"]
```

规则：

- 所有导出、复制、下载都必须记录。
- 可配置哪些动作需要审批。
- 审计记录包含：用户、会话、Run、Artifact、动作、权限判断、审批复用情况。

## 8. 右侧面板 Tab 管理

```mermaid
flowchart TD
  A["点击 Artifact 卡片"] --> B{"Tab 是否已打开"}
  B -->|是| C["激活已有 Tab"]
  B -->|否| D["打开新 Tab"]
  C --> E["渲染 Artifact"]
  D --> E
  E --> F["hover Tab 显示关闭按钮"]
  F --> G["关闭 Tab"]
  G --> H{"是否还有其他 Tab"}
  H -->|有| I["激活相邻 Tab"]
  H -->|无| J["显示右侧空态"]
```

约束：

- 关闭 Tab 不删除 Artifact。
- 会话切换时，右侧 Tab 状态跟会话区分。
- 如果当前会话无打开 Artifact，右侧默认关闭或显示空态。

