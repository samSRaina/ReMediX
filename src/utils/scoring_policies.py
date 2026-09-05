"""Configurable scoring policies for the ReMediX 21-step pipeline.

The four architectural decisions that were left open in the pipeline spec are
resolved here as EXPLICIT, CONFIGURABLE policies with traceability:

1. Assay aggregation (Step 3): how multiple activity measurements for one
   drug-target pair collapse into one representative value.
   -> ``assay_aggregation``: "median" (spec default) | "min" | "mean"

2. Missing activity values (Step 9): strength used when a confirmed
   interaction has no quantifiable nM value.
   -> ``missing_activity_strength``: 0.5 (spec default), any float in [0, 1]

3. Ambiguous directions (Step 8): what happens to genes with U == D.
   -> ``ambiguous_policy``: "unresolved" (spec default: keep in the matrix,
      classification UNRESOLVED, contribution 0) | "exclude" (drop the row
      from the gene matrix; it still counts as a matched target)

4. Activity strength model (Step 9): the bounded log transformation.
   -> ``activity_strength_model``: "log_ramp" (spec default,
      max(0, min(1, 1 - (log10(nM) - 1) / 3))) | "legacy_inverse_log"
      (the original 1 / (1 + log10(nM / 100)) formula, kept for A/B
      comparisons, hardened so its 10 nM zero-division can never crash)

Defaults follow the updated pipeline spec. Every scoring response embeds
``ScoringPolicies.describe()`` so any consumer can see exactly which policies
produced the numbers.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, replace

# Environment variable names for deployment-level defaults.
ENV_ASSAY_AGGREGATION = "REMEDIX_SCORING_ASSAY_AGGREGATION"
ENV_STRENGTH_MODEL = "REMEDIX_SCORING_STRENGTH_MODEL"
ENV_MISSING_ACTIVITY_STRENGTH = "REMEDIX_SCORING_MISSING_ACTIVITY_STRENGTH"
ENV_AMBIGUOUS_POLICY = "REMEDIX_SCORING_AMBIGUOUS_POLICY"

VALID_AGGREGATIONS = ("median", "min", "mean")
VALID_STRENGTH_MODELS = ("log_ramp", "legacy_inverse_log")
VALID_AMBIGUOUS_POLICIES = ("unresolved", "exclude")


def _validate(
    assay_aggregation: str,
    activity_strength_model: str,
    missing_activity_strength: float,
    ambiguous_policy: str,
) -> None:
    if assay_aggregation not in VALID_AGGREGATIONS:
        raise ValueError(
            f"assay_aggregation must be one of {VALID_AGGREGATIONS}, got {assay_aggregation!r}"
        )
    if activity_strength_model not in VALID_STRENGTH_MODELS:
        raise ValueError(
            f"activity_strength_model must be one of {VALID_STRENGTH_MODELS}, got {activity_strength_model!r}"
        )
    if not isinstance(missing_activity_strength, (int, float)) or isinstance(missing_activity_strength, bool):
        raise ValueError(f"missing_activity_strength must be numeric, got {missing_activity_strength!r}")
    if not 0.0 <= float(missing_activity_strength) <= 1.0:
        raise ValueError(
            f"missing_activity_strength must be within [0, 1], got {missing_activity_strength!r}"
        )
    if ambiguous_policy not in VALID_AMBIGUOUS_POLICIES:
        raise ValueError(
            f"ambiguous_policy must be one of {VALID_AMBIGUOUS_POLICIES}, got {ambiguous_policy!r}"
        )


@dataclass(frozen=True)
class ScoringPolicies:
    """The four policy knobs of the ReMediX scoring pipeline (spec v2 defaults)."""

    assay_aggregation: str = "median"
    activity_strength_model: str = "log_ramp"
    missing_activity_strength: float = 0.5
    ambiguous_policy: str = "unresolved"

    def __post_init__(self) -> None:
        _validate(
            self.assay_aggregation,
            self.activity_strength_model,
            self.missing_activity_strength,
            self.ambiguous_policy,
        )

    @classmethod
    def from_env(cls) -> "ScoringPolicies":
        """Build policies from deployment environment variables (spec defaults
        apply for anything unset or blank; illegal values raise ValueError)."""
        kwargs: dict = {}
        raw_agg = os.getenv(ENV_ASSAY_AGGREGATION, "").strip()
        if raw_agg:
            kwargs["assay_aggregation"] = raw_agg
        raw_model = os.getenv(ENV_STRENGTH_MODEL, "").strip()
        if raw_model:
            kwargs["activity_strength_model"] = raw_model
        raw_missing = os.getenv(ENV_MISSING_ACTIVITY_STRENGTH, "").strip()
        if raw_missing:
            kwargs["missing_activity_strength"] = float(raw_missing)
        raw_amb = os.getenv(ENV_AMBIGUOUS_POLICY, "").strip()
        if raw_amb:
            kwargs["ambiguous_policy"] = raw_amb
        return cls(**kwargs)

    def with_overrides(
        self,
        assay_aggregation: str | None = None,
        activity_strength_model: str | None = None,
        missing_activity_strength: float | None = None,
        ambiguous_policy: str | None = None,
    ) -> "ScoringPolicies":
        """Apply per-request overrides (None = keep current value)."""
        return replace(
            self,
            assay_aggregation=assay_aggregation if assay_aggregation is not None else self.assay_aggregation,
            activity_strength_model=activity_strength_model if activity_strength_model is not None else self.activity_strength_model,
            missing_activity_strength=missing_activity_strength if missing_activity_strength is not None else self.missing_activity_strength,
            ambiguous_policy=ambiguous_policy if ambiguous_policy is not None else self.ambiguous_policy,
        )

    def describe(self) -> dict:
        """Plain-dict policy snapshot embedded into every scoring response."""
        formulas = {
            "log_ramp": "max(0, min(1, 1 - (log10(Activity_nM) - 1) / 3))",
            "legacy_inverse_log": "1 / (1 + log10(Activity_nM / 100)), denominator <= 0 -> 1.0",
        }
        return {
            "assay_aggregation": self.assay_aggregation,
            "activity_strength_model": self.activity_strength_model,
            "activity_strength_formula": formulas[self.activity_strength_model],
            "missing_activity_strength": float(self.missing_activity_strength),
            "ambiguous_policy": self.ambiguous_policy,
            "gene_contribution_formula": "DC * (0.7 + 0.3 * ActivityStrength)",
            "source": "ReMediX 21-step pipeline spec v2",
        }
