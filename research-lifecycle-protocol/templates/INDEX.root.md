<!--
根级 INDEX.md 骨架（路线总表投影）。
用法：复制到项目根目录 INDEX.md，按实际内容填写。
职责：**跨路线总表** —— 每条路线一行，投影 route-registry.json。
      单条路线的细节不要写在这里，写到 routes/<R>/INDEX.md。
机器真相：.research-idea-pipeline/project/route-registry.json。
-->

# <项目名> — 根 INDEX（路线总表）

> **本文件是 route-registry 的人类投影，不是第二份真相。**
> 每条路线的细节见 `routes/<R>/INDEX.md` 与 `routes/<R>/STATUS.md`。
> 最后更新：`<YYYY-MM-DD>`

---

## 1. 项目概要

| 项 | 内容 |
|---|---|
| **项目主锚点**（**必填，只声明一次**） | theory / performance / phenomenon / benchmark / feasibility / negative |
| 次锚点（可空） | |
| 研究问题 | |
| 路线数 | |
| 目标会议 | CVPR / ICML / NeurIPS / MICCAI |
| 当前重点路线 | |

> ⚠️ **项目主锚点是项目级约束，任何路线都不能靠自称 `core_goal: theory` 来豁免它。**
> 它同时决定 §1.5 的例外是否生效：**只有它为 `theory` / `negative` 时**，
> "第 4 步改为给出可检验推论"才对路线生效（见 `SKILL.md` §0.1、§1.5）。
> **要改它，只能开「锚点变更单」（见 §5）。**

## 2. 路线总表（route-registry 投影）

> 每条路线一行。**字段固定为** `Route | Goal | Status | Thesis | Blocker`。
> 细节链接到该路线的 `STATUS.md`（当前状态）与 `INDEX.md`（材料）。
> **`Status` 只取冻结六值**：`candidate` / `active` / `supporting` /
> `dormant` / `archived` / `merged`。
> **禁止** `almost done` / `maybe` / `low priority` 这类自然语言状态。

| Route | Goal | Status | Thesis | Blocker |
|---|---|---|---|---|
| `routes/A/` | theory | `active` | | |
| `routes/B/` | performance | `supporting` | | |

## 2.1 锚点从属（三层锚点体系）

> 路线锚点与项目主锚点不一致时，**不得只提示冲突就继续**。
> `supporting` 必须可证伪。`orthogonal` 必须公开标注。

| 路线 | `core_goal` | `anchor_role` | `serves` / `serves_evidence` | 路线 README |
|---|---|---|---|---|
| `routes/A/` | theory | primary | — | `routes/A/README.md` |
| `routes/B/` | theory | **supporting** | 服务 performance · 选型依据 → `B003/K1` | `routes/B/README.md` |
| `routes/C/` | theory | **orthogonal** | —（**不参与主锚点成功判据**） | `routes/C/README.md` |

> - **`supporting`：`serves` 与 `serves_evidence` 必填**，且必须可证伪（说出一个会因它而
>   改变的下游决策 + 对主锚点判据的可测影响）。
> - **`orthogonal`：必须写明「不参与主锚点成功判据」**，且该路线**不得进入 R12、
>   不得作为投稿主线**。
> - 冲突时**当轮**二选一：
>   **① 重新定位（agent 可自行做）：** 给出可证伪的 `serves` + `serves_evidence`，
>   并标 `supporting`。答不出就标 `orthogonal` 并公开写明「不参与主锚点成功判据」。
>   **② 换方向（只有用户能授权）：** agent 只能**提请**（记 Warnings + 问用户）。
>   **用户显式同意后**才按 §5 开锚点变更单。
>   **agent 不得自行换方向、换主锚点或开新路线。**
> - **「必须服务」的强制力是「服务，否则降级 + 公开正交」，不是「服务，否则作废」。**
>   被禁止的是**沉默**：既不服务、又不公开标注、还继续当主线推进。

## 3. 跨路线共享资源

| 资源 | 位置 | 说明 |
|---|---|---|
| 参考文献库 | `docs/refs/` | PDF + sidecar + `index.json`（**必须保持同步**：`scripts/refs_index.py --check`） |
| 共享笔记 | `docs/notes/` | 可选，按 `AGENTS.md` |
| 共享理论材料 | `docs/theory/` | 可选，按 `AGENTS.md` |
| 共享 LaTeX | `docs/latex/` | 可选，按 `AGENTS.md` |
| 项目级决策 | `docs/decisions/` | `DEC<NNN>-<slug>.md`，append-only |
| 公用代码 | `src/` 与 `shared/` | 跨路线代码优先放 `src/` |

> ⚠️ **根 `docs/` 不放路线文档** —— 路线文档一律在 `routes/<R>/docs/`。

## 4. 全局 Warnings

> 跨路线的风险、未达饱和的检索、待核实的共同前提。
> **全局「待核实」条数：<N>**（各路线自己的条数记在该路线 `STATUS.md` 的
> Critical uncertainties。**全局合计超过 5** 必须在本轮内收敛：
> 补检索 / 补实验 / 明确降级措辞，见 `project-layout.md` §4.4 与
> `evidence-policy.md`）

| # | 警告 | 类型 | 影响 | 处置 |
|---|---|---|---|---|
| GW1 | | | | |

## 5. 锚点变更单（Anchor Change Order）

> 任何对**项目主锚点**的变更都记在这里（路线锚点的变更记在该路线 `README.md`）。
> **append-only**，不修改历史行。详细规则见 `SKILL.md` §0.2。

| 日期 | 旧方向 → 新方向 | 类型 | 依据 | 受影响产物 |
|---|---|---|---|---|
| | `performance → theory` | **增补** / **替换** | **替换时必须是用户显式指令原话** | **替换时必填**：需重审或标 `superseded` 的文档 ID |

> ⚠️ **两条硬约束：**
> 1. **`类型: 替换` 而没有「受影响产物」清单 = 变更单无效。**
> 2. **`替换` 的依据不是用户原话 = 变更单同样无效。**
>    证据（"主锚点不可达"）只能写进 §4 全局 Warnings 并向用户**提请**，
>    **不能**作为 agent 自行换方向的依据。**只有用户能授权换方向。**

## 6. 路线间关系

> 若路线之间存在依赖 / 互斥 / 可合并，写在这里。

- `routes/A/` 与 `routes/B/`：…

## 7. Recent Research Changes

> 跨路线层面的 state 变更投影。每行一条。

| 日期 | 变更 | 相关路线 |
|---|---|---|
| | | |
