<!--
路线 INDEX.md 骨架（资产目录 + 时间线）。
用法：复制到 routes/<R>/INDEX.md。
职责：回答「这条路线有哪些材料」。
      只登记资产，不登记当前状态。当前状态看 STATUS.md。
      禁止出现 已证实 / 已证伪 / TODO / Bugs / Warnings 这类当前状态。
      机器可读状态不放这里，放 .research-idea-pipeline/。
-->

# routes/<R> — INDEX

> 本文件是**资产目录**，回答「这条路线有哪些材料」。
> 当前状态见 `STATUS.md`，路线说明见 `README.md`。
> 最后更新：`<YYYY-MM-DD>`

---

## 1. Route Overview

| 项 | 内容 |
|---|---|
| 路线说明 | `README.md` |
| 当前状态 | `STATUS.md` |
| 路线锚点 `core_goal` | theory / performance / phenomenon / benchmark / feasibility / negative（只记主锚点） |
| 次锚点 `core_goal_secondary` | 可空（只写这里，不写进 frontmatter 的 `core_goal`） |
| `anchor_role` | primary / supporting / orthogonal |
| `serves` / `serves_evidence` | `supporting` 必填，且必须可证伪 |
| 目标会议 | CVPR / ICML / NeurIPS / MICCAI |
| 本路线 config | `configs/routes/<R>/` |

> **锚点变更单记在根 `INDEX.md`。** 本路线锚点要与它保持一致。
> `anchor_role: orthogonal` 时，这里必须写明「不参与主锚点成功判据」。
> 本路线不得进入 R12，也不得作为投稿主线。

---

## 2. Key Documents

> 链接相对本文件（即 `routes/<R>/`）书写，格式为 `docs/<文件名>`。
> **本路线的文档都在 `routes/<R>/docs/`，保持扁平。** 根目录 `docs/` 是跨路线共享区。
> **`subtype` 列必填**：枚举内写 `—`，枚举外写原义。
> **`slug` 只取封闭枚举**（详见本 Skill 的 `project-layout.md` §2.1）。
> **枚举外的派生物不要自创 slug**，归到最接近的枚举，原义写 `subtype`。
> 审阅意见为 `docs/<被审ID>-review-r<NN>.md`，**不占新序号**。

| ID | 文件 | 类型 | subtype | 阶段 | 状态 | 说明 |
|---|---|---|---|---|---|---|
| `<路线字母>000` | `docs/<文件名>` | anchor | — | — | frozen | 冻结契约 · v<版本> · hash <前16位> |
| `<路线字母>001` | `docs/<文件名>` | field-map | — | R2 | draft | 领域地图 |
| `<路线字母>002` | `docs/<文件名>` | discovery | — | R3—R6 | draft | 含 I1..In |
| `<路线字母>003` | `docs/<文件名>` | proposal | — | R8 | draft | 贡献 K1..Kn |
| `<路线字母>004` | `docs/<文件名>` | experiment-plan | experiment-cards | R9—R11 | draft | 实验 X1..Xn |
| `<路线字母>005` | `docs/<文件名>` | narrative | — | R12 | draft | 一次调用：I1..In 的 claim graph + 六槽位叙事 |
| `<路线字母>003-review-r01` | `docs/<文件名>` | review | — | R7 / R10 / R13 | draft | 对 `003` 的第 1 轮审阅 |

### 2.1 文档关系图

> **编号是"时间序"，关系图是"关系序"。** 每次产出后手工更新本节。

```text
A001 field-map
 └─▶ A002 discovery ─┬─▶ A003 proposal ─┬─▶ A004 experiment-plan
                     │                  ├─▶ A003-review-r01
                     │                  └─▶ A003-review-r02（接续复核）
                     └─▶ A005 narrative（含 I1 / I3 / I5）
                           └─▶ A005-review-r01
```

### 2.2 Idea 追踪

> 每个 idea 一行。**淘汰的 idea 不得删除**，标"已淘汰"并写理由。
> 这是历史资产登记，不是当前状态。当前状态查 `STATUS.md`。

| Idea | 状态 | 关联文档 | 最佳 preset | 备注 |
|---|---|---|---|---|
| `I1` | 进 population / 已进方案 / **已淘汰** | `<ID>/I1` … | `N2` | |

### 2.3 叙事追踪

> 每个 idea 的 claim 与叙事选型。**门禁未过的叙事**与**被否决的 preset** 都要留痕。

| Idea | 叙事文档 | (O, T, R) | 候选 preset | 最佳 preset | 门禁 G1—G5 | 六维（S/O/SM/ED/G/NC） | 是否推荐 |
|---|---|---|---|---|---|---|---|
| `I1` | `<ID>` | `(Method, hidden-assumption, design-algorithm)` | `N2/N3/N5/N9` | `N2` | 全 pass / `G3 fail` | `5/4/3/4/3/4` | 是 / 否（哪套、为何） |

---

## 3. Experiments

> **XID 是实验的唯一注册号。** 入口指向 `experiments/<R>/<XID>/README.md`。
> 结果摘要指向 `results/<R>/<XID>/summary.md`。
> 这里只登记资产，不写当前状态。

| XID | Question | 状态 | 结果 | 入口 |
|---|---|---|---|---|
| `X021` | | | | `experiments/<R>/X021-<slug>/README.md` |

---

## 4. Decisions

> 正式决策记录。项目级放 `docs/decisions/`，路线级放本路线 `docs/`。
> 命名 `DEC<NNN>-<slug>.md`，**append-only**。

| DEC | 主题 | 结论 | 日期 |
|---|---|---|---|
| `DEC001` | | | |

---

## 5. Reviews

> **复现风险高**、**中位数 <3**、**存在评审分歧**都必须在此可见。

| 被审文档 | 轮次 | 文件 | 中位数 | 复现风险 | 结论 |
|---|---|---|---|---|---|
| `<ID>` | 1 | `<ID>-review-r01.md` | | 低 / 中 / 高 | |
| `<ID>` | 2 | `<ID>-review-r02.md` | | 低 / 中 / 高 | 接续复核 |

---

## 6. Milestones

| 日期 | 里程碑 | 关联文档 |
|---|---|---|
| | | |

---

## 7. Recent Research Changes

> **这是 `history/` 的人类投影，不是变更日志的替代品。**
> 每行一条，来源是 `research-state.json` 的 state 变更。
> 完整变更日志可留在本节下方或 Archive。

| 日期 | state_version | 变更摘要 | 触发阶段 |
|---|---|---|---|
| | `<N>` | | |

---

## 8. Archive

> 已封存、已合并、已被取代的材料。**不删除，只归档。**

| 日期 | 材料 | 归档原因 | 去向 |
|---|---|---|---|
| | | | |
