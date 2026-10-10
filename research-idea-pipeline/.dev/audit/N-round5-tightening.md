# 第五轮：剩余未修项定向收紧 + 第四轮派发审计的发现（branch-local）

> 基线：`7ddde7f`。本轮做两件事：
> ① 定向收紧两项此前记录为「未修」的问题（短 token 泄漏、PT9 自述证据）；
> ② 处理第四轮派出的两个独立审计代理**延迟交付**的报告（`K-preset-router-bugs.md`、
> `L-harness-memory-bugs.md`）中的 CONFIRMED 发现。

## 一、定向收紧

### T-1 短 token 泄漏守卫（原「未修」）
**原状：** `RP2` 只扫描 ≥12 字符的隐藏串；隐藏答案若只由短标识符（`X1`/`LIT1`）表达，
完全测不出。

**收紧后的规则（两级）：**
1. 长串（≥12 字符）：原有子串扫描不变。
2. **短标识符**：`short_answer_tokens()` 只取「标识符形状」的 token（2–11 字符、以字母开头、
   含至少一个数字，如 `X1`/`LIT1`/`P3`/`ADV4`）。一个这样的 token 只有在**同时**满足
   「出现在授权上下文（`known_conditions`/`available_literature` 等作者字段）
   **且** 不出现在任何决策时输入（`state`/`legal_actions`/`scheduler`/`revisions`/
   `question`/`observation_packet`/`insight_cards`/`cognition`/`policy_candidates`）」
   时才算泄漏。

**为什么不是简单降低长度阈值：** 首版按「非 state 区域」判，把 14 个出货 case 全部判红——
机制名 `机制 A` 出现在 `question`、实验 id 出现在 `observation_packet`，都是**合法输入**。
「出现在作者上下文 + 不在任何输入里」才是真正的信息泄漏语义。

**验证：** 隐藏 id 泄漏进 `known_conditions`/`available_literature` → 判红；
同一 id 只出现在 state/observation_packet → 不判红；自然语言片段不判红；出货 14 case 全清白。
新增 `short_token_leaks()` 并接入 `leak_scan`（→ `run_case` 直接拒绝该 case）与 `leak_audit`（`RP2-short`）。

**仍存在的限制（如实记录）：** 只覆盖标识符形状的短 token；纯数字、纯中文短语、运行时拼接的
隐含关联仍不覆盖。

### T-2 PT9 跨项目证据必须是「可背书」的（原「未修」）
**原状（复现）：** `scope={"kind":"global"}` + `evidence_projects=["A","B"]`、**0 条记录** → **ALLOW**；
两条**没有 decision 的** outcome 行 → **ALLOW**。自述即可满足「≥2 个项目」。

**收紧后：** 只有「同一 trajectory 同时具备 decision 与 qualified outcome」的项目才算
**背书项目（attested）**，并要求：
1. 宽作用域需要 **≥2 个背书项目**（不再计自述集合）；
2. 自述的 `evidence_projects` 必须**是被背书项目的子集**，未背书即 BLOCK；
3. `supporting_trajectory_ids` 必须指向有「决策 + 合格 outcome」的轨迹；
4. `independent_evaluation_refs` 的每一项必须能落到某个背书项目/轨迹上，
   否则「自述的独立评价不算独立评价」。

**验证：** 自述列表 → BLOCK；两条裸 outcome 行 → BLOCK；两条真实轨迹（decision+outcome）
→ ALLOW；未背书项目 / 幽灵轨迹 / 未背书引用 → 均 BLOCK。
`test_policy_transfer` 中原先编码弱语义的一例已改为使用真实证据，并新增 5 例回归。

## 二、第四轮延迟交付审计的发现（已处理）

