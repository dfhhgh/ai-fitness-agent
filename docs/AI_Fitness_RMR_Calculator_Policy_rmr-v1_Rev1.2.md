It looks like there is a layout display issue in your browser interface where the side document panel is blacked out or collapsed.

To solve this, here is the **COMPLETE Revision 1.2 Policy Document** printed directly below as standard chat text. You can select, copy, and paste it directly from this message into any text editor and save it as `AI_Fitness_RMR_Policy_Revision_1.2_Final.md`.

---

# AI Fitness — RMR Calculator Policy

## Phase 2.2.2 — Research & Policy Specification

### Revision 1.2 — Final

## 1. Executive Summary

This specification establishes the authoritative, deterministic policy rules for the Resting Metabolic Rate (RMR) Calculator module within the AI Fitness Nutrition Core. Designated under policy version `rmr-v1`, this module functions as a pure, stateless mathematical calculation engine. It computes a client's baseline resting energy expenditure without relying on probabilistic inference, large language models, machine learning, external databases, or silent fallback assumptions.

Revision 1.2 performs a targeted contract and test boundary cleanup on Revision 1.1, clarifying input schema boundaries, mapper responsibilities, non-numeric type validation translation, and non-finite floating-point error handling:

1. **Primary Active Method (Option C):** The Mifflin-St Jeor (1990) equation is selected as the sole active calculation method for `rmr-v1`. The `CUNNINGHAM` method interface is retained in system schemas purely as a secondary enumeration for future expansion, but remains inactive in `rmr-v1`.
2. **Strict 4-Field Input Contract (`RMRInput`):** The `RMRInput` schema is strictly typed and contains ONLY four attributes: `age`, `gender` (normalized biological sex), `height_cm`, and `weight_kg`. Arbitrary extra fields are not accepted by `RMRInput` itself.
3. **Mapper Boundary Isolation:** The rule that non-RMR fields (e.g., goal type, activity metrics, training frequency, training duration, occupation, daily movement, target body weight, InBody composition) do not affect RMR calculations is enforced at the `RMRMapper` integration boundary. The mapper extracts strictly the four required attributes from `NutritionAssessmentInput` to instantiate `RMRInput`.
4. **Input Boundary Type Validation Translation:** `RMRCalculator` receives a typed, normalized `RMRInput` object. Detecting raw primitive type violations (e.g., string `"eighty"` supplied for weight) occurs at the input/mapper boundary, which translates the type failure into the standardized RMR error contract (`status = ERROR` with issue code `INVALID_NUMERIC_TYPE`).
5. **Strict Enforcement of "No Silent Defaults":** If any required input attribute is missing or unpopulated, execution halts instantly and returns `status = INCOMPLETE` accompanied by the issue code `MISSING_RMR_DATA`. Defaulting missing values to population medians or implicit assumptions is strictly prohibited.
6. **Biological Sex Normalization Boundary:** The core equation requires biological sex parameters (+5 for males, -161 for females). The calculator accepts only normalized enum strings (`"MALE"` or `"FEMALE"`). Inferring biological sex from names, pronouns, free-form text, or body measurements is forbidden within this module and must be handled upstream.
7. **Engineering Input Validation Bounds:** Numeric validation ranges (18 to 120 for age, 50.0 to 250.0 cm for height, and 20.0 to 350.0 kg for weight) are defined explicitly as engineering input-validation bounds designed to intercept data-entry or normalization errors, rather than as medical diagnostic limits or absolute physiological survival boundaries.
8. **Adult System Scope Boundary:** The minimum supported age of 18 represents an explicit system scope and engineering policy decision for AI Fitness `rmr-v1`, reflecting that pediatric energy requirements require distinct growth-adjusted models. Supplying an age under 18 returns `status = INVALID` with issue code `UNDERAGE_NOT_SUPPORTED`.
9. **Explicit Half-Up Rounding Semantics:** Calculations execute in 64-bit double-precision floating-point arithmetic without intermediate rounding. The raw output is rounded to the nearest whole integer kcal/day (`rmr_kcal`) using explicit half-up logic (ties at exactly x.5 round upward in magnitude for non-negative values). Runtimes must explicitly implement half-up behavior rather than relying on language-default round-to-even semantics.
10. **Consistent Non-Finite Error Semantics:** Non-finite floating-point values (`NaN`, `+Infinity`, `-Infinity`) return `status = ERROR` with issue code `NUMERIC_OUT_OF_RANGE`.

