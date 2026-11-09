# Evaluation Policy（领域评价与阈值冻结）

> 加载时机：R8 冻结预注册之前；以及任何"改进了 / 没改进"的判断之前。

## 1. 评价对象分离

同一个实验可以同时改善一个对象而恶化另一个。以下对象**分开报告、不得互相替代**：

| 对象 | 典型指标 | 常见误用 |
|---|---|---|
| Measurement-domain objective | SSL/一致性损失 | 当成图像质量证据 |
| Whole-image reconstruction | NMSE / PSNR / SSIM（全图） | 当成局部结构证据 |
| Local structure quality | 血管连通性、MIP 结构指标、局部 CNR | 用全局 NMSE 混充 |
| Mechanism-specific observation | 预注册的判别性观测量 | 事后从常规指标里"挑" |
| Robustness / generalization | 跨采样率、跨受试者、跨噪声档 | 单点最优化当成泛化 |
| Visual structural recovery | 盲评 / 结构比对 | "看起来更好" |
| Hallucination / false structure | 虚假结构率、假阳性结构计数 | 只报告新增细节不计假阳性 |

两条最小不等式（必须写进相关报告）：

```text
Lower SSDU loss    ⇏ Better reconstruction
Lower global NMSE  ⇏ Better micro-vessel recovery
```

## 2. 阈值冻结

- 每个 profile 配置的主指标、辅助指标、结构指标与**最小有意义改进阈值**必须在
  **结果产生之前**冻结：`frozen_before_results: true` + `frozen_at_state_version`。
- 配置检查（`domain_profile.py`）会拒绝：缺少冻结声明的阈值、冻结版本晚于当前
  state 版本却声称"事前冻结"、以及事后修改阈值。
- 结果产生后降低成功标准 = 修改冻结协议，属于用户授权的 C 类变更；Agent 不得自行执行，
  也不得在报告中用新阈值重判旧结果。

## 3. 成功判据与主锚点

- 任务成功判据必须与项目主锚点一致（`contract.primary_anchor`）。
  以微血管恢复为锚点的项目，"全局 NMSE 下降"**不构成**任务成功。
- 不允许仅凭全局指标下降声称微血管恢复成功；也不允许凭空恢复没有足够证据支持的
  血管并把幻觉计为恢复成功。结构恢复必须同时满足：结构指标改善 + 无新增虚假结构 +
  测量一致性保持。
- 已完成的 Oracle 检测功效实验（如 3D Wave-TOF 的 oracle 实验）结论应**限定研究空间**：
  功效上不可见的目标不得声称"已恢复"；可见的部分继续探索。重复执行等价的噪声诊断
  属于 TAG 的 `REPEATED_ATTRIBUTION`。

## 4. 容量与预算对照

- 声称"机制改进"的候选必须带**等容量对照**（参数量 / 训练预算 / 数据一致）；
  只扩大网络容量的改进必须如实写成容量效应，不得写成机制创新。
- 训练预算改变属于实验条件变更，需要新的预注册；不得在比较中混用不同预算的结果。

## 5. 报告措辞

- `partially-supported` / `supported` 的措辞纪律沿用 `references/evidence-policy.md`。
- 领域内追加两条：涉及 SSL 损失的结论必须同时报告图像指标；涉及结构恢复的结论必须
  同时报告虚假结构率。缺任何一项，结论只能写 `inconclusive`。
- 领域规则不能自我证明方法有效：MMS/TAG 的运行证据是 L1/L2 层面的；
  L3 科研有效性必须来自真实项目的对照实验（见 release notes 的分级声明）。
