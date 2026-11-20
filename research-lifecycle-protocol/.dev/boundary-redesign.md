# Skill / AGENTS.md 边界重设计（v2.4.0，已实现）

分支 `research-lifecycle-protocol/dev`。基线 2.3.1（`a13421b`）。本文件是 branch-local 记录，
合并前按根 AGENTS.md §14 做 PROMOTE / KEEP_BRANCH_ONLY / DELETE。

---

## 1. 结论：四层分工

| 层 | 载体 | 只管 | 不得承载 |
|---|---|---|---|
| 执行边界 | 项目根 `AGENTS.md` | 入口、写入范围、文件归属、交付检查、项目事实 | R 阶段流程、state schema、证据等级、指标公式 |
| 科研生命周期 | 本 Skill | R0—R14、state、证据资格、审查与决策门禁 | 某个项目的路径与服务器事实 |
| 具体实验 | 项目契约 + 预注册 + 冻结配置 | 数据划分、判据、预算、指标实现 | 跨项目通用规则 |
| 目录合规 | `scripts/layout_guard.py` | DI-1—DI-8 的机械判定 | 科学有效性 |

**优先级：布局可以让，门禁不能让。** 用户指令 ＞ 冻结协议 ＞ `AGENTS.md` 布局 ＞ RLP 默认布局。
RLP 的状态转换、证据资格与强制门禁不受该顺序影响。`AGENTS.md` 复述本文件的规则 = 内容错误：
删副本、留指针。

## 2. 旧结构为什么必然漂移

`AGENTS.md` 既是项目事实载体，又是 `project-layout.md` 规则的副本，而优先级规则让副本胜出。
DI-1—DI-8 因此退化为建议，且没有任何脚本读项目文件树。六个真实项目的实测见
[layout-audit-2026-11-20.md](layout-audit-2026-11-20.md)：`block` 合计 596 项。

## 3. 交付物

| 文件 | 作用 |
|---|---|
| `scripts/layout_guard.py` | `preflight` / `check` / `audit` / `selftest`；13 类 kind、route 与 XID 登记（三处来源）、`routes/<R>/docs/` 扁平、根 `docs/` 不放路线文档、受保护入口与软链接穿越、`AGENTS.md` 体量（>12 KB 告警，>20 KB 违规）。退出码 0/3/4 |
| `scripts/test_layout_guard.py` | 30 个用例：允许与拒绝两侧、两种真实 registry 形状、三处 XID 登记、宽模式拒绝、审计分级、CLI 退出码 |
| `templates/AGENTS.project.md` | 执行契约模板，6.7 KB，受控中文硬违规 0 |
| `templates/layout-policy.template.json` | 例外登记骨架（窄模式 + 授权人 + 理由 + 复审条件） |
| `references/project-layout.md` §0 | 四层分工、优先级拆分、`AGENTS.md` 内容与体量边界、guard 判定表 |
| `docs/releases/v2.4.0.md` | 发布说明；`CHANGELOG.md` 2.4.0 条目 |
| `release_check.py` 新步骤 | `Project layout guard`：selftest、模板存在性与体量、干净 fixture 0、违规 fixture 3 |

## 4. 关键判断（含被否决的方案）

| # | 判断 | 理由 |
|---|---|---|
| D-1 | `AGENTS.md` 是**执行边界**，不是 `layout.json` 的投影 | 投影方案要求先建 `layout.json` 全量布局机器件，迁移成本高；而执行边界的职责本来就窄，写成固定六节即可自证边界。机器裁决由 guard 直接读**磁盘**，不需要第二份布局声明 |
| D-2 | 例外登记在控制平面 `project/layout-policy.json` | 与 state 同域、单写者、可被 guard 直接读；旧位置 `docs/dev/path-allowlist.json` 保留只读兼容 |
| D-3 | 「纯伴随 / 密度补偿禁令」**留在项目**，不进 Skill | 按四层分工它属于「具体实验协议」。AGENTS v4 §5 明确数据、FFT、mask、CSM、纯伴随归项目冻结协议。代价：6 个项目仍有 3 种条目数（3/6/8）。缓解：`AGENTS.md` 只留指针，正文放 `docs/dev/protocol.md`。**这条是已知残余风险，不是遗漏** |
| D-4 | 托管块保留，但按「Skill 的投影」管理 | 训练前不加载 Skill 也能读到 7 条硬约束，这是真实收益；`mri_training.py` 已是唯一写者，guard 只管体量 |
| D-5 | `audit` 分 block / warn | 存量项目不可能一次清零。block = 结构性违规（DI-1/3/4/5/6/8、根级散文件、`log/`）；warn = 可容忍（隐藏目录、`docs/` 新类别、非枚举文件名） |
| D-6 | 不提供 `agents_migrate.py` | 机械重写 6 个项目的 `AGENTS.md` 风险大于收益；改为 `audit` 报告 + 人工按项目授权替换 |

## 5. 实现中发现的坑

1. **模板不能叫 `AGENTS.md`。** 本轮先把模板写成 `templates/AGENTS.md`，agent 运行时立刻把它
   当作指令自动加载，等于给每个会话注入一份未填的项目契约。改为 `.project.md` 后缀，
   并在 `release_check` 里加断言：`templates/AGENTS.md` 存在即 FAIL。
2. **模板要过受控中文 linter。** 首版 21 处硬违规（20 个分号 + 1 个营销词「闭环」），
   仓的闸门立刻判红。模板会被复制进项目，违规会跟着扩散。
3. **`_run()` 自带 `sys.executable`。** 新步骤照抄 `_run([sys.executable, ...])` 会把
   `/usr/bin/python3` 当脚本路径执行，报 «source code cannot contain null bytes»。
4. **XID 登记必须允许多源。** 现实项目里预注册、`experiments/*/manifest.json`、
   `research-state.json` 的 `experiments[].id` 三处都可能单独存在；只认一处会大面积误报。

## 6. 验证

| 项 | 结果 |
|---|---|
| `layout_guard.py selftest` | 0 failure |
| `test_layout_guard.py` | 30 tests OK |
| 虚拟项目 `.rlp-lab/rlp-fixture`（`build_fixture.py --verify`） | 0 failure：clean audit 0、6 个 preflight 允许/拒绝正确、`check` 0、`state_check` 0、`render_status` 0、`rlp_paths resolve` 0、`mri_training sync-agents` 0、注入 DI-1/ROOT-3/DI-4 后 audit 3、恢复后 0 |
| `AGENTS.md` 体量 | 模板 6657 B；加 MRI 受管块后 10037 B（warn 线 12000 B） |
| `release_check.py` | PASS（25 步；新增 `Project layout guard`） |
| 受控中文 linter（templates） | 硬违规 0 |

虚拟项目位置：`/home/lenovo/code/myproj/skills-dev/.rlp-lab/`（不在任何 Git 仓库内，
不污染技能仓；`build_fixture.py` 可随时重建）。

## 7. 未做 / 下一步

1. **存量项目未迁移**：6 个项目的 `block` 项见审计报告，逐项目由用户授权后处理。
2. **未把 `layout_guard.py` 接进各项目的 pre-commit / CI**：脚本已可用，
   是否强制由项目自己决定（`AGENTS.md` §2 已写命令）。
3. **未做内容语义检查**：路径合规不等于科学合法性。
4. **`AGENTS.md` 体量上限未做成 Skill 侧硬门禁**：目前是 guard 的 `AGENTS-1` 规则，
   默认 20 KB；若要更严，改 `layout-policy.json` 的 `agents_max_bytes`。
