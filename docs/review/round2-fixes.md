# 多轮审查与修复记录（Round 1 → Round 2）

> **基线**：`f2ce0ea` → 本轮结束时 HEAD 见文末。
> **方法说明**：第 1 轮四条审查线**全部只读**；第 2 轮由 Lead 逐条修复并保留证据。
> 本文件是**证据台账**，不是设计文档。

---

## 0. 第 1 轮：四条审查线

| 任务 | 审查线 | 负责人 | 自报写入 |
|---|---|---|---|
| `task-12` | 跨层漂移（"改了口径没改影子"） | `verifier` | **0** |
| `task-13` | Wave 5 schema 语义（V18—V21） | `state-model` | （曾被误判中断，已恢复） |
| `task-14` | Wave 6 目录规范 / 人类导航可用性 | `examples-templates` | **0** |
| `task-15` | 字面走查 `R0`→`R14`（逐阶段喂校验器） | `claim-core` | **0** |

**四条线均未按时落盘报告**，但其中两条通过消息直接回报了发现，已足以定案。

### 0.1 完整性事件（已结案）

审查期间工作树出现 15 个 skill 文件的改动，曾被怀疑为审查者越权写入。
**查明：写入者是 Wave 6 迁移子代理**（任务本身允许写，只是收尾拖进了审查期）。
`state-model` 曾被误判并被中断，**已致歉并恢复**。

**结论：四条审查线纪律良好，Lead 的归因有误。** 该批改动逐行复核后提交为 `c2b6a84`
（唯一真回归：`推荐 population` 被误改回 Wave 2 已作废的「推荐 elite 集合」，已还原）。

---

## 1. MAJOR 清单与修复

### M1 — `state_version` 的初始生产者无人认领

**现象**：全文档只有 R11 有「`state_version` +1」；R0 只说「以模板骨架落盘、八类数组清空、只填 `contract`」。
**后果**：R2 一写第一个一类对象，`V18` 就要求 `state_version`，而**没有任何一条规则产它** → 收工必然 exit 3。

**修复**：R0 写格显式化为「`` `contract` + 模板骨架（含 `state_version: 0`） ``」，
三处同步（`SKILL.md` §0 / `research-state-policy.md` §5 / `phase-r0-contract.md`）。

**证据**：三方读写比较器覆盖 14 阶段，**不一致 0**。
**提交**：`3eb58d4`

---

### M2 — `experiments[].preregistration` 的生产者与创建者错位

**现象**：读写表把 `preregistration` 划给 **R8**，但 `experiments[]` 由 **R9** 创建
→ R8 期目标对象**不存在**；而 R9 写集合又不含 `preregistration` / `result_at_state_version`，
`V21` 却在 R9 收工就要求它们 → **收工必然 exit 3**。

**修复**：改为 **R8 创建 `planned` 条目 + 冻结 `preregistration`**；
**R9 执行并写 `experiments[].status` / `result_at_state_version`**。

**`result_at_state_version` 的口径**（已写明，避免歧义）：**写"结果写入时的 `state_version`"**
（此时 R11 尚未 +1）。

**时序实测**（构造状态喂 `state_check.py`，原始退出码）：

| 情形 | 场景 | 结果 |
|---|---|---|
| A | R8 冻结，`status: planned`，`frozen_at_state_version: 0` | **exit 0** |
| B | R9 出结果，`result_at_state_version: 0`（== frozen） | **exit 0** |
| C | R11 先 +1（`state_version: 1`），R9 再出结果 `result_at_state_version: 1` | **exit 0** |
| D | 错序：`frozen_at_state_version: 2 > result_at_state_version: 0` | **exit 3**（V21 ×2） |
| E | `status: done` 但 `result_at_state_version: null` | **exit 3**（V21 ×2） |

**结论：`V21` 的时序约束在三种真实推进顺序下均可满足，且两种错序都被拦下。**
原先担心的「时序下必然冲突」**不成立**。

**提交**：`3eb58d4`

---

### M3 — R11「失效传播至不动点」只有口号、无可判定停止条件

