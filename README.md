# research-idea-pipeline

面向 **CVPR / ICML / NeurIPS** 投稿的研究创意全流程辅助 Skill。覆盖从文献调研、
idea 发现、方案生成到方案复核的完整链路。可单独调用任一 Mode，也可串联调用。

> **状态：已构建，待审核。** 本项目尚未安装到任何 skills 目录
> （`~/.claude/skills/`、`~/.agents/skills/` 等），仅在当前目录下作为独立项目存在。

---

## 目录结构

```
research-idea-pipeline/
├── SKILL.md                                  # 入口：mode 分发 + 全局不变量 + 状态传递
├── README.md                                 # 本文件
├── references/
│   ├── roles.md                              # 子代理角色库（11 个角色，全局共享）
│   ├── venue-standards.md                    # CVPR / ICML / NeurIPS 创新性标准
│   ├── literature-policy.md                  # 先本地后 arxiv + 429 退避 + 缓存规范
│   ├── mode-a-idea-discovery.md              # Mode A 完整流程（A1—A6）
│   ├── mode-b-proposal-generation.md         # Mode B 完整流程（B1—B6）
│   ├── mode-c-proposal-review.md             # Mode C 完整流程（C1—C7）
│   └── mode-d-literature-survey.md           # Mode D 完整流程（D1—D6）
├── scripts/
│   └── literature_search.py                  # 可运行的检索器（local-first + 429 backoff + cache）
├── templates/
│   └── state.template.json                   # state.json 片段模板（A/B/C/D）
├── examples/
│   ├── example-a-to-b-to-c.md                # 串联调用示例
│   ├── example-followup-review.md            # 接续复核示例
│   └── example-d-standalone.md               # 单独文献调研示例
└── local_literature/                         # 本地文献库（格式示例；实际默认指向用户工作目录）
    ├── papers/                               # {paper_id}.json + 可选 {paper_id}.md
    ├── cache/                                # {query_hash}.json
    └── index.json                            # 本地索引（可选）
```

---

## 四个 Mode

| Mode | 名称 | 作用 | 可独立调用 | 可被谁调用 |
|---|---|---|---|---|
| **A** | `idea-discovery` | 基础文献调研 + 多子代理头脑风暴，产出 idea 候选 | 是 | — |
| **B** | `proposal-generation` | 基于 idea 做创新性与可行性研究，产出方案 | 是 | 接 A 之后 |
| **C** | `proposal-review` | 复核已有方案与审阅内容的正确性与创新性 | 是 | 接 B，或接上一次 C 继续复核 |
| **D** | `literature-survey` | 补充文献、扩大检索范围 | 是 | 被 A/B/C 调用，也可单独调用 |

**串联链路：**

```
[用户输入]
    │
    ├─ Mode D（可独立）──────┐
    │                        │
    ├─ Mode A ──→ Mode B ──→ Mode C ──→ Mode C（接续）
    │      ↑         ↑          ↑
    │      └─ D ─────┴──── D ───┘
    │
    └─ 任意 Mode 可单独调用
```

---

## 三条全局硬约束

1. **文献检索：先本地，后 arxiv；429 必须等待。**
   本地命中即返回、不请求 arxiv；429 按 `10s → 20s → 40s → 80s → 160s` 指数退避，
   最多 5 次，退避期间不发起新请求；5 次失败则回退本地结果并明确标注。
   所有 arxiv 结果写入 `local_literature/cache/`，每条结果标注 `source`。
2. **顶会标准锚定。** 创新性判定必须引用 CVPR / ICML / NeurIPS 的具体标准；
   贡献必须标注类型；"首次提出"声称必须经 S-Lit 核实。
3. **输出规范。** 结构化报告；引用给出 `[作者, 会议/年份]`；无法确认标注"待核实"，
   不得臆造；"没做到"必须关联具体未建立的结构性质或未满足的理论条件。

---

## 命令行检索器

