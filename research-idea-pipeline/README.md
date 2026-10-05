# research-idea-pipeline

面向 **CVPR / ICML / NeurIPS** 投稿的研究创意全流程辅助 Skill。覆盖文献调研、idea
发现（含 idea 级审核）、方案生成、**多套路叙事生成与审稿**、方案复核的完整链路。
可单独调用任一 Mode，也可串联调用。

**字母顺序 = 工作流顺序：**

```
A 文献调研 → B idea 发现 → C 方案生成 → D 叙事生成 → E 方案复核
```

> **状态：已构建，待审核。** 本项目尚未安装到任何 skills 目录
> （`~/.claude/skills/`、`~/.agents/skills/` 等）。

---

## 目录结构

```
research-idea-pipeline/
├── SKILL.md                          # 入口：mode 分发 + 全局不变量 + 状态传递
├── README.md                         # 本文件
├── references/
│   ├── roles.md                      # 11 个共享子代理角色 + Mode D 叙事审核量表
│   ├── venue-standards.md            # CVPR / ICML / NeurIPS 标准 + 防复现标准
│   ├── narrative-patterns.md         # 十套叙事套路 + 跨域五步升级 + 叙事包装
│   ├── literature-policy.md          # 禁止只停留在本地；T1—T7 扩检；L1/L2/L3；饱和判据
│   ├── project-layout.md             # docs/ 命名、INDEX.md、AGENTS.md、shared/
│   ├── mode-a-literature-survey.md   # Mode A：文献调研（A1—A7）
│   ├── mode-b-idea-discovery.md      # Mode B：发现 + idea 级审核（B0—B8）
│   ├── mode-c-proposal-generation.md # Mode C：方案生成（C1—C7）
│   ├── mode-d-narrative-generation.md# Mode D：多套路叙事 + 五子代理审稿（D0—D8）
│   └── mode-e-proposal-review.md     # Mode E：方案级正确性 + 防复现（E0—E8）
├── scripts/
│   ├── literature_search.py          # 可运行检索器（本地+arxiv 并集 / 429 backoff / 缓存 / 代理检测）
│   └── refs_index.py                 # 为 docs/refs/ 下每个 PDF 建 index.json（--check 校验）
├── templates/
│   ├── INDEX.md                      # 路线 INDEX.md 骨架（必需）
│   └── state.template.json           # state.json 片段模板（键 = A—E）
├── examples/
│   ├── example-b-to-c-d-e.md         # 主链路串联
│   ├── example-d-narrative.md        # 多套路叙事与选型
│   ├── example-a-standalone.md       # 单独文献调研
│   ├── example-followup-review.md    # 接续复核
│   └── example-project-layout.md     # 多路线目录与文档管理
└── docs/refs/                        # 参考文献库格式示例（目标项目里放根目录 docs/refs/）
```

---

## 开工前：锚定点与派遣方式

### 锚定点（核心目标）—— **必须先问，不得猜**

开始任何 Mode 之前，先与用户确认本工作的核心目标。用户没说就**反问**，
**不要默认成"提高性能"**。**未确认前不得开工。**

| 锚点 | 核心目标 | 成功判据 | 贡献类型 |
|---|---|---|---|
| **理论** | 提出并验证理论：定理 / 界 / 不可能性 / 统一框架 | 命题成立、证明无缺口、假设必要且紧 | Theory |
| **性能** | 提高某个任务 / 指标的绝对性能 | 公平比较下超过最强基线 | 方法 |
| **现象** | 发现并解释反直觉现象 | 解释唯一且具预测力 | 实证 |
| **基准** | 揭示现有评测掩盖的失败 | 基准暴露真实失败模式 | 实证 / 问题定义 |
| **可行性** | 把不可行 / 过贵的方法变可行 | 保持理论保证同时显著降本 | Concept & Feasibility |
| **负结果** | 证明某目标在一定条件下不可能 | 不可能性成立且给出可达松弛 | Negative Results |

- **允许组合，但必须指定主锚点**（如"主锚点 = 理论，次锚点 = 可行性"）。
- **锚点必须落盘：** 文档 frontmatter 的 `core_goal`、`INDEX.md` 路线概要、`state.json`。
- **锚点变更必须显式记录**，并重新审视老锚点下产出的 idea / 方案 / 叙事 / 审阅结论。
- **锚点与产出不一致时必须当场指出**（如性能锚点却没做同算力公平比较）。

