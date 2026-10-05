<!--
根级 INDEX.md 骨架（与每条路线的 INDEX.md 配套）。
用法：复制到项目根目录 INDEX.md，按实际内容填写。
职责：**跨路线**索引 —— 各路线状态汇总 + 全局 TODO / Warnings。
      单条路线的细节不要写在这里，写到 routeX/INDEX.md。
-->

# <项目名> — 根 INDEX（跨路线）

> **一句话状态：** <项目整体处于什么阶段>
> **最后更新：** <YYYY-MM-DD>

---

## 1. 项目概要

| 项 | 内容 |
|---|---|
| 研究问题 | |
| 路线数 | |
| 目标会议 | CVPR / ICML / NeurIPS / MICCAI |
| 当前重点路线 | |

## 2. 路线总表

> 每条路线一行；细节链接到该路线的 `INDEX.md`。

| 路线 | 核心目标（锚点） | 当前阶段 | 最优方案 | 推荐优先级 | 路线 INDEX |
|---|---|---|---|---|---|
| routeA | theory / performance / … | Mode A—E | A003 | 高 / 中 / 低 | `routeA/INDEX.md` |
| routeB | | | | | `routeB/INDEX.md` |

## 3. 跨路线共享资源

| 资源 | 位置 | 说明 |
|---|---|---|
| 参考文献库 | `docs/refs/` | PDF + sidecar + `index.json`（**必须保持同步**：`scripts/refs_index.py --check`） |
| 共享笔记 | `docs/notes/` | 可选，按 `AGENTS.md` |
| 共享 LaTeX | `docs/latex/` | 可选，按 `AGENTS.md` |
| 公用代码 | `shared/` | 按 `AGENTS.md` |

> ⚠️ **根 `docs/` 不放路线文档** —— 路线文档一律在 `routeX/docs/`。

## 4. 全局 TODO

| # | 任务 | 涉及路线 | 优先级 | 状态 |
|---|---|---|---|---|
| GT1 | | | P0 | 待办 |

## 5. 全局 Warnings

> 跨路线的风险、未达饱和的检索、待核实的共同前提。
> **全局「待核实」条数：<N>**（各路线自己的条数记在该路线 `INDEX.md` §7；**全局合计超过 5**
> 必须在本轮内收敛：补检索 / 补实验 / 明确降级措辞，见 `project-layout.md` §4.2 与
> `evidence-policy.md`）

| # | 警告 | 类型 | 影响 | 处置 |
|---|---|---|---|---|
| GW1 | | | | |

## 6. 路线间关系

> 若路线之间存在依赖 / 互斥 / 可合并，写在这里。

- routeA 与 routeB：…

## 7. 变更日志

| 日期 | 变更 | 相关路线 |
|---|---|---|
| | | |