```bash
# 本地优先；未命中走 arxiv
python3 scripts/literature_search.py --query "diffusion model combinatorial optimization" --max 20

# 限定年份 + 强制刷新（跳过本地命中与缓存）
python3 scripts/literature_search.py --query "..." --from-year 2022 --to-year 2025 --refresh

# 指定本地库位置，输出完整 JSON
python3 scripts/literature_search.py --query "..." --local-dir ./local_literature --json
```

**参数：**

| 参数 | 默认 | 说明 |
|---|---|---|
| `--query` / `-q` | 必填 | 检索关键词或研究问题 |
| `--max` / `-n` | `20` | 最多返回条数 |
| `--from-year` / `--to-year` | 无 | 年份过滤（含端点） |
| `--local-dir` | `./local_literature` | 本地文献库；也可用 `RESEARCH_LOCAL_LITERATURE` |
| `--cache-dir` | `<local-dir>/cache` | 缓存目录 |
| `--refresh` | 关 | 强制跳过本地命中与缓存 |
| `--no-cache` | 关 | 不使用缓存（仍会写入） |
| `--json` | 关 | 输出完整 JSON |
| `--quiet` | 关 | 不输出过程日志 |

**退出码：** `0` 正常；`1` 硬错误；`2` arxiv 不可用但已回退到本地结果。

**运行时依赖：** `arxiv`（`pip install arxiv`）。未安装时脚本自动回退到本地结果，
不会崩溃。

---

## 本地文献库格式

```
local_literature/
├── papers/
│   ├── {paper_id}.json      # 元数据：title/authors/abstract/year/venue/url
│   └── {paper_id}.md        # 可选：全文或笔记（参与全文匹配）
├── cache/
│   └── {query_hash}.json    # arxiv 查询缓存
└── index.json               # 可选
```

单条元数据：

```json
{
  "paper_id": "2401.01234",
  "title": "...",
  "authors": ["..."],
  "abstract": "...",
  "year": 2024,
  "venue": "NeurIPS",
  "url": "https://arxiv.org/abs/2401.01234",
  "keywords": ["..."],
  "source": "local"
}
```

---

## 状态传递

每个 Mode 输出附加 `state.json` 片段（模板见
[templates/state.template.json](templates/state.template.json)）：

```json
{
  "mode": "A",
  "timestamp": "...",
  "idea_candidates": [],
  "literature_used": [],
  "open_questions": [],
  "next_mode_suggestion": "B"
}
```

接续规则：B 读 A 的 `idea_candidates`；C 读 B 的 `proposal` + `experiment_plan`；
接续 C 读上一次 C 的 `review_output` + `open_questions`；任意 Mode 调用 D 时传递
`query` + `scope`。

---

## 与规范的两点工程修正

原规范伪代码中有两处会在真实环境中失效，已在 `scripts/literature_search.py` 与
`references/literature-policy.md` §2.1 中修正：

1. **`arxiv.HTTPError` 并非 arxiv 包稳定导出的异常。** 实际 429 多为
   `urllib.error.HTTPError`（`.code`）或带 `.response.status_code` 的异常。
   脚本采用兼容捕获（`status` / `code` / `status_code` / 异常文本中的 `429`）。
2. **`hash(query)` 跨进程不稳定**（受 `PYTHONHASHSEED` 影响），不能作缓存文件名。
   脚本改用 `hashlib.md5(query)[:16]`，保证缓存真正可命中。

此外新增了"查询缓存"作为本地与 arxiv 之间的一层：命中缓存时直接返回并标注
`source="arxiv"`（含 `cache_hit: true`），进一步减少 arxiv 请求，符合"缓存机制
进一步减少重复请求"的设计意图。

---

## 安装（待审核通过后再执行）

本项目刻意**未**安装。审核通过后，任选其一：

```bash
# 软链接到个人 skills 目录（推荐，便于继续迭代）
ln -s "$PWD/research-idea-pipeline" ~/.claude/skills/research-idea-pipeline

# 或复制
cp -r research-idea-pipeline ~/.claude/skills/
```

安装后通过 `mode=A|B|C|D` 触发调用。
