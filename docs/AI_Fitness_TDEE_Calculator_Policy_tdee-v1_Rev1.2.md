# AI Fitness TDEE Calculator Policy Specification

**Policy Version:** `tdee-v1`

**Revision:** Rev 1.2

**Status:** REVIEW READY

**Target File Path:** `docs/nutrition/AI_Fitness_TDEE_Calculator_Policy_tdee-v1_Rev1.2.md`

---

## 1. Document Metadata

| Metadata Field | Specification Value |
| --- | --- |
| Policy Name | AI Fitness TDEE Calculator Policy |
| Policy Identifier | `tdee-v1` |
| Document Revision | Rev 1.2 |
| Status | REVIEW READY |
| Scope | AI Fitness Core Engine Phase 2.2.3 (TDEE Calculation Node) |
| Authoritative Target | Deterministic Python Core (`Pydantic` v2 Contracts) |
| Upstream Dependencies | Phase 2.2.1 Activity Policy v1, Phase 2.2.2 RMR Policy `rmr-v1` |
| Downstream Dependents | Phase 2.3 Calorie Target Engine |

---

## 2. Executive Summary

This engineering policy specification establishes the deterministic execution rules, contract boundaries, validation requirements, status semantics, error propagation hierarchy, and test matrix for Phase 2.2.3 (TDEE Calculator) of the AI Fitness platform.

The TDEE Calculator (`tdee-v1`) is a pure, stateless, deterministic composition node within the Nutrition Core pipeline. It consumes validated output domain objects from upstream services—specifically `RMRResult` from `rmr-v1` and `ActivityClassificationResult` from `Activity Policy v1`—and performs fixed-point decimal multiplication to compute Total Daily Energy Expenditure (TDEE) in integer kilocalories per day (`kcal/day`).

Revision 1.2 enforces strict architectural separation between **Layer A (Input Contract Validation)** and **Layer B (Calculator Domain Logic)**. Schema violations, missing contract fields, malformed primitive types, and forbidden extra fields are handled strictly as `Pydantic` boundary validation failures (`ValidationError`). Domain business logic in `TDEECalculator` operates exclusively on valid `TDEEInput` objects, handling upstream operational statuses using a deterministic precedence hierarchy (`ERROR > INVALID > INCOMPLETE`), converting float multipliers to fixed-point `Decimal` instances via string boundaries, and executing exact `ROUND_HALF_UP` quantization.

---

## 3. Scope

The scope of this policy specification is restricted to:

1. Defining the strict `TDEEInput`, `TDEEResult`, and `TDEETraceability` `Pydantic` v2 data contracts.
2. Defining the exact boundary validation obligations enforced by `Pydantic` v2 prior to domain execution.
3. Specifying the error propagation precedence hierarchy and domain validation logic executed by `TDEECalculator`.
4. Specifying the mathematical multiplication and final rounding semantics using Python's `Decimal` module with `ROUND_HALF_UP`.
5. Providing a two-layer test matrix covering schema contract failures separately from domain calculation scenarios.

---

## 4. Non-Goals

To preserve strict domain boundaries, `tdee-v1` explicitly excludes the following functionalities:

* No RMR Calculation: `tdee-v1` MUST NOT evaluate predictive BMR/RMR formulas (e.g., Mifflin-St Jeor, Harris-Benedict, Cunningham, Katch-McArdle) or recalculate RMR under any condition.


* No Activity Classification: `tdee-v1` MUST NOT parse exercise logs, step counts, lifestyle surveys, or select activity factors independently.
* No Caloric Target Adjustments: `tdee-v1` MUST NOT apply weight-loss deficits, weight-gain surpluses, goal-based rate-of-change adjustments, or clinical safety floors.
* No Macronutrient Distribution: `tdee-v1` MUST NOT calculate protein, carbohydrate, fat, or fiber targets.
* No Direct Body Composition Ingestion: `tdee-v1` MUST NOT consume InBody or bioelectrical impedance (BIA) raw metrics (e.g., Body Fat %, Lean Mass, Visceral Fat).


* No Non-Deterministic Operations: `tdee-v1` MUST NOT invoke Large Language Models (LLMs), query databases, make network API calls, generate random variables, or read system clocks.

---

## 5. Architectural Position

The `TDEECalculator` occupies a downstream composition position within the deterministic Nutrition Core pipeline:

* Pipeline Input: The orchestration layer receives a `NutritionAssessmentInput` payload.
* Upstream Ingestion: The orchestrator routes relevant payload fragments to `ActivityClassifier` (Phase 2.2.1) and `RMRMapper` -> `RMRCalculator` (Phase 2.2.2).
* Upstream Evaluation:
* `ActivityClassifier` evaluates lifestyle responses and outputs an authoritative `ActivityClassificationResult`.
* `RMRCalculator` computes resting metabolism and outputs an authoritative `RMRResult`.


* Contract Packaging: The orchestrator packages both domain result payloads into a `TDEEInput` instance.
* Schema Validation (Layer A): `Pydantic` v2 validates `TDEEInput` structural integrity. Schema failures immediately raise `ValidationError`.
* Domain Execution (Layer B): Validated `TDEEInput` is passed to `TDEECalculator`, which evaluates upstream statuses, executes decimal multiplication, and produces `TDEEResult`.
* Downstream Routing: The orchestrator forwards `TDEEResult` to the Calorie Target Engine.

---

## 6. Source-of-Truth Boundaries

The architecture enforces single-source-of-truth ownership across all pipeline components:

* RMR Ownership: `RMRCalculator` (`rmr-v1`) is the sole authority for resting metabolic expenditure. `TDEECalculator` treats `rmr_result.rmr_kcal` as an immutable scalar.


* Activity Ownership: `ActivityClassifier` (`Activity Policy v1`) is the sole authority for physical activity categories and multipliers. `TDEECalculator` treats `activity_result.activity_factor` as an immutable scalar.
* Arithmetic Ownership: `TDEECalculator` (`tdee-v1`) owns exclusively the fixed-precision arithmetic composition:

$$\text{TDEE} = \text{RMR} \times \text{ActivityFactor}$$

* Downstream Target Ownership: The Calorie Target Engine owns all goal adjustments, deficits, surpluses, and clinical safety thresholds.

---

## 7. Layer A: Input Contract Specification & Boundary Validation

The `TDEECalculator` input boundary is governed by `TDEEInput`. Structural and type validation occur at the contract boundary before business logic execution begins.

### Field Specifications for `TDEEInput`

| Field Name | Type Contract | Required | Metadata / Deterministic | Description |
| --- | --- | --- | --- | --- |
| `rmr_result` | `RMRResult` | Yes | Deterministic | Authoritative result payload from `rmr-v1` |
| `activity_result` | `ActivityClassificationResult` | Yes | Deterministic | Authoritative result payload from Activity Policy v1 |
| `correlation_id` | `Optional[str]` | No | Metadata Only | Tracking identifier for request tracing across services |

### Contract Configuration Rules

* Schema Configuration: Enforce `model_config = ConfigDict(extra="forbid", frozen=True)` using `Pydantic` v2.
* Non-Optional Required Fields: `rmr_result` and `activity_result` MUST NOT be typed as `Optional`. They are mandatory, non-null domain objects.
* Correlation ID Behavior: `correlation_id` is classified strictly as non-authoritative metadata. Passing, modifying, or omitting `correlation_id` MUST NOT alter arithmetic calculation or status outcome.

### Layer A Validation Boundary Semantics

If an incoming payload violates `TDEEInput` schema specifications (e.g., missing required fields, `None` supplied for `rmr_result` or `activity_result`, malformed primitive data types, or injected extra fields):

1. `Pydantic` v2 MUST raise a `pydantic.ValidationError`.
2. The pipeline MUST NOT catch schema failures to fabricate a `TDEEResult` object.
3. Schema validation failures represent contract integration bugs outside the jurisdiction of `TDEECalculator` domain status codes.

---

## 8. Layer B: TDEECalculator Domain Logic & Upstream Status Propagation

Once a valid `TDEEInput` object passes Layer A contract validation, it is supplied to `TDEECalculator`. The calculator evaluates the operational status of both upstream result objects.

### Short-Circuit Execution Rule

If either `rmr_result.status` or `activity_result.status` is not `OK`, `TDEECalculator` MUST immediately halt execution without performing mathematical calculations.

### Error Severity Precedence Hierarchy

When both upstream result objects report non-OK operational statuses, the overall status assigned to `TDEEResult.status` is dictated by the following strict precedence hierarchy:

$$\text{ERROR} > \text{INVALID} > \text{INCOMPLETE}$$

### Status Mapping Resolution Matrix

