<!--
路线级 README.md 骨架（与 routeX/INDEX.md 配套）。
用法：复制到 routeX/README.md。
职责：**本路线的说明** —— 做什么、怎么跑、目录怎么组织。
      进度与文档索引不要写在这里，写到 routeX/INDEX.md。
-->

# <routeX> — <一句话路线名>

> **本路线说明。** 进度与文档索引见 `INDEX.md`。跨路线信息见根目录 `../INDEX.md`。

## 1. 本路线做什么

- **核心目标（锚点）：** theory / performance / phenomenon / benchmark / feasibility / negative
- **研究问题：**
- **关键假设：**
- **目标会议：** CVPR / ICML / NeurIPS / MICCAI

## 2. 目录组织

```text
<routeX>/
├── README.md     # 本文件：本路线说明
├── INDEX.md      # 本路线索引：文档索引 + 关系图 + 进度
├── docs/         # ★ 本路线文档（扁平，不按类型分子目录）
│   ├── <R>001-literature-survey.md
│   ├── <R>002-ideas.md
│   ├── <R>003-proposal.md
│   ├── <R>004-experiment-plan.md
│   ├── <R>005-narrative.md
│   └── <R>003-review-r01.md
├── code/         # 本路线专属代码
└── experiments/  # 实验脚本与产物
```

> 参考文献不放这里 —— 统一在根目录 `docs/refs/`。

## 3. 怎么跑

```bash
# 环境自检（确认解释器与依赖）
python3 <skill>/scripts/literature_search.py --check-env

# 文献检索（默认全部源）
python3 <skill>/scripts/literature_search.py -q "<关键词>" --mailto you@example.com

# PDF 索引校验
python3 <skill>/scripts/refs_index.py --refs-dir docs/refs --check
```

## 4. 关键约定

- 文档命名与 ID 分配见本 Skill 的 `references/project-layout.md` §2。
- **本路线文档一律放 `docs/`，扁平。编号 `^<R>\d{3}-` 独立递增、永不复用。**
- 审阅命名 `<被审ID>-review-r01.md` / `-r02.md`（轮次零填充两位）。
- 路线之间**不得互相 import**。需要复用的下沉到根目录 `shared/`。
- 若项目根目录有 `AGENTS.md`，**以它为准**。

## 5. 当前状态

> 一句话即可。详细进度在 [INDEX.md](INDEX.md)。

- 当前阶段：
- 阻塞项：
