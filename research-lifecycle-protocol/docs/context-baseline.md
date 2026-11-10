# RLP 上下文基线（v2.2.0 · Phase A）

**结论：常规科研动作的上下文里，`SKILL.md` 占 55%—89%。** 先把这句话量出来，才谈得上精简。
本文件记录 v2.2.0 改动**之前**的实测基线，供之后的每一轮对比使用。

- 被测版本：`research-lifecycle-protocol` 2.1.1（`main` = `787b1d9`）
- 被测提交：`research-lifecycle-protocol/dev` @ `f02b340`
- 测量工具：`scripts/context_profile.py`（本轮新增，见 §1）
- 复现命令：见 §8

---

## 0. 先分清六层「上下文」

「Token 消耗」是一个含混的说法。本基线把上下文成本拆成六个互相不可替代的层，
并对每一层单独声明测到了什么。**不做这种拆分，下面的数字就没有意义。**

| 层 | 测什么 | 本基线是否可测 | 精度 |
|---|---|---|---|
| `static` | 磁盘上每个文件的确切字节数 | 可测 | 精确 |
| `loaded` | 某场景下加载器**实际读取并返回**的字符数 | 可测 | 精确 |
| `visible` | 真正进入模型请求的文本 | **不可测**（见 §2） | 单次外部观测 |
| `duplicate` | 已加载文本之间的逐字重复 | 可测 | 精确 |
| `estimate` | 启发式 token 估算 | 可测 | **估算**，非 tokenizer 输出 |
| `calls` | 工具调用次数 | 可测 | 保守估算 |

### 0.1 关于 token 的诚实声明

**本仓库没有可用的 tokenizer。** 实测目录内 `tiktoken` 与 `transformers` 均不可导入。
因此本文件**不产出**「真实 Token 数」，只产出两列：

- `chars`：精确字符数
- `est_tokens`：`heuristic_v1` 估算，方法为「CJK 字符 1 token/char + 其余非空白
  1 token/4 chars，向上取整」。

**为什么不用固定系数乘字节数。** 一个中文字符在不同 tokenizer 下可能是 1 到 2 个 token，
拉丁文本约 4 字符 1 token。用单一系数换算出的数字，精度是假的。`heuristic_v1` 对中文取
1.0 token/char 是偏低的一侧，因此估算值不会被夸大。

**本文件里没有任何一行是「把 Markdown 字节数除以固定系数然后称为真实 Token 统计」。**

### 0.2 关于场景读取集合的诚实声明

每个场景的 `baseline_reads` 是**按当前 `SKILL.md` 的书面加载指令推导**出的读取集合。
它**不是**观测到的模型请求。推导依据逐场景写在 `scripts/context_profile.py` 的
`baseline_rationale` 字段里，可逐条核对。

因此下表的 `loaded` 层回答的问题是：

> 「一个遵守当前 `SKILL.md` 书面指令的 Agent，在这个场景下会读到多少文本」。

它**不**回答「某个具体 Agent 那一轮实际读了什么」。

---

## 1. 测量工具

`scripts/context_profile.py` 是只读的测量器，不是第二个 Agent 执行框架。它做四件事。

1. 按场景枚举读取集合，逐文件真实读盘，统计字符与字节。
2. 用行级 3-gram 量已加载文本之间的**跨文档**逐字重复。
3. 按标题文本（不是行号）定位「本场景用不到但被加载」的章节。
4. 输出 JSON 与 Markdown，并把 token 口径写进每一次输出。

自检覆盖 19 项，含「围栏内的 `#` 不算标题」「插入段落不改变 section id」
「同文档内重复不计」「观测记录必须自洽」等。

---

## 2. Harness 实测（唯一一条 `visible` 层数据）

本轮开发会话里发生了一次真实注入，记录在
[context-harness-observation.json](context-harness-observation.json)。

| 项 | 值 |
|---|---|
| 注入字节 | 154495 |
| 模型可见 | 84026 |
| 被省略 | 70469 |
| 可见率 | **54.4%** |

**这不是一次统计，是一次观测。** 它支持的结论只有一条：

> 154 KB 的 Skill 正文在单次加载中**不会**被完整送达模型，省略发生在规则正文中间。

这条观测的意义超出了 Token 成本：**当前 `SKILL.md` 在真实 Harness 里已经不是完整送达的**。
「规则都在 SKILL.md 里」这个说法，在 156 KB 规模上不成立。
精简到 10—15 KB 的直接收益不是省钱，而是**规则重新变得可完整加载**。

省略由工具输出额度触发，不是 Skill 特有行为，因此不能推广成「所有 Harness 都会省略 46%」。

---

## 3. 场景基线

`SKILL.md` 恒为已注入，因此它计入 `loaded` 而**不**计入工具调用。

