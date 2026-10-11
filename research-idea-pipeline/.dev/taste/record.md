# Research Taste & Architecture Simplification（Taste 轮）

> 起始 HEAD `95da8313a5d4fb553d6fcd8fcf6a80a469cf3de8`。**只做减法与选择质量**，不新增门禁/状态机/阶段。

## 1. 落地内容

### A. 精简（减法）
- `SKILL.md` §0.4：把历轮累积的**重复行为定义**压成一张「约束 → 一句话 → 权威来源」表；
  **每条规则只保留一个权威来源**（运行时接口或 policy 文档），SKILL 只做指针。
- `references/scheduler-policy.md` §3.1：同样压缩为要点 + 指针，删除与 SKILL 重复的 I2M 细节。
- 清理与新逻辑冲突的旧表述（「方法指纹变化且有新执行证据」→ 指向运行时定义，
  因为 `method_progress` 已允许**同一方法版本**的独立验证构成 Validation Progress）。

### B. 方法合成不再强制 2—3 个
- `synthesis_errors`：**允许一个有理由的单候选**（须写 `single_candidate_justification`，
  说明不存在值得比较的设计分歧）；>3 个拒绝；**科学对照与竞争方法数量分开**（对照仍必须齐全）。
- 新增 `method_sketch_errors`（四问：问题 / Insight / 干预 / 否证条件）作为**探索阶段**轻量产物；
  完整 Design Contract 仍只在**冻结实验前**要求。

### C. 科研品味参与选择（偏好，不是评分）
- 新增 `compare_candidates()`：在**都可执行**的候选之间，按四轴
  `Importance / Insight / Elegance / Evidence` 给出**理由**、最大不确定性，并保留备选。
- `_taste_rank` 是**文档化的偏好启发式**：更简单 → 能说明「为何不更简单」→ 有决定性实验 →
  有动机理由；它**无法判断哪段文字更重要**，因此比较结果返回理由供人或模型权衡。
- **不产生任何分数/权重**（测试断言 `score/weight/total` 不存在）。
- 接入 `transition`/`loop_step`：合成结果带 `taste` 块；硬门禁、EIG÷cost、授权与 1—3 级优先级不变。

### D. 成对偏好验收（Research Taste Evaluation Set）
- 新增 `scripts/test_research_taste.py`：6 组**真实研究场景对照**（大量消融 vs 有机制动机的方法、
  复杂模块小收益 vs 简洁干预、跨域类比 vs 直击核心、性能改善无机制 vs 机制清晰、未超 SOTA 但发现
  失效边界、真实进展 vs 改写解释），断言**方向一致性 + 有理由 + 有不确定性 + 无评分**。

## 2. 验证

| 项 | 结果 |
|---|---|
| 全量单元测试 | **1985 OK / 3 SKIP**（新增 6 项 taste 验收） |
| `insight_to_method` selftest | **47 项 OK**（新增：单候选、偏好非评分、草案四问） |
| 模块 selftest | **7/7 OK** |
| `release_check.py` | **PASS** |

## 3. 诚实的边界（重要）

- **本轮没有做人类偏好验证**。`test_research_taste.py` 的 6 组是**专家撰写的场景夹具**，
  灵感来自架构审查的「更理想的研究者选择」一栏；它们**不是**经人类研究者标注的成对偏好数据，
  也不是 TASTE 式人类评测。因此本轮**不能**声称「科研品味已被证明提高」——只能声称
  「选择逻辑已从代理指标/数量要求，改为**比较性理由 + 保留备选 + 无评分**」。
- 真正的验收需要：10—20 组**真实领域案例**、由有经验研究者做成对偏好判断并记录分歧与不确定性、
  用**成对一致性 / 失败案例 / 跨场景行为变化**衡量，而不是任何单一分数。**这部分尚未进行。**
- `_taste_rank` 无法判断语义重要性；它只是把「是否给出理由」结构化，最终判断仍需模型/研究者。
- L3 科研有效性、真实 GPU/外部调度仍未验证；不伪造证据。

---

## 4. 再次复核（独立复跑 + 自审）

