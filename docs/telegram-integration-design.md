# Telegram Integration Design — Architecture Audit

**Phase:** 1.2.0 — Architecture Audit Only
**Date:** 2026-09-22
**Status:** Audit complete. No production code changed.

---

## 1. Current Interview Core Architecture

### Components

| Component | Location | Responsibility |
|-----------|----------|----------------|
| `ProfileExtractor` | `app/llm/extractor.py` | User message → LLM → `ProfilePatch` |
| `InterviewController` | `app/interview/controller.py` | Orchestrates one turn: extract → detect conflicts → merge or return WAITING |
| `InterviewTurnResult` | `app/interview/models.py` | Frozen result: profile, patch, state, next_field, missing_fields, conflicts, merged |
| `QuestionGenerator` | `app/interview/question_generator.py` | Field path → Egyptian Arabic question string |
| `ClarificationGenerator` | `app/interview/clarification_generator.py` | `Conflict` → Egyptian Arabic clarification question |
| `ClarificationResolver` | `app/interview/clarification_resolver.py` | User answer + `Conflict` → `ClarificationResolution` (resolved patch or unresolved) |
| `detect_conflicts` | `app/profile/conflicts.py` | Profile + patch → list of `Conflict` |
| `ProfileMerger` | `app/profile/merger.py` | Profile + validated patch → new profile |
| `get_interview_status` | `app/profile/state_machine.py` | Profile → `InterviewStatus` (state, next_field, missing_fields) |
| `get_missing_fields` | `app/profile/missing_fields.py` | Profile → ordered list of missing required fields |
| `validate_profile_patch` | `app/profile/validator.py` | Deterministic patch validation |

### Current InterviewController Contract

```python
class InterviewController:
    def __init__(self, extractor: ProfileExtractor) -> None: ...

    def process_message(
        self,
        profile: ClientProfile,
        user_message: str,
    ) -> InterviewTurnResult: ...
```

**Input:** `ClientProfile` + raw user message string
**Output:** `InterviewTurnResult` containing:
- `profile`: resulting profile (original if no merge, updated if merged)
- `patch`: extracted `ProfilePatch`
- `state`: `InterviewState` (INTERVIEWING / WAITING_FOR_CLARIFICATION / READY_FOR_PLAN)
- `next_field`: next missing field path, or None
- `missing_fields`: all still-missing required fields
- `conflicts`: detected conflicts (empty if none)
- `merged`: True only if patch was safely merged

### Current Gap

The controller handles the **normal flow** (extract → detect → merge) but does NOT handle the **clarification flow**:

```
Normal flow:       user message → controller → merged profile + next question
Clarification flow: user answer → ??? → resolved patch → merge → next question
```

When `state == WAITING_FOR_CLARIFICATION`, the controller returns conflicts but does NOT:
- Call `ClarificationGenerator` to produce the question
- Call `ClarificationResolver` to interpret the user's answer
- Merge the resolved patch

This gap must be bridged for Telegram integration.

---

## 2. Proposed Telegram Architecture

```
Telegram Update (webhook/polling)
    ↓
TelegramAdapter          (app/telegram/adapter.py)
    ↓
InterviewService          (app/interview/service.py)   ← NEW
    ↓
InterviewController       (existing, unchanged)
    ↓
ClarificationGenerator    (existing, unchanged)
    ↓
ClarificationResolver     (existing, unchanged)
    ↓
ProfileMerger             (existing, unchanged)
    ↓
InterviewTurnResult
    ↓
ResponseMapper            (app/telegram/response.py)   ← NEW
    ↓
TelegramAdapter           (send message)
```

### Key Principle

The Telegram layer is a **thin adapter**. All business logic lives in the Interview Core or a small application service layer.

---

## 3. Message Flow

### Normal Turn (no conflict)

```
1. Telegram sends: "أنا 25 سنة وراجل"
2. Adapter receives update, extracts chat_id and text
3. Adapter calls service.handle_message(chat_id, text)
4. Service loads profile for chat_id
5. Service calls controller.process_message(profile, text)
6. Controller returns InterviewTurnResult (state=INTERVIEWING, merged=True)
7. Service saves updated profile
8. Service calls QuestionGenerator.generate(next_field)
9. Service returns response text to adapter
10. Adapter sends message to Telegram
```

### Clarification Turn

```
1. Telegram sends: "26"
2. Adapter receives update
3. Service loads profile + pending conflicts for chat_id
4. Service detects state == WAITING_FOR_CLARIFICATION
5. Service calls ClarificationResolver.resolve(conflict, "26")
6. If resolved:
   a. validate_profile_patch(resolved_patch)
   b. ProfileMerger.merge(profile, resolved_patch)
   c. Save updated profile
   d. get_interview_status(profile) → determine next action
   e. Generate next question or return completion message
7. If unresolved:
   a. Re-ask the clarification question
8. Adapter sends response
```