锚点如何约束各 Mode：A 定**检索边界**、B 定**推导与筛选**、C 定**贡献类型与实验**、
D 定**叙事套路**（见[锚点 → 套路映射](references/narrative-patterns.md)）、
E 定**评审侧重**。

### 派遣方式：Team 优先询问

**派发子代理前先判断环境是否具备 Team 能力**（可创建持久、可被寻址的 teammate，
如 Agent Teams）：

| # | 情形 | 处理 |
|---|---|---|
| 1 | **具备** Team 能力 | **必须先询问用户是否使用 Team**，不得自行决定。用户要求用 → 用 Team；不要或未表态 → 默认子代理 |
| 2 | **不具备**，用户也没提 | 用默认子代理，无需询问 |
| 3 | 用户**显式要求 Team** 但环境不具备 | **回退到默认子代理**，并**显式告知"当前环境无 Team 能力，已回退"** |

- **不得静默降级**；**不得假装使用了 Team**；**不得因"更高级"就默认启用**。
- **方式不改变标准：** 角色库、派遣矩阵、评分维度、交叉质询与中位数规则完全一致
  （见 [roles.md](references/roles.md) §4.1）。
- 用 Team 时必须守**写作用域**：并行写者写互不重叠的文件；写冲突按
  "重新读取后再提交"处理。

---

## 五个 Mode

| Mode | 名称 | 作用 | 可独立调用 | 可被谁调用 |
|---|---|---|---|---|
| **A** | `literature-survey` | 补充文献、扩大检索范围 | 是 | 被 B/C/D/E 调用，也可单独调用 |
| **B** | `idea-discovery` | 文献调研 + 多子代理头脑风暴产出 idea，**并做 idea 级创新性/可行性审核** | 是 | 接 A 之后 |
| **C** | `proposal-generation` | 基于 idea 做创新性与可行性研究，产出方案 | 是 | 接 B 之后 |
| **D** | `narrative-generation` | **基于 idea + 方案**生成多种顶会风格叙事逻辑，并拉起子代理评审，筛出最佳叙事 | 是 | 接 B（仅 idea）或接 C（推荐） |
| **E** | `proposal-review` | 复核**已成型方案**的正确性与可行性，并守创新性底线（防复现） | 是 | 接 C/D，或接上一次 E |

### 各阶段的分工

> **B 决定"做不做"，C 决定"做什么"，D 决定"怎么讲"，E 决定"做得对不对"。**

| 维度 | Mode B（idea 级） | Mode E（方案级） |
|---|---|---|
| 对象 | 一句话级 idea / 技术方向 | 成型的 proposal + 实验计划 |
| 可行性 | 概念可行性：路线是否成立 | 工程可行性：具体做法能否跑通、变量是否可控 |
| 正确性 | 前提是否自洽 | 方法正确性：推导/实现/指标/统计是否成立 |
| 创新性 | 方向是否已被覆盖、是否非平凡 | 方案是否**实质复现**已有工作 |
| 复现性 | 不涉及（不派 S-Repro） | 必查（S-Repro + 防复现六项检查） |
| 深度 | 快筛：双评分 + 致命反驳 | 深审：七子代理 + 交叉质询 + 中位数 |

Mode E 的结论卡片**必须**给出复现风险等级；**复现风险 = 高时总体判定不得为"高"**。

### Mode D：多套路叙事（本 Skill 的差异化能力）

同一 idea 在不同叙事下，审稿人的接收意愿差异显著。Mode D 因此：

1. 从[十套套路](references/narrative-patterns.md)中为每个 idea 选 **≥4 套**生成叙事；
2. 跨域类 idea 强制走**五步升级**（结构性缺陷 → 结构同构 → 迁移合法性 → 新算法 → 实证）；
3. 拉起 **5 个维度化子代理**（R-CVPR / R-ICML / R-NeurIPS / S-Devil / S-Lit）打分；
4. **综合评分必须覆盖全部维度，不得只看创新性**；**聚合前先做极性归一化**（S-Devil 的反驳分是 5=完全无新颖性、越低越好，须转为**新颖性稳健度 = 6 − 反驳分**），**归一化后任一维度中位数 ≤ 2** 一票否决（见 [mode-d §D4.1](references/mode-d-narrative-generation.md)）；
5. 完成**叙事包装 = 重新定位，不是夸大**：只改参照系，不改事实，每句声称都要能在
   方案里找到证据。

