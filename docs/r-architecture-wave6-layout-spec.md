# Wave 6 规格：项目目录规范（四世界投影）

> **定位：** Wave 1—3 建流程，Wave 4 冻结生成/攻击权，Wave 5 补跨阶段机制。
> **Wave 6 改的是「项目长什么样」** —— 这是唯一一个**面向人**的 Wave。

## 0. 目标与核心原则

**结论：不能过度偏向机器控制平面。研究者才是一手用户。**

若人进入仓库后必须连开几个 JSON 才知道「现在做到哪、为什么这么做、下一步是什么」，这套结构就失败了。

**四个世界必须同时成立并互相投影：**

```text
Research World      ↔  .research-idea-pipeline/routes/<R>/research-state.json   我们目前认为世界是什么样
Human Knowledge     ↔  README / STATUS / INDEX / docs                            人应该怎样理解现在的研究
Experimental World  ↔  experiments / results / logs / checkpoints                实际做过什么、观察到什么
Implementation      ↔  src / scripts / configs                                   怎样把实验运行出来
```

> **机器真相集中，人类视图就近；路线独立清楚，公共资产只存一份；
> 实验可追溯，但不让实验目录淹没科研逻辑。**

---

## 1. 八条目录 invariant（**硬规则，冻结**）

| # | invariant |
|---|---|
| **DI-1** | **`R0`—`R14` 永远不成为目录结构。** 阶段是系统行为，不是文件树。 |
| **DI-2** | **每条战略研究路线只对应一个 route**；hypothesis 不自动建 route（门槛见 §9）。 |
| **DI-3** | **每条 route 只有一个 canonical `research-state.json`。** |
| **DI-4** | **`README` / `STATUS` / `INDEX` 都是人类视图，不是第二份 machine state** —— 它们必须可从 state 投影，不得独立演化出真相。 |
| **DI-5** | **所有正式实验拥有唯一 `XID`**，并贯穿 `config / result / log / checkpoint / state`。 |
| **DI-6** | **代码只维护 canonical implementation，route 不复制代码。** route 的差异用 `configs/routes/<R>/` 表达。 |
| **DI-7** | **`cache` / `runtime` 与 durable research provenance 严格分离。** |
| **DI-8** | **任何机器状态都必须存在一个合理的人类入口，但不要求人直接阅读机器状态。** |

**DI-8 是这一 Wave 的灵魂。** 它同时否掉两个极端：既不让人读 JSON，也不让机器状态无处被理解。

---

## 2. 推荐结构

### 2.1 项目级

```text
MoSA/
├── AGENTS.md
├── README.md                        # 项目是什么
├── INDEX.md                         # 路线总表（人看）
│
├── docs/                            # 项目级人类知识库（跨路线）
│   ├── refs/{papers/,index.json,README.md}
│   ├── notes/                       # 跨路线科研笔记
│   ├── theory/                      # 跨路线理论材料
│   ├── decisions/                   # 项目级重大决策（DEC 记录）
│   ├── dev/
│   └── latex/
│
├── routes/                          # ★ 所有科研路线集中
│   ├── T-transfer/
│   │   ├── README.md                # ★ 路线身份证（低频变更）
│   │   ├── STATUS.md                # ★ 当前状态人类摘要（高频变更）
│   │   ├── INDEX.md                 # ★ 资产目录 + 时间线
│   │   └── docs/                    # 正式文档，保持扁平 + ID
│   │       ├── T001-field-map.md
│   │       ├── T002-discovery.md
│   │       ├── T003-theory.md
│   │       ├── T004-experiment-plan.md
│   │       ├── T005-result-analysis.md
│   │       ├── T006-narrative.md
│   │       └── T004-review-r01.md
│   ├── M-method/                    # 同构
│   └── D-diagnostic/
│
├── src/                             # ★ canonical implementation（唯一）
│   ├── models/  methods/  solvers/  losses/  data/  utils/
├── scripts/{train/,eval/,analysis/,research/}
├── configs/{base/,datasets/,routes/<R>/}
├── dataset/
│
├── experiments/                     # ★ 实验注册表（人可浏览，回答"想做什么"）
│   ├── README.md
│   └── T/X021-identifiability/{README.md,manifest.json,config.yaml}
│
├── results/                         # 回答"发生了什么"（不承担科研状态）
│   └── T/X021/{summary.md,summary.json,metrics.json,tables/,figures/,artifacts/}
├── checkpoints/<R>/<XID>/
├── logs/<R>/<XID>/
├── shared/                          # 极小；见 §12
│
└── .research-idea-pipeline/         # ★ 机器控制平面（**可忽略**）
    ├── project/{contract.json,route-registry.json,constraints.json}
    ├── routes/<R>/{research-state.json,history/,actions/,populations/,
    │                assurance/,repairs/,reviews/,
    │                experiments/<XID>/{preregistration.json,state-delta.json}}
    ├── meta/{operator-stats.json,eig-calibration.json,
    │          recurring-failures.json,scheduler-history.jsonl}
    ├── cache/{literature/,retrieval/,embeddings/}
    └── runtime/{locks,tmp,tool-output}/
```

