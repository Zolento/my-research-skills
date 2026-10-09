# skills

我的 agent skill 集合。**每个子目录 = 一个独立的 skill**，入口是它自己的 `SKILL.md`；
子目录里可以各带 `references/`、`scripts/`、`templates/`、`examples/` 与自己的 `.gitignore`。

## 子目录

| 目录 | 是什么 |
|---|---|
| [`research-idea-pipeline/`](research-idea-pipeline/) | 以 **Research State** 为中心的科研搜索系统（`R0`—`R14` 双循环：Discovery 扩大候选并保多样性 / Assurance 对抗审核与修复），面向 CVPR / ICML / NeurIPS / MICCAI 投稿。24 条硬规则由校验器机械强制；含结构等价审计、状态投影与多源检索脚本，并配套离线回归测试。本地文献源默认走 Zotero（Local API 只读），不可用时自动回落到 `docs/refs/` 旧格式；`zotero_refs.py` 可把 Zotero 元数据 / PDF 导出到该格式。内部 Evidence Outcome Analysis 区分有效负证据与无效执行，固化 scoped updates、negative knowledge 和下一步决策。PEIG/AALG 将风险对照、有限诊断与内容绑定 receipt 接入受控执行入口。**Cognitive Insight Engine** 在路线控制平面下维护四类认知记忆（机制 / 异常 / 竞争 / 科学价值）：`cognition/index.json` 与 `cognition/context-brief.md` 完全可由 `research-state.json` 加 append-only 修订日志重建，支持等级一律由 canonical 证据推出，跨会话恢复机制模型、失败约束与未完成竞争。预测通过冻结在既有 `preregistration.outcomes[]` 里的可判定判据比较，输出成立 / 偏差 / 容差内 / 部分评价 / 探索性 / 无效 / 不可判定七类结果；互斥分支必须由预注册冻结 `outcome_mode` 与 `branch_rule` 才能进入 branch mode，所选分支由冻结规则作用于原始观测导出，事后声明 `observed_outcome` 一律按完整模式判定。证据资格只有 `qualify_evidence` 一个入口（`PQ1`—`PQ8`）：**`PQ4` 直接消费观测包校验器的完整结论**（schema 错误、缺字段、字段类型非法、越界 `observed_outcome`、来源缺失、摘要不符一律 fail closed），判定集合不完整、分支不可追溯、时间顺序被破坏或冻结登记无法核验同样阻断，不得授权 Claim 升级、机制否证或 Insight 认证；纯提示性多余键不误伤，诊断性比较仍保留在 `diagnostic_outcome_class`。Insight 只有绑定到**具体预测**——evidence 必须带 `prediction_ref`，或该实验只冻结了一个结果（禁止用"同实验 / 同 claim / 同机制 / 同指标"推断）——且**适用范围覆盖**（字符串 scope 规范化精确相等；结构化 `scope_region` 按约束子集判包含，`"MRI"` 不覆盖 `"MRI-3D"`，更窄证据不得外推）并通过结构等价审计后才能成为 `evidence_supported_insight`；机制竞争要求各机制拥有不同的冻结判据。**Legacy Research Handoff** 让已初始化项目在 `continue-research` 入口下只读接管：不重置 state version、claim 状态、证据、实验 ID、锚点或诊断预算，不补造历史预测，严重兼容性错误阻止写回。**科学价值与自适应发现** 分维判断 Decision Value 与 Discovery Potential（无总分），科学品味区分用户所有与证据校准两部分，探索策略复用既有算子并保留探索下限——算子降级需要至少两次独立失败、限定问题结构且带重启条件，`scheduler.json` 保持只读。**Research Preset Library（2.3.1）** 内容包 = `shared-contract.md`（共同约束）+ `preset-registry.json`（16 条元数据与 48 条意图示例）+ `presets/<id>.md`（16 份独立协议，按需只加载一份）+ `router-fixtures.json`（53 条路由基准）；把 16 个排练过的协议放进既有四个入口，用户用自然语言即可调用（`preset_router.py resolve`）：6 个主动预设（自主科研闭环 / 范式逃逸 / 状态恢复 / 科学重规划 / 对抗审查 / 进展回顾）、7 个 Loop 自动恢复（证据冲突 / 上下文漂移 / 记忆整合 / 资源 / 工程失败 / 体检 / 停滞打破）、3 个自进化（策略进化 / 假设再平衡 / 回放评估）。触发只看机器可读信号，同一状态快照只允许一次并带冷却与上限，超限 `HOLD` 交人裁决（事件监听与后台常驻由调用方/既有 Scheduler 负责，本 skill 不装守护进程、不宣称无人值守自动执行）；工程故障（OOM/NaN）只做修复路由、绝不写成科学否证；自进化经 Strategy Decision Adapter 在**同一 `EIG ÷ cost` 优先级层内**影响真实动作选择，并把候选集/建议/采纳与否/原因记入 `scheduler.strategy_decisions[]` 供下一轮消费（被采纳 ≠ 科研能力提升，收益仍由回放与科学结果验证）。**历史回放与验证** 用当时可见信息重放研究决策，以隐藏答案评分：七维独立指标（无加权总分，不可评记 `null`）、四个消融 arm、十四个对抗 case，并强制隐藏信息不可达；样本不足时明确声明不得宣称提升。真实 Agent A/B 评测尚未进行。 |
| [`scientific-manuscript-reviser/`](scientific-manuscript-reviser/) | 科学论文架构、审计与修改。提供 Scientific Coherence Audit、Compact / Full Blueprint、多选 suggestion bank、作者风格保护和语义 / style 门禁；可独立安装，不依赖其他 skill。 |
| [`academic-figure-draft-architect/`](academic-figure-draft-architect/) | 学术示意图**字符草稿**架构师：读代码 / 论文 / 配置 / 用户说明，产出若干份结构不同的 Markdown 字符示意图 draft，作为 SVG / TikZ / Figma 代理的结构蓝图。强制四级证据（A/B/C/D）、强制区分 train / inference / frozen，禁止补造不存在的模块；含契约校验脚本与离线测试。 |

