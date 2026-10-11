<!-- 推荐内容示例：把本文件放到项目的 .dsh/loop.md（需用户授权后再写入项目）。 -->
继续当前科研项目，不要重新初始化。

每轮按顺序做四件事：

1. **Research Resume**。读取磁盘上的 canonical `research-state.json`、必要的认知投影、
   `scheduler.json`，以及已有方法产物（`<route>/methods/*.json`）。已初始化项目**不**执行
   Legacy Handoff，不重复兼容性审查，也不重新 Bootstrap。
2. **Artifact Resolution**。确认真实落盘的产物（Sketch、Candidate、Preference、Contract、
   实验）。只依据文件与 canonical state 判断下一步，不依据上一轮的自我声明。
3. **Scheduler Decision**。按既有 `EIG ÷ cost`、硬门禁与授权选择下一项合法行动。
   I2M 只提出候选动作，派遣与执行仍由既有链路决定。
4. **Scientific Action**。完成本项工作并把产物落盘，然后回答
   Problem / Insight / Method / Evidence / Next Decision。

约束。不把单个方法阶段完成当作整个 Loop 结束。预算、GPU、预注册与人工审批边界不变。
无法推进时报告真实缺口，不重复生成文档。
