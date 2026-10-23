# 科研汇报示例（X88–X90，MoSA 2026-10-24 快照）

> 本文件演示**同一条事实**在修改前后的两种写法。示例数据取自 MoSA 项目当日快照，
> 只用于说明汇报形态。它不是本 Skill 的科学证据，也不替代项目里的 canonical state。
>
> 默认写法遵守 [scientific-communication-policy.md](../references/scientific-communication-policy.md)。
> 操作分类遵守 [operational-autonomy-policy.md](../references/operational-autonomy-policy.md)。

## 1. 修改前：操作细节占据主文

### 1.1 X88

```text
X88 全 val1000 参照已完成。
- 远端 /home/zhanglt/code/MoSA_statealign_20261022，PID 1713654 已退出，
  GPU UUID GPU-c0599104-96d9-ae2c-f6e3-01920fd7e2bd。
- state_version 162 升至 163，E110/E111 已写入，STATUS 已刷新，认知投影已重建。
- X88 与 X89 已置 done；scheduler 仍为 160，监控记录仍是旧的。
- 需要你确认是否继续同步 X90 监控记录，以及是否允许我刷新 scheduler。
```

### 1.2 X87

```text
X87 的 PID 1227614 收到 SIGTERM，进程已退出。
我把 X87 标记为 done，因为两臂已经跑了 20/2000 步。
请确认是否把这次停止写成 negative result。
```

### 1.3 X90

```text
X90 pilot 正在运行。PID 3025775，GPU UUID GPU-c0599104-96d9-ae2c-f6e3-01920fd7e2bd，
远端 root /home/zhanglt/code/MoSA_em_prior_20261023，当前 417/512，
约 110 秒/例，预计还需数十小时。scheduler state_version=160，
是否需要我更新状态并继续监控？
```

**问题：** 主文没有回答科学问题。读者看不到方法原理、证据边界与下一步判别标准。
X87 还把进程终止写成了完成。Agent 把维护动作转交给用户确认。

## 2. 修改后：科学优先，维护内部完成

### 2.1 X88：结果已落盘，证据边界清楚

```text
### Problem
当前要判断：目标域监督先验与适配方法之间的差距，是否足以支撑“适配机制有效”的主张。
这个差距是主锚点（性能）的上界参照，不是方法本身的成绩。

### Insight
全 val 参照显示，目标域监督先验比两条适配臂高约 1.24 dB。
差距在配对切片上稳定，但这是 val 上的描述性参照。
它只说明“上界在哪里”，不证明适配机制成立，也不证明因果。

### Method
参照臂是固定 100k EMA 的目标域模型。它与适配臂使用同一数据划分、
同一 100 步 FBS、同一 image 域噪声与同一评估口径，只改变先验来源。
因此它校准的是“监督先验上界”，不是新方法。

### Evidence
- 参照：PSNR 37.225，SSIM 0.930，NMSE 0.00507。
- TPOT 臂：PSNR 35.988，SSIM 0.918。
- 配对差：+1.237 dB，95% CI [1.200, 1.273]；SSIM 差 +0.0119 [0.0113, 0.0124]。
- 口径：val 1000 切片 / 660 volume / 100 FBS / fp32；不是 test。
- 适配臂读数约 35.966—35.988，差距约 1.24 dB。

### Decision
不在 val 上调参，也不把 val 差距写成 test 结论。
下一步是在独立 test 或 volume-disjoint 划分上做固定预算配对检验。
判别标准：配对 ΔPSNR 的 95% CI 下界 > 0.1 dB，且 SSIM 不降；
否则把主张收窄为“val 上的监督先验参照”。
```

### 2.2 X87：进程终止不是科学完成

```text
### Problem
X87 要检验：训练状态匹配是否能解释单步部署迁移的不足。
这是机制判别问题，不是“训练有没有跑完”的问题。

### Insight
用户在 a800 队列中止了 X87。当前只有两臂各约 20/2000 步的有限读数。
没有完整 val，也没有可判别的配对结果。
因此目前没有支持或否定该机制的科学结论；中止本身不是负证据。

### Method
两臂共享同一父模型、优化器、数据与预算，只改变 clean-side 状态构造。
原计划在 2k 步后做 full-val 配对比较与尾部检查。
这个设计仍可回答机制问题，但必须按冻结预注册执行。

### Evidence
没有任何合法 outcome 事务。SIGTERM 只说明执行被中止，不说明机制失败。
state 仍为 running/未闭环；没有新增 E 或 F，也没有把中止写成 negative result。

### Decision
两条合法路径：
① 若用户重新授权，按原预注册恢复同一实验；
② 若不恢复，记录为 incomplete execution，保留原始产物，不进入科学证据。
不自动重启，不把 X87 标为 done。
```

