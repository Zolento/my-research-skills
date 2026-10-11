# Worktree and Repository Isolation Policy

本仓库采用多子项目结构。根目录下的各一级子目录通常代表一个独立的 skill、plugin、tool 或其他可独立维护的组件。开发工作必须遵循目录隔离和分支隔离原则，避免不同组件之间产生隐式耦合或污染主分支。

## 1. Root Repository Responsibilities

仓库根目录只维护跨项目共享的信息和规则。

根目录必须长期保留以下文件。

- "AGENTS.md" 负责定义整个仓库的开发规范、agent 行为约束、worktree 使用方式、提交和合并规则。
- "README.md" 负责提供项目总览，并说明各一级子目录的用途、状态、入口和基本使用方式。

除确有必要的全局配置外，不应在根目录直接放置某个单独 skill 或 plugin 的实现文件。

新增一级子项目后，应同步更新根目录 "README.md" 中的项目索引和简要说明。

## 2. One Subdirectory, One Development Boundary

每个一级子目录默认视为独立开发边界。

例如

```
repository/
├── AGENTS.md
├── README.md
├── skill-a/
├── skill-b/
├── plugin-a/
└── tool-a/
```

开发某个子项目时，应尽量将代码、测试、模板、reference、example 和项目内文档限制在该目录内部。

未经明确架构设计，不得因为开发一个子项目而修改其他无关子目录。

如果确实需要跨目录修改，必须先说明

- 为什么单目录无法完成任务
- 哪些目录会受到影响
- 是否形成新的共享依赖
- 是否需要修改根目录文档或全局规范

默认禁止为了方便而引入跨 skill 或跨 plugin 的隐式依赖。

## 3. Worktree Isolation

功能开发、实验性重构和较大范围修改应优先使用独立 Git worktree。

每个 worktree 必须绑定一个独立开发分支。

不要在同一个工作目录中频繁切换多个开发分支来执行并行任务。

推荐模式如下。

```
main repository
→ stable main checkout

worktrees/
├── skill-a-feature-x/
├── skill-b-refactor/
└── plugin-a-dev/
```

每个 worktree 只承担一个明确开发目标。

一个 worktree 不应同时承载多个无关 feature。

Agent 在开始修改前必须确认

- 当前 worktree 路径
- 当前 branch
- 目标子目录
- 本次任务允许修改的目录范围

如果当前 worktree 与目标分支不匹配，应先停止修改并修正环境。

## 4. Development Branch Scope

开发分支应尽量对应单个子项目和单个开发目标。

推荐命名形式为

```
<component>/<topic>-dev
```

例如

```
scientific-manuscript-reviser/narrative-style-dev
research-idea-pipeline/failure-recovery-dev
plugin-name/api-refactor-dev
```

开发分支中允许存在仅用于开发过程的辅助材料，统一放在对应组件的 ".dev/"。

例如

```
research-idea-pipeline/.dev/architecture.md
scientific-manuscript-reviser/.dev/review.md
```

只有跨组件的仓库级开发记录才放在根 ".dev/"。不要新建根 "docs/" 或
其他临时目录承载组件开发笔记。已有记录应迁入对应组件的 ".dev/"，
正式运行文档、文献库、模板和测试 fixture 保留正式位置。

这些内容可提交到开发分支，但默认不得进入 "main"。具体规则见第 11—20 节。

## 5. Development-Only Documentation Must Not Merge Into Main

开发分支中的临时文档默认属于 branch-local artifacts。

除非经过明确筛选并正式转化为项目文档，否则不得合并进入 "main"。

特别禁止直接将以下内容带入主分支。

- 临时开发计划
- agent 工作日志
- implementation scratch notes
- 中间架构草稿
- branch-specific TODO
- debugging notes
- migration scratch files
- 未完成的实验记录
- 仅用于当前 worktree 的说明文件
- 临时 review 或 audit 报告

合并前必须执行一次 development-document cleanup。

对每个开发文档做以下三选一处理。

PROMOTE
内容长期有效，将其整理后合并进正式 README、reference 或 docs。