### K（preset_router 定向）— 9 条 CONFIRMED
| ID | 严重度 | 问题 | 处置 |
|---|---|---|---|
| K-2 | HIGH | 非 UTF-8 的 `policy/candidates.jsonl` 抛 `UnicodeDecodeError` 穿透 | **FIXED**（`load_chained` 捕获解码失败 → 严格抛 `TrajectoryError`、tolerant 出诊断；路由器 → `HOLD / policy_store_tampered`）|
| K-3 | HIGH | 非 UTF-8 的 `decision-trajectory.jsonl` 同样穿透 | **FIXED** → `HOLD / decision_trajectory_unreadable` |
| K-4 | MED/HIGH | 只读路由不可写时审计事件写入抛 `PermissionError` | **FIXED** → `HOLD / control_plane_unwritable` |
| K-5 | MED | 派遣来自历史遥测（无策略）时仍报 `policy_delta=applied, level=L2, policy_id=null` | **FIXED**（要求 `policy_id` 才产生 policy delta）|
| K-6 | LOW/MED | 被篡改的策略存储把 `BLOCKED` 降级为 `HOLD`（退出码 3→4） | **FIXED** |
| K-7 | LOW | 后一个 ACTIVE 变 HOLD 时，仍 ACTIVE 的策略被静默丢弃 | **FIXED**（指针跟随生命周期状态；无 ACTIVE 即无生效策略）|
| K-8 | LOW | 裸相对路径 → `route=""`，轨迹 route 为空且迁移门被跳过 | **FIXED**（`_route_name()` 先绝对化）|
| K-9 | LOW | 策略存储用 realpath、其他控制文件用词法父目录 → symlink 路由错配 | **FIXED**（统一词法父目录）|
| K-10 | LOW | 只有 `.head` 没有日志不算篡改 | **FIXED**（孤 head 即篡改）|

### L（消融/闸门/策略记忆定向）— 12 条
| ID | 严重度 | 问题 | 处置 |
|---|---|---|---|
| L-1 | HIGH | `.dev/` 扫描器漏判：`os.path.join(root, ".dev", …)`、`DEV=".dev"`、最后一个 selftest 之后的代码 | **FIXED**（改为 AST：字符串字面量含 `.dev` 路径段**且被用于建路径/打开**才算；模块级 `.dev` 常量被调用使用也计入；selftest/fixture 按外层函数名跳过）|
| L-2 | MED | 显式 `prefer_actions` 被更早声明的 operator/island 对齐动作压过 | **FIXED**（显式 rank 永远优先于对齐）|
| L-3 | MED | `undifferentiated_arms` 只比维度均值：pass_rate 1.0/无违规 与 0.0/有违规被判「不可区分」 | **FIXED**（签名含 pass_rate 与 violations）|
| L-4 | MED | 空 answer 的非法 case 被照常评分：七维全 `None` 却 `sufficient_sample=True` | **FIXED**（`run_suite` 拒绝非法 case；`sufficient_sample` 还要求至少一维可评）|
| L-5 | MED | `cases_from_trajectory` 在 `chosen=None` 时产出 `observed_actions: ['None']` | **FIXED** |
| L-6 | MED | `coverage_report` 把「有 outcome 无 decision」算作可评（回归） | **FIXED**（要求 decision+outcome）|
| L-7 | MED | guard 探针把**被拒绝**的候选算作 diverging | **FIXED**（diverging 只认 `policy_applied`；bypass 标记另列）|
| L-8 | MED/LOW | `decision_errors` 只认四臂，RSI 臂被判「未知 ablation arm」 | **FIXED**（接受 `ABLATION_ARMS + RSI_ARMS`）|
| L-9 | MED/LOW | RP7 跳过 `.pyc`；且把 case 文件本身判为泄漏 | **FIXED**（扫描 `.pyc`；按 `_schema`+`id` 跳过 case 自身）|
| L-10 | LOW | `Path("config.dev.json")` 误判 | **FIXED**（按路径段判定）|
| L-11 | LOW | `overhead_report(iterations=0)` 除零 | **FIXED**（`max(1, …)`）|
| L-12 | LOW | `must_not_conflate` 纯装饰 | **记录**（是文档字段，不被任何门禁使用）|

## 三、验证（本轮结束时）

| 检查 | 结果 |
|---|---|
| 全量单元测试 | **1708 tests OK (skipped=3)**（本轮前 1695） |
| `release_check.py` | **PASS（18 步）** |
| 5 个模块 `--selftest` | 全 OK |
| `.dev/` 扫描器 | 对 `os.path.join(r,".dev",…)` / `DEV=".dev"` 判红；对 `config.dev.json` / docstring 不判红；真实树通过 |
| 短 token 守卫 | 真泄漏判红；合法输入不判红；出货 14 case 全清白 |
| PT9 | 自述 → BLOCK；裸 outcome → BLOCK；真实轨迹 → ALLOW |

## 四、仍存在的限制（不假装已解决）

1. **短 token 守卫**只覆盖标识符形状；纯数字、纯中文短语、运行时拼接的隐含关联不覆盖。
2. **PT9** 的「真实轨迹」仍由调用方提供记录；生产路径经 `decision_trajectory.load_records`
   校验哈希链，但直接传裸 list 的调用方仍需自证。
3. `.dev/` 扫描器无法识别运行时拼接的 `"." + "dev"`。
4. 其余仍在案：`verify()` 不覆盖「改了又改回」（E-16）、L3 未验证、并发仅在单机验证。