---

## 2. RMR vs. BMR Terminology

### 2.1 Conceptual Definitions

* **Basal Metabolic Rate (BMR):** The minimal energy expenditure rate necessary to maintain basic cellular and organ function at complete rest. Clinical measurement requires strict laboratory conditions: immediately upon waking after 10–12 hours of overnight fasting, in a thermoneutral room, following prolonged physical recumbency without prior exertion.
* **Resting Metabolic Rate (RMR):** The energy expended at rest in a thermal neutral environment without requiring overnight clinical stay or prolonged fasting. RMR includes minor thermic effects from quiet digestion and postural adjustments, typically measuring 3% to 10% higher than clinical BMR.

### 2.2 Equation Measurement Context

The Mifflin-St Jeor (1990) equation was derived from indirect calorimetry measurements under resting conditions following an overnight fast. In dietetic literature and software systems, the terms BMR and Resting Energy Expenditure (REE / RMR) are used interchangeably when applying standard predictive formulas.

### 2.3 Terminology Decision for AI Fitness

1. **System Output Attribute:** The output attribute of this module is explicitly designated as `rmr_kcal`.
2. **Downstream Consumption:** Downstream components (e.g., Phase 2.2.3 TDEE Calculator) consume `rmr_kcal` directly as the baseline requirement to multiply against the Physical Activity Level factor ($TDEE = RMR \times PAL$).
3. **Operational Impact:** The minor historical distinction between clinical BMR and RMR has zero operational impact on downstream energy calculations, provided naming conventions remain uniform across system boundaries.

---

## 3. Scientific Evidence

The selection of the primary predictive equation for `rmr-v1` is supported by systematic reviews evaluating predictive equation accuracy against indirect calorimetry:

* **Mifflin MD, St Jeor ST, Hill LA, Scott BJ, Daugherty SA, Koh YO (1990):** "A new predictive equation for resting energy expenditure in healthy individuals." *American Journal of Clinical Nutrition*, 51(2):241-247. Derived from a sample of 498 healthy adult subjects (247 males, 251 females aged 19–78 years) across normal-weight and obese categories.
* **Frankenfield DC, Roth-Yousey L, Compher C (2005):** "Comparison of predictive equations for resting metabolic rate in healthy nonobese and obese adults: a systematic review." *Journal of the American Dietetic Association*, 105(5):775-789. Evaluated Harris-Benedict, Mifflin-St Jeor, Owen, and WHO/FAO/UNU equations. The systematic review established that the Mifflin-St Jeor equation was the most reliable, predicting RMR within $\pm 10\%$ of indirect calorimetry in 82% of non-obese adults and 70% of obese adults, with the narrowest error margin and minimal systematic bias.
* **Frankenfield DC (2013):** Re-validated Mifflin-St Jeor accuracy across 337 subjects, confirming that Mifflin-St Jeor remains statistically unbiased compared to alternative non-body-composition formulas.

The scientific evidence confirms Mifflin-St Jeor as the baseline predictive model for general adult populations when direct indirect calorimetry or validated fat-free mass data are unavailable.

---

## 4. Mifflin-St Jeor Equation

The exact mathematical formulation of the Mifflin-St Jeor equation is defined as:

$$\text{RMR}_{\text{raw}} = (10 \times \text{weight\_kg}) + (6.25 \times \text{height\_cm}) - (5 \times \text{age\_years}) + s$$

Where:

* $\text{weight\_kg}$ is total body mass in kilograms ($\text{kg}$, floating-point number).
* $\text{height\_cm}$ is stature in centimeters ($\text{cm}$, floating-point number).
* $\text{age\_years}$ is chronological age in years (integer or floating-point number).
* $s$ is the biological sex constant:
* $s = +5$ for males
* $s = -161$ for females



### 4.1 Canonical Worked Examples

* **Male Benchmark:** Age 30 years, Weight 80.0 kg, Height 180.0 cm:

$$\text{RMR} = (10 \times 80.0) + (6.25 \times 180.0) - (5 \times 30) + 5 = 1780 \text{ kcal/day}$$


* **Female Benchmark:** Age 30 years, Weight 80.0 kg, Height 180.0 cm:

$$\text{RMR} = (10 \times 80.0) + (6.25 \times 180.0) - (5 \times 30) - 161 = 1614 \text{ kcal/day}$$



---

## 5. Input Requirements

The `RMRInput` contract is strictly typed and contains ONLY the four fields required for baseline metabolic calculation:

| Field Name | Type | Accepted Range | Required | Usage in Calculation |
| --- | --- | --- | --- | --- |
| `age` | Integer / Float | $18 \le \text{age} \le 120$ | **Yes** | Multiplied by coefficient -5 |
| `gender` | String Enum | `"MALE"`, `"FEMALE"` | **Yes** | Selects biological sex constant $s$ (+5 vs -161) |
| `height_cm` | Float | $50.0 \le \text{height\_cm} \le 250.0$ | **Yes** | Multiplied by coefficient 6.25 |
| `weight_kg` | Float | $20.0 \le \text{weight\_kg} \le 350.0$ | **Yes** | Multiplied by coefficient 10.0 |

### 5.1 Integration Boundary & Explicitly Ignored Fields

The rule that non-RMR attributes do not affect calculations applies at the `RMRMapper` integration boundary. When processing a broader `NutritionAssessmentInput`, the `RMRMapper` extracts strictly `age`, `gender`, `height_cm`, and `weight_kg` to build `RMRInput`.

The following attributes present in broader intake structures MUST NOT influence the resulting `RMRInput` or `RMRResult`:

* `goal_type`, `target_weight_kg`, `weight_change_target_kg`
* `training_days_per_week`, `work_activity`, `training_duration_minutes`, `exercise_intensity`, `daily_movement`
* `activity_factor`, `activity_category`
* `assessment_date`
* `body_fat_percentage`, `InBody_data`

`RMRInput` itself remains a strict schema containing only the four mandatory fields.

---

## 6. Gender / Sex Normalization Boundary

The Mifflin-St Jeor equation requires binary biological sex inputs due to physiological differences in average muscle tissue ratio and organ metabolic density.

### 6.1 Normalization Rules

1. **Allowed Enumerations:** The calculator accepts only `"MALE"` or `"FEMALE"`.
2. **Handling Non-Standard Values:** Values other than `"MALE"` or `"FEMALE"` (e.g., `"OTHER"`, `"NON_BINARY"`, `"UNSPECIFIED"`, `"M"`, `"F"`, free-form Egyptian Arabic text, or `null`) trigger `status = INVALID` with issue code `UNSUPPORTED_GENDER`.
3. **Zero-Inference Principle:** The RMR calculator MUST NEVER attempt to infer biological sex from user names, voice transcripts, Egyptian Arabic dialogue, pronouns, or body measurements.
4. **Upstream Responsibility:** Normalizing raw intake selections or profile data into valid biological sex parameters is the exclusive responsibility of an upstream `RMRMapper` component prior to invoking `RMRCalculator`.

---

## 7. Validation Policy

Validation checks separate mathematical validity, input error trapping, and system scope enforcement.

| Input Field | Min Bound | Max Bound | Boundary Violation Result | Issue Code Triggered |
| --- | --- | --- | --- | --- |
| `age` | 18 | 120 | Out of Bounds | `UNDERAGE_NOT_SUPPORTED` (if <18), `INVALID_AGE` (if >120) |
| `height_cm` | 50.0 | 250.0 | Out of Bounds | `INVALID_HEIGHT` |
| `weight_kg` | 20.0 | 350.0 | Out of Bounds | `INVALID_WEIGHT` |

### 7.1 Engineering Input Validation Bounds Rationale

* **Data-Entry Error Trapping:** The boundaries (18–120 years, 50–250 cm, 20–350 kg) are engineering input-validation bounds designed to catch data-entry, normalization, or ingestion errors. They do not represent medical diagnostic limits or absolute human physiological limits. For instance, specifying height 50–250 cm means this range is the accepted input domain for `rmr-v1`, not a claim that humans cannot exist outside these height limits.
* **Adult System Scope Boundary (<18 years):** The original Mifflin-St Jeor study was conducted in adult populations (ages 19–78) and does not establish a pediatric equation. AI Fitness `rmr-v1` is explicitly an adult-only system scope. Supplying an age under 18 halts calculation with `status = INVALID` and issue code `UNDERAGE_NOT_SUPPORTED` as an explicit product boundary decision.
* **Upper Age Boundary (>120 years):** Serves as an engineering upper validation limit to intercept corrupt inputs, triggering `status = INVALID` and issue code `INVALID_AGE`.