**与上一版的两个关键变化：**

1. **`route_*` 集中进 `routes/`** —— 否则路线一多，根目录会同时混着代码、route、dataset、result、docs、configs，人扫一眼建立不起结构。
2. **新增 `STATUS.md`** —— 机器有 `research-state.json`，但人需要「30 秒理解现在发生了什么」。

### 2.2 `shared/` 必须极小（否则它是垃圾桶）

**只允许放：无法合理归入 `src/` / `docs/` / `configs/`，但多个 route 都依赖的项目资产。**

大部分东西应该去：跨路线代码 → `src/`；跨路线文档 → `docs/`；跨路线 config → `configs/base/`；跨路线 refs → `docs/refs/`。

**反例（一旦出现就说明划错了）：** `shared/misc.py`、`shared/temp.md`、`shared/old_config.yaml`、`shared/final_v2/`。

---

## 3. 三个文件的职责严格不同

**结论：路线级三个文件回答三个不同问题，更新频率不同，不得互相塞。**

| 文件 | 回答 | 更新频率 | 内容 |
|---|---|---|---|
| `README.md` | 这条路线**是什么**？为什么存在？ | **很低** | 路线身份证（§3.1） |
| `STATUS.md` | **现在做到哪了？下一步是什么？** | **很高** | state 的人类投影（§4） |
| `INDEX.md` | 这条路线**有哪些材料**？ | 中等 | 资产目录 + 时间线（§3.2） |

### 3.1 `README.md` 必须稳定

固定八节：① Research Question ② Why this route exists ③ Relation to project goal
④ Current central thesis ⑤ Scope / non-goals ⑥ Route lineage ⑦ Key resources ⑧ Entry points
（→ STATUS / INDEX / Research State）。

**禁止**把实验进展、今日 TODO、临时 hypothesis 塞进 README。否则几个月后它变成历史垃圾场。

### 3.2 `INDEX.md` 减负：只做资产目录 + 时间线

`已证实 / 已证伪 / TODO / Bugs / Warning` 这类**当前状态**一律交给 `STATUS.md`，不得重复。

推荐节：① Route Overview（→ README / STATUS）② Key Documents（ID/Type/Title/Status）
③ Experiments（XID/Question/Status/Result）④ Decisions ⑤ Reviews ⑥ Milestones ⑦ Archive。

### 3.3 `experiments/` 独立出来，不藏在控制平面

机器 spec 当然可以放 `.research-idea-pipeline/routes/<R>/experiments/`，
但人常问「**X021 到底做的是什么**」—— 不能要求人钻隐藏目录读 JSON。

**`experiments/<R>/<XID>-<slug>/` 只放：** `README.md`（§3.4）+ `manifest.json` + `config.yaml`。
**不放**：checkpoint、巨型 output、raw logs。

### 3.4 每个实验目录必须有人类 README

固定节：Question / Targets（Claim、Hypothesis、Uncertainty）/ Motivation / Setup /
Expected outcomes（O1…）/ Result / Interpretation / Links（config、manifest、results、logs、state delta）。

> 几个月后最不想遇到的问题是「`exp_final_v3_fix2` 到底做了什么」。**用 `XID` 彻底解决。**

---

## 4. `STATUS.md` = `f(research-state.json)`（**投影，不是第二份真相**）

**结论：`State = machine truth`；`STATUS = human current-state view`。
STATUS 必须自动或半自动生成，不得成为新的人工 truth source。**

生成入口：`python scripts/research/render_status.py --route <R>`（读 active claims / active hypotheses /
unresolved uncertainties / active experiments / critical attacks / latest decision）。

