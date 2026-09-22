"""Tests for app.llm.extractor — fully mocked LLMClient, no network access.

Each test injects a predetermined JSON string into LLMClient.chat() to verify
that ProfileExtractor correctly parses and validates into ProfilePatch.
"""

import json
from unittest.mock import MagicMock

import pytest

from app.llm.client import LLMClient
from app.llm.exceptions import LLMExtractionError
from app.llm.extractor import ProfileExtractor
from app.llm.prompts import PROFILE_EXTRACTION_SYSTEM_PROMPT
from app.profile.models import ProfilePatch


def _make_extractor(chat_return: str) -> ProfileExtractor:
    """Create a ProfileExtractor with a mocked LLMClient returning *chat_return*."""
    mock_client = MagicMock(spec=LLMClient)
    mock_client.chat.return_value = chat_return
    return ProfileExtractor(client=mock_client)


class TestProfileExtractor:
    """Semantic extraction tests using mocked LLM responses."""

    def test_extract_basic_profile(self):
        """Full Egyptian Arabic message with multiple fields."""
        # Simulates LLM output for:
        # "أنا 25 سنة، راجل، طولي 175 سم ووزني 85 كيلو،
        #  بتمرن 4 أيام في الأسبوع وبقالي شهرين في الجيم، شغلي مكتبي وعايز أخس."
        llm_output = json.dumps({
            "updates": {
                "personal.age": 25,
                "personal.gender": "رجل",
                "personal.height_cm": 175,
                "personal.weight_kg": 85,
                "training.days_per_week": 4,
                "training.duration": "2 months",
                "training.activity_description": "مكتبي",
                "goal.type": "weight_loss",
            },
            "unknown_fields": [],
            "conflicts": [],
        }, ensure_ascii=False)

        extractor = _make_extractor(llm_output)
        patch = extractor.extract("أنا 25 سنة، راجل، طولي 175 سم ووزني 85 كيلو")

        assert isinstance(patch, ProfilePatch)
        assert patch.updates["personal.age"] == 25
        assert patch.updates["personal.gender"] == "رجل"
        assert patch.updates["personal.height_cm"] == 175
        assert patch.updates["personal.weight_kg"] == 85
        assert patch.updates["training.days_per_week"] == 4
        assert patch.updates["training.duration"] == "2 months"
        assert patch.updates["training.activity_description"] == "مكتبي"
        assert patch.updates["goal.type"] == "weight_loss"
        # Must NOT contain training.experience
        assert "training.experience" not in patch.updates

    def test_weight_loss_amount_not_current_weight(self):
        """'عايز أخس 10 كيلو' → weight_change_target_kg=10, NOT personal.weight_kg=10."""
        llm_output = json.dumps({
            "updates": {
                "training.days_per_week": 4,
                "training.duration": "2 months",
                "goal.type": "weight_loss",
                "goal.weight_change_target_kg": 10,
            },
            "unknown_fields": [],
            "conflicts": [],
        })

        extractor = _make_extractor(llm_output)
        patch = extractor.extract("بتمرن 4 أيام، وبقالي شهرين في الجيم، وعايز أخس 10 كيلو.")

        assert patch.updates.get("goal.type") == "weight_loss"
        assert patch.updates.get("goal.weight_change_target_kg") == 10
        # Critical: must NOT set personal.weight_kg to 10
        assert "personal.weight_kg" not in patch.updates

    def test_target_weight_not_current_weight(self):
        """Current weight 85 + target 75 → correct field mapping."""
        llm_output = json.dumps({
            "updates": {
                "personal.weight_kg": 85,
                "goal.target_weight_kg": 75,
                "goal.type": "weight_loss",
            },
            "unknown_fields": [],
            "conflicts": [],
        })

        extractor = _make_extractor(llm_output)
        patch = extractor.extract("وزني الحالي 85 كيلو وعايز أوصل لـ 75 كيلو.")

        assert patch.updates["personal.weight_kg"] == 85
        assert patch.updates["goal.target_weight_kg"] == 75
        assert patch.updates["goal.type"] == "weight_loss"

    def test_goal_boundary(self):
        """Training + disliked activity without explicit goal → no goal.type."""
        llm_output = json.dumps({
            "updates": {
                "training.days_per_week": 4,
                "nutrition.disliked_activities": ["الجري"],
            },
            "unknown_fields": [],
            "conflicts": [],
        })

        extractor = _make_extractor(llm_output)
        patch = extractor.extract("أنا بتمرن 4 أيام في الأسبوع ومش بحب الجري.")

        assert patch.updates["training.days_per_week"] == 4
        assert "الجري" in patch.updates["nutrition.disliked_activities"]
        # Must NOT invent a goal
        assert "goal.type" not in patch.updates

    def test_experience_vs_duration(self):
        """Beginner + 2 months → separate experience and duration fields."""
        llm_output = json.dumps({
            "updates": {
                "training.experience": "beginner",
                "training.duration": "2 months",
            },
            "unknown_fields": [],
            "conflicts": [],
        })

        extractor = _make_extractor(llm_output)
        patch = extractor.extract("أنا مبتدئ ولسه داخل الجيم من شهرين.")

        assert patch.updates["training.experience"] == "beginner"
        assert patch.updates["training.duration"] == "2 months"

    def test_no_inference(self):
        """Only training days mentioned → only training.days_per_week extracted."""
        llm_output = json.dumps({
            "updates": {
                "training.days_per_week": 4,
            },
            "unknown_fields": [],
            "conflicts": [],
        })

        extractor = _make_extractor(llm_output)
        patch = extractor.extract("أنا بتمرن 4 أيام في الأسبوع.")

        assert patch.updates == {"training.days_per_week": 4}
        # Must NOT invent any other fields
        assert "goal.type" not in patch.updates
        assert "personal.weight_kg" not in patch.updates
        assert "personal.height_cm" not in patch.updates
        assert "personal.age" not in patch.updates
        assert "personal.gender" not in patch.updates
        assert "training.experience" not in patch.updates

    def test_extractor_messages_contract(self):
        """Verify the exact messages payload sent to LLMClient.chat().

        The first message must be the system prompt, and the second message
        must be the exact user message passed to extract().
        """
        mock_client = MagicMock(spec=LLMClient)
        mock_client.chat.return_value = json.dumps({
            "updates": {"personal.age": 28},
            "unknown_fields": [],
            "conflicts": [],
        })
        extractor = ProfileExtractor(client=mock_client)
        user_msg = "أنا عندي 28 سنة وطولي 180 سم"
        extractor.extract(user_msg)

        mock_client.chat.assert_called_once()
        call_args, _ = mock_client.chat.call_args
        messages = call_args[0]

        assert len(messages) == 2
        assert messages[0]["role"] == "system"
        assert messages[0]["content"] == PROFILE_EXTRACTION_SYSTEM_PROMPT
        assert messages[1]["role"] == "user"
        assert messages[1]["content"] == user_msg



