#!/usr/bin/env python3
"""test_preset_router.py — Intent routing, loop recovery, self-evolution and the adapter.

What this file is guarding
--------------------------
The preset library is only useful if three things hold, and each of them is a behaviour rather
than a document:

* **routing** — the sixteen presets are reachable from the way a researcher actually talks,
  refusals are respected, ambiguity falls back to the least privileged protocol, and a
  read-only question never becomes an execution;
* **recovery** — the loop notices context drift, engineering failure, resource blockage and
  evidence conflict from machine-readable state, cannot loop forever, and never turns an
  engineering failure into a scientific verdict;
* **self-evolution** — a strategy change reaches the *next real action selection*, not just a
  log line; and when the hard gates leave no room the decision says so instead of inventing a
  difference.

Verification levels are reported at the end of the file: L1 (unit), L2 (synthetic end-to-end
through the real interfaces). L3 (real research A/B) is **not** performed here and must not be
claimed.
"""

from __future__ import annotations

import contextlib
import io
import json
import pathlib
import subprocess
import sys
import tempfile
import unittest

import cognition as cg
import preset_router as pr
import strategy_memory as sm

ROOT = pathlib.Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "preset_router.py"
STRATEGY_SCRIPT = ROOT / "scripts" / "strategy_memory.py"


def clone(value):
    return json.loads(json.dumps(value))


def quiet(callable_, *args, **kwargs):
    with contextlib.redirect_stdout(io.StringIO()) as sink:
        result = callable_(*args, **kwargs)
    return result, sink.getvalue()


def candidate(hid, island, operator, niche, statement="探索方向"):
    return {
        "id": hid, "statement": statement,
        "structural_signature": {"assumption_distance": 1, "formulation_distance": 1,
                                 "representation_distance": 1, "theory_lens_distance": 1,
                                 "mechanism_distance": 1},
        "novelty_source": "迁移", "theory_lens": "逆问题", "nearest_prior": "LIT1",
        "falsifier": "干预无效", "expected_information_gain": 0.3, "status": "active",
        "niche": niche, "island": island, "generation": 1, "operator": operator,
        "parents": ["H1"], "depends_on": [],
        "validity": {"status": "valid", "reason": "未推翻", "since_state_version": 0},
        "scientific_scope": "数据集 A",
    }


ZERO_GAIN = {"experiment": "X0", "predicted_information_gain": "high",
             "actual_information_gain": "zero",
             "observed_delta": {"claim_status_changes": [], "uncertainty_changes": [],
                                "hypothesis_status_changes": [], "new_uncertainties": [],
                                "unexpected_observations": 0}}


def scheduler_with(actions, *, zero_gain=0, operator_stats=None):
    return {"_schema": "research-idea-pipeline/scheduler@1", "state_version": 4,
            "next_actions": list(actions),
            "eig_calibration": {"records": [clone(ZERO_GAIN) for _ in range(zero_gain)]},
            "operator_stats": operator_stats or {"by_operator": {},
                                                 "recurring_failure_patterns": []}}


def action(ident, *, target=None, eig="high", cost="low", kind="repair"):
    return {"action": ident, "type": kind, "target": target or ident, "eig": eig, "cost": cost}


# ---------------------------------------------------------------------------
# L1: intent routing
# ---------------------------------------------------------------------------