---

## 三条全局硬约束

### 1. 文献检索：先本地，后 arxiv —— **禁止只停留在本地**

本地是**起点与排序依据，不是终点**。凡触发下列任一条件，必须查 arxiv 并扩大范围：

| # | 触发条件 | 最低等级 |
|---|---|---|
| T1 | **创新性声明**（"首次提出 / 没人做过 / 首个 / 该方向空白"） | **L3 穷尽** |
| T2 | **理论不清**（证不出来、假设无法验证、收敛性说不清） | L2 强化 |
| T3 | **可行性不确定** | L2 强化 |
| T4 | 新颖性判定（C1、D3.2、E2.2） | **L3 穷尽** |
| T5 | 本地命中不足（< 5 条） | L2 强化 |
| T6 | 用户要求"尽可能多 / 彻底查" | **L3 穷尽** |
| T7 | "现有工作尚未……"式论断 | L2 强化 |

- **尽职调查等级：** L1 快速 / L2 强化（≥4 检索式）/ L3 穷尽（≥8 检索式，含否定式与负结果）。
- **饱和判据：** 连续两轮扩大检索零新增、或达上限、或达标且新增趋零。
  **未达饱和就停止属于违规。**
- **禁止推断：** 本地未命中 ≠ 不存在；arxiv 未见 ≠ 无人研究过；429 中断 ≠ 检索完整。
- **创新性声明门禁：** 完成 L3 + S-Lit 核实 + 负检索记录，三项缺一只能写
  **"据本次检索未见"**，不得写"首次提出"。
- **卡点第一动作是检索：** 理论证不出、不确定能不能做时，先查该问题本身、相邻领域
  的处理方式、以及**负结果文献**。

**代理环境识别：** 发起 arxiv 请求前先解析 `arxiv.org` / `export.arxiv.org`。
**若解析到本地 IP**（回环 / 私有网段 / 链路本地 / `0.0.0.0`，例如 Clash 的
`198.18.x.x` fake-IP），说明**可能存在代理环境**——DNS 已被 hosts 或本地代理接管。
此时：① 报告中单列「代理环境提示」并写明**具体 IP**；② **不得**据此判定
"arxiv 不可用"或"无人在研究"；③ 代理链路上的 429 **未必**是 arxiv 官方限流；
④ 用于支撑创新性声明时记入 INDEX 的 Warnings。**只告警，不阻断。**

### 2. 顶会标准锚定

创新性判定必须引用 CVPR / ICML / NeurIPS 的具体标准；贡献必须标注类型；
"首次提出"必须经 S-Lit 核实。Mode E 另有**防复现六项检查**与复现风险等级。

### 3. 输出规范

结构化报告；引用给 `[作者, 会议/年份]`；无法确认标注"待核实"，**不得臆造**；
"没做到"必须关联具体未建立的结构性质或未满足的理论条件。

---

## 项目组织与文档落盘

```
<项目根目录>/
├── AGENTS.md              # 共享契约；存在则优先遵循
├── docs/                  # ★ 所有路线的文档集中于此（扁平，不分子目录）
│   ├── A001-literature-survey.md
│   ├── A002-ideas.md      # 含 I1..In 与 B5 审核
│   ├── A003-proposal.md
│   ├── A004-experiment-plan.md
│   ├── A005-narrative-I1.md
│   ├── A003-review.md
│   ├── B001-literature-survey.md   # routeB 的文档同目录，靠 B 前缀区分
│   └── refs/              # ★ 参考文献库（= 本地文献库根目录）
│       ├── papers/        # {paper_id}.pdf（不进版本库）+ .json sidecar + 可选 .md
│       ├── cache/         # {query_hash}.json
│       └── index.json     # ★ 必需：PDF 索引，进版本库
├── routeA/
│   ├── INDEX.md           # ★ 必需：索引到 ../docs/A*
│   └── code/
├── routeB/
│   └── INDEX.md
├── shared/                # 跨路线公用代码/笔记
└── .research-idea-pipeline/   # 机器状态（不入 docs）
```