class TestProfileExtractorEdgeCases:
    """Edge cases for LLM output cleaning and error handling."""

    def test_json_fence_stripping(self):
        """LLM wraps output in ```json ... ``` — still parses correctly."""
        inner = json.dumps({
            "updates": {"personal.age": 30},
            "unknown_fields": [],
            "conflicts": [],
        })
        fenced = f"```json\n{inner}\n```"

        extractor = _make_extractor(fenced)
        patch = extractor.extract("أنا عندي 30 سنة")

        assert patch.updates["personal.age"] == 30

    def test_json_fence_no_language(self):
        """LLM uses ``` without 'json' label."""
        inner = json.dumps({
            "updates": {},
            "unknown_fields": [],
            "conflicts": [],
        })
        fenced = f"```\n{inner}\n```"

        extractor = _make_extractor(fenced)
        patch = extractor.extract("مرحبا")

        assert patch.updates == {}

    def test_whitespace_padded_output(self):
        """LLM output with leading/trailing whitespace."""
        raw = "  \n " + json.dumps({
            "updates": {"personal.age": 22},
            "unknown_fields": [],
            "conflicts": [],
        }) + "  \n  "

        extractor = _make_extractor(raw)
        patch = extractor.extract("عندي 22 سنة")

        assert patch.updates["personal.age"] == 22

    def test_invalid_json_raises_extraction_error(self):
        """Garbage text from LLM raises LLMExtractionError."""
        extractor = _make_extractor("This is not JSON at all!")

        with pytest.raises(LLMExtractionError, match="invalid JSON"):
            extractor.extract("test")

    def test_non_object_json_raises_extraction_error(self):
        """LLM returns a JSON array instead of object."""
        extractor = _make_extractor("[1, 2, 3]")

        with pytest.raises(LLMExtractionError, match="expected object"):
            extractor.extract("test")

    def test_empty_patch_is_valid(self):
        """Empty updates/unknown_fields/conflicts is a valid ProfilePatch."""
        llm_output = json.dumps({
            "updates": {},
            "unknown_fields": [],
            "conflicts": [],
        })

        extractor = _make_extractor(llm_output)
        patch = extractor.extract("مرحبا")

        assert isinstance(patch, ProfilePatch)
        assert patch.updates == {}
        assert patch.unknown_fields == []
        assert patch.conflicts == []

    def test_unknown_fields_and_conflicts(self):
        """Verify unknown_fields and conflicts are passed through."""
        llm_output = json.dumps({
            "updates": {"personal.weight_kg": 85},
            "unknown_fields": ["personal.height_cm"],
            "conflicts": [
                {
                    "field": "personal.weight_kg",
                    "values": [85, 90],
                    "message": "وزني 85، لا استنى 90",
                }
            ],
        }, ensure_ascii=False)

        extractor = _make_extractor(llm_output)
        patch = extractor.extract("وزني 85 لا استنى 90 ومش عارف طولي")

        assert patch.updates["personal.weight_kg"] == 85
        assert "personal.height_cm" in patch.unknown_fields
        assert len(patch.conflicts) == 1
        assert patch.conflicts[0]["field"] == "personal.weight_kg"

    def test_llm_arbitrary_path_rejected(self):
        """LLM emitting an arbitrary update path is rejected deterministically."""
        llm_output = json.dumps({
            "updates": {"some.random.field": "bad"},
            "unknown_fields": [],
            "conflicts": [],
        })
        extractor = _make_extractor(llm_output)

        with pytest.raises(LLMExtractionError, match="Arbitrary paths are strictly forbidden"):
            extractor.extract("test")

    def test_llm_inbody_path_rejected(self):
        """LLM emitting an inbody path is rejected deterministically."""
        llm_output = json.dumps({
            "updates": {"inbody.body_fat_percent": 20},
            "unknown_fields": [],
            "conflicts": [],
        })
        extractor = _make_extractor(llm_output)

        with pytest.raises(LLMExtractionError, match="InBody fields cannot be updated via ProfilePatch"):
            extractor.extract("test")

    def test_llm_invalid_type_rejected(self):
        """LLM emitting wrong type for field is rejected deterministically."""
        llm_output = json.dumps({
            "updates": {"personal.age": "twenty five"},
            "unknown_fields": [],
            "conflicts": [],
        })
        extractor = _make_extractor(llm_output)

        with pytest.raises(LLMExtractionError, match="must be an integer"):
            extractor.extract("test")


