<!--
路线级 STATUS.md 骨架。

**canonical 形态由 `scripts/render_status.py` 决定。** 它是 executable specification。
本文件必须与它**同形**，包括节名、顺序与每节的块形态。
`scripts/test_render_status.py` 的 content-shape parity 机械核对这件事。

用法：优先由 renderer 生成。手写初稿后也立刻交给 renderer 覆盖。

两条硬要求。
一、本文件是 `research-state.json` 的投影，不是第二份真相。
二、同一份 state 连续生成两次，内容必须逐字节一致。这就是幂等。

禁止手工补充 state 之外的事实。
**刻意不写「最后更新（墙钟时间）」**，那会破坏幂等（DI-4）。
时间线由 `routes/<R>/INDEX.md` 的 Recent Research Changes 承担。
-->

# Route <R> — STATUS

> **本文件是 `research-state.json` 的投影，不是第二份真相。**
> **禁止手改** —— 手改会在下一次 render 时被覆盖。
> 重新生成：`python3 scripts/render_status.py --root <项目根> --route <R>`。校验是否过期：加 `--check`（不一致退出码 3）。

## State version

- State version：S0000

## Current thesis

<中心命题一句话>

Status: <ungrounded | partially-supported | supported>

## Strongest supported findings

- `C1` — <结论>（supported）

## Active hypotheses

- `H1` — <假设>（elite）

## Critical uncertainties

- `U1` — <未知是什么>（open）

## Open critical attacks

- `A1` — <什么结果会杀死该 claim>

## Active experiments

- `X1` — <这个实验问什么>（planned）

## Most important negative findings

- `F1` — <什么失败了>（inconclusive）

## Next recommended actions

- `R1` — <发现的缺陷>（RUN_TEST）

## Current decision

CONTINUE
