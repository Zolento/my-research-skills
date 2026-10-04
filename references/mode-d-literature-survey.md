# Mode D — literature-survey（文献调研）

补充文献、扩大检索范围。可被 A/B/C 调用，也可单独调用。

## 输入

| 输入 | 必填 | 说明 |
|---|---|---|
| 检索关键词或研究问题 | ✅ | 自然语言或布尔式 |
| 检索范围 | ❌ | 时间范围、会议范围、数量上限 |
| 是否强制刷新本地缓存 | ❌ | **默认否** |

---

## D1. 本地检索

按 [literature-policy.md](literature-policy.md) §1 规范搜索本地文献库：

- 匹配字段：标题、摘要、关键词、全文（`.md` / `.json`）。
- 命中则返回，标注 `source="local"`。
- `--refresh` 未开启时，本地命中即返回，**不请求 arxiv**。

## D2. arxiv 补充检索

本地未命中或**信息不足**（判定见 literature-policy §1）时：

- 使用 **Python `arxiv` 包**，查询构造 = 关键词 + 会议过滤 + 时间范围。
- **严格处理 429**：指数退避 `10s → 20s → 40s → 80s → 160s`，最多 5 次；
  重试期间不发起新请求；5 次失败则回退本地结果并标注
  **"arxiv 暂时不可用，以下结果仅来自本地库"**。
- 结果**必须缓存**到 `./local_literature/cache/{query_hash}.json`。
- 每条结果标注 `source="arxiv"`。
- 建议直接调用 [../scripts/literature_search.py](../scripts/literature_search.py)。

## D3. 范围扩大策略

若结果不足，**按以下顺序**逐级扩大，每轮扩大后**重新检索**，直至满足数量或
用户设定的上限：

| 轮次 | 策略 | 说明 |
|---|---|---|
| 1 | **放宽关键词** | 加同义词、上位词（如 "combinatorial optimization" → "discrete optimization"） |
| 2 | **扩大时间范围** | 向前放宽起始年份 |
| 3 | **扩大会议范围** | 加入 ICLR / ACL / AAAI 等 |
| 4 | **增加 max_results** | 提高单次检索上限 |

**升级纪律：** 一次只升一级；每级都记录检索式与命中数。达到用户设定的上限即停止，
不要无限扩大。

## D4. 输出

**文献列表（核心交付物）：**

| 论文 | 来源 | 会议/年份 | 核心思路 | 关键假设 | 理论工具 | 相关性 |
|---|---|---|---|---|---|---|
| [作者, 会议/年份] | local / arxiv | … | … | … | … | 高/中/低 |

**其他交付物：**

- **检索过程记录** —— 每轮检索式、命中数、是否扩大、扩大原因。
- **429 等待日志** —— 格式：`[429] 限流，等待 20s 后重试（第 2 次）`；
  无 429 时明确写"本轮无 429"。
- **本地缓存更新记录** —— 写入的 cache 文件名、条数、时间戳。

---

## D5. 被其他 Mode 调用的接口

| 调用方 | 传递内容 | 期望返回 |
|---|---|---|
| Mode A | `query` + `scope` | 技术路线归纳所需文献 + 创新性边界线索 |
| Mode B | idea 涉及的**特定理论工具** | 该工具的代表工作、假设、局限 |
| Mode C | S-Lit 标记的**"待核实"项** | 针对该条目的定向核实证据 |

调用时只做**定向补充**，不重复拉取已有内容（Step 3 原则）。

---

## D6. 输出后

附 `state.json` 片段：

```json
{
  "mode": "D",
  "timestamp": "2025-01-01T00:00:00Z",
  "query": "diffusion model combinatorial optimization",
  "scope": {"from_year": 2022, "to_year": 2025, "venues": ["NeurIPS"], "max_results": 20},
  "literature_used": [{"title": "…", "source": "arxiv", "url": "…", "ref": "[作者, 会议/年份]"}],
  "retrieval_log": [{"round": 1, "query": "…", "hits": 12, "escalation": null}],
  "rate_limit_log": ["[429] 限流，等待 10s 后重试（第 1 次）"],
  "cache_updates": ["cache/ab12cd34ef56.json (12 条)"],
  "open_questions": ["arxiv 未命中的会议论文需人工补充"],
  "next_mode_suggestion": null
}
```
