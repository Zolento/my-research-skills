# Context Benchmark（v2.2.0 前后对比）

本文件是 v2.2.0「Context & Architecture Optimization」的**实测**对比。
基线定义与测量限制见 [context-baseline.md](context-baseline.md)，重复的方法口径不在这里复述。

- 基线版本：`research-lifecycle-protocol` 2.1.1（`main` = `787b1d9`）
- 对比版本：`research-lifecycle-protocol` 2.2.0（`research-lifecycle-protocol/dev`）
- 工具：`scripts/context_profile.py` + `scripts/context_planner.py`

---

## 0. 两臂分别是什么

| 臂 | L0 | 读取集合来自 |
|---|---|---|
| **旧架构** | v2.1.1 的 `SKILL.md`（156565 bytes） | 旧 `SKILL.md` 的**书面加载指令**（逐场景推导，写在 `context_profile.py` 的 `baseline_rationale`） |
| **新架构** | v2.2.0 的 `SKILL.md`（26744 bytes） | `preset-registry.json` 的 `context` 声明，经 `context_planner.plan()` 解析 |

两臂的差异同时包含**两件事**：L0 变小，以及读取集合由「按文档写的指令推测」变成
「按机器可读依赖声明解析」。这两件事都是本轮架构变更的一部分，因此合并报告；
但第 3 节会把它们拆开，单独给出「只换 L0」的效应。

---

## 1. 静态：`SKILL.md`

| 指标 | 旧 | 新 | 变化 |
|---|---|---|---|
| 字节 | 156,565 | 26,744 | **−82.9%** |
| 字符 | 95,831 | 18,272 | −80.9% |
| 行 | 1,794 | 513 | −71% |
| 一级/二级标题 | 35 | 12 | −66% |

**本轮 L0 的工程目标是 10—15 KB，实测 26.7 KB，未达标。** 差距的来源与处置见 §5。

---

## 2. 每次调用的协议上下文

`est` 是启发式估算（`heuristic_v1`），**不是真实 tokenizer 输出**。见基线的口径声明。

| 场景 | 旧字符 | 新字符 | 变化 | 旧 est | 新 est | 变化 | 工具调用 |
|---|---|---|---|---|---|---|---|
| `bootstrap` | 116,352 | 31,448 | −73% | 53,090 | 15,548 | −71% | 3 → 3 |
| `resume` | 116,237 | 21,401 | −82% | 52,082 | 10,032 | −81% | 3 → 2 |
| `research-loop` | 115,098 | 39,258 | −66% | 53,038 | 15,725 | −70% | 4 → 4 |
| `literature` | 136,837 | 71,959 | −47% | 62,512 | 32,938 | −47% | 4 → 4 |
| `paradigm-escape` | 175,343 | 48,587 | −72% | 73,599 | 21,936 | −70% | 4 → 3 |
| `audit` | 133,302 | 53,687 | −60% | 60,742 | 25,256 | −58% | 5 → 5 |
| `r8-prereg` | 141,032 | 38,262 | −73% | 55,945 | 14,527 | −74% | 4 → 3 |
| `r9o-outcome` | 142,154 | 39,258 | −72% | 57,443 | 15,725 | −73% | 5 → 4 |
| `mri-ssl` | 107,415 | 32,832 | −69% | 48,966 | 15,458 | −68% | 5 → 5 |
| `mri-method` | 125,387 | 39,620 | −68% | 57,799 | 19,293 | −67% | 6 → 6 |
| `context-drift` | 120,512 | 21,063 | −83% | 50,927 | 9,902 | −81% | 3 → 2 |
| `subagent` | 123,449 | 16,881 | −86% | 57,031 | 7,846 | −86% | 3 → 0 |
| **平均** | **129,426** | **37,855** | **−71%** | **56,931** | **17,016** | **−70%** | **4.08 → 3.42** |

**没有任何场景的工具调用次数上升。** 这是本轮的一条硬要求：需要读**更多**文件才能完成
常规研究动作，属于优化失败（§12.3 第 3 条）。

### 2.1 为什么 `literature` 只降 47%

`explore` 入口登记的预设是 `paradigm-escape`，它的必需集合里包含
`phase-r3-r6-discovery.md`（26,816 字符），而文献任务还会条件加载
`literature-policy.md`。两个大文档叠加，压缩空间最小。

这是**如实结果**，不是测量误差：探索类任务的协议本身最重。
若要继续压缩，正确方向是给 `phase-r3-r6` 建立更细的章节级加载，而不是删规则。

### 2.2 为什么 `audit` 与 `mri-method` 的工具调用没有下降

