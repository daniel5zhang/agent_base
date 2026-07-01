# Phase D 开发前 UI/UX 对齐 Review

版本：2026-07-01  
Review 范围：`phase-d-plugin-center-implementation-plan.md` 对照 `ui-ux-interaction-design.md`  
结论：Phase D 满足开发条件；插件中心前端形态已确认。

## 1. Review 结论

Phase D 的插件中心不是右侧业务面板，也不是 Composer 弹窗，而是设置页面中的完整页面。

已确认：

```text
插件中心作为设置页面菜单
插件按业务类型组织
状态作为筛选条件
Web 普通用户不显示“安装”
普通用户操作为申请授权 / 启用 / 停用 / 使用
管理员管理和审计记录第一版展示
```

## 2. Phase D 与 UI/UX 映射

| UI/UX 要求 | Phase D 支撑点 | 是否满足 |
| --- | --- | --- |
| 插件中心位于设置页 | UI 决策已确认 | 满足 |
| 按业务类型组织 | 插件 manifest/plugin_type/business category | 满足 |
| 状态作为筛选条件 | catalog status/user_visible_status | 满足 |
| 普通用户申请授权 | PluginAuthorization | 满足 |
| 普通用户启用/停用/使用 | PluginEnablement | 满足 |
| 管理员管理 | admin package APIs | 满足 |
| 插件审计 | PluginAuditEvent | 满足 |
| Composer `+` 菜单只展示已授权插件 | catalog 过滤 | 满足 |

## 3. 前端场景

普通用户：

```text
打开设置页
→ 插件
→ 选择“问数”
→ 看到问数插件卡片
→ 未授权时点击申请授权
→ 授权通过后启用
→ Composer + 菜单出现问数插件
```

管理员：

```text
打开设置页
→ 插件
→ 管理员管理
→ 查看已发布插件
→ 租户级启用
→ 配置可见范围和权限
→ 查看插件审计
```

## 4. 开发前门槛

- [x] Phase D 详细实施计划已完成。
- [x] 插件中心 UI 形态已确认。
- [x] 用户侧无“安装”概念已确认。
- [x] 管理员管理和审计第一版展示已确认。
- [x] 无产品决策阻塞。

## 5. 风险与约束

风险：

- 后端仍使用 `PluginInstallation` 命名可能和用户侧“无安装”产生概念混淆。
- Catalog 如果暴露未授权内部业务插件给 Composer，会造成误用。

约束：

- 后端内部可以保留安装/启用语义，但前端用户侧文案必须是授权/启用/使用。
- Composer `+` 菜单不展示未授权内部业务插件。
- 未授权自然语言触发时展示申请授权卡片。

## 6. 最终判断

```text
Phase D 可以开始开发。
```

