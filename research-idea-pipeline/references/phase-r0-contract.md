# R0 — 研究契约（research-contract）

**R0 是一次性入口阶段。** 它把「研究什么、边界在哪、有什么资源」固定成契约，
之后所有阶段都在这个契约下工作；**改契约要走锚点变更单**（见 [../SKILL.md](../SKILL.md) §0.2）。

> **R0 只写 `contract`。** `assurance[]` 由 **R7** 写 —— kill condition 是对具体 attack
> 的回应，R0 期还没有 claim、更没有 attack，在那里写只能写出空话。

---

## 输入

| 输入 | 必填 | 说明 |
|---|---|---|
| 研究问题 / 方向 | ✅ | 用户自己的表述，**原样记录**，不要替用户改写 |
| 项目主锚点 | ✅ | 理论 / 性能 / 现象 / 基准 / 可行性 / 负结果（见 [../SKILL.md](../SKILL.md) §0.1） |
| 约束 | ❌ | 时间、算力、数据可得性、伦理 / 合规 |
| 资源 | ❌ | 已有代码、数据、模型、合作者 |
| 已有材料 | ❌ | 文献、笔记、先前实验 |

---

## 动作

### R0.1 复述并确认（**不得跳过**）

把用户的研究问题与主锚点**复述一遍**请其确认。**未确认前不得进入 R1 之后的任何阶段**
（与 [../SKILL.md](../SKILL.md) §0.1 一致）。

判据：复述里出现「我理解你要的是……对吗」这类**可被否定**的表述。
只写「已确认」三个字不算确认。

### R0.2 契约字段落盘

**以 `templates/research-state.template.json` 骨架落盘，八类数组保持空 `[]`，只填 `contract`**
（只写 `contract` 一个键会让 `state_check.py` 判 `exit 4` —— 它要求八类数组存在）：

写进 `research-state.json` 的 `contract`：

```jsonc
{"goal":"…","primary_anchor":"performance","constraints":["…"],"resources":["…"],
 "provisional_anchor_rationale":"…","out_of_scope":["…"]}
```

- `primary_anchor` 取值逐字取自 SKILL §0.1 的锚点枚举（英文原样）。
- **`out_of_scope` 是必填的**：写不出「不做什么」，说明边界还没想清。
- **`provisional_anchor_rationale` 必须写「为什么现在先按这个锚点走」** —— 它是给 R1 的
  Anchor Eligibility 复核用的（见下）。

### R0.3 路线与骨架检查

按 [project-layout.md](project-layout.md) §7 的清单确认目录与路线三件套
（`README.md` / `STATUS.md` / `INDEX.md`）存在；不存在则先建。

---

## 产出

| 产物 | 位置 |
|---|---|
| `contract` | `.research-idea-pipeline/routes/<R>/research-state.json` |
| 根 `INDEX.md` 的项目主锚点声明 | 项目根 |

---

## 硬规则

1. **契约期的 anchor 是 `provisional`（暂定），不是决定。**
   证据到位后由 **R1 的 Anchor Eligibility Test** 复核（见
   [claim-first-policy.md](claim-first-policy.md) §6）。若证据不支持用户偏好的锚点，
   **必须显式告知**「你想定位成 X，但现有证据支持的是 Y」，**不得**帮用户强化不被证据支持的故事。
2. **改主锚点只能由用户授权**，走 SKILL §0.2 锚点变更单；agent 只能提请或降级。
3. **不得在 R0 产出 claim。** R0 只有目标与约束，没有科学主张 —— 出现 `claims[]` 条目即违规。
4. 用户表述与研究问题不一致时，**记录原话并提问**，不要替其"整理成更合理的版本"。

---

---

## 读 / 写 World Model（强制）

| 阶段 | 读 | 写 |
|---|---|---|
| **R0** | — | `contract` |

> 权威定义见 [research-state-policy.md](research-state-policy.md) §5；本节与它**必须逐字一致**。
> 回写后跑 `python3 scripts/state_check.py --check .research-idea-pipeline/routes/<R>/research-state.json`，**硬违规须为 0**。