KEEP_BRANCH_ONLY
仅对当前开发分支有价值，不进入 main。

DELETE
已完成使命，不应继续保留。

禁止因为“以后可能有用”而把所有开发文档默认合入 "main"。

"main" 中的文档应代表当前正式实现，而不是开发过程历史。

## 6. Formal Documentation Promotion

如果开发分支中的内容确实具有长期价值，不应直接原样合并。

应先整理成正式文档。

可能的目标位置包括

```
README.md
<component>/README.md
<component>/references/
<component>/docs/
root AGENTS.md
```

正式文档必须满足

- 与当前代码一致
- 不包含过期 TODO
- 不引用 branch-local 路径
- 不记录已失效的设计决策
- 不包含临时 agent 指令
- 不包含未验证结论
- 面向未来维护者，而不是当前开发会话

## 7. Main Branch Cleanliness

"main" 被视为当前可维护、可理解、可使用的正式状态。

主分支不应包含

- 临时 worktree 文件
- branch-specific notes
- scratch artifacts
- agent session logs
- 未归档的设计争论
- 无对应实现的 speculative docs
- 仅用于一次开发任务的文件

合并前应检查

```
code
tests
formal docs
root README
component README
temporary docs
```

确保主分支只保留长期需要维护的内容。

## 8. Root README Synchronization

如果一次开发造成以下变化之一，应更新根目录 "README.md"。

- 新增一级子项目
- 删除一级子项目
- 子项目重命名
- 子项目职责发生明显变化
- 新增重要入口
- 项目状态从 experimental 变为 stable，或反之

根目录 "README.md" 只提供高层项目地图。

详细实现说明应留在对应子目录中。

避免将所有子项目细节复制到根 README。

## 9. Merge Boundary

合并开发分支前，必须确认本次 diff 与开发目标一致。

默认允许合并

```
target component code
target component tests
target component formal docs
necessary root README updates
necessary root AGENTS.md updates
explicitly approved shared changes
```

默认不允许合并

```
unrelated component changes
temporary development docs
local worktree artifacts
debug outputs
personal notes
generated scratch files
unreviewed cross-component refactors
```

如果 diff 超出原计划目录范围，必须单独审查。

## 10. Agent Behavior

Agent 在本仓库中工作时必须优先遵守以下原则。

1. 先确认目标子目录，再修改代码。
2. 大型开发优先创建独立 worktree 和开发分支。
3. 不修改与当前任务无关的其他子项目。
4. 不默认把开发过程文档合入 "main"。
5. 合并前主动清理 branch-only artifacts。
6. 长期有效的信息应整理后进入正式文档，而不是保留原始开发笔记。
7. 新增或修改一级子项目时同步维护根 "README.md"。
8. 根 "AGENTS.md" 是全仓库最高级开发规范，子目录中的 "AGENTS.md" 只能补充局部规则，不得与根规则冲突。
9. 当局部规则和根规则冲突时，以根目录 "AGENTS.md" 为准，除非根规则明确允许子项目覆盖。
10. 在无法判断某个文件是否应进入 "main" 时，默认不合并，先将其保留在开发分支。

## 11. Unified Development-Only Directory

所有仅服务于当前开发分支、当前 worktree 或临时实现过程的文档和辅助材料，统一放入对应开发边界下的 ".dev/" 目录。

不要在仓库中随意创建多个等价目录，例如：

```
dev-notes/
notes/
scratch/
tmp-docs/
architecture-drafts/
implementation-notes/
agent-notes/
```

统一使用：

```
.dev/
```

如果开发内容只属于某个子项目，应放在该子项目内部：

```
repository/
├── AGENTS.md
├── README.md
├── skill-a/
│   ├── README.md
│   ├── SKILL.md
│   ├── src/
│   ├── tests/
│   └── .dev/
│       ├── plan.md
│       ├── architecture.md
│       ├── decisions.md
│       ├── experiments.md
│       └── review.md
└── skill-b/
```