| 规则 | 说明 |
|---|---|
| 命名 | `docs/<路线字母><NNN>-<slug>.md`；审阅为 `<ID>-review.md`，接续为 `-review-2.md` |
| 存放 | **所有路线共用根目录 `docs/`（扁平）**，靠文件名前缀区分路线；参考文献在 `docs/refs/` |
| slug 枚举 | `literature-survey` / `ideas` / `proposal` / `experiment-plan` / `narrative-I<n>` |
| 子编号 | `I<n>` idea、`N<k>` 套路、`K<n>` 贡献、`E<n>` 实验、`H<n>` 假设；引用写作 `<文档ID>/<子编号>` |
| ID | 按路线独立递增、永不复用；审阅记录不占新序号 |
| 文档 ID 前缀 | `A`/`B` 是**路线编号**，与 Mode A—E 无关；Mode 记在 frontmatter |
| INDEX.md | 每条路线必需，每次产出后更新 |
| 进度必须包含 | **已证实 / 已证伪 / TODO / Bugs / Warnings** + 文档索引 + 变更日志 |
| 负结果 | 被证伪的假设**不得删除**，保留并注明处置 |
| 机器状态 | 进 `.research-idea-pipeline/`，**不进 docs** |
| **PDF 索引** | **`docs/refs/` 下每个 PDF 必须在 `docs/refs/index.json` 有记录**；索引进版本库、PDF 不进 |

完整规范见 [references/project-layout.md](references/project-layout.md)（含手工建立
骨架的检查清单）。骨架可参考 [templates/INDEX.md](templates/INDEX.md)。

---

## 命令行检索器

```bash
# 默认：本地 + arxiv 并集（不会因本地命中而跳过 arxiv）
python3 scripts/literature_search.py --query "diffusion model combinatorial optimization" --max 20

# 创新性声明：L3 穷尽 + 自动扩检 + 追加同义词/否定式检索式
python3 scripts/literature_search.py --query "discrete diffusion combinatorial optimization" \
    --level L3 --exhaustive \
    --also-query "score-based generative model discrete optimization" \
    --also-query "limits of diffusion model combinatorial optimization" \
    --json

# 离线：显式只用本地（会打印规则违反提示；不得支撑创新性声明）
python3 scripts/literature_search.py --query "..." --local-only
```

| 参数 | 默认 | 说明 |
|---|---|---|
| `--query` / `-q` | 必填 | 检索关键词或研究问题（支持中文） |
| `--max` / `-n` | `20` | **每次 arxiv 查询**的条数上限；本地命中不受此限制 |
| `--limit` | 不截断 | 最终返回条数上限（截断时保留本地优先顺序，并报告截断量） |
| `--from-year` / `--to-year` | 无 | 年份过滤（含端点；启用过滤时**年份未知的条目被排除**） |
| `--level {L1,L2,L3}` | 无 | 尽职调查等级，输出达成情况（饱和只对 L2/L3 是硬要求） |
| `--exhaustive` | 关 | 自动执行 A3 第 ②④ 级扩大检索直到饱和 |
| `--also-query` | 无 | 追加检索式（可重复）；A3 第 ①③ 级需人工构造 |
| `--local-only` | 关 | **显式**只用本地（违反默认规则；**不得用于支撑创新性声明**） |
| `--local-dir` | `./docs/refs` | 本地库；亦可用 `RESEARCH_LOCAL_LITERATURE` |
| `--cache-dir` | `<local-dir>/cache` | 缓存目录；亦可用 `RESEARCH_LIT_CACHE` |
| `--refresh` | 关 | 跳过缓存（仍查本地与 arxiv，可与 `--exhaustive` 同用） |
| `--no-cache` | 关 | 不读缓存（结果仍会写入缓存） |
| `--json` / `--quiet` | 关 | JSON 输出 / 静默 |

**退出码：** `0` 正常；`1` 硬错误（含参数错误、渲染失败）；`2` arxiv
不可用、已回退本地结果（**检索未达饱和**）。

**依赖：** `arxiv`（`pip install arxiv`）。未安装时自动回退本地结果，不会崩溃。

**输出：** 文献列表（含 `source`）+ 检索过程记录 + 429 等待日志 + 缓存更新记录 +
范围扩大记录 + **逐检索式的负检索记录** + **饱和判定与等级达成情况**。

