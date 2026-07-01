# Phase A 开发前 UI/UX 对齐 Review

版本：2026-07-01  
Review 范围：`phase-a-agent-runtime-implementation-plan.md` 对照 `ui-ux-interaction-design.md`  
结论：Phase A 满足开发条件，可以开工。

## 1. Review 结论

Phase A 是后端 Agent Runtime 底座阶段，原则上不做前端重构。当前 Phase A 技术任务与 UI/UX 基线一致：

```text
Message 继续服务现有 assistant-ui Thread
TranscriptEvent 为后续完整回放和迁移预留
RuntimeEvent 继续服务执行过程展示
StandardToolResult 为工具过程和结果卡片预留统一结构
RunStateMachine 支撑取消、重试、失败、完成等 UI 状态
UsageMeter 支撑后续设置页模型用量展示
```

## 2. Baseline 测试

已执行：

```bash
cd /Users/daniel/Desktop/code/工作台/workbench-app/frontend-v2/backend
pytest -q
```

结果：

```text
46 passed, 1 warning
```

warning 为 Starlette/TestClient 依赖提示，不阻塞 Phase A。

## 3. Phase A 与 UI/UX 映射

| UI/UX 要求 | Phase A 支撑点 | 是否满足 |
| --- | --- | --- |
| 点击历史会话加载对应 Thread | 继续保留 `Message` 和 `/api/threads/{thread_id}` | 满足 |
| Agent 执行过程显示在对应消息内部 | `RuntimeEvent` + `TranscriptEvent` 记录 reasoning/tool events | 满足 |
| 模型输出支持流式显示 | 保持 `/api/agent/run/stream` 兼容 | 满足 |
| 失败不能假装成功 | `RunStateMachine` + `StandardToolResult.status` | 满足 |
| 工具结果可进入下一轮模型上下文 | `StandardToolResult.model_context` | 满足 |
| 右侧 Artifact 后续可由结果卡片打开 | `ToolArtifactRef` 和 Artifact ref 结构预留 | 满足 |
| 设置页后续展示模型用量 | `UsageMeter` | 满足 |
| 审计和运行证据可追踪 | `RuntimeEvent` 继续保留，TranscriptEvent 增强回放 | 满足 |

## 4. 不应在 Phase A 做的前端工作

Phase A 不做以下 UI：

- 设置完整页面。
- 插件中心。
- 审批中心。
- 右侧 Artifact Renderer。
- 主对话 Artifact Link Card。
- assistant-ui runtime 迁移。

如果实现 Phase A 时遇到前端必须改动，只允许做兼容性修复，并需要说明：

```text
1. 哪个现有接口不兼容
2. 需要改哪个前端文件
3. 用户会看到什么变化
4. 是否可以通过后端兼容避免前端修改
```

## 5. Phase A 开发任务优先级

建议开发顺序保持原计划：

```text
1. TranscriptEvent 和 UsageMeter 数据模型
2. Transcript 查询 API
3. StandardToolResult
4. RunStateMachine
5. Agent Runtime 双写 Message + TranscriptEvent
6. ModelProviderRegistry + UsageMeter 记录
7. Usage 查询 API
8. 后端回归和文档更新
```

## 6. 开工门槛

Phase A 开工前门槛状态：

- [x] 全量平台计划已确认。
- [x] Phase A 详细实施计划已完成。
- [x] UI/UX 交互基线已完成。
- [x] Phase A 与 UI/UX 映射已完成。
- [x] 后端 baseline 测试通过。
- [x] 无产品决策阻塞。

## 7. 风险与执行约束

风险：

- TranscriptEvent 与 Message 双写可能不一致。
- Run 状态直接写入的旧路径可能遗漏。
- 模型 Provider usage schema 可能不稳定。
- SQLite sequence 在未来多并发下可能需要升级。

约束：

- 先写测试，再实现。
- 每个 Task 独立提交。
- 不夹带 Phase B-G 能力。
- 不改前端主交互。
- 后端接口必须兼容当前 assistant-ui 前端。

## 8. 最终判断

```text
Phase A 可以开始开发。
```
