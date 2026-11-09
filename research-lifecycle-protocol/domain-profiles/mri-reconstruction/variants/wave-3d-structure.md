# Variant: Wave 3D Structure Reconstruction（3D Wave-TOF 微血管重建）

> 任务级配置样例：以现有 3D Wave-TOF 研究为回放样例。参数以项目契约为准。

## 1. 任务形态

- 3D Wave MRI / Wave-TOF，20-coil wave 算子，固定 z slab，高加速欠采样。
- INR / CNN / 3D local-global 结构建模；微血管与弱对比度结构恢复。
- 自监督拆分：Θ 输入、Λ 损失、Ω_val 模型选择（见 `../ssl-contract.md`）；
  Stage1 anchor 期间采集协议冻结。

## 2. 五类区分（本任务的核心归因纪律）

对"某类结构没恢复出来"，必须先判断属于哪一类，**再**选择动作：

| # | 类别 | 判定依据 | 动作 |
|---|---|---|---|
| 1 | 测量中真正缺乏可恢复信息 | Oracle 检测功效实验（已完成的可信结论）显示该结构在当前采样下不可见 | 记负知识并限定研究空间；不得声称"已恢复" |
| 2 | 测量有信息但模型未充分利用 | 功效可见、oracle 可分，当前方法输出缺失 | METHOD_TRANSITION_READY：MMS 方向 C/D/E |
| 3 | 表示与优化造成的损失 | 同信息下不同表示/训练动力学产生不同恢复 | MMS 方向 C/D；等容量对照 |
| 4 | 先验偏差造成的结构压制 | 结构被系统性平滑/抹除而非缺失 | MMS 方向 B/E；检查先验强度与近端步 |
| 5 | 无法判断 | 无功效实验、无判别证据 | INSUFFICIENT_EVIDENCE：先设计判别实验，不得下结论 |

**不允许仅根据全局 NMSE 下降声称微血管恢复成功**；也不允许凭空恢复没有足够证据支持的
血管并把幻觉当成真实恢复。结构恢复 = 结构指标改善 + 无新增虚假结构 + 测量一致性保持。

## 3. 评价边界

- 全局 NMSE / PSNR 与 2D MIP 血管评价**分开报告**；
  `Lower global NMSE ⇏ Better micro-vessel recovery`。
- 结构指标（连通性、直径分布、检出率）与虚假结构率必须同时报告。
- 已完成的 Oracle 检测功效实验结论用于**限定研究空间**；重复执行等价的噪声诊断属于
  TAG `REPEATED_ATTRIBUTION`。

## 4. 高频平凡归因（TAG 重点）

本任务的历史高频重复归因：`undersampling_information`（"20 倍加速信息不够"）、
`noise_level`、`snr_limit`、`conditioning`（"3D 大核病态"）、`ill_posedness`。
其中只有**带 oracle/理论证据**的不可恢复结论才构成 `PHYSICAL_LIMIT_WITH_SCOPE`；
其余同一指纹重复出现时按 TG4 处理，转 MMS 菜单或带新证据的判别实验。

冻结项：wave 算子、z slab、Θ/Λ/Ω_val 拆分、Stage1 anchor、采样协议。
修改任何冻结项 = C 类变更（用户授权），不是探索的默认出口。
