# RLP 2.0.0 开发决策记录（branch-local）

> 分支 `research-lifecycle-protocol/dev`；不进入 main（根 AGENTS.md §5/§13）。

## D-RLP-1 — 更名只改 Skill 身份，协议命名空间与旧运行目录冻结

- schema id（`research-idea-pipeline/...@1`）是不透明数据契约：canonical state、执行账本、
  回放 fixture、认知投影都携带它。改名 = 让所有旧项目失效。
- `.research-idea-pipeline/` 是旧项目的运行根：新项目默认 `.research-lifecycle-protocol/`，
  旧根继续有效；两根并存时 fail closed（`rlp_paths.resolve_storage_root`）。
- 集中点：`scripts/rlp_paths.py` + `scripts/test_identity_compat.py`（生产模块的
  `_schema` 值扫描 + 双根行为 + CLI）。

## D-RLP-2 — 版本 2.0.0：语义化主版本 + legacy-name 元数据

- 更名属于破坏 Skill 身份的变更 → 主版本号递增（1.1.0 → 2.0.0）。
- frontmatter 增加 `abbreviation: RLP` 与 `legacy-name: research-idea-pipeline`，
  供安装器与文档区分身份；`upstream-spec` 更新为新名。
- 历史 release notes（v1.0.0/v1.1.0）不改写；新 release notes 为 `docs/releases/v2.0.0.md`。
- tag 语义沿用：`research-lifecycle-protocol/vX.Y.Z`，打在 merge 进 main 的提交上；
  本分支不打 tag（`test_release_metadata` 的分支感知规则自动适用）。

## D-RLP-3 — Domain Profile 是显式启用的规则扩展

- 启用 = 项目或路线存在 `domain/<profile>.json`（route 优先于 project）；未声明 = RLP
  Core，行为逐字节不变（测试锁定：未声明时 TAG 完全静默）。
- 声明了但非法 → fail closed（exit 3；loop 侧可诊断 HOLD），不得当作"没有领域规则"。
- 不新增 canonical 对象、不新增 Preset（16 个数量冻结）、不加 R15；一切领域数据落
  route 控制平面。

## D-RLP-4 — TAG 的六类判定与失败开放（fail open）边界

- 六类逐字枚举；`VALIDITY_BLOCKER` 永远优先，重复不压制真实缺陷。
- 机制指纹 = `digest({mechanism(受控枚举), assumptions(排序), scope(小写)})`；
  预测与证据引用不进指纹（它们正是重复判定要比较的新信息）。
- **TAG 只对"声明了归因"的动作生效**：scheduler 动作未声明
  `attribution_mechanism/attribution_scope` 时对守卫不可见，保持正常优先级——
  守卫不阻断它看不见的东西。
- 等价性无法机械证明（自由文本机制、部分重叠假设）→ `review_required`，不自动阻断。
- 判定事件写 `<route>/domain/tag-events.jsonl`（append-only + 哈希链 + flock）；
  篡改检出后拒绝追加，loop 侧以 `tag_chain_damaged` HOLD。

## D-RLP-5 — MMS 是菜单 + 契约，不是第二个探索引擎

- 六方向菜单按"失败机制链接 + 已有候选拥挤度"排序，**无聚合分**（沿用 scoring 纪律）；
  advisory，不改 scheduler 优先级。
- 方法候选 MM1—MM8a 机械检查：等容量对照（MM6）、最接近工作 delta（MM7）、
  GT-free 边界与锚点对齐（MM8）为硬项；`anchor_change_requested=true` + 理由时保留
  challenging 候选（改锚点仍由用户授权）。
- 候选经既有 I2M 流转，产物落 `<route>/methods/`；MMS 不建平行流水线。
- 失败上限（MM3a）：同一机制 ≥2 条独立失败 → 必须声明 `scope_change_justification`；
  已验证物理限制（MM3b）：候选必须证明目标在排除范围之外。

## D-RLP-6 — 领域消融是计数对比，不替换 CIE 四臂

- `test_domain_replay.py` 的 core / +profile / +tag / +mms 只统计派遣行为
  （重复被拦截数、novel/validity 保留数），无分数；`ABLATION_ARMS` 四臂语义冻结
  （测试断言）。
- 全部场景为**合成** fixture：证明的是 L2 机制接线；L3 科研有效性未验证，
  release notes 与文档如实声明。

## D-RLP-7 — 旧 RSI 分支清理原则

- 内容等价优先于提交等价：`skill-rsi-dev` 上未推送的 store 文档（737f4af）已先移植到
  本分支，再清理该分支；无法确认等价的（feat/failure-analysis 的英文 README 重写）
  保留并报告。
- `feat/zotero` 按任务要求默认保留。
- 历史 tag 一律不动。
