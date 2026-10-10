# 第三轮整体检查：修复引入的回归 + 契约一致性（branch-local）

> 检查基线：`8887a48`（第二轮修复后的提交）。方法：2 路独立对抗审计
> （`H-fix-deltas-bugs.md` 复核修复增量、`I-consistency.md` 复核文档/契约一致性）
> + 主开发者对循环、写入守卫与规则码的复现探针。

## 本轮新发现（均已修复并有回归测试）

### HIGH

| ID | 问题 | 复现观察 | 状态 |
|---|---|---|---|
| S-1 | **同一 `state_version` 下调度器候选集变化会让循环错误 HOLD**。`scheduler.json` 是遥测，可在不 bump state 的情况下合法地新增候选（例如 assurance 解阻），但决策轨迹按字段逐字比较，把「候选列表变长」当成改写历史 → `DT2` → `HOLD` | 第二次 `run research-loop apply=True` → `HOLD / decision_trajectory_rejected` | **FIXED**：重复判定改为**决策语义**比较（被选动作 + 冻结上下文），候选集变化视为重新观测 → `DUPLICATE`，不写、不 HOLD |
| S-2 | **PT10 仍被「加一条不成立的条件」中和**（第二轮 F-3 的不完整修复）：反例只写 `conditions` 而不写任何结构时，`structured=True` 提前 `continue`，覆盖检查被跳过 | `{"id":"CE"}` → BLOCK；加 `conditions:[{...eq "__nope__"}]` → ALLOW | **FIXED**：不成立的条件只对**声明了结构**的反例生效，否则 fail-closed 阻塞 |

### MEDIUM

| ID | 问题 | 状态 |
|---|---|---|
| S-3 | `guard_write(allowed_roots="<path>")` 按字符迭代 → `'/'` 成为允许根，`/scheduler.json` 等绝对路径全部放行 | **FIXED**（字符串视为单个根；`None`/非序列 → 拒绝而不是 `TypeError`） |
| S-4 | `allowed_roots=None/42/Path` 抛未捕获 `TypeError`（第二轮修复引入的回归） | **FIXED**（统一规范化） |
| S-5 | 原件被删除后硬链接守卫失效（inode 集合里已无该项） | **FIXED**（受保护顶层条目缺失即 fail-closed） |
| S-6 | 作用域检查只在 skill 根之外生效，根内「route」可任意写 | **FIXED**（作用域检查对根内同样生效） |
| S-7 | `ALLOWED_WRITE_SCOPES` 写 `decision-trajectory`，真实存储是文件 `decision-trajectory.jsonl` → 合法写入会被拒 | **FIXED**（补齐文件名作用域并接受 stem） |
| S-8 | `expired_trajectories` 接受**负数** `state_version` → 过期判定整体失效 | **FIXED**（要求非负整数） |
| S-9 | 来源可自证：`propose()` 用 `setdefault`，候选自己声明 `source_route` 等于目标路由即可跳过迁移门 | **FIXED**（`propose()` 覆盖式打戳 `origin_stamped`；门只信打戳来源；自述来源一律 BLOCK） |
| S-10 | `negative_knowledge.ruled_out` 非字符串时被真值强制转成非字符串再被过滤 → PT8 静默失效 | **FIXED**（非字符串即 PT8 fail-closed） |
| S-11 | `guard_errors` 是死代码（只有自己的测试调用） | **FIXED**（接入 `candidate_errors` 作为第二道源码保护扫描）；同时收窄其 shell 规则，使普通英文分号/比例文本不再误判 |
| S-12 | `applicability` 校验要求 `problem_structure`，消费者却把它当 `island` → 该策略面实际无效 | **FIXED**（要求 `island` 并校验；无 island 的 applicability 不算可消费变更） |

### 契约一致性（`I-consistency.md`）

