# Phase B 开发前 UI/UX 对齐 Review

版本：2026-07-01  
Review 范围：`phase-b-iam-audit-implementation-plan.md` 对照 `ui-ux-interaction-design.md`  
结论：Phase B 满足后端开发条件，可以开工；不要求新增前端页面。

## 1. Review 结论

Phase B 建立企业账号权限、RBAC/ABAC、数据范围和审计底座。它主要支撑 UI/UX 中的权限判断、审计提示、设置页账号权限和审计记录能力。

Phase B 不直接实现完整设置页 UI，但必须提供后续 UI 所需的权限和审计 API。

## 2. Phase B 与 UI/UX 映射

| UI/UX 要求 | Phase B 支撑点 | 是否满足 |
| --- | --- | --- |
| 用户只看到授权范围内模型、插件、数据 | RBAC + ABAC PermissionService | 满足 |
| 无权限状态展示申请入口 | PermissionDecision 返回 deny/approval_required | 满足 |
| 审批、导出、明文查看均可审计 | AuditService + audit event types | 满足 |
| 设置页账号与权限后续可展示 | Tenant/User/Role/Permission/Department/Group | 满足 |
| 审计记录可检索、导出 | `/api/audit/events`, `/api/audit/export` | 满足 |
| 敏感字段默认脱敏 | Audit masking | 满足 |
| 查看明文写审计 | `audit.plaintext_viewed` | 满足 |

## 3. UI/UX 开发边界

Phase B 不做：

- 设置页账号权限 UI。
- 设置页审计检索 UI。
- SSO 登录界面。
- 组织架构可视化。

Phase B 只需要保证这些未来 UI 能通过 API 获取：

```text
当前用户信息
当前用户角色
当前用户权限摘要
权限判断结果
审计事件列表
审计导出结果
```

## 4. 开发前门槛

- [x] Phase B 详细实施计划已完成。
- [x] UI/UX 交互基线已覆盖账号权限、审计、权限不足状态。
- [x] 无产品决策阻塞。
- [x] 可先开发后端，不依赖前端页面。

## 5. 风险与约束

风险：

- 权限模型如果过早复杂化，会拖慢 Phase B。
- 审计字段如果不统一，会影响后续检索和监管留存。
- 明文查看审计必须从一开始纳入，否则后续补审计不完整。

约束：

- deny 优先。
- 权限变更后下一次权限判断读最新数据。
- Phase B 不引入 Redis。
- 审计导出本身也必须审计。

## 6. 最终判断

```text
Phase B 可以开始后端开发。
```

