# CIE Preset Library — 集成说明（16 个协议）

这是可直接复制到 `research-idea-pipeline/` 中的 **Preset 内容包**，不是已修改远程 Git 仓库的声明，也不是完整 Router / Runtime 代码。

## 集成最小动作

1. 将 `presets/`、`shared-contract.md`、`preset-registry.json` 拷入 Skill 根目录。若现有分支已有相同文件，先 diff，按权威 Spec 合并而不是覆盖。
2. 在现有 `SKILL.md` 四层解析器后挂接 **Preset 子路由**：顶层 `start-project` / `continue-research` / `explore` / `audit` 仍是唯一入口。只在匹配意图后加载 Registry 条目与对应一个 Preset；保留现有语义入口对 `phase=` 的优先级规则。
3. 规范化 `preset_id`、自然语言意图与只读/执行授权；禁止将“总结一下”“不要执行”路由为执行型 Preset。显式 `preset_id` 可避免歧义，但不能提高执行权限。
4. 每次调用加载当前版 `SKILL.md`、`shared-contract.md`、对应一个 `presets/<id>.md` 以及必要阶段 references。不要把全部 16 份预设注入一个上下文。
5. 自动型 Preset 必须由现有 Scheduler、日志事件或外部 Hook/Runner 触发、持续化并防重复；如运行时不具备监听/派遣能力，只允许推荐，不得宣称自动执行。
6. 对 Strategy Evolution：L1 建议 / L2 Adapter 实际消费 / L3 科学效果三层分别验收。缺少 Adapter 必须 recommendation-only。
7. 预设本身不能单独证明路由、自动触发、持久恢复已经落地。需要新增路由单测、事件去重测试、权限测试、端到端 State 恢复测试。

## 路由建议和冲突优先级

- 四顶层入口语义契约优先，不因 Preset 改写。明确 `phase=` 依原 SKILL.md 现有优先级处理。
- 安全、证据、运行有效性问题先于发现策略；其后是 Context Recovery，再是 Stagnation / Paradigm Escape。
- 用户的只读意图必须保持只读；任何同时命中“审查/继续实验”的模糊表达以较低权限处理或请求澄清。
- 某状态快照同一原因不得重复触发相同恢复 Preset；必须有 reason key、last_action、冷却/终止条件，避免嵌套递归。
- `research-recovery` 不等于 Legacy Handoff；旧项目初次接入仍遵守现有入口接管协议，但本包不新增 Handoff Preset。

## 如何验证

A. 16 个文件与 Registry 路径均存在；Router 返回选中 `preset_id`、入口与执行边界。  
B. 只读请求不产生任何科学状态写入或实验副作用。  
C. 停滞/工程故障/证据冲突互不误判，并且同一状态快照不会无限重触发。  
D. 跨会话重新加载 Skill、State、Memory 后下一动作合法且不重复已完成实验。  
E. Strategy Evolution 的下一动作对照不能伪造 `decision_changed`，缺实际 Dispatcher 不宣称 L2。

## 文件列表

- `shared-contract.md`：跨预设统一执行/证据/记忆边界。
- `preset-registry.json`：16 个预设的机器可读入口元数据。
- `presets/*.md`：16 份独立执行协议。
- `INTEGRATION.md`：接入方式与验收条件。

- `router-fixtures.json`：意图路由的 16×3 个自然语言正例和 5 个约束/否定反例；实际路由行为需要由代码或受支持 Harness 实现和运行测试。