| 场景 | 入口 | 文件 | 章节 | 字符 | est_tokens | 工具调用 | 跨文件逐字重复 | 未用但加载 |
|---|---|---|---|---|---|---|---|---|
| `bootstrap` | start-project | 4 | 70 | 114808 | 52410 | 3 | 0.0% | 21.9% |
| `resume` | continue-research | 4 | 73 | 113814 | 50824 | 3 | 0.0% | 14.7% |
| `research-loop` | continue-research | 5 | 80 | 114160 | 52504 | 4 | 0.0% | 34.1% |
| `literature` | explore | 5 | 107 | 133401 | 60716 | 4 | 0.0% | 13.4% |
| `paradigm-escape` | explore | 5 | 180 | 175343 | 73599 | 4 | 0.0% | 13.4% |
| `audit` | audit | 6 | 96 | 133302 | 60742 | 5 | 0.2% | 18.7% |
| `r8-prereg` | continue-research | 5 | 84 | 141032 | 55945 | 4 | 0.0% | 13.3% |
| `r9o-outcome` | continue-research | 6 | 95 | 142154 | 57443 | 5 | 0.0% | 17.0% |
| `mri-ssl` | continue-research | 6 | 77 | 107415 | 48966 | 5 | 0.0% | 21.4% |
| `mri-method` | continue-research | 7 | 108 | 124231 | 57062 | 6 | 0.0% | 14.2% |
| `context-drift` | continue-research | 4 | 71 | 115707 | 48597 | 3 | 0.0% | 16.7% |
| `subagent` | continue-research | 4 | 94 | 123449 | 57031 | 3 | 0.0% | 18.7% |

平均：128235 字符 / 56320 est_tokens / 4.08 次工具调用。`SKILL.md` 自身为 95831 字符、
156565 字节。

### 3.1 `SKILL.md` 的占比

| 场景 | `SKILL.md` 占该场景字符数 |
|---|---|
| `mri-ssl` | 89% |
| `resume` | 84% |
| `research-loop` | 84% |
| `bootstrap` | 83% |
| `context-drift` | 83% |
| `subagent` | 78% |
| `mri-method` | 77% |
| `literature` | 72% |
| `audit` | 72% |
| `r8-prereg` | 68% |
| `r9o-outcome` | 67% |
| `paradigm-escape` | 55% |

**诊断：优化对象不是 references，是 `SKILL.md`。** 12 个场景里只有 `paradigm-escape`
的 `SKILL.md` 占比低于 60%，因为在那个场景里 `phase-r3-r6-discovery.md`（43 KB）与
`structural-equivalence-policy.md`（63 KB）被同时加载。

---

## 4. 逐字重复几乎不存在，语义重复才是问题

`SKILL.md` 与 `references/` 之间**没有任何一个章节**存在 50% 以上的逐字重合：

| 项 | 值 |
|---|---|
| `SKILL.md` 字符 | 95831 |
| `references/` 文件数 | 39 |
| `references/` 字符 | 604200 |
| 有逐字副本的章节 | **0 个** |
| 单章节最高逐字重合率 | **17%**（`C. 路径与命名`，245 字符，匹配对象是无关文件） |

这条否定结果很重要，它**否定了一种省事的做法**：

> 不能靠「这段在 reference 里已经有了，删掉即可」来精简。`SKILL.md` 是独立措辞的复述，
> 不是复制粘贴。

因此每一段都只能**逐条迁移**：先确认目标 references 里是否已有等价规范，有则合并
差异（阈值、顺序、禁止项），无则新增权威位置。迁移判据写进
[rule-relocation-matrix.md](rule-relocation-matrix.md)。

**本节的盲区必须一起报出：** 逐字重复低不等于没有语义重复。同一规则换个说法写两遍，
shingle 检测不出来。语义层面的权威归属由迁移矩阵人工逐条裁定，不由本工具判定。

---

## 5. 未用内容：最坏的是 `research-loop`

`research-loop` 场景有 34.1% 的已加载字符属于该轮用不到的章节，在 12 个场景里最高。
主要来源是 `SKILL.md` 的 §7 设计依据（11513 字节）、§8 规则变更自检清单（10116 字节）、
§2 共享资源索引（19340 字节）和 §1.1 文献检索（6425 字节）。

这四块在**每一轮科研循环**里都会被重新注入，而它们的作用分别是「历史设计解释」
「维护本 Skill 时的自检」「资源目录」「文献检索规范」——没有一块服务于当轮科研决策。

`mri-ssl` 的 21.4% 与 `bootstrap` 的 21.9% 来源不同：前者是同一个 MRI Profile 下
与自监督任务无关的协议被一并加载，后者是 Bootstrap 序列里用不到的 R 阶段速查。

---

## 6. 子 Agent 场景

`subagent` 场景当前加载 4 个文件 / 123449 字符。其中 `shared-contract.md` 与
`references/roles.md` 是**整份**交给子代理的，而子代理真正需要的只是自己那一份任务契约。

当前没有「按角色裁剪」的机制。这是 Phase E 的输入。

---

## 7. 本基线不能证明什么

1. **不能证明真实 token 消耗。** 没有 tokenizer，没有 Harness 请求记录。
2. **不能证明模型理解成本。** 字符少不等于读得懂，读得懂也不等于判断正确。
3. **不能证明科学能力。** 本基线与科研判断质量无关，后者由行为回归与科学 Replay 承担。
4. **不能推广到其他 Harness。** 第二节的省略率是单次观测。
5. **不能证明场景读取集合就是实际读取集合。** 见 §0.2。

---

## 8. 复现

```bash
cd research-lifecycle-protocol
python3 scripts/context_profile.py --selftest
python3 scripts/context_profile.py --list
python3 scripts/context_profile.py --all --markdown
python3 scripts/context_profile.py --all --json --out /tmp/base.json

# 折入 Harness 实测（visible 层）
python3 scripts/context_profile.py --all --markdown \
    --observation docs/context-harness-observation.json

# 语料级逐字重复
python3 scripts/context_profile.py --corpus
```

精简后的对照数据见 [context-benchmark.md](context-benchmark.md)。
