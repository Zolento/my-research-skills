# MRI 重建训练规范

本规范是 MRI 强约束的**唯一权威来源**，适用于 RLP 管理的所有 MRI 重建项目与路线：
全监督、自监督、2D、3D 与逐例优化。`scripts/mri_training.py sync-agents <project>` 把下列
受管段注入项目根 `AGENTS.md`，项目不再维护第二份 MRI 文字。同步不修改项目已冻结的实验协议，
也不授权新的 GPU 实验。与既有条款、冻结协议或数据条件冲突时，一次性列明冲突与受影响训练，
暂停受影响操作，不自行覆盖。

依据：[MRI Research Contract v1.0](../../docs/contracts/mri-research-contract-v1.0.md)
（用户确认版，2026-11-20）。规范升级不改写历史实验。

<!-- BEGIN RLP MRI TRAINING -->
## MRI 重建训练硬约束（Contract v1.0）

1. **划分与测试隔离**：2D 严格使用已有 train/val/test，以 slice 评价。若同一病例的切片
   跨越不同集合，必须披露该事实，不得称为病例独立泛化。
   3D 必须 subject/patient 隔离，同病例衍生的 slab/patch/slice 不跨集合。test 仅在方法、配置、
   checkpoint 与指标冻结后做最终评价，不用于调参或选模。发现既有划分违规时 HOLD，不自改。
2. **自监督与选模**：自监督的梯度、输入、loss 与训练归一化不得访问 GT，严格遵守冻结的
   Ω/Θ/Λ/ACS。存在完整 val GT 时按事先固定的 `full_val_gt` 与主指标（PSNR 最大或
   complex_NMSE 最小）在完整 val 选 `best_val`，不得称为全流程 GT-free。真正没有 val GT 的
   项目允许经用户确认、**事先冻结**的 `gt_free_frozen`：必须声明无 GT 的选择指标、方向、来源、
   范围与停止准则，并绑定预注册。不得默认用训练 mask-split loss 或 test GT 选模。
   缺少合法方案时 HOLD。
3. **开发诊断与正式证据**：允许固定、可追溯的 val 子集做 smoke、错误定位与探索诊断，
   不得作为正式选模、主要消融或完整验证结论。正式选模、主消融与整体结果使用全量 val，
   最终结果使用冻结的全量 test。固定 ROI 或子组分析须标明覆盖率，不能替代整体评价。
4. **2D mask 强制约定**：2D 单方向 Cartesian 数据在标准 k-space `[H,W]` 表示下，
   **沿 W 变化，每个采样列沿 H 恒定**（竖条纹列采样），不得改为行采样或用转置伪造。
   存在 per-slice mask 时必须按实际 subject/slice/acquisition 精确配对，禁换共享 mask
   或新随机 mask。ACS、线数、加速率与轴向必须与冻结协议一致。
   3D 与非单方向 Cartesian 按各自冻结的采集契约执行。
5. **物理算子与纯伴随**：固定复数 dtype、FFT 轴与 norm、CSM 来源（见第 10 条）、mask、
   前向与伴随及坐标，
   并在真实调用点执行 adjoint 内积、FFT、shape 与轴测试。多线圈 Cartesian 的纯 `A^H`、
   ZF 初始化与评估线圈合并不得隐式除以 `D = Σ|S_c|²` 或 `√D`，不得悄悄加入采样密度权重、
   CSM 再归一化、线圈能量阈值置零，或以 RSS 取代复数主参考。`D` 是线圈灵敏度能量，
   不是采样密度。冻结方案明确声明的 SENSE/CG/PCG 正规方程与预条件器可独立合法使用，
   但不得改变纯伴随定义与 ZF/GT 评估口径。
   **灵敏度来源见第 10 条**：默认强制使用数据集存储的 CSM，只有显式联合估计灵敏度的
   方法类别例外。
6. **尺寸、尺度、指标**：2D 按处理后的原生全尺寸训练、验证与测试，不擅自裁剪、缩放或旋转。
   3D 可按已冻结协议用 patch/slab 训练，正式评价保持物理坐标与规定的 volume/ROI 定义。
   所有拥有 GT 的数值评价按每个评价样本的 GT 幅度 RMS `r = sqrt(mean(|GT|²))` 建立共同尺度，
   参考与预测**同除以 r**，禁止单独校准预测或事后最优缩放。自监督训练与 GT-free 选择
   不得访问 GT RMS。主 NMSE 为 `Σ|pred−GT|²/Σ|GT|²` 的 `complex_NMSE`，
   `magnitude_NMSE` 必须单列。PSNR 与 SSIM 在幅度图上用同一 GT 幅度峰值作 `data_range`，
   样本聚合方式事前冻结。
7. **训练前完整编号报告**：每段新训练启动前向用户编号分节完整汇报实验目的、数据与划分、
   维度与尺寸、mask/ACS/采样方向、前向与伴随算子、CSM 模式与来源与样本配对键、
   训练归一化、输入输出、损失、
   优化器、初始 LR 与调度、epoch/step 预算、选模协议与指标、checkpoint、配置与代码版本、
   资源与授权状态。正常通过的内部审计不逐项汇报，科学异常、协议冲突、风险与训练设置
   不得隐藏。报告本身不是新的训练授权。
8. **checkpoint 与复现**：默认 `best_val` 与 `latest`，两者都可恢复模型、优化器、进度、
   选择值与适用的 scheduler、AMP、随机与 sampler 状态。额外里程碑需冻结授权。
   保存实际生效配置、数据版本、mask、来源、commit、指标与 checkpoint 的关联，不篡改旧实验。
