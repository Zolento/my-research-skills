<!--
项目共享契约骨架（可选）。项目自行决定是否采用；采用时放到项目根目录并命名为 AGENTS.md。
本文件一经存在，其约定优先于 research-idea-pipeline 的默认约定。
-->

# AGENTS.md — 项目共享契约

> 本文件是本项目**所有协作者（人 + 代理）**的唯一共享契约。
> **开工前先读本文件，再读目标路线的 `INDEX.md`。**
> 与 `research-idea-pipeline` Skill 默认约定冲突时，**以本文件为准**。

最后更新：<YYYY-MM-DD>

---

## 1. 项目概览

- **项目名：**
- **总目标：**
- **目标会议：** CVPR / ICML / NeurIPS
- **负责路线：** routeA, routeB, …

## 2. 目录结构

```
.
├── AGENTS.md              # 本文件
├── docs/                  # 人类可读文档，按路线分目录
│   ├── routeA/            # A001-*.md, A001-review.md …
│   └── routeB/
├── routeA/                # 路线 A：代码 + 实验
│   ├── INDEX.md           # 必需
│   └── code/
├── routeB/
│   └── INDEX.md
├── shared/                # 跨路线公用部分
│   ├── code/
│   ├── literature/        # 公用文献库
│   └── docs/
└── .research-idea-pipeline/   # 机器状态（不入 docs）
```

## 3. 命名与文档规则

- 文档 ID：`<路线字母><三位序号>`，如 `A001`、`B012`；序号按路线独立递增、永不复用。
- 交付物：`docs/<routeX>/<ID>-<slug>.md`
- 审阅记录：`docs/<routeX>/<被审ID>-review.md`；接续复核为 `-review-2.md`。
- 每份文档必须有 YAML frontmatter（`id/route/mode/type/status/created`）。
- **禁止**把 JSON、日志、traceback 贴进 docs 正文。

## 4. 路线隔离规则

- 路线之间**不得互相 import**；需要复用的一律下沉到 `shared/`。
- 每条路线维护自己的 `INDEX.md`，**单写者**：同一时刻只允许一人改一条路线的 INDEX。
- 新增文档序号分配必须串行化（先读最大序号，再写入）。

## 5. 公用部分（shared/）规则

- 放入 `shared/` 的条件：**被 ≥2 条路线使用**。
- 修改 `shared/` 前必须先读当前内容，并在 `shared/CHANGELOG.md` 记录变更。
- `shared/` 的接口变更必须同步通知所有使用方。

## 6. 实验与代码规范

- 每个实验有唯一编号（E1, E2…），与 INDEX.md 的 TODO 对应。
- 实验结果写入 `routeX/experiments/<E编号>/`，包含配置、命令、原始输出、结论。
- 固定随机种子并记录；不记录种子的结果视为无效。
- 失败实验保留，结论写入 INDEX.md 的**已证伪**。

## 7. 文献检索规范

- **先本地，后 arxiv；不得只停留在本地。**
- 创新性声明、理论不清、可行性不确定时必须执行强化/穷尽级检索（L2/L3）。
- 未完成 L3 前，文档不得出现"首次提出"；只能写"据本次检索未见"。
- 检索未达饱和（如 arxiv 429 失败）必须记入 `INDEX.md` 的 Warnings。

## 8. 提交规范

- 提交信息格式：`<type>(<route>): <描述>`，type ∈ feat|fix|exp|docs|chore。
- 提交前更新对应 `INDEX.md`。
- 不提交大文件、数据集、密钥。

## 9. 分工（可选）

| 角色 | 负责范围 | 写权限 |
|---|---|---|
| — | — | — |