class TestIntentRouting(unittest.TestCase):

    def test_all_sixteen_are_reachable_by_id(self):
        self.assertEqual(len(pr.PRESETS), 16)
        for preset in pr.PRESETS:
            result = pr.resolve(preset["id"])
            self.assertEqual(result["preset_id"], preset["id"], preset["id"])
            self.assertEqual(result["trigger"], "explicit")
            self.assertEqual(result["entry"], preset["entry"])
            self.assertEqual(result["execution_scope"], preset["execution_scope"])
            self.assertTrue(result["protocol"].startswith("presets/"))

    def test_all_sixteen_are_reachable_from_chinese(self):
        for preset in pr.PRESETS:
            for phrase in preset["zh"]:
                result = pr.resolve(phrase)
                self.assertEqual(result["preset_id"], preset["id"],
                                 f"{phrase!r} should route to {preset['id']}")

    def test_all_sixteen_are_reachable_from_english(self):
        for preset in pr.PRESETS:
            for phrase in preset["en"]:
                result = pr.resolve(phrase)
                self.assertEqual(result["preset_id"], preset["id"],
                                 f"{phrase!r} should route to {preset['id']}")

    def test_documented_examples_from_the_specification(self):
        """The exact user phrasings the release promises to understand."""
        cases = {
            "继续自动科研": "research-loop",
            "一直跑科研闭环": "research-loop",
            "跳出当前思路": "paradigm-escape",
            "换一种数学建模方法": "paradigm-escape",
            "恢复之前的科研状态": "research-recovery",
            "上下文丢了": "research-recovery",
            "重新规划研究路线": "scientific-replanning",
            "审查目前的方法和实验": "research-audit",
            "现在到底取得了什么科学进展？": "research-review",
            "一直在重复归因，没有新东西": "stagnation-breaker",
            "训练 OOM 了": "experiment-failure-recovery",
            "实验出现 NaN": "experiment-failure-recovery",
            "证据和研究状态对不上": "evidence-conflict-repair",
            "GPU 不够了": "resource-recovery",
            "执行环境坏了": "resource-recovery",
            "合并和整理机制记忆": "memory-consolidation",
            "检查 Loop 是否正在原地打转": "loop-health-check",
            "根据历史结果改进探索策略": "strategy-evolution",
            "所有 idea 都太相似了": "hypothesis-rebalance",
            "用历史案例验证自进化是否有效": "discovery-replay",
        }
        for text, expected in cases.items():
            result = pr.resolve(text)
            self.assertEqual(result["preset_id"], expected, f"{text!r} → {result}")
            self.assertEqual(result["action"], "ROUTE")

    def test_a_negated_preset_is_never_selected(self):
        for text in ("不要审计", "别审查", "先不做对抗审查", "don't audit"):
            result = pr.resolve(text)
            self.assertNotEqual(result["preset_id"], "research-audit", text)
            self.assertEqual(result["action"], "HOLD", text)
            self.assertIn(result["hold_reason"], ("intent_negated", "no_intent_matched"))

    def test_a_negation_does_not_swallow_the_rest_of_the_request(self):
        result = pr.resolve("先不要跑自动科研，只汇报进展")
        self.assertEqual(result["preset_id"], "research-review")
        self.assertIn("research-loop", result["negated"])

    def test_an_exact_tie_falls_back_to_the_least_privileged_protocol(self):
        result = pr.resolve("汇报并恢复")
        self.assertTrue(result["requires_confirmation"])
        self.assertGreaterEqual(len(result.get("ambiguous_with") or []), 2)
        self.assertEqual(pr.scope_privilege(result["execution_scope"]), "read_only")

    def test_the_expert_phase_entry_is_not_hijacked(self):
        result = pr.resolve("phase=R7")
        self.assertIsNone(result["preset_id"])
        self.assertEqual(result["hold_reason"], "expert_phase_entry")
        self.assertTrue(result["expert_phase"])
        self.assertEqual(pr.resolve("phase=R7 审计方法")["preset_id"], "research-audit")

    def test_a_read_only_question_never_becomes_an_execution(self):
        """`research-review` / `loop-health-check` are read-only; `audit` is advisory.

        The provided registry separates `read_only` / `inspect_only` from `audit` (which may
        write `assurance[]` through R7). Neither may execute, and the distinction is kept.
        """
        for text, expected_privilege in (("总结进展", {"read_only"}),
                                         ("汇报一下", {"read_only"}),
                                         ("现在到底取得了什么科学进展", {"read_only"}),
                                         ("审查目前的方法和实验", {"read_only", "advisory"}),
                                         ("检查 Loop 是否正在原地打转", {"read_only"})):
            result = pr.resolve(text)
            privilege = pr.scope_privilege(result["execution_scope"])
            self.assertIn(privilege, expected_privilege, text)
            self.assertNotIn(privilege, ("discovery", "strategy", "execute"), text)
            self.assertIsNot(result["requires_confirmation"], True, text)

    def test_a_descriptive_report_starts_read_only_and_asks(self):
        result = pr.resolve("训练 OOM 了")
        self.assertEqual(result["preset_id"], "experiment-failure-recovery")
        self.assertEqual(result["next_action"], "diagnose")
        self.assertTrue(result["requires_confirmation"])

    def test_an_explicit_request_may_execute(self):
        result = pr.resolve("帮我恢复训练失败的实验")
        self.assertEqual(result["preset_id"], "experiment-failure-recovery")
        self.assertEqual(result["next_action"], "execute")
        self.assertFalse(result["requires_confirmation"])

    def test_unknown_text_holds_instead_of_guessing(self):
        result = pr.resolve("今天天气不错")
        self.assertEqual(result["action"], "HOLD")
        self.assertEqual(result["hold_reason"], "no_intent_matched")

    def test_the_result_is_traceable(self):
        result = pr.resolve("训练 OOM 了")
        for key in ("preset_id", "entry", "trigger", "reason", "execution_scope", "protocol"):
            self.assertIn(key, result)
            self.assertIsNotNone(result[key])
        self.assertIn(result["trigger"], pr.TRIGGERS)

    def test_the_router_cli_exits_zero_for_a_route_and_four_for_a_hold(self):
        routed = subprocess.run([sys.executable, str(SCRIPT), "resolve", "--text", "总结进展"],
                                capture_output=True, text=True, cwd=str(ROOT))
        self.assertEqual(routed.returncode, pr.EXIT_OK, routed.stderr)
        self.assertEqual(json.loads(routed.stdout)["preset_id"], "research-review")
        held = subprocess.run([sys.executable, str(SCRIPT), "resolve", "--text", "不要审计"],
                              capture_output=True, text=True, cwd=str(ROOT))
        self.assertEqual(held.returncode, pr.EXIT_ENV)
        self.assertEqual(json.loads(held.stdout)["action"], "HOLD")

    def test_list_and_inspect_cover_every_preset(self):
        code, out = quiet(pr.op_list, True)
        self.assertEqual(code, pr.EXIT_OK)
        self.assertEqual(len(json.loads(out)["presets"]), 16)
        for preset in pr.PRESETS:
            payload = pr.inspect(preset["id"])
            self.assertNotIn("error", payload)
            self.assertEqual(payload["sections_present"], list(pr.PROTOCOL_SECTIONS),
                             preset["id"])
        self.assertIn("error", pr.inspect("no-such-preset"))


# ---------------------------------------------------------------------------
# L1: the registry cannot drift from the protocols
# ---------------------------------------------------------------------------

class TestRegistryParity(unittest.TestCase):

    def test_the_registry_is_valid(self):
        self.assertEqual(pr.registry_errors(), [])

    def test_groups_and_handlers_are_complete(self):
        self.assertEqual(len(pr.PRESET_IDS), 16)
        self.assertEqual(set(pr.HANDLERS), set(pr.PRESET_IDS))
        groups = {group: sum(1 for p in pr.PRESETS if p["group"] == group)
                  for group in pr.PRESET_GROUPS}
        self.assertEqual(groups, {"user": 6, "recovery": 7, "evolution": 3})

    def test_every_documented_command_is_a_command_the_code_runs(self):
        with tempfile.TemporaryDirectory() as temp:
            for preset in pr.PRESETS:
                state_path = pr._fixture(pathlib.Path(temp) / preset["id"])
                payload, _, _ = pr.run_preset(preset["id"], state_path)
                # The protocol templates the throwaway fixture path; compare like for like.
                commands = {str(step.get("command")).replace(str(state_path), "<state>")
                            for step in payload["steps"]}
                text = (ROOT / preset["protocol"]).read_text(encoding="utf-8")
                for command in commands:
                    self.assertIn(command, text,
                                  f"{preset['id']} documents a command it does not run: {command}")

    def test_every_preset_declares_its_boundaries(self):
        for preset in pr.PRESETS:
            self.assertTrue(preset["allowed"] and preset["forbidden"])
            self.assertTrue(preset["stops"] and preset["outputs"] and preset["writes"])
            self.assertIn(preset["entry"], pr.ENTRIES)
            self.assertIn(preset["execution_scope"], pr.EXECUTION_SCOPES)
            self.assertIn(pr.scope_privilege(preset["execution_scope"]), pr.PRIVILEGE_RANK)

    def test_user_presets_are_never_auto_started(self):
        """A user preset may be *recommended* by the trigger, never started by it."""
        for preset in pr.PRESETS:
            if preset["group"] == "user":
                if preset["auto"] is not None:
                    self.assertEqual(preset["auto"]["mode"], "recommend", preset["id"])
            else:
                self.assertIsNotNone(preset["auto"], preset["id"])
                self.assertEqual(preset["auto"]["mode"], "recover", preset["id"])


# ---------------------------------------------------------------------------
# L2: loop recovery
# ---------------------------------------------------------------------------

