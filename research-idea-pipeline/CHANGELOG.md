# Changelog — research-idea-pipeline

本文件记录 Research Idea Pipeline 的正式发行历史。**当前正式稳定版：1.0.0**。
版本序列从 1.0.0 重新建立；此前的 v1.x / v2.x 是同一组件的公开开发迭代记录，原样保留、不改写。

格式：`## <version> — <date>`，条目分为 Added / Changed / Fixed / Security / Docs。
每个版本的权威说明见 `docs/releases/<version>.md`。

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
