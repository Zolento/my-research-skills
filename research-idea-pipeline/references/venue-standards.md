# 顶会 / 顶刊创新性标准（锚定用）

所有创新性判定**必须**引用本文件中的具体标准条目，不得只写"新颖性不足 / 很新"。

**本文件的职责边界：**

- §1—§4 = 四个会议（CVPR / ICML / NeurIPS / MICCAI）的 **2026 官方口径**。
- §5 = 贡献类型与方法来源标注；§6 = 创新性判定输出模板；§7 = 复现风险判定；§8 = 禁止事项。
- §9 = **顶刊标准**（TMI / JMLR / Nature Machine Intelligence）。
- §10 = **contribution type → evidence contract → venue calibration** 的顺序与映射。

**流程顺序**（谁在什么阶段调用本文件）由 [claim-first-policy.md](claim-first-policy.md) 与
[phase-r12-narrative.md](phase-r12-narrative.md) 规定；本文件只提供**判定标准**，
不自行定义流程。

---

## 来源标注约定（本文件强制）

| 标记 | 含义 | 硬要求 |
|---|---|---|
| **【原文】** | 官方页面英文原句的**直引** | **必须**附该页面 URL |
| **【概括】** | 本 skill 的归纳 | **必须**紧跟 `← <原文编号>`，指明它追溯的官方原文 |
| **【待核实】** | 本轮**未能在官方页面读到逐字依据**（页面不可达 / 付费墙 / 仅见于未公开来源） | **不得**据此下判定；只能作线索登记，且须写明"缺什么" |

> ⚠️ **禁止推断。** 任何 2026 规则条目，若既非 **【原文】** 也非 **【概括】**，一律无效。
> **不得**凭记忆、也不得凭"往年如此"写 2026 的规则。
> 引文保留英文原句，方括号 `[...]` 内为本文件补充的说明；**不得**用"大意是……"替代直引。
> 无法核实的条目**宁可标【待核实】也不得写成确定口径**——这是本仓库的「禁止推断」纪律。

**核实日期：** 2026-10-06（与 `docs/claim-first-spec.md` 同期；该 spec 位于仓库根 `docs/`，
不进安装副本，故此处不写相对链接）。

### 本轮已核实的官方来源清单

| # | 来源（页面标题） | URL |
|---|---|---|
| S1 | ICML 2026 Reviewer Instructions | https://icml.cc/Conferences/2026/ReviewerInstructions |
| S2 | NeurIPS 2026 Reviewer Guidelines | https://neurips.cc/Conferences/2026/ReviewerGuidelines |
| S3 | ICLR 2026 Reviewer Guide | https://iclr.cc/Conferences/2026/ReviewerGuide |
| S4 | CVPR 2026 Reviewer Guidelines | https://cvpr.thecvf.com/Conferences/2026/ReviewerGuidelines |
| S5 | MICCAI 2026 Reviewer Guidelines | https://conferences.miccai.org/2026/en/REVIEWER-GUIDELINES.html |
| S6 | IEEE TMI — Key Criteria for Publication | https://www.embs.org/tmi/key-criteria-for-publication/ |
| S7 | IEEE TMI — Instruction to Reviewers | https://www.embs.org/tmi/instructions-for-reviewers/ |
| S8 | IEEE TMI — Scope | https://www.embs.org/tmi/scope/ |
| S9 | IEEE TMI — Instruction to Authors | https://www.embs.org/tmi/authors-instructions/ |
| S10 | JMLR — Guidelines for JMLR reviewers | https://www.jmlr.org/reviewer-guide.html |
| S11 | JMLR — Author Guide | https://www.jmlr.org/author-info.html |
| S12 | Nature MI — Peer Review | https://www.nature.com/natmachintell/editorial-policies/peer-review |
| S13 | Nature MI — Editorial Process | https://www.nature.com/natmachintell/submission-guidelines/editorial-process |
| S14 | Nature MI — Aims & Scope | https://www.nature.com/natmachintell/aims |
| S15 | Nature MI — Submission Guidelines（索引页） | https://www.nature.com/natmachintell/submission-guidelines |