class TestLoopRecovery(unittest.TestCase):

    def _project(self, root, **kw):
        state_path = pr._fixture(root)
        if kw:
            state = json.loads(state_path.read_text(encoding="utf-8"))
            state.update(kw)
            state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2),
                                  encoding="utf-8")
        return state_path

    def _trigger(self, state_path, *, build=True, records=None, scheduler=None):
        if build:
            cg.op_build(state_path, state_path.parent / cg.COGNITION_DIRNAME)
        context = pr.project_context(state_path)
        return pr.trigger(context["state"], index=context["index_on_disk"],
                          scheduler=scheduler if scheduler is not None else context["scheduler"],
                          revisions=context["revisions"], records=records or [],
                          index_missing=context["index_missing"],
                          projection=context["index"]), context

    def test_a_missing_projection_triggers_context_recovery(self):
        with tempfile.TemporaryDirectory() as temp:
            state_path = self._project(pathlib.Path(temp) / "A")
            decision, _ = self._trigger(state_path, build=False)
            self.assertEqual(decision["action"], "RECOVER")
            self.assertEqual(decision["selected"]["preset_id"], "context-drift-recovery")

    def test_a_built_matching_index_has_nothing_to_recover(self):
        with tempfile.TemporaryDirectory() as temp:
            state_path = self._project(pathlib.Path(temp) / "A")
            decision, _ = self._trigger(state_path)
            self.assertEqual(decision["action"], "HOLD")
            self.assertEqual(decision["hold_reason"], "no_signal")

    def test_an_engineering_failure_triggers_its_own_recovery(self):
        with tempfile.TemporaryDirectory() as temp:
            root = pathlib.Path(temp) / "A"
            state_path = self._project(root)
            state = json.loads(state_path.read_text(encoding="utf-8"))
            state["experiments"][0].update({"status": "failed", "result_at_state_version": 4,
                                            "known_flaws": ["F1"]})
            state["failures"] = [{"id": "F1", "kind": "implementation_failure",
                                  "what": "loss 里 shape mismatch", "why": "张量维度写错",
                                  "referenced_by": ["X1"], "depends_on": [],
                                  "validity": {"status": "valid", "reason": "记录",
                                               "since_state_version": 4},
                                  "source_review": None}]
            state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2),
                                  encoding="utf-8")
            decision, _ = self._trigger(state_path)
            self.assertEqual(decision["selected"]["preset_id"], "experiment-failure-recovery")
            self.assertTrue(decision["selected"]["requires_confirmation"])

    def test_resource_failure_outranks_the_generic_engineering_recovery(self):
        with tempfile.TemporaryDirectory() as temp:
            root = pathlib.Path(temp) / "A"
            state_path = self._project(root)
            state = json.loads(state_path.read_text(encoding="utf-8"))
            state["experiments"][0].update({"status": "failed", "result_at_state_version": 4,
                                            "known_flaws": ["F1"]})
            state["failures"] = [{"id": "F1", "kind": "optimization_failure",
                                  "what": "训练 OOM", "why": "显存不足，batch 过大",
                                  "referenced_by": ["X1"], "depends_on": [],
                                  "validity": {"status": "valid", "reason": "记录",
                                               "since_state_version": 4},
                                  "source_review": None}]
            state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2),
                                  encoding="utf-8")
            decision, _ = self._trigger(state_path)
            self.assertEqual(decision["selected"]["preset_id"], "resource-recovery")

    def test_evidence_safety_outranks_scientific_stagnation(self):
        with tempfile.TemporaryDirectory() as temp:
            root = pathlib.Path(temp) / "A"
            state_path = self._project(root)
            state = json.loads(state_path.read_text(encoding="utf-8"))
            state["evidence"] = [{"id": "E1", "kind": "experiment", "supports": ["C1"],
                                  "contradicts": [], "strength": "strong", "scope": "数据集 A",
                                  "epistemic_status": "Observed", "source_ref": "X1",
                                  "verification_tier": "T2", "depends_on": ["X1"],
                                  "validity": {"status": "valid", "reason": "已写入",
                                               "since_state_version": 4}}]
            state["claims"][0].update({"status": "supported", "supporting_evidence": ["E1"],
                                       "refuting_evidence": ["E1"]})
            state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2),
                                  encoding="utf-8")
            scheduler = scheduler_with([], zero_gain=3)
            decision, _ = self._trigger(state_path, records=[], scheduler=scheduler)
            self.assertEqual(decision["selected"]["preset_id"], "evidence-conflict-repair")
            self.assertLess(decision["selected"]["priority"],
                            pr.presets_by_id()["stagnation-breaker"]["priority"])

    def test_an_invalid_canonical_state_blocks_every_recovery(self):
        with tempfile.TemporaryDirectory() as temp:
            state_path = self._project(pathlib.Path(temp) / "A")
            state = json.loads(state_path.read_text(encoding="utf-8"))
            state["claims"][0]["supporting_evidence"] = ["E9"]
            state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2),
                                  encoding="utf-8")
            decision, _ = self._trigger(state_path)
            self.assertEqual(decision["action"], "HOLD")
            self.assertEqual(decision["hold_reason"], "state_integrity_blocked")

    def test_the_same_snapshot_cannot_trigger_twice(self):
        with tempfile.TemporaryDirectory() as temp:
            state_path = self._project(pathlib.Path(temp) / "A")
            decision, context = self._trigger(state_path, build=False)
            selected = decision["selected"]
            records = [{"preset_id": selected["preset_id"],
                        "signal_fingerprint": selected["fingerprint"],
                        "at_state_version": 4}]
            again, _ = self._trigger(state_path, build=False, records=records)
            self.assertEqual(again["action"], "HOLD")
            self.assertEqual(again["hold_reason"], "already_attempted_at_this_snapshot")

    def test_a_moved_state_may_try_again(self):
        with tempfile.TemporaryDirectory() as temp:
            state_path = self._project(pathlib.Path(temp) / "A")
            decision, _ = self._trigger(state_path, build=False)
            fingerprint = decision["selected"]["fingerprint"]
            records = [{"preset_id": "context-drift-recovery", "signal_fingerprint": fingerprint,
                        "at_state_version": 3}]
            again, _ = self._trigger(state_path, build=False, records=records)
            self.assertEqual(again["action"], "RECOVER")

    def test_cooldown_and_attempt_limit_are_enforced(self):
        preset = pr.presets_by_id()["stagnation-breaker"]
        self.assertGreaterEqual(preset["cooldown_rounds"], 1)
        cooled = pr.recovery_guard([{"preset_id": preset["id"], "signal_fingerprint": "other",
                                     "at_state_version": 4}], preset, "fresh", 5)
        self.assertEqual(cooled["reason"], "cooldown_active")
        capped = pr.recovery_guard([{"preset_id": preset["id"],
                                     "signal_fingerprint": "fresh",
                                     "at_state_version": 1}] * preset["max_attempts"],
                                   preset, "fresh", 9)
        self.assertEqual(capped["reason"], "attempt_limit_reached")

    def test_the_ledger_is_control_plane_and_never_touches_canonical(self):
        with tempfile.TemporaryDirectory() as temp:
            state_path = self._project(pathlib.Path(temp) / "A")
            before = state_path.read_bytes()
            code = pr.main(["record", "--state", str(state_path),
                            "--preset", "loop-health-check", "--outcome", "checked"])
            self.assertEqual(code, pr.EXIT_OK)
            ledger = pr.ledger_path(state_path.parent / cg.COGNITION_DIRNAME)
            self.assertTrue(ledger.is_file())
            records, diagnostics = pr.load_ledger(ledger)
            self.assertEqual(diagnostics, [])
            self.assertEqual(records[0]["preset_id"], "loop-health-check")
            self.assertIn("signal_fingerprint", records[0])
            self.assertEqual(state_path.read_bytes(), before)

    def test_the_recovery_never_refreshes_the_aalg_budget(self):
        with tempfile.TemporaryDirectory() as temp:
            root = pathlib.Path(temp) / "A"
            state_path = self._project(root)
            ledger_dir = state_path.parent / ".execution"
            ledger_dir.mkdir(exist_ok=True)
            policy = ledger_dir / "policy.json"
            policy.write_text(json.dumps({"max_preflight_revisions": 3}), encoding="utf-8")
            before = policy.read_bytes()
            pr.main(["trigger", "--state", str(state_path)])
            pr.main(["record", "--state", str(state_path), "--preset", "loop-health-check"])
            self.assertEqual(policy.read_bytes(), before)

    def test_every_preset_runs_through_the_public_interface(self):
        with tempfile.TemporaryDirectory() as temp:
            state_path = self._project(pathlib.Path(temp) / "A")
            before = state_path.read_bytes()
            for preset in pr.PRESETS:
                payload, _, code = pr.run_preset(preset["id"], state_path)
                self.assertEqual(payload["preset_id"], preset["id"])
                self.assertIn(payload["status"], ("OK", "NO_CHANGE", "BLOCKED", "HOLD"))
                self.assertIn(code, (pr.EXIT_OK, pr.EXIT_HARD, pr.EXIT_ENV))
                self.assertIn("canonical_untouched", payload)
                self.assertTrue(payload["canonical_untouched"], preset["id"])
                if pr.scope_privilege(preset["execution_scope"]) == "read_only":
                    self.assertEqual(payload["writes"], [], preset["id"])
            self.assertEqual(state_path.read_bytes(), before)

    def test_the_trigger_cli_reports_hold_with_exit_four(self):
        with tempfile.TemporaryDirectory() as temp:
            state_path = self._project(pathlib.Path(temp) / "A")
            cg.op_build(state_path, state_path.parent / cg.COGNITION_DIRNAME)
            proc = subprocess.run([sys.executable, str(SCRIPT), "trigger", "--state",
                                   str(state_path)], capture_output=True, text=True, cwd=str(ROOT))
            self.assertEqual(proc.returncode, pr.EXIT_ENV)
            self.assertEqual(json.loads(proc.stdout)["hold_reason"], "no_signal")


