# 存量项目接管清单（project-intake）

**结论：在一个已有代码、实验、文献与结论的项目根目录下启动本 Skill 时，执行者必须先按本清单摸清现状，把结果直接落成 R0 的 `contract` 与 R1 的首批 `assumptions[]` / `uncertainties[]` / `failures[]`，不得从零开始，也不得重复询问项目里已经有的信息。**

本文件只规定「怎么摸现状、摸到的东西写进哪个字段」。R0 的契约规则见
[phase-r0-contract.md](phase-r0-contract.md)，八类对象的逐字字段表见
[research-state-policy.md](research-state-policy.md) §3，目录骨架见
[project-layout.md](project-layout.md) §7 —— 本文**不重复定义**它们。

---

## 1. 接管在流程中的位置

**接管是 R0 的前置动作，不是新阶段，也不是锚点变更。**

| 项 | 规定 |
|---|---|
| 触发条件 | 用户所在的**项目根目录已经有代码 / 实验 / 文献 / 结论** |
| 产出落点 | `.research-idea-pipeline/routes/<R>/research-state.json` 的 `contract` + 首批八类对象条目 |
| 是否新阶段 | 否。流程仍走 R0 之后的正常阶段序列，阶段一律用 **R0—R14** |
| 是否改锚点 | 否。见 §4 硬规则 5 |
| 疑问处理 | 见 §5。**一次问完**，且只问「缺失且会实质影响科研判断」的项 |

### 1.1 五步摸底（对齐 [SKILL.md](../SKILL.md) §0 的「启动前置动作」）

1. **先确认项目主锚点**（[SKILL.md](../SKILL.md) §0.1）—— 未声明前不得开工，也**不得**用摸底结果
   替用户「定」锚点。
2. **读根 `AGENTS.md`**（若存在）与根 `README.md` / `INDEX.md`，**并逐个校验其引用的路径是否存在**；
   悬空引用记入根 `INDEX.md` 的 Warnings。
3. **确定路线**（`routes/<R>`），读该路线的 `README.md` / `STATUS.md` / `INDEX.md`
   （身份证、当前状态、材料目录）。
4. **按 §2 的九个维度盘点**，每条都写清三件事：**看什么 → 落到哪个字段 → 缺失时怎么办**。
5. **骨架缺失时先补齐**（目录 + 路线 `README.md` / `STATUS.md` / `INDEX.md` +
   根 `README.md` / `INDEX.md` + `docs/refs/index.json`，
   见 [project-layout.md](project-layout.md) §7），再落盘。

---

## 2. 盘点维度（看什么 → 落到 state 的哪个字段 → 缺失时怎么办）

