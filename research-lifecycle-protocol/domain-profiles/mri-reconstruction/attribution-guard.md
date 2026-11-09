# Trivial Attribution Guard（TAG，平凡归因守卫）

> 加载时机：领域 profile 激活后，任何"性能瓶颈归因"进入决策之前。
> 机械实现：`scripts/domain_guard.py`；规则 `TG1`—`TG9`。

## 0. 解决的问题

MRI 重建研究中反复出现如下低价值模式：

```text
性能提升失败
    ↓ 检查 forward operator
    ↓ 检查 noise level / SNR
    ↓ 检查 CSM / sampling / condition number
    ↓ 归因于物理逆问题困难
    ↓ 建议继续诊断或停止      ← 没有新证据，也不改变任何研究决定
```

这些分析**可能是对的**，但在没有新信息时反复成为研究终点，方法探索就停摆了。
TAG 的职责是识别**缺少新证据、无法改变研究决策的重复归因**，并把研究推向合法的方法转化。

## 1. 六类判定（逐字枚举）

| class | 含义 | 后续动作 |
|---|---|---|
| `VALIDITY_BLOCKER` | 真实实验有效性错误（实现、泄漏、数据不一致） | 必须优先修复；**永远不被压制** |
| `NOVEL_DECISION_RELEVANT_DIAGNOSIS` | 有新证据且能改变科学决策的诊断 | 正常进入 R9.O/R10 分析 |
| `REPEATED_ATTRIBUTION` | 已有等价证据、无新增决策价值的重复归因 | 不再派同类诊断；转方法转化/重规划 |
| `PHYSICAL_LIMIT_WITH_SCOPE` | 经可靠验证、带明确适用范围的物理限制 | 记负知识并**限定研究空间**；范围内不虚构改进 |
| `METHOD_TRANSITION_READY` | 现有洞见足以推进方法设计 | 走 MMS / I2M，不再等待更多诊断 |
| `INSUFFICIENT_EVIDENCE` | 当前无法判断机制，也不能宣称找到根因 | 不得写成结论；可设计判别实验或搁置 |

## 2. 机制指纹（不是关键词匹配）

每个归因声明五元组，由 agent 填写、guard 机械规整：

```jsonc
{
  "mechanism": "condition_number",        // 受控枚举（§3）
  "assumptions": ["高斯噪声", "固定 mask"],
  "scope": "10x variable-density, 20-coil",
  "predictions": ["X12 中 O1 与 O2 无显著差异"],
  "evidence_refs": ["E7", "X11"],
  "decision_consequence": "若成立则放弃方向 B"
}
```

指纹 = `digest({mechanism, assumptions(排序后), scope(规范化小写)})`。
**预测与证据引用不进指纹**——它们是新信息的载体，正是重复判定要比较的东西。

等价关系按结构判断：机制枚举相同 + 假设集合相同 + 范围相同。自由文本解释（"可能是
病态问题"）**不参与**匹配。无法机械证明的等价关系（例如 mechanism 是自由文本、假设
集合只有部分重叠）→ `review_required: true`，生成待审查判断，**不自动阻断**。

## 3. 受控机制枚举

```text
forward_operator_mismatch   coil_sensitivity_error   noise_level          snr_limit
undersampling_information   conditioning             ill_posedness
oversmoothing               overstrong_prior         data_scarcity
other_declared
```

新机制一律先登记为 `other_declared` 并附结构化假设，经 R7/R10 确认后再提升为专用枚举值；
**不得**为了让归因绕过守卫而换词（等价换词由 assumptions+scope 结构比对拦截）。

## 4. 机械规则（TG1—TG9）

| 规则 | 内容 |
|---|---|
| TG1 | 判定必须携带结构化声明；缺 mechanism / scope / evidence_refs 时按 `INSUFFICIENT_EVIDENCE` 处理 |
| TG2 | 声明指向**未解决**的算子/流程验证失败、测量不一致或泄漏证据 → `VALIDITY_BLOCKER`，优先于一切，**永不因重复被压制** |
| TG3 | 声明引用已验证物理限制且带适用范围 → `PHYSICAL_LIMIT_WITH_SCOPE`；范围外不得推出"所有先验方法无效" |
| TG4 | 存在指纹相同、且证据引用集是历史已记录子集的等价归因 → `REPEATED_ATTRIBUTION`（重复按次数累计） |
| TG5 | 存在新证据引用（不在该指纹历史集合中）→ `NOVEL_DECISION_RELEVANT_DIAGNOSIS`；同时记录是否声明了 decision_consequence |
| TG6 | `REPEATED_ATTRIBUTION` 且存在合法方法候选或 I2M readiness 成立 → 追加 `METHOD_TRANSITION_READY` 指令 |
| TG7 | 等价性无法机械证明 → `review_required: true`，不阻断、不否证，只登记待审 |
| TG8 | TAG 不绕过 PEIG/AALG、不启动 GPU 实验、不刷新诊断预算、不改 claim 状态；它只在 loop 选步时**排除重复诊断动作**并给出转化指令 |
| TG9 | 判定事件写入 route 控制平面 `<route>/domain/tag-events.jsonl`（append-only + 哈希链）；删除该文件不得影响 canonical state 校验 |

## 5. 避免误伤（同样重要）

TAG **不禁止**讨论噪声和算子。以下情况保留完整的诊断与阻断能力：

- 明确的算子实现错误、错误 CSM、数据泄漏、测量模型与原始数据不一致；
- 真实数值不稳定、影响实验结论的模型失配；
- 已可靠证明的特定信息不可恢复边界（带范围记录）。

即使物理限制成立，也不能自动推出"所有先验方法都无法改进"；反之，若某项限制已从理论
或严格实验上排除了特定目标，Agent 不得为满足探索要求而虚构可行改进。

## 6. 运行方式

```sh
# 对一条归因声明做分类（advisory；不写任何状态）
python3 scripts/domain_guard.py classify --state <route>/research-state.json \
  --declaration declaration.json

# 查看/校验本路线的 TAG 事件链
python3 scripts/domain_guard.py events --route <route-dir>
python3 scripts/domain_guard.py check   --route <route-dir>
```

Loop 内（research-loop preset）：TAG 在 `_loop_step` 里于既有
`diagnosis_decision_impact` 检查之后运行。被判定为 `REPEATED_ATTRIBUTION` 的
scheduler 动作**不再派遣**，loop 输出方法转化步骤（I2M / MMS 菜单），并在
`tag` 字段里给出判定依据与指纹；`apply` 时事件写入 `tag-events.jsonl`。
TAG 从不修改 `scheduler.json` 的优先级，也不改写 canonical state。

## 7. L1/L2/L3 诚实边界

- **L1**：分类规则、指纹、事件链有机械测试。
- **L2**：`preset_router._loop_step` 真实消费 TAG 结果，重复诊断被排除、
  转化指令出现；断开调用时行为回归测试失败。
- **L3**：TAG 是否真正提高科研产出（而不是只减少重复动作），**未验证**；
  需要真实项目 A/B（见 `scripts/test_domain_replay.py` 的合成回放与局限声明）。
