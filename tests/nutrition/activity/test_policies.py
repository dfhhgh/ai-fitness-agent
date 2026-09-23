"""Tests for app.nutrition.activity.policies — activity factor lookup and constants.

Tests cover:
- Every ActivityCategory maps to the exact approved factor
- No unknown category silently maps to sedentary
- Factor lookup is deterministic
- Policy constants are centralized
- Occupation baseline scores
- Exercise intensity weights
- WES upgrade thresholds
- Unknown categories fail explicitly
"""

import pytest

from app.nutrition.activity.activity_policies import (
    ACTIVITY_FACTORS,
    ACTIVITY_POLICY_VERSION,
    INTENSITY_WEIGHTS,
    OCCUPATION_BASELINES,
    WES_UPGRADE_THRESHOLDS,
    get_activity_factor,
)
from app.nutrition.models import (
    ActivityCategory,
    DailyMovement,
    ExerciseIntensity,
    OccupationalActivity,
)


class TestActivityFactors:
    """Verify activity factor values match the approved specification."""

    def test_sedentary_factor(self):
        """SEDENTARY must map to 1.20."""
        assert get_activity_factor(ActivityCategory.SEDENTARY) == 1.20

    def test_light_factor(self):
        """LIGHT must map to 1.35."""
        assert get_activity_factor(ActivityCategory.LIGHT) == 1.35

    def test_moderate_factor(self):
        """MODERATE must map to 1.55."""
        assert get_activity_factor(ActivityCategory.MODERATE) == 1.55

    def test_high_factor(self):
        """HIGH must map to 1.75."""
        assert get_activity_factor(ActivityCategory.HIGH) == 1.75

    def test_all_categories_have_factors(self):
        """Every ActivityCategory must have a defined factor."""
        for cat in ActivityCategory:
            assert cat in ACTIVITY_FACTORS, f"Missing factor for {cat}"

    def test_factors_dict_matches_get_function(self):
        """ACTIVITY_FACTORS dict and get_activity_factor() agree."""
        for cat, factor in ACTIVITY_FACTORS.items():
            assert get_activity_factor(cat) == factor


class TestActivityFactorLookup:
    """Test factor lookup behavior."""

    def test_lookup_is_deterministic(self):
        """Same input always produces same output."""
        results = [get_activity_factor(ActivityCategory.MODERATE) for _ in range(100)]
        assert len(set(results)) == 1

    def test_all_factors_are_positive(self):
        """All factors must be positive."""
        for cat, factor in ACTIVITY_FACTORS.items():
            assert factor > 0, f"Factor for {cat} must be positive, got {factor}"

    def test_all_factors_are_reasonable(self):
        """All factors must be in reasonable range (1.0–2.0)."""
        for cat, factor in ACTIVITY_FACTORS.items():
            assert 1.0 <= factor <= 2.0, (
                f"Factor for {cat} is {factor}, expected 1.0–2.0"
            )


class TestPolicyVersion:
    """Test policy versioning."""

    def test_policy_version_exists(self):
        """ACTIVITY_POLICY_VERSION must be defined."""
        assert ACTIVITY_POLICY_VERSION is not None
        assert isinstance(ACTIVITY_POLICY_VERSION, str)

    def test_policy_version_format(self):
        """Policy version should follow the naming convention."""
        assert ACTIVITY_POLICY_VERSION == "activity-v1"


class TestNoSilentDefaults:
    """Verify no unknown category silently maps to sedentary."""

    def test_unknown_category_not_in_factors(self):
        """A fabricated category must NOT be in ACTIVITY_FACTORS."""
        known_values = {cat.value for cat in ActivityCategory}
        for key in ACTIVITY_FACTORS:
            assert key.value in known_values, (
                f"Unknown category {key} found in ACTIVITY_FACTORS"
            )

    def test_get_factor_fails_for_invalid_input(self):
        """get_activity_factor must fail for invalid input, not default."""
        with pytest.raises(KeyError, match="No activity factor defined"):
            get_activity_factor("unknown_category")  # type: ignore