| Upstream `RMRResult.status` | Upstream `ActivityResult.status` | Resolved `TDEEResult.status` | Action & Output Behavior |
| --- | --- | --- | --- |
| `OK` | `OK` | `OK` | Execute calculation; return populated integer `tdee_kcal`. |
| `INCOMPLETE` | `OK` | `INCOMPLETE` | Short-circuit; return `tdee_kcal = None`. |
| `OK` | `INCOMPLETE` | `INCOMPLETE` | Short-circuit; return `tdee_kcal = None`. |
| `INCOMPLETE` | `INCOMPLETE` | `INCOMPLETE` | Short-circuit; return `tdee_kcal = None`. |
| `INVALID` | `OK` | `INVALID` | Short-circuit; return `tdee_kcal = None`. |
| `OK` | `INVALID` | `INVALID` | Short-circuit; return `tdee_kcal = None`. |
| `INVALID` | `INCOMPLETE` | `INVALID` | Short-circuit (`INVALID` overrides `INCOMPLETE`); return `tdee_kcal = None`. |
| `INCOMPLETE` | `INVALID` | `INVALID` | Short-circuit (`INVALID` overrides `INCOMPLETE`); return `tdee_kcal = None`. |
| `INVALID` | `INVALID` | `INVALID` | Short-circuit; return `tdee_kcal = None`. |
| `ERROR` | `OK` / `INCOMPLETE` / `INVALID` | `ERROR` | Short-circuit (`ERROR` overrides all); return `tdee_kcal = None`. |
| `OK` / `INCOMPLETE` / `INVALID` | `ERROR` | `ERROR` | Short-circuit (`ERROR` overrides all); return `tdee_kcal = None`. |
| `ERROR` | `ERROR` | `ERROR` | Short-circuit; return `tdee_kcal = None`. |

### Issue Code Aggregation Principles

When short-circuiting due to upstream non-OK statuses:

1. Local Context Assignment: Append `UPSTREAM_RMR_NOT_OK` if `rmr_result.status != OK`. Append `UPSTREAM_ACTIVITY_NOT_OK` if `activity_result.status != OK`.
2. Upstream Code Inheritance: Inherit all issue code strings present in `rmr_result.issues` and `activity_result.issues`.
3. Deduplication: Preserve insertion order while removing duplicate issue strings.

---

## 9. Domain Validation Rules

When both upstream results report `status == OK`, `TDEECalculator` performs domain-level numeric and presence validation on the contained values before executing arithmetic.

### Domain Validation Matrix

| Validation ID | Parameter Evaluated | Trigger Condition | Assigned Status | Generated Issue Code |
| --- | --- | --- | --- | --- |
| `VAL-001` | `rmr_result.rmr_kcal` | Field is `None` in an `OK` `rmr_result` | `ERROR` | `MISSING_RMR_VALUE` |
| `VAL-002` | `activity_result.activity_factor` | Field is `None` in an `OK` `activity_result` | `ERROR` | `MISSING_ACTIVITY_FACTOR_VALUE` |
| `VAL-003` | `rmr_result.rmr_kcal` | `rmr_kcal <= 0` | `INVALID` | `RMR_VALUE_NON_POSITIVE` |
| `VAL-004` | `activity_result.activity_factor` | `activity_factor <= 0.0` | `INVALID` | `ACTIVITY_FACTOR_NON_POSITIVE` |
| `VAL-005` | `rmr_kcal` / `activity_factor` | Value is `NaN`, `+Infinity`, or `-Infinity` | `ERROR` | `NON_FINITE_INPUT` |

### Explicit Removal of Duplicate Biological Bounds and Factor Tables

* Biological Bounds: `RMRCalculator` (`rmr-v1`) owns physiological range validation for RMR inputs. `TDEECalculator` MUST NOT duplicate RMR range checks (e.g., rejecting RMR < 500), preserving single-source-of-truth ownership.


* Activity Factor Tables: `ActivityClassifier` (Activity Policy v1) owns the physical activity factor lookup table (`1.20`, `1.35`, `1.55`, `1.75`). `TDEECalculator` accepts any finite, positive numeric factor passed from an `OK` activity classification result.

---

## 10. Decimal Arithmetic Boundary

To eliminate IEEE 754 floating-point representation artifacts during multiplication, conversion of the activity factor to Python's `Decimal` type must pass through string conversion at the boundary.

### Boundary Conversion Semantics

When `activity_factor` is supplied as a floating-point primitive (`float`), direct casting via `Decimal(activity_factor)` introduces binary representation artifacts (e.g., `1.35` becomes `1.350000000000000088817841970012523233890533447265625`).

`tdee-v1` requires explicit string-based conversion:

$$\text{factor\_dec} = \text{Decimal}(\text{str}(\text{activity\_factor}))$$

$$\text{rmr\_dec} = \text{Decimal}(\text{rmr\_kcal})$$

