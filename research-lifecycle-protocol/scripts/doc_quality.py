#!/usr/bin/env python3
"""doc_quality.py — 中文科研文档的类型感知质量检查（协调层）。

它回答四个问题：这份文档该有什么、它现在缺什么、哪些问题机器能确认、哪些只能交给人。

    python3 doc_quality.py check --path routes/F/docs/F010-theory.md
    python3 doc_quality.py check --changed --json
    python3 doc_quality.py check --staged
    python3 doc_quality.py compare --before old.md --after new.md --intent prose-only
    python3 doc_quality.py selftest

**它不是什么：** 不是第二套文档事实库，不是科研事实的判据，不是提交前钩子。
路径与 ID 归 `layout_guard.py`；句子形式归 `ste_lint_zh.py`；科学真实性归 RLP 门禁。
本模块只按文档类型把这些结果编排成 BLOCK / WARN / REVIEW_REQUIRED 三档。

退出码：0 = 没有 BLOCK；3 = 有 BLOCK；4 = 环境问题（文件不存在、不是 Git 仓库）。
"""

from __future__ import annotations

import argparse
import difflib
import hashlib
import json
import pathlib
import re
import subprocess
import sys
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

import ste_lint_zh

SCHEMA = "research-lifecycle-protocol/doc-quality@1"
EXIT_OK, EXIT_BLOCK, EXIT_ENV = 0, 3, 4

BLOCK, WARN, REVIEW = "BLOCK", "WARN", "REVIEW_REQUIRED"

#: 文档类型。取自 frontmatter 的 `type`，缺失时按文件名后缀推断。
TYPES = ("anchor", "field-map", "discovery", "proposal", "theory",
         "experiment-plan", "evidence", "review", "decision")

#: 文件名后缀 → 类型（frontmatter 缺失或写 null 时的兜底）。
SLUG_TYPES = (
    ("-anchor", "anchor"), ("-field-map", "field-map"), ("-fieldmap", "field-map"),
    ("-discovery", "discovery"), ("-theory", "theory"), ("-proposal", "proposal"),
    ("-candidate", "proposal"), ("-experiment-plan", "experiment-plan"),
    ("-preregistration", "experiment-plan"), ("-results", "evidence"),
    ("-result", "evidence"), ("-audit", "review"), ("-review", "review"),
    ("-decision", "decision"), ("-evidence", "evidence"),
)

#: 需要带导航的长文档门槛。
LONG_LINES = 300
LONG_HEADINGS = 20

#: 操作流水线索：出现得多说明正文在承担审计日志的职责。
OPERATIONAL_PATTERNS = re.compile(
    r"sha256|sha1\b|\b[0-9a-f]{16,}\b|mtime|并发写|其他 Agent|他人写入|"
    r"写入披露|文件修改|改动记录|修订过程|写后对拍|append-only")

#: 无证据宣传与套话：命中的句子可以确定要改。
#: 只有这两类能在散文层判 BLOCK：套话可以确定要改，宣传词没有实证支撑同样要改。
#: 注意 `marketing-adjective` 的默认词表包含「闭环」，在 MRI / ADMM 语境里它是术语，
#: 所以宣传词只作 WARN，避免把领域词当成营销词。
PROSE_BLOCK_RULES = {"empty-phrase"}
PROSE_WARN_RULES = {"marketing-adjective"}

#: 每份文档每条规则最多报这么多条，其余折叠成一条计数，避免真实文档刷屏。
MAX_PER_RULE = 8

#: 明确的结构性套话。
DUPLICATE_MIN_CHARS = 80
SIMILARITY_THRESHOLD = 0.82


@dataclass
class Finding:
    code: str
    severity: str
    path: str
    line: int
    message: str
    hint: str = ""

    def key(self) -> Tuple[str, str]:
        """用于增量比较：去掉行号，只留规则与描述。"""
        return (self.code, self.message)

    def as_dict(self) -> Dict[str, Any]:
        payload = {"code": self.code, "severity": self.severity, "path": self.path,
                   "line": self.line, "message": self.message}
        if self.hint:
            payload["hint"] = self.hint
        return payload

    def render(self) -> str:
        tail = f"\n    → {self.hint}" if self.hint else ""
        return f"{self.path}:{self.line} [{self.severity}] {self.code} {self.message}{tail}"


@dataclass
class Doc:
    path: pathlib.Path
    text: str
    front: Dict[str, Any] = field(default_factory=dict)
    body_start: int = 0          # frontmatter 之后的第一个行号（1-based）
    kind: str = ""
    lines: List[str] = field(default_factory=list)
    masked: str = ""

    @property
    def rel(self) -> str:
        return str(self.path)

    @property
    def doc_id(self) -> Optional[str]:
        match = re.match(r"^([A-Z])(\d{3})-", self.path.name)
        return (match.group(1) + match.group(2)) if match else None


# ---------------------------------------------------------------------------
# 读取与解析
# ---------------------------------------------------------------------------

def doc_from_text(text: str, path: pathlib.Path) -> Doc:
    front, body_start = parse_frontmatter(text)
    doc = Doc(path=pathlib.Path(path), text=text, front=front,
              body_start=body_start, lines=text.split("\n"))
    doc.kind = detect_kind(doc)
    doc.masked = mask(text)
    return doc