---

## 8. Missing-Data Policy

To enforce the platform's "No Silent Defaults" principle, missing mandatory attributes halt evaluation immediately.

### 8.1 Incomplete Execution Protocol

If any required field (`age`, `gender`, `height_cm`, `weight_kg`) is `null`, missing, or unpopulated:

1. Execution halts immediately.
2. The calculator returns `status = INCOMPLETE`.
3. The `issues` array contains `["MISSING_RMR_DATA"]`.
4. Output calculation metrics (`rmr_kcal`, `rmr_method`) are set to `null`.

Defaulting missing fields to population medians (e.g., assuming an age of 30 or height of 170 cm) is strictly forbidden.

---

## 9. Error Policy

Structural violations, invalid primitive types, and non-finite floating-point values trigger error states.

### 9.1 Input Boundary Translation & Error Semantics

* **Input Boundary Type Validation (`INVALID_NUMERIC_TYPE`):** `RMRCalculator` receives a typed, normalized `RMRInput` payload. The mapper/input validation boundary intercepts raw non-numeric primitives (e.g., string `"eighty"` for weight) prior to constructing `RMRInput` and translates the failure into the standardized RMR error contract: `status = ERROR` with issue code `INVALID_NUMERIC_TYPE`.
* **Non-Finite Floating-Point Values (`NUMERIC_OUT_OF_RANGE`):** Supplying `NaN`, `+Infinity`, or `-Infinity` for numeric fields (`age`, `height_cm`, `weight_kg`) halts execution with `status = ERROR` and issue code `NUMERIC_OUT_OF_RANGE`. These values represent floating-point numeric types that are not finite valid numeric inputs.
* **Negative / Zero Numeric Values:** Negative or zero numeric values (e.g., `weight_kg = -50.0` or `height_cm = 0.0`) fail input domain boundary checks and return `status = INVALID` with issue code `INVALID_WEIGHT` or `INVALID_HEIGHT`.

---

## 10. Rounding Policy

The rounding policy establishes exact, deterministic precision mechanics:

1. **Internal Precision:** Calculations execute using 64-bit double-precision floating-point arithmetic (IEEE 754).
2. **No Intermediate Rounding:** Intermediate terms ($10 \times W$, $6.25 \times H$, $5 \times A$) MUST NOT be rounded prior to summation.
3. **Explicit Half-Up Rounding Mechanics:** The raw calculated value ($\text{RMR}_{\text{raw}}$) is rounded to the nearest integer kcal/day (`rmr_kcal`) using explicit round-half-up logic.
* Ties at exactly x.5 round upward in magnitude for non-negative RMR values.
* Example: $1234.49 \rightarrow 1234$
* Example: $1234.50 \rightarrow 1235$
* Example: $1234.51 \rightarrow 1235$


4. **Independent of Language Defaults:** Implementations MUST NOT rely on language-default `round()` implementations (such as Python's round-to-even / banker's rounding). Runtimes must explicitly implement half-up behavior.
5. **Final Output Precision:** Output precision is integer 1 kcal/day. Coarser rounding (e.g., nearest 10 kcal or 50 kcal) is forbidden within this module.

The execution sequence is strictly:

$$\text{raw Mifflin-St Jeor calculation} \longrightarrow \text{no intermediate rounding} \longrightarrow \text{final half-up rounding} \longrightarrow \text{integer } \text{rmr\_kcal}$$

---

## 11. InBody & Cunningham Analysis

### 11.1 Cunningham Equation Mechanics

The Cunningham (1980, 1991) equation calculates RMR as a direct function of Fat-Free Mass (FFM):

$$\text{RMR}_{\text{cunningham}} = 500 + (22 \times \text{FFM}_{\text{kg}})$$

Where $\text{FFM}_{\text{kg}} = \text{weight\_kg} \times \left(1 - \frac{\text{body\_fat\_percent}}{100}\right)$.

### 11.2 Evaluation of Bioelectrical Impedance Analysis (BIA)

While the Cunningham equation provides accuracy for lean athletes, its output depends on the accuracy of measured FFM. Consumer BIA devices (such as InBody) introduce variance driven by hydration, meal timing, and body temperature, yielding FFM error margins of $\pm 3\%$ to $5\%$.