**现象**：SKILL §0、`phase-r9-r11` 读写行、policy §3.0 边界各出现一次，
但**没有任何可判定的停止条件或过程定义**。

**修复**（写入 `research-state-policy.md` §3.0）：

1. 对**全体一类对象**做一趟扫描；**本趟无任何 `validity.status` 变化**即为不动点，停止；
2. **趟数上限 = 对象总数（下界 3）**，禁止无限迭代；
3. 到达上限仍未收敛 → **不得静默继续**：落 `uncertainties[]`（`importance: critical`）
   + `repairs[]`（`disposition: FIX_IMPLEMENTATION`）；
4. 传播**只允许改 `validity`**；`claims[].status` 只能经 R8 / R10。

**遗留（登记，未修）**：**不动点不唯一** —— 规则只要求「下游不得为 `valid`」，
执行者可选 `stale` 或 `invalid`；若选 `invalid` 则继续传播，若选 `stale` 则停止
（`stale` 不传染）。因此**同一初始状态可能收敛到不同终态**。
两种终态都满足 `V19`，故不构成硬违规，但 `R11` 的输出**不是确定性的**。
**建议后续加一条口径：「传播产生的下游状态一律写 `stale`」**，使不动点唯一且一趟即达。

**提交**：`3eb58d4`

---

### M4 — `render_status.py` 不存在，却是 DI-4 的唯一验收判据

**现象**：`find` 无此文件，却被 6 个文件 **11 处**引用。
**后果**：`templates/STATUS.md` 写「禁止手改」，`project-layout` §6.2 又要求各 R 阶段
「必须更新 STATUS.md」—— 脚本缺失时两条互斥，**人只能手写 → DI-4 名存实亡**。

**修复**：实现 `scripts/render_status.py`（stdlib-only）：

- `render(state, route)` 是**纯函数**（无时间戳、无随机、无环境依赖）；
- 产出模板声明的 **10 个人类入口节**；
- 退出码 `0` / `3`（STATUS 过期）/ `4`（state 缺失或非法 JSON）；
- **只读 state，只写 STATUS.md**。

**幂等实测（DI-4 的机械判据）**：

```
两次渲染 sha256 相同      9aa6b9583076…
--check 一致            → exit 0
手改一行后 --check      → exit 3
缺 state                → exit 4
```

**新增** `scripts/test_render_status.py`（11 例）：幂等、纯函数性、`state_version` 传导、
`--check` 三态、环境侧 4、10 节齐备、自我声明是投影、thesis 取自 claim 根。

**顺带修复**：文档 7 处写 `scripts/research/render_status.py`，而 Skill 自身脚本目录是**扁平**的、
且 `scripts/research/` **并不存在**（那是**目标项目**的目录设计，被混淆）→ 全部统一为
`scripts/render_status.py`。

**提交**：`c260583`

---

## 2. 第 2 轮修复后的闸门（全部实测）

```
175 tests OK（164 → +11）          selftest V1—V21 全覆盖
模板 --check exit 0                规则表 21 条 ↔ policy §4 逐字不一致 0
三方读写 14 阶段逐字不一致 0        链接 464 条 断链 0
deprecated 0 命中                  examples/ 与 templates/ linter 全绿
工作树干净
```

---

## 3. 未完成 / 待复验

| 项 | 状态 |
|---|---|
| 四条审查线的**完整报告落盘** | ❌ 未落盘（`docs/review/round1-*.md` 均不存在）；发现已由消息取得并处理 |
| **第 3 轮独立复验** | 🔄 已派发 fresh-context 复验代理，要求重点攻击 M2 时序与 M3 不动点可判定性 |
| M3 的不动点不唯一 | 登记（见 M3 遗留），**未修** |
| L1/L2/L3 创新层级、P1-7/8/11、`invocation-prompts.md`、SKILL §0.3、MAJOR-4 | 挂账，本轮未动 |

**第 3 轮的验收标准**：M1—M4 每项裁决 + 总体裁决；**M2 时序与 M3 不动点必须给出实测证据**。
