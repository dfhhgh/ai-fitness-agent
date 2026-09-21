# AI Fitness Platform

An intelligent, deterministic AI fitness assistant platform designed to collect client profiles, run deterministic calculations, and generate verified nutrition and workout plans.

---

## 1. Architectural Principles

### The LLM is NOT the Source of Truth
The LLM is strictly confined to:
- Natural language understanding and dialogue.
- Extracting explicitly stated user information into candidate `ProfilePatch` objects.
- Formulating clarifying questions directed by the deterministic interview state machine.
- Candidate meal suggestions matching backend targets.

The LLM is **NEVER** the source of truth for:
- Numerical nutrition calculations (calories, protein, carbs, fats, fiber).
- Macro formulas and energy expenditure equations.
- Profile validation and merging rules.
- Conflict detection and resolution policies.
- Database persistence and state transitions.

### System Pipeline Flow
```
Telegram
   ↓
  n8n (Orchestration / Integration Layer)
   ↓
  LLM (Candidate Extraction)
   ↓
Structured Profile Patch
   ↓
Profile Validation (Deterministic)
   ↓
Profile Merge (Deterministic)
   ↓
Missing Fields Resolver
   ↓
Interview State Machine
   ↓
Manual InBody Data
   ↓
Deterministic Nutrition Calculator
   ↓
Food Database
   ↓
Workout Generator
   ↓
Plan Validation (Against Authoritative JSON Schema)
   ↓
Existing Backend API
   ↓
Mobile Application
```

---

## 2. Important Semantic Rules & Constraints

### Explicit Evidence Only
The system must extract **only** information explicitly supported by the user's message. It must never infer:
- `gender`
- `goal`
- `current weight`
- `target weight`
- `injuries`
- `activity level`
unless directly stated by the user.

### Weight Change vs. Current Weight
- **Example**: User says: `"بتمرن 4 أيام، وبقالي شهرين في الجيم، وعايز أخس 10 كيلو."`
  - **MUST NOT** produce: `personal.weight_kg = 10` (10 kg is the amount to lose, not current weight).
  - **MAY** produce: `goal.type = "weight_loss"`, `goal.weight_change_target_kg = 10`.

### Disliked Activities / Frequency are NOT Goal Evidence
- **Example**: User says: `"أنا بتمرن 4 أيام في الأسبوع ومش بحب الجري."`
  - **MUST NOT** infer a goal (e.g. weight loss or endurance).
  - Training frequency and disliked activities are not evidence of a goal.

### Semantics of `health.injuries`
- `health.injuries = null`: The system has **not** asked about injuries yet.
- `health.injuries = []`: The user **explicitly** stated that they have no injuries.
- `health.injuries = ["knee pain"]`: The user **explicitly** reported an injury.
- **Never collapse `null` and `[]`.**

---

## 3. Project Structure

```
ai-fitness-agent/
│
├── app/
│   ├── __init__.py
│   │
│   ├── profile/
│   │   ├── __init__.py
│   │   ├── models.py             # Pydantic v2 models
│   │   ├── schemas.py            # JSON schema loading utilities
│   │   ├── validator.py          # Deterministic validator (Phase 1.1.2)
│   │   ├── merger.py             # Deterministic merger (Phase 1.1.2)
│   │   ├── conflicts.py          # Conflict detector (Phase 1.1.2)
│   │   ├── policies.py           # Resolution policies (Phase 1.1.2)
│   │   ├── missing_fields.py     # Missing fields resolver (Phase 1.1.2)
│   │   └── state_machine.py      # Interview state machine (Phase 1.1.2)
│   │
│   └── llm/
│       ├── __init__.py
│       └── extractor.py          # LLM candidate extractor (subsequent phases)
│
├── tests/
│   └── profile/
│       ├── __init__.py
│       ├── test_contracts.py     # Schema, model & semantics tests
│       ├── test_validator.py     # (Phase 1.1.2)
│       ├── test_merger.py        # (Phase 1.1.2)
│       ├── test_conflicts.py     # (Phase 1.1.2)
│       ├── test_missing_fields.py# (Phase 1.1.2)
│       ├── test_state_machine.py # (Phase 1.1.2)
│       └── test_regression.py    # (Phase 1.1.2)
│
├── schemas/
│   ├── client_profile.schema.json # JSON Schema Draft 2020-12
│   ├── profile_patch.schema.json  # JSON Schema Draft 2020-12
│   └── fitness_plan.schema.json   # Authoritative JSON Schema Draft 2020-12
│
├── .env.example
├── .gitignore
├── pyproject.toml
├── README.md
└── requirements.txt
```

---

## 4. Setup and Installation

### Prerequisites
- Python 3.12 or 3.13

### Virtual Environment Setup
```powershell
# Create virtual environment
python -m venv .venv

# Activate virtual environment (Windows PowerShell)
.venv\Scripts\Activate.ps1

# Install dependencies
pip install -r requirements.txt
```

### Running Tests
```powershell
pytest
```