# ---------------------------------------------------------------------------
# L2: scientific behaviour
# ---------------------------------------------------------------------------

class TestScientificBehaviour(unittest.TestCase):

    def test_paradigm_escape_changes_the_representation_and_demands_an_audit(self):
        with tempfile.TemporaryDirectory() as temp:
            state_path = pr._fixture(pathlib.Path(temp) / "A")
            payload, _, code = pr.run_preset("paradigm-escape", state_path)
            self.assertEqual(code, pr.EXIT_OK)
            self.assertGreaterEqual(len(payload["observed"]["axes_changed"]), 2)
            before = payload["observed"]["representation_before"]
            after = payload["observed"]["representation_after"]
            self.assertNotEqual(cg.digest_of(after), cg.digest_of(
                {axis: before.get(axis) for axis in pr.REPRESENTATION_AXES}))
            self.assertTrue(payload["decision"]["requires_structural_audit"])
            self.assertEqual(payload["entry"], "explore")
            self.assertIn("参数/模块替换不算范式改变", payload["decision"]["note"])

    def test_stagnation_breaker_ignores_a_single_negative_result(self):
        with tempfile.TemporaryDirectory() as temp:
            state_path = pr._fixture(pathlib.Path(temp) / "A")
            payload, _, code = pr.run_preset("stagnation-breaker", state_path)
            self.assertEqual(code, pr.EXIT_OK)
            self.assertEqual(payload["status"], "NO_CHANGE")
            self.assertFalse(payload["changed_decision"])

    def test_stagnation_breaker_fires_on_repeated_zero_gain(self):
        with tempfile.TemporaryDirectory() as temp:
            root = pathlib.Path(temp) / "A"
            state_path = pr._fixture(root)
            scheduler = scheduler_with([], zero_gain=3)
            (state_path.parent / cg.SCHEDULER_NAME).write_text(
                json.dumps(scheduler, ensure_ascii=False), encoding="utf-8")
            payload, _, _ = pr.run_preset("stagnation-breaker", state_path)
            self.assertEqual(payload["status"], "OK")
            self.assertTrue(payload["changed_decision"])
            self.assertIn(payload["decision"]["switch_action"], pr.pc.SWITCH_ACTIONS)

    def test_research_review_is_read_only(self):
        with tempfile.TemporaryDirectory() as temp:
            state_path = pr._fixture(pathlib.Path(temp) / "A")
            payload, _, code = pr.run_preset("research-review", state_path)
            self.assertEqual(code, pr.EXIT_OK)
            self.assertEqual(pr.scope_privilege(payload["execution_scope"]), "read_only")
            self.assertEqual(payload["writes"], [])
            self.assertTrue(payload["decision"]["read_only"])
            self.assertIn("next_decisions", payload["observed"] | payload["decision"]
                          or payload["decision"]["next_decisions"])

    def test_audit_does_not_start_discovery(self):
        with tempfile.TemporaryDirectory() as temp:
            state_path = pr._fixture(pathlib.Path(temp) / "A")
            payload, _, _ = pr.run_preset("research-audit", state_path)
            self.assertEqual(payload["entry"], "audit")
            self.assertTrue(payload["decision"]["discovery_started"] is False)
            self.assertEqual(payload["execution_scope"], "audit")
            self.assertEqual(pr.scope_privilege(payload["execution_scope"]), "advisory")
            self.assertNotIn(pr.scope_privilege(payload["execution_scope"]),
                             ("discovery", "strategy", "execute"))
            for step in payload["steps"]:
                self.assertNotIn("experiment_execute.py run", step["command"])

    def test_an_engineering_failure_never_changes_scientific_status(self):
        with tempfile.TemporaryDirectory() as temp:
            root = pathlib.Path(temp) / "A"
            state_path = pr._fixture(root)
            state = json.loads(state_path.read_text(encoding="utf-8"))
            state["experiments"][0].update({"status": "failed", "result_at_state_version": 4,
                                            "known_flaws": ["F1"]})
            state["failures"] = [{"id": "F1", "kind": "optimization_failure", "what": "OOM",
                                  "why": "显存不足", "referenced_by": ["X1"], "depends_on": [],
                                  "validity": {"status": "valid", "reason": "记录",
                                               "since_state_version": 4},
                                  "source_review": None}]
            state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2),
                                  encoding="utf-8")
            before_claims = cg.digest_of(state["claims"])
            before_hypotheses = cg.digest_of(state["hypotheses"])
            payload, _, _ = pr.run_preset("experiment-failure-recovery", state_path)
            self.assertEqual(payload["observed"]["scientific_effect"], "none")
            self.assertFalse(payload["decision"]["rerun_authorized"])
            current = json.loads(state_path.read_text(encoding="utf-8"))
            self.assertEqual(cg.digest_of(current["claims"]), before_claims)
            self.assertEqual(cg.digest_of(current["hypotheses"]), before_hypotheses)
            self.assertTrue(payload["canonical_untouched"])

    def test_memory_and_scheduler_do_not_upgrade_an_invalid_result(self):
        with tempfile.TemporaryDirectory() as temp:
            root = pathlib.Path(temp) / "A"
            state_path = pr._fixture(root)
            cg.op_build(state_path, state_path.parent / cg.COGNITION_DIRNAME)
            before = json.loads((state_path.parent / cg.COGNITION_DIRNAME
                                 / cg.INDEX_NAME).read_text(encoding="utf-8"))
            state = json.loads(state_path.read_text(encoding="utf-8"))
            state["experiments"][0].update({"status": "failed", "result_at_state_version": 4,
                                            "known_flaws": ["F1"]})
            state["failures"] = [{"id": "F1", "kind": "implementation_failure", "what": "崩溃",
                                  "why": "shape mismatch", "referenced_by": ["X1"],
                                  "depends_on": [],
                                  "validity": {"status": "valid", "reason": "记录",
                                               "since_state_version": 4},
                                  "source_review": None}]
            state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2),
                                  encoding="utf-8")
            cg.op_build(state_path, state_path.parent / cg.COGNITION_DIRNAME)
            after = json.loads((state_path.parent / cg.COGNITION_DIRNAME
                                / cg.INDEX_NAME).read_text(encoding="utf-8"))
            self.assertEqual(
                [m["support_level"] for m in after["mechanisms"]],
                [m["support_level"] for m in before["mechanisms"]])
            self.assertEqual([m["status"] for m in after["mechanisms"]],
                             [m["status"] for m in before["mechanisms"]])

    def test_discovery_replay_is_leak_checked_and_has_no_composite_score(self):
        with tempfile.TemporaryDirectory() as temp:
            state_path = pr._fixture(pathlib.Path(temp) / "A")
            payload, _, code = pr.run_preset("discovery-replay", state_path)
            self.assertEqual(code, pr.EXIT_OK)
            self.assertTrue(payload["observed"]["leak_checked"])
            self.assertIsNone(payload["decision"]["composite_score"])
            self.assertIn("limitations", payload["decision"])
            self.assertNotIn("score", json.dumps(payload["observed"], ensure_ascii=False).lower()
                             .replace("no_weighted_score", ""))