**独立复跑（不引用上轮结论）**：`1985 OK / 3 SKIP`、闸门 `PASS`、7/7 模块 selftest、
HEAD == 远程 == `327afc8`、工作区干净、`main` 未动、13 tags、0 merge。**与上轮声明一致。**

**复核发现 3 处由本身上轮改动引入的缺陷**（均已最小修复）：

| # | 缺陷 | 证据 | 修复 |
|---|---|---|---|
| 1 | **偏好只到 payload，未决定产物**——违反审查点 3（价值判断要与实际选择挂钩）的初衷 | `compare_candidates` 仅被 `synthesize_methods` 调用，`transition` 不消费偏好 | `transition` 现在用偏好选定候选：返回 `i2m.candidate_id`、`preferred_over`（备选保留）、`contract_skeleton`（由被偏好候选构建），动作文案点名该候选 |
| 2 | **Method Sketch 是死代码**——只有测试与 selftest 引用，运行时从不使用 | `grep method_sketch_errors` 仅命中定义与测试 | readiness 可行动但**尚无候选**时，`transition` 返回 `stage="sketch"`（四问 + 缺失字段），探索阶段真正使用轻量产物 |
| 3 | **精简丢了 agent 可见的绑定指令**——「Insight 必须绑定同一候选」在 SKILL/policy/prompts 中 0 处（运行时仍拒绝，属 fail-closed，但指引丢失） | `grep 绑定同一候选` → 0 | SKILL §0.4 表恢复一行「Insight 绑定」（指向 `_binding_errors` I2M60–64）+ 两段式产物一行 |

**复核确认无误的部分**：精简保留的其余运行规则均有权威来源（`scheduler-policy` §3.1 仍含
planned 决策价值、running 不得中断、诊断决策价值）；`_review_credential`/`anchor_gap`/
`attributed` 等上轮修复在复跑中行为一致。

**仍未解决（如实保留）**：无人类成对偏好验证；`_taste_rank` 无法判断语义重要性；
taste 仍是**建议**（设计如此，非门禁）；L3 科研有效性与真实 GPU/外部调度未验证。

---

## 5. 独立复核（309af4d）与 Decision Semantics 收尾

**复核发现**（由用户指出，源码核实）：

| 问题 | 性质 | 处置 |
|---|---|---|
| `indeterminate` 被 `transition` 默认取 `candidates[0]` 并生成契约骨架 | **运行时语义缺陷** | 修复：无明确偏好 → `stage="discriminate"`，不生成胜者契约，保留全部候选并给出判别/并行探索动作；`resolve_artifacts` 不再把 `indeterminate` 偏好文件当作"已比较完成" |
| `record_outcome_feedback` 未核对实验真实性 | **来源可信性缺陷** | 修复：新增 `feedback_source_errors`（**复用既有结果记录**，不加新门禁）：实验必须存在于 canonical state、已完成且有 R9.O/R10 结果凭证、绑定被校准的方法假设、`source` 可追溯、且有与该实验绑定的证据；不满足即 `INVALID`；`--feedback` 必须传 `--state` |
| 校准只进报告、未影响判断 | **文档过度声明** | 澄清：校准当前为 **advisory**（进入比较报告供 Agent 重新考虑），文档已明确标注，不再声称已影响优选 |
| 内部用 `len(good)-len(poor)` 排序 | 启发式代理 | 保留并如实标注为启发式；不新增排序规则 |
| 生产消费者验收缺乏规范 | 流程缺陷 | 已写入根 `AGENTS.md` §22（Producer / Runtime Entry / Consumer / Decision Effect / Persistence-Recovery；纯展示须标注 scope） |

**验证**：2015 OK / 3 SKIP；`release_check.py` PASS；`insight_to_method` selftest 51 项。

**仍未做**：`exploration_balance` 不影响 Scheduler 排序（按约束保持只读）；R10 后自动触发反馈
**刻意未接**（来源验证之前不接，避免产生不可追溯反馈）；真实科研品味评测与 DSH `/loop` 真实任务未开始。
