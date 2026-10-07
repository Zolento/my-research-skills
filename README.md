# skills

我的 agent skill 集合。**每个子目录 = 一个独立的 skill**，入口是它自己的 `SKILL.md`；
子目录里可以各带 `references/`、`scripts/`、`templates/`、`examples/` 与自己的 `.gitignore`。

## 子目录

| 目录 | 是什么 |
|---|---|
| [`research-idea-pipeline/`](research-idea-pipeline/) | 以 **Research State** 为中心的科研搜索系统（`R0`—`R14` 双循环：Discovery 扩大候选并保多样性 / Assurance 对抗审核与修复），面向 CVPR / ICML / NeurIPS / MICCAI 投稿。24 条硬规则由校验器机械强制；含结构等价审计、状态投影与多源检索脚本，并配套离线回归测试。 |
| [`academic-figure-draft-architect/`](academic-figure-draft-architect/) | 学术示意图**字符草稿**架构师：读代码 / 论文 / 配置 / 用户说明，产出若干份结构不同的 Markdown 字符示意图 draft，作为 SVG / TikZ / Figma 代理的结构蓝图。强制四级证据（A/B/C/D）、强制区分 train / inference / frozen，禁止补造不存在的模块；含契约校验脚本与离线测试。 |

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

`main` 的职责是**可安装的 skill 集合** —— 它的根目录只有本文件与各 skill 子目录。

**根 `docs/` 属开发产物**（设计规格 `*-spec.md`、验证记录 `verify-*.md`、审查报告
`review/*.md`），只与开发有关，**不在 `main` 上**；它保留在开发分支
（如 `research-idea-pipeline-dev`），那是设计记录的家。

> **维护提示：** 若在开发分支上**修改**根 `docs/`，再向 `main` 合并时会遇到
> `modify/delete` 冲突 —— 因为 `main` 已删除该路径。**按「保留删除」处理**：
> 开发文档不要进 `main`。新增开发文档请直接提交到开发分支。

---

## 仓库结构

```
my-research-skills/
├── README.md                          # 本文件：子目录索引 + 安装与维护
├── research-idea-pipeline/            # skill 1（自带 README.md、docs/、.gitignore）
│   ├── SKILL.md                       # 入口（frontmatter: name / description / argument-hint）
│   └── references/ scripts/ templates/ examples/
└── academic-figure-draft-architect/   # skill 2（自带 README.md）
    ├── SKILL.md                       # 入口；description 内含触发词，供 skills 发现
    └── references/ scripts/ templates/ examples/
```