This boundary conversion guarantees that a float multiplier of `1.35` translates exactly to `Decimal('1.35')`.

---

## 11. TDEE Formula and Rounding Policy

### Mathematical Formula

$$TDEE_{\text{raw}} = \text{rmr\_dec} \times \text{factor\_dec}$$

$$TDEE_{\text{final}} = \text{int}(\text{quantize}(TDEE_{\text{raw}}, \text{Decimal}('1'), \text{rounding}=\text{ROUND\_HALF\_UP}))$$

### Rounding Policy Directives

1. Zero Intermediate Rounding: $TDEE_{\text{raw}}$ must be computed across full decimal precision. No truncation or rounding is permitted prior to final quantization.
2. Quantization Mode: Final rounding must utilize `ROUND_HALF_UP` semantics. Fractional values of exactly $.5000...$ round away from zero to the next higher integer.
3. Final Type Conversion: The quantized Decimal value is converted to Python's built-in `int` (arbitrary-precision integer).

### Exact Rounding Behavior Examples

| Consumed RMR (`kcal`) | Consumed Activity Factor | Exact $TDEE_{\text{raw}}$ Product | Fractional Boundary | Applied Rounding | Final `tdee_kcal` |
| --- | --- | --- | --- | --- | --- |
| `1613` | `1.55` | `2500.15` | Below $.5$ | Round Down | `2500` |
| `1510` | `1.35` | `2038.50` | Exact $.5$ | Round Up | `2039` |
| `1425` | `1.35` | `1923.75` | Above $.5$ | Round Up | `1924` |
| `1780` | `1.20` | `2136.00` | Whole Integer | No Adjustment | `2136` |

---

## 12. Output Contract Specification

The `TDEECalculator` returns a deterministic output payload, `TDEEResult`.

### Field Specifications for `TDEEResult`

| Field Name | Type Contract | Nullable in `OK` State | Nullable in Non-`OK` State | Description |
| --- | --- | --- | --- | --- |
| `status` | `Status` Enum | No | No | Operational calculation status (`OK`, `INCOMPLETE`, `INVALID`, `ERROR`) |
| `tdee_kcal` | `Optional[int]` | No | Must be `None` | Calculated Total Daily Energy Expenditure in integer kcal/day |
| `rmr_kcal_used` | `Optional[int]` | No | Must be `None` | Integer RMR value consumed from `rmr_result` |
| `activity_factor_used` | `Optional[Decimal]` | No | Must be `None` | Exact `Decimal` activity factor consumed from `activity_result` |
| `activity_category_used` | `Optional[ActivityCategory]` | No | Must be `None` | `ActivityCategory` enum consumed from `activity_result` |
| `issues` | `List[str]` | No | No | Aggregated list of issue code strings |
| `policy_version` | `str` | No | No | Constant policy version identifier string (`"tdee-v1"`) |
| `traceability` | `Optional[TDEETraceability]` | No | Must be `None` | Structured audit trail object tracking calculation parameters |

### Strict Nullability Rule for Non-OK States

When `status != Status.OK`:

* `tdee_kcal` MUST be `None`.
* `rmr_kcal_used` MUST be `None`.
* `activity_factor_used` MUST be `None`.
* `activity_category_used` MUST be `None`.
* `traceability` MUST be `None`.
* Fabricated fallback values, default factors, or partial calculation results are strictly prohibited.

---

## 13. Traceability Contract

To support clinical auditing and automated verification without compromising functional determinism, `TDEEResult` includes a structured `TDEETraceability` object when status is `OK`.

### Field Specifications for `TDEETraceability`

| Traceability Field | Type Contract | Sample Value | Description |
| --- | --- | --- | --- |
| `rmr_kcal_used` | `int` | `1780` | Exact integer RMR consumed |
| `activity_factor_used` | `str` | `"1.55"` | String representation of `Decimal` factor used |
| `raw_tdee_unrounded` | `str` | `"2759.00"` | Unrounded decimal product string |
| `formula_expression` | `str` | `"TDEE = RMR * ActivityFactor"` | Literal mathematical formula expression |
| `rounding_mode` | `str` | `"ROUND_HALF_UP"` | Quantization strategy applied |
| `policy_version` | `str` | `"tdee-v1"` | Policy version identifier string |

### Deterministic Timestamp Prohibition

`TDEETraceability` and `TDEEResult` MUST NOT include execution timestamps or dynamic system clock references. Timestamps break functional idempotency ($f(x) \equiv f(x)$) and invalidate automated test equality assertions. Timestamps belong exclusively to external orchestration logging infrastructures.