### 11.3 Weight Precedence Boundary

In accordance with platform architecture:

* The RMR calculator DOES NOT evaluate body composition or resolve conflicts between profile weight and InBody weight.
* An upstream `RMRMapper` selects the authoritative `weight_kg` parameter.
* The RMR calculator accepts the supplied `weight_kg` as absolute truth.

---

## 12. Primary Method Decision

### 12.1 Evaluation of Method Options

* **Option A (Mifflin-St Jeor Only):** Implement Mifflin-St Jeor exclusively. Simplifies contract but removes schema extensibility.
* **Option B (Implement Both Simultaneously):** Automatically switch between Mifflin-St Jeor and Cunningham based on body fat availability. Rejected due to BIA hydration instability and silent branch switching risk.
* **Option C (Mifflin-St Jeor Primary; Cunningham Secondary Interface - SELECTED):** Implement Mifflin-St Jeor as the sole active calculation method for Phase 2.2.2 (`rmr-v1`). Retain `CUNNINGHAM` in the `RMRMethod` enum schema, but require explicit activation in future policy revisions when certified FFM protocols are deployed.

### 12.2 Explicit Decision

Phase 2.2.2 strictly implements **Option C**. The active method for `rmr-v1` is fixed to `MIFFLIN_ST_JEOR`.

---

## 13. Output Contract

The deterministic RMR result payload is defined by the `RMRResult` specification:

* `status` (string enum, required): Allowed values: `"OK"`, `"INCOMPLETE"`, `"INVALID"`, `"ERROR"`.
* `issues` (array of string enums, required): Allowed values: `"MISSING_RMR_DATA"`, `"UNSUPPORTED_GENDER"`, `"UNDERAGE_NOT_SUPPORTED"`, `"INVALID_AGE"`, `"INVALID_HEIGHT"`, `"INVALID_WEIGHT"`, `"INVALID_NUMERIC_TYPE"`, `"NUMERIC_OUT_OF_RANGE"`. Empty array `[]` when `status = OK`.
* `rmr_kcal` (integer or null, conditional): Calculated resting energy expenditure in kcal/day rounded to the nearest whole integer using half-up logic. Populated when `status = OK`, null otherwise.
* `rmr_method` (string enum or null, conditional): Active calculation method (`"MIFFLIN_ST_JEOR"`). Populated when `status = OK`, null otherwise.
* `policy_version` (string, required): Active policy tracking string (`"rmr-v1"`).

### 13.1 Success and Failure Payload Contract

* **Successful Execution (`status = OK`):**
* `rmr_kcal`: integer (e.g., `1780`)
* `rmr_method`: `"MIFFLIN_ST_JEOR"`
* `policy_version`: `"rmr-v1"`
* `issues`: `[]`


* **Failure Execution (`status = INCOMPLETE | INVALID | ERROR`):**
* `rmr_kcal`: `null`
* `rmr_method`: `null`
* `policy_version`: `"rmr-v1"`
* `issues`: `["ISSUE_CODE_1", ...]`



---

## 14. Status Model

The RMR calculator adopts a four-tier status model consistent with platform standards:

| Primary Status | Condition Description | Output `rmr_kcal` | Output `rmr_method` |
| --- | --- | --- | --- |
| **`OK`** | All required inputs are valid and present. Calculation completed successfully. | Integer (e.g., 1780) | `"MIFFLIN_ST_JEOR"` |
| **`INCOMPLETE`** | Required fields (`age`, `gender`, `height_cm`, `weight_kg`) are null/missing. | null | null |
| **`INVALID`** | Inputs violate domain validation bounds (underage, out-of-bounds, unsupported gender). | null | null |
| **`ERROR`** | Structural payload invalid, non-numeric primitive types, or non-finite floats (`NaN`, `Infinity`). | null | null |

The primary status contract DOES NOT include `WARNING` or `REVIEW_REQUIRED`. Downstream Nutrition Safety modules handle clinical warnings separately.

---

## 15. Uncertainty and Limitations