固定节：Last updated + State version / Current thesis（含 status）/ Strongest supported findings /
Active hypotheses / Critical uncertainties / Open critical attacks / Active experiments /
Most important negative findings / Next recommended actions / Current decision。

**这是研究者最常打开的页面。**

---

## 5. `XID` 贯穿：整个目录架构最重要的工程 invariant

```text
X021  ⟷  experiments/T/X021-identifiability/
      ⟷  configs/routes/T/X021.yaml
      ⟷  results/T/X021/
      ⟷  logs/T/X021/
      ⟷  checkpoints/T/X021/
      ⟷  .research-idea-pipeline/routes/T/experiments/X021/
```

于是 `rg "X021"` 就把整个 provenance 找出来。

### 5.1 `experiments/` 与 `results/` 必须分开

两者语义不同，且正好对应科研哲学的一对概念：

| 目录 | 回答 | 对应 |
|---|---|---|
| `experiments/` | **想做什么？** | pre-registration |
| `results/` | **发生了什么？** | observation |

**不能混在同一目录。**

### 5.2 `results/` 要有人可读摘要（`summary.md` + `summary.json` 同时存在）

`summary.md` 给人；`summary.json` 给 Agent。人打开 `summary.md` 应直接看到：
Result / Main observation / Unexpected / Limitations / **State impact**（如 `C7: Hypothesized → Supported`、`U4: High → Medium`）。
**不应该先翻 TensorBoard。**

---

## 6. 决策记录：`docs/decisions/DEC<NNN>-<slug>.md`

借软件 ADR 的思想。**命名用 `DEC`，避免与 route ID 字母 `D` 冲突。**

固定节：Context / Evidence / Alternatives / Decision / Consequences / **Revisit condition**。

> 半年后最难回答的是「**我们当初为什么没走另一条路**」。
> **Failure Memory 告诉机器；Decision Record 告诉人。**

---

## 7. 文档命名：从「流程类型」升级成「知识类型」

**结论：旧 slug 绑定已退役的 A—E pipeline，必须换成与 `R0`—`R14` 解耦的封闭枚举。**

| 旧 slug（退役） | 新 slug（冻结） | 用途 |
|---|---|---|
| `literature-survey` | `field-map` | 领域地图 |
| `ideas` | `discovery` | hypothesis / paradigm discovery |
| — | `theory` | 理论分析 |
| — | `evidence` | evidence synthesis |
| `experiment-plan` | `experiment-plan` | 实验规划（保留） |
| — | `result-analysis` | 实验结果分析 |
| — | `decision` | 科研重大决策 |
| `narrative` | `narrative` | 论文叙事（保留） |
| `review` | `review` | 审查（保留） |
| `proposal` | `proposal` | 正式方案（保留） |

**为什么要换：** 同一份 `discovery` 文档可能来自 `R3 + R4 + R5 + R6`。
**pipeline 类型名无法表达这种多阶段汇聚，而知识类型名可以。**

**`route/docs/` 保持扁平** —— 单路线正式文档通常几十份以内，扁平 + ID 最易搜索、最易跨文档引用。

---

## 8. 路由注册表：`.research-idea-pipeline/project/route-registry.json`

**它是路线管理的核心。** 每条约 `{name, path, status, primary, parent, forked_from}`。

**根 `INDEX.md` 投影成：** `Route | Goal | Status | Thesis | Blocker`。

**`status` 用小而稳定的枚举（冻结六值）：**
`candidate` / `active` / `supporting` / `dormant` / `archived` / `merged`。
**禁止** `almost done` / `maybe` / `low priority` / `temporarily paused` 这类自然语言状态 —— 说明写单独字段。

---

## 9. Route fork 门槛（**不得 hypothesis 一多就 fork**）

**满足下列至少两项**才考虑新 route：

| 条件 | 含义 |
|---|---|
| 独立 central question | 已不是原路线的子问题 |
| 独立 claim graph | 核心 claim 明显分叉 |
| 独立 experiment tree | 大部分实验不再共享 |
| 独立论文 thesis | 可单独成稿 |
| 长期资源投入 | 需要持续维护 |

否则保留为 `H<n>`，不开 route。（DI-2 的落地判据。）

---

## 10. Git 版本控制边界