---

## 14. Determinism Requirements

1. Pure Functional Contract: The `TDEECalculator` MUST be implemented as a pure, side-effect-free function.
2. Identical Input Guarantee: For any two invocations with structurally identical `TDEEInput` payloads, the calculator MUST produce identical `TDEEResult` payloads.
3. System Isolation: Calculation logic MUST NOT depend on database connections, network I/O, system clocks, environment variables, or probabilistic machine learning models.

---

## 15. Error and Issue Codes

Standardized string issue codes generated or propagated by `tdee-v1`:

| Issue Code | Category | Associated Status | Description / Cause |
| --- | --- | --- | --- |
| `UPSTREAM_RMR_NOT_OK` | Propagation | Inherited | `RMRResult.status` is not `OK` |
| `UPSTREAM_ACTIVITY_NOT_OK` | Propagation | Inherited | `ActivityClassificationResult.status` is not `OK` |
| `MISSING_RMR_VALUE` | Domain Integrity | `ERROR` | `rmr_kcal` is `None` in an `OK` RMR result |
| `MISSING_ACTIVITY_FACTOR_VALUE` | Domain Integrity | `ERROR` | `activity_factor` is `None` in an `OK` activity result |
| `RMR_VALUE_NON_POSITIVE` | Numeric Boundary | `INVALID` | `rmr_kcal` is less than or equal to 0 |
| `ACTIVITY_FACTOR_NON_POSITIVE` | Numeric Boundary | `INVALID` | `activity_factor` is less than or equal to 0.0 |
| `NON_FINITE_INPUT` | Arithmetic | `ERROR` | Numeric input evaluates to `NaN` or `Infinity` |

---

## 16. Test Matrix

The test matrix is divided into **Layer A (Contract Validation Tests)** and **Layer B (Calculator Domain Tests)**.

### Layer A: TDEEInput Contract Validation Tests (Schema Boundary)

| Test ID | Scenario Category | Input Payload Variation | Expected Outcome | Verification Objective |
| --- | --- | --- | --- | --- |
| `CT-001` | Missing Field | `rmr_result` omitted or set to `None` | `pydantic.ValidationError` | Verify required non-optional contract for `rmr_result` |
| `CT-002` | Missing Field | `activity_result` omitted or set to `None` | `pydantic.ValidationError` | Verify required non-optional contract for `activity_result` |
| `CT-003` | Malformed Type | `rmr_result = "1780"` (String primitive) | `pydantic.ValidationError` | Verify schema type rejection for invalid RMR payload |
| `CT-004` | Malformed Type | `activity_result = {}` (Empty dict) | `pydantic.ValidationError` | Verify schema type rejection for invalid Activity payload |
| `CT-005` | Extra Field | `extra_field = "unauthorized"` injected | `pydantic.ValidationError` | Verify strict extra-field rejection (`extra="forbid"`) |
| `CT-006` | Metadata Type | `correlation_id = 12345` (Integer primitive) | `pydantic.ValidationError` | Verify strict string type checking for metadata field |

### Layer B: TDEECalculator Domain Tests (Business Logic)

