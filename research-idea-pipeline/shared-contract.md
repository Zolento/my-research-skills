# CIE Preset Shared Contract（所有 Preset 共同适用）

> 这是加载时的共同契约，不是新的 R 阶段、Research State 或 Scheduler。加载一个预设时，先读取当前安装版 `SKILL.md`、项目 `AGENTS.md` / 适用 `CLAUDE.md`，再加载本文件与选中的单个 Preset；需要时按现有 references 补充。不得一次注入所有预设。

## 权威与权限

1. 仅使用当前项目已生效的研究契约、路线锚点、已有授权、实际执行环境；已有 `research-state.json` 不得重新 Bootstrap。尚未确定路线且不能唯一确定时，先解决路线归属；不猜测。
2. canonical Research State、冻结预注册与原始实验产物是科学事实依据。Cognitive Memory、Context Brief、Strategy Memory、Preset 事件均为索引、派生或辅助建议，不是第二份科学真相。
3. 证据必须经过现有 R8/R9.O/R10/R11 及 Evidence Qualification 规则；运行失败不等于机制被否证；未经事前冻结的预测不能追认。Scope 不得无证据扩大。
4. 现有 AALG、PEIG、容量/干预强度/优化条件/可识别性、公平对照、资源限制、角色隔离和 Anchor Change Order 均优先于 Preset。
5. 先判断意图是否只读/建议/执行；只读请求不能触发实验或科学状态写入。不可自行授权 GPU、修改主锚点、推送、合并、发布或执行破坏性操作。
6. 每次科研动作之前从磁盘恢复相关 State、Scheduler、Cognitive Memory 与尚未完成的执行检查点；重要更新后核验、持久化并保证可恢复，不依赖聊天历史。
7. 如本环境没有自动事件监听器、运行时执行器或 Dispatcher，不能假装 Preset 已自动触发/动作已派遣。明确输出 `recommendation_only` / `blocked` 以及缺口。

## 标准执行与回报

- 开始：报告 `preset_id`、入口、路线、state_version、意图与执行边界，核验关键先决条件。
- 过程：使用已有 R 阶段和工具完成本 Preset 所定义的工作；任何失败、证据与权限冲突均保留原始来源和范围。
- 结束：给出 `action_taken`、`scientific_delta`、`decision_delta`、`state_writeback`、`next_action`、`stop_reason`；无变化应如实写 `none`，不得包装为 Insight。
- 派生记忆写回前先确认源版本；若 State 变化，按现有授权更新 canonical 再重建认知投影。只有实际拥有的 API 才能调用，不得虚构工具或状态字段。
