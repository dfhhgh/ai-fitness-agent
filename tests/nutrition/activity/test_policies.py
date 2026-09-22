"""Tests for app.nutrition.activity.policies — activity factor lookup.

Tests cover:
- Every ActivityCategory maps to the exact approved factor
- No unknown category silently maps to sedentary
- Factor lookup is deterministic
- Policy constants are centralized
- Unknown categories fail explicitly
"""

import pytest

from app.nutrition.activity.policies import (
    ACTIVITY_FACTORS,
    ACTIVITY_POLICY_VERSION,
    get_activity_factor,
)
from app.nutrition.models import ActivityCategory


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
        # Simulate an unknown category by checking the dict directly
        known_values = {cat.value for cat in ActivityCategory}
        for key in ACTIVITY_FACTORS:
            assert key.value in known_values, (
                f"Unknown category {key} found in ACTIVITY_FACTORS"
            )

    def test_get_factor_fails_for_invalid_input(self):
        """get_activity_factor must fail for invalid input, not default."""
        # We can't pass an invalid enum value directly, but we can verify
        # the function raises KeyError for missing keys
        with pytest.raises(KeyError, match="No activity factor defined"):
            # This simulates what would happen with an unknown category
            get_activity_factor("unknown_category")  # type: ignore
