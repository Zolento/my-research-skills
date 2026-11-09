# Mechanism-to-Method Search（MMS，机制到方法搜索）

> 加载时机：TAG 判定方法可转化（`METHOD_TRANSITION_READY`），或 R3–R6 需要领域探索方向时。
> 机械实现：`scripts/domain_mms.py`；规则 `MM1`—`MM8`。

## 0. 核心思想

MMS 是 **R3–R6 的领域探索策略**，不是新的通用探索引擎，不新增 Exploration Agent，
不替代 `P1—P6` 算子。它解决的问题是：遇到性能瓶颈时，Agent 优先寻找**可以改进的机制**，
而不是不断解释已知困难。

```text
失败/瓶颈（F 条目、异常记忆）
    ↓ 结构化映射（受控机制 token → 六方向）
六方向菜单（按失败证据 + 拥挤度排序；无聚合分）
    ↓ 选择有希望的空间（不机械逐个执行）
方法候选（十问具体化，MM1—MM8 机械检查）
    ↓ 复用既有 I2M：Sketch → Candidate → Preference → Contract → Minimal Test
R8 冻结预注册（既有证据与可识别性规则不变）
```

## 1. 六个探索方向

| id | 方向 | 研究什么 |
|---|---|---|
| `ssl_information_use` | 自监督信息利用 | 不同采样测量的监督信息效率；SSL 目标与重建误差的关系；拆分结构对可学习结构的影响；严格无 GT 下的监督信号改进 |
| `prior_posterior_adaptation` | 先验与后验适配 | 来源域先验与目标域测量失配；conditional posterior adaptation；measurement-dependent prior weighting；先验修正与数据一致性的冲突；后验自蒸馏 |
| `representation_inductive_bias` | 表示与归纳偏置 | CNN/UNet/INR/Fourier/HashGrid 的局部/全局结构；频率/尺度局限；空间结构与不确定性；低参数量适配的有效容量 |
| `optimization_dynamics` | 优化动力学 | 训练优化与最终重建动力学的失配；unrolled 与非展开更新；FBS/HQS/ADMM 机制；固定推理算法中的可达更新空间 |
| `measurement_prior_coupling` | 测量与先验耦合 | 哪些观测方向真正约束先验修正；稳定的 measurement-conditioned correction；避免先验覆盖有效测量 |
| `target_structure_recovery` | 目标结构恢复 | 微小结构与全局指标的权衡；弱对比度结构；结构特定先验；虚假结构控制 |

**六方向不是任务清单。** 按当前 Research State、Failure Memory 与主锚点选择有希望的空间；
`domain_mms.py menu` 只给结构化菜单（失败机制链接 + 已有候选拥挤度），**无聚合分**。

## 2. 方法候选十问（重要候选必须回答）

1. 目标失效机制是什么？（`target_failure_mechanism`，受控枚举）
2. 当前证据支持到什么程度？（引用 `evidence_refs` / F 条目）
3. 方法改变了哪个数学对象或优化规则？（`mathematical_change.changes_object` / `.changed_rule`）
4. 为什么预期会改变重建结果？（`expected_effect.prediction` + 冻结判据 `criterion`）
5. 与最接近工作相比的实质差异？（`nearest_prior_work.reference` + `.delta`）
6. 为什么这种差异在当前 MRI 任务中有意义？（写进候选说明）
7. 什么控制组排除容量/预算等平凡因素？（`control_condition.capacity_matched: true`）
8. 什么实验会否定这个机制？（`expected_effect.falsification_test`）
9. 预期改善是否符合严格自监督边界？（`ssl_boundary_compliance`；GT-free 项目必填）
10. 成功判据是否与主锚点一致？（`anchor_alignment` 引用项目主锚点）

其中 1/3/4/5/7/8/9/10 由 `MM1—MM8` 机械检查；2/6 由证据资格与 R7 审查把关。

## 3. 机械规则（MM1—MM8）

| 规则 | 内容 |
|---|---|
| MM1 | 候选必须携带 `_schema`（冻结协议命名空间的 `method-candidate-mms@1`） |
| MM2 | `direction` ∈ 六方向；不得用"融合注意力/增加频域特征"这类空泛表述充当方向 |
| MM3 | `target_failure_mechanism` ∈ 受控机制枚举；`other_declared` 必须附确认依据 |
| MM4 | `mathematical_change` 必须写清改变的对象与规则；没有可定义的数学对象就不是方法候选 |
| MM5 | `expected_effect` 必须有可证伪预测、冻结判据与否定实验 |
| MM6 | 必须声明等容量/等预算对照；只扩大容量的改进不得写成机制创新 |
| MM7 | 必须指认最接近工作并写明实质差异；核心机制重合时必须如实指出 |
| MM8 | GT-free 项目的 `ssl_boundary_compliance` 必填且不得用 GT 做选择；`anchor_alignment` 必须引用主锚点 |

## 4. 与 I2M 的整合（不建平行流水线）

MMS 候选**就是** I2M 的候选输入：通过既有 `insight_to_method.py` 的
sketch → candidates → preference → contract → minimal test 流转，产物落
`<route>/methods/`。MMS 只增加两件事：

- **菜单**（`menu`）：TAG 触发方法转化时，loop 输出里附带 `tag.transition.menu`；
- **入口检查**（`validate`）：候选进入 I2M 前的领域具体性检查。

进入 R8 前仍须通过既有证据与可识别性规则（`insight_to_method` 的 I2M 系列规则、
PEIG/AALG、预注册冻结）。MMS 不能让任何候选跳过它们。

## 5. 运行方式

```sh
# 领域方向菜单（advisory；无聚合分）
python3 scripts/domain_mms.py menu --state <route>/research-state.json

# 方法候选具体性检查
python3 scripts/domain_mms.py validate --candidate candidate.json --state <route>/research-state.json
```

## 6. 诚实边界

- `menu` 是 **advisory**：它改变的是 loop 在 TAG 触发后展示给 agent 的探索空间，
  不直接改写 scheduler 优先级。
- `validate` 是机械具体性检查：通过 ≠ 科学上正确；机制等价性、新颖性判断仍属 R7/R12。
- L3（真实科研改进）未验证：合成 fixture 只能证明候选契约与菜单机制被真实消费。