| # | 维度 | 看什么 | 落到 state 的字段 | 缺失时怎么办 |
|---|---|---|---|---|
| 1 | **README / AGENTS.md / 项目说明** | 根 `AGENTS.md`、根与路线的 `README.md` / `STATUS.md` / `INDEX.md`、「怎么做 / 怎么跑」章节 | `contract.resources`（已有材料、合作者）；`AGENTS.md` 的纪律性条款与 Warnings **不落 state**，落根 `INDEX.md` | 无 `AGENTS.md` 不阻塞；缺 `README.md` / `STATUS.md` / `INDEX.md` ⇒ 按 [project-layout.md](project-layout.md) §7 建；`AGENTS.md` 的悬空引用记根 `INDEX.md` 的 Warnings |
| 2 | **代码结构、训练与推理入口** | 训练入口、推理入口、模型与数据模块、依赖清单；**入口是训练还是推理、冻结还是可训练，必须分清** | `contract.resources`；实现与声称不一致时落 `uncertainties[]`（`question` / `importance` / `uncertainty` / `cheapest_discriminating_test` / `status`） | 无代码 ⇒ 在 `contract.resources` 明写「暂无代码」；入口找不到 ⇒ 落 `uncertainties[]`，并由 `X1`（可行性 / 健全性）实验核实 |
| 3 | **configs / scripts / datasets / checkpoints** | `configs/`、`scripts/`、数据集路径与划分、checkpoint 路径与来源 | `contract.resources`（数据、模型）；`contract.constraints`（数据可得性）；已跑过的实验还要写 `experiments[].data_split` / `seed` / `code_commit` | 路径存在但语义不明 ⇒ **不猜**，落 `uncertainties[]`；划分或种子缺 provenance ⇒ 该实验不当证据用 |
| 4 | **已有实验结果、logs、表格与笔记** | 结果表、训练曲线、`logs/`、散落笔记；数字能否被复算 | `experiments[]`（`metric` / `result` / `interpretation` / `unexpected` / `status`）；达到证据标准者落 `evidence[]`（`kind` / `strength` / `scope` / `epistemic_status` / `source_ref`） | 无 provenance 的结果**只进** `experiments[]`，**不得**升格为 `evidence[]`；基线校准只能记 `stage: X2`，**`X2` 不得承担 claim 判别**（[research-state-policy.md](research-state-policy.md) §3.5） |
| 5 | **项目已有 refs / PDFs / literature notes** | `docs/refs/papers/`、`docs/refs/index.json`、`docs/refs/cache/<source>/`、文献笔记 | `literature[]`（`ref` + `relation`，ID 逐字用 `LIT<n>`）；元数据以 `docs/refs/index.json` 为准 | 索引缺失 ⇒ 跑 `python3 scripts/refs_index.py`（校验用 `--check`）；`needs_verification = true` 的条目**不得**用于创新性声明（[literature-policy.md](literature-policy.md) §7.1） |
| 6 | **已有方法、baseline 与实现状态** | 论文 / 笔记**声称**的方法 vs 代码里**真的实现**的方法；baseline 是否跑通 | 声称与代码不一致 ⇒ `uncertainties[]`；baseline 实测结果 ⇒ `experiments[]`（`stage: X2`）；被默认接受的前提 ⇒ `assumptions[]`（`status` 取 `explicit` / `tacit`） | 只有声称、没有实现 ⇒ 落 `uncertainties[]` 并在 `contract.resources` 标注；**不得**据声称写 `evidence[]` |
| 7 | **已明确的研究目标** | 用户原话、路线 `README.md` 概要、写在文档里的目标与成功判据 | `contract.goal`（**用户原话，不得改写**）、`contract.primary_anchor`（暂定值）、`contract.provisional_anchor_rationale` | 目标只在文档里、用户未确认 ⇒ 复述请其确认（[phase-r0-contract.md](phase-r0-contract.md) §R0.1）；**确认前不得开工** |
| 8 | **GPU、显存、运行环境与实验预算** | `nvidia-smi`、可见设备变量、环境文件、历史训练日志的耗时与峰值显存、用户口述预算 | 实测到的写 `contract.constraints`（算力 / 时间）；**未实测的记 `uncertainties[]` 并标待核实**；环境自检可借 [scripts/env_probe.py](../scripts/env_probe.py)（只测解释器与依赖，**不测显存**） | **不得猜测**。缺就写 `contract.constraints` 或 `uncertainties[]`，标待核实 |
| 9 | **已经验证 / 否证 / 放弃的方向** | `STATUS.md` 的「Strongest supported findings」「Most important negative findings」、废案笔记、废弃分支、被注释掉的实验 | 已否证 / 已放弃 ⇒ `failures[]`（`kind` / `what` / `why` / `referenced_by`）；已明确排除的边界 ⇒ `contract.out_of_scope` | 只有「试过不行」而无原因 ⇒ 先补 `why`；补不出就用 `kind: inconclusive`。**废弃方向不得消失**（[research-state-policy.md](research-state-policy.md) §2 ID 纪律 3） |

> **`failures[].kind` 只准用** [research-state-policy.md](research-state-policy.md) §3.7 的六个值：
> `falsified` / `unsupported` / `inconclusive` / `failed-to-reproduce` / `engineering-failure` /
> `deprioritized`。**不得**新增、翻译或改连字符。

---

## 3. 落盘映射：摸到的东西直接喂给 R0 与 R1

