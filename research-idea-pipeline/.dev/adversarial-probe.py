"""Before/after adversarial probe: the previous module (5279b1f) vs the current one."""
import copy, importlib.util, json, sys
from pathlib import Path

SCRIPTS = Path('/home/lenovo/code/myproj/skills-dev/main/research-idea-pipeline/scripts')
sys.path.insert(0, str(SCRIPTS))
import cognition as cg, evidence_outcome as eo, structural_equivalence_check as sec

def load_old():
    spec = importlib.util.spec_from_file_location('pc_old', '/tmp/oldmod/prediction_compare_old.py')
    mod = importlib.util.module_from_spec(spec); sys.modules['pc_old'] = mod
    spec.loader.exec_module(mod)
    return mod

OLD = load_old()
import prediction_compare as NEW

def src(content, location="results/A/X1/summary.json"):
    return {"kind": "result", "location": location, "content": content, "digest": eo.digest(content)}

def base_state(branch=False, exclusive=True, outcome_analysis=True, evidence_supports=("C1",),
               evidence_prediction_ref=None, evidence_valid=True, claim_status="partially-supported"):
    state = {
        "state_version": 6,
        "contract": {"goal": "判断两个机制中哪一个解释目标现象", "primary_anchor": "phenomenon",
                     "constraints": [], "resources": [],
                     "provisional_anchor_rationale": "先形式化", "out_of_scope": []},
        "claims": [{"id": "C1", "statement": "机制 A 解释目标现象", "parent": None, "subclaims": [],
                    "status": claim_status, "supporting_evidence": ["E1"], "refuting_evidence": [],
                    "nearest_alternative": "机制 B", "falsifier": "干预后现象消失", "scope": "数据集 A",
                    "known_flaws": [], "depends_on": [],
                    "validity": {"status": "valid", "reason": "已按预注册写入", "since_state_version": 5}}],
        "evidence": [{"id": "E1", "kind": "experiment", "supports": list(evidence_supports),
                      "contradicts": [], "strength": "strong", "scope": "数据集 A",
                      "epistemic_status": "Observed", "source_ref": "X1",
                      "verification_tier": "T2", "depends_on": ["X1"],
                      "validity": {"status": "valid" if evidence_valid else "invalid",
                                   "reason": "X1 done", "since_state_version": 5}}],
        "assumptions": [{"id": "AS1", "statement": "测量无偏", "status": "explicit",
                         "challenged_by": [], "if_false": "不可归因", "depends_on": [],
                         "validity": {"status": "valid", "reason": "仍被接受", "since_state_version": 4}}],
        "hypotheses": [{"id": "H1", "statement": "机制 A",
                        "structural_signature": {"assumption_distance": 1, "formulation_distance": 1,
                                                 "representation_distance": 0, "theory_lens_distance": 1,
                                                 "mechanism_distance": 2},
                        "novelty_source": "迁移", "theory_lens": "逆问题", "nearest_prior": "LIT1",
                        "falsifier": "干预无效", "expected_information_gain": 0.4, "status": "elite",
                        "niche": "mechanism-shift", "island": "P2", "generation": 0,
                        "operator": "assumption_breaker", "parents": [], "depends_on": [],
                        "validity": {"status": "valid", "reason": "未推翻", "since_state_version": 4},
                        "scientific_scope": None}],
        "experiments": [{"id": "X1", "parent": None, "stage": "X3", "claim_targeted": ["C1"],
                         "alternative_targeted": ["ALT-1"], "code_commit": "abc", "data_split": "A/train",
                         "seed": 0, "metric": "落差", "result": "落差 0.8", "interpretation": "初步",
                         "unexpected": [], "known_flaws": [], "next_branches": [], "status": "done",
                         "preregistration": {"frozen_at_state_version": 5, "outcomes": [
                             {"id": "O1", "observation": "落差 ≥ 0.5",
                              "criterion": {"kind": "quantitative", "quantity": "落差（dB）",
                                            "expected_range": [0.5, 3.0], "tolerance": 0.1},
                              "update": [{"target": "C1", "op": "strengthen"}]},
                             {"id": "O2", "observation": "落差 < 0.1",
                              "criterion": {"kind": "quantitative", "quantity": "落差（dB）",
                                            "expected_range": [0.0, 0.1 if exclusive else 0.6],
                                            "tolerance": 0.1},
                              "update": [{"target": "C1", "op": "retain-with-alternative"}]}]},
                         "result_at_state_version": 6, "depends_on": [],
                         "validity": {"status": "valid", "reason": "按预注册写入", "since_state_version": 6},
                         "outcome_analysis": None, "execution_protocol": None},
                        {"id": "X2", "parent": "X1", "stage": "X3", "claim_targeted": ["C1"],
                         "alternative_targeted": ["ALT-1"], "code_commit": "TBD", "data_split": "A/fixed",
                         "seed": 0, "metric": "落差变化", "result": "", "interpretation": "尚未运行",
                         "unexpected": [], "known_flaws": [], "next_branches": [], "status": "planned",
                         "preregistration": None, "result_at_state_version": None, "depends_on": ["X1"],
                         "validity": {"status": "pending", "reason": "尚未运行", "since_state_version": 5},
                         "outcome_analysis": None, "execution_protocol": None}],
        "literature": [{"id": "LIT1", "ref": "[A, V/2024]", "relation": "shares-structure",
                        "depends_on": [], "validity": {"status": "valid", "reason": "未撤回",
                                                       "since_state_version": 0}}],
        "failures": [], "uncertainties": [], "assurance": [], "repairs": [],
    }
    if branch:
        st = state["experiments"][0]["preregistration"]
        st["outcome_mode"] = "branch"
        st["branch_rule"] = {"selector": {"kind": "result", "location": "results/A/X1/summary.json"},
                             "quantity": "落差（dB）", "branches": ["O1", "O2"]}
    if outcome_analysis:
        content = "落差 0.8 dB"
        state["experiments"][0]["outcome_analysis"] = {
            "packet": {"schema": "evidence-result@1", "experiment_id": "X1",
                       "experiment_digest": "sha256:x", "execution_status": "completed",
                       "result_summary": content,
                       "sources": [{"id": "S1", "kind": "result",
                                    "location": "results/A/X1/summary.json",
                                    "content": content, "digest": eo.digest(content)}],
                       "observations": [{"id": "OBS1", "statement": content, "scope": "数据集 A",
                                         "source_ids": ["S1"]}]},
            "analysis": {"schema": "evidence-outcome-analysis@1", "id": "AN1", "experiment_id": "X1",
                         "verification_tier": "T2", "outcome": "POSITIVE_EVIDENCE",
                         "claim_updates": [{"id": "C1", "direction": "positive",
                                            "identification": "PASS", "new_status": "SUPPORTED",
                                            "evidence": ["OBS1"], "scope": "数据集 A"}]},
            "audit": None}
    if evidence_prediction_ref:
        state["evidence"][0]["prediction_ref"] = evidence_prediction_ref
    return state

