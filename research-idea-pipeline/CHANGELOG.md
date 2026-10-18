# Changelog — research-idea-pipeline

本文件记录 Research Idea Pipeline 的正式发行历史。**当前正式稳定版：1.1.0**。
版本序列从 1.0.0 重新建立；此前的 v1.x / v2.x 是同一组件的公开开发迭代记录，原样保留、不改写。

格式：`## <version> — <date>`，条目分为 Added / Changed / Fixed / Security / Docs。
每个版本的权威说明见 `docs/releases/<version>.md`。

## 1.1.0 — 2026-10-18

Skill-RSI 集成版。**代码合并提交**与**发布提交**分离：先以单次提交把开发分支的可分发树
（不含 `.dev/`）并入 `main`，再以本提交升级版本、CHANGELOG 与 Release Notes。

**Added**
- Insight-to-Method Transition：Sketch → Candidate → Preference → Contract → Minimal Test，
  产物落盘于 `<route>/methods/` 并从磁盘恢复；`indeterminate` 不再被默认取第一个候选。
- Research Resume 与 Cold Handoff 的入口分类（`legacy_handoff.resume_decision`）。
- 科研选择比较：四轴（Importance / Insight / Elegance / Evidence）给出 `prefer` / `indeterminate`、
  反对意见、最大不确定性与“复杂度是否必要”，不产生综合评分。
- 只读深度科研总结（11 节 + 统一回报契约），配套通用提示词与 `research_summary.py`。

**Fixed**
- P0 账本完整性：启动失败退款改为在锁内基于重新读取的链写入，并绑定实际消费事件；
  拒绝重复/跨 family/伪造退款。此前锁外追加会破坏哈希链，导致账本永久 `LEDGER_TAMPERED`。
- P1 预算口径统一（`issue()` 与 `run()` 同用 `effective_spend`）；人工例外在预算闸门之前校验，
  仅解除资源限制。
- P1 argv 解析与真实 `subprocess` 一致（裸命令走 PATH，路径形式直接打开），
  不可启动的 `argv[0]` 在执行前被拒绝；启动失败与执行失败语义分离。
- 畸形输入不再以未捕获异常终止闸门（非对象 state、空 argv、损坏账本行）。

**Verification**
- L1（实现有效性）：**已验证** — 2054 tests OK / 3 skipped、9 个模块 selftest、`release_check.py` PASS。
- L2（运行有效性）：**部分验证** — 离线回放、真实文件锁与账本、真实 exec 失败路径；真实 GPU /
  外部 Harness 未验证。
- L3（科研有效性）：**未验证** — 未做真实科研 A/B；本版本不主张任何真实科研收益。

见 [docs/releases/v1.1.0.md](docs/releases/v1.1.0.md)。

## 1.0.0 — 2026-10-10

首个正式稳定版。功能集合与 v2.3.3 之后的 main 一致（含 Loop Runtime Correctness Hotfix 与
R7 Assurance 作者工具），并完成发布元数据统一与 R7 `--output` 路径校验修复。

见 [docs/releases/v1.0.0.md](docs/releases/v1.0.0.md)。

### Fixed
- `evidence_outcome.py assurance-store --output <route>/assurance/outcome/<analysis_id>.json`
  曾因比较最后两段路径组件（`("assurance","outcome")`）而被错误拒绝；现改为与由当前
  State route 推导出的**期望路径**比较：同一文件接受，其他 route、其他文件、路径穿越或
  symlink 越界一律拒绝（原有原子写、文件锁、过期与重复提交规则不变）。

### Added
- 自动化版本一致性检查：`scripts/test_release_metadata.py` 与 `release_check.py` step 17
  （SKILL.md / 两个 README / CHANGELOG / Release Notes 必须一致；Schema 与协议 id 不随发行版本漂移）。

## 发行历史（组件历史迭代，按真实 tag 记录）

| 版本 | Tag | Commit | 日期 | 说明（提交标题） |
|---|---|---|---|---|
| 1.2.0 | `research-idea-pipeline/v1.2.0` | `2c633beb` | 2026-10-05 | chore(repo): 新增根级 .gitignore |
| 1.3.0 | `research-idea-pipeline/v1.3.0` | `43b643e0` | 2026-10-06 | release(research-idea-pipeline): v1.3.0 —— bump metadata.version 1.2.0 |
| 1.4.0 | `research-idea-pipeline/v1.4.0` | `3d0b1308` | 2026-10-06 | release(research-idea-pipeline): v1.4.0 —— bump metadata.version 1.3.0 |
| 2.0.0 | `research-idea-pipeline/v2.0.0` | `4303b6c5` | 2026-10-06 | chore: main 不包含开发文档（docs/ 属开发产物，与 skill 交付无关） |
| 2.1.0 | `research-idea-pipeline/v2.1.0` | `e797af15` | 2026-10-07 | Merge branch 'research-idea-pipeline-dev' into main — research-idea-pi |
| 2.1.1 | `research-idea-pipeline/v2.1.1` | `fd2b63ea` | 2026-10-07 | release(research-idea-pipeline): v2.1.1 |
| 2.2.0 | `research-idea-pipeline/v2.2.0` | `a889ce38` | 2026-10-08 | docs(research-idea-pipeline): 移除已失效的网络不可用自述（SSH/DNS 已恢复） |
| 2.3.0 | `research-idea-pipeline/v2.3.0` | `4baf4585` | 2026-10-09 | Merge feat/cognitive-insight-engine: Cognitive Insight Engine (R0—R14  |
| 2.3.1 | `research-idea-pipeline/v2.3.1` | `ba9b9cbc` | 2026-10-09 | Merge feat/cognitive-insight-engine: Research Preset Library v2.3.1（共同 |
| 2.3.2 | `research-idea-pipeline/v2.3.2` | `c7acd959` | 2026-10-09 | Merge fix/r10-outcome-loop-liveness: R10/R11 完成判定改用正式事务凭证，修复 Autonomou |
| 2.3.3 | `research-idea-pipeline/v2.3.3` | `7e7942d3` | 2026-10-10 | chore(research-idea-pipeline): 版本号 2.3.2 → 2.3.3（运行时正确性修复） |

> 这些历史 Tag 与 Release 仍然有效，本文档不改写其内容。是否清理旧 Tag 由发布决策单独批准；
> 归档索引见本次发布准备记录（`.dev/`，不进入 main）。
