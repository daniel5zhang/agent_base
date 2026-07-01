# Phase G 开发前 UI/UX 对齐 Review

版本：2026-07-01  
Review 范围：`phase-g-artifact-renderer-implementation-plan.md` 对照 `ui-ux-interaction-design.md`  
结论：Phase G 满足开发条件；右侧业务面板和受控动态 UI 策略已确认。

## 1. Review 结论

Phase G 是 UI/UX 影响最大的阶段，但关键交互已经闭合：

```text
右侧面板只承载业务 Artifact
主对话结果卡片打开右侧 Artifact
多次查询生成独立 Artifact 和独立卡片
Tab 关闭不删除 Artifact
下载、导出、复制都走权限和审计
相同内容审核可复用，但复用也写审计
动态 UI 使用 Artifact schema + renderer_hint 白名单
不执行模型生成的 React/JS
```

## 2. Phase G 与 UI/UX 映射

| UI/UX 要求 | Phase G 支撑点 | 是否满足 |
| --- | --- | --- |
| 主对话业务结果卡片 | Artifact Link Card | 满足 |
| 点击卡片打开右侧面板 | Artifact panel open by artifact_id | 满足 |
| 多 Tab | ArtifactTabs | 满足 |
| Tab 关闭不删除 Artifact | UI state only, backend Artifact remains | 满足 |
| Renderer 白名单 | renderer_hint mapping | 满足 |
| 未注册 renderer fallback | JSONFallback | 满足 |
| 下载/导出/复制权限审计 | ArtifactPermission + DownloadRequest | 满足 |
| 审核复用 | permission grant cache/hash | 满足 |
| AI 动态 UI 安全 | controlled schema, no code execution | 满足 |

## 3. 前端场景

业务查询：

```text
用户发起业务查询
→ Agent 返回摘要
→ 主对话生成结果卡片
→ 用户点击打开结果
→ 右侧业务面板打开 Artifact Tab
→ Renderer 按 renderer_hint 渲染
```

多次查询：

```text
第一次查询 → Artifact A / Card A / Tab A
第二次查询 → Artifact B / Card B / Tab B
关闭 Tab A → Artifact A 仍存在
点击 Card A → Tab A 重新打开
```

导出：

```text
点击导出
→ 权限判断
→ 审批或允许
→ 写审计
→ 相同内容再次导出可复用审批
```

## 4. 开发前门槛

- [x] Phase G 详细实施计划已完成。
- [x] 右侧业务面板定位已确认。
- [x] Artifact 卡片和多 Tab 交互已确认。
- [x] 受控动态 UI 策略已确认。
- [x] 权限审核复用已确认。
- [x] 无产品决策阻塞。

## 5. 风险与约束

风险：

- 如果让 AI 直接生成 UI 代码，会产生安全和审计风险。
- 如果大表格直接进入主对话，会破坏对话体验和性能。
- 如果 Tab 关闭删除 Artifact，会破坏结果可追溯。

约束：

- 右侧面板只展示业务 Artifact。
- 设置、插件、审批不进入右侧面板。
- 未注册 renderer 必须 fallback。
- 不执行 AI 生成的 React/JS。
- 下载、导出、复制必须权限判断和审计。

## 6. 最终判断

```text
Phase G 可以开始开发。
```

