# Phase F 开发前 UI/UX 对齐 Review

版本：2026-07-01  
Review 范围：`phase-f-approval-center-implementation-plan.md` 对照 `ui-ux-interaction-design.md`  
结论：Phase F 满足开发条件；审批中心 UI 形态已确认。

## 1. Review 结论

Phase F 的审批中心统一放在设置页面，不进入右侧业务面板。主对话只展示审批摘要卡片，并 deep link 到设置页审批详情。

已确认：

```text
审批中心集成在设置页面
主对话显示审批摘要卡片
审批详情不放右侧业务面板
审批通过后手动继续执行
拒绝后允许修改范围重新提交
第一版按钮：通过 / 拒绝 / 重新提交 / 继续执行
```

## 2. Phase F 与 UI/UX 映射

| UI/UX 要求 | Phase F 支撑点 | 是否满足 |
| --- | --- | --- |
| 审批中心位于设置页 | UI 决策已确认 | 满足 |
| 主对话审批摘要卡片 | ApprovalRequest + status | 满足 |
| 查看详情进入设置页 | Approval detail API | 满足 |
| 审批通过不自动继续 | ApprovalResumeToken | 满足 |
| 用户点击继续执行 | `/resume-run` | 满足 |
| 拒绝后修改范围重提 | `/resubmit` | 满足 |
| 审批事件全部审计 | ApprovalAuditEvent / AuditService | 满足 |

## 3. 前端场景

申请人：

```text
主对话触发超权操作
→ 显示审批摘要卡片
→ 点击查看详情
→ 设置页审批详情
→ 等待审批
→ 审批通过后点击继续执行
```

审批人：

```text
设置页
→ 审批
→ 待我审批
→ 查看申请范围和风险
→ 通过或拒绝
```

## 4. 开发前门槛

- [x] Phase F 详细实施计划已完成。
- [x] 审批中心 UI 形态已确认。
- [x] 不使用右侧业务面板承载审批详情。
- [x] 手动继续执行已确认。
- [x] 无产品决策阻塞。

## 5. 风险与约束

风险：

- 如果审批通过后自动继续，会违背已确认交互。
- 如果审批详情放右侧面板，会污染业务 Artifact 面板定位。

约束：

- 审批通过后只改变状态，不自动 resume。
- resume-run 必须由用户操作触发。
- 审批详情统一在设置页。
- 主对话卡片只承载摘要和跳转。

## 6. 最终判断

```text
Phase F 可以开始开发。
```