def packet(complete=True, observed="O1", location="results/A/X1/summary.json", digest_ok=True,
           validity="VALID", value=0.8, source=True):
    outs = []
    first = {"id": observed or "O1", "value": value}
    if source:
        s = src("落差 %.1f dB" % value, location)
        if not digest_ok:
            s["digest"] = "0" * 64
        first["source"] = s
    outs.append(first)
    if complete:
        second = {"id": "O2" if (observed or "O1") == "O1" else "O1", "value": 0.05,
                  "source": src("落差 0.05 dB", location)}
        if not digest_ok:
            second["source"]["digest"] = "0" * 64
        outs.append(second)
    p = {"schema": NEW.SCHEMA_OBSERVATION, "experiment_id": "X1",
         "execution": {"status": "completed", "validity": validity}, "outcomes": outs}
    if observed:
        p["observed_outcome"] = observed
    return p

def card(state, ref="X1:O1", packet_obj=None, declare="evidence_supported_insight",
         with_evidence=True, experiment_ref="X1"):
    pred = {"ref": ref, "statement": "落差 ≥ 0.5", "experiment_ref": experiment_ref}
    if packet_obj is not None:
        pred["observation"] = packet_obj
        pred["observation_digest"] = cg.digest_of(packet_obj)
    refs = {"claims": ["C1"], "hypotheses": ["H1"], "experiments": ["X1"]}
    if with_evidence:
        refs["evidence"] = ["E1"]
    return {"_schema": NEW.SCHEMA_INSIGHT, "id": "IC1", "at_state_version": 6, "actor": "R6",
            "observation": "x", "existing_mechanism": "M1", "challenged_assumption": "AS1",
            "proposed_mechanism": "M2", "explanatory_gain": "y", "competing_mechanism": "M1",
            "novel_prediction": pred, "discriminating_intervention": "X1",
            "scope_boundary": "数据集 A", "scientific_implication": "z",
            "refs": refs, "declared_class": declare}