如果开发内容确实属于整个仓库级别，例如跨多个子项目的迁移、仓库结构重构或全局规范升级，可以使用根目录：

```
repository/
├── .dev/
├── AGENTS.md
└── README.md
```

根 ".dev/" 不得用于存放某个单独 skill 或 plugin 的局部开发记录。

## 12. ".dev/" Content Scope

".dev/" 适合存放以下内容：

```
plan.md
architecture.md
decisions.md
todo.md
experiments.md
review.md
migration.md
debug-notes.md
agent-handoff.md
```

也可以存放临时分析产物、开发阶段检查结果和未定稿设计。

".dev/" 不应存放正式运行所需内容。

以下内容不得仅存在于 ".dev/"：

- 正式 API 文档
- 用户使用说明
- 长期有效的架构规范
- 正式 reference
- 运行时依赖配置
- 必须随发布保留的 migration information
- 测试所需 fixture
- 正式 benchmark protocol
- 用户可见模板

如果某个 ".dev/" 内容逐渐成为正式规范，应执行文档提升，而不是让正式实现依赖 ".dev/"。

## 13. ".dev/" Is Branch-Local by Default

".dev/" 默认视为：

"development-only"

和

"branch-local"

内容。

它允许提交到开发分支，以便不同 agent、worktree 或开发者之间共享开发上下文。

但是：

«".dev/" 中的内容默认禁止进入 "main"。»

开发分支存在 ".dev/" 是正常行为。

主分支存在 ".dev/" 默认视为需要审查的问题。

除非根目录 "AGENTS.md" 明确声明某个特殊 ".dev/" 文件允许长期存在，否则合并前必须处理。

## 14. Pre-Merge ".dev/" Cleanup

在开发分支准备合并到 "main" 之前，必须遍历所有新增或修改的 ".dev/" 内容。

每个文件只能进入以下三种状态之一：

```
PROMOTE
KEEP_BRANCH_ONLY
DELETE
```

PROMOTE

该内容具有长期维护价值。

必须将内容整理并迁移到正式位置，例如：

```
README.md
docs/
references/
AGENTS.md
architecture/
```

迁移完成后删除对应 ".dev/" 原稿。

KEEP_BRANCH_ONLY

内容仍然有开发历史价值，但不属于正式项目。

保留在开发分支。

不得出现在最终 merge diff 中。

DELETE

内容已完成使命。

在合并前删除。

## 15. No Runtime Dependency on ".dev/"

正式代码、测试、构建流程和运行时逻辑不得依赖 ".dev/"。

禁止出现类似：

```
load config from .dev/
read prompt from .dev/
import fixture from .dev/
require .dev/architecture.md
```

如果某文件被运行时依赖，它就不再是 development-only artifact，必须迁移到正式目录。

".dev/" 的删除不能导致：

```
build failure
test failure
runtime failure
missing documentation required for use
```

## 16. Worktree and ".dev/" Relationship

每个 worktree 可以维护自己的 ".dev/" 内容。

不同 worktree 不应通过同一个未提交的本地目录共享状态。

需要跨 agent 或跨 worktree 共享的重要开发信息，应提交到当前开发分支的 ".dev/"。

例如：

```
skill-a/.dev/agent-handoff.md
```

可以记录：

```
current objective
completed work
open questions
known failures
next recommended step
```

但这些 handoff 文档仍然遵循 branch-local 规则，不得默认进入 "main"。

## 17. ".gitignore" Policy

不要默认将整个 ".dev/" 加入 ".gitignore"。

原因是 ".dev/" 中的一部分开发材料可能需要：

- agent handoff
- worktree coordination
- architecture discussion
- reproducible development history

因此开发分支允许提交 ".dev/"。

真正不应进入 Git 的大型临时产物仍应单独忽略，例如：

```
.dev/cache/
.dev/tmp/
.dev/generated/
.dev/logs/
```

具体 ignore 规则可根据项目需要配置。

## 18. Main Branch Guard

推荐在 CI 或 merge check 中增加自动规则：

```
main must not contain newly introduced .dev/ files
```