---

## 4. State Flow

### States Between Telegram Messages

| State | Profile | Pending Conflict | Next Action |
|-------|---------|-------------------|-------------|
| `INTERVIEWING` | Partial | None | Ask next missing field question |
| `WAITING_FOR_CLARIFICATION` | Partial | Yes | Wait for user to resolve conflict |
| `READY_FOR_PLAN` | Complete | None | Show completion message / generate plan |

### State Transitions

```
START → INTERVIEWING (profile empty)
INTERVIEWING → INTERVIEWING (field answered, more fields missing)
INTERVIEWING → WAITING_FOR_CLARIFICATION (conflict detected)
INTERVIEWING → READY_FOR_PLAN (all fields present, no conflicts)
WAITING_FOR_CLARIFICATION → INTERVIEWING (conflict resolved, more fields missing)
WAITING_FOR_CLARIFICATION → READY_FOR_PLAN (conflict resolved, all fields present)
WAITING_FOR_CLARIFICATION → WAITING_FOR_CLARIFICATION (unresolved, re-ask)
```

---

## 5. Identity Model

### Two Distinct Identifiers

| Identifier | Source | Purpose |
|------------|--------|---------|
| `chat_id` | Telegram | Identifies the Telegram conversation |
| `client_id` | Application | Identifies the client profile |

### Do NOT Assume Equivalence

- `chat_id` is a Telegram-specific integer (e.g., `123456789`)
- `client_id` is an application-level string (e.g., `"client-abc-123"`)
- A single Telegram user maps to exactly one client profile
- A single client profile could theoretically be accessed from multiple channels

### MVP Mapping Strategy

For the first MVP, use `chat_id` as the `client_id` directly:

```python
client_id = str(chat_id)
```

This is simple and sufficient for a single-channel MVP. A future multi-channel version should introduce a proper identity mapping table.

---

## 6. Telegram/Core Boundary

### What the Telegram Adapter Does

- Receives Telegram updates (message text + chat_id)
- Looks up conversation state
- Calls the application service
- Formats the response for Telegram
- Sends the response via Telegram API

### What the Telegram Adapter Does NOT Do

- LLM extraction
- Profile validation
- Profile merging
- Conflict detection
- Clarification resolution
- Missing-field logic
- Interview state-machine logic
- Nutrition calculations
- Workout generation
- Business rules

### What the Application Service Does

The `InterviewService` (or equivalent) bridges Telegram and the Interview Core:

```python
class InterviewService:
    def handle_message(self, chat_id: int, text: str) -> str: ...
```

It is responsible for:
1. Loading/creating the profile for a chat_id
2. Determining the current conversation state
3. Routing to the correct handler (normal vs clarification)
4. Calling InterviewController or ClarificationResolver as needed
5. Saving the updated profile
6. Generating the response text
7. Returning the response string to the adapter

---

## 7. Required Interfaces

### 7.1 Conversation Store (In-Memory for MVP)

```python
class ConversationStore:
    """Stores conversation state between Telegram messages."""

    def get_profile(self, client_id: str) -> ClientProfile | None: ...
    def save_profile(self, client_id: str, profile: ClientProfile) -> None: ...
    def get_pending_conflicts(self, client_id: str) -> list[Conflict] | None: ...
    def save_pending_conflicts(self, client_id: str, conflicts: list[Conflict]) -> None: ...
    def clear_pending_conflicts(self, client_id: str) -> None: ...
```

### 7.2 Interview Service

```python
class InterviewService:
    """Application service bridging Telegram and Interview Core."""

    def __init__(
        self,
        controller: InterviewController,
        store: ConversationStore,
    ) -> None: ...

    def handle_message(self, chat_id: int, text: str) -> str: ...
```

### 7.3 Telegram Adapter

```python
class TelegramAdapter:
    """Thin adapter between Telegram API and InterviewService."""

    def __init__(self, service: InterviewService, bot_token: str) -> None: ...

    def handle_update(self, update: dict) -> None: ...
```

---

## 8. Proposed Folder Structure