class TestOccupationBaselines:
    """Verify occupation baseline scores match Revision 3 policy."""

    def test_sedentary_baseline(self):
        """SEDENTARY occupation must have baseline 0."""
        assert OCCUPATION_BASELINES[OccupationalActivity.SEDENTARY] == 0

    def test_light_manual_baseline(self):
        """LIGHT_MANUAL occupation must have baseline 1."""
        assert OCCUPATION_BASELINES[OccupationalActivity.LIGHT_MANUAL] == 1

    def test_active_manual_baseline(self):
        """ACTIVE_MANUAL occupation must have baseline 2."""
        assert OCCUPATION_BASELINES[OccupationalActivity.ACTIVE_MANUAL] == 2

    def test_heavy_manual_baseline(self):
        """HEAVY_MANUAL occupation must have baseline 3."""
        assert OCCUPATION_BASELINES[OccupationalActivity.HEAVY_MANUAL] == 3

    def test_all_occupations_have_baselines(self):
        """Every OccupationalActivity must have a defined baseline."""
        for occ in OccupationalActivity:
            assert occ in OCCUPATION_BASELINES, f"Missing baseline for {occ}"

    def test_baselines_are_monotonic(self):
        """Baselines must be monotonically increasing."""
        values = [OCCUPATION_BASELINES[occ] for occ in OccupationalActivity]
        assert values == sorted(values)


class TestIntensityWeights:
    """Verify exercise intensity weights match Revision 3 policy."""

    def test_none_weight(self):
        """NONE intensity must have weight 0."""
        assert INTENSITY_WEIGHTS[ExerciseIntensity.NONE] == 0

    def test_light_weight(self):
        """LIGHT intensity must have weight 2."""
        assert INTENSITY_WEIGHTS[ExerciseIntensity.LIGHT] == 2

    def test_moderate_weight(self):
        """MODERATE intensity must have weight 4."""
        assert INTENSITY_WEIGHTS[ExerciseIntensity.MODERATE] == 4

    def test_vigorous_weight(self):
        """VIGOROUS intensity must have weight 7."""
        assert INTENSITY_WEIGHTS[ExerciseIntensity.VIGOROUS] == 7

    def test_all_intensities_have_weights(self):
        """Every ExerciseIntensity must have a defined weight."""
        for intensity in ExerciseIntensity:
            assert intensity in INTENSITY_WEIGHTS, f"Missing weight for {intensity}"

    def test_weights_are_non_negative(self):
        """All intensity weights must be non-negative."""
        for intensity, weight in INTENSITY_WEIGHTS.items():
            assert weight >= 0, f"Weight for {intensity} must be ≥ 0, got {weight}"


class TestWesUpgradeThresholds:
    """Verify WES upgrade thresholds match Revision 3 policy."""

    def test_thresholds_are_ascending(self):
        """Thresholds must be in ascending order."""
        thresholds = [t for t, _ in WES_UPGRADE_THRESHOLDS]
        assert thresholds == sorted(thresholds)

    def test_upgrade_scores_are_ascending(self):
        """Upgrade scores must be in ascending order."""
        upgrades = [u for _, u in WES_UPGRADE_THRESHOLDS]
        assert upgrades == sorted(upgrades)

    def test_first_threshold_is_600(self):
        """First threshold must be 600."""
        assert WES_UPGRADE_THRESHOLDS[0][0] == 600.0

    def test_second_threshold_is_1800(self):
        """Second threshold must be 1800."""
        assert WES_UPGRADE_THRESHOLDS[1][0] == 1800.0

    def test_upgrade_range(self):
        """Upgrade scores must be in range 0–2."""
        for _, upgrade in WES_UPGRADE_THRESHOLDS:
            assert 0 <= upgrade <= 2, f"Upgrade {upgrade} out of range 0–2"
