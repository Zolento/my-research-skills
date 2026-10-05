# academic-figure-draft-architect

**Academic Figure Draft Architect（学术示意图字符草稿架构师）** —— 把项目代码、论文、技术
文档、实验配置与用户说明，转成若干份 **Markdown 字符示意图 draft**，供人类研究者审阅，
并作为后续 SVG / Illustrator / TikZ / Figma 图生成代理的**结构蓝图**。

> **职责边界：不做最终插图、不生成 SVG、不输出只有 Mermaid 没有字符图的方案。**
> 它是 **代码 / 论文语义 → 科学视觉结构** 之间的中间层。

**成功判据只有两条：**

1. 一名**没有读过源码**的论文合作者，能通过字符图理解方法；
2. 一名**没有深入理解算法**的 SVG 绘图代理，能按 draft 准确制作正式示意图。

> **状态：已构建，待审核。** 本项目尚未安装到任何 skills 目录
> （`~/.claude/skills/`、`~/.agents/skills/` 等）。

---

## 目录结构

```
academic-figure-draft-architect/
├── SKILL.md                              # 入口：边界、参数、七步流程、自检清单
├── README.md                             # 本文件
├── references/
│   ├── evidence-policy.md                # ★ 唯一权威：A/B/C/D 四级证据 + 禁止补造清单
│   ├── source-reading.md                 # 源码 / 论文阅读规范（入口函数、迭代 solver、多阶段）
│   ├── figure-semantics.md               # Entities/Relations → 布局；内部十问；train/infer
│   ├── visual-grammar.md                 # A–H 八种视觉语法 + 多样性矩阵 + 密度预算
│   ├── ascii-design-language.md          # 字形 / 线型语义 / 中英混排宽度 / 反模式
│   ├── figure-types.md                   # 8 种 FIGURE_TYPE 的侧重与必备元素
│   └── output-contract.md                # ★ 十段式 schema + 机器校验条件
├── scripts/
│   ├── check_draft.py                    # 契约校验（缺段 / 字符图 / D 级进图 / 悬空 ID / 对齐）
│   └── test_check_draft.py               # 离线测试（stdlib unittest）
├── templates/
│   ├── figure-draft.template.md          # 十段式骨架
│   └── element-inventory.template.md     # 元素表列定义 + 填写示例 + 反例
└── examples/
    ├── demo-source/                      # 示例用的小型真实源码库（自监督 MRI 重建 + flow prior）
    ├── example-code-grounded.md          # ★ 代码驱动：3 个结构不同的 draft 全流程
    └── example-uncertainty.md            # 证据不足时的降级处理与不确定性清单
```

---

## 核心原则

### 1. Grounded Figure（最高优先级）

图中的模块、箭头、变量、操作、数据流与训练关系**必须能追溯到输入材料**。
**禁止为了"让图完整"而虚构模块。**

```text
❌ Input → Encoder → Feature Alignment → Decoder → Output     （若无据）
✅ Input → Backbone → Output                                  （有据）
```

### 2. 四级证据

| 等级 | 含义 | 能进主图 | 图后必须交代 |
|---|---|---|---|
| **A** Directly Observed | 代码/论文直接存在 | ✅ | 出处 |
| **B** Strongly Implied | 计算过程可确定存在 | ✅ | 出处 + `semantic abstraction` |
| **C** Author-Level Interpretation | 多操作合理聚合 | ✅ | 聚合前后逐项对应 |
| **D** Speculative | 材料不足 | ❌ | 只能进 `Uncertainties` 或 `[? label]` |

**权威定义见 [references/evidence-policy.md](references/evidence-policy.md)。**

### 3. 最容易被忽略、但后果最重的三条

```
1. train / inference 混淆（GT 被画进 inference 区）
2. 冻结网络被画成在训练
3. 迭代 solver 被压成 Input → Network → Output
```

三条都是**契约违规**，不是风格问题。

---

## 参数

| 参数 | 取值 | 缺省 |
|---|---|---|
| `FIGURE_TYPE` | method-overview / architecture / training / inference / optimization / motivation / comparison / ablation | `method-overview`（推断时须声明） |
| `DETAIL_LEVEL` | overview / medium / detailed | `medium` |
| `NUM_DRAFTS` | 2–5 | `3`（简单 2；复杂多 story 4；上限 5） |
| `FOCUS` | 自由文本 | 按 FIGURE_TYPE 默认侧重 |
| `TARGET_PAPER` | 会议 / 论文 | 只影响详略与画幅建议 |
| `MUST_INCLUDE` / `MUST_NOT_INCLUDE` | 清单 | 空；**硬约束** |
| `KNOWN_FACTS` | 用户已确认事实 | 空；按 A 级 + `[user]` 处理 |

**参数缺失不阻塞任务**，但补上的参数必须在输出开头声明。

---

## 七步工作流

```
S1 采集  → 读真正的计算图（forward / training_step / loss / solve / reconstruct）
S2 语义  → 建 Entities / Relations，先有语义后有布局
S3 十问  → 答不出就进 Uncertainties，不得补全
S4 选语法 → 从 A–H 中选，且保证结构级多样性
S5 画图  → 字符图 + 线型语义 + 中英混排宽度
S6 输出  → 十段式 Markdown
S7 终检  → 自检清单 + scripts/check_draft.py
```

