# 示例：单独调用 Mode A（文献调研）

演示不串接其他 Mode，直接做一次带范围和等级的文献调研。

---

## 调用

```
调用 research-idea-pipeline，mode=A
输入：query="diffusion model combinatorial optimization",
      scope="NeurIPS 2022-2025",
      level="L3"        # 因为要支撑"是否有人做过"的判断
```

## 对应命令行

```bash
python3 scripts/literature_search.py \
    --query "diffusion model combinatorial optimization" \
    --level L3 --exhaustive \
    --also-query "score-based generative model discrete optimization" \
    --also-query "limits of diffusion model combinatorial optimization" \
    --from-year 2022 --to-year 2025 --max 20
```

---

## 关键行为：本地命中**不会**让流程停下

### 场景 A：本地库已有 6 条命中

```
## 检索过程记录
- local: 6 条
- arxiv: 20 条          ← 仍然执行，不因本地命中而跳过
- cache_write: 20 条
```

结果集 = 本地 6 条 + arxiv 20 条**去重后的并集**，每条标 source。
**旧行为（本地命中即返回、不请求 arxiv）已被取消**，见
[literature-policy.md §0](../references/literature-policy.md)。

### 场景 B：离线，显式只用本地

```bash
python3 scripts/literature_search.py --query "..." --local-only
```

```
> ⚠️ 仅使用本地库（--local-only）：违反默认检索规则——本地检索不得作为终点，
>    本地结果不构成任何不存在性证据。
```

此模式下**不得**输出任何"没人做过"类结论。

### 场景 C：某个在线源不可用（429 耗尽重试）

```
## 429 等待日志 / arxiv 失败记录
- [429] 限流，等待 10s 后重试（第 1 次）
- [429] 限流，等待 20s 后重试（第 2 次）
- [429] 限流，等待 40s 后重试（第 3 次）
- [429] 限流，等待 80s 后重试（第 4 次）
- [429] 限流，等待 160s 后重试（第 5 次）

> ⚠️ arxiv 暂时不可用，以下结果仅来自本地库
> ⚠️ 检索未达饱和 —— 请记入 INDEX.md 的 Warnings。
```

退出码为 `2`。

### 场景 D：二次运行命中缓存

```
## 检索过程记录
- local: 6 条
- cache: 20 条
```

缓存中的结果仍标 `sources=["arxiv"]`（或对应的源名）并带 `cache_hit: true`。

---

## A3 范围扩大示例

`--exhaustive` 自动逐级扩大，直到**连续两轮零新增**：

```
## 范围扩大记录
- 第 2 轮 [放宽时间范围] max=20 → 新增 0 条
- 第 3 轮 [增加 max_results] max=40 → 新增 0 条

## 饱和与尽职调查
- 饱和：是（连续两轮扩大检索均无新增文献（§3.3 判据 1））
- 等级 L3：未达成  实际 检索式 3 个 / 结果 26 条
- 未达标项：queries, results
```

人工追加同义词检索式可提升覆盖：

| 轮次 | 策略 | 检索式 | 命中 |
|---|---|---|---|
| 1 | 原式 | `diffusion model combinatorial optimization` | 4 |
| 2 | 放宽关键词 | `score-based generative model discrete optimization` | 9 |
| 3 | 否定式 | `limits of diffusion model combinatorial optimization` | 3 |
| 4 | 增加 max_results | `--max 50` | 21 |

---

## A4 输出（节选）

| 论文 | 来源 | 会议/年份 | 核心思路 | 关键假设 | 理论工具 | 相关性 |
|---|---|---|---|---|---|---|
| [Author A, NeurIPS 2023] | arxiv | NeurIPS 2023 | … | … | 扩散过程 | 高 |
| [Author B, ICML 2022] | local | ICML 2022 | … | … | 离散扩散 | 高 |

**负检索记录（L3 必需）：**

| 检索式 | 命中数 | 为何不足以否定目标声明 |
|---|---|---|
| `limits of diffusion model combinatorial optimization` | 3 | 命中的 3 篇均针对连续空间，未覆盖离散置换约束 |

**措辞门禁：** 只能说"据本次检索未见（检索式见附录）"，
**不得**写"目前没有人做过"。

---

## 落盘

```
docs/A001-literature-survey.md      ← 本报告（含负检索记录与饱和判定）
routeA/INDEX.md                            ← 更新文档索引 / TODO / Warnings
```

INDEX 的 Warnings 至少会出现一行：

| # | 警告 | 类型 | 影响 | 处置 |
|---|---|---|---|---|
| W1 | L3 未达成（检索式仅 3 个） | 检索 | 新颖性结论不完整 | 追加同义词与否定式检索式 |