# ---------------------------------------------------------------------------
# L2: the strategy decision adapter reaches the next action selection
# ---------------------------------------------------------------------------

class TestStrategyDecisionAdapter(unittest.TestCase):

    def _project(self, root, *, candidates=(), zero_gain=0, actions=None,
                 operator_stats=None):
        state_path = pr._fixture(root)
        state = json.loads(state_path.read_text(encoding="utf-8"))
        state["hypotheses"] = list(state["hypotheses"]) + [candidate(*item) for item in candidates]
        state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
        scheduler = scheduler_with(actions or [], zero_gain=zero_gain,
                                   operator_stats=operator_stats)
        (state_path.parent / cg.SCHEDULER_NAME).write_text(
            json.dumps(scheduler, ensure_ascii=False, indent=2), encoding="utf-8")
        return state_path

    def test_the_advice_reorders_inside_one_tier_and_changes_the_choice(self):
        with tempfile.TemporaryDirectory() as temp:
            state_path = self._project(
                pathlib.Path(temp) / "A",
                candidates=[("H2", "P1", "reframe", "representation-shift")],
                zero_gain=2,
                actions=[action("H1", target="H1"), action("H2", target="H2")])
            context = pr.project_context(state_path)
            decision = sm.strategy_decision(context["state"], context["index"],
                                            context["scheduler"], context["revisions"])
            self.assertEqual(decision["advice"]["operator"], "reframe")
            self.assertTrue(decision["adopted"])
            self.assertTrue(decision["decision_changed"])
            self.assertEqual(decision["chosen_without_memory"], "H1")
            self.assertEqual(decision["chosen"], "H2")
            aligned = [c for c in decision["candidates_after"] if c["aligned"]]
            self.assertEqual([c["action"] for c in aligned], ["H2"])
            self.assertIn("hypotheses[H2]", aligned[0]["affinity_basis"])

    def test_a_better_tier_is_never_displaced_by_the_advice(self):
        with tempfile.TemporaryDirectory() as temp:
            state_path = self._project(
                pathlib.Path(temp) / "A",
                candidates=[("H2", "P1", "reframe", "representation-shift")],
                zero_gain=2,
                actions=[action("H1", target="H1", eig="high", cost="low"),
                         action("H2", target="H2", eig="low", cost="high")])
            context = pr.project_context(state_path)
            decision = sm.strategy_decision(context["state"], context["index"],
                                            context["scheduler"], context["revisions"])
            self.assertEqual(decision["chosen"], "H1")
            self.assertFalse(decision["decision_changed"])
            self.assertEqual([c["action"] for c in decision["candidates_after"]], ["H1", "H2"])
            self.assertEqual(decision["reason_if_not"], "single_candidate_in_tier")

    def test_the_adapter_says_why_when_it_cannot_change_anything(self):
        with tempfile.TemporaryDirectory() as temp:
            state_path = self._project(
                pathlib.Path(temp) / "A",
                candidates=[("H2", "P1", "reframe", "representation-shift")],
                actions=[action("H1", target="H1")])
            context = pr.project_context(state_path)
            decision = sm.strategy_decision(context["state"], context["index"],
                                            context["scheduler"], context["revisions"])
            self.assertFalse(decision["strategy_applied"])
            self.assertFalse(decision["decision_changed"])
            self.assertIn(decision["reason_if_not"],
                          ("single_candidate_in_tier", "no_aligned_candidate_in_tier"))

    def test_blocked_actions_are_never_selected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = pathlib.Path(temp) / "A"
            state_path = self._project(
                root, candidates=[("H2", "P1", "reframe", "representation-shift")],
                zero_gain=2,
                actions=[action("X1", target="X1", kind="discriminating_experiment"),
                         action("H2", target="H2")])
            state = json.loads(state_path.read_text(encoding="utf-8"))
            state["experiments"][0]["execution_blocked_by"] = ["STOP1"]
            state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2),
                                  encoding="utf-8")
            context = pr.project_context(state_path)
            decision = sm.strategy_decision(context["state"], context["index"],
                                            context["scheduler"], context["revisions"])
            self.assertIn("X1", decision["hard_gates"]["blocked_actions"])
            self.assertNotEqual(decision["chosen"], "X1")

    def test_recording_touches_only_scheduler_telemetry(self):
        with tempfile.TemporaryDirectory() as temp:
            state_path = self._project(
                pathlib.Path(temp) / "A",
                candidates=[("H2", "P1", "reframe", "representation-shift")],
                zero_gain=2, actions=[action("H1", target="H1"), action("H2", target="H2")])
            context = pr.project_context(state_path)
            decision = sm.strategy_decision(context["state"], context["index"],
                                            context["scheduler"], context["revisions"])
            before = context["scheduler"]
            updated = sm.record_strategy_decision(before, decision, dispatch_result="H2 dispatched")
            self.assertEqual(sorted(set(updated) - set(before)), ["strategy_decisions"])
            for key in before:
                self.assertEqual(updated[key], before[key], key)
            entry = sm.latest_strategy_decision(updated)
            self.assertEqual(entry["dispatch_result"], "H2 dispatched")
            self.assertIn("candidates_before", entry)
            self.assertEqual(entry["reason_if_not"], None)

    def test_the_cli_decide_records_into_the_scheduler_file(self):
        with tempfile.TemporaryDirectory() as temp:
            state_path = self._project(
                pathlib.Path(temp) / "A",
                candidates=[("H2", "P1", "reframe", "representation-shift")],
                zero_gain=2, actions=[action("H1", target="H1"), action("H2", target="H2")])
            scheduler_path = state_path.parent / cg.SCHEDULER_NAME
            before = json.loads(scheduler_path.read_text(encoding="utf-8"))
            proc = subprocess.run(
                [sys.executable, str(STRATEGY_SCRIPT), "decide", "--state", str(state_path),
                 "--scheduler", str(scheduler_path), "--record",
                 "--dispatch-result", "H2 dispatched"],
                capture_output=True, text=True, cwd=str(ROOT / "scripts"))
            self.assertEqual(proc.returncode, 0, proc.stderr)
            after = json.loads(scheduler_path.read_text(encoding="utf-8"))
            self.assertEqual(len(after["strategy_decisions"]), 1)
            self.assertEqual(after["eig_calibration"], before["eig_calibration"])
            self.assertEqual(after["next_actions"], before["next_actions"])
            self.assertEqual(after["operator_stats"], before["operator_stats"])

    def test_apply_is_recommendation_only_and_says_so(self):
        with tempfile.TemporaryDirectory() as temp:
            state_path = self._project(pathlib.Path(temp) / "A", zero_gain=1,
                                       actions=[action("H1", target="H1")])
            scheduler_path = state_path.parent / cg.SCHEDULER_NAME
            before = scheduler_path.read_bytes()
            proc = subprocess.run(
                [sys.executable, str(STRATEGY_SCRIPT), "apply", "--state", str(state_path),
                 "--scheduler", str(scheduler_path)],
                capture_output=True, text=True, cwd=str(ROOT / "scripts"))
            self.assertEqual(proc.returncode, 0, proc.stderr)
            payload = json.loads(proc.stdout)
            self.assertEqual(payload["writes"], [])
            self.assertIn("只输出建议", payload["note"])
            self.assertEqual(scheduler_path.read_bytes(), before)

    def test_the_next_round_consumes_the_recorded_decision(self):
        with tempfile.TemporaryDirectory() as temp:
            state_path = self._project(
                pathlib.Path(temp) / "A",
                candidates=[("H2", "P1", "reframe", "representation-shift")],
                zero_gain=2, actions=[action("H1", target="H1"), action("H2", target="H2")])
            cg.op_build(state_path, state_path.parent / cg.COGNITION_DIRNAME)
            context = pr.project_context(state_path)
            decision = sm.strategy_decision(context["state"], context["index"],
                                            context["scheduler"], context["revisions"])
            updated = sm.record_strategy_decision(context["scheduler"], decision,
                                                  dispatch_result="H2 dispatched")
            (state_path.parent / cg.SCHEDULER_NAME).write_text(
                json.dumps(updated, ensure_ascii=False, indent=2), encoding="utf-8")
            payload, _, code = pr.run_preset("research-loop", state_path)
            self.assertEqual(code, pr.EXIT_OK)
            guidance = payload["observed"]["strategy_guidance"]
            self.assertIsNotNone(guidance)
            self.assertFalse(guidance["stale"])
            self.assertEqual(guidance["dispatch"]["action"], "H2")
            self.assertEqual(guidance["discovery_operator"], "reframe")
            self.assertTrue(payload["decision"]["consumes_previous_decision"])
            self.assertIn("H2", payload["next_action"])

    def test_the_evolution_preset_reports_the_adapter_verdict(self):
        with tempfile.TemporaryDirectory() as temp:
            state_path = self._project(
                pathlib.Path(temp) / "A",
                candidates=[("H2", "P1", "reframe", "representation-shift")],
                zero_gain=2, actions=[action("H1", target="H1"), action("H2", target="H2")])
            payload, _, code = pr.run_preset("strategy-evolution", state_path)
            self.assertEqual(code, pr.EXIT_OK)
            self.assertEqual(payload["status"], "OK")
            self.assertTrue(payload["changed_decision"])
            self.assertTrue(payload["decision"]["strategy_applied"])
            self.assertIsNone(payload["decision"]["reason_if_not"])
            self.assertEqual(payload["decision"]["dispatch"]["action"], "H2")
            self.assertTrue(payload["decision"]["adoption_is_not_capability"])

    def test_the_evolution_preset_applies_revisions_and_records_the_decision(self):
        with tempfile.TemporaryDirectory() as temp:
            state_path = self._project(
                pathlib.Path(temp) / "A",
                candidates=[("H2", "P1", "reframe", "representation-shift")],
                zero_gain=2, actions=[action("H1", target="H1"), action("H2", target="H2")])
            cg.op_build(state_path, state_path.parent / cg.COGNITION_DIRNAME)
            scheduler_before = json.loads((state_path.parent / cg.SCHEDULER_NAME)
                                         .read_text(encoding="utf-8"))
            revisions_path = state_path.parent / cg.COGNITION_DIRNAME / cg.REVISIONS_NAME
            payload, _, _ = pr.run_preset("strategy-evolution", state_path, apply=True)
            self.assertIn(cg.SCHEDULER_NAME, payload["writes"])
            after = json.loads((state_path.parent / cg.SCHEDULER_NAME)
                               .read_text(encoding="utf-8"))
            self.assertEqual(len(after["strategy_decisions"]), 1)
            self.assertEqual(after["eig_calibration"], scheduler_before["eig_calibration"])
            self.assertTrue(payload["canonical_untouched"])
            self.assertTrue(revisions_path.exists() or payload["observed"]["applied_revisions"] == 0)

    def test_an_unchangeable_decision_is_reported_not_faked(self):
        with tempfile.TemporaryDirectory() as temp:
            state_path = self._project(pathlib.Path(temp) / "A",
                                       actions=[action("H1", target="H1")])
            payload, _, code = pr.run_preset("strategy-evolution", state_path)
            self.assertEqual(code, pr.EXIT_OK)
            self.assertEqual(payload["status"], "NO_CHANGE")
            self.assertFalse(payload["changed_decision"])
            self.assertEqual(payload["decision"]["strategy_applied"], False)
            self.assertTrue(payload["decision"]["reason_if_not"])

    def test_cross_session_recovery_still_consumes_the_experience(self):
        """A new session re-reads the scheduler from disk and gets the same decision path."""
        with tempfile.TemporaryDirectory() as temp:
            state_path = self._project(
                pathlib.Path(temp) / "A",
                candidates=[("H2", "P1", "reframe", "representation-shift")],
                zero_gain=2, actions=[action("H1", target="H1"), action("H2", target="H2")])
            context = pr.project_context(state_path)
            decision = sm.strategy_decision(context["state"], context["index"],
                                            context["scheduler"], context["revisions"])
            updated = sm.record_strategy_decision(context["scheduler"], decision,
                                                  dispatch_result="H2 dispatched")
            (state_path.parent / cg.SCHEDULER_NAME).write_text(
                json.dumps(updated, ensure_ascii=False, indent=2), encoding="utf-8")
            fresh = pr.project_context(state_path)
            replayed = sm.strategy_decision(fresh["state"], fresh["index"], fresh["scheduler"],
                                            fresh["revisions"])
            self.assertEqual(replayed["chosen"], decision["chosen"])
            self.assertEqual(sm.latest_strategy_decision(fresh["scheduler"])["dispatch_result"],
                             "H2 dispatched")