**已核实但本轮未采用的来源（登记备查）：** TMI [FAQ for Reviewers](https://www.embs.org/tmi/faqs-for-reviewers/)
与 [Peer Review Process](https://www.embs.org/tmi/peer-review-and-decision-process/) 已取到，但其中**不含**
创新性判定口径，故未据其立规则。

**本轮取不到的来源（→ 相关条目标【待核实】）：** TMI 编辑部文章 *Criteria for TMI Papers*
（DOI `10.1109/TMI.2025.3628662`，由 S6 页面链接）—— IEEE Xplore 返回反爬响应（HTTP 202，正文 0 字节），
**未能读到正文**，故 §9.1 中该文可能包含的"四准则"说法一律标【待核实】。

---

## 0. 两角度评价框架（**作用域已限定**）

### 0.1 作用域（先读本节）

**「两角度 + 会议特性」框架仍然有效，但作用域已收窄为两处：**

| 使用位置 | 用法 | 是否派遣子代理 |
|---|---|---|
| **venue calibration 表的会议视角**（`R-CVPR` / `R-ICML` / `R-NeurIPS` / `R-MICCAI`，仅 R12 / R13） | 校准表的每一行**必须**给出 `理论角度` + `应用角度` + `会议特性判定` 三段 | **否**（表，不是子代理） |
| **R12 `D6` venue calibration** | 会议差异以**校准表**形式出现，沿用同一套判据（`理论角度` / `应用角度` / `会议特性判定`） | **否**（不派子代理，只出校准判定） |

> ⚠️ **R12 `D5` 已改用攻击面审稿人**（`R-Novelty` / `R-Causal` / `R-Experimental` /
> `R-Theory` / `R-Generalization` / `R-Utility`），**不再**派遣会议审稿人。
> 因此 **不得**在 R12 的 `D5` 阶段要求"四个会议审稿人的两角度意见"——那与
> [roles.md](roles.md) §1B 冲突。会议维度在 R12 中**只出现一次**，即 `D6`，
> 其结论落到硬门禁 `G5 Venue scope`（见 [scoring-policy.md](scoring-policy.md)）。

**依据：** `docs/claim-first-spec.md` §4（`D5` / `D6` 行）与 §2.9；`SKILL.md` §1.2 与 §3 派遣表。

### 0.2 两个角度（**都要有实质内容**）

| 角度 | 看什么 |
|---|---|
| **理论角度** | 命题 / 假设 / 推导是否成立；形式化是否完整；有无未证明的跳跃；理论贡献的深度与新颖性。**偏应用的工作也要说清理论侧是否成立、缺哪一步形式化。** |
| **应用角度** | 能否落地；实用性与效率；影响面；可验证性；与真实工作流的兼容性。**偏理论的工作也要说清应用侧的可达性与限制。** |

### 0.3 再叠加会议特性判定

这是"突出各自会议特性"的落点，**必须显式引用**对应章节的标准条目：

| 审稿人 | 会议特性判定 |
|---|---|
| R-CVPR | technically sound + contribution 是否同时成立；是否触发"新颖性谬误"（§1） |
| R-ICML | soundness / presentation / significance / originality 是否**分开**评（§2）；是否属于广义原创性 |
| R-NeurIPS | 贡献类型判定；是否**按类型**校准期望；Theory 是否被错罚"缺实验"（§3） |
| R-MICCAI | 方法创新**或**应用创新是否成立；临床影响与方法创新的权衡（§4） |

**输出要求：** 书面意见必须**显式分三段** —— `理论角度` / `应用角度` / `会议特性判定`；
R7 / R10 / R13 的评分维度也按该结构给出（见 [roles.md](roles.md) §1、§5、§6）。
R12 的 `D6` 只输出**校准表**，不派子代理、不产出三段式审稿意见。

> ⚠️ **两个角度都要有实质内容。** 用"理论上没问题、应用上很有价值"这类空话充数，
> 等同于没写。每条判断必须落到**具体的命题、假设、实验或工作流环节**上。

---

## 1. CVPR 2026

**官方来源：** S4 = [CVPR 2026 Reviewer Guidelines](https://cvpr.thecvf.com/Conferences/2026/ReviewerGuidelines)

| # | 类型 | 2026 口径 | 依据（S4 页面小节） |
|---|---|---|---|
| CVPR-1 | **【原文】** | "Each paper that is accepted should be **technically sound** and **make a contribution** to the field. Look for what is good or stimulating in the paper, and what knowledge advance it has made." | Be Mindful |
| CVPR-2 | **【原文】** | "We recommend that you **embrace novel, brave concepts**, even if they have not been tested on many datasets." | Be Mindful |
| CVPR-3 | **【原文】** | "the fact that a proposed method **does not exceed the state-of-the-art** accuracy on an existing benchmark dataset is **not grounds for rejection by itself**. Rather, it is important to weigh both the **novelty and potential impact** of the work alongside the reported performance." | Be Mindful |
| CVPR-4 | **【原文】** | "Claims in a review that the submitted work **"has been done before" MUST be backed up with specific references** and an explanation of how closely they are related." | Be Specific |
| CVPR-5 | **【原文】** | "for a **positive** review, be sure to **summarize what novel aspects are most interesting** in the Strengths section." | Be Specific |
| CVPR-6 | **【原文】** | "simply saying "this is well known" or "this has been common practice in the industry for years" is **not sufficient**: cite specific publications, including books or public disclosures of techniques." | Be Specific |
| CVPR-7 | **【原文】** | "**Do not reject** papers solely because they are **missing citations or comparisons to prior work that has only been published without review** (e.g., arXiv or technical reports)." | Be Specific |
| CVPR-8 | **【原文】** | "Minor flaws that can be easily corrected should **not** be a reason to reject a paper." | Be Mindful |
| CVPR-9 | **【原文】** | 数据集类贡献："it is expected that the dataset will be **made publicly available no later than the camera-ready deadline**, should it be accepted." | Check for Data Contribution |
| CVPR-10 | **【原文】** | "the use of private or otherwise restricted datasets ... **DOES NOT** constitute grounds for rejection. However, **private or otherwise restricted datasets cannot be claimed as contributions in their own right**." | FAQ "A paper claims a dataset as one of its contributions" |
| CVPR-11 | **【原文】** | 代码/复现是**自愿**项："we **highly encourage** authors to **voluntarily** submit their code as part of supplementary material ... Reviewers may **optionally** check this code ... but are **not required** to." | Check for Reproducibility |

> **⚠️ "新颖性谬误"（本 skill 术语）：**
> **【概括】** 不能仅凭"看起来新"给正面，也不能仅凭"有人做过类似的"给负面。
> ← CVPR-2、CVPR-3、CVPR-4、CVPR-7。
> 反向的两种误用都被 2026 官方原文覆盖：**冒进**由 CVPR-1（须 technically sound）约束，
> **误杀**由 CVPR-3 / CVPR-7（SOTA 与 arXiv 引用均不构成单独否决理由）约束。

**2026 新增/修正：** CVPR-3 与 CVPR-7 是**明确的"不得仅凭 X 否决"**条款，
旧版仅笼统写"警惕新颖性谬误"；判定时必须落到 CVPR-3 / CVPR-7 的具体条款上。

---

## 2. ICML 2026

**官方来源：** S1 = [ICML 2026 Reviewer Instructions](https://icml.cc/Conferences/2026/ReviewerInstructions)

### 2.1 四个维度**必须分开评**（2026 明确拆分）

| # | 类型 | 2026 口径 | 依据（S1 页面小节） |
|---|---|---|---|
| ICML-1 | **【原文】** | "Please provide a thorough assessment ... touching on **each of the following dimensions: soundness, presentation, significance, and originality**." | Main Track Reviewer Form Instructions |
| ICML-2 | **【原文】** | 四维**各有独立评分项**，标尺为 "4: excellent / 3: good / 2: fair / 1: poor"；选 "fair" 或 "poor" 时**必须**在 Strengths and Weaknesses 中给出明确理由。 | 同上（Soundness / Presentation / Significance / Originality 四节各自的量表） |
| ICML-3 | **【原文】** | **soundness 与 impact 分离**："**Soundness is distinct from impact.** A paper can be technically sound ... **even if its contributions are modest or incremental**. Conversely, a paper proposing a **high-impact idea must still meet the same bar** for technical soundness. **Reviewers should assess these dimensions separately.**" | Soundness 节 Note |
| ICML-4 | **【原文】** | Soundness 定义："Is the submission **technically sound**? Are **claims well supported**（e.g., by theoretical analysis or experimental results）? ... If the paper includes **theoretical results, are the proofs correct and based on reasonable assumptions**? If ... **empirical results, are the experiments well-designed**?" | Soundness 节 |
| ICML-5 | **【原文】** | Presentation 含**定位义务**："Does the work properly **position itself in the context of prior/concurrent literature** and clearly discuss how it differs?"；并注 "a superbly written paper provides enough information for an expert reader to **reproduce its results**." | Presentation 节 |
| ICML-6 | **【原文】** | Significance："Does the paper address an important or relevant problem? ... **Even if the improvements are modest or domain-specific**, could they **unlock new directions or provide practical utility**?" | Significance 节 |

### 2.2 广义原创性（**2026 明文列举三种来源**）

| # | 类型 | 2026 口径 | 依据（S1 页面小节） |
|---|---|---|---|
| ICML-7 | **【原文】** | "We encourage you to be **open-minded** about the potential strengths and **broad definitions of significance and originality**. For example, **originality may arise from creative combinations of existing ideas, application to a real-world use case, or removing restrictive assumptions from prior theoretical results**." | Strengths and Weaknesses 节 |
| ICML-8 | **【原文】** | **不要求全新方法**："originality **does not necessarily require introducing an entirely new method**. Rather, a work that provides **novel insights by evaluating existing methods**, or demonstrates **improved understanding** is also equally valuable." | Originality 节 |
| ICML-9 | **【原文】** | Originality 的构成问句含："Does this work offer a **novel combination of existing techniques**, and is the **reasoning behind this combination well-articulated**? Are the contributions **clearly distinguished from closely related literature**, and is the novelty well justified?" | Originality 节 |
| ICML-10 | **【原文】** | 论文侧引用义务："Assessments about a paper's **"originality" and "significance" often crucially depend on how the paper compares to prior works**, and thus, such prior works **should be cited and discussed in the paper**."；同时注 "in many cases, it is difficult and often unnecessary to cite all related prior works. If some relevant prior works are missed, then think about whether or not including them would **change the conclusions** of the paper. Some omissions may be considered **minor issues**." | Reviewing Principles 节 |

> **⚠️【待核实】旧「ICML 断言纪律」不再成立：**
> 旧版 §2 写"原创性被否定时**必须**提供精确先前工作引用"。
> **本轮在 S1 上未读到该逐字要求**——S1 只规定论文侧应引用（ICML-10），并未规定**审稿人**否定原创性时
> 必须给出精确引用（该要求见 S4/CVPR-4 与 S5/MICCAI-8，属于 CVPR 与 MICCAI 的明文规则）。
> **缺什么：** ICML 2026 审稿人表格/AC 指南中是否有对应条款（本轮未取到该页面）。
> 在此之前，ICML 视角**不得**以"审稿人必须给精确引用"为判定依据；改引 ICML-9（须说明贡献与
> 邻近文献的区别如何被论证）。

**2026 新增/修正：** 四维**拆分评分**（ICML-1/2）与 **soundness ≠ impact**（ICML-3）是本轮新增口径；
广义原创性三来源（ICML-7）由"创造**性**组合"更正为官方原文 "**creative combinations** of existing ideas"。

---

## 3. NeurIPS 2026

**官方来源：** S2 = [NeurIPS 2026 Reviewer Guidelines](https://neurips.cc/Conferences/2026/ReviewerGuidelines)

### 3.1 按 contribution type 校准期望（2026 的核心机制）

| # | 类型 | 2026 口径 | 依据（S2 页面小节） |
|---|---|---|---|
| NIPS-1 | **【原文】** | 五类："**General** ... **Theory** ... **Use-Inspired** ... **Concept & Feasibility** ... **Negative Results**"，"Authors should select the Contribution Type that best fits their submission." | Reviewing Guidelines for Different Contribution Types |
| NIPS-2 | **【原文】** | **同一表格、不同解读**："The review form is the same for all Contribution Types, but **the way that reviewing criteria should be interpreted differ across Types**. Reviewers should **assess a submission according to the Contribution Type selected by the authors**. It is **not possible** for Contribution Type to be changed after submission, either by the authors or by the reviewers." | 同上 |
| NIPS-3 | **【原文】** | **C&F 与 Negative Results 的"significance 与 originality 门槛都高"**："Concept & Feasibility: The main contribution is a highly novel, high potential reward idea with scope beyond what can be validated in a single paper. (**The significance and originality bar for these contributions is high.**)"；"Negative Results: ... (**The significance and originality bar for these contributions is high.**)" | 同上 |

### 3.2 Theory：**不要求** SOTA 实验

| # | 类型 | 2026 口径 | 依据（S2 页面小节） |
|---|---|---|---|
| NIPS-4 | **【原文】** | **"Empirical validation is not necessary.** Theoretical contributions may stand on their own and the purpose of designing new algorithms in this context **need not be to outperform state-of-the-art** applied models or methods. **Empirical evaluation is not a necessary component, and a theory paper shouldn't be penalized for lacking experiments.** If empirical results are included, their function can be to further study formalized insights, **not necessarily to compete with state-of-the-art** applied models or the largest datasets." | Theory Reviewing Guidelines → Quality |
| NIPS-5 | **【原文】** | 理论 Quality 两支柱："**Mathematical rigor and correctness**. The primary criterion is the **correctness of the claims**. Proofs, lemmas, and the overall logical flow must be mathematically sound."；"**Appropriateness of assumptions** ... should be weighed against the **novelty of the result** and standard norms of the existing literature." | Theory → Quality |
| NIPS-6 | **【原文】** | 理论 Clarity 含"**Clear scoping of the contribution**：The paper must clearly signpost its **type of theoretical contribution** early on and the distinction between **novel contributions and prior work** must be clear." | Theory → Clarity |
| NIPS-7 | **【原文】** | 理论 Significance 的两种落点："**Novel Abstractions and Formulations** ... Good abstractions provide the community with a **new vocabulary**"；"**Progress on Established Problems** ... surface a new angle of study on a well-established problem that has faced bottlenecks, or **solve an open problem**?" | Theory → Significance |
| NIPS-8 | **【原文】** | 理论 Originality 的形态："It might be a **fundamentally new proof technique**, a **novel synthesis of tools from other disciplines**（e.g., statistical physics, pure mathematics）, or a **completely new way to parameterize or define a problem**." | Theory → Originality |

### 3.3 Use-Inspired / Negative Results

| # | 类型 | 2026 口径 | 依据（S2 页面小节） |
|---|---|---|---|
| NIPS-9 | **【原文】** | Use-Inspired："**Is the design matched to the use case?** ... methods may need to accommodate the structure of the data, incorporate physical constraints, or be evaluated using metrics such as **interpretability or robustness**, depending on the use case." | Use-Inspired Reviewing Guidelines |
| NIPS-10 | **【原文】** | Use-Inspired 数据："**Expect "non-standard" datasets.** ... evaluated on **real-world datasets that fall outside common ML benchmarks**. Such datasets **should be encouraged** if they are justified in relation to the use case." | Use-Inspired Reviewing Guidelines |
| NIPS-11 | **【原文】** | C&F 举证："the submission **must be technically sound and claims must be rigorously grounded** through some combination of **empirical, analytical, and conceptual arguments**. ... the scope of the ideas presented **may be bigger than can be validated within a single paper, but must be strongly supported nonetheless**." | Concept and Feasibility Reviewing Guidelines |
| NIPS-12 | **【原文】** | Negative Results 不是"实验没成"："it is important that the negative result **not be simply an empirical observation that some experiment did not turn out as expected or hoped**. It is important that a negative result be **grounded in deeper analysis**, whether through a combination of conceptually-informed conjectures and careful experimentation, through **rigorous proofs**, or some combination." | Negative Results Reviewing Guidelines |
| NIPS-13 | **【原文】** | Negative Results 的 originality 判据 = **反直觉**："The negative result must be **surprising or unexpected** in some way — that is, it should **run counter to a popularly held understanding**."；并给出反例（"A linear classifier cannot separate a nonlinear decision boundary" 严谨、清晰、重要，但**不 original**，因为读者要么已知、要么不会意外）。 | Negative Results Reviewing Guidelines |
| NIPS-14 | **【原文】** | Negative Results 不要求解决方案："A Negative Results paper **need not identify a path to mitigate** the negative finding; that can be left to future work." | Negative Results Reviewing Guidelines |
| NIPS-15 | **【原文】** | General 类 Originality 的认定含："originality **does not necessarily require introducing an entirely new method**. Rather, a work that provides novel insights by **evaluating existing methods**, or demonstrates **improved efficiency, fairness, etc.** is also equally valuable." | General Reviewing Guidelines → Originality |

**2026 新增/修正：**

1. 旧版写"**Concept & Feasibility 类**的重要性与原创性门槛更高"——2026 原文是
   **C&F 与 Negative Results 两类都高**（NIPS-3），须逐类引用，不得只提 C&F。
2. 旧版写"区分**五种**贡献类型"但把 Theory 也算作一类贡献类型的"首要"；
   2026 的机制是 **按作者选定的类型校准解读**（NIPS-2），不是由审稿人重新分类。

---

## 4. MICCAI 2026

**官方来源：** S5 = [MICCAI 2026 Reviewer Guidelines](https://conferences.miccai.org/2026/en/REVIEWER-GUIDELINES.html)

### 4.1 创新 = 方法创新**或**应用创新

| # | 类型 | 2026 口径 | 依据（S5 页面小节） |
|---|---|---|---|
| MICCAI-1 | **【原文】** | 总判据："consider **whether the proposed methods are innovative or whether the application is innovative**." | 2. Specific Reviewing Notes → General review considerations |
| MICCAI-2 | **【原文】** | **临床影响可补偿较低方法创新**："Is the paper of **sufficiently high clinical impact to outweigh a lower degree of methodological innovation**?" | 1. What Makes a Good Review → 推荐节 |
| MICCAI-3 | **【原文】** | **贡献形态多元**："**a novel algorithm is only one of many ways to contribute.** Other examples include (but are not limited to) a **novel interventional system**, an **application of existing methods to a new problem**, and **new insights into existing methods**." | 1. What Makes a Good Review → 推荐节 |
| MICCAI-4 | **【原文】** | 好贡献的定义："A paper would make a good contribution if you think that **others in the community would want to know it**."；接收率参考 "MICCAI typically accepts around **30%** of submissions." | 1. What Makes a Good Review → 推荐节 |
| MICCAI-5 | **【原文】** | 增量警示："Does the work make a **substantial contribution** to the field or society, or is it **mostly incremental over previous work**?" | 2. → General review considerations |
| MICCAI-6 | **【原文】** | 强度清单含多种创新形态："A reviewer should write about a **novel formulation**, **demonstration of clinical feasibility**, an **original way to use data**, a **novel application**, a **particularly strong evaluation**, or anything else that is a strong aspect of this work." | 1. → strengths 节 |

### 4.2 数据 / 验证 / 统计（**2026 逐句清单**）

| # | 类型 | 2026 口径 | 依据（S5 页面小节） |
|---|---|---|---|
| MICCAI-7 | **【原文】** | "Do the authors clearly explain **data collection, processing, and division methods**?" | 2. → General review considerations |
| MICCAI-8 | **【原文】** | 数据代表性："Do the data **accurately reflect the range and diversity of potential patients and disease manifestations**?" | 同上 |
| MICCAI-9 | **【原文】** | 标签质量："Are the data **labels** (if applicable) of **sufficient quality** to support the claimed performance or analysis of the algorithms?" | 同上 |
| MICCAI-10 | **【原文】** | 不确定度："Do the authors report a **sufficient number and type of performance measures** ...? Are performance measures reported with **measures of uncertainty or confidence**（e.g., error bars, standard deviations, etc.）?" | 同上 |
| MICCAI-11 | **【原文】** | 统计检验："Have the authors performed a **proper statistical analysis** of results（e.g. **p-values**）?" | 同上 |
| MICCAI-12 | **【原文】** | 临床语境："Are the results and comparison with prior art **placed in the context of a clinical application** in terms of significance and contribution?" | 同上 |
| MICCAI-13 | **【原文】** | 局限讨论："Do the authors **discuss limitations** and other implications of their methods and directions for future research?" | 同上 |
| MICCAI-14 | **【原文】** | 复现性："**Comment on the reproducibility of the paper.** Where possible, we encourage authors to **use open data** or to make their **data and code available** for open access ... we understand that ... some researchers are unable to release their proprietary dataset and code; therefore, a **clear and detailed description of the algorithm, its parameters, and the dataset is highly valuable**." | 1. → reproducibility 节 |
| MICCAI-15 | **【原文】** | 非新颖须给引用："if a method is **not novel, provide citations to prior work**."；"if the method is not novel, **explain why and provide a reference to prior work**." | 1. → weaknesses 节 / Please avoid 节 |

### 4.3 分类别考量

| # | 类型 | 2026 口径 | 依据（S5 页面小节） |
|---|---|---|---|
| MICCAI-16 | **【原文】** | CAI 类可接受**单例可行性**："Demonstration of clinical feasibility, **even on a single subject/animal/phantom**." | 2. → CAI-based papers |
| MICCAI-17 | **【原文】** | Clinical Translation 专场："keep a **high standard for methodology development while enabling a strong focus on the clinical application**"，考量"**Barriers and challenges in translation**, and how to overcome these"、"**Robustness and reliability evaluation** of algorithms"、"**usability**"、"**User interaction, adoption and acceptance**"、"**Performance monitoring and clinical deployment**"。 | 2. → Clinical Translation papers |
| MICCAI-18 | **【原文】** | 评审范围纪律："**Asking the authors to substantially expand their paper**" 属应避免行为——"The paper should be **evaluated as submitted**." | 1. → Please avoid 节 |

> **⚠️【待核实】"按受试者分组的划分"：**
> 旧版 §4 写"**必须**声明划分是按病人 / 受试者分组（防泄漏）"。
> **本轮在 S5 上只读到 MICCAI-7 的 "division methods" 一般性问句**，未读到"按受试者 / 按病人分组"
> 或 "leakage" 的逐字要求（已扫描 `subject` / `split` / `patient` / `leak` / `group` 等词）。
> **缺什么：** MICCAI 2026 是否在 Call for Papers / 作者指南（本轮未取到）中逐字要求 subject-level split。
> **处置：【概括】** 该要求作为本 skill 的**方法论纪律**保留（← MICCAI-7），
> 但**不得**表述为"MICCAI 2026 官方逐字要求"；须与 MICCAI-7 的原文表述一并出现。

**2026 新增/修正：**

1. MICCAI-2 与 MICCAI-3 是**临床影响 ↔ 方法创新的显式权衡条款**：高临床影响**可以**补偿较低方法创新，
   且"novel algorithm 只是众多贡献形态之一"。判定时必须引用这两条，不得用"方法不够新"单向否决。
2. MICCAI-16 给出**可行性优先**的例外：CAI 类接受单例 / 动物 / 体模的临床可行性演示。
3. MICCAI-18 是**评审范围纪律**：不得要求作者大幅扩充论文（会议无机制保证改动落实）。

---

## 5. 贡献类型标注规范

任何阶段输出的贡献点都必须标注类型。两种标注体系二选一，**全篇保持一致**。

**按 NeurIPS 五类**（口径以 §3.1 的 S2 原文为准；分类由**作者**选择，审稿人按该类校准解读）：

| 类型 | 含义 | 典型证据 | 门槛（S2 原文） |
|---|---|---|---|
| General | 通用贡献 | 方法 + 大规模经验验证 | 一般 |
| Theory | 理论贡献 | 定理、证明、界 | 一般；**不要求实验 / SOTA**（NIPS-4） |
| Use-Inspired | 应用驱动 | 面向实际 use case 的结果 | 设计须匹配 use case（NIPS-9） |
| Concept & Feasibility | 概念与可行性 | 概念验证、可行性证据 | **significance 与 originality 双高**（NIPS-3） |
| Negative Results | 负结果 | 严谨的否证与失效分析 | **significance 与 originality 双高**（NIPS-3），且须反直觉（NIPS-13） |

**按通用四类：** 方法 / 理论 / 实证 / 问题定义。

### 5.1 方法来源标注（原创 / 部分原创 / 迁移）

**贡献类型说明「这是什么贡献」；方法来源说明「这个方法是哪来的」。两者都必须标。**

| 标注 | 含义 | 判据 | 对创新性的影响 |
|---|---|---|---|
| **原创** | 核心机制由本工作提出 | 指出最接近先前工作 + **机制层面**的差异 | 正常计入创新性 |
| **部分原创** | 核心机制部分来自既有工作，但有关键改造 / 新组合 / 新性质 | 写明**改了哪一条** + 改造带来的新性质 | 创新性取决于改造是否触及新结构性质 |
| **迁移** | 把其他领域 / 任务的既有方法搬来，机制不变 | 写明**来源领域 + 迁移合法性依据** | **迁移本身不算增量**；只有证明"迁移带来新性质"才构成贡献 |

**硬性要求：**

- **不得留空、不得模糊。** "受 X 启发""结合了 A 与 B"都不是标注。
- **迁移不得包装成原创。** 这属于夸大（违反 R12 包装纪律）。
- ICML 视角下，`迁移` 唯一可能的出口是 §2.2 的 "**application to a real-world use case**" 或
  "**removing restrictive assumptions**"（ICML-7）——那需要证明迁移的**合法性**（假设如何修改）
  与新领域中的**新性质**，而不是"拿来就用"。
- 迁移合法性分级见 [narrative-patterns.md](narrative-patterns.md) §4 的 `Transfer Legitimacy Argument`
  （`L1` / `L2` / `L3`）。
- R7 / R10 / R13 见 §7：`迁移` 且无新性质 → **复现风险高**。

---

## 6. 创新性判定输出模板

```markdown
### 创新性判定

**目标会议：** CVPR / ICML / NeurIPS / MICCAI
**锚定标准：** <引用本文档中的具体条目编号，如 CVPR-3 / ICML-7 / NIPS-3 / MICCAI-2>

| 视角 | 判定 | 引用依据 | 原文标准 |
|---|---|---|---|
| R-CVPR | 高 / 中 / 低 | [作者, 会议/年份] | "断言'已有类似工作'必须附具体引用"（CVPR-4） |
| R-ICML | 高 / 中 / 低 | …… | "originality may arise from creative combinations ..."（ICML-7） |
| R-NeurIPS | 高 / 中 / 低 | …… | "The significance and originality bar ... is high"（NIPS-3） |
| R-MICCAI | 高 / 中 / 低 / **不适用** | …… | "clinical impact to outweigh a lower degree of methodological innovation"（MICCAI-2） |

> **R-MICCAI 行可填"不适用"：** 当工作无临床 / 医学影像属性时，填"不适用"并在
> `clinical_relevance` / `validation_rigor` 两个维度记 `N/A`（**不进中位数向量**）。
> 此时 R-MICCAI 仍以通用审稿视角参与（原创性、方法正确性）。

**最接近先前工作（S-Lit）：** ……
**重叠度判定：** 足够 / 边缘 / 不足
**S-Lit 核实结果：** 已核实 / **待核实**
**创新性边界重界定：** ……
```

> **引用纪律：** "原文标准"列**必须**写条目编号（`CVPR-n` / `ICML-n` / `NIPS-n` / `MICCAI-n` /
> `TMI-n` / `JMLR-n` / `NMI-n`），**不得**只写会议名或只写中文概括。
> 若引用的是 **【待核实】** 条目，该行判定必须同时写明"依据待核实"。

---

## 7. 复现风险判定标准（Anti-Reproduction，R7 / R10 / R13 强制）

> **目的：避免把一个"做得很扎实的复现"当成贡献送审。** 技术正确 ≠ 可发表。

### 7.1 六项检查

| # | 检查项 | 判定 |
|---|---|---|
| 1 | 是否存在**可一对一对应**的已有方案（问题、机制、结论三层都对应）？ | 有 / 部分 / 无 |
| 2 | 本方案相对它的增量是**设计改变**，还是仅**实现优化/超参调整**？ | 设计改变 / 实现优化 / 无实质增量 |
| 3 | 增量是否触及**新的结构性质或理论条件**？ | 是 / 否 |
| 4 | 若把已有方案原样重跑，本方案的核心声称是否仍成立？ | 是 → 风险高 / 否 |
| 5 | 是否只是把已有方法**换数据集 / 换 backbone**？ | 是 → 风险高 / 否 |
| 6 | 最接近工作的作者会认为这是**独立贡献**还是**自己的后续工作**？ | 独立 / 后续 / 复现 |

> ⚠️ **「换数据集 / 换 backbone」与「换问题定义 / 评估口径」要分开判：**
> 第 5 项的换数据集 / 换 backbone 指**机制与结论不变、只替换数据或骨干网络** → 风险高；
> 若改的是**问题定义 / 评估口径**（新的问题形式化或新的评估协议），**不自动等于风险高**，
> 必须**单独论证**该形式化 / 协议本身是否构成设计层面的贡献（见 §7.3 MICCAI 一条）。

### 7.2 等级与后果

| 等级 | 判据 | 后果 |
|---|---|---|
| **低** | 设计层面增量，触及新的结构性质或理论条件 | 可继续 |
| **中** | 增量偏实现层，但问题设定或评估口径不同 | 必须补强贡献声称或改变定位 |
| **高** | 可一对一对应且无实质设计增量 | **列为致命风险；总体判定不得为"高"** |

### 7.3 与各顶会标准的对应

- **CVPR：** 警惕"新颖性谬误"——既要防止把复现当新工作，也要防止仅因"有人做过类似的"
  就否定（CVPR-3 / CVPR-4 / CVPR-7）；断言复现**必须附具体引用**（CVPR-4）。
- **ICML：** 复现通常不构成"广义原创性"；但若增量属于 ICML-7 的
  **removing restrictive assumptions** 或 **application to a real-world use case**，
  可重新定位为贡献（需明确写出被移除的假设）。
- **NeurIPS：** 若确实是复现，可考虑转为 **Negative Results** 或
  **Concept & Feasibility** 定位；但这两类的 significance 与 originality **双高**（NIPS-3），
  且 Negative Results 另须**反直觉**（NIPS-13），不能当作"降级发表"。
- **MICCAI：** 只**换数据集或换中心**属于 MICCAI 明确的增量警示（MICCAI-5）；
  但若增量是 **novel formulation** 或**新的验证协议**（见 MICCAI-6 的
  "particularly strong evaluation" / "original way to use data"），可重新定位为贡献。
  复现类工作在 MICCAI 同样要按 MICCAI-7 / MICCAI-14 说明数据处理与复现细节。
- **顶刊（§9）：** TMI 明确"incremental gains are not sufficient"（TMI-5）；
  JMLR 明确列出去要"insufficient deltas"（JMLR-6）。

### 7.4 措辞门禁

- 复现判定必须达到 **L3 穷尽检索**并附负检索记录；否则只能写"据本次检索未见"，
  且**不得**断言"复现风险低"。
- **证据等级与措辞统一见 [evidence-policy.md](evidence-policy.md)**，本节不另立措辞表。
- 禁止把"我们的实现比原论文高 0.3%"当作独立贡献。

---

## 8. 禁止事项

- ❌ 不引用任何具体标准条目就给出创新性判定。
- ❌ 引用 **【待核实】** 条目却把它当作已核实的官方规则使用。
- ❌ 贡献点不标注类型。
- ❌ 未经 S-Lit 核实即使用"首次提出 / first to"。
- ❌ 以"没人做过"作为新颖性的唯一论据（需说明**为什么之前没人做**，见 R8 §R8.2.6 第 4 节）。
- ❌ R7 / R10 / R13 结论卡片缺少**复现风险等级**。
- ❌ 用 **venue 直接选 preset**（见 §10.0 的顺序硬规则）。
- ❌ 用 `clinical significance` 冒充 `methodological innovation`（见 §9.4）。

---

## 9. 顶刊标准（TMI / JMLR / Nature Machine Intelligence）

> **适用时机：** 当 R12 `D6` 或 R7 / R10 / R13 的目标 venue 是**期刊**（而非 §1—§4 的四个会议）时，
> 用本节做校准。本轮顶刊**不作为审稿角色**登记（不新增 `R-TMI` / `R-JMLR` / `R-NMI`），
> 只在 `D6` 校准表中出现（见 §10.2），与 ICLR 的处理一致（§10.3）。

### 9.1 IEEE TMI（Transactions on Medical Imaging）

**官方来源：** S6 = [Key Criteria for Publication](https://www.embs.org/tmi/key-criteria-for-publication/) ·
S7 = [Instruction to Reviewers](https://www.embs.org/tmi/instructions-for-reviewers/) ·
S8 = [Scope](https://www.embs.org/tmi/scope/) ·
S9 = [Instruction to Authors](https://www.embs.org/tmi/authors-instructions/)

| # | 类型 | 口径 | 依据 |
|---|---|---|---|
| TMI-1 | **【原文】** | Regular paper 四条准则："**Novelty**: The manuscript must introduce **new science or a novel approach to existing science**. **Quality**: The content must be **technically accurate** and the manuscript well-written. **Appropriateness**: The paper should be **self-contained and within the scope** of TMI. **Impact**: The work must **significantly impact the field or represent more than an incremental advancement**." | S6 Key Criteria for Publication → Regular Paper |
| TMI-2 | **【原文】** | Challenge paper 四条："**Overall Impact** ... **Evaluation Clarity**（含 how gold standards are established）... **Method Novelty** ... **Discussion Depth**"，并要求 "Publicly accessible links to **authors' code** to support **reproducible research**." | S6 → Challenge Paper |
| TMI-3 | **【原文】** | Review paper 四条（受邀）："**Comprehensive Coverage** ... **Critical Analysis** ... **Identify Gaps** ... **High-Quality Citations**"。 | S6 → Review Paper |
| TMI-4 | **【原文】** | **范围纪律（关键）**："Papers describing **important applications based on medically adopted and/or established methods without significant innovation in methodology** will be **directed to other journals**."；且 "Strong application papers that describe **novel methods** are particularly encouraged." | S8 Scope |
| TMI-5 | **【原文】** | **增量不足即拒**："our desk rejection rate is around **70%** and less than **10%** of all submissions are finally published ... we publish (and expect) **major methodological innovations and breakthroughs, i.e., incremental gains are not sufficient for TMI**."；并重申 "TMI does **not** publish papers that describe applications based on medically adopted and/or established methods and **lack significant innovation in methodology**." | S9 Instruction to Authors |
| TMI-6 | **【原文】** | 评分与意见须一致："We use both the **evaluation ratings** and review comments ... please make sure the **review comments are consistent with the ratings**. For example, if you choose **Fair for Originality** or **Excellent for Impact**, please elaborate on why."（即评审表含 **Originality** 与 **Impact** 等评分项。） | S7 Instruction to Reviewers → 4.1 |
| TMI-7 | **【原文】** | 推荐档位："**Reject/Resubmit with Major Revision** ... **Reject/Submit to Another Journal** ... **REJECT** ... **Accept with Minor Revision**"；且 major revision 只允许一次。 | S7 → 3. Assess and Recommend |
| TMI-8 | **【原文】** | 复现：Challenge 论文**必须**提供公开代码链接（同 TMI-2）；S7 的复现要求以 Challenge 口径为准，Regular 论文未见逐字强制。 | S7 → 1.1 / S6 |

> **⚠️【待核实】"Significance—Innovation—Evaluation—Reproducibility" 四准则：**
> 本轮任务清单与旧版设想把 TMI 标准概括为这四条，但**本轮在 S6 / S7 / S8 / S9 四个官方页面上
> 均未读到该四元组**（已逐页扫描 `significance` / `innovation` / `evaluation` / `reproducibility`）。
> S6 页面链接的编辑部文章 *Criteria for TMI Papers*（DOI `10.1109/TMI.2025.3628662`）
> **可能**含该四元组，但 IEEE Xplore 返回反爬响应（HTTP 202、正文 0 字节），**本轮未取到正文**。
> **处置：【原文】口径以 TMI-1 的四条（Novelty / Quality / Appropriateness / Impact）为准**；
> 该四元组标 **【待核实】**，**不得**作为判定依据。
> **缺什么：** *Criteria for TMI Papers* 全文（需 IEEE Xplore 订阅或机构访问）。

### 9.2 JMLR（Journal of Machine Learning Research）

**官方来源：** S10 = [Guidelines for JMLR reviewers](https://www.jmlr.org/reviewer-guide.html) ·
S11 = [JMLR Author Guide](https://www.jmlr.org/author-info.html)

| # | 类型 | 口径 | 依据 |
|---|---|---|---|
| JMLR-1 | **【原文】** | 审稿人应触及的要点："**Goals** ... **Description**（adequately detailed for others to replicate the work）... **Evaluation** ... **Significance** ... **Related Work and Discussion** ... **Clarity** ... **Recommendation**"。 | S10 Guidelines for JMLR reviewers |
| JMLR-2 | **【原文】** | **claim 必须有支撑（核心）**："**Are all claims clearly articulated and supported either by empirical experiments or theoretical analyses?**" | S10 → Evaluation |
| JMLR-3 | **【原文】** | **"学到了什么"（核心）**："Papers should report on **what was learned in doing the work, rather than merely on what was done**."；并 "it should be clear **how the work advances the current state of understanding and why the advance matters**." | S11 → Content |
| JMLR-4 | **【原文】** | 显著性判据："Does the paper constitute a **significant, technically correct contribution** to the field that is appropriate for JMLR? Is it **sufficiently different from prior published work**（by the author or others）to merit a new publication?" | S10 → Significance |
| JMLR-5 | **【原文】** | 理论工作也要讲实用性："Papers describing **theoretical results should also discuss their practical utility**."；"Papers describing systems should clearly describe the contributions or the principles underlying the system." | S11 → Content / S10 → Description |
| JMLR-6 | **【原文】** | **delta 判据（对"会议版扩展"极重要）**："Examples of (possibly) acceptable 'deltas' ... include: **new theoretical results, entirely new application domains, significant new insights and/or analyses**. Examples of **insufficient deltas** include: **adding proofs that were omitted from a conference paper; minor variations or extensions of previous experiments; adding extra background material or references**." | S11 → Originality |
| JMLR-7 | **【原文】** | 范围：JMLR "**does not publish applications** of machine learning to other domains"，"favors papers of interest to a **broader machine learning audience** and may deem a paper unsuitable if ... its audience **too narrow**."；"does **not allow simultaneous submission** to conferences or other journals." | S11 → 范围段 |
| JMLR-8 | **【原文】** | 推荐档位："**accept, conditional accept, reject with encouragement to revise and resubmit, and reject**"；conditional accept 须给出**可逐条核对的修改清单**。 | S10 → Recommendation |
| JMLR-9 | **【原文】** | 篇幅与复现："any experiments reported should be **reproducible**"；长文（>35 页）审稿更慢，>50 页须在 cover letter 说明理由，可能被 desk reject。 | S11 → Content / 篇幅段 |

### 9.3 Nature Machine Intelligence

**官方来源：** S12 = [Peer Review](https://www.nature.com/natmachintell/editorial-policies/peer-review) ·
S13 = [Editorial Process](https://www.nature.com/natmachintell/submission-guidelines/editorial-process) ·
S14 = [Aims & Scope](https://www.nature.com/natmachintell/aims)

| # | 类型 | 口径 | 依据 |
|---|---|---|---|
| NMI-1 | **【原文】** | **接收总标准（核心）**："In general, to be acceptable, a paper should represent an **advance in understanding likely to influence thinking in the field**, with **strong evidence for their conclusions**. There should be a **discernible reason why the work deserves the visibility of publication in a Nature Portfolio journal rather than the best of the specialist journals**." | S12 → Criteria for publication |
| NMI-2 | **【原文】** | 编辑初筛四条："Editors decide whether to send a manuscript for peer review based on **the degree to which it advances our understanding of the field**, the **soundness of conclusions**, **the extent to which the evidence presented — including appropriate data and analyses — supports these conclusions**, and the **wide relevance of these conclusions to the journal's readership**." | S13 → 编辑流程节 |
| NMI-3 | **【原文】** | 审稿人须回答的问题："**Key results** ... **Validity**: Does the manuscript have **flaws which should prohibit its publication**? ... **Originality and significance**: If the conclusions are not original, please provide **relevant references** ... do you feel that the results ... are of **immediate interest to many people in your own discipline, and/or to people from several disciplines**? ... **Data & methodology** ... Is the reporting of data and methodology sufficiently detailed and transparent to **enable reproducing the results**? ... **Appropriate use of statistics and treatment of uncertainties** ..." | S12 → 审稿人问题清单 |
| NMI-4 | **【原文】** | 退稿理由："**Reject outright**, typically on grounds of **specialist interest, lack of novelty, insufficient conceptual advance or major technical and/or interpretational problems**"；或在评审后 "**insufficient support for the conclusions** or a **reassessment of the level of interest or advance**"。 | S12 → 决定档位 / S13 → Editorial decision |
| NMI-5 | **【原文】** | 期刊定位："publishes **high-quality original research** and reviews ... We also explore and discuss the **significant impact** that these fields have on **other scientific disciplines as well as many aspects of society and industry**." | S14 Aims & Scope |
| NMI-6 | **【原文】** | "Originality and significance" 中要求：若结论不原创，审稿人**须给出相关引用**。 | S12 → 审稿人问题清单 |

> **说明：** NMI-1 的 "**likely to influence thinking in the field**" 即"是否改变领域思考方式"的
> 官方原文落点，**已核实**。NMI-2 / NMI-4 表明"**strong evidence**"在官方口径中具体化为
> "证据是否足以支撑结论"（insufficient support for the conclusions 是退稿理由之一）。

### 9.4 硬规则：`clinical significance ≠ methodological innovation`

> **两者不得互相冒充。** 这是本节的**判定纪律**，不是可选建议。

| 方向 | 禁止的做法 | 官方依据 |
|---|---|---|
| **临床意义 → 冒充方法创新** | 把"临床问题重要 / 数据来自医院 / 医生认为有用"当作方法学创新 | TMI-4 与 TMI-5 明文：**重要应用但方法无显著创新 → 转投他刊**（"without significant innovation in methodology will be directed to other journals"）；TMI-5 "incremental gains are not sufficient for TMI" |
| **方法创新 → 冒充临床意义** | 把"指标提升 / 模块替换 / 更大 backbone"当作临床收益 | MICCAI-2 要求**显式权衡**"clinical impact ... outweigh a lower degree of methodological innovation"；MICCAI-12 要求结果放在**临床语境**中；MICCAI-8/9/10/11 要求数据代表性、标签质量、不确定度与统计检验 |
| **正确写法** | 分别给出**两条独立判定**：① 方法学创新是什么（对照 TMI-1 Novelty / MICCAI-1 方法创新）；② 临床意义是什么（对照 MICCAI-2 / MICCAI-12 / TMI-1 Impact）。**任一条不成立就不写该条**，不得用另一条顶上 | 上述各条 |

**注意（容易误读）：** MICCAI-2 **允许**高临床影响补偿较低方法创新——这是**会议**口径；
TMI-4 / TMI-5 则**要求**方法学创新，临床重要性**不能**替代方法论创新。**两个口径不同，不得互相套用**：
MICCAI 的补偿规则**不得**用于 TMI，TMI 的方法学硬门槛**不得**用于 MICCAI 的 CAI / Clinical Translation 类。

---

## 10. contribution type → evidence contract → venue calibration

### 10.0 顺序硬规则（禁止倒序）

**逻辑依赖顺序（不是 R12 的时间顺序）：**

```
① Contribution type        ② Evidence contract            ③ Venue calibration
   (O, T, R) 三轴             该类型最少需要哪几类证据        把已定的 claim + 证据契约
   取自 claim-first-policy      ← 本文件 §10.1                放到某 venue 的标准下判定
   §5；由 D2 登记                                             ← 本文件 §10.2，落 G5

R12 步骤：  D2 登记类型  →  D0 台账 / D1 claim graph / D4 的 S5  →  D6 校准
```

> **说明：** 上表是**逻辑依赖顺序**，**不是** R12 的时间顺序。
> 在 R12 的实际时间轴上，`D0`（证据台账）与 `D1`（claim graph）**先于** `D2`（类型登记），
> 因为类型要由 claim graph 推出来。**被禁止的是倒序**——先定 venue、再回填 claim 与 preset；
> **不是**这三者在时间轴上的先后。硬约束只有一条：
> **`D6` 校准必须等到 ① 与 ② 都已确定之后才能做。**

| 步 | 输入 | 产物 | 权威文件 |
|---|---|---|---|
| ① Contribution type | claim graph | `(O, T, R)` + 贡献类型 | [claim-first-policy.md](claim-first-policy.md) §5 |
| ② Evidence contract | ① + 证据台账 | 每条 claim 的**最低证据要求** | 本文件 §10.1 + [claim-first-policy.md](claim-first-policy.md) §2—§4 |
| ③ Venue calibration | ① + ② + 全部叙事 | 会议适配判定 → 硬门禁 `G5 Venue scope` | 本文件 §10.2 + [scoring-policy.md](scoring-policy.md) |

**明令禁止：**

> ❌ **不得保留「venue 直接选 preset」的顺序。** 先选会议、再据会议挑叙事 preset，
> 属于**倒序**——它会让 claim 与证据反向迁就会议口味，直接违反 claim-first 总纲。
> ❌ **不得**为了匹配某会议而**改写 claim 或补造证据**。venue 只用于**判定与校准**，
> 不用于**反向生成 claim**。
> ❌ **不得**把 `(O, T, R)` 当作 venue 的替代品：三轴是**科学分类**（这是什么研究），
> venue 是**接收标准**（谁认这个贡献）。二者**不可互相推导**。
> ❌ **不得**跳过 ② 直接做 ③：没有 evidence contract 的 venue calibration 无法判定
> `G1 Claim grounding`，等于给"看起来适合该会议"的空壳放行。

**preset 的位置：** preset（`N1—N10`）在**顺序之后**才选，依据是
`(O, T, R)` + anchor eligibility（见 [narrative-patterns.md](narrative-patterns.md) §2）。
preset **不是** venue 的函数。

### 10.1 Contribution type → evidence contract

**约定：** 下表"最低证据契约"列是本 skill 的**规定**（【概括】），其可追溯依据见"依据"列——
要么指向会议/期刊官方原文（`§n` 编号），要么指向 [claim-first-policy.md](claim-first-policy.md) 的内部约定。
`epistemic_status` 五值见 [claim-first-policy.md](claim-first-policy.md) §2：只有
`Observed` / `Supported` 可进 Evidence Contract（`S5`）。

| # | Contribution type（`O` / `T`） | 最低证据契约（本 skill 规定） | 依据 |
|---|---|---|---|
| EC-1 | `O=Method`，`T=hidden-assumption` / `shift-failure` | ① 机制层面与最近工作的 delta；② 公平 baseline + 消融证明**该机制**（而非其他改动）带来收益；③ 至少一个**失败条件**的界定 | CVPR-1 / ICML-3 / ICML-4 / MICCAI-5 |
| EC-2 | `O=Theory`，`R=prove` / `characterize` | ① 定理 + 完整证明；② **假设的必要性 / 紧性**讨论；③ 清晰标注贡献类型（理论） | NIPS-4 / NIPS-5 / NIPS-6 / NIPS-8 / JMLR-2 / JMLR-5 |
| EC-3 | `O=Phenomenon`，`T=unexplained-phenomenon` | ① 控制变量后现象**稳定存在**的证据；② 证伪性实验（能推翻该现象的条件）；③ 现象与解释分离 | ICML-4 / ICML-8 / JMLR-3 |
| EC-4 | `O=Evaluation`，`T=evaluation-mismatch` | ① 原 protocol **无法识别**目标能力 `C` 的证据；② 新协议的设计理由与效度讨论；③ 协议可复现 | CVPR-9 / CVPR-11 / MICCAI-6 / JMLR-1 |
| EC-5 | `O=Resource-System` | ① 可用性 / 可获取性证明（公开链接或明确许可说明）；② 规模与覆盖范围；③ 与现有资源的差异 | CVPR-9 / CVPR-10 / TMI-2 / NIPS-10 |
| EC-6 | `O=Problem`，`R=reformulate` | ① 新形式化的**动机**；② 它比旧形式化多解释 / 多预测了什么；③ 边界（在哪些条件下不适用，`S6` 必填） | ICML-9 / MICCAI-1 / MICCAI-6 / NMI-4 |
| EC-7 | `T=infeasibility`（Negative Results） | ① 严谨否证（分析或证明），**不得**只是"实验没成"；② **反直觉性**证据（对照流行理解）；③ 不需要给出解决方案 | NIPS-12 / NIPS-13 / NIPS-14 |
| EC-8 | 临床 / Use-inspired（论文形态，**不是** `O` 枚举值） | ① use case 的**真实约束**及其如何改变设计；② 数据代表性 + 标签质量；③ 不确定度与统计检验；④ 临床意义**单独**判定（见 §9.4） | NIPS-9 / NIPS-10 / MICCAI-2 / MICCAI-7—MICCAI-12 |
| EC-9 | 概念与可行性（C&F） | ① claim 由 empirical / analytical / conceptual 论证**共同**支撑；② 影响范围可超出单篇验证但**仍须强支撑**；③ 门槛高 | NIPS-3 / NIPS-11 |
| EC-10 | `O=Method` 且 `R=reformulate`（跨域迁移） | ① "为什么 B 在 A 中合法"；② 迁移带来的**新性质**；③ 合法性等级 `L1` / `L2` / `L3` 与声称的贡献等级**匹配** | ICML-7 / [narrative-patterns.md](narrative-patterns.md) §4（定义所在） |

> ⚠️ **证据不足时的唯一合法动作：** 在 `S5 Evidence Contract` 中写 `Ci ← [待补]`，
> 并在 `D9` 输出「缺失证据清单」+「最小必要实验 / 定理」。
> **不得**用措辞掩盖缺失证据，也**不得**换一个 venue 来绕开证据要求。

### 10.2 Venue calibration（**在 ①② 之后**做）

**校准问句（对每个候选 venue 逐条回答，落 `G5 Venue scope`）：**

| Venue | 校准问句（本 skill 规定） | 2026 官方依据 | 不匹配的信号 |
|---|---|---|---|
| **CVPR** | 是否 **technically sound 且 make a contribution** 同时成立？novelty 与 potential impact 是否与报告的 performance 一起被权衡？ | CVPR-1 / CVPR-3 | 只堆 SOTA 数字而无 contribution；或只喊"brave"而不 technically sound |
| **ICML** | 四维（soundness / presentation / significance / originality）是否**分开**成立？若走广义原创性，落在 ICML-7 的哪一支？ | ICML-1 / ICML-3 / ICML-7 | 用 impact 掩盖 soundness 缺陷；或把"迁移"当原创（§5.1） |
| **NeurIPS** | 作者选的 **Contribution Type** 是哪一类？该类的最低门槛是否满足（Theory 不罚缺实验；C&F / Negative Results 双高）？ | NIPS-1 / NIPS-2 / NIPS-3 / NIPS-4 | 用 General 的标准去罚 Theory；或把 Negative Results 当"降级发表" |
| **MICCAI** | **方法创新或应用创新**是否至少一条成立？临床影响与方法创新是否已**分别**判定（§9.4）？ | MICCAI-1 / MICCAI-2 / MICCAI-3 | 用"方法不够新"单向否决应用创新；或把指标提升当临床收益 |
| **TMI**（期刊） | 是否有**超越增量**的方法学创新？是否落在 TMI 范围内（重要应用但方法无创新 → 转投他刊）？ | TMI-1 / TMI-4 / TMI-5 | 临床重要性替代方法学创新（§9.4） |
| **JMLR**（期刊） | 是否满足"claims supported by empirical or theoretical analyses"？**学到了什么**（而非做了什么）？相对会议版的 delta 是否**充分**？ | JMLR-2 / JMLR-3 / JMLR-6 | delta 只是补证明 / 加背景 / 微调实验（JMLR-6 明确列 insufficient） |
| **Nature MI**（期刊） | 是否是"**advance in understanding likely to influence thinking in the field**"且 **strong evidence**？ | NMI-1 / NMI-2 / NMI-4 | 只是 specialist interest；或结论支撑不足（NMI-4 退稿理由） |
| **ICLR**（**仅作校准参考**，见 §10.3） | 四个关键问题（problem / motivation / claim support / new knowledge）是否都能答上？是否误把"SOTA 非必要"读成"无需证据"？ | ICLR-1—ICLR-5（见 §10.3） | 用"没有 SOTA"自我否决；或用"不要求 SOTA"替代证据 |

**G5 判定输出格式（`D6`）：**

```markdown
### D6 Venue Calibration

**Contribution type（来自 D2）：** (O=…, T=…, R=…) / <贡献类型>
**Evidence contract（来自 §10.1）：** EC-… 已满足项：…；缺失项：…（对应 Ci ← [待补]）

| Venue | 校准问句回答 | 引用条目 | 判定 |
|---|---|---|---|
| CVPR | …… | CVPR-1 / CVPR-3 | 匹配 / 边缘 / 不匹配 |
| ICML | …… | ICML-1 / ICML-7 | 匹配 / 边缘 / 不匹配 |
| NeurIPS | …… | NIPS-2 / NIPS-3 | 匹配 / 边缘 / 不匹配 |
| MICCAI | …… | MICCAI-1 / MICCAI-2 | 匹配 / 边缘 / 不匹配 / 不适用 |

**G5 Venue scope：** pass / fail
**首选 venue 与理由：** ……
**注：** 若上表任一行引用的是【待核实】条目，必须在本处标注。
```

### 10.3 ICLR：**本轮仅作 calibration 参考**（登记为 P1）

**ICLR 2026 已核实口径**（S3 = [ICLR 2026 Reviewer Guide](https://iclr.cc/Conferences/2026/ReviewerGuide)）：

| # | 类型 | 口径 | 依据（S3 页面小节） |
|---|---|---|---|
| ICLR-1 | **【原文】** | 评审目的："a review aims to determine whether a submission will **bring sufficient value to the community and contribute new knowledge**." | Reviewing a submission: step-by-step |
| ICLR-2 | **【原文】** | **四个必答关键问题**："**What is the specific question and/or problem tackled by the paper?**"；"**Is the approach well motivated, including being well-placed in the literature?**"；"**Does the paper support the claims?** This includes determining if results, whether theoretical or empirical, are correct and if they are scientifically rigorous."；"**What is the significance of the work? Does it contribute new knowledge and sufficient value to the community?**" | 同上 |
| ICLR-3 | **【原文】** | **SOTA 非必要条件**："Note, this **does not necessarily require state-of-the-art results**. Submissions bring value to the ICLR community when they **convincingly demonstrate new, relevant, impactful knowledge**（incl., empirical, theoretical, for practitioners, etc）." | 同上 |
| ICLR-4 | **【原文】** | FAQ 直答："**Q: If a submission does not achieve state-of-the-art results, is that grounds for rejection? A: No**, a lack of state-of-the-art results **does not by itself constitute grounds for rejection**. Submissions ... can achieve this **without** achieving state-of-the-art results." | FAQ 节 |
| ICLR-5 | **【原文】** | 论文目标分类："**Objective of the work**: What is the goal of the paper? Is it to better address a known application or problem, draw attention to a new application or problem, or to introduce and/or explain a new theoretical finding? A combination of these? **Different objectives will require different considerations** as to potential value and impact." | 同上 |

> **⚠️ 本轮不新增 ICLR 为审稿角色。**
> §1—§4 目前只覆盖 **3 + 1** 个会议（CVPR / ICML / NeurIPS / MICCAI）。
> 若把 ICLR 提升为审稿角色（例如新增 `R-ICLR`），会触发**跨文件大范围漂移**——
> 至少涉及 `SKILL.md` 的 §0 / §3 / §4、[roles.md](roles.md) §1 的会议审稿人表、
> 本文件 §0.3 与 §6 模板、以及各 R 阶段 的派遣矩阵（合计约 **13 处**）。
> 因此本轮的处理是：**ICLR 只作为 §10.2 的 calibration 参考**（与 TMI / JMLR / Nature MI 同级），
> **不进入** §0.3 的会议特性判定表，**不进入** §6 模板，**不派**子代理。
>
> **已登记为 P1 待办**（见 `docs/claim-first-spec.md` §9 第 3 条：
> "会议枚举新增 `ICLR` 与顶刊（TMI / JMLR / Nature MI）——涉及 SKILL §0/§3/§4、venue-standards、
> roles §1（约 13 处），单独一轮"）。**本轮不得**擅自把 ICLR 写成审稿角色。

**ICLR 的校准价值（为什么值得登记）：** ICLR-2 的四个问题与
[claim-first-policy.md](claim-first-policy.md) §3 的 Claim Graph `C0`—`C5`
高度同构（问题 / 动机 / claim 支撑 / 新知识），ICLR-3 / ICLR-4 则是对
"没有 SOTA 是否致命"的直接回答，可用于校正 `G1 Claim grounding` 的过严判定。
**但校准不等于派遣**——引用 ICLR 条目时必须在同一行写明它是**校准参考**。

---

## 引用本文件的位置（维护提示）

| 位置 | 引用内容 |
|---|---|
| [roles.md](roles.md) §1、§5、§6 | §0 两角度框架（**只用于 R12 / R13 的 venue calibration 表**；会议 persona 不在**任何** R 阶段派遣） |
| [phase-r3-r6-discovery.md](phase-r3-r6-discovery.md) / [phase-r8-evidence-contract.md](phase-r8-evidence-contract.md) / [phase-r7-r10-r13-assurance-repair-review.md](phase-r7-r10-r13-assurance-repair-review.md) | §0、§5.1、§6、§7 |
| [phase-r12-narrative.md](phase-r12-narrative.md) | `D6` venue calibration → §10；贡献类型 → §5 |
| [claim-first-policy.md](claim-first-policy.md) §5、§7.4 | §10（`(O, T, R)` 与证据契约 ← claim-first §5） |
| [scoring-policy.md](scoring-policy.md) | `G5 Venue scope` → §10.2 |
| [narrative-patterns.md](narrative-patterns.md) §2 | preset 选择**在** §10.0 顺序之后 |

**节号稳定性：** §1—§8 的编号被上述文件引用，属**冻结区**；
§9 / §10 为本轮新增。移动或重编号冻结区节号，**必须**同轮更新全部引用点。