| 摸底产出 | R0 `contract`（六字段逐字） | R1 首批条目 |
|---|---|---|
| 维度 7 的用户原话 | `goal` | — |
| 维度 7 的锚点倾向 | `primary_anchor` + `provisional_anchor_rationale` | R1 的 Anchor Eligibility Test 复核（[claim-first-policy.md](claim-first-policy.md) §6） |
| 维度 8 + 维度 3 的数据/时间/合规限制 | `constraints` | 未实测项 ⇒ `uncertainties[]` |
| 维度 1 / 2 / 3 / 6 的代码、数据、模型、合作者 | `resources` | — |
| 维度 9 的排除边界 | `out_of_scope` | — |
| 维度 6 与维度 2 的「声称 vs 代码」差异 | — | `uncertainties[]` + `assumptions[]` |
| 维度 9 的否证 / 放弃方向 | — | `failures[]` |

- **角色分界：** 六字段逐字定义与 R0 硬规则见 [phase-r0-contract.md](phase-r0-contract.md)；八类对象的
  必填字段与 ID 前缀见 [research-state-policy.md](research-state-policy.md) §2、§3。
- **R0 不产 claim：** 接管同理，**不得**在 R0 期写 `claims[]` 条目（[research-state-policy.md](research-state-policy.md) §3.10）。
- **证据等级措辞：** 摸底得到的说法按 [evidence-policy.md](evidence-policy.md) §1 先定级再写，未达级别一律标待核实。

---

## 4. 硬规则（编号）

1. **已存在的信息不得重复询问用户。** 只对「**缺失**且**会实质影响科研判断**」的信息集中提问，
   且**一次问完**；上限见 §5。
2. **不得从零开始。** 接管产出**直接作为** R0 `contract` 与 R1 首批 `assumptions[]` / `uncertainties[]` /
   `failures[]` 的输入，不允许丢掉已有结论重来一遍。
3. **已否证 / 已放弃的方向必须落 `failures[]`。** `kind` 只能取 §3.7 的六个合法值之一，
   并同时填 `referenced_by`（与 `claims[].known_flaws` 引用**并存**）。
4. **测量与预算必须绑定。** 没有**实测**的 GPU / 显存 / 算力预算**不得猜**；缺就写进
   `contract.constraints` 或 `uncertainties[]`，标注为待核实。
5. **接管不是锚点变更。** 接管阶段只记录 `contract.goal`（用户原话，不得改写）+
   `primary_anchor` **暂定值**；要改主锚点只能走 [SKILL.md](../SKILL.md) §0.2 锚点变更单，
   且**只有用户能授权** —— agent 只能提请或降级。
6. **代码事实与论文声明必须分开记。** 代码里做了什么 ≠ 论文 / 笔记里声称做了什么；
   两者不一致是**重要发现**，要落 `uncertainties[]`，不得被平均数或概括抹平。

---

## 5. 集中提问（一次问完）

**触发条件：** 该信息**缺失**，**且**缺失会实质影响科研判断（锚点、可行性、claim 判别、预算）。

**格式：** 按维度编号集中成一批，每条附「为什么它会改变某个下游决策」。

**上限：一次最多问 5 个关键问题。** 超过 5 个时，按「影响锚点 > 影响可行性 > 影响预算」排序，
只保留前 5 个，其余写成 `uncertainties[]` 并在 `cheapest_discriminating_test` 里给出判别实验 ID
（暂时给不出时用字面量 `TBD`）。

**不得**用提问代替盘点：凡是项目里已经写下的信息（README、`AGENTS.md`、`INDEX.md`、配置、日志），
一律自己读，不得拿去问用户。

---

## 6. 与其它文件的接口

| 需要什么 | 去哪儿看 |
|---|---|
| 阶段划分、锚定点、锚点变更单 | [SKILL.md](../SKILL.md) §0、§0.1、§0.2 |
| R0 契约字段与硬规则 | [phase-r0-contract.md](phase-r0-contract.md) |
| 八类对象、ID 前缀、逐字字段表 | [research-state-policy.md](research-state-policy.md) §2、§3 |
| 目录骨架与「AGENTS.md 优先」 | [project-layout.md](project-layout.md) §0、§7 |
| 文献库索引与元数据字段 | [literature-policy.md](literature-policy.md) §7 |
| 证据等级与允许措辞 | [evidence-policy.md](evidence-policy.md) §1 |
| 锚点资格复核 | [claim-first-policy.md](claim-first-policy.md) §6 |
| 检索边界（按锚点决定查什么） | [phase-r2-r5-field-mapping-retrieval.md](phase-r2-r5-field-mapping-retrieval.md) |
