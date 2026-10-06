<!--
路线级 STATUS.md 骨架。
用法：复制到 routes/<R>/STATUS.md。
生成入口：scripts/render_status.py。
要求：本文件是 research-state.json 的投影，不是第二份真相。
      同一份 state 连续生成两次，内容必须一致。这就是幂等。
      禁止手工补充 state 之外的事实。
-->

# routes/<R> — STATUS

> 本文件是 `research-state.json` 的投影，不是第二份真相。
> 应由 `scripts/render_status.py` 生成，手改无效。
> 要新增事实，先改 `research-state.json`，再重新生成。

---

## Last updated + State version

- 最后更新：`<YYYY-MM-DD>`
- State version：`<N>`

## Current thesis（含 status）

- 中心命题：`<一句话>`
- status：`ungrounded` / `partially-supported` / `supported`

## Strongest supported findings

| # | 结论 | 证据 | state 引用 |
|---|---|---|---|
| `S1` | | | `C1` |

## Active hypotheses

| # | 假设 | 状态 | niche |
|---|---|---|---|
| `H1` | | | |

## Critical uncertainties

- 待核实条数：`<N>`
- `<不确定性>`（等级：High / Medium / Low）

## Open critical attacks

| # | 攻击 | 状态 | 处置 |
|---|---|---|---|
| `A1` | | | |

## Active experiments

| XID | Question | 状态 | 结果 |
|---|---|---|---|
| `X021` | | | |

## Most important negative findings

| # | 负结果 | 证据 | 处置 |
|---|---|---|---|
| `F1` | | | |

## Next recommended actions

| # | 动作 | 优先级 | 依赖 |
|---|---|---|---|
| `N1` | | P0 | — |

## Current decision

- 决策：`continue` / `pivot` / `archive` / `submit`
- 依据：`<一句话>`
- Revisit condition：`<触发条件>`
