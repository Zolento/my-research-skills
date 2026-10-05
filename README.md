# skills

我的 agent skill 集合。**每个子目录 = 一个独立的 skill**，入口是它自己的 `SKILL.md`；
子目录里可以各带 `references/`、`scripts/`、`templates/`、`examples/` 与自己的 `.gitignore`。

## 子目录

| 目录 | 是什么 |
|---|---|
| [`research-idea-pipeline/`](research-idea-pipeline/) | 面向 CVPR / ICML / NeurIPS / MICCAI 投稿的研究创意全流程流水线：文献调研 → idea 发现 → 方案生成 → 多套路叙事生成与审稿 → 方案复核。含可运行的多源检索脚本与离线测试。 |
| [`academic-figure-draft-architect/`](academic-figure-draft-architect/) | 学术示意图**字符草稿**架构师：读代码 / 论文 / 配置 / 用户说明，产出若干份结构真正不同的 Markdown 字符示意图 draft，供人审阅并作为 SVG / TikZ / Figma 代理的结构蓝图。强制四级证据（A/B/C/D）、强制区分 train / inference / frozen，禁止补造不存在的模块；含契约校验脚本与离线测试。 |

## 约定

- 一个子目录一个 skill，互不依赖。
- skill 之间不共享代码；公共约定写在各子目录自己的文档里。

---

## 安装

`npx skills` 从 GitHub 仓库按 **skill 名**（= 子目录名）安装，支持 `-s` 指定单个 skill。

```bash
# 1) 先列有什么（只列不装）
npx skills add Zolento/my-research-skills -l

# 2) 逐个装（source 相同，便于统一更新）
npx skills add Zolento/my-research-skills -g -s research-idea-pipeline -y
npx skills add Zolento/my-research-skills -g -s academic-figure-draft-architect -y

# 或一次装全部
npx skills add Zolento/my-research-skills -g -s '*' -y
```

| 参数 | 含义 |
|---|---|
| `Zolento/my-research-skills` | source：本仓库的 `owner/repo` |
| `-s <name>` | 只装指定 skill（= 子目录名）；`'*'` 表示全部 |
| `-g` | 装到**全局**（`~/.agents/skills/` + 各 agent 软链）；不加则装到当前项目的 `.agents/skills/` |
| `-y` | 跳过交互确认 |
| `-l` | 只列出仓库里有哪些 skill，不安装 |

### ⚠️ 四个坑

1. **同名 skill 只能装一个。** 装了分支版会**覆盖** main 版。想并存只能改 skill 的
   `name` —— 那就是两个不同的 skill 了。
2. **装了分支版后，它就跟着那条 ref 走，不再跟 main。** 之后在 main 上改了**不生效**，
   别奇怪。
3. **`#<片段>` 会带来耦合并发问题：** `update` 会对比那条 ref 的 tree hash；分支被
   force-push 后 hash 变了会触发更新。
4. **`-g` 与不加 `-g` 是两套：** `-g` = 全局（`~/.agents/skills/` + 各 agent 软链）；
   不加 `-g` = 装到当前项目的 `.agents/skills/`。**本仓库一直用 `-g`。**

> 所以在 worktree 分支上开发 / 联调时，要么**先合回 main 再装**，要么明确接受"这个
> skill 暂时跟分支走、之后的改动不会自动出现在 main 安装里"。

## 日常维护

```bash
npx skills list -g                              # 看已装
npx skills update -g -y                         # 全部更新
npx skills update research-idea-pipeline -g -y  # 单独更新
npx skills remove research-idea-pipeline -g -y  # 卸载
```

> **更新语义：** `npx skills update` 是把已安装的 skill **重新拉取 source 的当前内容**
> （含上面坑 3 的 tree-hash 对比）。因此**改动必须先进本仓库**（子目录内的 `SKILL.md`
> 及 `references/` / `scripts/` / `templates/` / `examples/`），本地零散修改不会被同步，
> 也会在下一次 update 时被覆盖。

> **新增子 skill 后：** 需要 `npx skills update -g -y`（或重新 `add`）才会出现在已装列表里；
> 仅 `list` 不会自动发现。

---

## 仓库结构

```
my-research-skills/
├── README.md                          # 本文件：子目录索引 + 安装与维护
├── research-idea-pipeline/            # skill 1
│   ├── SKILL.md                       # 入口（frontmatter: name / description / argument-hint）
│   └── references/ scripts/ templates/ examples/
└── academic-figure-draft-architect/   # skill 2
    ├── SKILL.md                       # 入口；description 内含触发词，供 skills 发现
    └── references/ scripts/ templates/ examples/
```

**每个 skill 的 `SKILL.md` frontmatter 里 `name` 必须等于它的子目录名**——
`npx skills add -s <name>` 就是按这个名字定位的。
