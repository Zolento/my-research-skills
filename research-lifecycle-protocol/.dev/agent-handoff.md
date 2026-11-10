# Agent Handoff — research-lifecycle-protocol/dev（branch-local）

## 当前目标

1. ✅ 更名 `research-idea-pipeline` → `research-lifecycle-protocol`（目录/frontmatter/
   安装/根 README/AGENTS），旧项目与协议命名空间兼容，双根 fail closed。
2. ✅ MRI Reconstruction Domain Profile：`domain-profiles/mri-reconstruction/` +
   `scripts/domain_profile.py`（DP1—DP14）。
3. ✅ TAG（`scripts/domain_guard.py`，TG1—TG9，六类判定，事件链）+ loop 消费点
   （`preset_router._loop_step`，在 `i2m.diagnosis_decision_impact` 之后）。
4. ✅ MMS（`scripts/domain_mms.py`，六方向菜单 + MM1—MM8a 契约）+ TAG 转化菜单。
5. ✅ 合成回放十场景 + 四臂领域消融（`scripts/test_domain_replay.py`）。
6. ✅ release_check 新增 Domain Profiles 步骤；隔离安装/卸载实测。

## 分支状态

- 基线：`main` @ `dcdce9c`（含 1.1.0 发布 + 未发布的科学汇报/运维自主 + Mesh 契约）。
- worktree：`/home/lenovo/code/myproj/skills-dev/research-lifecycle-protocol/dev`。
- 分支提交：896ae67（更名）→ 7d3ac99（MRI profile）→ 3171cce（store 文档移植）→
  本提交（.dev 记录）。
- main 上已知问题：`references/invocation-prompts.md` 存在合并产生的重复段落
  （~38 行 ×2，来自 d9a5949 合并 a8d42f5）。**本分支未修 main**；合并回 main 前须先在
  main 修掉，否则会把重复段落带回。

## 验证读数

- 全量 unittest：2174+ tests OK（skipped=4）。
- `release_check.py` PASS（19 步，含 Domain Profiles 步骤）。
- 隔离安装：`npx skills add <干净副本> -y` → `.agents/skills/research-lifecycle-protocol/`
  frontmatter `name: research-lifecycle-protocol`、version 2.0.0；副本内
  `release_check.py` PASS；`npx skills remove` 实测成功。
- 全局安装（`-g`）在本会话沙箱内因 `~/.agents` 只读未验证（CLI 报 ENOENT/mkdir）；
  需要在无沙箱环境重跑一次 `-g` 安装确认。

## 未完成 / 风险

1. L3 科研有效性未验证：合成回放只能证明机制接线。下一步最值得做的是拿一个真实
   CT-FM 或 Wave-TOF 项目路线做 TAG/MMS 的真实回放 A/B（隐藏未来信息，对照
   core vs +tag+mms 的重复归因次数与方法候选质量）。
2. main 的重复段落修复 + 本分支合并回 main + 打 `research-lifecycle-protocol/v2.0.0`
   tag（合并时执行，本分支不打）。
3. 旧 RSI 分支清理：见 `.dev/decisions.md` D-RLP-7；`feat/failure-analysis` 因有未合并
   提交保留；`feat/zotero` 按任务要求保留。
4. `domain_mms.recommend_directions` 的失败-机制映射基于 finding 文本中的受控 token；
   项目的 failure 记录应尽量把 `mechanism` 字段写成受控枚举，以提高菜单质量。

## 2026-11-10 收尾（合并与安装）

- main 已合并本分支：merge commit `dacfcd6`（`.dev/` 按约定未进 main，KEEP_BRANCH_ONLY）。
- 已打 annotated tag `research-lifecycle-protocol/v2.0.0`（指向 dacfcd6）并推送 origin。
- 合并前的重复段落（invocation-prompts.md Method-Driven/Resume/核心行为 ×2）已在
  1ee83b0 修复，main 上为单份。
- 正式安装：`~/.agents/skills/research-lifecycle-protocol/`（真实目录，v2.0.0，
  release_check PASS 于可写副本；安装副本与发布树字节一致）。旧 `rsi-pipeline`
  （live + .bak 备份 + 大写 RSI-pipeline 死链接）已全部卸载，catalog 只剩新名称。
- 已知限制：沙箱内 `~/.agents` 只读，变异测试（写真实文件再还原）无法在安装副本
  原位运行；用可写副本 + diff -r 字节一致替代验证。


## 2026-11-10 v2.0.1 收尾

- 六个提交（Phase A–E）：4a8f9a5 / 574a1ca / c8820f8 / 5aaed54 / 08427f1 / 2db2852。
- 缺陷修复矩阵与链路图见 docs/releases/v2.0.1.md；replay 接口见
  scripts/domain_replay.py + examples/domain/mri-reconstruction/。
- L3：NOT YET VALIDATED。下一步 = 真实 CT-FM / Wave-TOF 路线按 pack schema 固化后盲化 A/B。
- 遗留：TAG classify 的机制枚举仍是封闭集合（新机制登记 other_declared 待审）；
  指标契约的 GT 来源验证只覆盖 config/protocol 类来源中的机器记录，
  checkpoint 选择记录的深度验证需要 Execution Manifest 落地后的第二阶段。


## 2026-11-10 v2.1.0 合并与发布

- main 已合并本分支：merge commit `cdabc9a`（`.dev/` 未进 main）。
- tag `research-lifecycle-protocol/v2.1.0`（annotated `2ca9445` → cdabc9a）已推送。
- 本机 `~/.agents/skills/research-lifecycle-protocol/` 已刷新为 v2.1.0（与发布树字节一致）。
- 下一步（真实项目迁移）：逐项目 inspect → plan → migrate --apply → verify → Resume；
  Mesh 插件硬编码旧路径的协同修复仍待外部处理。