---

## 输出：十段式

```
1  Figure Understanding      5–12 行概括
2  Evidence Summary          证据表（element / evidence / confidence）
3+ Draft A/B/C…              字符图 + Best for / Strength / Weakness（grammar 必须不同）
6  Recommended Draft         明确推荐一个（`**Recommended: Draft X**`）
7  Alignment Notes           视觉元素 ↔ 代码/论文；聚合与改名显式声明
8  Uncertainties             U1/U2…，不得偷偷解决
9  SVG Handoff Notes         画布 / 主流向 / 分组 / 强调 / 线型 / 样式层级
10 Figure Element Inventory  ID/Type/Label/Group/Inputs/Outputs/Status
```

**产出落盘建议：** `<项目>/.figure-drafts/<figure-id>.draft.md`，
`<figure-id>` 形如 `F001-method-overview`。draft **不写进论文目录**。

完整 schema 见 [references/output-contract.md](references/output-contract.md)，
骨架见 [templates/figure-draft.template.md](templates/figure-draft.template.md)。

---

## 字符图设计语言（速查）

| 线型 | 语义 |
|---|---|
| 实线 `───▶` | inference / 前向计算 |
| 虚线 `─ ─ ▶` | training supervision（loss / target / gradient） |
| 点线 `┈┈▶` | optional / conceptual / initializes |
| 双线 `═══▶` | domain / stage 分隔带（不是数据流） |

**宽度规则（对齐的根本）：中日韩字符占 2 显示列，ASCII 占 1 列。**
含中文的行必须按双宽补齐空格，否则右边框会歪。

**样式层级：** Level 1 = domain/stage 容器；Level 2 = 主要模块；Level 3 = 算子/loss；
Level 4 = 注释。**视觉中心 = 核心贡献模块。**

完整规范见 [references/ascii-design-language.md](references/ascii-design-language.md)。

---

## 自检脚本

```bash
# 单份 draft
python3 scripts/check_draft.py path/to/F001-method-overview.draft.md

# 严格模式 + 强制约束（对应 MUST_NOT_INCLUDE / MUST_INCLUDE）
python3 scripts/check_draft.py --strict \
    --forbid "Cross Attention" --require "Flow Prior" \
    path/to/F001-method-overview.draft.md

# 机器可读
python3 scripts/check_draft.py --json path/to/*.draft.md

# 离线测试
python3 -m unittest discover -s scripts -p 'test_*.py' -v
```

| 退出码 | 含义 |
|---|---|
| `0` | 通过 |
| `1` | 用法 / 文件错误 |
| `2` | 存在警告（对齐可疑、ID 未被引用、grammar 少样等） |
| `3` | **契约违规**（缺段、缺字符图、D 级进图、悬空 ID、Status 非法、多样性不足…） |

**脚本只校验形式契约，不校验科学正确性。** 语义忠实性由
[SKILL.md §8 自检清单](SKILL.md)负责。

> **`--forbid` 的扫描范围是「图的内容」**（`text` 字符块 + Evidence Summary 表 + 元素表），
> **不扫正文** —— 这样 draft 才能公开声明"哪些内容被排除在图外"；`--require` 扫整篇文档。

---

## 示例

| 示例 | 演示了什么 |
|---|---|
| [example-code-grounded.md](examples/example-code-grounded.md) | 从 `examples/demo-source/`（自监督 MRI 重建 + flow prior + 非展开 solver）产出 3 个结构不同的 draft，含迭代循环、冻结 prior、target adaptation 的视觉表达 |
| [example-uncertainty.md](examples/example-uncertainty.md) | 材料不足时如何降级到 `Uncertainties`、如何遵守 `MUST_NOT_INCLUDE`、如何避免把 hypothesis 画成事实 |

---

## 与其他 skill 的关系

**无硬依赖。** 上游若使用 `research-idea-pipeline` 的 Mode C/D 产出（方案 / 叙事），
可以把其中的方法与实验计划作为本 Skill 的输入材料之一；但本 Skill 不读取、不写入该
流水线的任何文件，也不假设其目录结构存在。

---

## 维护本 Skill 时

改任何**规则 / 枚举 / 列名 / 计数 / 路径**前，同步检查这四处（历史漂移从不发生在规则
本身，而是发生在"看起来不像规则"的位置）：

1. `SKILL.md` 的资源索引表与交叉链接；
2. [output-contract.md](references/output-contract.md) 的 schema ↔
   [scripts/check_draft.py](scripts/check_draft.py) 的校验逻辑 ↔
   [templates/](templates/) 的骨架（**三者必须同值**）；
3. [visual-grammar.md](references/visual-grammar.md) 的 grammar 枚举 ↔ 示例里声明的
   grammar 名称；
4. 证据等级 A–D（[evidence-policy.md](references/evidence-policy.md)）↔ 元素表 `Status`
   取值域 ↔ 自检清单措辞。

> **每条新规则都要问：①字段表里有槽位吗？②枚举里有值吗？③脚本校验得到吗？**

---

## 安装（待审核通过后再执行）

本项目刻意**未**安装。审核通过后：

```bash
ln -s "$PWD/academic-figure-draft-architect" ~/.claude/skills/academic-figure-draft-architect
```