## 新增论文架构、审计与修改

[`scientific-manuscript-reviser`](scientific-manuscript-reviser/SKILL.md) 是独立 skill，核心对象是 scientific argument。

- **Audit** 审计已有论文，先检查科学推理，再检查 narrative、段落、语言和 style。默认提供多选建议，保护 Keep as is。
- **Architect** 从不完整研究材料构建 thesis、claim/evidence map 和论文蓝图。普通大纲使用 Compact，详细大纲使用 paragraph-level Full Blueprint。
- **Revise** 在明确要求修改时，按诊断和选择重写，并检查 scientific invariance 与个人 hard style rules。已批准蓝图可用于逐节起草。

示例请求包括“分析这一节并给多个修改方向”“基于这些实验笔记给详细论文大纲”和“按已选建议修改并保留数值、scope 与 limitation”。计划实验不能写成已完成结果。生成和审计使用相同科学标准，不以 reviewer 分数或 AI detector 为优化目标。
详细用法、验证边界和示例见 [skill README](scientific-manuscript-reviser/README.md)。

## 约定

- 一个子目录一个 skill，互不依赖。
- skill 之间不共享代码；公共约定写在各子目录自己的文档里。

---

## 安装

`npx skills` 按 `SKILL.md` frontmatter 里的 **`name`** 定位并安装 skill。目录名不参与匹配；
本仓库约定两者字面值一致。

```bash
# 先列有什么（只列不装）
npx skills add Zolento/my-research-skills -l

# 逐个装（source 相同，便于统一更新）
npx skills add Zolento/my-research-skills -g -s research-idea-pipeline -y
npx skills add Zolento/my-research-skills -g -s academic-figure-draft-architect -y
npx skills add Zolento/my-research-skills -g -s scientific-manuscript-reviser -y

# 或一次装全部
npx skills add Zolento/my-research-skills -g -s '*' -y
```

