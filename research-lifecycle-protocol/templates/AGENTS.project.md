# AGENTS.md — 执行契约（RLP v2.4 模板）

本文件只管**执行边界**：入口、写入范围、文件归属、交付检查。它**不复制**科研阶段流程、
state schema、证据等级、指标口径、代码风格清单。那些内容在 RLP Skill 与项目冻结协议里，
各有唯一权威。采用本模板**不触发迁移、Bootstrap 或新建目录**。

## 0. 四层分工

| 层 | 载体 | 只管 |
|---|---|---|
| 执行边界 | **本文件** | 谁在什么时候、可以把什么写到哪个路径 |
| 科研生命周期 | RLP Skill（`research-lifecycle-protocol`） | R0—R14、state、证据资格、审查与决策门禁 |
| 具体实验 | 项目契约 + 预注册 + 冻结配置 | 数据划分、判据、预算、指标实现 |
| 目录合规 | RLP `scripts/layout_guard.py` | DI-1—DI-8 的机械判定（路径类型、登记、扁平、软链接） |

**本文件不写**：R 阶段说明、state 字段、claim 状态枚举、攻击面清单、指标公式、PEP 8 细则。
需要时读 Skill 的对应 reference。

## 1. 启动与权威

1. 先读本文件、根 `README.md`、根 `INDEX.md`，确认任务对应的 route、允许改动范围与现有文件。
   不从聊天摘要推断当前状态。
2. Skill 固定为 `research-lifecycle-protocol`。核验实际加载的 `SKILL.md` 路径、版本与 commit，
   区分安装版与开发版。只加载当前任务需要的 L0/L1、一个 Preset 与领域切片。
3. 科研工作按 RLP 四个语义入口选择：`start-project` / `continue-research` / `explore` / `audit`。
   已有有效 state 只能 Resume，不得重新 Bootstrap。先用 **Skill 目录下**
   `python3 scripts/rlp_paths.py resolve <项目根>` 判定存储。需迁移或根不明确时只读 `HOLD`。
4. `.research-lifecycle-protocol/routes/<R>/research-state.json` 是科学事实的唯一机器源。
   实验 issue/run、outcome 与 state 回写必须走 RLP 门禁。`STATUS.md` 由投影生成，不手改结论。
5. **优先级**：用户当前指令 ＞ 已冻结实验协议 ＞ 本文件的布局与写入范围 ＞ RLP 默认布局。
   **RLP 的状态转换、证据资格与强制门禁不受上述顺序影响。布局可以让，门禁不能让。**
   遇到冲突时列明受影响操作并停下，不暗自选一种继续。

## 2. 路径与文件归属

**先复用现有文件。新增前依次确定产物类型、route/XID/ID、目标路径，跑一次路径预检，再写。**
不擅自建顶层目录、平行 `docs*/results*/logs*`、新 route、`R0`—`R14` 目录、路线内代码副本。

| 类型 | 允许位置 |
|---|---|
| 可复用实现 / 入口 / 测试 | `src/` / `scripts/` / `tests/`，`tests/` 不放生产入口 |
| 配置 | `configs/`，路线差异在 `configs/routes/<R>/` |
| 正式路线文档与审查 | `routes/<R>/docs/<R><NNN>-<slug>.md`，**扁平、无子目录**，ID 与 frontmatter 由 RLP 规范决定 |
| 项目级资料 | `docs/refs/`、`docs/dev/`、`docs/latex/`、`docs/decisions/`，路线正式文档不进根 `docs/` |
| 正式实验登记 | `experiments/<R>/<XID>-<slug>/`，只放 `README.md` / `manifest.json` / `config.yaml` |
| 结果 / 日志 / 权重 | `results/<R>/<XID>/` / `logs/<R>/<XID>/` / `checkpoints/<R>/<XID>/`，按 run 隔离 |
| 状态、历史、原始子代理件、scratch | `.research-lifecycle-protocol/` 内 RLP 规定位置，scratch 放 `runtime/` |

`dataset/` 与 `store/` 只读。远程软链接不擅自覆盖、搬迁、清理。

