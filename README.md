# skills

我的 agent skill 集合。**每个子目录 = 一个独立的 skill**，入口是它自己的 `SKILL.md`；
子目录里可以各带 `references/`、`scripts/`、`templates/`、`examples/` 与自己的 `.gitignore`。

## 子目录

| 目录 | 是什么 |
|---|---|
| [`research-idea-pipeline/`](research-idea-pipeline/) | 科研搜索系统：R0—R14 双循环由 24 条硬规则强制，含证据资格与对抗审查；认知引擎维护机制/异常/竞争记忆，可跨会话重建；16 个 Preset 支持自然语言调用与自动恢复。 |
| [`scientific-manuscript-reviser/`](scientific-manuscript-reviser/) | 科学论文架构、审计与修改：提供 Coherence Audit、Compact/Full Blueprint、suggestion bank 与风格门禁；可独立安装。 |
| [`academic-figure-draft-architect/`](academic-figure-draft-architect/) | 学术示意图字符草稿：读代码/论文/配置产出多份 Markdown 字符示意图，供 SVG/TikZ/Figma 绘制；强制四级证据与 train/inference/frozen 区分，不补造模块。 |

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
当前为 **2.3.3**）。发布以**注释 tag** 标记，命名 `<component>/vX.Y.Z`，打在 merge 进 `main`
的提交上；tag 消息里写清 merge commit、升级注意、验收读数与安装结果。
2.3.3 = 运行时正确性修复：执行预览零副作用（不消耗预算与一次性收据）、Scheduler 硬门禁
fail-closed、策略修订写入权限统一、post-update Assurance 可被真实 `decision_gate` 消费。

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