| 参数 | 含义 |
|---|---|
| `Zolento/my-research-skills` | source：本仓库的 `owner/repo` |
| `-s <name>` | 只装指定 skill（`<name>` = frontmatter 的 `name`）；`'*'` 表示全部 |
| `-g` | 装到**全局**（`~/.agents/skills/` + 各 agent 软链）；不加则装到当前项目的 `.agents/skills/` |
| `-y` | 跳过交互确认 |
| `-l` | 只列出仓库里有哪些 skill，不安装 |

分支名含 `/`（本仓库约定 `<skill>/<主题>`）时，**不要**用
`github.com/<owner>/<repo>/tree/<分支>/<子目录>`——CLI 用 `[^/]+` 取 ref，斜杠会被当成路径。
改用片段语法（ref 可含斜杠）；分支版会**覆盖**同名 main 版：

```bash
npx skills add "Zolento/my-research-skills#<分支>@<skill>" -g -y
```

## 版本与发布

每个 skill 的版本写在它自己 `SKILL.md` frontmatter 的 `metadata.version`（`research-idea-pipeline`
当前为 **2.3.1**）。发布以**注释 tag** 标记，命名 `<component>/vX.Y.Z`，打在 merge 进 `main`
的提交上；tag 消息里写清 merge commit、升级注意、验收读数与安装结果。

```bash
git tag -l 'research-idea-pipeline/v*'          # 看已发布版本
git show research-idea-pipeline/v2.3.0          # 看该版本的发布说明
```

## 日常维护

```bash
npx skills list -g                              # 看已装
npx skills update -g -y                         # 全部更新
npx skills update research-idea-pipeline -g -y  # 单独更新
npx skills remove research-idea-pipeline -g -y  # 卸载
```

改动请改本仓库，不要改 `~/.agents/skills/` 下的安装副本；新增子 skill 后要重新 `add`，
`update` 不会发现它。

---

## 分支与开发产物

`main` 的职责是**可安装的 skill 集合** —— 它的根目录只有本文件、`AGENTS.md` 与各 skill 子目录。

开发规范以根 [AGENTS.md](AGENTS.md) 为准，所有分支遵循同一套目录和合并规则。

- 组件开发记录统一放在 `<component>/.dev/`。只有仓库级、跨组件记录使用根 `.dev/`。
- 原根 `docs/` 中的开发计划、实现笔记和临时审查报告应迁入所属组件的 `.dev/`。
  不再新建其他临时目录。正式文档、运行所需文献库和测试 fixture 保留正式位置。
- `.dev/` 可提交到开发分支，默认不得进入 `main`。合并前逐项执行
  `PROMOTE`、`KEEP_BRANCH_ONLY` 或 `DELETE`。提升为正式文档时先整理内容，再放入组件 README、references 或 docs。
- 正式代码、测试和发布流程不得依赖 `.dev/`。删除它不能影响构建、测试或运行。
- 从开发分支安装或手动复制时，应排除 `.dev/`，只保留正式 skill 文件。
  不要整体忽略 `.dev/`，大型缓存或临时生成物可单独忽略。

---

## 仓库结构

```
my-research-skills/
├── AGENTS.md                          # 仓库开发规范：worktree / 分支 / 开发产物隔离
├── README.md                          # 本文件：子目录索引 + 安装与维护
├── research-idea-pipeline/            # skill 1（自带 README.md、docs/、.gitignore）
│   ├── SKILL.md                       # 入口（frontmatter: name / description / argument-hint）
│   └── references/ scripts/ templates/ examples/
├── academic-figure-draft-architect/   # skill 2（自带 README.md）
│   ├── SKILL.md                       # 入口；description 内含触发词，供 skills 发现
│   └── references/ scripts/ templates/ examples/
└── scientific-manuscript-reviser/     # skill 3（独立论文架构、审计与修改）
    ├── SKILL.md                       # 入口；按模式渐进读取 references
    └── references/ scripts/ templates/ examples/ tests/
```