| 版本控制 ✅ | 不版本控制 ❌ |
|---|---|
| `AGENTS.md` / `README.md` / `INDEX.md` / `routes/**` / `docs/**` | `checkpoints/` |
| `src/**` / `scripts/**` / `configs/**` | `logs/` |
| `experiments/**/{README.md,manifest.json,config.yaml}` | `dataset/` |
| `.research-idea-pipeline/**/research-state.json`、`history/*`、`experiments/*/preregistration.json`、`meta/*` | `.research-idea-pipeline/cache/`、`.research-idea-pipeline/runtime/` |

`results/` 视体积决定，但**至少 `summary.md` / `summary.json` / `metrics.json` 应保留**。

---

## 11. 人类导航只有 3 层

```text
项目级:  README.md → INDEX.md
路线级:  routes/<R>/README.md → STATUS.md → INDEX.md
任务级:  experiments/<R>/<XID>/README.md
```

**研究者应该永远不需要想「R8 的文件在哪里」** —— 因为 R8 是系统行为。
他只需要想「我要看路线 T」或「我要看实验 X021」。这就是好的系统设计。

---

## 12. 概念 → 人类入口 → canonical 机器源（**直接写进 `project-layout.md`**）

| 科研概念 | 人类入口 | Canonical machine source |
|---|---|---|
| 项目 | `/README.md` | project contract |
| 路线 | `routes/<R>/README.md` | route registry |
| 当前状态 | `routes/<R>/STATUS.md` | `research-state.json` |
| 文档 | `routes/<R>/docs/` | 文档本身 |
| Claim | STATUS / docs | `claims[]` |
| Hypothesis | STATUS | `hypotheses[]` |
| Experiment | `experiments/<R>/<XID>/README.md` | `experiments[]` + manifest |
| Result | `results/<R>/<XID>/summary.md` | metrics + `evidence[]` |
| Literature | `docs/refs/` | refs index + `literature[]` |
| Failure | STATUS / result docs | `failures[]` |
| Decision | `docs/decisions/` | `decision` + history |
| Narrative | route docs | `narrative_view` |
| Agent telemetry | 通常不展示 | `.research-idea-pipeline/meta/` |

---

## 13. 两条内容过滤原则

### 13.1 机器目录必须「可忽略」

普通研究者只看 `README` / `INDEX` / `routes/` / `experiments/` / `results/` / `src/` 就能正常工作，
**完全不知道 `.research-idea-pipeline/` 内部细节也没关系**。

### 13.2 反过来说：控制平面内部不追求人类漂亮

它追求：`schema 清晰` / `ID 稳定` / `mutation safe` / `validator friendly` / `append-only provenance`。
`research-state.json`、`actions.jsonl`、`operator-stats.json` 完全没问题。
**不要为了"人看起来方便"破坏机器状态一致性** —— 人需要的内容通过 STATUS / INDEX 投影。

### 13.3 失败不得污染正式 docs

一次 CUDA OOM：机器写 `failures[]`（`kind: engineering_failure`）+ `logs/` 有 trace；
**但不生成** `T047-cuda-oom-analysis.md`。

只有**科研价值高的失败**（counterexample / null result / falsification / regime failure）才形成正式 route 文档。

```text
machine memory has everything;
human docs contain knowledge-worthy events.
```

---

## 14. 文档成熟度（**不新增状态，用位置表达**）

| 位置 | 成熟度 |
|---|---|
| `.research-idea-pipeline/runtime/` | `scratch` |
| `routes/<R>/docs/` | `working` / `canonical` |

**`scratch` 不进 `routes/<R>/docs/`。** 若确需在 frontmatter 标注，只用三值
`scratch` / `working` / `canonical`，**不要再增加状态**。

---

## 15. MoSA 现状核对（**实地勘察，2026-10；该项目仍为旧规范，本 Wave 不改它**）