或者更严格：

```
no .dev/ path may be merged into main
unless explicitly allowlisted
```

如果检测到：

```
*/.dev/*
.dev/*
```

出现在 merge diff 中，则默认阻止合并，并要求执行：

"PROMOTE / KEEP_BRANCH_ONLY / DELETE"

分类。

## 19. Documentation Lifecycle

开发文档应遵循统一生命周期：

```
Idea
↓
.dev/
↓
Validated design
↓
Formal documentation
↓
Main
```

而不是：

```
Idea
↓
Random markdown file
↓
Main forever
```

".dev/" 是设计成熟前的缓冲区。

它的存在目的是让开发过程可以被记录，又不污染正式仓库。

## 20. Agent Requirement for ".dev/"

Agent 在大型开发任务中应主动使用 ".dev/" 记录必要的开发状态，但应保持克制。

建议只在确有必要时创建：

```
.dev/plan.md
.dev/decisions.md
.dev/agent-handoff.md
```

不要为每个小步骤生成一个新 Markdown 文件。

开发完成后，agent 必须主动检查：

```
find . -path "*/.dev/*"
```

并确认哪些内容：

```
PROMOTE
KEEP_BRANCH_ONLY
DELETE
```

在报告任务完成之前，不得忽略这一检查。

最高原则：

«".dev/" is a development workspace, not part of the product.»

以及：

«Development history may live on feature branches, while "main" should contain only durable code, tests, and documentation.»

## 21. Skill Installation: Local Directory Source

本仓库的一级子目录是独立 skill 组件。除在仓库内直接使用外，也可以把组件**安装**到本机
agent 配置目录，供本机各 agent 加载。本节规定安装方式，尤其是**用不同名字安装开发分支**的做法。

> **工具边界：** `dsh` 本身**没有** skill 安装子命令（只有 `dsh plugin` 用于插件）；
> skill 由文件系统发现。安装使用生态 CLI `npx skills`。首次运行需要网络或已缓存的 npm 包。

### 21.1 为什么用本地目录源

`npx skills add` 既支持 GitHub 仓库，也**支持本地目录**（CLI 会打印 `Local path validated`
并回显 `Source: <path>`）。本仓库是私有仓库、skill 位于仓库**子目录**，且经常需要安装
**尚未合并的开发分支**，因此统一使用本地目录源：

```sh
npx skills add <本地目录> -g -y
```

常用开关：`-g/--global`（用户级，而非项目级）、`-y/--yes`（免交互）、
`--copy`（每个 agent 目录各放一份副本，而非符号链接）、`-a/--agent <agents>`（限定目标 agent）、
`-l/--list`（只列出可安装的 skill）、`-s/--skill <names>`（选择仓库内的某个 skill）。

### 21.2 安装后的布局与发现规则

CLI 默认行为：

- **真实内容**落在 `<agentsHome>/skills/<skill-name>/`，本机即 `~/.agents/skills/<skill-name>/`；
- 其它 agent 目录（`~/.claude/skills/` 等）建立指向该目录的**符号链接**；
- 使用 `--copy` 时改为在每个 agent 目录各放一份副本。

DSH 的 skill 扫描根与优先级（`@deepseek-ai/dsh-skill-filesystem`）：

| 优先级 | 来源 | 路径 |
|---|---|---|
| 100 | `project-dsh` | `<projectRoot>/.dsh/skills` |
| 200 | `project-agents` | `<projectRoot>/.agents/skills` |
| 300 | `custom` | 配置项 `customSkillDirs` |
| 400 | `user-dsh` | `$DSH_HOME/skills`（默认 `~/.dsh/skills`）|
| 500 | `user-agents` | `$DSH_AGENTS_HOME/skills`（默认 `~/.agents/skills`）|

发现规则：