| ID | 问题 | 状态 |
|---|---|---|
| R-7 HIGH | `research-loop` §8 写入集合漏掉 apply 路径实际写的 `decision-trajectory.jsonl` 与 `scheduler.json` | **FIXED**（补齐写入集合，并标注「仅 apply 路径」） |
| R-5 | §7 声称 `loop_state` / `evidence_delta`，处理器不返回 | **FIXED**（处理器补上这两个字段） |
| R-6 | §7 声称 `priors_before/after`、`recommendation_before/after`，处理器不返回 | **FIXED**（按实际返回字段改写契约） |
| R-8 | §8 漏列 `scheduler.json`、并错误地允许 `decision-trajectory.jsonl` | **FIXED** |
| R-9 | `stagnation-breaker` §6 只记录了 NO_CHANGE 分支的 1 条命令，OK 分支返回 3 条 | **FIXED**（步骤表改为分支无关，文档同步为 3 条） |
| R-1/R-2/R-3 | `PT1`—`PT10` 范围过期（已有 PT11）；`DT7`/`DT8` 未列入；参考文档完全没列 PT 规则 | **FIXED**（`PT1`—`PT11`；补全 DT7/DT8 与 PT1—PT11 全表） |
| R-11 | 发布闸门注释指向 branch-local `.dev/decisions.md` | **FIXED** |
| R-13 | `policy_evolution.write_snapshot` / `state_snapshot_path` 生产无人调用 | **FIXED（删除）**：`rebuild_state` 是唯一来源，保留无消费者的派生缓存只会增加复杂度 |
| R-16 | `TRAJECTORY_LOCK` 死常量（真实锁是 `store_lock`） | **FIXED（删除）** |
| R-10/R-14/R-15 | `policy_transfer selftest` 未在文档列出；`level_report(l3_evidence=…)` 与 `cases_from_trajectory` 仅库/测试可达 | **记录为库 API**（前者属于真实 A/B 评估器接口，不是本轮可宣称的 L3 路径） |

## 本轮确认**不是** bug（负结果，来自独立审计）

- `DT7`/`DT8` 已真实实现且列名正确；`PE1`—`PE14` 无缺号。
- 所有文档声称的 CLI 子命令都真实存在；没有 `.dev/` 运行时依赖。
- 冻结不变量：`state_check.py` 输入输出、canonical 顶层键、八类对象、16 个 Preset、
  `metadata.version = "1.0.0"` 均未变；没有替换任何既存 schema id。
- `EXCLUDED_DIRS_ANYWHERE=(".git","__pycache__")` 下，真实根清单 135 项与独立 `find` 一致；
  嵌套 `scripts/.dev/evil.py` 可见，而 `.git`/`__pycache__` **目录**不可见。
- 完整性链：重复的合法行不会被静默接受；调用方无法覆盖 `seq`/`previous`/`recorded_at`。
- `_condition_eval`、`F-1` 全部真实假设状态、`F-10` 仅两处常量 `re.` 模式等均无新问题。

## 仍**未修**（如实记录，不假装已解决）

1. `verify()` 只比内容摘要、不绑 manifest 的 root/realpath（E-5）。
2. 受保护目录下的**符号链接目录**不入清单（E-9）。
3. `allow_canonical` 未绑定 route（E-11）；`route_dir=None` 不写审计事件（E-12）。
4. **enter/exit 之间「改了又改回」检测不到**（E-16），已在模块级 `RESIDUAL RISK` 与
   `read_only_deployment_plan()["residual_risks"]` 声明。
5. PT9 的跨项目证据仍可自述（F-12）；PT10 的裸字符串反例只按引用语法放行。
6. 并发修复只在同机多线程验证，未跨主机/网络文件系统验证。
7. **L3 仍未验证**：全部结论基于合成 fixture 与单元测试。

## 验证（本轮结束时）

| 检查 | 结果 |
|---|---|
| 全量单元测试 | **1680 tests OK (skipped=3)**（第二轮结束 1661） |
| `release_check.py` | **PASS（18 步）** |
| 5 个模块 `--selftest` | 全 OK |
| 冷 `__pycache__` 端到端 | `source_integrity: PASS` |
| 循环幂等（同 state 连跑 3 次） | 3 次 OK，轨迹仅 1 行 |