| 现状 | 新规范 | 差距 |
|---|---|---|
| `route_{d,m,t}_<slug>/` 在根目录（3 条） | `routes/<R>-<slug>/` | **需移动** |
| 路线级 `configs/ docs/ logs/ results/ src/` | 仅 `README/STATUS/INDEX/docs/` | **需收敛**（logs→根、results→根、configs→`configs/routes/`） |
| **路线级 `src/` 真的存在**（`route_t/src/{lfbs.py,run_e0_*.py,arxiv_l3_driver.py,selftest_lfbs.py}`） | DI-6：route 不复制代码 | **冲突**：需判定它是「route 专属研究代码」还是「应上收 `src/`」 |
| 根目录 `models/ utils/` + `config.py`、`train_*.py`、`infer_*.py` 裸露在顶层 | `src/{models,utils,…}` + `scripts/train/` | **需移动**（§15 的 P2 项） |
| 文档 slug = `literature-survey / ideas / proposal / experiment-plan / narrative` | §7 知识类型枚举 | **需改名** |
| 文档 ID `T001-…` 扁平 + `-review-rNN` | 保留 | ✅ 已符合 |
| `results/` 下 ~13 个 `*_YYYYMMDD` 目录，**无 XID** | `results/<R>/<XID>/` | **需规范化** |
| `.research-idea-pipeline/route_*/` 内是 `T001-raw/`、`T002-r01/` 等**评审产物**，**无 `research-state.json`** | DI-3 每 route 一个 canonical state | **缺核心文件**；评审产物应归 `reviews/` |
| 无 `experiments/`、`STATUS.md`、`src/`、`routes/` | 新增 | **需新增** |
| `.gitignore` 忽略 `/results/`、`/test/`、`/logs/`、`/checkpoints/` | §10：`results/*/summary.*` 应保留 | **需调整** `.gitignore` |
| 根目录散落 `.ada_tmp.txt`、`.knee_*.log/sh`、`.run_w6_until_done.sh`、`.tmp_pdf*`、`__pycache__`、`test/`（含 `_scratch`、`*_out`） | `.research-idea-pipeline/runtime/` 或 ignore | **需清理** |

---

## 16. 迁移清单（**改动不大，不是推倒重建**）

**本质只增加 `routes/`、`experiments/`、`STATUS.md`，并升级 `.research-idea-pipeline/`。**

| 阶段 | 动作 | 阻塞风险 |
|---|---|---|
| **M1（低风险）** | 新增 `routes/`，把三条 `route_*` 移入并改名为 `<R>-<slug>` | 路径引用需全库扫（Skill 内 + 项目内脚本） |
| **M2（低风险）** | 每 route 新增 `README.md` / `STATUS.md` / `INDEX.md`（由现有 `INDEX.md` 拆分：状态 → STATUS，资产 → INDEX） | 需确认旧 INDEX 内容不丢（**内容丢失检查**） |
| **M3** | `.research-idea-pipeline/route_*` → `routes/<R>/`，并新建 canonical `research-state.json`；旧评审产物归 `reviews/` | 需先跑通 `state_check.py` |
| **M4** | 新增 `experiments/<R>/<XID>/`，把现有 `results/*_YYYYMMDD` 映射成 `XID` | 需人工判定 XID 归属 |
| **M5（P2）** | 根 `models/ utils/ train_*.py infer_*.py config.py` → `src/` + `scripts/` | 影响所有 import，**最后做** |
| **M6** | 文档 slug 改名（`literature-survey`→`field-map`、`ideas`→`discovery`、…）；`.gitignore` 调整；根目录临时文件清理 | 低 |

---

## 17. 验收（实现完成后机械可核）

| # | 项 | 判据 |
|---|---|---|
| 1 | DI-1 | `grep -oE 'R1[0-9]' -r routes/` 无目录名含 R 阶段 |
| 2 | DI-3 | 每条 route 恰好一个 `research-state.json` |
| 3 | DI-4 | `STATUS.md` 可由 `render_status.py` 重新生成且内容一致（幂等） |
| 4 | DI-5 | 每个 XID 在 `configs/` / `results/` / `logs/` / `checkpoints/` / state 中**同时可查到** |
| 5 | DI-6 | 任意 `routes/*/src/` 为空或不存在 |
| 6 | DI-7 | `.research-idea-pipeline/{cache,runtime}` 不在 Git tracked 列表 |
| 7 | DI-8 | 13 行概念映射表（§13）中每个「人类入口」都真实存在 |
| 8 | §7 | `routes/*/docs/` 下无任何退役 slug（`literature-survey` / `ideas`） |

**注意：本 Wave 有一项特有能力要求 —— `render_status.py` 必须幂等。**
否则 `STATUS.md` 就退化成第二份人工真相（违反 DI-4）。这是唯一需要新代码的项。