`audit` 的必需集合就是四份文档（phase-r7 / evidence-policy / scoring-policy / 契约），
与旧架构推导出的集合基本重合。它的收益来自 **L0 变小**（133,302 → 53,687 字符中，
约 95,800 来自旧 L0），而不是来自读更少的文件。

---

## 3. 拆开效应：只换 L0 会怎样

把读取集合**固定在旧架构的那一套**，只把 L0 从 156,565 bytes 换成 26,744 bytes：

| 项 | 值 |
|---|---|
| 旧架构平均字符 | 129,426 |
| 固定读取集合 + 新 L0 | 约 40,200（平均） |
| 单换 L0 的降幅 | 约 69% |
| 新架构（换 L0 + 计划器）平均 | 37,855 |
| 计划器带来的额外降幅 | 约 6% |

结论：**约 90% 的收益来自 L0 精简，约 10% 来自按任务加载。**
两者都必要：只精简 L0 不会让「MRI 任务不再加载全部 MRI 文档」，
只做计划器也无法抵消 156 KB 的常驻正文。

---

## 4. 未用内容与重复

| 指标 | 旧架构 | 新架构 |
|---|---|---|
| 平均「已加载但本场景用不到」占比 | 最高 34.1%（`research-loop`） | ≤ 1.7%（各场景） |
| 跨文件逐字重复 | ≤ 0.2% | ≤ 0.4% |
| `SKILL.md` 与 `references/` 的逐字重合章节 | 0 个 | — |

旧架构里 `research-loop` 有 34.1% 的已加载字符属于该轮用不到的章节（设计依据、
维护自检、资源目录、文献检索规范），而它们在**每一轮**都被重新注入。

`SKILL.md` 与 `references/` 的逐字重合为 0 这件事必须一起报告：它说明**不能靠删除重复
来精简**。冗余是语义层面的复述，只能逐条迁移（见
[rule-relocation-matrix.md](rule-relocation-matrix.md)）。

---

## 5. 未达标项与理由

### 5.1 L0 目标 10—15 KB，实测 26.7 KB

差 11.7—16.7 KB。**没有为了达标删除必要规则。** 组成如下：

| 部分 | 约字节 | 能否再压 |
|---|---|---|
| frontmatter（Skill 发现用） | 2,440 | 只能压缩 trigger 词表，会损伤发现率 |
| §0 入口与身份（含锚点门槛、存储判定、四种恢复） | 约 6,100 | 已压到表格与短句 |
| §1 七条最小全局不变量 | 约 7,400 | 每条都对应一项强制保留的硬约束 |
| §2 载入映射 | 约 2,400 | 已下沉任务表与完整目录 |
| §3 子代理（含 §3.1.0 跨组件锚点） | 约 1,900 | §3.1.0 被根 `AGENTS.md` §23.1 绑定，不能移走 |
| §4 R0—R14 能力索引 | 约 2,300 | 16 行不能少 |
| §5—§8 | 约 4,200 | 已压到最小集 + 指针 |

判断：**中文规范文本对「11 条强制硬约束 + 14 项 L0 必备内容 + 3 个被外部引用的锚点」
的下限约在 20—24 KB。** 继续压缩必须删规则或删锚点，两者都被本轮明令禁止。

因此本项按任务书 §9.1「工程目标可以按实测调整」处理，并把 40,000 bytes 写成
`release_check` 的回归上限：**L0 不得悄悄长回去**。

### 5.2 没有真实 tokenizer，也没有 Harness 请求记录

所有 `est` 列都是估算。`visible` 层只有一条单次观测（见基线 §2）。
**本文件不把估算和实测混在同一列。**

### 5.3 Prompt Cache 未验证

`plan_digest` 目前只用于检测计划变化。本轮**没有**验证任何一层的缓存命中率
（本地文件缓存 / Harness 层上下文复用 / 服务商 Prompt Cache），因此不声称缓存收益。

---

## 6. 复现

```bash
cd research-lifecycle-protocol

# 基线臂：用 v2.1.1 的 SKILL.md
git show research-lifecycle-protocol/v2.1.1:research-lifecycle-protocol/SKILL.md \
  > /tmp/SKILL.v2.1.1.md
python3 scripts/context_profile.py --all --json --out /tmp/base.json \
  --skill-doc /tmp/SKILL.v2.1.1.md

# 新架构臂
python3 scripts/context_profile.py --all --json --architecture planned \
  --out /tmp/new.json

# 单场景
python3 scripts/context_planner.py plan --preset research-loop \
  --authorization execute --conditional evidence_qualification
python3 scripts/context_planner.py load --preset research-loop   # 真正读盘，填 loaded
```
