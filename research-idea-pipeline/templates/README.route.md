<!--
路线级 README.md 骨架（路线身份证）。
用法：复制到 routes/<R>/README.md。
职责：这条路线是什么、为什么存在。更新频率很低。
禁止：实验进展、今日 TODO、临时 hypothesis 一律不得写在这里。
      进度看 STATUS.md，资产看 INDEX.md。
-->

# routes/<R> — <一句话路线名>

> **路线身份证。** 本文件更新频率很低，只回答「这条路线是什么」。
> 当前进度见 [STATUS.md](STATUS.md)，材料目录见 [INDEX.md](INDEX.md)。

---

## 1. Research Question

- <这条路线要回答的那个问题>

## 2. Why this route exists

- <为什么值得做，与别的路线不重复>

## 3. Relation to project goal

- 项目主锚点：<见根 INDEX.md 的声明>
- 本路线 `core_goal`：theory / performance / phenomenon / benchmark / feasibility / negative
- `anchor_role`：primary / supporting / orthogonal
- `serves` / `serves_evidence`（`supporting` 必填）：

## 4. Current central thesis

- <当前中心命题，一句话>
- 可证伪条件：<什么观察会推翻它>

## 5. Scope / non-goals

- 做：<…>
- 不做：<…>

## 6. Route lineage

- 来源：<从哪条路线分出，或从零开始>
- 分叉 / 合并：<`forked_from` / `merged` 记录>
- 关联路线：<…>

## 7. Key resources

- 数据：<数据集、许可、可得性>
- 算力：<GPU·小时、显存>
- 外部依赖：<库版本、接口>
- 共享代码：`src/`。共享 config：`configs/base/`。
- 本路线 config：`configs/routes/<R>/`。

```bash
# 环境自检（确认解释器与依赖）
python3 <skill>/scripts/literature_search.py --check-env

# 文献检索（默认全部源）
python3 <skill>/scripts/literature_search.py -q "<关键词>" --mailto you@example.com

# PDF 索引校验
python3 <skill>/scripts/refs_index.py --refs-dir docs/refs --check
```

## 8. Entry points

| 想去哪 | 入口 |
|---|---|
| 当前状态 | [STATUS.md](STATUS.md) |
| 材料目录 | [INDEX.md](INDEX.md) |
| 机器状态 | `.research-idea-pipeline/routes/<R>/research-state.json` |
| 项目总览 | `../README.md` |
| 路线总表 | `../INDEX.md` |

> **禁止把实验进展、今日 TODO、临时 hypothesis 塞进 README。**
> 几个月后它会变成历史垃圾场。进度写 `STATUS.md`，资产写 `INDEX.md`。
