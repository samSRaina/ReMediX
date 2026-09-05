"""Tests for the configurable ReMediX scoring policies (spec v2).

Runs under pytest OR standalone:  python -m tests.test_scoring_policies
No network required — CREEDS consensus is monkeypatchable via the injected
lookup, and aggregated targets are synthetic fixtures.
"""

from __future__ import annotations

import math
import os
import sys
import unittest
from unittest import mock
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.utils.scoring_policies import ScoringPolicies  # noqa: E402
from src.utils import remedix_scoring  # noqa: E402


def measurements(values_nm, activity_type="IC50"):
    """Build synthetic ChEMBLClient-style measurements."""
    out = []
    for v in values_nm:
        m = {"activity_type": activity_type.upper(), "standard_type": activity_type}
        if v is not None:
            m["activity_value_nm"] = v
        out.append(m)
    return out


class TestStrengthModels(unittest.TestCase):
    """Step 9: Pharmacological Activity Strength formulas."""

    def setUp(self):
        self.policies = ScoringPolicies()  # spec v2 defaults

    def test_log_ramp_anchors(self):
        f = lambda nm: remedix_scoring._activity_strength_from_nm(nm, self.policies)[0]
        self.assertAlmostEqual(f(1.0), 1.0, places=6)
        self.assertAlmostEqual(f(10.0), 1.0, places=6)  # historical crash point
        self.assertAlmostEqual(f(100.0), 1 - (2 - 1) / 3, places=6)   # 2/3
        self.assertAlmostEqual(f(1000.0), 1 - (3 - 1) / 3, places=6)   # 1/3
        self.assertAlmostEqual(f(10000.0), 0.0, places=6)
        self.assertAlmostEqual(f(100000.0), 0.0, places=6)  # clamped below 0

    def test_log_ramp_monotone_nonincreasing(self):
        values = [1, 2, 5, 9, 10, 15, 50, 100, 300, 999, 1000, 5000, 10000, 100000]
        strengths = [remedix_scoring._activity_strength_from_nm(v, self.policies)[0] for v in values]
        for a, b in zip(strengths, strengths[1:]):
            self.assertGreaterEqual(a, b - 1e-12)

    def test_legacy_model_never_crashes(self):
        policies = ScoringPolicies(activity_strength_model="legacy_inverse_log")
        # 10 nM was the exact ZeroDivisionError point of the old formula.
        strength, defaulted = remedix_scoring._activity_strength_from_nm(10.0, policies)
        self.assertEqual(strength, 1.0)
        self.assertFalse(defaulted)
        # Sub-10 nM values no longer produce negative pre-clip strengths.
        for nm in (0.001, 0.1, 5.0, 9.999):
            s, _ = remedix_scoring._activity_strength_from_nm(nm, policies)
            self.assertTrue(0.0 <= s <= 1.0, f"strength out of range for {nm} nM: {s}")

    def test_legacy_anchors_match_old_behaviour(self):
        policies = ScoringPolicies(activity_strength_model="legacy_inverse_log")
        f = lambda nm: remedix_scoring._activity_strength_from_nm(nm, policies)[0]
        self.assertAlmostEqual(f(100.0), 1.0, places=6)
        self.assertAlmostEqual(f(1000.0), 0.5, places=6)
        self.assertAlmostEqual(f(10000.0), 1 / 3, places=6)

    def test_missing_value_policy(self):
        # Missing / non-positive nM -> policy default (0.5), flagged defaulted.
        strength, defaulted = remedix_scoring._activity_strength_from_nm(None, self.policies)
        self.assertEqual(strength, 0.5)
        self.assertTrue(defaulted)
        strength, defaulted = remedix_scoring._activity_strength_from_nm(0.0, self.policies)
        self.assertEqual(strength, 0.5)
        self.assertTrue(defaulted)
        # Configurable default.
        policies = ScoringPolicies(missing_activity_strength=0.9)
        strength, _ = remedix_scoring._activity_strength_from_nm(None, policies)
        self.assertEqual(strength, 0.9)


