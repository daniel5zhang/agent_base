# Phase C 开发前 UI/UX 对齐 Review

版本：2026-07-01  
Review 范围：`phase-c-model-provider-implementation-plan.md` 对照 `ui-ux-interaction-design.md`  
结论：Phase C 满足开发条件；后端可直接开工，前端按已确认 Codex-style 设置页实现。

## 1. Review 结论

Phase C 的 UI 决策已经闭合：

```text
完整设置页面，类似 Codex
入口为左下角“设置与模型”
普通用户可看授权字段
管理员可管理 Provider
API Key 默认脱敏
有权限可切换明文
查看明文必须审计
第一版只支持 OpenAI-compatible
```

## 2. Phase C 与 UI/UX 映射

| UI/UX 要求 | Phase C 支撑点 | 是否满足 |
| --- | --- | --- |
| 设置页是完整页面 | Phase C UI 决策已确认 | 满足 |
| 模型 Provider 列表 | `GET /api/model-providers` | 满足 |
| 新增/编辑 Provider | Provider CRUD | 满足 |
| API Key 默认脱敏 | CredentialService + masked response | 满足 |
| API Key 明文切换 | 受控 plaintext endpoint + audit | 满足 |
| 连通性测试 | `/api/model-providers/{id}/test` | 满足 |
| 刷新模型列表 | `/models:refresh` | 满足 |
| 普通用户权限受控 | Phase B PermissionService | 满足 |

## 3. 前端场景

设置页“模型”场景：

```text
进入设置页
→ 点击“模型”
→ 查看当前模型
→ 查看 Provider 卡片
→ 管理员点击新增 Provider
→ 输入 base_url / API Key / 默认模型
→ 测试连接
→ 保存
→ 审计记录产生
```

API Key 明文查看：

```text
点击显示
→ 权限检查
→ 二次确认
→ 短时显示明文
→ 自动恢复脱敏
→ 写审计
```

## 4. 开发前门槛

- [x] Phase C 详细实施计划已完成。
- [x] UI/UX 已明确设置页形态。
- [x] API Key 明文查看审计已明确。
- [x] OpenAI-compatible 范围已明确。
- [x] 无产品决策阻塞。

## 5. 风险与约束

风险：

- 明文 key 查看如果直接复用普通 GET，会产生安全风险。
- Provider scope 和用户权限如果不一致，会导致普通用户看到不该看的配置。

约束：

- API Key 不进入前端持久化。
- 明文 key 只通过独立、受权限控制、可审计接口返回。
- 前端不得缓存明文 key。

## 6. 最终判断

```text
Phase C 可以开始开发。
```

