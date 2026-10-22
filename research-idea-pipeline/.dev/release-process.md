# 发布流程约定（本分支的版本语义）

**决定（2026-10-22，用户裁定）：本开发分支保持"下一个待发布版本"的语义。**

即：`research-idea-pipeline/skill-rsi-dev` 的 `metadata.version` 允许**落后于** `main` 上已发布的版本；
只有当真正要发布时才对齐版本、补 CHANGELOG 与 Release Notes。不在每次发布后回填版本到开发分支。

## 为什么

1. 已发布的版本由 `main` 上的发布提交 + tag 唯一归属；开发分支若复制发布文档，会出现两份"权威"。
2. 版本号在开发分支上代表"正在开发的下一版"，而不是"上一个已发布版"。
3. 闸门已经能区分两种情形（`release_check.step_release_metadata` 与
   `test_release_metadata.py` 使用同一条规则）：
   - tag 是 `main` 的祖先且 `main` 声明了更新版本 → **旧发布线（lag）**，报告并跳过；
   - tag 不是 `main` 的祖先 → **漂移（drift）**，仍然失败。

## 发布时的步骤（沿用第 41 轮已验收的流程）

1. 冻结来源快照：记录开发分支 HEAD（不改动该提交）。
2. 在独立 worktree 中**从 `main` 构造代码合并提交**（引入可分发树，排除 `.dev/`；不使用 fast-forward，
   不保留开发分支祖先）。
3. 验收：快照等价性（排除 `.dev/`）、无 `.dev/` 的独立目录跑闸门、失败语义（PATH/权限/启动失败/账本）。
4. **单独**的发布提交：`metadata.version` 对齐/递增 + CHANGELOG + `docs/releases/v<version>.md`。
5. 带 tag 复跑闸门，然后创建注释 tag `<component>/vX.Y.Z`；旧 tag 不动。

## 相关记录

- `.dev/provenance/record.md`、`.dev/taste/record.md`、`.dev/attribution/record.md`：各轮研发证据。
- 本轮默认预算变更：`templates/preflight-protocol.template.json` `budget_hours: 2 -> 12`；
  pilot 上限（`max_runs 1` / `max_hours 0.1` / `DEFAULT_POLICY.max_pilot_hours 2`）**刻意不变**。
