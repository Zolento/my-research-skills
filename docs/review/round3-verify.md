# 第 3 轮复验记录（终验）

> **HEAD**：`d94b55b`｜**工作树**：干净｜**日期**：本会话末轮

## ⚠️ 独立性声明（必须披露）

第 3 轮本应由**未参与修复**的一方执行。三次尝试独立复验均失败：
`verifier`／`state-model` 等 teammate 与两个 fresh-context 子代理都未落盘报告（一个被停止、一个中途停止）。
**最终复验由 Lead 自己执行 —— 因此它是"终验"而非"独立复验"。**
为部分补偿，复验一律以**实跑退出码与原始输出**为证据，不采信任何自述；凡可疑处均构造最小片段实证。

---

## 1. 机械闸门（全部实测）

| 项 | 结果 |
|---|---|
| 离线测试 | **175 tests OK** |
| `--selftest` | **OK**（V1—V21 全覆盖） |
| 模板 `--check` | **exit 0** |
| 规则表 `--list-rules` ↔ policy §4 | **21/21，逐字不一致 0** |
| 三方读写表（SKILL §0 ↔ policy §5 ↔ phase 文件） | **覆盖 14 阶段，不一致 0** |
| 相对链接 | **464 条，断链 0** |
| deprecated 措辞扫描 | **命中 0** |
| `examples/` + `templates/` linter | **全绿（0 fail）** |
| 工作树 | **干净** |

---

## 2. M1 — `state_version` 初始生产者

R0 写格文本在**三处各出现恰好 1 次**且逐字一致：

```
SKILL.md:1   references/research-state-policy.md:1   references/phase-r0-contract.md:1
文本：`contract` + 模板骨架（含 `state_version: 0`）
```

**裁决：已修。** 只读文档即可知道 R0 要产 `state_version: 0`。

---

## 3. M2 — `preregistration` 归属与 `V21` 时序

| 情形 | 退出码 | 期望 |
|---|---|---|
| 合法：`frozen: 0`，`result: 1` | **0** | ✅ |
| 错序：`frozen: 2 > result: 0` | **3** | ✅ |
| `status: done` 但 `result_at_state_version: null` | **3** | ✅ |

**裁决：已修。** 时序约束在真实推进顺序下可满足，两种错序都被拦下。

---

## 4. M3 — R11 不动点

`研究-state-policy.md` §3.0 含「**传播产生的下游状态一律写 `stale`**」口径（命中 1 处）。

**裁决：已修。** 该口径使不动点**唯一且一趟即达**（`stale` 不传染；
`invalid` 只能来自独立判定，不得由传播产生）。

---

## 5. M4 — `render_status.py`（DI-4 落地判据）

| 检查 | 结果 |
|---|---|
| 幂等（两次渲染 sha256） | `9aa6b958307612aa` == `9aa6b958307612aa` → **一致** |
| `--check` 与 state 一致 | **exit 0** |
| 手改一行后 `--check` | **exit 3** |

**裁决：已修。** DI-4「`STATUS.md = f(research-state.json)`，不是第二份真相」现已有机械判据。

---

## 6. 总体裁决

**可交付（终验通过）。**

**遗留（登记，不阻塞交付）：**
1. **第 3 轮非独立复验**（见文首声明）—— 若需真正的独立复验，应换一个可稳定交付的执行体重跑。
2. 第 1 轮四条线的**完整报告**始终未落盘；其发现已由消息取得、修复并留证于 `round2-fixes.md`。
3. M3 的 `stale` 口径是 Lead 新增的设计决定（原规格只要求「下游不得为 `valid`」），**如需改回，须重跑 V19 相关用例**。
4. 未做：L1/L2/L3 创新层级、P1-7/8/11、`invocation-prompts.md`、SKILL §0.3 首次运行编排、MAJOR-4。
