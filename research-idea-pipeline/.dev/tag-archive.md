# research-idea-pipeline 历史 Tag 归档索引（branch-local，不进 main）

基准 main: `7c36fae1aeb1697e8e8a462b592a62043b586bd4`

| Tag | 对象类型 | 指向 Commit | 日期 | 说明 |
|---|---|---|---|---|
| `research-idea-pipeline/v1.2.0` | tag | `2c633beb` | 2026-10-05 | research-idea-pipeline v1.2.0 |
| `research-idea-pipeline/v1.3.0` | tag | `43b643e0` | 2026-10-06 | research-idea-pipeline v1.3.0 |
| `research-idea-pipeline/v1.4.0` | tag | `3d0b1308` | 2026-10-06 | research-idea-pipeline v1.4.0 |
| `research-idea-pipeline/v2.0.0` | tag | `4303b6c5` | 2026-10-06 | research-idea-pipeline v2.0.0 |
| `research-idea-pipeline/v2.1.0` | tag | `e797af15` | 2026-10-07 | research-idea-pipeline v2.1.0 |
| `research-idea-pipeline/v2.1.1` | tag | `fd2b63ea` | 2026-10-07 | 本次发布完善结构等价审计，并修复科研 agent 在方法瓶颈下反复诊断、缺少后续探索的问题。 |
| `research-idea-pipeline/v2.2.0` | tag | `a889ce38` | 2026-10-08 | research-idea-pipeline v2.2.0 |
| `research-idea-pipeline/v2.3.0` | tag | `4baf4585` | 2026-10-09 | research-idea-pipeline v2.3.0 |
| `research-idea-pipeline/v2.3.1` | tag | `ba9b9cbc` | 2026-10-09 | research-idea-pipeline v2.3.1 |
| `research-idea-pipeline/v2.3.2` | tag | `c7acd959` | 2026-10-09 | research-idea-pipeline v2.3.2 |
| `research-idea-pipeline/v2.3.3` | tag | `7e7942d3` | 2026-10-10 | research-idea-pipeline v2.3.3 |

## 备份位置

- `~/.agents/.backups/research-idea-pipeline-v1.0.0-<date>/all-tags.bundle`（全部 tag 的 Git bundle，`git bundle verify` 通过）
- `tag-index.txt` / `for-each-ref.txt`（Tag 类型、Commit SHA、日期、说明）
- `CHANGELOG.md` / `v1.0.0.md`（本次发行文档快照）

## GitHub Release 现状

- 本地克隆无法枚举 GitHub Releases；`gh` CLI 在本机不存在（未安装），本轮**未做任何删除**。
- 需人工在网页端确认哪些 tag 同时存在 Release；清理必须另行批准（方案 A / B，见发布报告）。

## 拟删除清单（**未执行**）

方案 B 下拟删除对象（需你明确批准后才可操作，且远程 Tag 与 Release 需分别处理）：
- `research-idea-pipeline/v1.2.0`
- `research-idea-pipeline/v1.3.0`
- `research-idea-pipeline/v1.4.0`
- `research-idea-pipeline/v2.0.0`
- `research-idea-pipeline/v2.1.0`
- `research-idea-pipeline/v2.1.1`
- `research-idea-pipeline/v2.2.0`
- `research-idea-pipeline/v2.3.0`
- `research-idea-pipeline/v2.3.1`
- `research-idea-pipeline/v2.3.2`
- `research-idea-pipeline/v2.3.3`

风险（方案 B）：历史 tag 引用会失效；已有克隆不会同步删除；CHANGELOG/Release Notes 中指向旧 tag 的链接需改为指向本索引与 bundle。
