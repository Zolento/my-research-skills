# MRI Replay Packs（真实科研回放评测接口）

> 结构化 fixture，用于后续**真实项目**盲化 A/B 的评测载体；不是真实项目历史，
> 运行它们只证明机制接线（L2）。L3 科研有效性：**NOT YET VALIDATED**。

## 防泄漏协议

1. 每个 pack 声明 `visible`（决策点当时可见的材料）——运行器只读取 pack 文件本身。
2. `hidden_after` 列出被隐藏的后续事实，作为泄漏审计依据；运行器**永远不读**它们。
3. 真实项目回放 = 把真实路线的当时材料按本 schema 固化成 pack，交独立评测者运行。

## Pack 字段

| 字段 | 说明 |
|---|---|
| `task` | `cross_domain_generative_prior` / `wave_3d_structure` |
| `decision_point` | 历史决策点描述 |
| `visible.failures` | 当时的 Failure Memory（F 条目） |
| `visible.prior_declarations` | 当时已做过的归因声明（用于重复判定） |
| `hidden_after` | 被隐藏的后续结果/决策（防泄漏） |
| `probe` | `{kind: diagnosis, declaration}` 或 `{kind: method_candidate, candidate}` |
| `expected` | `{no_fallbacks: [机制], allow: [可接受分类]}` |

## 运行

```sh
python3 scripts/domain_replay.py validate --pack examples/domain/mri-reconstruction
python3 scripts/domain_replay.py run --pack examples/domain/mri-reconstruction
```
