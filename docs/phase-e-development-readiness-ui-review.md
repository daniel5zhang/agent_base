# Phase E 开发前 UI/UX 对齐 Review

版本：2026-07-01  
Review 范围：`phase-e-connector-runtime-implementation-plan.md` 对照 `ui-ux-interaction-design.md`  
结论：Phase E 满足后端开发条件；不要求新增前端页面。

## 1. Review 结论

Phase E 是服务端 Connector Runtime 阶段。它支撑 UI/UX 中的工具调用、权限不足、Connector 失败、Artifact 生成等交互，但不直接实现右侧 Artifact Renderer。

## 2. Phase E 与 UI/UX 映射

| UI/UX 要求 | Phase E 支撑点 | 是否满足 |
| --- | --- | --- |
| Agent 可调用业务系统能力 | ConnectorRuntime | 满足 |
| ToolPool 动态过滤 | `tool_pool.py` | 满足 |
| 未授权工具不暴露给模型 | ToolPool + PermissionService | 满足 |
| 权限不足展示申请入口 | `approval_required` result | 满足 |
| Connector 失败可展示错误卡 | ConnectorResult status/error | 满足 |
| 大响应不塞进对话 | `raw_ref` | 满足 |
| 后续 Artifact 面板有结构化数据 | ConnectorResult artifacts | 满足 |

## 3. 前端影响

Phase E 不直接开发前端。

它给前端提供的状态：

```text
completed
failed
partial
blocked
approval_required
```

当前主对话可以先使用已有 ToolFallback / runtime event 展示。正式 Artifact Link Card 和右侧 Renderer 在 Phase G。

## 4. 开发前门槛

- [x] Phase E 详细实施计划已完成。
- [x] UI/UX 已覆盖 Connector 失败、权限不足、Artifact 生成场景。
- [x] 不要求新增前端页面。
- [x] 无产品决策阻塞。

## 5. 风险与约束

风险：

- ConnectorResult 如果结构不稳定，会影响 Phase G Artifact 渲染。
- raw response 如果直接进消息，会造成性能和审计风险。

约束：

- Connector 凭据只保存在服务端。
- ToolPool 每次 run 动态过滤。
- `raw_ref` 只引用原始响应，不把大响应塞进对话。
- 三类 mock connector 都要覆盖。

## 6. 最终判断

```text
Phase E 可以开始后端开发。
```