```
app/
├── __init__.py
├── profile/                    # existing — unchanged
├── interview/
│   ├── __init__.py
│   ├── controller.py           # existing — unchanged
│   ├── models.py               # existing — unchanged
│   ├── question_generator.py   # existing — unchanged
│   ├── question_policy.py      # existing — unchanged
│   ├── clarification_generator.py   # existing — unchanged
│   ├── clarification_policy.py      # existing — unchanged
│   ├── clarification_resolver.py    # existing — unchanged
│   └── service.py              # NEW — application service
├── llm/                        # existing — unchanged
├── telegram/
│   ├── __init__.py
│   ├── adapter.py              # Telegram update handling
│   ├── response.py             # Response formatting for Telegram
│   └── models.py               # Telegram-specific data models
└── storage/
    ├── __init__.py
    └── memory.py               # In-memory conversation store
```

---

## 9. MVP State Persistence Strategy

### Phase 1.2.0: In-Memory Store

For the first MVP, use a simple in-memory dictionary:

```python
class InMemoryConversationStore:
    def __init__(self):
        self._profiles: dict[str, ClientProfile] = {}
        self._conflicts: dict[str, list[Conflict]] = {}

    def get_profile(self, client_id: str) -> ClientProfile | None:
        return self._profiles.get(client_id)

    def save_profile(self, client_id: str, profile: ClientProfile) -> None:
        self._profiles[client_id] = profile

    def get_pending_conflicts(self, client_id: str) -> list[Conflict] | None:
        return self._conflicts.get(client_id)

    def save_pending_conflicts(self, client_id: str, conflicts: list[Conflict]) -> None:
        self._conflicts[client_id] = conflicts

    def clear_pending_conflicts(self, client_id: str) -> None:
        self._conflicts.pop(client_id, None)
```

### Limitations

- State is lost on restart
- Single-process only
- No concurrent access protection

### Future: Database Backend

Replace `InMemoryConversationStore` with a database-backed implementation. The interface remains the same.

---

## 10. Error-Handling Strategy

### Error Categories

| Category | Example | Telegram Response |
|----------|---------|-------------------|
| LLM failure | `LLMConnectionError` | "مش عارف أتصل بالservers دلوقتي. جرب تاني." |
| LLM extraction error | `LLMExtractionError` | "مش فاهم القصد. ممكن توضح أكتر؟" |
| Validation error | `ProfileValidationError` | "فيه خطأ في البيانات. ممكن ت检查؟" |
| Clarification unresolved | `resolved=False` | Re-ask the clarification question |
| Unknown error | Any other exception | "حصل مشكلة. جرب تاني." |

### Principles

- Never expose internal errors to the user
- Always return a user-friendly Arabic message
- Log the full error for debugging
- The Telegram adapter should never crash on a single message failure

---

## 11. What is Explicitly NOT Included in Phase 1.2.0

- Telegram bot creation or token management
- Telegram webhook setup or ngrok
- Telegram polling implementation
- Database or persistent storage
- Docker configuration
- Multi-user concurrency handling
- Webhook signature verification
- Telegram inline keyboards or reply markup
- File/image handling
- Group chat support
- Admin interfaces
- Monitoring or analytics
- Rate limiting
- Caching beyond in-memory

---

## 12. Recommended Next Implementation Step

### Step 1.2.1: Application Service + In-Memory Store

**Goal:** Create the `InterviewService` and `InMemoryConversationStore` that bridge the Interview Core to any adapter.

**Deliverables:**

1. `app/storage/memory.py` — `InMemoryConversationStore`
2. `app/interview/service.py` — `InterviewService`
3. `tests/interview/test_service.py` — Unit tests for the service

**This step does NOT require Telegram.** It can be tested with a fake adapter, proving the integration works before adding Telegram API complexity.

**The service handles both flows:**

```python
class InterviewService:
    def handle_message(self, chat_id: int, text: str) -> str:
        client_id = str(chat_id)
        profile = self._store.get_profile(client_id)
        if profile is None:
            profile = ClientProfile(client_id=client_id)

        # Check if we're waiting for clarification
        pending = self._store.get_pending_conflicts(client_id)
        if pending:
            return self._handle_clarification(client_id, profile, text, pending)

        # Normal flow
        return self._handle_normal(client_id, profile, text)
```

**After this step,** adding Telegram is just:
1. Create `TelegramAdapter` that calls `service.handle_message()`
2. Format the response string for Telegram

---

## Architecture Findings Summary

| Finding | Detail |
|---------|--------|
| InterviewController contract | `(profile, user_message) → InterviewTurnResult` — clean, reusable |
| Missing application layer | No service orchestrating the full flow (normal + clarification) |
| No state persistence | Profile is not stored between calls; external storage required |
| Clarification gap | Controller detects conflicts but does not resolve them |
| Identity model | `chat_id` ≠ `client_id` by definition; MVP can map `str(chat_id)` → `client_id` |
| Telegram boundary | Adapter should be thin; all logic in service + core |
| Test baseline | 408 passed, 1 deselected — stable |