def assurance(state, verdict="formulation-delta", tier="T1", with_ref=True):
    art = sec._selftest_artifact()
    art = dict(art, verdict=verdict)
    entry = {"id": "A1", "target": "H1", "attack_type": "structural-equivalence",
             "verification_tier": tier, "kill_condition": "x", "discriminating_test": "X1"}
    if with_ref:
        entry["audit_ref"] = ".research-idea-pipeline/routes/A/assurance/structural-equivalence/H1.json"
    state["assurance"] = [entry]
    return {"A1": {"artifact": art, "verdict": verdict, "candidate": art.get("candidate"),
                   "source": "<probe>", "violations": []}}

def old_run(state, pkt=None, card_obj=None, audits=None, mode='assess'):
    if mode == 'assess':
        a, _ = OLD.assess_experiment(state, pkt)
        allowed = OLD.evidence_transition_allowed(state, a)[0]
        return {"class": a["outcome_class"], "eligible": a["evidence_eligible"], "allow": allowed}
    d, _ = OLD.classify_insight(card_obj, state)
    return {"class": d}

def new_run(state, pkt=None, card_obj=None, audits=None, mode='assess'):
    if mode == 'assess':
        a, _ = NEW.assess_experiment(state, pkt)
        allowed = NEW.evidence_transition_allowed(state, a)[0]
        return {"class": a["outcome_class"], "eligible": a["evidence_eligible"], "allow": allowed}
    d, _ = NEW.classify_insight(card_obj, state, audits)
    return {"class": d}

CASES = []
def case(name, state_fn, packet_fn=None, card_fn=None, audits_fn=None, mode='assess'):
    st = state_fn()
    pkt = packet_fn() if packet_fn else None
    audits = audits_fn(st) if audits_fn else None
    card_obj = card_fn(st) if card_fn else None
    before = old_run(st, pkt, card_obj, audits, mode)
    after = new_run(st, pkt, card_obj, audits, mode)
    CASES.append((name, before, after))

# --- P0-1
case("A1 2 independent predictions, only O1 submitted",
     lambda: base_state(branch=False),
     lambda: packet(complete=False, observed="O1"))
case("A2 legit frozen branch, one raw observation",
     lambda: base_state(branch=True),
     lambda: packet(complete=False, observed="O1"))
case("A3 branch declared, rule not frozen",
     lambda: base_state(branch=False),
     lambda: packet(complete=False, observed="O1"))
case("A4 declaration conflicts with observation",
     lambda: base_state(branch=True),
     lambda: packet(complete=False, observed="O2", value=0.8))
case("A5 branches not mutually exclusive",
     lambda: base_state(branch=True, exclusive=False),
     lambda: packet(complete=False, observed="O1"))
case("A6 observation source missing",
     lambda: base_state(branch=True),
     lambda: packet(complete=False, observed="O1", source=False))
# --- P0-2
case("A7 source digest mismatch",
     lambda: base_state(branch=True),
     lambda: packet(complete=False, observed="O1", digest_ok=False))
