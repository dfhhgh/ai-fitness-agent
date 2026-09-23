# carb-v1 Final Implementation Clarifications

Scope: resolves 4 implementation ambiguities in the locked carb-v1
policy. No scientific or architectural decisions are reopened. Where
the existing document already resolves a point unambiguously, that is
stated as "Confirmed — no policy change required" rather than restated
as a new rule.

---

## 1. target_calories = 0

**Final Decision:** Confirmed — no policy change required. **OPTION A.**
`target_calories` is a schema-level non-negative integer; `0` is
schema-valid, not a domain error.

**Exact Contract Rule:**
```python
target_calories: int = Field(..., ge=0)
```
This is the constraint already present in the carb-v1 pseudo-contract
(Section: Pseudo-Pydantic Contracts). No change to the `Field`
definition is required.

**Rationale:** The calculator's own Negative Residual and Zero Residual
policies (Sections 16–17) already define behavior purely in terms of
`residual_calories`, not `target_calories` in isolation. A
`target_calories` of `0` is not itself invalid — it only produces a
domain-level outcome once combined with `protein_g` and `fat_calories`.
Rejecting `0` at the schema layer would require inventing a new
constraint (`ge=1`) that has no basis anywhere in the locked policy and
would contradict the "purely mathematical, no hidden domain
assumptions" principle in Section 23. No new `INVALID`-for-zero status
is introduced, consistent with the instruction against doing so.

**Implementation Requirement:** No code change. Engineers must not add
`ge=1` or any zero-rejection logic to `CarbInput`.

**Expected Result for target_calories = 0, protein_g = 0, fat_calories = 0:**
```python
protein_calories = 0
residual_calories = 0 - 0 - 0 = 0
# residual_calories == 0 → OK path (Section 17)
CarbResult(
    status=CarbStatus.OK,
    carbohydrates_g=0,
    carbohydrate_calories=0,
    residual_calories=0,
    issues=(),
    policy_version="carb-v1",
)
```

**Does this change any other policy?** No. This is a direct application
of the already-locked Zero Residual Policy (Section 17) to a boundary
input; it introduces no new branch.

**Required Regression Tests:**
- `target_calories=0, protein_g=0, fat_calories=0` → `status=OK`,
  `carbohydrates_g=0`, `carbohydrate_calories=0`, `residual_calories=0`.
- `target_calories=0, protein_g=1, fat_calories=0` → `status=INVALID`,
  `residual_calories=-4`, `carbohydrates_g=None`,
  `carbohydrate_calories=None`, `issues=(NEGATIVE_CARBOHYDRATE_RESIDUAL,)`.
- `target_calories=-1` → `pydantic.ValidationError` (schema rejection,
  never reaches calculator logic).

---

## 2. CarbStatus = OK / INVALID

**Final Decision:** Confirmed — no policy change required. CarbStatus
remains a two-state enum: `OK`, `INVALID`.

**Exact Contract Rule:**
```python
class CarbStatus(str, Enum):
    OK = "OK"
    INVALID = "INVALID"
```
No `INCOMPLETE`, `REVIEW_REQUIRED`, or `ERROR` states are added.

**Rationale — why two states is intentional, not an inconsistency with
Protein/Fat:** Section 23 already draws this distinction explicitly.
The carb calculator sits strictly downstream of Protein and Fat and
consumes only their already-validated, already-rounded outputs plus a
validated `target_calories`. Because malformed, missing, or wrong-type
input is intercepted by Pydantic (`ValidationError`) before any
calculator logic runs, there is no code path left in which the
calculator itself could observe an "incomplete" input — that case is
structurally unreachable, not merely unhandled. Likewise,
`REVIEW_REQUIRED` belongs to Layer B clinical/contextual judgment
(Section 26), which the carb calculator is explicitly forbidden from
performing. Protein and Fat calculators may carry richer state models
because they sit earlier in the pipeline and/or absorb different classes
of upstream uncertainty; that is a property of their position in the
pipeline, not a template the carb calculator is required to mirror. The
only domain-level failure possible after schema validation is a
negative residual, which is fully captured by `OK` / `INVALID`.

**Implementation Requirement:** No code change. Do not add additional
enum members to `CarbStatus`.

**Required Regression Tests:**
- Malformed/missing/extra-field input (e.g. missing `fat_calories`, or
  an unexpected key) → `pydantic.ValidationError` raised before
  `CarbResult` is constructed; `CarbStatus` is never invoked for this
  case.
- Valid schema, `residual_calories >= 0` → `status=OK`.
- Valid schema, `residual_calories < 0` → `status=INVALID`.
- Confirm `CarbStatus` has exactly two members (enum length == 2) as a
  contract-shape regression test.

---

## 3. residual_calories on INVALID

**Final Decision:** Confirmed — no policy change required.
`residual_calories` remains populated (including negative values) on
both `OK` and `INVALID` results. It is never nulled.

**Exact Contract Rule:**
```python
residual_calories: int   # never Optional; populated for OK and INVALID
```
This matches the existing Output Contract (Section 25), which states
`residual_calories` is present specifically to enable traceability of
the exact shortfall when the status is `INVALID`.

**Rationale:** Section 16 (Negative Residual Policy) and Section 25
(Output Contract) already establish that `residual_calories` is
retained on `INVALID` for debugging/traceability, while only
`carbohydrates_g` and `carbohydrate_calories` — the two fields that
have no valid mathematical value once residual is negative — are
nulled. Nulling `residual_calories` on `INVALID` would erase the exact
diagnostic information (e.g. `-50`) that Section 16 explicitly requires
the calculator to surface instead of silently clamping to zero.