def read_doc(path: pathlib.Path) -> Doc:
    return doc_from_text(pathlib.Path(path).read_text(encoding="utf-8"), path)


def parse_frontmatter(text: str) -> Tuple[Dict[str, Any], int]:
    """极简 YAML 子集：只认顶层 `key: value`。返回 (字段, 正文首行行号)。"""
    lines = text.split("\n")
    if not lines or lines[0].strip() != "---":
        return {}, 1
    fields: Dict[str, Any] = {}
    for index in range(1, len(lines)):
        line = lines[index]
        if line.strip() == "---":
            return fields, index + 2
        match = re.match(r"^([A-Za-z_][\w-]*)\s*:\s*(.*)$", line)
        if not match or line.startswith((" ", "\t")):
            continue
        key, value = match.group(1), match.group(2).strip()
        if value in ("", "null", "~"):
            fields[key] = None
        else:
            fields[key] = value.strip('"').strip("'")
    return {}, 1                                    # 没有闭合的 frontmatter


def detect_kind(doc: Doc) -> str:
    declared = (doc.front.get("type") or "").strip().lower()
    if declared in TYPES:
        return declared
    name = doc.path.name.lower()
    for suffix, kind in SLUG_TYPES:
        if suffix in name:
            return kind
    return ""


# ---------------------------------------------------------------------------
# 掩码：代码、公式、链接不参与句子检查
# ---------------------------------------------------------------------------

FENCE_RE = re.compile(r"```.*?```", re.S)
DISPLAY_MATH_RE = re.compile(r"\$\$.*?\$\$|\\\[.*?\\\]|\\begin\{[a-zA-Z*]+\}.*?\\end\{[a-zA-Z*]+\}", re.S)
INLINE_CODE_RE = re.compile(r"`[^`\n]*`")
INLINE_MATH_RE = re.compile(r"(?<!\$)\$(?!\$)[^$\n]{1,200}\$(?!\$)")
LINK_RE = re.compile(r"!?\[[^\]]*\]\([^)]*\)")


def mask(text: str) -> str:
    """把非散文内容替换成空格，保持长度与换行，行号仍然可用。"""
    def blank(match: re.Match) -> str:
        return re.sub(r"[^\n]", " ", match.group(0))
    result = text
    for pattern in (FENCE_RE, DISPLAY_MATH_RE, INLINE_CODE_RE, INLINE_MATH_RE, LINK_RE):
        result = pattern.sub(blank, result)
    return result


# ---------------------------------------------------------------------------
# 结构
# ---------------------------------------------------------------------------

HEADING_RE = re.compile(r"^(#{1,6})\s+(.*)$")


def headings(doc: Doc) -> List[Tuple[int, str, int]]:
    """(层级, 标题, 行号)。跳过代码块内的 # 行。"""
    result: List[Tuple[int, str, int]] = []
    in_fence = False
    for index, line in enumerate(doc.lines, start=1):
        if line.lstrip().startswith("```"):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        match = HEADING_RE.match(line)
        if match:
            result.append((len(match.group(1)), match.group(2).strip(), index))
    return result


def slugify(title: str) -> str:
    text = title.strip().lower()
    text = re.sub(r"[`*_~]", "", text)
    text = re.sub(r"[^\w\u4e00-\u9fff \-]", "", text)
    return re.sub(r"\s+", "-", text).strip("-")


def has_navigation(doc: Doc) -> bool:
    heads = headings(doc)
    limit = max(1, int(len(doc.lines) * 0.2))
    for _level, title, line_no in heads:
        if line_no > limit:
            break
        if re.search(r"摘要|执行摘要|导航|目录|小结|TL;DR|summary", title, re.I):
            return True
    toc_links = sum(1 for line in doc.lines[:limit] if re.match(r"^\s{0,3}(?:[-*]|\d+\.)\s+\[", line))
    return toc_links >= 3


def operational_pressure(doc: Doc) -> Tuple[int, List[int]]:
    hits: List[int] = []
    for index, line in enumerate(doc.lines, start=1):
        if index < doc.body_start:
            continue
        if OPERATIONAL_PATTERNS.search(line):
            hits.append(index)
    return len(hits), hits


def paragraphs(doc: Doc) -> List[Tuple[int, str]]:
    """正文段落（不含标题、表格、代码、列表项）。"""
    result: List[Tuple[int, str]] = []
    buffer: List[str] = []
    start = 0
    in_fence = False
    for index, line in enumerate(doc.lines, start=1):
        stripped = line.strip()
        if stripped.startswith("```"):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        is_body = stripped and not stripped.startswith(("#", "|", "-", "*", ">", "!", "<")) \
            and not re.match(r"^\d+[.)]\s", stripped)
        if is_body:
            if not buffer:
                start = index
            buffer.append(stripped)
        elif buffer:
            result.append((start, "".join(buffer)))
            buffer = []
    if buffer:
        result.append((start, "".join(buffer)))
    return [(line, text) for line, text in result if len(text) >= DUPLICATE_MIN_CHARS]


