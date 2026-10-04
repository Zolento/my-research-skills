# 示例：单独调用 Mode D（文献调研）

演示不串接其他 Mode，直接做一次带范围的文献调研。

---

## 调用

```
调用 research-idea-pipeline，mode=D
输入：query="diffusion model combinatorial optimization",
      scope="NeurIPS 2022-2025"
```

## 对应命令行

```bash
python scripts/literature_search.py \
    --query "diffusion model combinatorial optimization" \
    --from-year 2022 --to-year 2025 \
    --max 20
```

### 首次运行（本地未命中，走 arxiv）

```
# 检索：diffusion model combinatorial optimization
# 命中：18 条
 1. [Author A et al., arXiv 2023] ...
    来源: arxiv    https://arxiv.org/abs/...

## 检索过程记录
- local: 0 条
- arxiv: 20 条

## 429 等待日志
- [429] 限流，等待 10s 后重试（第 1 次）

## 本地缓存更新记录
- ./local_literature/cache/ab12cd34ef567890.json (20 条)
```

### 二次运行（命中缓存，不再请求 arxiv）

```
## 检索过程记录
- local: 0 条
- cache: 20 条
```

### 若本地库已有命中

```
## 检索过程记录
- local: 6 条
```

此时**不会**触碰 arxiv，`429 等待日志` 显示"本轮无 429"。

---

## D3 范围扩大示例

假设首轮 `--max 20` 只返回 4 条，按顺序逐级扩大，每轮记录：

| 轮次 | 策略 | 检索式 | 命中 |
|---|---|---|---|
| 1 | 原式 | `diffusion model combinatorial optimization` | 4 |
| 2 | 放宽关键词 | `score-based generative model discrete optimization` | 9 |
| 3 | 扩大时间范围 | 起始年 2022 → 2019 | 14 |
| 4 | 扩大会议范围 | 加入 ICLR / AAAI / ACL | 21 |
| 5 | 增加 max_results | `--max 20` → `--max 50` | 38 |

达到用户设定的上限即停止。

---

## D4 输出（节选）

| 论文 | 来源 | 会议/年份 | 核心思路 | 关键假设 | 理论工具 | 相关性 |
|---|---|---|---|---|---|---|
| [Author A, NeurIPS 2023] | arxiv | NeurIPS 2023 | … | … | 扩散过程 | 高 |
| [Author B, ICML 2022] | local | ICML 2022 | … | … | 离散扩散 | 高 |

**待核实：** arXiv 元数据不含会议信息，会议归属需人工或额外来源确认。