1. **Standard Error of Estimate:** Predictive RMR equations carry an inherent physiological estimation error of $\pm 10\%$ ($\pm 150-200 \text{ kcal/day}$) relative to indirect calorimetry.
2. **Severe Obesity ($\text{BMI} \ge 40 \text{ kg/m}^2$):** Fat mass contributes less metabolic activity per unit weight than lean mass, leading to potential RMR overestimation of $5\%-10\%$.
3. **Geriatric Sarcopenia (>65 years):** Age-related muscle loss may cause Mifflin-St Jeor to overestimate RMR slightly in older adults.
4. **Metabolic Adaptation:** The equation reflects baseline cross-sectional population averages and cannot account for active metabolic adaptation resulting from prolonged caloric restriction.

---

## 16. Science vs. Engineering Decisions

To preserve auditability, policy rules are classified by grounding rationale:

* **Evidence-Supported Scientific Facts:**
* Biological sex constant differential (+5 male vs -161 female).
* Mifflin-St Jeor weighting factors ($10 \times \text{weight}$, $6.25 \times \text{height}$, $-5 \times \text{age}$).
* BMR vs RMR clinical definition distinctions.


* **Evidence-Informed Methodological Choices:**
* Selection of Mifflin-St Jeor over Harris-Benedict based on meta-analysis accuracy (82% vs 69%).
* Deferring Cunningham activation due to BIA hydration variability.


* **Pure System Engineering Conventions:**
* Adult-only system scope ($age \ge 18$).
* Engineering input validation bounds (18–120 age, 50–250 cm height, 20–350 kg weight).
* Option C decision (implementing `MIFFLIN_ST_JEOR` primary while preserving `CUNNINGHAM` enum schema).
* Explicit half-up rounding to nearest integer 1 kcal/day.
* Policy versioning (`"rmr-v1"`).
* Four-tier status classification (`OK`, `INCOMPLETE`, `INVALID`, `ERROR`) and specific issue code naming.



---

## 17. Policy Versioning

This specification defines policy version `rmr-v1`.

### Version Control Rules

* The output attribute `policy_version` MUST be populated with `"rmr-v1"` for all responses.
* Any modification to underlying coefficients, validation boundaries, default method selection, or rounding algorithms mandates a major version update (e.g., `rmr-v2`) to preserve auditability of historical metabolic plans.

---

## 18. Test Specification

The automated test suite for Phase 2.2.2 executes 35 deterministic test cases:

| Test ID | Purpose / Description | Input `age` | Input `gender` | Input `height_cm` | Input `weight_kg` | Expected `rmr_kcal` | Expected `status` | Expected `issues` Array |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| **TC-01** | Standard Male Benchmark | 30 | `"MALE"` | 180.0 | 80.0 | 1780 | `OK` | `[]` |
| **TC-02** | Standard Female Benchmark | 30 | `"FEMALE"` | 180.0 | 80.0 | 1614 | `OK` | `[]` |
| **TC-03** | Young Adult Male | 25 | `"MALE"` | 175.0 | 70.0 | 1674 | `OK` | `[]` |
| **TC-04** | Young Adult Female | 25 | `"FEMALE"` | 165.0 | 60.0 | 1345 | `OK` | `[]` |
| **TC-05** | Boundary Min Age (18) | 18 | `"MALE"` | 170.0 | 65.0 | 1628 | `OK` | `[]` |
| **TC-06** | Boundary Max Age (120) | 120 | `"FEMALE"` | 150.0 | 50.0 | 677 | `OK` | `[]` |
| **TC-07** | Boundary Min Height (50.0 cm) | 40 | `"MALE"` | 50.0 | 50.0 | 618 | `OK` | `[]` |
| **TC-08** | Boundary Max Height (250.0 cm) | 40 | `"FEMALE"` | 250.0 | 100.0 | 2202 | `OK` | `[]` |
| **TC-09** | Boundary Min Weight (20.0 kg) | 50 | `"MALE"` | 180.0 | 20.0 | 1080 | `OK` | `[]` |
| **TC-10** | Boundary Max Weight (350.0 kg) | 50 | `"FEMALE"` | 180.0 | 350.0 | 4214 | `OK` | `[]` |
| **TC-11** | Underage Minor (17 yr) | 17 | `"MALE"` | 175.0 | 70.0 | null | `INVALID` | `["UNDERAGE_NOT_SUPPORTED"]` |
| **TC-12** | Pediatric Age (0 yr) | 0 | `"FEMALE"` | 50.0 | 3.5 | null | `INVALID` | `["UNDERAGE_NOT_SUPPORTED"]` |
| **TC-13** | Exceed Max Age (121 yr) | 121 | `"MALE"` | 170.0 | 65.0 | null | `INVALID` | `["INVALID_AGE"]` |
| **TC-14** | Below Min Height (49.9 cm) | 30 | `"FEMALE"` | 49.9 | 50.0 | null | `INVALID` | `["INVALID_HEIGHT"]` |
| **TC-15** | Exceed Max Height (250.1 cm) | 30 | `"MALE"` | 250.1 | 80.0 | null | `INVALID` | `["INVALID_HEIGHT"]` |
| **TC-16** | Below Min Weight (19.9 kg) | 30 | `"FEMALE"` | 160.0 | 19.9 | null | `INVALID` | `["INVALID_WEIGHT"]` |
| **TC-17** | Exceed Max Weight (350.1 kg) | 30 | `"MALE"` | 180.0 | 350.1 | null | `INVALID` | `["INVALID_WEIGHT"]` |
| **TC-18** | Missing Age Parameter | null | `"MALE"` | 180.0 | 80.0 | null | `INCOMPLETE` | `["MISSING_RMR_DATA"]` |
| **TC-19** | Missing Gender Parameter | 30 | null | 180.0 | 80.0 | null | `INCOMPLETE` | `["MISSING_RMR_DATA"]` |
| **TC-20** | Missing Height Parameter | 30 | `"MALE"` | null | 80.0 | null | `INCOMPLETE` | `["MISSING_RMR_DATA"]` |
| **TC-21** | Missing Weight Parameter | 30 | `"FEMALE"` | 180.0 | null | null | `INCOMPLETE` | `["MISSING_RMR_DATA"]` |
| **TC-22** | Non-Binary Gender Enum | 30 | `"OTHER"` | 180.0 | 80.0 | null | `INVALID` | `["UNSUPPORTED_GENDER"]` |
| **TC-23** | Unspecified Gender String | 30 | `"UNKNOWN"` | 180.0 | 80.0 | null | `INVALID` | `["UNSUPPORTED_GENDER"]` |
| **TC-24** | Unnormalized Single Char | 30 | `"M"` | 180.0 | 80.0 | null | `INVALID` | `["UNSUPPORTED_GENDER"]` |
| **TC-25** | Negative Age Value | -10 | `"FEMALE"` | 160.0 | 55.0 | null | `INVALID` | `["INVALID_AGE"]` |
| **TC-26** | Negative Height Value | 30 | `"MALE"` | -170.0 | 70.0 | null | `INVALID` | `["INVALID_HEIGHT"]` |
| **TC-27** | Negative Weight Value | 30 | `"FEMALE"` | 160.0 | -55.0 | null | `INVALID` | `["INVALID_WEIGHT"]` |
| **TC-28** | Rounding Below Half (.4875) | 30 | `"FEMALE"` | 180.078 | 80.0 | 1614 | `OK` | `[]` |
| **TC-29** | Exact Half-Up Rounding (.50) | 30 | `"MALE"` | 180.08 | 80.0 | 1781 | `OK` | `[]` |
| **TC-30** | Rounding Above Half (.5125) | 30 | `"MALE"` | 180.082 | 80.0 | 1781 | `OK` | `[]` |
| **TC-31** | Floating Point NaN Input | NaN | `"MALE"` | 180.0 | 80.0 | null | `ERROR` | `["NUMERIC_OUT_OF_RANGE"]` |
| **TC-32** | Floating Point Positive Infinity | 30 | `"FEMALE"` | 180.0 | Infinity | null | `ERROR` | `["NUMERIC_OUT_OF_RANGE"]` |
| **TC-33** | Non-Numeric Primitive Type | 30 | `"MALE"` | 180.0 | `"eighty"` | null | `ERROR` | `["INVALID_NUMERIC_TYPE"]` |
| **TC-34** | Mapper Isolation Test | 30 | `"MALE"` | 180.0 | 80.0 | 1780 | `OK` | `[]` |
| **TC-35** | Floating Point Negative Infinity | 30 | `"MALE"` | 180.0 | -Infinity | null | `ERROR` | `["NUMERIC_OUT_OF_RANGE"]` |

### 18.1 Detailed Context for Input & Mapper Boundary Tests