**Implementation Requirement:** No code change.

**Full Nullability Rules:**
| Field | On OK | On INVALID |
|---|---|---|
| `status` | `"OK"` | `"INVALID"` |
| `carbohydrates_g` | non-null `int` | `null` |
| `carbohydrate_calories` | non-null `int` | `null` |
| `residual_calories` | non-null `int` | non-null `int` (may be negative) |
| `issues` | `()` (empty tuple) | `(NEGATIVE_CARBOHYDRATE_RESIDUAL,)` |
| `policy_version` | `"carb-v1"` | `"carb-v1"` |

**Required Regression Tests:**
- `residual_calories=-50` on an `INVALID` result: assert
  `result.residual_calories == -50` (not `None`, not `0`).
- Assert `result.carbohydrates_g is None` and
  `result.carbohydrate_calories is None` when `status=INVALID`.
- Assert `result.residual_calories is not None` for every generated
  test case regardless of status (property-based/parametrized check).

---

## 4. FatResult.fat_calories as authoritative input

**Final Decision:** Confirmed — no policy change required.
`CarbInput` consumes `fat_calories` directly; it never receives `fat_g`
and never recomputes `fat_g * 9`.

**Exact Contract Rule:**
```python
class CarbInput(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)
    target_calories: int = Field(..., ge=0)
    protein_g: int = Field(..., ge=0)
    fat_calories: int = Field(..., ge=0)   # no fat_g field exists
```

**Rationale (explicit statements, as required):**
1. The Carb Calculator does not receive `fat_g` — it is not a field on
   `CarbInput` (Section 9, Section 12).
2. The Carb Calculator does not calculate fat calories — no
   `fat_g * 9` computation exists anywhere in carb-v1 logic (Section 12
   explicitly prohibits this).
3. `FatResult.fat_calories` is authoritative — the carb calculator
   trusts it as the exact realized energy footprint of the upstream fat
   allocation (Section 8, Section 12).
4. Any future change to the Fat Calculator's energy policy (e.g. a
   revised kcal/g factor in a Fat Calculator V2) must be reflected
   through the Fat Calculator's own output contract/version, and the
   Carb Calculator inherits it automatically by continuing to read
   `fat_calories` — carb-v1 requires no change to do so.
5. This is intentional separation of concerns to prevent "ghost
   decimal" drift between an internally-reconstructed fat energy value
   and the actual rounded value the Fat Calculator committed to output
   (Section 8), not an accidental omission of `fat_g` from the input
   schema.

**Implementation Requirement:** No code change. Reviewers should treat
any PR that adds a `fat_g` field to `CarbInput`, or that computes fat
calories internally, as a policy violation requiring rejection, not a
valid implementation variant.

**Required Regression Tests:**
- Construct `CarbInput` and assert it has exactly the fields
  `target_calories`, `protein_g`, `fat_calories` (schema-shape test via
  `CarbInput.model_fields.keys()`), confirming `fat_g` is absent.
- Passing `fat_g` as an extra field to `CarbInput` → `ValidationError`
  (`extra="forbid"`).
- Unit test asserting the calculator's residual formula uses
  `input.fat_calories` directly with no multiplication by 9 anywhere in
  the code path (static/code-review-level regression, e.g. a grep-based
  CI check for `fat_g` inside the carb calculator module).

---

# Final Contract

```python
CarbInput
    target_calories: int   # ge=0
    protein_g: int         # ge=0
    fat_calories: int      # ge=0  (authoritative; no fat_g field)

CarbResult
    status: CarbStatus                       # OK | INVALID
    carbohydrates_g: Optional[int]           # non-null iff OK
    carbohydrate_calories: Optional[int]     # non-null iff OK
    residual_calories: int                   # always non-null, may be negative
    issues: tuple[CarbIssueCode, ...]        # () on OK, (NEGATIVE_CARBOHYDRATE_RESIDUAL,) on INVALID
    policy_version: str                      # "carb-v1"
```

**All nullability rules, stated explicitly:**
- `status` — never null.
- `carbohydrates_g` — null **only** when `status == INVALID`; otherwise
  a non-null integer, including `0` when residual is exactly `0`.
- `carbohydrate_calories` — null **only** when `status == INVALID`;
  otherwise a non-null integer, including `0`.
- `residual_calories` — **never** null, on either status; may be
  negative only when `status == INVALID`.
- `issues` — never null; an empty tuple on `OK`, a single-element tuple
  on `INVALID`.
- `policy_version` — never null; fixed literal `"carb-v1"`.

---

# Final Locked Decisions

| Decision | Final Rule | Locked |
|----------|------------|--------|
| target_calories = 0 | `Field(..., ge=0)`; `0` is schema-valid; with zero upstream macro energy it yields `status=OK`, `carbohydrates_g=0`, `carbohydrate_calories=0`, `residual_calories=0` | YES |
| CarbStatus | Remains exactly `{OK, INVALID}`; no `INCOMPLETE`/`REVIEW_REQUIRED`/`ERROR` added, since schema failures never reach the calculator and clinical review is out of Layer A scope | YES |
| residual_calories on INVALID | Always populated (non-null), including negative values, for traceability; only `carbohydrates_g` and `carbohydrate_calories` are nulled on `INVALID` | YES |
| fat_calories source | `CarbInput` consumes `FatResult.fat_calories` directly; `fat_g` is never received and never recomputed inside the carb calculator | YES |

No new architecture and no new nutrition rules are introduced by this
addendum. All four points are confirmations of behavior already fully
specified in the carb-v1 document and its pseudo-Pydantic contracts.