| Test ID | Scenario Category | Input Parameters & Upstream Statuses | Expected Status | Expected `tdee_kcal` | Expected Issue Codes | Rationale / Verification Objective |
| --- | --- | --- | --- | --- | --- | --- |
| `DT-001` | Happy Path | RMR=1780 (OK), Factor=1.20 (OK) | `OK` | `2136` | `[]` | Standard Sedentary calculation |
| `DT-002` | Happy Path | RMR=1780 (OK), Factor=1.35 (OK) | `OK` | `2403` | `[]` | Standard Light activity calculation |
| `DT-003` | Happy Path | RMR=1780 (OK), Factor=1.55 (OK) | `OK` | `2759` | `[]` | Standard Moderate activity calculation |
| `DT-004` | Happy Path | RMR=1780 (OK), Factor=1.75 (OK) | `OK` | `3115` | `[]` | Standard High activity calculation |
| `DT-005` | Upstream State | RMR Status=INCOMPLETE, Activity Status=OK | `INCOMPLETE` | `None` | `["UPSTREAM_RMR_NOT_OK", ...]` | Propagation of upstream INCOMPLETE RMR |
| `DT-006` | Upstream State | RMR Status=OK, Activity Status=INCOMPLETE | `INCOMPLETE` | `None` | `["UPSTREAM_ACTIVITY_NOT_OK", ...]` | Propagation of upstream INCOMPLETE Activity |
| `DT-007` | Upstream State | RMR Status=INVALID, Activity Status=OK | `INVALID` | `None` | `["UPSTREAM_RMR_NOT_OK", ...]` | Propagation of upstream INVALID RMR |
| `DT-008` | Upstream State | RMR Status=OK, Activity Status=INVALID | `INVALID` | `None` | `["UPSTREAM_ACTIVITY_NOT_OK", ...]` | Propagation of upstream INVALID Activity |
| `DT-009` | Upstream State | RMR Status=ERROR, Activity Status=OK | `ERROR` | `None` | `["UPSTREAM_RMR_NOT_OK", ...]` | Propagation of upstream ERROR RMR |
| `DT-010` | Upstream State | RMR Status=OK, Activity Status=ERROR | `ERROR` | `None` | `["UPSTREAM_ACTIVITY_NOT_OK", ...]` | Propagation of upstream ERROR Activity |
| `DT-011` | Error Precedence | RMR Status=INVALID, Activity Status=INCOMPLETE | `INVALID` | `None` | `["UPSTREAM_RMR_NOT_OK", "UPSTREAM_ACTIVITY_NOT_OK", ...]` | Verify `INVALID` overrides `INCOMPLETE` |
| `DT-012` | Error Precedence | RMR Status=INCOMPLETE, Activity Status=INVALID | `INVALID` | `None` | `["UPSTREAM_RMR_NOT_OK", "UPSTREAM_ACTIVITY_NOT_OK", ...]` | Verify `INVALID` overrides `INCOMPLETE` regardless of order |
| `DT-013` | Error Precedence | RMR Status=ERROR, Activity Status=INVALID | `ERROR` | `None` | `["UPSTREAM_RMR_NOT_OK", "UPSTREAM_ACTIVITY_NOT_OK", ...]` | Verify `ERROR` overrides `INVALID` |
| `DT-014` | Field Integrity | RMR Status=OK (`rmr_kcal = None`), Factor=1.55 | `ERROR` | `None` | `["MISSING_RMR_VALUE"]` | Handling missing numeric field in OK RMR object |
| `DT-015` | Field Integrity | RMR=1780 (OK), Activity Status=OK (`factor = None`) | `ERROR` | `None` | `["MISSING_ACTIVITY_FACTOR_VALUE"]` | Handling missing factor field in OK Activity object |
| `DT-016` | Numeric Safety | RMR=0 (OK), Factor=1.55 (OK) | `INVALID` | `None` | `["RMR_VALUE_NON_POSITIVE"]` | Non-positive RMR rejection |
| `DT-017` | Numeric Safety | RMR=-1500 (OK), Factor=1.55 (OK) | `INVALID` | `None` | `["RMR_VALUE_NON_POSITIVE"]` | Negative RMR rejection |
| `DT-018` | Numeric Safety | RMR=1780 (OK), Factor=0.0 (OK) | `INVALID` | `None` | `["ACTIVITY_FACTOR_NON_POSITIVE"]` | Zero activity factor rejection |
| `DT-019` | Numeric Safety | RMR=1780 (OK), Factor=-1.35 (OK) | `INVALID` | `None` | `["ACTIVITY_FACTOR_NON_POSITIVE"]` | Negative activity factor rejection |
| `DT-020` | Numeric Safety | RMR=NaN, Factor=1.55 (OK) | `ERROR` | `None` | `["NON_FINITE_INPUT"]` | NaN RMR rejection |
| `DT-021` | Numeric Safety | RMR=1780 (OK), Factor=+Infinity | `ERROR` | `None` | `["NON_FINITE_INPUT"]` | Infinity activity factor rejection |
| `DT-022` | Decimal Conversion | RMR=1000 (OK), Factor=1.35 (`float` representation) | `OK` | `1350` | `[]` | Exact string boundary conversion (`1000 * Decimal('1.35')`) |
| `DT-023` | Rounding Below | RMR=1613 (OK), Factor=1.55 (Raw: 2500.15) | `OK` | `2500` | `[]` | Rounding down when fractional part is below .5 |
| `DT-024` | Rounding Exact | RMR=1510 (OK), Factor=1.35 (Raw: 2038.50) | `OK` | `2039` | `[]` | `ROUND_HALF_UP` on exact x.500 boundary |
| `DT-025` | Rounding Above | RMR=1425 (OK), Factor=1.35 (Raw: 1923.75) | `OK` | `1924` | `[]` | Rounding up when fractional part is above .5 |
| `DT-026` | Metadata Isolation | Valid inputs + `correlation_id="test-123"` vs `None` | `OK` | Both `2759` | `[]` | `correlation_id` does not affect arithmetic |