* **TC-33 (Non-Numeric Type Validation):** Tested at the mapper/input boundary. Supplying `"eighty"` for `weight_kg` fails primitive type validation before `RMRInput` instantiation, producing an externally observable result of `status = ERROR` and `issues = ["INVALID_NUMERIC_TYPE"]`.
* **TC-34 (Mapper Boundary Isolation):** Evaluates two identical physical sets of facts (30 yr, `"MALE"`, 180.0 cm, 80.0 kg) supplied in `NutritionAssessmentInput` objects with completely different non-RMR fields (e.g., `goal_type = "WEIGHT_LOSS"` vs `"MUSCLE_GAIN"`, `training_days_per_week = 0` vs `6`, or presence of `InBody_data`). The `RMRMapper` extracts identical `RMRInput` objects, yielding identical `RMRResult` outputs (`rmr_kcal = 1780`).
* **TC-35 (Negative Infinity Handling):** Supplying `-Infinity` for numeric fields yields `status = ERROR` and `issues = ["NUMERIC_OUT_OF_RANGE"]`.

---

## 19. Integration Boundary

The RMR calculator functions as an isolated node within the AI Fitness Nutrition Core architecture:

1. **ClientProfile / Assessment Intake Data:** Broad user facts and intake survey responses are ingested.
2. **RMRMapper:** An upstream mapper component extracts strictly the 4 required fields (`age`, `gender`, `height_cm`, `weight_kg`), normalizes biological sex to `"MALE"` or `"FEMALE"`, and translates raw type errors into `INVALID_NUMERIC_TYPE`.
3. **RMRInput:** A strictly typed 4-field payload (`age`, `gender`, `height_cm`, `weight_kg`) is instantiated.
4. **RMRCalculator:** The stateless, deterministic Mifflin-St Jeor engine computes baseline resting expenditure.
5. **RMRResult:** A structured payload containing `status`, `issues`, `rmr_kcal`, `rmr_method`, and `policy_version` is produced.
6. **TDEECalculator:** Downstream calculator consumes `rmr_kcal` alongside `activity_factor` from Phase 2.2.1b (`ActivityClassifier`).

The RMR calculator remains completely decoupled from activity factors, goal targets, and macronutrient distribution.

---

## 20. Final Implementation Checklist

Confirm:

* [✓] Terminology strictly defines output as `rmr_kcal`.
* [✓] Mifflin-St Jeor equation verified: Male +5, Female -161 constants.
* [✓] Option C selected: Mifflin-St Jeor primary for `rmr-v1`.
* [✓] Input contract `RMRInput` is strict and contains exactly four fields (`age`, `gender`, `height_cm`, `weight_kg`).
* [✓] Extra broader-profile fields handled and filtered at `RMRMapper` boundary.
* [✓] No silent defaults: missing inputs return `status = INCOMPLETE`.
* [✓] Biological sex strictly normalized to `"MALE"` or `"FEMALE"`.
* [✓] Zero inference rule enforced for gender mapping.
* [✓] Age 18 minimum defined as adult system scope boundary.
* [✓] Validation bounds (18–120 age, 50–250 cm height, 20–350 kg weight) defined as engineering input validation bounds.
* [✓] Raw non-numeric types translated to `INVALID_NUMERIC_TYPE` at input boundary.
* [✓] `NaN` returns `NUMERIC_OUT_OF_RANGE`.
* [✓] `+Infinity` returns `NUMERIC_OUT_OF_RANGE`.
* [✓] `-Infinity` returns `NUMERIC_OUT_OF_RANGE`.
* [✓] Double-precision arithmetic with explicit round-half-up logic to nearest whole integer kcal/day.
* [✓] Genuine x.50 half-up rounding test included in test vectors.
* [✓] Weight precedence handled strictly by upstream mapper.
* [✓] Status model adheres strictly to `OK`, `INCOMPLETE`, `INVALID`, `ERROR`.
* [✓] Policy version tagged as `"rmr-v1"`.
* [✓] TC-34 tests mapper/integration isolation rather than arbitrary extra fields in `RMRInput`.
* [✓] TC-35 tests negative infinity.
* [✓] Test specification includes 35 deterministic test cases.
* [✓] Architecture strictly decoupled from activity factors and macro distribution.
* [✓] Document is fully implementation-ready for software engineering execution.