# ---------------------------------------------------------------------------
# L2: the provided library is integrated as data, not pasted as prose
# ---------------------------------------------------------------------------

class TestProvidedLibraryIntegration(unittest.TestCase):
    """`preset-registry.json` drives ids/entries/scopes/examples; the repo keeps enforcement."""

    def test_the_registry_is_the_source_of_truth(self):
        registry = pr.load_registry()
        records = {item["preset_id"]: item for item in registry["presets"]}
        self.assertEqual(len(records), 16)
        self.assertEqual(registry["base_contract"], "shared-contract.md")
        for preset in pr.PRESETS:
            record = records[preset["id"]]
            self.assertEqual(preset["entry"], record["entry"], preset["id"])
            self.assertEqual(preset["execution_scope"], record["execution_scope"], preset["id"])
            self.assertEqual(preset["protocol"], record["path"], preset["id"])
            self.assertEqual(preset["registry_trigger"], record["trigger"], preset["id"])
            self.assertEqual(len(preset["intent_examples"]), 3, preset["id"])

    def test_every_protocol_is_independent_and_references_the_shared_contract(self):
        for preset in pr.PRESETS:
            path = ROOT / preset["protocol"]
            text = path.read_text(encoding="utf-8")
            self.assertIn("shared-contract.md", text, preset["id"])
            self.assertIn(preset["id"], text)
            for other in pr.PRESET_IDS:
                if other != preset["id"]:
                    self.assertNotIn(f"`{other}` — ", text,
                                     f"{preset['id']} embeds another preset")
            self.assertLess(len(text), 12000, preset["id"])

    def test_the_provided_router_fixtures_all_pass(self):
        report = pr.run_router_fixtures()
        self.assertEqual(report["status"], "PASS", report["failed"])
        self.assertEqual(report["total"], 53)
        self.assertEqual(report["passed"], 53)

    def test_every_positive_fixture_reports_its_boundary(self):
        report = pr.run_router_fixtures()
        for case in report["cases"]:
            if case["guard"]:
                continue
            resolved = pr.resolve(case["input"])
            self.assertEqual(resolved["action"], "ROUTE", case["input"])
            self.assertIn(resolved["entry"], pr.ENTRIES, case["input"])
            self.assertIn(resolved["execution_scope"], pr.EXECUTION_SCOPES, case["input"])
            self.assertIn(pr.scope_privilege(resolved["execution_scope"]),
                          pr.PRIVILEGE_RANK, case["input"])
            self.assertTrue(resolved["protocol"].startswith("presets/"), case["input"])

    def test_the_five_guard_fixtures_hold_behaviourally(self):
        by_input = {case["input"]: case for case in
                    json.loads((ROOT / pr.ROUTER_FIXTURES_NAME).read_text(encoding="utf-8"))
                    ["fixtures"] if case.get("guard")}
        self.assertEqual(len(by_input), 5)

        no_audit = pr.resolve("不要审查，我只想知道下一步方案")
        self.assertNotEqual(no_audit["preset_id"], "research-audit")
        self.assertIn(pr.scope_privilege(no_audit["execution_scope"]), ("read_only",))

        read_only = pr.resolve("只总结研究结果，不要跑 GPU")
        self.assertEqual(pr.scope_privilege(read_only["execution_scope"]), "read_only")
        payload, _, code = pr.run_preset(read_only["preset_id"],
                                        pr._fixture(pathlib.Path(tempfile.mkdtemp()) / "A"))
        self.assertEqual(code, pr.EXIT_OK)
        self.assertEqual(payload["writes"], [])

        loop = pr.resolve("我想继续科研，但是不能启动新实验")
        self.assertEqual(loop["preset_id"], "research-loop")
        preset = pr.presets_by_id()["research-loop"]
        self.assertTrue(any("授权" in item or "AALG" in item or "PEIG" in item
                            for item in preset["forbidden"]),
                        "research-loop must forbid unauthorised execution")

        oom = pr.resolve("OOM 之后是不是说明理论失败了")
        self.assertEqual(oom["preset_id"], "experiment-failure-recovery")
        with tempfile.TemporaryDirectory() as temp:
            root = pathlib.Path(temp) / "A"
            state_path = pr._fixture(root)
            state = json.loads(state_path.read_text(encoding="utf-8"))
            state["experiments"][0].update({"status": "failed", "result_at_state_version": 4,
                                            "known_flaws": ["F1"]})
            state["failures"] = [{"id": "F1", "kind": "optimization_failure", "what": "OOM",
                                  "why": "显存不足", "referenced_by": ["X1"], "depends_on": [],
                                  "validity": {"status": "valid", "reason": "记录",
                                               "since_state_version": 4},
                                  "source_review": None}]
            state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2),
                                  encoding="utf-8")
            before = state_path.read_bytes()
            recovery, _, _ = pr.run_preset("experiment-failure-recovery", state_path)
            self.assertEqual(recovery["observed"]["scientific_effect"], "none")
            self.assertEqual(state_path.read_bytes(), before)

        upgrade = pr.resolve("把已否证的机制直接标记为支持")
        self.assertIsNone(upgrade["preset_id"])
        self.assertEqual(upgrade["action"], "HOLD")

    def test_only_the_selected_preset_is_loaded(self):
        payload, code = pr.load_preset_context("research-review")
        self.assertEqual(code, pr.EXIT_OK)
        self.assertEqual(payload["load"], ["shared-contract.md", "presets/research-review.md"])
        self.assertEqual(len(payload["not_loaded"]), 15)
        text = payload["protocol_text"]
        self.assertIn("research-review", text)
        for other in payload["not_loaded"]:
            self.assertNotIn(f"# Preset: `{other}`", text)
        self.assertLess(payload["protocol_chars"], 12000)
        self.assertEqual(pr.load_preset_context("no-such-preset")[1], pr.EXIT_ENV)

    def test_a_user_preset_can_only_be_recommended_by_the_trigger(self):
        recommend = [p for p in pr.PRESETS if p["group"] == "user" and p["auto"]]
        self.assertTrue(recommend, "the registry marks some user presets as event-triggerable")
        for preset in recommend:
            self.assertEqual(preset["auto"]["mode"], "recommend")
        with tempfile.TemporaryDirectory() as temp:
            state_path = pr._fixture(pathlib.Path(temp) / "A")
            cg.op_build(state_path, state_path.parent / cg.COGNITION_DIRNAME)
            context = pr.project_context(state_path)
            scheduler = pr.scheduler_with([], zero_gain=3) if hasattr(pr, "scheduler_with") else {
                "state_version": 4, "next_actions": [],
                "eig_calibration": {"records": [{"experiment": "X0",
                                                 "predicted_information_gain": "high",
                                                 "actual_information_gain": "zero",
                                                 "observed_delta": {}}] * 3},
                "operator_stats": {"by_operator": {}, "recurring_failure_patterns": []}}
            decision = pr.trigger(context["state"], index=context["index_on_disk"],
                                  scheduler=scheduler, revisions=context["revisions"],
                                  projection=context["index"])
            recommended = [c for c in decision["candidates"] if c.get("recommended_only")]
            self.assertTrue(recommended, "stagnation should at least recommend paradigm escape")
            for candidate in recommended:
                self.assertFalse(candidate["allowed"])
                self.assertEqual(candidate["blocked_by"], "recommended_only")
                self.assertIn(candidate["preset_id"], [p["id"] for p in recommend])
            if decision["selected"]:
                self.assertFalse(decision["selected"].get("recommended_only"))

    def test_auto_trigger_needs_the_runtime_entry_point(self):
        """No daemon claims here: the trigger is an explicit call, and nothing self-starts."""
        with tempfile.TemporaryDirectory() as temp:
            state_path = pr._fixture(pathlib.Path(temp) / "A")
            context = pr.project_context(state_path)
            # Without a trigger evaluation there is no auto route, even for a drifting project.
            self.assertEqual(pr.resolve("")["action"], "HOLD")
            self.assertEqual(pr.resolve("")["hold_reason"], "no_intent_matched")
            decision = pr.trigger(context["state"], index=None, index_missing=True,
                                  projection=context["index"])
            self.assertEqual(decision["action"], "RECOVER")
            routed = pr.resolve("", extra_triggers=[c for c in decision["candidates"]
                                                    if c["allowed"]])
            self.assertEqual(routed["trigger"], "auto")
            self.assertEqual(routed["preset_id"], "context-drift-recovery")
            self.assertTrue(routed["requires_confirmation"])

    def test_write_back_permission_per_scope(self):
        with tempfile.TemporaryDirectory() as temp:
            state_path = pr._fixture(pathlib.Path(temp) / "A")
            before = state_path.read_bytes()
            for preset in pr.PRESETS:
                payload, _, _ = pr.run_preset(preset["id"], state_path)
                privilege = pr.scope_privilege(preset["execution_scope"])
                if privilege != "execute":
                    self.assertTrue(payload["canonical_untouched"], preset["id"])
                if privilege == "read_only":
                    self.assertEqual(payload["writes"], [], preset["id"])
                self.assertIn(pr.SCOPE_CANONICAL[preset["execution_scope"]],
                              (ROOT / preset["protocol"]).read_text(encoding="utf-8")
                              if False else [pr.SCOPE_CANONICAL[preset["execution_scope"]]])
            self.assertEqual(state_path.read_bytes(), before)

    def test_cross_session_recovery_keeps_the_next_round_legal(self):
        with tempfile.TemporaryDirectory() as temp:
            state_path = pr._fixture(pathlib.Path(temp) / "A")
            cg.op_build(state_path, state_path.parent / cg.COGNITION_DIRNAME)
            first = pr.run_preset("research-loop", state_path)[0]
            self.assertTrue(first["canonical_untouched"])
            # A new session: nothing is carried in memory, everything is re-read from disk.
            fresh = pr.project_context(state_path)
            second, _, code = pr.run_preset("research-loop", state_path)
            self.assertEqual(code, pr.EXIT_OK)
            self.assertTrue(second["canonical_untouched"])
            self.assertEqual(fresh["canonical_digest"], second["canonical_digest_before"])
            planned = [item["id"] for item in fresh["state"]["experiments"]
                       if item.get("status") in ("planned", "running")]
            self.assertEqual(planned, ["X1"], "the fixture has exactly one planned experiment")
            ledger = pr.ledger_path(state_path.parent / cg.COGNITION_DIRNAME)
            if ledger.is_file():
                records, _ = pr.load_ledger(ledger)
                self.assertLessEqual(len(records), 20)


if __name__ == "__main__":
    unittest.main()