### 2.3 X90：长 pilot 只报一行状态，重点解释方法

```text
### Problem
单步 FBS 的误差，是否主要来自源先验与目标分布失配？
如果失配是主因，那么把“单点源输出”换成“条件后验样本”应当改变误差结构。
这是机制问题，不是单纯把 PSNR 调高。

### Insight
候选机制是：用 EM 后验替代确定性源端点，改变的是先验对象，
不是只增加容量。竞争解释至少有三类：
① 收益来自额外计算或采样步数；② 来自 working likelihood 的近似；
③ 来自 GMRES 截断或缓存误差。当前 engineering 结果不能区分它们。

### Method
条件模型写成 p(x|y) ∝ p(y|x) p(x)。
E 步在局部线性化后用 GMRES 求后验均值与协方差，再做条件采样；
M 步只更新 adapter，源模型冻结。
实现用 64 个 posterior steps、GMRES 8 次迭代、t∈[0.01, 0.99]、σ=0.03。
关键假设：端点近似高斯、前向可线性化、截断求解误差可控、噪声模型匹配。
与最近 baseline 的区别是“后验采样对象”，不是模块数量。
最可能的失败机制：GMRES 遇到负曲率或非 PSD 近似，后验样本失真；
其次是 working likelihood 与真实后验不一致，导致 EM 不单调。
能区分这些机制的实验：fixed vs refreshed bank 的配对 val1000，
同时报告 PSNR/SSIM/NMSE 的 CI、尾部与采样步数敏感性。

### Evidence
目前只有 engineering 证据：10 项 CPU 测试、16 次 M 更新、
源模型冻结与 GT 隔离检查通过。
pilot 在 baseline val 上约 417/512，尚无配对效果读数。
这些只证明可执行性，不证明方法有效，也不证明机制成立。

### Decision
等待 fixed vs refreshed 的配对 val1000 完成，不自动扩到 100k。
判别标准：配对 ΔPSNR 的 CI 与尾部同时支持方向，且 0.02 dB 实用阈值不被越过；
若为零或有害，停止扩规模，保留负结果并检查上述三类失败机制。
运行状态：pilot 正常，预计仍需数十小时；不影响当前方法判断。
```

## 3. 用户要求详细审计时

```text
审计模式：以下信息按用户显式请求展开，科学结论与默认模式一致。

- X88 来源：results/A/gt_mri_reference_20261022/gap_comparison_val1000.json；
  参照运行 PID 1713654；远端 /home/zhanglt/code/MoSA_statealign_20261022；
  GPU UUID GPU-c0599104-96d9-ae2c-f6e3-01920fd7e2bd。
- X87 停止凭证：results/A/trajectory_state_20261022/user_stop_20261022.json；
  PID 1227614；signal SIGTERM；all_target_processes_exited=true。
- X90 启动凭证：results/A/em-prior-gmres-20261023/launch_verified.json；
  manager PID 3025775；pilot PID 3025788；GPU UUID 同上。
- 维护状态：scheduler state_version=160，canonical=163；scheduler 已过期，
  其 next_actions 与监控记录不得作为当前决策依据。
- 未完成项：X87 无 outcome 事务。
- 未完成项：X88/X89 无 outcome 事务。
- 未完成项：X90 仍在运行。
```

**详细模式只展开事实，不改变结论。** 默认模式隐藏的 PID、GPU UUID、长路径与版本号，
在审计模式下原样给出。维护失败与证据缺口也一并列出。

## 4. 负结果示例（合成，不是 MoSA 结果）

```text
### Problem
判断方法 M 在匹配预算下是否改善重建。主锚点是性能，不是“实验是否跑完”。

### Insight
配对结果没有显示改善。这排除了“在当前 scope 下有实际增益”，
但没有排除实现错误、功效不足或分布差异。
“方法无效”与“本次比较不可判别”仍是两个竞争解释。

### Method
M 与 baseline 使用同一数据、同一容量、同一优化预算，只改变训练目标。
因此负结果不能归因于容量或预算不公平。

### Evidence
ΔPSNR = +0.02 dB，95% CI [-0.03, 0.06]；SSIM 变化 -0.001。
机制代理读数没有同向变化。样本为 32 个配对切片，功效只够排除大于 0.08 dB 的效应。
这是 scoped negative evidence，不是对方法的全局否证。

### Decision
不扩大规模，也不把结果写成“方法被证明无效”。
先做实现与功效审计；若确认是有效负结果，收窄 claim 并保留 negative knowledge。
只有独立复制满足冻结标准后，才建立 stop rule。
```
