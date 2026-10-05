# Figure Element Inventory — 列定义与填写示例

契约定义见 [references/output-contract.md §8](../references/output-contract.md)。
本文件只给**填写示例**，不重复定义规则。

## 列定义

| 列 | 必需 | 取值 / 格式 | 写错会怎样 |
|---|---|---|---|
| `ID` | ✅ | `N1`、`N2`…（`^N\d+$`，文档内唯一） | 非法或重复 → 契约违规 |
| `Type` | ✅ | `data` / `model` / `operator` / `state` / `objective` / `parameter` / `supervision` / `output` | 非法值 → 契约违规 |
| `Label` | ✅ | 论文语义名称（**不用源码变量名**） | 无机器校验，但人工审阅会退 |
| `Group` | ✅ | stage / 视觉分组名，与 SVG Handoff 一致 | 不一致 → 后续 SVG 分组会错 |
| `Inputs` | ✅ | `—` 或逗号分隔 ID 列表 | 悬空 ID → 契约违规 |
| `Outputs` | ✅ | 同上 | 同上 |
| `Status` | ✅ | `observed` / `abstraction` + 可选限定词 | 非法值 → 契约违规；首字段写 `inferred` → 契约违规（D 级不进元素表） |

**Status 限定词**（用 ` · ` 连接）：`frozen`、`trainable`、`train-only`、`inference-only`、`optional`、`semantic`。

## 填写示例（迭代重建）

| ID | Type | Label | Group | Inputs | Outputs | Status |
|---|---|---|---|---|---|---|
| N1 | data | Measurement y | Inference | — | N4 | observed · inference-only |
| N2 | model | Flow Prior | Prior | N1,N3 | N5 | observed · frozen |
| N3 | state | Current reconstruction x_k | Solver | N5,N6 | N4 | observed |
| N4 | operator | Data Consistency Step | Solver | N1,N3 | N5 | observed |
| N5 | operator | Prior Step | Solver | N2,N4 | N3 | observed |
| N6 | state | Initial reconstruction x_0 | Solver | N1 | N3 | observed |
| N7 | supervision | Fully-sampled reference y_gt | Training | — | N8 | observed · train-only |
| N8 | objective | Reconstruction Loss | Training | N3,N7 | N9 | observed · train-only |
| N9 | parameter | Network parameters θ | Training | N8 | N2 | observed · trainable |
| N10 | output | Reconstructed image x* | Inference | N3 | — | observed |

## 反例

```text
❌ N3 | model | pred2 | model | x | y | observed          ← 源码名做 Label
❌ N3 | model | Adapter | model | — | N4 | observed       ← 材料无据的模块（补造）
❌ N3 | op   | DC Step | solver | N99 | N4 | observed      ← 悬空 ID
❌ N3 | model | Alignment | model | — | N4 | inferred      ← D 级不得进正式 draft
❌ N3 | model | Flow Prior | prior | — | N4 | maybe        ← Status 非法值
```
