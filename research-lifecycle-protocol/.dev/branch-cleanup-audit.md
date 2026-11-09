# 旧 RSI 分支清理审计（branch-local）

> 日期：2026-11-10 · 执行分支：`research-lifecycle-protocol/dev` · 依据：任务 §11 + 根 AGENTS.md
> 原则：内容等价优先于提交等价；无法确认等价或存在未合并实质提交 → 保留并报告。

## 审计方法

1. `git merge-base --is-ancestor <tip> main` 判定是否已合并；
2. `git rev-list --count main..<branch>` 数独有提交；
3. 对唯一提交做**内容**核对（是否已被后续重写取代 / 是否已移植）；
4. PR 检查：本机无 `gh`，无法读取 GitHub PR 状态 —— 以"分支 tip 已是 main 祖先且
   无独有提交"为合并证据；此为本次审计的已知限制。

## 逐分支结论

| 分支 | tip | 已合并进 main | 独有提交 | 处理 | 理由 |
|---|---|---|---|---|---|
| `research-idea-pipeline/skill-rsi-dev` | `737f4af`（本地）/ `a8d42f5`（远程） | 远程 tip 已合并 | 本地 1（store 文档 737f4af，未推送） | **删除本地 + 远程** | 737f4af 的 §9.1 store 段落已逐字移植到本分支（内容等价已 diff 验证）；远程 tip 是 main 祖先 |
| `feat/cognitive-insight-engine` | `e3ab5d2` | 是 | 0 | **删除本地 + 远程** | 完全合并（CIE 已进 main） |
| `fix/loop-runtime-correctness` | `62159c8` | 是 | 0 | **删除本地 + 远程** | 完全合并（v1.0.0 已含） |
| `fix/r10-outcome-loop-liveness` | `64f0945` | 是 | 0 | **删除本地 + 远程** | 完全合并（v2.3.2 已含） |
| `release/research-idea-pipeline-v1.0.0` | `973f81a` | 是 | 0 | **删除本地 + 远程** | 发布提交已进 main；tag `research-idea-pipeline/v1.0.0` 保留不动 |
| `feat/preflight-identifiability-loop-guard` | `5555d78` | 是 | 0 | **删除本地** | 无远程分支；完全合并 |
| `feat/zotero-library-ops-fulltext` | `1157d28` | 是 | 0 | **删除本地** | 无远程分支；完全合并 |
| `release/rsi-1.1.0` | `0a1b686` | 是 | 0 | **删除本地** | 发布提交已进 main；worktree `/tmp/rsi-release/wt` 已 prunable |
| `feat/failure-analysis` | `0d1eb80` | **否** | 1（英文 README 重写，涉及三个组件） | **保留** | 存在未合并提交且无法确认内容等价（其改动已被后续 README 重写部分取代，但等价性不可机械证明） |
| `feat/zotero` | `8882be5` | 是 | 0 | **保留** | 任务明确：默认保留，除非确认纯遗留且无独立工作 |

## 不变量

- `main`、`research-lifecycle-protocol/dev`、所有 tag（含历史
  `research-idea-pipeline/v*`）不动。
- 删除分支不删除任何提交对象；合并证明（tip ∈ main 祖先）保证历史可达。
- 失败分析分支与 zotero 分支的保留原因已记录于本文件。

## 已知限制

- 无 `gh`：PR 状态未核对。若某被删分支在 GitHub 上有活跃 PR，删除远程分支会使该 PR
  关闭（其提交仍在 main 历史中，不会丢内容）；建议合并前在 GitHub 上复查一次。