class TestNestedSectionFlattening:
    """Tests for the targeted flattener that handles nested LLM output."""

    def test_nested_health_injuries_flattened(self):
        """Nested {'health': {'injuries': []}} is flattened to 'health.injuries': []."""
        llm_output = json.dumps({
            "updates": {
                "health": {
                    "injuries": []
                }
            },
            "unknown_fields": [],
            "conflicts": [],
        })

        extractor = _make_extractor(llm_output)
        patch = extractor.extract("مفيش عندي أي إصابات")

        assert "health.injuries" in patch.updates
        assert patch.updates["health.injuries"] == []

    def test_nested_health_injuries_with_values(self):
        """Nested injuries with values are flattened correctly."""
        llm_output = json.dumps({
            "updates": {
                "health": {
                    "injuries": ["إصابة في الركبة"]
                }
            },
            "unknown_fields": [],
            "conflicts": [],
        })

        extractor = _make_extractor(llm_output)
        patch = extractor.extract("عندي إصابة في الركبة")

        assert patch.updates["health.injuries"] == ["إصابة في الركبة"]

    def test_nested_personal_flattened(self):
        """Nested {'personal': {'age': 25}} is flattened to 'personal.age': 25."""
        llm_output = json.dumps({
            "updates": {
                "personal": {
                    "age": 25,
                    "gender": "رجل"
                }
            },
            "unknown_fields": [],
            "conflicts": [],
        })

        extractor = _make_extractor(llm_output)
        patch = extractor.extract("أنا 25 سنة وراجل")

        assert patch.updates["personal.age"] == 25
        assert patch.updates["personal.gender"] == "رجل"

    def test_nested_training_flattened(self):
        """Nested training fields are flattened correctly."""
        llm_output = json.dumps({
            "updates": {
                "training": {
                    "days_per_week": 4,
                    "duration": "2 months"
                }
            },
            "unknown_fields": [],
            "conflicts": [],
        })

        extractor = _make_extractor(llm_output)
        patch = extractor.extract("بتمرن 4 أيام في الأسبوع وبقالي شهرين")

        assert patch.updates["training.days_per_week"] == 4
        assert patch.updates["training.duration"] == "2 months"

    def test_mixed_flat_and_nested(self):
        """Mix of flat dotted paths and nested section dicts."""
        llm_output = json.dumps({
            "updates": {
                "personal.age": 25,
                "health": {
                    "injuries": []
                },
                "training.days_per_week": 4,
            },
            "unknown_fields": [],
            "conflicts": [],
        })

        extractor = _make_extractor(llm_output)
        patch = extractor.extract("أنا 25 سنة، بتمرن 4 أيام، مفيش إصابات")

        assert patch.updates["personal.age"] == 25
        assert patch.updates["health.injuries"] == []
        assert patch.updates["training.days_per_week"] == 4

    def test_flat_format_still_works(self):
        """Standard flat dotted-path format continues to work unchanged."""
        llm_output = json.dumps({
            "updates": {
                "personal.age": 25,
                "health.injuries": [],
                "training.days_per_week": 4,
            },
            "unknown_fields": [],
            "conflicts": [],
        })

        extractor = _make_extractor(llm_output)
        patch = extractor.extract("test")

        assert patch.updates["personal.age"] == 25
        assert patch.updates["health.injuries"] == []
        assert patch.updates["training.days_per_week"] == 4

    def test_unknown_section_not_flattened(self):
        """Unknown top-level key in updates is NOT flattened, just passed through."""
        llm_output = json.dumps({
            "updates": {
                "unknown_section": {
                    "some_field": "value"
                }
            },
            "unknown_fields": [],
            "conflicts": [],
        })

        extractor = _make_extractor(llm_output)
        with pytest.raises(LLMExtractionError, match="Arbitrary paths are strictly forbidden"):
            extractor.extract("test")