---

## 17. Invariants and Property-Based Tests

Implementations of `tdee-v1` must satisfy the following mathematical invariants:

1. Baseline Maintenance Floor Invariant: For all valid positive inputs where $\text{ActivityFactor} \ge 1.00$:

$$\text{TDEE} \ge \text{RMR}$$

2. Monotonic Activity Invariant: Holding RMR strictly constant, increasing the activity factor MUST NOT decrease TDEE:

$$\text{factor}_2 > \text{factor}_1 \implies \text{TDEE}(\text{RMR}, \text{factor}_2) \ge \text{TDEE}(\text{RMR}, \text{factor}_1)$$

3. Monotonic RMR Invariant: Holding the activity factor strictly constant, increasing RMR MUST NOT decrease TDEE:

$$\text{RMR}_2 > \text{RMR}_1 \implies \text{TDEE}(\text{RMR}_2, \text{factor}) \ge \text{TDEE}(\text{RMR}_1, \text{factor})$$

4. Correlation ID Invariance: For any valid `TDEEInput` payload $I$ and arbitrary metadata strings $c_1, c_2$:

$$\text{TDEECalculator}(I[\text{correlation\_id}=c_1]) \equiv \text{TDEECalculator}(I[\text{correlation\_id}=c_2])$$

5. Goal & InBody Isolation Invariance: Supplying or modifying external goal selections or InBody body composition metrics in upstream contexts MUST NOT alter `TDEECalculator` arithmetic, as TDEE depends strictly upon `rmr_kcal` and `activity_factor`.

---

## 18. Integration Architecture & Workflow

The integration topology across upstream services and downstream target engines proceeds as follows:

* Upstream RMR Source: `RMRCalculator` (`rmr-v1`) owns RMR calculation and output validation, producing an authoritative `RMRResult`.
* Upstream Activity Source: `ActivityClassifier` (Activity Policy v1) owns activity survey classification and multiplier selection, producing an authoritative `ActivityClassificationResult`.
* Composition Node: `TDEECalculator` (`tdee-v1`) consumes `TDEEInput` (wrapping `RMRResult` and `ActivityClassificationResult`), owns exact arithmetic composition ($RMR \times ActivityFactor$), and produces `TDEEResult`.

The orchestration workflow executes sequentially:

1. Extract `RMRResult` and `ActivityClassificationResult` from upstream context.
2. Construct `TDEEInput(rmr_result=rmr_res, activity_result=act_res, correlation_id=trace_id)`. If schema validation fails, handle `pydantic.ValidationError`.
3. Pass `TDEEInput` to `calculate_tdee(input_data)`.
4. Inspect `TDEEResult.status`. If `OK`, extract `tdee_kcal` for downstream target calculations. If non-OK, route aggregated `issues` to system diagnostic handlers.

---

## 19. Cross-Phase Compatibility Findings

Prior to finalizing Revision 1.2, a compatibility audit was conducted against Phase 2.2.1 (Activity Policy v1), Phase 2.2.2 (RMR Policy `rmr-v1`), and Core specifications:

* Finding 1 (Precision Alignment): RMR Policy `rmr-v1` uses `ROUND_HALF_UP` for final RMR output rounding. `tdee-v1` aligns perfectly by utilizing `Decimal` string boundary conversion and `ROUND_HALF_UP` quantization for final TDEE output rounding.
* Finding 2 (Status Model Alignment): RMR Policy `rmr-v1` and Activity Policy v1 utilize the status enum set (`OK`, `INCOMPLETE`, `INVALID`, `ERROR`). `tdee-v1` adopts this exact enum structure without introducing divergent status names.
* Finding 3 (Boundary Ownership): RMR Policy `rmr-v1` enforces biological bounds on age, weight, and height. `tdee-v1` respects this boundary by removing duplicate RMR/TDEE biological range checks.


* Finding 4 (Determinism Alignment): `rmr-v1` and Activity Policy v1 execute pure deterministic functions. `tdee-v1` maintains pipeline purity by removing timestamps from domain results.

---

## 20. Implementation Mapping Guidelines

When converting this policy specification into executable Python code using `Pydantic` v2:

1. Pydantic Models:
* Define `TDEEInput` with non-optional fields `rmr_result: RMRResult`, `activity_result: ActivityClassificationResult`, and optional `correlation_id: Optional[str] = None`. Enforce `model_config = ConfigDict(extra="forbid", frozen=True)`.
* Define `TDEETraceability` with string and integer fields representing calculation metadata.
* Define `TDEEResult` with fields `status: Status`, `tdee_kcal: Optional[int]`, `rmr_kcal_used: Optional[int]`, `activity_factor_used: Optional[Decimal]`, `activity_category_used: Optional[ActivityCategory]`, `issues: List[str]`, `policy_version: str = "tdee-v1"`, `traceability: Optional[TDEETraceability]`.


2. Calculator Function Execution:
* Evaluate `rmr_result.status` and `activity_result.status`. Apply precedence (`ERROR > INVALID > INCOMPLETE`). If non-OK, return `TDEEResult` with null outputs and aggregated inherited issues.
* Check numeric field presence (`rmr_kcal`, `activity_factor`).
* Perform string-decimal conversion: `factor_dec = Decimal(str(activity_result.activity_factor))`.
* Multiply: `raw_tdee = Decimal(rmr_result.rmr_kcal) * factor_dec`.
* Quantize: `final_tdee = int(raw_tdee.quantize(Decimal("1"), rounding=ROUND_HALF_UP))`.
* Construct and return `TDEEResult` with `status = Status.OK`.



---

## 21. Deferred / Out of Scope & Future Extensions

* Dynamic Exercise Energy Add-ons (`tdee-v2` Candidate): Evaluating architectural models to ingest discrete wearable exercise expenditure (e.g., Apple Health / Garmin workouts) as structured additive inputs to baseline TDEE.
* Clinical Life-Stage Offsets (`tdee-v2` Candidate): Investigating standardized offset parameters for pregnancy or lactation energy demands.


* Empirical TDEE Calibration (`tdee-v2` Candidate): Assessing 3-week exponential smoothing trend algorithms to adjust calculated baseline TDEE against empirical body mass changes and logged dietary energy intake.



---

## 22. Revision History

| Revision | Release Status | Primary Policy Changes |
| --- | --- | --- |
| Rev 1.0 | DRAFT | Initial research specification draft. Included duplicate biological bounds, hardcoded activity factor tables, and timestamps in traceability metadata. |
| Rev 1.1 | REVIEW READY | Complete architectural revision. Removed duplicate biological bounds and activity factor tables. Enforced string conversion for `Decimal` activity factors. Established error precedence hierarchy (`ERROR` > `INVALID` > `INCOMPLETE`). Removed timestamps to guarantee determinism. Expanded test matrix. |
| Rev 1.2 | REVIEW READY | Resolved contract validation layer vs calculator logic layer ambiguities. Moved schema failures (`rmr_result = None`, malformed types, extra fields) to Layer A contract tests expecting `Pydantic ValidationError`. Clarified Python arbitrary-precision `int` conversion. Corrected cross-phase compatibility statement regarding final RMR output rounding in `rmr-v1`. |

---

## 23. Revision 1.2 Final Review Checklist

* [x] **Contract Validation Layer Separation**: Schema failures (`None` required fields, wrong primitive types, forbidden extra fields) are explicitly defined as Layer A `pydantic.ValidationError` events.
* [x] **Missing-Result Test Matrix Reorganization**: Moved `rmr_result = None` and `activity_result = None` out of `TDEECalculator` domain tests into Layer A contract validation tests (`CT-001` and `CT-002`).
* [x] **Two Distinct Test Layers**: Test matrix is cleanly bifurcated into Layer A (Schema Validation Tests) and Layer B (Domain Calculation Tests).
* [x] **Integer Type Description Correctness**: Replaced "64-bit integer" with "Python's built-in `int` (arbitrary-precision integer)".
* [x] **Cross-Phase Compatibility Accuracy**: Correctly described `rmr-v1` rounding as applying `ROUND_HALF_UP` to final RMR output rounding.
* [x] **Upstream Policy Preservation**: Zero modifications or re-interpretations made to locked Activity Policy v1 or RMR Policy `rmr-v1`.
* [x] **Fixed-Point Precision Boundary**: Retained `Decimal(str(activity_factor))` for binary float representation safety.
* [x] **Status Precedence Hierarchy**: Retained `ERROR > INVALID > INCOMPLETE` short-circuiting precedence.
* [x] **Exact-Half Rounding Verification**: Preserved $1510 \times 1.35 = 2038.50 \rightarrow 2039$ (`ROUND_HALF_UP`).
* [x] **Deterministic Output Guarantee**: Confirmed zero system clock timestamps or dynamic state exist in `TDEEResult` or `TDEETraceability`.