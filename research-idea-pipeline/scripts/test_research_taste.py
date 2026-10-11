#!/usr/bin/env python3
"""test_research_taste.py — Research Taste 的成对偏好验收（方向一致性，不是评分）。

**诚实的边界（请勿过度解读）：**

* 这里的 6 组对照是**专家撰写的场景夹具**，来自架构审查中「更理想的研究者选择」一栏；
  它们**不是**经过人类研究者验证的偏好数据集，也**不是** TASTE 式的人类评测。
* 验收标准是**方向一致性**：在两组都可执行的候选之间，`compare_candidates` 的偏好是否与
  该场景的期望方向一致，以及它**是否给出了理由、说明不确定性、且不产生任何分数**。
* 真正的「科研品味是否提高」需要独立研究者对**真实领域案例**做成对偏好判断（含分歧记录），
  这部分**尚未进行**（见 .dev/taste/record.md）。
"""

from __future__ import annotations

import unittest

import insight_to_method as i2m


def candidate(cid, *, complexity, simplicity_reason="", predictions=("p",),
              importance="针对社区长期存在的核心问题", insight="机制直接给出干预",
              uncertainty="", boundary=("不升则否定",), importance_reason="",
              decisive=""):
    return {"candidate_id": cid,
            "importance_reason": importance_reason,
            "decisive_experiment": decisive,
            "intervention": {"kind": "objective"},
            "how_it_addresses": importance,
            "mechanism_basis": insight,
            "structural_difference": "d",
            "minimal_implementation_complexity": complexity,
            "why_not_simpler": simplicity_reason,
            "expected_benefit": "b", "resource_cost": complexity,
            "failure_boundary": list(boundary),
            "falsifiable_predictions": list(predictions),
            "distinctive_mechanism": cid + "-m",
            "mathematical_formulation": "L-" + cid,
            "main_uncertainty": uncertainty}


#: (场景, 期望更优的候选 id, 一句理由)
CASES = (
    ("大量新消融 vs 一个有机制动机的方法",
     "M-method",
     "证据已足够时优先实现并验证方法，而不是继续增加消融"),
    ("复杂模块小收益 vs 简洁干预有明确解释",
     "M-simple",
     "证据相当时优先简洁、自然、能解释「为何不更简单」的方案"),
    ("结构距离很大的跨域类比 vs 直击核心问题的小改动",
     "M-direct",
     "不迷信结构距离，比较实际科学价值"),
    ("性能改善但无机制支持 vs 机制清晰但性能一般",
     "M-mechanism",
     "接受性能事实的同时优先有机制依据的贡献"),
    ("性能未超 SOTA 但发现重要失效边界",
     "M-boundary",
     "失效边界具有独立科学价值，不盲目淘汰"),
    ("主锚点未达标但方法有真实进展 vs 改写解释",
     "M-progress",
     "有真实进展时继续合理迭代，不偷换成功条件"),
)


def pair(index):
    """Two *executable* candidates; the expected preference follows from the taste axes."""
    cases = {
        0: (candidate("M-ablate", complexity="low", predictions=("p1", "p2", "p3"),
                      importance="继续细分归因"),
            candidate("M-method", complexity="low", predictions=("关键判别预测",),
                      importance="针对社区真正关心的核心问题",
                      importance_reason="该局限长期限制社区可复现性",
                      decisive="一个关键判别实验即可区分作用与替代解释")),
        1: (candidate("M-complex", complexity="high"),
            candidate("M-simple", complexity="low",
                      simplicity_reason="单个重加权项即可解释，无需额外模块")),
        2: (candidate("M-analogy", complexity="high", importance="跨域类比带来的结构差异"),
            candidate("M-direct", complexity="low", importance="直击核心问题的单一改动")),
        3: (candidate("M-perf", complexity="medium", insight=""),
            candidate("M-mechanism", complexity="medium",
                      insight="机制给出明确可检验的干预方向",
                      simplicity_reason="只改目标函数一项",
                      importance_reason="机制结论可迁移到同类长尾问题",
                      decisive="机制预测与性能同时被检验")),
        4: (candidate("M-sota", complexity="high"),
            candidate("M-boundary", complexity="low",
                      importance="刻画重要失效边界，独立于 SOTA",
                      importance_reason="失效边界改变了后续方法设计的边界条件",
                      decisive="边界实验可独立于 SOTA 判定")),
        5: (candidate("M-narrative", complexity="low", predictions=("解释性结论",),
                      importance="改写解释"),
            candidate("M-progress", complexity="low",
                      predictions=("可判别的验证结果",),
                      importance="在真实进展上继续迭代",
                      importance_reason="已有可归属的验证进展",
                      decisive="下一轮判别实验直接检验进展")),
    }
    return cases[index]


class TestResearchTastePreference(unittest.TestCase):
    def test_six_scenarios_prefer_the_better_research_choice(self):
        for index, (name, expected, reason) in enumerate(CASES):
            with self.subTest(scenario=name):
                left, right = pair(index)
                verdict = i2m.compare_candidates([left, right])
                self.assertTrue(verdict["compared"], verdict)
                self.assertEqual(verdict["preference"], expected,
                                 f"{name}: {verdict['reasons']}")

    def test_a_preference_is_reasoned_and_never_scored(self):
        for index, (name, _, _) in enumerate(CASES):
            with self.subTest(scenario=name):
                verdict = i2m.compare_candidates(list(pair(index)))
                for axis in i2m.TASTE_AXES:
                    self.assertIn(axis, verdict["axes"])
                self.assertTrue(verdict["reasons"], verdict)
                self.assertTrue(verdict["uncertainty"], verdict)
                self.assertIn("不是分数", verdict["note"])
                for banned in ("score", "weight", "rank_score", "total"):
                    self.assertNotIn(banned, verdict)

    def test_a_single_candidate_is_not_compared_against_a_copy(self):
        solo = candidate("M-only", complexity="low")
        verdict = i2m.compare_candidates([solo])
        self.assertFalse(verdict["compared"])
        self.assertEqual(verdict["preference"], "M-only")
        self.assertIn("不做比较", verdict["note"])

    def test_one_candidate_is_legal_when_the_reason_is_stated(self):
        solo = candidate("M-only", complexity="low")
        solo["single_candidate_justification"] = "机制只指向一种自然干预"
        self.assertEqual(i2m.synthesis_errors({}, {"verdict": i2m.VERDICT_HYPOTHESIS},
                                              [solo]), [])
        self.assertTrue(i2m._rules(i2m.synthesis_errors(
            {}, {"verdict": i2m.VERDICT_HYPOTHESIS}, [dict(solo, single_candidate_justification="")])))

    def test_alternative_routes_are_kept_not_deleted(self):
        """Preferring A must not remove B: the preference is advice over a retained portfolio."""
        left, right = pair(1)
        verdict = i2m.compare_candidates([left, right])
        self.assertEqual(verdict["preference"], "M-simple")
        self.assertIn("M-complex", verdict["alternatives"])

    def test_the_exploration_stage_uses_a_lightweight_sketch(self):
        sketch = {"problem": "长尾召回不足", "insight": "头部主导梯度",
                  "intervention": "样本层级重加权", "falsifier": "召回不升"}
        self.assertFalse(i2m.method_sketch_errors(sketch))
        self.assertTrue(i2m._rules(i2m.method_sketch_errors({"problem": "只有问题"})))


if __name__ == "__main__":
    unittest.main()
