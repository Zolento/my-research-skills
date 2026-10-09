#!/usr/bin/env python3
"""Development-only merge: provided preset protocols + the repo's machine-checked sections.

The provided `presets/<id>.md` are the authoritative *protocol prose*. This script preserves
every provided line verbatim and re-hosts it inside the nine sections the repo validates, so
`test_preset_router` can assert the contract and the executed commands without rewriting what
the provider wrote. Run once per provided revision; the shipped files never depend on `.dev/`.
"""
import pathlib, re, sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'scripts'))
import preset_router as pr  # noqa: E402

PROVIDED = ROOT / '.dev' / 'provided'
SECTIONS = {
    'intent': ('意图', '触发'),
    'steps': ('执行协议', '执行步骤'),
    'stops': ('防漂移与退出', '边界和退出', '停止', '失败'),
    'outputs': ('产出', '输出'),
}


def parse(text):
    """Split a provided preset file into its preamble and its `##` sections.

    The provider uses slightly different section names per preset (`意图` / `触发`,
    `防漂移与退出` / `边界和退出`, …), so sections are mapped onto a small frozen set of roles and
    anything unmapped is preserved verbatim as a supplement.
    """
    header, sections, current = [], {}, None
    for line in text.splitlines():
        if line.startswith('## '):
            name = line[3:].strip()
            current = None
            for key, names in SECTIONS.items():
                if any(name.startswith(candidate) or candidate in name
                       for candidate in names):
                    current = key
                    break
            sections.setdefault(current or f"补充：{name}", [])
            continue
        if line.startswith('# '):
            continue
        if current is None:
            if line.strip():
                header.append(line)
            continue
        sections[current].append(line)
    return header, sections


def body(lines):
    return '\n'.join(lines).strip('\n')