class TestAssayAggregation(unittest.TestCase):
    """Step 3: median/min/mean aggregation per drug-target pair."""

    def test_median_odd_and_even(self):
        policies = ScoringPolicies()  # median default
        rep, count = remedix_scoring._representative_nm(measurements([10, 50, 200]), policies)
        self.assertEqual((rep, count), (50, 3))
        rep, count = remedix_scoring._representative_nm(measurements([10, 50, 200, 1000]), policies)
        self.assertEqual((rep, count), (125.0, 4))  # (50+200)/2

    def test_min(self):
        policies = ScoringPolicies(assay_aggregation="min")
        rep, _ = remedix_scoring._representative_nm(measurements([10, 50, 200, 1000]), policies)
        self.assertEqual(rep, 10)

    def test_mean(self):
        policies = ScoringPolicies(assay_aggregation="mean")
        rep, _ = remedix_scoring._representative_nm(measurements([10, 50, 200, 1000]), policies)
        self.assertAlmostEqual(rep, 315.0)

    def test_invalid_values_ignored(self):
        policies = ScoringPolicies()
        ms = measurements([10, None, 50]) + [
            {"activity_type": "IC50", "standard_type": "IC50", "activity_value_nm": -5},
            {"activity_type": "IC50", "standard_type": "IC50"},  # no value at all
        ]
        rep, count = remedix_scoring._representative_nm(ms, policies)
        self.assertEqual((rep, count), (30.0, 2))

    def test_no_valid_values(self):
        policies = ScoringPolicies()
        rep, count = remedix_scoring._representative_nm(measurements([None, None]), policies)
        self.assertIsNone(rep)
        self.assertEqual(count, 0)


class TestPolicyValidation(unittest.TestCase):
    def test_illegal_values_raise(self):
        with self.assertRaises(ValueError):
            ScoringPolicies(assay_aggregation="mode")
        with self.assertRaises(ValueError):
            ScoringPolicies(activity_strength_model="sqrt")
        with self.assertRaises(ValueError):
            ScoringPolicies(missing_activity_strength=1.5)
        with self.assertRaises(ValueError):
            ScoringPolicies(missing_activity_strength=-0.1)
        with self.assertRaises(ValueError):
            ScoringPolicies(ambiguous_policy="drop")

    def test_from_env_applies_and_defaults(self):
        env = {
            "REMEDIX_SCORING_ASSAY_AGGREGATION": "min",
            "REMEDIX_SCORING_STRENGTH_MODEL": "legacy_inverse_log",
            "REMEDIX_SCORING_MISSING_ACTIVITY_STRENGTH": "0.25",
            "REMEDIX_SCORING_AMBIGUOUS_POLICY": "exclude",
        }
        with mock.patch.dict(os.environ, env):
            policies = ScoringPolicies.from_env()
        self.assertEqual(policies.assay_aggregation, "min")
        self.assertEqual(policies.activity_strength_model, "legacy_inverse_log")
        self.assertEqual(policies.missing_activity_strength, 0.25)
        self.assertEqual(policies.ambiguous_policy, "exclude")
        with mock.patch.dict(os.environ, {}, clear=True):
            policies = ScoringPolicies.from_env()
        self.assertEqual(policies, ScoringPolicies())

    def test_overrides(self):
        base = ScoringPolicies()
        overridden = base.with_overrides(assay_aggregation="mean", missing_activity_strength=0.1)
        self.assertEqual(overridden.assay_aggregation, "mean")
        self.assertEqual(overridden.missing_activity_strength, 0.1)
        self.assertEqual(overridden.activity_strength_model, base.activity_strength_model)
        self.assertEqual(overridden.ambiguous_policy, base.ambiguous_policy)

    def test_frozen(self):
        policies = ScoringPolicies()
        with self.assertRaises(Exception):
            policies.assay_aggregation = "min"

    def test_describe_shape(self):
        d = ScoringPolicies().describe()
        self.assertEqual(d["assay_aggregation"], "median")
        self.assertEqual(d["activity_strength_model"], "log_ramp")
        self.assertIn("activity_strength_formula", d)
        self.assertEqual(d["missing_activity_strength"], 0.5)
        self.assertEqual(d["ambiguous_policy"], "unresolved")