case("A8 selector outside the frozen source",
     lambda: base_state(branch=True),
     lambda: packet(complete=False, observed="O1", location="results/other.json"))
case("A9 execution validity UNKNOWN",
     lambda: base_state(),
     lambda: packet(complete=True, observed=None, validity="UNKNOWN"))
# --- P1
case("A11 T2 evidence bound to another prediction",
     lambda: base_state(evidence_prediction_ref="X1:O2"),
     lambda: packet(complete=True, observed=None),
     lambda st: card(st, ref="X1:O1", packet_obj=packet(complete=True, observed=None)),
     lambda st: assurance(st), mode='insight')
case("A12 assurance present, audit result unknown",
     lambda: base_state(),
     lambda: packet(complete=True, observed=None),
     lambda st: card(st, packet_obj=packet(complete=True, observed=None)),
     lambda st: ({}, assurance(st, with_ref=False))[0], mode='insight')
def audit_map(verdict="formulation-delta"):
    art = dict(sec._selftest_artifact(), verdict=verdict)
    return {"A1": {"artifact": art, "verdict": verdict, "candidate": art.get("candidate"),
                   "source": "<probe>", "violations": []}}


def state_with_tbd_audit():
    st = base_state()
    assurance(st)
    st["assurance"][0]["discriminating_test"] = "TBD"
    return st

case("A13 audit entry with no executable test",
     state_with_tbd_audit,
     lambda: packet(complete=True, observed=None),
     lambda st: card(st, packet_obj=packet(complete=True, observed=None)),
     lambda st: audit_map(), mode='insight')
case("A14 audit finds an equivalent prior",
     lambda: base_state(),
     lambda: packet(complete=True, observed=None),
     lambda st: card(st, packet_obj=packet(complete=True, observed=None)),
     lambda st: assurance(st, verdict="equivalent"), mode='insight')
case("A10 hand-written eligibility flag",
     lambda: base_state(),
     lambda: packet(complete=True, observed=None))
case("A20 fully bound card (positive path)",
     lambda: base_state(),
     lambda: packet(complete=True, observed=None),
     lambda st: card(st, packet_obj=packet(complete=True, observed=None)),
     lambda st: assurance(st), mode='insight')
case("A15 prediction not held (value outside range)",
     lambda: base_state(),
     lambda: None,
     lambda st: card(st, packet_obj=packet(complete=True, observed=None, value=0.2)),
     lambda st: assurance(st), mode='insight')

# A10 is measured directly: a hand-written eligibility flag instead of the gate result.
st = base_state()
pkt = packet(complete=True, observed=None)
old_assessment, _ = OLD.assess_experiment(st, pkt)
new_assessment, _ = NEW.assess_experiment(st, pkt)
forged_old = {k: v for k, v in old_assessment.items() if k != "qualification"}
forged_new = {k: v for k, v in new_assessment.items() if k != "qualification"}
forged_old.update(evidence_eligible=True, evidence_class="QUALIFIED_EVIDENCE",
                  scientific_status="MAY_INFORM_TRANSITION")
forged_new.update(evidence_eligible=True, evidence_class="QUALIFIED_EVIDENCE",
                  scientific_status="MAY_INFORM_TRANSITION")
CASES.append(("A10 hand-written eligibility flag",
              {"class": "forged", "eligible": True,
               "allow": OLD.evidence_transition_allowed(st, forged_old)[0]},
              {"class": "forged", "eligible": True,
               "allow": NEW.evidence_transition_allowed(st, forged_new)[0]}))
CASES = [c for c in CASES if c[0] != "A10 hand-written eligibility flag" or c is CASES[-1]]

print(f"{'case':52s} {'before (5279b1f)':44s} after (current)")
for name, before, after in CASES:
    def fmt(r):
        if 'eligible' in r:
            return f"{r['class']:18s} elig={str(r['eligible']):5s} allow={r['allow']}"
        return r['class']
    print(f"{name:52s} {fmt(before):44s} {fmt(after)}")