def render(preset, registry):
    path = PROVIDED / f"{preset['id']}.md"
    header, sections = parse(path.read_text(encoding='utf-8'))
    provided_steps = body(sections.get('steps', []))
    provided_stops = body(sections.get('stops', []))
    provided_outputs = body(sections.get('outputs', []))
    provided_intent = body(sections.get('intent', []))
    extras = [(name, body(lines)) for name, lines in sections.items()
              if name.startswith("补充：") and body(lines)]

    steps_table = []
    for index, step in enumerate(preset['_steps'], 1):
        steps_table.append(f"| {index} | {step.get('step')} | `{step.get('command')}` |")
    auto = preset.get('auto')
    if auto:
        trigger_line = (f"- 自动触发（`{auto['mode']}`，需先过防重入守卫）："
                        f"信号 {', '.join('`' + s + '`' for s in auto['signals'])}；"
                        f"前提：{auto['requires']}；冷却 {preset['cooldown_rounds']} 轮；"
                        f"每指纹上限 {preset['max_attempts']} 次。")
    else:
        trigger_line = "- 自动触发：**不适用**（用户显式意图优先）。"
    lines = [
        f"# Preset: `{preset['id']}` — {preset['name_zh']} / {preset['name_en']}",
        "",
        "> 提供版协议正文（逐字保留）+ 本仓库的机器可校验章节。加载时先读 `shared-contract.md`"
        "与选中的**这一个** Preset，不要一次注入全部 16 份。",
        "",
        "| 字段 | 值 |", "|---|---|",
        f"| preset id | `{preset['id']}` |",
        f"| 顶层入口 | `{preset['entry']}` |",
        f"| 执行授权 | `{preset['execution_scope']}`（权限层 `{pr.scope_privilege(preset['execution_scope'])}`）|",
        f"| registry trigger | `{registry['trigger']}` |",
        f"| 分组 / 优先级 | `{preset['group']}` / {preset['priority']}（越小越优先）|",
        f"| 协议来源 | 提供版 `presets/{preset['id']}.md` 正文 + 本仓库 9 节契约 |",
        "",
        "## 1. 意图与入口", "",
        provided_intent or preset['intent_zh'],
        "",
        f"- 中文意图：{preset['intent_zh']}",
        f"- English intent: {preset['intent_en']}",
        f"- 入口 `{preset['entry']}`；授权 `{preset['execution_scope']}`；共同约束见 "
        "[shared-contract.md](../shared-contract.md)。",
        "",
        "## 2. 触发条件", "", "- 适用条件："]
    lines += [f"  - {item}" for item in preset['applies_when']]
    lines += [trigger_line,
              f"- registry 声明：`{registry['trigger']}`；自然语言示例："
              + "、".join(f"「{item}」" for item in registry['intent_examples']),
              "- 不触发的情形：显式否定、意图歧义、只陈述问题而无执行请求（先只读诊断并要求确认）。", ""]
    lines += ["## 3. 必需输入", ""]
    lines += [f"- `{item}`" for item in preset['requires']]
    lines += ["- 加载顺序见 `shared-contract.md`：当前 `SKILL.md` → 项目 `AGENTS.md` → "
              "`shared-contract.md` → **本 Preset** → 必要 references。", ""]
    lines += ["## 4. 允许与禁止", "", "- 允许："]
    lines += [f"  - {item}" for item in preset['allowed']]
    lines += ["- 禁止："]
    lines += [f"  - {item}" for item in preset['forbidden']]
    lines += ["- 共同硬边界见 `shared-contract.md`：canonical state 是唯一科学事实、只读请求不得触发执行、"
              "工程故障不得写成否证、AALG/PEIG/容量与公平对照优先于 Preset、不得自行授权 GPU 或发布。", ""]
    lines += ["## 5. 复用的阶段、脚本与检查器", "",
              f"- 阶段：{pr.STAGES.get(preset['id'], '既有 R 阶段')}", "- 脚本 / 检查器："]
    lines += [f"  - `scripts/{name}.py`" for name in preset['reuses']]
    lines += ["- 规则号：本仓库自身产生 `PR1`—`PR9`；科学判定仍由既有规则号给出。", "",
              "## 6. 执行步骤", "", "**提供版执行协议（逐字）：**", "", provided_steps or "（提供版未给出步骤）",
              "", "**在本仓库中实际执行的命令：**", "",
              "| # | 步骤 | 命令 |", "|---|---|---|"]
    lines += steps_table
    lines += ["", "> 上表由 `preset_router.py run --preset " + preset['id'] + "` 实际返回，"
              "文档与代码由 `test_preset_router` 断言一致。", ""]
    lines += ["## 7. 输出契约", "", "**提供版产出（逐字）：**", "", provided_outputs or "（提供版未给出产出）",
              "", "- 机器可读字段："]
    lines += [f"  - `{item}`" for item in preset['outputs']]
    lines += ["  - 统一字段：`preset_id` / `status` / `entry` / `execution_scope` / `protocol` / "
              "`reused` / `observed` / `decision` / `steps` / `writes` / `changed_decision` / "
              "`next_action` / `canonical_untouched`。", ""]
    lines += ["## 8. 状态写回", "", "- 允许写入："]
    lines += [f"  - {item}" for item in preset['writes']]
    lines += [f"- canonical `research-state.json`：{pr.SCOPE_CANONICAL.get(preset['execution_scope'], '不写')}。",
              "- 恢复动作记录到 `cognition/recovery-log.jsonl`；策略决策记录到 "
              "`scheduler.strategy_decisions[]`（皆为控制平面/遥测，不是科学事实）。", ""]
    lines += ["## 9. 停止、失败与恢复", "", "**提供版边界与退出（逐字）：**", "",
              provided_stops or "（提供版未给出边界）", "", "- 机器可读停止条件："]
    lines += [f"  - {item}" for item in preset['stops']]
    lines += ["- 失败处理：无法继续时 `HOLD`（退出码 4）并说明 `hold_reason`；不重复检查、不放宽门禁。",
              "- 恢复条件：状态变化后可再次尝试；同一指纹超过上限即交人裁决。", ""]
    for name, text_value in extras:
        lines += [f"### {name}", "", text_value, ""]
    return '\n'.join(lines).rstrip() + '\n'


def main():
    registry = {item['preset_id']: item
                for item in pr.load_registry()['presets']}
    written = []
    for preset_id in pr.PRESET_IDS:
        preset = pr.presets_by_id()[preset_id]
        import tempfile
        with tempfile.TemporaryDirectory() as temp:
            state_path = pr._fixture(pathlib.Path(temp) / preset_id)
            payload, _, _ = pr.run_preset(preset_id, state_path)
        preset = {**preset, '_steps': [
            {**step, 'command': str(step.get('command')).replace(str(state_path), '<state>')}
            for step in payload['steps']]}
        text = render(preset, registry[preset_id])
        (ROOT / 'presets' / f"{preset_id}.md").write_text(text, encoding='utf-8')
        written.append(preset_id)
    return written


if __name__ == '__main__':
    print('merged:', ', '.join(main()))