---

## 参考文献库格式（`docs/refs/`）

**参考文献统一放项目根目录的 `docs/refs/`**，它同时就是检索脚本的本地文献库根目录
（脚本默认 `--local-dir ./docs/refs`）。

```
docs/refs/
├── index.json                 # ★ PDF 索引（强制，进版本库）
├── papers/{paper_id}.pdf      # PDF 原文（大文件，不进版本库）
├── papers/{paper_id}.json     # sidecar 元数据：title/authors/abstract/year/venue/url
├── papers/{paper_id}.md       # 可选：全文或笔记（参与全文匹配）
└── cache/{query_hash}.json    # arxiv 查询缓存（键含 max_results 与年份）
```

### ★ PDF 必须入索引

**`docs/refs/` 下的每一个 PDF，都要在 `docs/refs/index.json` 里有一条记录**，包含
`file` / `paper_id` / `title` / `authors` / `year` / `arxiv_id` / `doi` / `url` /
`abstract` / `keywords` / `pages` / `size_bytes` / `sha256` / `added_at` / `source` /
`metadata_from` / `needs_verification`。

**索引进版本库，PDF 不进** —— 别人 clone 到的是完整文献清单，不必下载几十 GB 原文。

```bash
python3 scripts/refs_index.py            # 扫描 ./docs/refs，写入 ./docs/refs/index.json
python3 scripts/refs_index.py --check    # 只校验；不一致时退出码 3
```

| 元数据来源 | 说明 |
|---|---|
| `papers/{paper_id}.json`（sidecar） | 最准，检索脚本写入 |
| PDF 内嵌元数据 | `pypdf`；缺失时回退命令行 `pdfinfo` |
| 文件名解析 | 兜底；此时 `needs_verification = true` |

**未入索引的 PDF 视为不存在**；新增/替换/删除 PDF 后**必须重建索引**；
`needs_verification = true` 的条目**不得**用于支撑创新性声明。

完整字段约定见 [references/literature-policy.md](references/literature-policy.md) §7.1。

---

## 状态传递

每个 Mode 输出附加 `state.json` 片段（模板见
[templates/state.template.json](templates/state.template.json)，键名 = Mode 字母 A—E）。
机器状态写入 `.research-idea-pipeline/`，人类可读产出写入 `docs/`。

接续规则：

- Mode C 读取 Mode B 的 `idea_candidates`（含 B5 的 `review` 评分）。
- Mode D 读取 Mode B 的 idea 与 Mode C 的 `proposal`。
- Mode E 读取 Mode C 的 `proposal` + `experiment_plan`，以及 Mode D 的最佳叙事推荐。
- 接续 E 读取上一次 E 的 `review_output` + `open_questions`。
- 任意 Mode 调用 Mode A 时，传递 `query` + `scope` + `level`。

---

## 相对原规范的四点工程修正

原规范中有四处在真实环境会失效，已修正并记录在
[literature-policy.md §5.2 / §5.3](references/literature-policy.md)：

1. **`arxiv.HTTPError` 并非 arxiv 包稳定导出的异常。** 实际 429 多为
   `urllib.error.HTTPError`（`.code`）或带 `.response.status_code` 的异常。
   脚本兼容捕获 `status` / `code` / `status_code` 及异常文本中的 `429`。
2. **`hash(query)` 跨进程不稳定**（受 `PYTHONHASHSEED` 影响），不能作缓存文件名。
   改用 `hashlib.md5(...)[:16]`。
3. **缓存键必须含检索参数。** 只按 query 建键会导致"用更大的 `--max` 复跑却命中旧的
   小结果集"，直接损害 L3 与扩检索质量。缓存键 = `md5(query|max|from_year|to_year)`。
4. **"本地命中即返回"被取消。** 本地检索改为起点而非终点；默认取本地 + arxiv 的
   并集，只有显式 `--local-only` 才跳过 arxiv（并打印规则违反提示）。

---

## 安装（待审核通过后再执行）

本项目刻意**未**安装。审核通过后：

```bash
ln -s "$PWD/research-idea-pipeline" ~/.claude/skills/research-idea-pipeline
```

安装后通过 `mode=A|B|C|D|E` 触发调用。