9. **关键不确定：一次性询问**：若既有 AGENTS、冻结协议、state、代码与数据元信息不足以确认
   可能改变训练、算子、划分、评价、预算或写入权限的事项，暂停**受影响操作**，把全部关键
   未决项、影响、现行冲突与推荐选项**集中一次性询问用户**。不得自行猜默认值后执行，
   不得拆成连续碎片化问题，已回答内容不重复问。不受影响的只读工作可以继续。
10. **CSM 来源（MRI-10，强制）**：常规多线圈方法在训练、验证、测试与推理中，前向与伴随算子、
    数据一致性、ZF 初始化与线圈合并一律使用**与样本正确配对的数据集存储复数 CSM**。不得用自行
    估计的 CSM、共享模板、其他样本的 CSM 或模型预测的 CSM 替代，不得擅自重新估计、归一化、
    裁剪或平滑。只允许保持物理值不变的维度与格式适配，且变换可追溯。
    **唯一例外**是方法自身把灵敏度 `S` 作为联合重建的待估变量、可学习输出或联合优化对象，
    且在**实验启动前**已写入冻结方法协议：须写明 `S` 的数学定义、输入与初始化、约束、
    优化或学习过程、训练与推理时的来源，以及评价时的线圈合并口径。仅在预处理阶段单独重估
    CSM、后续重建并不联合估计的做法**不属于**该例外。
    非联合估计方法发现 CSM 缺失、来源不明、样本配对不一致或与冻结设置冲突时 HOLD 并一次性
    汇总冲突，不得用重估、除以 `D`、RSS 或从其他病例复制来隐式修复。单线圈声明
    `not_applicable`，不伪造线圈维度。训练前报告须写明 `csm.mode`、真实存储来源与样本配对键，
    联合估计另给冻结协议引用。数据加载、算子调用、模型执行与评估入口须有可重复断言核对
    同一声明。第 5 条的纯伴随与禁止隐式 `D` 补偿在两种模式下都有效。
<!-- END RLP MRI TRAINING -->

## 执行绑定要求（不注入项目 AGENTS 的机器规范）

受管段写入人可读的硬约束。下列字段由 `experiment_execute.py` 的 `issue` / `run` 逐个核对，
缺项或与领域 profile 相反时拒绝，不静默兜底。

1. **绑定配置**：至少一个绑定的 JSON 配置必须含 `mri_training` 对象。训练模式必须提供非空
   `budget`、`learning_rate`、`optimizer`、`input`、`output`、`mask`、`normalization`、
   `csm`、`checkpoint`、`report_ref`。单线圈项目在相应字段写明 `not_applicable` 并解释。
   `report_ref` 指向已呈给用户的训练前报告记录。
   `csm` 是对象，`mode` 只取三个值：
   - `dataset_stored`（默认）：必须给出 `source`（真实存储来源，如数据集字段或文件）与
     `sample_identity`（配对键，如 `subject/volume/slice/acquisition`）。
   - `joint_estimation`（唯一例外）：必须给出 `protocol_ref`（启动前冻结的方法协议，路径须存在）、
     `eval_reference`（评价时的线圈合并口径）。若 `eval_reference` 不是项目冻结口径
     （`stored` / `frozen_protocol`），还须给出指向冻结协议的 `eval_reference_ref`。
   - `not_applicable`：单线圈，不伪造线圈维度。
2. **两种选择模式，二选一**：
   - `selection: full_val_gt`：要求 `best_val_metric` ∈ {`PSNR`, `complex_NMSE`}。
     领域 profile 必须声明 `gt.available: true`、`model_selection.uses_gt: true`。
   - `selection: gt_free_frozen`：要求 `selection_metric`、`metric_direction`
     （`maximize` / `minimize`）、`metric_source`、`selection_scope`、`stop_rule`、
     `selection_source_ref` 全部非空，且 `selection_source_ref` 指向真实存在的预注册文件。
     领域 profile 必须声明 `gt.available: false`、`model_selection.uses_gt: false`，
     且 `model_selection.metric` 与 `selection_metric` 一致。**不得要求 GT-free 项目改用
     `full_val_gt`，也不得让 GT-free 静默回退到训练损失。**
3. **禁止项**：`model_selection.uses_loss_measurements: true` 一律拒绝。
   用 test GT 选模、未被用户确认的 GT-free 方案、缺少预注册绑定的 GT-free 方案同样拒绝。
4. **同步与幂等**：`sync-agents` 只管理 `BEGIN/END RLP MRI TRAINING` 受管段，保留项目自己的
   文字，重复同步不改变文件内容。受管段与其 SHA 不一致时，`issue` / `run` 返回
   `MRI_TRAINING_AGENTS` 并拒绝执行。
5. **执行门禁不变**：`execution_binding` 仍是唯一入口，绑定结果进入 receipt digest。
   绑定后的配置字段被改动时 `run` 返回 `RECEIPT_CONTENT_MISMATCH`。
   不新增状态源、不新增 R 阶段、不新增报告流水线。

## 项目启动与申请

- `start-project` 的 B0 识别 MRI 重建任务，B2 运行
  `python3 scripts/mri_training.py sync-agents <project>`。已有项目在首次按本规范训练前同步。
  项目已有冲突条款时先向用户指出，不把写入视为冲突已解决。
- 只运行已选模型的评估入口时，绑定配置可用 `"mri_training": {"mode": "evaluation_only"}`。
  含权重更新的命令必须走训练门禁，科学审查核对实际命令与声明一致。
- 执行器核对项目规则、选模声明与绑定字段。审查训练入口、数据加载、验证与指标实现，
  核对实际目录、全量评估、尺寸、mask、checkpoint 与指标口径，以实际代码、抽样检查与恢复
  验证作依据。直接用外部调度器启动训练时同样遵循项目根规则。