- 只认扫描根**顶层**的 `<name>/SKILL.md`（或扁平 `<name>.md`），**不递归** `**/SKILL.md`；
- catalog 名取自 `SKILL.md` frontmatter 的 `name:`，**不是目录名**；
- **`name:` 必须是 kebab-case**：provider 用 `/^[a-z0-9]+(?:-[a-z0-9]+)*$/` 校验，
  **含大写、下划线、首尾连字符或连续连字符的名字会被整个 skill 丢弃**
  （provider 只写一条 warning，catalog 里看不到，极易误判为「安装失败」）；
- `npx skills add` 会把**目录名**规范化为小写（例如 frontmatter 写 `RSI-pipeline` 时目录是
  `rsi-pipeline`），但 catalog 名仍取自 frontmatter —— 两者不一致时以 frontmatter 为准；
- 根目录被 watch：新增、改名、删除的 skill 无需重启即可进入下一轮 catalog；
- 多个根按上表 rank 顺序扫描；**不要依赖「同名后来者覆盖」这种未文档化的行为**——
  安装变体一律使用不同的 `name:`（见 §21.3）。

### 21.3 用不同名字安装同一组件的开发分支（后缀 `-rsi` 的做法）

**关键约束：** 安装后的 skill id 来自 frontmatter `name:`。因此**不要直接安装工作树**——
它与已安装的稳定版同名，会互相覆盖。正确做法是从分支导出一份干净副本、在副本里改名：

1. 从目标分支导出该组件的干净副本（只取版本库内容）到临时目录：

   ```sh
   git -C <worktree> archive <branch> <component> | tar -x -C <tmp>
   ```

2. 剔除只属于开发分支的产物与机器缓存：

   ```sh
   rm -rf <tmp>/<component>/.dev
   find <tmp>/<component> -name __pycache__ -type d -prune -exec rm -rf {} +
   ```

3. **只在这个安装副本里**修改 `SKILL.md` 的 frontmatter：

   - 把 `name:` 改为带后缀的**合法 kebab-case** 名字（例如 `research-idea-pipeline-rsi`、
     `rsi-pipeline`）；**不要用大写**（`RSI-pipeline` 会被 provider 静默丢弃）；
   - 建议在 `description:` 前加一行可区分的说明（例如「[RSI 开发版] 来自分支 X」），
     否则模型难以在稳定版与变体之间正确选择。

   **仓库里的 `SKILL.md` 不得为此改名**：`name:` 是组件身份，改名属于安装副本的本地适配。

   > 安装后若 catalog 里看不到：先核对 `name:` 是否满足上面的 kebab-case 语法
   > （这是最常见的「装上了但看不见」原因），再核对扫描根与 `SKILL.md` 是否在根目录顶层。

4. 安装：

   ```sh
   npx skills add <tmp>/<component> -g -y
   ```

5. 核对（应同时列出稳定版与后缀变体）：

   ```sh
   npx skills list -g
   ```

6. 卸载：`npx skills remove <带后缀的名字> -g -y`

**必须注意：**

- 安装副本**没有 `.git`**。组件内的发布闸门会自动跳过 tag 校验；实测该副本中
  `python3 scripts/release_check.py` 仍为 `PASS`。
- 安装副本里的 **schema id**（`research-idea-pipeline/...@1`）与**运行时目录**
  （`.research-idea-pipeline/routes/...`）保持原名：它们是数据契约与落盘路径标识，
  与 skill 的 catalog 名无关，改名会破坏兼容性。
- 用默认（符号链接）方式安装时，`<agentsHome>/skills/<name>/` 必须是**持久目录**。
  不要把源指向会被清理的 `/tmp` 目录；需要临时目录时用 `--copy`，或先把副本放到持久位置。
- 安装副本与本仓库工作树是两份独立内容：修改工作树不会自动更新已安装的 `--copy` 副本。

### 21.4 与开发流程的关系

- 安装副本属于**本机环境**，不是仓库内容：不得提交进仓库，也不得写入组件目录。
- `.dev/` 是开发分支产物，**不得**进入安装副本（见 §5、§13、§15）。
- L3 级别的「已安装版本」声明必须来自正式发布的 tag；分支安装副本只是本机测试环境，
  不代表发布了新版本（见 §6、§9）。
