"""Pydantic v2 models representing the ClientProfile and ProfilePatch contracts.

Note:
- No business logic or complex validation rules are implemented here.
- HealthInfo.injuries distinguishes None (unasked) from [] (no injuries).
- ProfilePatch represents structured candidate updates emitted by the LLM.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional, Union
from pydantic import BaseModel, ConfigDict, Field


class PersonalInfo(BaseModel):
    model_config = ConfigDict(extra="forbid")

    age: Optional[int] = None
    gender: Optional[str] = None
    height_cm: Optional[float] = None
    weight_kg: Optional[float] = None


class GoalInfo(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: Optional[str] = None
    target_weight_kg: Optional[float] = None
    weight_change_target_kg: Optional[float] = None


class TrainingInfo(BaseModel):
    model_config = ConfigDict(extra="forbid")

    days_per_week: Optional[int] = None
    duration: Optional[Union[str, float, int]] = None
    experience: Optional[str] = None
    activity_description: Optional[str] = None


class HealthInfo(BaseModel):
    model_config = ConfigDict(extra="forbid")

    # Important semantic distinction:
    # None = unasked
    # [] = explicitly reported no injuries
    # ["..."] = reported injuries
    injuries: Optional[List[str]] = None


class NutritionPreferences(BaseModel):
    model_config = ConfigDict(extra="forbid")

    food_preferences: List[str] = Field(default_factory=list)
    disliked_foods: List[str] = Field(default_factory=list)
    disliked_activities: List[str] = Field(default_factory=list)


class InBodyInfo(BaseModel):
    model_config = ConfigDict(extra="forbid")

    weight_kg: Optional[float] = None
    body_fat_percent: Optional[float] = None
    fat_mass_kg: Optional[float] = None
    skeletal_muscle_mass_kg: Optional[float] = None
    bmi: Optional[float] = None
    visceral_fat_level: Optional[float] = None


class ProfileMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid")

    profile_status: str = "INCOMPLETE"
    missing_fields: List[str] = Field(default_factory=list)
    last_updated: Optional[datetime] = None


class ClientProfile(BaseModel):
    model_config = ConfigDict(extra="forbid")

    client_id: Optional[str] = None
    personal: PersonalInfo = Field(default_factory=PersonalInfo)
    goal: GoalInfo = Field(default_factory=GoalInfo)
    training: TrainingInfo = Field(default_factory=TrainingInfo)
    health: HealthInfo = Field(default_factory=HealthInfo)
    nutrition: NutritionPreferences = Field(default_factory=NutritionPreferences)
    inbody: InBodyInfo = Field(default_factory=InBodyInfo)
    metadata: ProfileMetadata = Field(default_factory=ProfileMetadata)


class ProfilePatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    updates: Dict[str, Any] = Field(default_factory=dict)
    unknown_fields: List[str] = Field(default_factory=list)
    conflicts: List[Dict[str, Any]] = Field(default_factory=list)