def shingles(text: str, size: int = 4) -> set:
    compact = re.sub(r"\s+", "", text)
    return {compact[i:i + size] for i in range(0, max(0, len(compact) - size), max(1, size // 2))}


# ---------------------------------------------------------------------------
# BLOCK：能确认的结构错误
# ---------------------------------------------------------------------------

def check_frontmatter(doc: Doc) -> List[Finding]:
    findings: List[Finding] = []
    if doc.doc_id is None:
        return findings                                  # 不是路线正式文档
    if not doc.front:
        findings.append(Finding("DQ-01", BLOCK, doc.rel, 1,
                                "路线正式文档缺少可解析的 frontmatter",
                                "补 id / route / type / status；机器字段缺失时下游无法定位"))
        return findings
    for key in ("id", "route", "type"):
        if not doc.front.get(key):
            findings.append(Finding("DQ-01", BLOCK, doc.rel, 1,
                                    f"frontmatter 缺少 `{key}`",
                                    "路线正式文档的 id / route / type 是机器入口"))
    declared_id = doc.front.get("id")
    if declared_id and declared_id != doc.doc_id:
        findings.append(Finding("DQ-02", BLOCK, doc.rel, 1,
                                f"文件名 ID {doc.doc_id} 与 frontmatter id {declared_id} 不一致",
                                "改文件名或改 frontmatter，两者必须相同"))
    declared_route = doc.front.get("route")
    if declared_route and doc.doc_id and not doc.doc_id.startswith(str(declared_route)):
        findings.append(Finding("DQ-03", BLOCK, doc.rel, 1,
                                f"frontmatter route={declared_route} 与文件名 ID {doc.doc_id} 不一致",
                                "路线编号是目录与 ID 的共同事实"))
    if not doc.front.get("status"):
        findings.append(Finding("DQ-18", WARN, doc.rel, 1,
                                "frontmatter 没有 status",
                                "状态是判断「历史快照 / 当前协议」的入口之一"))
    return findings


def check_markdown(doc: Doc) -> List[Finding]:
    findings: List[Finding] = []
    fences = sum(1 for line in doc.lines if line.lstrip().startswith("```"))
    if fences % 2:
        findings.append(Finding("DQ-08", BLOCK, doc.rel, len(doc.lines),
                                "代码块围栏数量为奇数：有一个围栏没有闭合",
                                "补上结束围栏；未闭合会把后半篇当成代码"))
    previous = 0
    for level, title, line_no in headings(doc):
        if previous and level > previous + 1:
            findings.append(Finding("DQ-19", WARN, doc.rel, line_no,
                                    f"标题层级从 H{previous} 跳到 H{level}（{title}）",
                                    "跳级会让目录结构失真"))
        previous = level
    return findings


def check_links(doc: Doc) -> List[Finding]:
    findings: List[Finding] = []
    anchors = {slugify(title) for _l, title, _n in headings(doc)}
    for index, line in enumerate(doc.lines, start=1):
        for match in re.finditer(r"!?\[[^\]]*\]\(([^)]+)\)", line):
            target = match.group(1).strip()
            if not target or target.startswith(("http://", "https://", "mailto:", "tel:")):
                continue
            if target.startswith("#"):
                anchor = slugify(target[1:])
                if anchor and anchor not in anchors:
                    findings.append(Finding("DQ-07", BLOCK, doc.rel, index,
                                            f"页内锚点不存在：{target}",
                                            "锚点必须对应一个真实标题"))
                continue
            path_part = target.split("#", 1)[0]
            if not path_part:
                continue
            resolved = (doc.path.parent / path_part).resolve()
            if resolved.exists():
                continue
            if "research-idea-pipeline" in path_part:
                # 旧控制根里的证据是历史事实：迁移后目录可能已经不在，
                # 但「引用了它」本身不是文档错误，更不能自动改写。
                findings.append(Finding("DQ-44", REVIEW, doc.rel, index,
                                        f"链接指向旧控制根，当前不可解析：{path_part}",
                                        "确认这份证据是否已随迁移归档；不要只是把旧路径替换成新路径"))
                continue
            findings.append(Finding("DQ-06", BLOCK, doc.rel, index,
                                    f"相对链接指向不存在的路径：{path_part}",
                                    "改为真实路径，或说明它是历史引用"))
    return findings


PREREG_RE = re.compile(
    r"([\w./-]*preregistration\.json)[^\n]{0,120}?sha256\s*[:：]?\s*`?([0-9a-f]{64})")


def check_prereg_reference(doc: Doc, project_root: Optional[pathlib.Path]
                           ) -> List[Finding]:
    """正文引用了预注册 digest：文件在就核对，不在就交给人。

    机器能确认的是「文件内容与正文写的摘要是否一致」。至于这份预注册是否该冻结、
    冻结得对不对，属于科研判断，不在本模块的职责内。
    """
    findings: List[Finding] = []
    for index, line in enumerate(doc.lines, start=1):
        for match in PREREG_RE.finditer(line):
            rel, digest = match.group(1), match.group(2)
            candidates: List[pathlib.Path] = []
            if project_root is not None:
                candidates.append(project_root / rel)
            candidates.append(doc.path.parent / rel)
            target = next((path for path in candidates if path.is_file()), None)
            if target is None:
                findings.append(Finding(
                    "DQ-43", REVIEW, doc.rel, index,
                    f"正文绑定预注册摘要 {digest[:12]}…，但 {rel} 不在可解析位置",
                    "确认这份预注册仍在项目里；无法核验时不要把它当成当前协议"))
                continue
            actual = hashlib.sha256(target.read_bytes()).hexdigest()
            if actual != digest:
                findings.append(Finding(
                    "DQ-10", BLOCK, doc.rel, index,
                    f"{rel} 的实际摘要 {actual[:12]}… 与正文写的 {digest[:12]}… 不一致",
                    "要么正文引用了错误版本，要么预注册被改过；核清前不要当作已冻结"))
    return findings


def check_ids(doc: Doc, project_root: Optional[pathlib.Path]) -> List[Finding]:
    """同一路线内 ID 冲突（Case D）：只在该 ID 真被两个文件占用时报。"""
    if project_root is None or doc.doc_id is None:
        return []
    try:
        import layout_guard
        control = layout_guard.control_root(project_root)
        route = doc.doc_id[0]
        conflicts = layout_guard.doc_id_conflicts(project_root, control, route)
    except Exception:                                    # noqa: BLE001 — 环境问题不算 BLOCK
        return []
    findings: List[Finding] = []
    for conflict in conflicts:
        if doc.doc_id != conflict["id"]:
            continue
        others = [name for name in conflict["files"] if name != doc.path.name]
        findings.append(Finding("DQ-05", BLOCK, doc.rel, 1,
                                f"文档 ID {doc.doc_id} 同时被 {', '.join(others)} 占用",
                                "并行会话抢同一个 ID：先跑 layout_guard.py allocate 拿独占 ID"))
    return findings


# ---------------------------------------------------------------------------
# WARN：结构质量
# ---------------------------------------------------------------------------

def check_navigation(doc: Doc) -> List[Finding]:
    heads = headings(doc)
    long_doc = len(doc.lines) >= LONG_LINES or len(heads) >= LONG_HEADINGS
    if not long_doc or has_navigation(doc):
        return []
    return [Finding("DQ-20", WARN, doc.rel, 1,
                    f"{len(doc.lines)} 行 / {len(heads)} 个标题，但没有摘要或章节导航",
                    "加一段「执行摘要」或 3 条以上的页内目录；长文不等于错，找不到结论才是")]


#: 本来就该写运行细节的章节标题：附录、复现、清单、环境、预注册。
RECORD_SECTION_HINT = re.compile(r"附录|复现|清单|环境|预注册|哈希|gate|日志|记录", re.I)


def _sections(doc: Doc) -> List[Tuple[str, int, List[str]]]:
    heads = headings(doc)
    bounds = [item[2] for item in heads] + [len(doc.lines) + 1]
    sections = [("（正文开头）", 1, doc.lines[:bounds[0] - 1])]
    for index, (_level, title, line_no) in enumerate(heads):
        sections.append((title, line_no, doc.lines[line_no:bounds[index + 1] - 1]))
    return sections


def check_operational_log(doc: Doc) -> List[Finding]:
    """Case B：科学结论与运行记录混在同一节里。

    不按全文计数，也不按行数阈值：真实文档里往往是三个长条目把哈希、mtime、
    并发写入塞进「限制与未决」，行数很少而信息量很大。
    """
    if doc.kind in ("review", "experiment-plan"):
        return []                                        # 审计与预注册本来就绑定哈希
    for title, line_no, body in _sections(doc):
        if RECORD_SECTION_HINT.search(title):
            continue
        hits = [line for line in body if OPERATIONAL_PATTERNS.search(line)]
        science = [line for line in body
                   if len(line) >= 24 and not OPERATIONAL_PATTERNS.search(line)
                   and not line.strip().startswith(("#", "|", "```"))]
        if len(hits) >= 3 and len(science) >= 2:
            return [Finding("DQ-21", WARN, doc.rel, line_no,
                            f"「{title}」同时承载科学判断与运行记录（{len(hits)} 处哈希/并发/修订痕迹）",
                            "运行记录移到 docs/dev/ 或引用既有审计文档。"
                            "不要删除，不要隐去看穿正确性的异常")]
    return []


def check_results_first(doc: Doc) -> List[Finding]:
    if doc.kind not in ("evidence",):
        return []
    heads = headings(doc)
    if not heads:
        return []
    total = max(1, len(doc.lines))
    result_index = next((i for i, (_l, title, _n) in enumerate(heads)
                         if re.search(r"结果|读数|发现|观察", title)), None)
    execution_index = next((i for i, (_l, title, _n) in enumerate(heads)
                            if re.search(r"执行|运行|实现|环境|命令|流程|环境与", title)), None)
    if result_index is None:
        return []
    if execution_index is None or execution_index > result_index:
        return []
    line_no = heads[result_index][2]
    if line_no / total < 0.35:
        return []
    return [Finding("DQ-23", WARN, doc.rel, line_no,
                    "执行细节出现在结果之前，核心结果落在全文 35% 之后",
                    "结果类文档先给读数与科学决定，执行记录压到「来源与复现」")]


def check_responsibility_mixing(doc: Doc) -> List[Finding]:
    if doc.kind not in ("theory", "discovery"):
        return []
    mixed = [(title, line_no) for _l, title, line_no in headings(doc)
             if re.search(r"决策|decision|开发记录|探针|数值实验日志|运行记录", title)]
    if not mixed:
        return []
    title, line_no = mixed[0]
    return [Finding("DQ-27", WARN, doc.rel, line_no,
                    f"研究正文里混入了「{title}」这类非本文职责的段落",
                    "理论与方法文档只回答自己的问题；决策与运行记录各有归属文档")]


def check_redundancy(doc: Doc) -> List[Finding]:
    items = paragraphs(doc)
    if len(items) > 300:
        items = items[:300]
    findings: List[Finding] = []
    shingle_sets = [(line, text, shingles(text)) for line, text in items]
    reported: set = set()
    for i in range(len(shingle_sets)):
        left_line, _left_text, left = shingle_sets[i]
        for j in range(i + 1, len(shingle_sets)):
            right_line, right_text, right = shingle_sets[j]
            if not left or not right:
                continue
            overlap = len(left & right) / max(1, len(left | right))
            if overlap < 0.6:
                continue
            ratio = difflib.SequenceMatcher(None, shingle_sets[i][1],
                                            right_text).ratio()
            if ratio < SIMILARITY_THRESHOLD:
                continue
            key = (left_line, right_line)
            if key in reported:
                continue
            reported.add(key)
            findings.append(Finding("DQ-22", WARN, doc.rel, right_line,
                                    f"与第 {left_line} 行的段落高度相似（{ratio:.2f}）",
                                    "两段若条件不同，说明差异；若结论相同，留一处并引用"))
            if len(findings) >= 3:
                return findings
    return findings


# ---------------------------------------------------------------------------
# REVIEW_REQUIRED：只能交给人判断
# ---------------------------------------------------------------------------

#: 只认「把现象归因到某个机制」的措辞。「证明」不算：数学证明与「不能证明」都是正常写法，
#: 按关键词判会把合法论证判成违规。
CAUSAL_RE = re.compile(r"导致|归因于|根本原因|正是由于|充分说明|说明了.{0,12}的原因")
NEGATED_RE = re.compile(r"不能|无法|未|不足以|尚不|并非|没有")
HEDGE_RE = re.compile(r"条件|假设|前提|在.{0,8}下|可能|倾向于|提示|证据|相关|未排除|不确定|对照")


def check_semantics(doc: Doc) -> List[Finding]:
    findings: List[Finding] = []
    heads = headings(doc)
    titles = " ".join(title for _l, title, _n in heads)

    if doc.kind == "theory" and not re.search(r"条件|前提|假设|记号|边界|适用范围", titles):
        findings.append(Finding("DQ-41", REVIEW, doc.rel, 1,
                                "理论文档没有「条件 / 前提 / 假设 / 边界」类章节",
                                "定理成立范围需要写明；这不是文字问题，需作者确认"))

    if doc.kind in ("theory", "discovery", "evidence"):
        causal = 0
        for index, line in enumerate(doc.lines, start=1):
            if index < doc.body_start or "|" in line:
                continue
            sentence = line.strip()
            if not CAUSAL_RE.search(sentence) or HEDGE_RE.search(sentence):
                continue
            if NEGATED_RE.search(sentence):
                continue
            findings.append(Finding("DQ-40", REVIEW, doc.rel, index,
                                    "因果表述没有附条件或证据限定",
                                    "确认这条因果是否有对照支持；文字不能替代证据"))
            causal += 1
            if causal >= 2:
                break

    if doc.kind == "experiment-plan":
        body = "\n".join(doc.lines[doc.body_start - 1:])
        if re.search(r"冻结|frozen", body, re.I) and not re.search(
                r"权威|以 .*preregistration\.json 为准|覆盖|不覆盖|解释它", body):
            status = doc.front.get("status")
            findings.append(Finding("DQ-42", REVIEW, doc.rel, 1,
                                    f"正文涉及冻结协议，但 Markdown status 是 {status or '未声明'}，"
                                    "且没有说明哪一份是权威来源",
                                    "机器预注册与说明性文档可以有不同的冻结状态；"
                                    "请写明权威 JSON 与版本，不要改冻结字段"))
    return findings


# ---------------------------------------------------------------------------
# 句子形式：包装 ste_lint_zh，按文档政策重新分级
# ---------------------------------------------------------------------------

def check_prose(doc: Doc) -> List[Finding]:
    options = ste_lint_zh.Options(disabled=frozenset({"synonym-rotation"}))
    findings: List[Finding] = []
    for item in ste_lint_zh.analyze(doc.masked, doc.rel, options):
        severity = BLOCK if item.rule in PROSE_BLOCK_RULES else WARN
        findings.append(Finding(f"DQ-3-{item.rule}", severity, doc.rel, item.line,
                                item.message, f"命中：{item.match}"))
    return findings


# ---------------------------------------------------------------------------
# 纯语言修改：受保护内容比对
# ---------------------------------------------------------------------------

PROTECTED_PATTERNS: Tuple[Tuple[str, re.Pattern], ...] = (
    ("公式", re.compile(r"\$\$.*?\$\$|\\\[.*?\\\]|\\\(.*?\\\)|\\begin\{[a-zA-Z*]+\}.*?\\end\{[a-zA-Z*]+\}|(?<!\$)\$(?!\$)[^$\n]{1,200}\$(?!\$)", re.S)),
    ("带单位数值", re.compile(r"\d+(?:\.\d+)?\s*(?:dB|%|×|ms|GB|MB|KB|px|mm|cm|Hz|kHz|MHz|T\b|bit|bytes?)")),
    ("指标名", re.compile(r"\b(?:PSNR|SSIM|NMSE|NRMSE|FID|LPIPS|SNR|CNR)\b[\w().]*")),
    ("实验与文档 ID", re.compile(r"\b(?:X|E|F)\d{1,5}\b|DOC-\d+")),
    ("文献标识", re.compile(r"10\.\d{4,9}/[^\s，。；]+|arXiv:\s?\d{4}\.\d{4,5}")),
    ("摘要值", re.compile(r"\b[0-9a-f]{16,}\b")),
    ("路径", re.compile(r"`[^`\n]*[./][^`\n]*`")),
    ("情态与限定", re.compile(r"必须|不得|仅|除非|当且仅当|至少|至多|总是|从不|保证|可能|约")),
    ("数据范围", re.compile(r"n\s*=\s*\d+|\d+\s*(?:例|个样本|卷|受试者|次运行)")),
)


def extract_protected(text: str) -> Dict[str, List[str]]:
    """抽出「仅改语言时不允许改变」的东西。逐类返回排好序的清单。"""
    cleaned = FENCE_RE.sub(lambda m: "\n" * m.group(0).count("\n"), text)
    result: Dict[str, List[str]] = {}
    for name, pattern in PROTECTED_PATTERNS:
        items = sorted({re.sub(r"\s+", " ", match.group(0)).strip()
                        for match in pattern.finditer(cleaned)})
        if items:
            result[name] = items
    return result


def compare_protected(before: str, after: str) -> List[Dict[str, Any]]:
    """返回每类受保护内容的增删。空列表表示没有变化。"""
    left, right = extract_protected(before), extract_protected(after)
    diffs: List[Dict[str, Any]] = []
    for name in sorted(set(left) | set(right)):
        old = left.get(name, [])
        new = right.get(name, [])
        if old == new:
            continue
        diffs.append({
            "category": name,
            "removed": [item for item in old if item not in new][:8],
            "added": [item for item in new if item not in old][:8],
        })
    return diffs


# ---------------------------------------------------------------------------
# 编排
# ---------------------------------------------------------------------------

def lint_doc(doc: Doc, project_root: Optional[pathlib.Path],
             *, prose: bool = True) -> List[Finding]:
    findings: List[Finding] = []
    for check in (check_frontmatter, check_markdown, check_links,
                  check_navigation, check_operational_log, check_results_first,
                  check_responsibility_mixing, check_redundancy, check_semantics):
        findings.extend(check(doc))
    findings.extend(check_ids(doc, project_root))
    findings.extend(check_prereg_reference(doc, project_root))
    if prose:
        findings.extend(check_prose(doc))
    return cap_findings(findings, doc)


def cap_findings(findings: Sequence[Finding], doc: Doc) -> List[Finding]:
    """同一规则命中过多时保留前 MAX_PER_RULE 条，再补一条计数说明。"""
    grouped: Dict[str, List[Finding]] = {}
    order: List[str] = []
    for item in findings:
        if item.code not in grouped:
            grouped[item.code] = []
            order.append(item.code)
        grouped[item.code].append(item)
    capped: List[Finding] = []
    for code in order:
        items = grouped[code]
        capped.extend(items[:MAX_PER_RULE])
        if len(items) > MAX_PER_RULE:
            capped.append(Finding(code, items[0].severity, doc.rel, items[-1].line,
                                  f"另有 {len(items) - MAX_PER_RULE} 处同类问题未逐条列出",
                                  "先修代表性几处；同类批量问题通常是同一个写作习惯"))
    return sorted(capped, key=lambda item: (item.line, item.code))


def subtract_findings(findings: Sequence[Finding],
                      baseline: Optional[Sequence[Finding]]) -> List[Finding]:
    """只保留基线里没有的问题：多集合相减，不看行号。"""
    if baseline is None:
        return list(findings)
    remaining: Dict[Tuple[str, str], int] = {}
    for item in baseline:
        remaining[item.key()] = remaining.get(item.key(), 0) + 1
    kept: List[Finding] = []
    for item in findings:
        count = remaining.get(item.key(), 0)
        if count:
            remaining[item.key()] = count - 1
            continue
        kept.append(item)
    return kept


def summarize(findings: Sequence[Finding]) -> Dict[str, int]:
    counts = {BLOCK: 0, WARN: 0, REVIEW: 0}
    for finding in findings:
        counts[finding.severity] = counts.get(finding.severity, 0) + 1
    return counts


def report_for(path: pathlib.Path, project_root: Optional[pathlib.Path],
               *, prose: bool = True, baseline: Optional[Sequence[Finding]] = None
               ) -> Dict[str, Any]:
    doc = read_doc(path)
    findings = lint_doc(doc, project_root, prose=prose)
    findings = subtract_findings(findings, baseline)
    return {
        "path": str(path),
        "kind": doc.kind or "unknown",
        "doc_id": doc.doc_id,
        "findings": [item.as_dict() for item in findings],
        "counts": summarize(findings),
    }


# ---------------------------------------------------------------------------
# Git 增量
# ---------------------------------------------------------------------------

def git_root(start: pathlib.Path) -> Optional[pathlib.Path]:
    proc = subprocess.run(["git", "rev-parse", "--show-toplevel"],
                          capture_output=True, text=True, cwd=str(start))
    return pathlib.Path(proc.stdout.strip()) if proc.returncode == 0 else None


def _git_text(root: pathlib.Path, ref: str) -> Optional[str]:
    proc = subprocess.run(["git", "show", ref], capture_output=True, text=True,
                          cwd=str(root))
    return proc.stdout if proc.returncode == 0 else None


def changed_docs(root: pathlib.Path, *, staged: bool) -> List[pathlib.Path]:
    if staged:
        args = ["git", "diff", "--cached", "--name-only", "--diff-filter=ACMR",
                "--", "*.md"]
    else:
        args = ["git", "diff", "--name-only", "--diff-filter=ACMR", "HEAD", "--", "*.md"]
    proc = subprocess.run(args, capture_output=True, text=True, cwd=str(root))
    if proc.returncode != 0:
        return []
    return [root / line.strip() for line in proc.stdout.splitlines() if line.strip()]


def baseline_for(root: pathlib.Path, path: pathlib.Path, *, staged: bool
                 ) -> Optional[List[Finding]]:
    """旧版本（HEAD 或索引）的检查结果；新文件返回 None。"""
    rel = path.relative_to(root).as_posix()
    # 两种增量模式的旧版本都是 HEAD：--staged 的新版本来自索引，--changed 的来自工作区。
    old_text = _git_text(root, f"HEAD:{rel}")
    if old_text is None:
        return None
    doc = doc_from_text(old_text, path)
    return lint_doc(doc, root)


def current_text(root: pathlib.Path, path: pathlib.Path, *, staged: bool) -> Optional[str]:
    if staged:
        rel = path.relative_to(root).as_posix()
        return _git_text(root, f":{rel}")
    return path.read_text(encoding="utf-8") if path.is_file() else None


# ---------------------------------------------------------------------------
# 命令行
# ---------------------------------------------------------------------------

def render_human(reports: Sequence[Dict[str, Any]], stream) -> None:
    total = {BLOCK: 0, WARN: 0, REVIEW: 0}
    for report in reports:
        for key, value in report["counts"].items():
            total[key] = total.get(key, 0) + value
        if not report["findings"]:
            continue
        print(f"\n{report['path']}  [{report['kind']}]", file=stream)
        for item in report["findings"]:
            finding = Finding(item["code"], item["severity"], item["path"],
                              item["line"], item["message"], item.get("hint", ""))
            print("  " + finding.render(), file=stream)
    print(f"\nBLOCK {total[BLOCK]} · WARN {total[WARN]} · REVIEW {total[REVIEW]}"
          f" · 文件 {len(reports)}", file=stream)


def command_check(args: argparse.Namespace) -> int:
    root = pathlib.Path(args.root).resolve() if args.root else pathlib.Path.cwd()
    project = root if args.root else None
    repo = git_root(root)
    targets: List[Tuple[pathlib.Path, Optional[List[Finding]]]] = []
    if args.staged or args.changed:
        if repo is None:
            print("[env] 需要 Git 仓库才能做增量检查", file=sys.stderr)
            return EXIT_ENV
        for path in changed_docs(repo, staged=bool(args.staged)):
            if not path.is_file() and not args.staged:
                continue
            targets.append((path, baseline_for(repo, path, staged=bool(args.staged))))
    for raw in args.path:
        path = pathlib.Path(raw)
        path = path if path.is_absolute() else (root / path)
        if not path.is_file():
            print(f"[env] 文件不存在：{path}", file=sys.stderr)
            return EXIT_ENV
        targets.append((path, None))
    if not targets:
        print(json.dumps({"_schema": SCHEMA, "status": "NO_TARGETS", "reports": []},
                         ensure_ascii=False) if args.json else "没有要检查的文档")
        return EXIT_OK

    reports: List[Dict[str, Any]] = []
    for path, baseline in targets:
        if args.staged:
            rel = path.relative_to(repo).as_posix()
            text = current_text(repo, path, staged=True)
            if text is None:
                continue
            doc = doc_from_text(text, path)
            findings = lint_doc(doc, project, prose=not args.no_prose)
            findings = subtract_findings(findings, baseline)
            reports.append({"path": str(path), "kind": doc.kind or "unknown",
                            "doc_id": doc.doc_id,
                            "findings": [item.as_dict() for item in findings],
                            "counts": summarize(findings)})
        else:
            reports.append(report_for(path, project,
                                      prose=not args.no_prose, baseline=baseline))

    blocks = sum(report["counts"].get(BLOCK, 0) for report in reports)
    payload = {"_schema": SCHEMA,
               "status": "BLOCK" if blocks else "OK",
               "root": str(root),
               "counts": {BLOCK: sum(r["counts"].get(BLOCK, 0) for r in reports),
                          WARN: sum(r["counts"].get(WARN, 0) for r in reports),
                          REVIEW: sum(r["counts"].get(REVIEW, 0) for r in reports)},
               "reports": reports}
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    elif not args.quiet or blocks:
        render_human(reports, sys.stdout)
    return EXIT_BLOCK if blocks else EXIT_OK


def command_compare(args: argparse.Namespace) -> int:
    before = pathlib.Path(args.before)
    after = pathlib.Path(args.after)
    for path in (before, after):
        if not path.is_file():
            print(f"[env] 文件不存在：{path}", file=sys.stderr)
            return EXIT_ENV
    old_text = before.read_text(encoding="utf-8")
    new_text = after.read_text(encoding="utf-8")
    diffs = compare_protected(old_text, new_text)
    if args.intent != "prose-only":
        status = "REVIEW_ONLY"
        diffs = []
    elif diffs and not args.allow_scientific_change:
        status = "BLOCK"
    elif diffs:
        status = "SCIENTIFIC_CHANGE_ALLOWED"
    else:
        status = "PROSE_ONLY_OK"
    payload = {"_schema": SCHEMA, "command": "compare", "intent": args.intent,
               "status": status, "before": str(before), "after": str(after),
               "protected_changes": diffs}
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        if status == "PROSE_ONLY_OK":
            print("仅改语言：受保护内容没有变化")
        elif status == "SCIENTIFIC_CHANGE_ALLOWED":
            print("受保护内容有变化，且按明确授权放行：")
        for diff in diffs:
            print(f"  [{diff['category']}] 删除 {diff['removed']} 新增 {diff['added']}")
        if status == "BLOCK":
            print("声明只改语言，但受保护内容变了 —— 要么恢复，要么改为科学修订任务")
    return EXIT_BLOCK if status == "BLOCK" else EXIT_OK


def selftest() -> int:
    checks: List[Tuple[str, bool]] = []
    sample = "---\nid: F001\nroute: F\ntype: theory\nstatus: draft\n---\n\n# T\n\n$a^2+b^2$\n"
    doc = doc_from_text(sample, pathlib.Path("F001-theory.md"))
    checks.append(("frontmatter 解析", doc.front.get("id") == "F001"))
    checks.append(("类型推断", doc.kind == "theory"))
    checks.append(("公式被掩码", "$a^2" not in doc.masked))
    checks.append(("ID 提取", doc.doc_id == "F001"))
    checks.append(("标题 slug", slugify("3.2 定理一：零初始化") != ""))
    diffs = compare_protected("必须达到 PSNR 32.5 dB", "须达到 PSNR 32.5 dB")
    checks.append(("纯语言改动识别", any("必须" in str(d["removed"]) for d in diffs)))
    same = compare_protected("必须达到 PSNR 32.5 dB", "必须达到 PSNR 32.5 dB")
    checks.append(("相同文本无差异", same == []))
    failed = [name for name, ok in checks if not ok]
    for name, ok in checks:
        print(f"{'ok  ' if ok else 'FAIL'} {name}")
    print(f"selftest: {len(failed)} failure(s)")
    return EXIT_OK if not failed else EXIT_BLOCK


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="中文科研文档质量检查")
    sub = parser.add_subparsers(dest="command", required=True)

    check = sub.add_parser("check", help="检查一份或多份文档")
    check.add_argument("--path", action="append", default=[], help="文档路径，可重复")
    check.add_argument("--changed", action="store_true", help="检查工作区相对 HEAD 的改动")
    check.add_argument("--staged", action="store_true", help="检查暂存区内容")
    check.add_argument("--root", help="项目根（用于解析链接与文档 ID）")
    check.add_argument("--json", action="store_true")
    check.add_argument("--quiet", action="store_true", help="只在有 BLOCK 时输出")
    check.add_argument("--no-prose", action="store_true", help="跳过句子形式检查")
    check.set_defaults(handler=command_check)

    compare = sub.add_parser("compare", help="比较两次修订的受保护内容")
    compare.add_argument("--before", required=True)
    compare.add_argument("--after", required=True)
    compare.add_argument("--intent", default="prose-only",
                         choices=("prose-only", "scientific-change"))
    compare.add_argument("--allow-scientific-change", action="store_true",
                         help="本轮任务本来就允许改科学内容（需已有授权）")
    compare.add_argument("--json", action="store_true")
    compare.set_defaults(handler=command_compare)

    selftest_parser = sub.add_parser("selftest", help="内置自检")
    selftest_parser.set_defaults(handler=lambda _args: selftest())
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    return args.handler(args)


if __name__ == "__main__":
    sys.exit(main())