```bash
# 写入前（逐个产物）
python3 <skill>/scripts/layout_guard.py preflight --kind <类型> --path <相对路径>
# 提交前（只看 Git 新增与暂存新增）
python3 <skill>/scripts/layout_guard.py check
# 定期审计（全树，block 与 warn 分级）
python3 <skill>/scripts/layout_guard.py audit
```

未安装脚本时人工列出类型、目标路径与 RLP 依据，**不得声称门禁已通过**。
路径例外只登记在 `.research-lifecycle-protocol/project/layout-policy.json`，须用户授权且模式窄
（`paper/*.tex` 可以，`**/*.md` 拒绝）。路径预检不代替科研门禁。

## 3. 执行顺序与收尾

- **开工**：`git status`。读现有 route state、冻结配置、数据与环境说明。新实验先走 RLP
  issue/run，不先建 XID 目录。
- **执行**：最小范围修改，复用项目统一算子、配置与评估口径。改动算子时核对 shape、dtype、
  device、复数与 FFT/伴随关系。测试代码与必要 smoke。未经授权不增加种子、算力或测试集调参。
- **收尾**：核对 diff 与文件归属。保存实际配置、commit 与指标。按 RLP 门禁回写证据与 state，
  刷新派生视图。报告完成项、核验结果与未解决问题。**smoke 不是科学证据。**
- **AI 生成内容**在提交说明或注释标记 `[AI-gen]`。

- **关键不确定性一次问完**：先查既有冻结协议、代码、数据元信息、配置与 RLP state。
  若仍有影响实验设计、数据、算子、指标、预算或写入权限的未决事项，暂停**受影响操作**，
  把全部未决项合并成一份清单一次性询问，每项给出影响范围与推荐选项。
  不得自行选默认值后继续，不得拆成连续碎片化提问，已记录的事项不重复问。
  不受影响的只读工作照常进行。
- **训练前报告不可省略**：按编号完整呈报配置与授权状态，形态见
  `references/scientific-communication-policy.md` §1.3。MRI 训练必报 CSM 模式、来源与样本
  配对键，其余必报项由受管段第 7 条规定。
  正常通过的内部审计不逐项罗列，详细记录留在项目标准日志。

## 4. 权限与协作

用户未授权时不得：新建路线或改研究锚点、扩大预算、改冻结协议、删改历史证据、重建 state、
强推、停止他人任务、修改全局环境。已授权范围内不重复询问。

启用 DSH Research Mesh 时遵循 `dsh-research-mesh/mesh-collaboration@1`：canonical checkout
只有一个，worktree 是临时检出而非 route 副本，worker 只写分配范围，canonical state 与公共索引
单写者维护。未启用时不建 Mesh 目录。

## 5. MRI 训练受管条款

MRI 重建项目按 RLP `domain-profiles/mri-reconstruction/training-policy.md` 执行，用 **Skill 自带**的
`python3 scripts/mri_training.py sync-agents <项目根>` 注入 `BEGIN/END RLP MRI TRAINING` 受管章节，
**不手改，也不手工复制第二份 MRI 文字**。训练前检查协议冲突与生效配置并报告。
重点关注 2D 单方向 Cartesian 的列采样与 per-slice mask 配对、默认强制数据集原始 CSM
（仅显式联合估计灵敏度的方法例外）、纯伴随禁止隐式补偿、GT 幅度 RMS 共同尺度，
以及 `full_val_gt` 与 `gt_free_frozen` 两种合法选模。
数据、FFT、mask、CSM 与评估尺度的项目取值以现行冻结协议为准，
不把某个数据集口径推广到所有 MRI。冲突时暂停受影响训练并上报。

## 6. 项目配置（采用前填写）

- canonical 仓库：`<绝对路径>`，当前 route 与主锚点：`<根 INDEX.md>`
- RLP Skill 根 / 版本 / commit：`<绝对路径> / <version> / <sha>`
- 冻结实验协议与环境入口：`<既有协议与 README>`
- 数据、产物与服务器映射：`<既有存储文档>`（不自动建 `store` 链接）
- 经批准的非标准路径：`<layout-policy.json 路径或 none>`，Mesh：`disabled` 或 `<配置>`

> 受管章节由 RLP 同步程序附加，独立于上述通用核心。本文件超过 10 KB 时审计会告警，
> 超过 20 KB 判违规。它应当只装执行边界。
