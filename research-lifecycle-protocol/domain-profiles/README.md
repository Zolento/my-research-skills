# Domain Profiles（领域研究协议）

> 渐进加载：只有项目声明了 `domain` 时才读取对应 profile。Profile 是 **RLP 规则的领域扩展**，
> 不是第二份事实数据库，不是新阶段，不新增 canonical Research State 对象。

## 0. 定位与边界

RLP 规定科研生命周期行为；DSH Harness / Research Mesh 负责 Agent 生命周期与外部调度；
Domain Profile 只补充**特定领域的语义、探索约束与评价规则**。

三条硬边界：

1. **Profile 不是事实来源。** canonical `research-state.json`、冻结预注册与原始实验产物
   仍然是唯一科学事实。Profile 配置里的参数只用于**判定规则适用性**。
2. **不改变全局证据权威。** Evidence Qualification、R7/R8/R9.O/R10/R11/R13 与
   PEIG/AALG 保持最终裁决权。领域规则不能自我证明其方法有效。
3. **不隐式启用。** 必须由项目契约显式声明；未声明时 RLP Core 行为完全不变。

## 1. 启用方式

项目或路线在控制平面写一个声明文件（**机器可读、人工可审**）：

```text
<project>/.research-lifecycle-protocol/domain/<profile-id>.json                  # 项目级（新根，文档默认）
<project>/.research-lifecycle-protocol/routes/<R>/domain/<profile-id>.json       # 路线级（优先）
<project>/.research-idea-pipeline/domain/<profile-id>.json                       # 项目级（旧根项目，同优先级）
<project>/domain/<profile-id>.json                                               # 2.0.x 平铺位置（兼容回退，最后）
```

优先级：路线级 > 项目级（新根/旧根同层，先找到先生效）> 2.0.x 平铺回退位置。
两个运行根同时存在时，`scripts/rlp_paths.py` 会按既有规则 fail closed；
从平铺位置迁移 = 把文件移入运行根的 `domain/`，不做静默双读冲突。

```sh
python3 scripts/domain_profile.py load --state <route>/research-state.json --profile mri-reconstruction
python3 scripts/domain_profile.py check --state <route>/research-state.json
```

- `load` 输出解析后的配置与适用的规则档；配置缺失时输出 `{"active": false}`，**不报错**
  ——未声明领域 = RLP Core。
- `check` 在"声明了 profile 但配置非法"时退出码 3（fail closed）：一份解析不了的领域契约
  不能被当作"没有领域规则"继续用。

## 2. 当前 registry

| profile id | 用途 | 入口文档 |
|---|---|---|
| `mri-reconstruction` | 自监督/欠采样 MRI 重建科研 | [mri-reconstruction/PROFILE.md](mri-reconstruction/PROFILE.md) |

registry 由 `scripts/domain_profile.py` 的 `PROFILE_IDS` 冻结；新增 profile 必须同时提供
契约文档、loader 校验与测试。

## 3. 通用契约（所有 profile 共同适用）

1. 配置是**声明**，不是实验数据；修改配置不产生科学增量，也不重置任何预算。
2. 配置里的冻结项（frozen components、禁止修改的实验条件、评价阈值）一经结果产出
   **不得回溯修改**；阈值必须带 `frozen_before_results` 冻结声明。
3. GT 可用性是**信息边界**：`gt.available: false` 时，训练与模型选择不得引用 GT；
   独立离线 GT 评价只能作为外部审计存在，且必须显式标注，不得反向污染选择流程。
4. Profile 允许新增的落盘内容只有**控制平面**文件（如 TAG 事件日志、方法候选草稿），
   路径在 route 内，且删除它们不得影响 canonical state 的校验。
5. 每个机械规则集（DP/TG/MM 系列）必须配有离线测试；无法机械证明的判断一律输出
   `review_required`，交人工或 R7，不得自动阻断。