class TestEndToEndScoring(unittest.TestCase):
    """Steps 6-21 against a synthetic fixture with hand-computed expectations."""

    def setUp(self):
        # Disease consensus: PTGS2 UP (3U/1D -> DC 0.5), NFE2L2 DOWN (0U/2D -> DC 1.0),
        # BRCA1 ambiguous (2U/2D -> DC 0).
        self.disease_consensus = {
            "disease": "fixture disease",
            "source_entry_count": 3,
            "gene_records": [
                {"gene": "PTGS2", "U": 3, "D": 1, "disease_direction": "UP", "dc": 0.5},
                {"gene": "NFE2L2", "U": 0, "D": 2, "disease_direction": "DOWN", "dc": 1.0},
                {"gene": "BRCA1", "U": 2, "D": 2, "disease_direction": "AMBIGUOUS", "dc": 0.0},
                {"gene": "TP53", "U": 4, "D": 0, "disease_direction": "UP", "dc": 1.0},  # unmatched
            ],
            "disease_gene_set": ["PTGS2", "NFE2L2", "BRCA1", "TP53"],
            "disease_total": 4,
        }

        # Drug targets (aspirin-like): PTGS2 inhibitor w/ values, NFE2L2
        # activator with NO valid nM, BRCA1 ambiguous-direction gene w/ values.
        self.aggregated_targets = [
            {
                "gene_symbol": "PTGS2",
                "uniprot_ids": ["P23219"],
                "target_chembl_ids": ["CHEMBL230"],
                "target_names": ["Prostaglandin G/H synthase 1"],
                "target_types": ["SINGLE PROTEIN"],
                "target_organisms": ["Homo sapiens"],
                "protein_target_classifications": [],
                "measurements": measurements([10, 50, 200], activity_type="IC50"),
                "activity_summary": {},
                "measurement_count": 3,
            },
            {
                "gene_symbol": "NFE2L2",
                "uniprot_ids": ["Q16236"],
                "target_chembl_ids": ["CHEMBL612545"],
                "target_names": ["Nuclear factor erythroid 2-related factor 2"],
                "target_types": ["SINGLE PROTEIN"],
                "target_organisms": ["Homo sapiens"],
                "protein_target_classifications": [],
                "measurements": measurements([None], activity_type="AC50"),
                "activity_summary": {},
                "measurement_count": 1,
            },
            {
                "gene_symbol": "BRCA1",
                "uniprot_ids": ["P38398"],
                "target_chembl_ids": ["CHEMBL4071"],
                "target_names": ["Breast cancer type 1 susceptibility protein"],
                "target_types": ["SINGLE PROTEIN"],
                "target_organisms": ["Homo sapiens"],
                "protein_target_classifications": [],
                "measurements": measurements([100], activity_type="IC50"),
                "activity_summary": {},
                "measurement_count": 1,
            },
        ]

    def _score(self, policies=None):
        with mock.patch.object(
            remedix_scoring.creeds_client,
            "build_disease_direction_consensus",
            return_value=self.disease_consensus,
        ):
            return remedix_scoring.calculate_remedix_score(
                self.aggregated_targets, "fixture disease", policies
            )

    def test_spec_defaults(self):
        result = self._score()
        # Policies echoed.
        self.assertEqual(result["policies"]["assay_aggregation"], "median")
        self.assertEqual(result["policies"]["activity_strength_model"], "log_ramp")

        records = {r["gene"]: r for r in result["gene_records"]}

        # PTGS2: UP + INHIBITION -> BENEFICIAL. Median 50 nM ->
        # strength 1 - (log10(50) - 1)/3 = 0.76701.
        ptgs2 = records["PTGS2"]
        self.assertEqual(ptgs2["classification"], "BENEFICIAL")
        self.assertEqual(ptgs2["representative_value_nm"], 50)
        self.assertEqual(ptgs2["representative_aggregation"], "median")
        self.assertEqual(ptgs2["valid_measurement_count"], 3)
        self.assertFalse(ptgs2["activity_strength_defaulted"])
        expected_strength = 1 - (math.log10(50) - 1) / 3
        self.assertAlmostEqual(ptgs2["activity_strength"], expected_strength, places=4)
        # contribution = 0.5 * (0.7 + 0.3 * 0.76701) = 0.5 * 0.93010 = 0.46505
        self.assertAlmostEqual(ptgs2["gene_contribution"], 0.5 * (0.7 + 0.3 * expected_strength), places=4)
        self.assertEqual(ptgs2["activity_type"], ["IC50"])  # original ChEMBL casing

        # NFE2L2: DOWN + ACTIVATION -> BENEFICIAL. No valid nM -> 0.5 default.
        nfe2l2 = records["NFE2L2"]
        self.assertEqual(nfe2l2["classification"], "BENEFICIAL")
        self.assertTrue(nfe2l2["activity_strength_defaulted"])
        self.assertEqual(nfe2l2["activity_strength"], 0.5)
        self.assertIsNone(nfe2l2["representative_value_nm"])
        # contribution = 1.0 * (0.7 + 0.3 * 0.5) = 0.85
        self.assertAlmostEqual(nfe2l2["gene_contribution"], 0.85, places=4)

        # BRCA1: ambiguous -> UNRESOLVED, contribution 0, row PRESENT.
        brca1 = records["BRCA1"]
        self.assertEqual(brca1["classification"], "UNRESOLVED")
        self.assertEqual(brca1["gene_contribution"], 0.0)
        self.assertEqual(brca1["disease_direction"], "AMBIGUOUS")

        # Aggregation: B = 0.46505 + 0.85 = 1.31505, H = 0, total = 4.
        expected_b = 0.5 * (0.7 + 0.3 * (1 - (math.log10(50) - 1) / 3)) + 0.85
        self.assertAlmostEqual(result["beneficial_signal"], expected_b, places=4)
        self.assertAlmostEqual(result["harmful_signal"], 0.0, places=4)
        self.assertAlmostEqual(result["net_therapeutic_signal"], expected_b, places=4)
        self.assertAlmostEqual(result["benefit_coverage"], expected_b / 4, places=4)
        self.assertAlmostEqual(result["raw_remedix_score"], 100 * expected_b / 4, places=4)
        self.assertAlmostEqual(result["remedix_score"], 100 * expected_b / 4, places=4)
        self.assertEqual(result["matched_target_count"], 3)
        self.assertEqual(result["target_coverage_percent"], 75.0)

        # Traceability matrix has all three matched genes (unresolved kept).
        self.assertEqual(len(result["gene_records"]), 3)

    def test_exclude_ambiguous_policy(self):
        policies = ScoringPolicies(ambiguous_policy="exclude")
        result = self._score(policies)
        genes = {r["gene"] for r in result["gene_records"]}
        self.assertNotIn("BRCA1", genes)
        # Still counted as matched target for coverage.
        self.assertEqual(result["matched_target_count"], 3)
        # Scores identical (BRCA1 contributed 0 anyway).
        expected_b = 0.5 * (0.7 + 0.3 * (1 - (math.log10(50) - 1) / 3)) + 0.85
        self.assertAlmostEqual(result["beneficial_signal"], expected_b, places=4)

    def test_min_policy_changes_contribution(self):
        policies = ScoringPolicies(assay_aggregation="min")
        result = self._score(policies)
        ptgs2 = {r["gene"]: r for r in result["gene_records"]}["PTGS2"]
        self.assertEqual(ptgs2["representative_value_nm"], 10)
        self.assertEqual(ptgs2["representative_aggregation"], "min")
        # 10 nM -> log_ramp strength 1.0 -> contribution 0.5 * (0.7+0.3) = 0.5
        self.assertAlmostEqual(ptgs2["gene_contribution"], 0.5, places=4)

    def test_legacy_model_reproduces_old_math(self):
        policies = ScoringPolicies(
            activity_strength_model="legacy_inverse_log", assay_aggregation="min"
        )
        result = self._score(policies)
        records = {r["gene"]: r for r in result["gene_records"]}
        # PTGS2 min 10 nM under legacy -> floored to 1.0 (old formula crashed here).
        self.assertEqual(records["PTGS2"]["activity_strength"], 1.0)
        # NFE2L2: legacy missing -> 0.5 default, contribution 0.85.
        self.assertAlmostEqual(records["NFE2L2"]["gene_contribution"], 0.85, places=4)

    def test_policies_echoed_in_response(self):
        policies = ScoringPolicies(assay_aggregation="mean")
        result = self._score(policies)
        self.assertEqual(result["policies"]["assay_aggregation"], "mean")
        self.assertIn("gene_contribution_formula", result["policies"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
