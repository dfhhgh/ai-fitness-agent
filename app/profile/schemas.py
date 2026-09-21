"""Utilities to load and access JSON Schema contracts."""

import json
from pathlib import Path
from typing import Any, Dict

SCHEMA_DIR = Path(__file__).resolve().parent.parent.parent / "schemas"


def load_schema(schema_filename: str) -> Dict[str, Any]:
    """Load and parse a JSON schema file from the project's schemas directory.

    Args:
        schema_filename: Filename such as 'client_profile.schema.json'.

    Returns:
        Dict representing the parsed JSON schema.
    """
    schema_path = SCHEMA_DIR / schema_filename
    if not schema_path.exists():
        raise FileNotFoundError(f"Schema file not found at: {schema_path}")
    with open(schema_path, "r", encoding="utf-8") as f:
        return json.load(f)


def get_client_profile_schema() -> Dict[str, Any]:
    return load_schema("client_profile.schema.json")


def get_profile_patch_schema() -> Dict[str, Any]:
    return load_schema("profile_patch.schema.json")


def get_fitness_plan_schema() -> Dict[str, Any]:
    return load_schema("fitness_plan.schema.json")
