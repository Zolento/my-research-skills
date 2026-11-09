# Domain Profile: MRI Reconstruction（`mri-reconstruction`）

> 加载顺序：本文件 → 按需读 `acquisition-contract.md` / `ssl-contract.md` /
> `evaluation-policy.md` / `attribution-guard.md` / `mechanism-search.md` / `variants/`。
> 一次调用只加载当前步骤需要的部分；不要把六个文件全部注入上下文。

## 0. 一句话

在 RLP 的既有证据纪律内，为**欠采样 / 自监督 MRI 重建**研究补充物理与信息边界的判定规则，
把 Agent 的注意力从「反复解释逆问题为什么难」转到「寻找可以改进并证伪的机制」。

## 1. 研究对象

典型任务：CS-MRI、多线圈欠采样重建、SSDU 类自监督训练、跨域生成先验适配（CT→MRI）、
3D Wave / Wave-TOF 高加速重建、微血管弱结构恢复。

核心事实结构（一般多线圈欠采样模型）：

```text
y_Ω = A_Ω x + ε
Ω = Θ ∪ Λ            # 训练输入 / 损失留出（具体拆分由项目协议决定）
Ω_val                # 独立验证测量或验证拆分，用于模型选择隔离
```

`A_Ω` 可以包括 coil sensitivity、Fourier encoding、undersampling mask、wave encoding
及其他**已在项目契约中确认**的物理算子。Profile 不替项目假定任何具体算子。

## 2. 领域规则包

| 文件 | 回答的问题 | 主要机械规则 |
|---|---|---|
| [acquisition-contract.md](acquisition-contract.md) | 物理模型与采集边界是什么？哪些被冻结？ | DP1—DP10（`domain_profile.py`） |
| [ssl-contract.md](ssl-contract.md) | 自监督信息边界：什么能进输入/损失/选择？ | DP 系列 + GT-free 边界 |
| [evaluation-policy.md](evaluation-policy.md) | 改进用什么衡量？阈值何时冻结？ | DP 系列（阈值冻结） |
| [attribution-guard.md](attribution-guard.md) | 哪些归因是重复的、不能改变决策的？ | TG1—TG9（`domain_guard.py`） |
| [mechanism-search.md](mechanism-search.md) | 下一步该探索哪个机制？方法候选是否具体？ | MM1—MM8（`domain_mms.py`） |
| [variants/cross-domain-generative-prior.md](variants/cross-domain-generative-prior.md) | CT→MRI 先验适配任务配置 | 任务级冻结项 |
| [variants/wave-3d-structure.md](variants/wave-3d-structure.md) | 3D Wave-TOF 结构重建任务配置 | 任务级冻结项 |

## 3. 四类区分（贯穿所有领域规则）

遇到性能瓶颈时，先判断它属于哪一类，**再**决定动作：

| 类 | 判定依据 | 正确动作 |
|---|---|---|
| 1. 算子/流程实现错误 | 与原始数据不一致、伴随检验失败、维度错误等**可复现证据** | VALIDITY_BLOCKER：走 R10 修复，优先于一切方法探索 |
| 2. 已知物理限制 | 理论或严格实验已证明的不可恢复边界，且带明确适用范围 | PHYSICAL_LIMIT_WITH_SCOPE：记录负知识，限定研究空间，不虚构可行改进 |
| 3. 方法瓶颈 | 信息存在但当前方法未充分利用 | METHOD_TRANSITION_READY：走 MMS / I2M 设计可证伪干预 |
| 4. 无证据猜测 | 既无新证据也无历史验证的口头归因 | INSUFFICIENT_EVIDENCE：不得写成结论，不得据此改变方向 |

**同一现象可以同时存在多类**（例如：一个真实的 CSM 错误 + 一个已验证的物理限制）。
分类按证据逐条进行，不得用一句"forward operator 问题"概括。

## 4. 与 RLP 核心的衔接

- **发现与候选（R3–R6）**：MMS 是这个阶段的**领域探索策略**，候选仍走既有
  `P1—P6` 算子与隔离 island，不新增探索 Agent。
- **证据契约与实验（R8/R9）**：领域评价指标进入冻结预注册的 `outcomes[]`；
  阈值在结果前冻结，事后不得降低成功标准。
- **结果分析与修复（R9.O/R10/R11）**：SSL 目标改善而图像质量未改善必须作为
  objective mismatch 进入分析，不得自动写成"训练成功"，也不得自动回退到噪声解释。
- **对抗审查（R7/R13）**：审稿视角增加领域检查点（信息泄漏、GT 边界、容量对照、
  幻觉结构），但 verdict 与门禁语义不变。
- **停滞恢复**：TAG 判定的 `REPEATED_ATTRIBUTION` 交给既有 `stagnation-breaker` /
  `prediction_compare.py switch` / I2M / R5.1 定向检索处理；TAG 不绕过 PEIG/AALG，
  不刷新诊断预算，不启动 GPU 实验。

## 5. 配置最小骨架

```jsonc
{
  "_schema": "research-idea-pipeline/domain-profile@1",
  "profile": "mri-reconstruction",
  "acquisition": {
    "forward_operators": ["coil_sensitivity", "fourier", "undersampling_mask"],
    "coils": 20,
    "undersampling": {"pattern": "variable_density", "acceleration": 10},
    "noise": {"model": "gaussian", "level_known": false}
  },
  "gt": {"available": false, "usage": "none"},
  "ssl": {
    "type": "ssdu",
    "split": {"input": "theta", "loss": "lambda", "held_out_validation": "omega_val"},
    "acs": {"usage": "frozen_protocol"}
  },
  "model_selection": {"protocol": "omega_val_only", "uses_gt": false},
  "frozen": {"components": ["ct-fm backbone", "fbs 100 steps"],
             "forbidden_changes": ["主干权重", "推理算法"]},
  "metrics": {
    "primary": {"name": "nmse_global", "threshold": 0.02,
                "frozen_before_results": true, "frozen_at_state_version": 12},
    "structural": [{"name": "vessel_mip_connectivity", "threshold": 0.05,
                    "frozen_before_results": true, "frozen_at_state_version": 12}]
  },
  "resources": {"gpu_hours_budget": 12}
}
```

`_schema` 沿用冻结协议命名空间（见 `references/identity-and-compatibility.md`）；
版本号独立于发行版本。

## 6. 加载与校验

配置由 `scripts/domain_profile.py` 解析（规则 `DP1`—`DP14`）：

```sh
python3 scripts/domain_profile.py load --state <route>/research-state.json --profile mri-reconstruction
python3 scripts/domain_profile.py check --state <route>/research-state.json
```

- `load` 输出解析后的配置与违规列表；未声明时 `{"active": false}`，RLP Core 行为不变。
- `check` 在"声明了 profile 但配置非法"时退出码 3（fail closed）；
  loop 侧（`preset_router._loop_step` 的 TAG 检查点）同样按 fail-closed 处理：
  非法配置会以可诊断的 HOLD 暂停领域守卫，而不是当作"无领域规则"继续。
