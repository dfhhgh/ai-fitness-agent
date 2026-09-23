# **Calorie Goal Calculator Policy Specification (Phase 2.2.4)**

## **1\. Title**

Engineering and Scientific Policy Specifications for the Calorie Target Calculator within the food core of the AI Sports Platform.

## **2\. Status**

**LOCKED / IMPLEMENTATION READY**  
This specification is the final reference and authoritative source of truth for the execution of code by Claude Code. The arithmetic, contractual, and architectural rules contained therein may not be exceeded without undergoing rigorous formal architectural review. This policy is designed to ensure absolute determinism in calculations, with a complete separation between basic business logic and generative models.

## **3\. Policy ID**

The official identifier approved for this component within the system is. This identifier must be used in all trace records, data structures, and APIs to ensure compatibility with the Food Kernel's version management system.calorie-v1

## **4\. Review**

This revision document (Rev1.2) represents the policies of Phase 2.2.4. This revision adds an explicit post-calculation domain invariant: a derived target of `target_calories_kcal <= 0` is rejected with `status = ERROR`, `target_calories_kcal = null`, and issue `NEGATIVE_OR_ZERO_TARGET`, evaluated before the low-calorie review rule. Positive targets below 1200 kcal remain valid and continue to receive the existing Engineering Review Trigger flag. This revision introduces no calorie floor and no high-calorie threshold, and it preserves the prior consensus on failure semantics, strict structural verification, and engineering-only safety thresholds.

## **5\. Executive Summary**

The Calorie Goal Calculator is an essential core component that lies at the heart of Nutrition Core. Its exclusive role is to receive the approved value of total daily energy expenditure (TDEE) along with the user-defined "target type," and then apply a deterministic mathematical transformation to produce the "daily calorie goal."  
One of the most important pillars of this policy is the decisive security and engineering decision to reject the application of the so-called "hidden floor" of calories. Instead of restricting a score that falls below 1200 calories silently, the calculator presents the exact mathematical score as is. Based on the first version's conservative Engineering Policy, the calculator generates a safety flag called the Engineering Review Trigger. This procedure leaves the final medical assessment and contextual decisions (such as age, gender, and medical condition) to the upper echelons of the systemLOW\_CALORIE\_REVIEW\_REQUIRED1.

## **6\. Scope**

The scope of this calculator is limited to tasks that ensure that it works as a pure function3. The scope includes receiving deterministic inputs limited to the result of total daily energy expenditure (TDEEResult) and set goal (GoalType), and applying mathematical calorie adjustment based on . The scope also includes generating the output structure and evaluating the resulting value mathematically to generate the low-calorie review safety flag. All of these processes must take place in an environment completely isolated from any external influences.calorie-v1

## **7\. Out of range**

Applying the principle of single responsibility4, the calculator does not calculate or recalculate the BMR, activity factor, or total daily expenditure (TDEE).  
This calculator does not deal with Target Weight or InBody data, nor does it account for macros. Advanced nutrition strategies such as Carb Cycling, Dynamic Energy-Balance Modeling, or percentage-based adjustments are excluded in this version (V1).

## **8\. Architectural Structure and Compatibility**

The Calorie Goal Calculator acts as a purely mathematical conversion node that is fully compliant with the previous policies:

* The activity classification has an exclusive policy.activity-v1  
* The Basal Metabolic Rate (BMR) execution context has an exclusive policy (Revision 1.2).rmr-v1  
* The Total Daily Energy Expenditure (TDEE) context has an exclusive policy (Revision 1.2) where .tdee-v1TDEE \= RMR × ActivityFactor  
* The calorie calculator exclusively has a formula: .Target Calories \= TDEE \+ Goal Adjustment

This calculator may not examine the raw data of the activity or interfere with the output of the previous components.

## **9\. The Source of Truth and Ownership**

The Calorie Goal Calculator treats outputs as absolute facts and only builds on them. There is no other unit in the system that is authorized to adjust or recalculate the final calorie goal.TDEECalculator

## **10\. Input Contract**

The deterministic input contract is designed to include only the essential elements required. Strict Pydantic Validation is enforced using the . Any attempt to pass unsupported fields (e.g., ) will inevitably lead to immediate structural failure, and will not be ignored in silence.extra="forbid"target\_weight

| Field | Type | Mandatory | Description |
| ----: | ----: | ----- | ----- |
| tdee\_result | TDEEResult | yes | Approved object for daily spending. Its value is structurally wrong.None |
| goal\_type | GoalType | yes | Target type. Its non-availability is a structural error, and it does not assume a silent alternative target. |
| correlation\_id | String | no | An optional ID for tracking records doesn't affect accounts. |

## **11\. Goal Mapping**

As a V1 operational baseline parameter, the component applies a deterministic fixed adjustment to translate each goal into a numerical modification:

| GoalType | Modification (kcal) |
| ----: | ----- |
| maintenance | 0 |
| weight\_loss | \-500 |
| weight\_gain | \+500 |
| muscle\_gain | \+500 |

These fixed differences (±500) represent V1 operational baseline parameters chosen to avoid mathematical complexity, and should not be considered universal physiological laws or guaranteed weight-change rates.

## **12\. Equation**

The only deterministic mathematical equation adopted: Target Calories \= TDEE \+ Calorie Adjustment

## **13\. Digital Accounts**

The calculator relies exclusively on correct calculations (Integer Arithmetic) to ensure accuracy and avoid floating-point problems5. The end result must be an integer (Integer). The Decimal library is not allowed, and no type of implicit rounding or non-integer scaling (e.g., rounding to the nearest 10\) is allowed. The calculation is done accurately: .target \= tdee \+ adjustment

## **14\. Failure Semantics & Validation**

Architectural policy makes a clear and decisive distinction between two levels of verification and error:

### **Layer A — Structural Contract Validation**

This layer uses strict check(). The system issues an error of a type and refuses to complete the implementation in the following cases:Pydanticextra="forbid"ValidationError

* Absence of an object (if it is).tdee\_resulttdee\_result=None  
* Absence of a goal type or submission of a goal that is not in the valid list.Enum  
* Pass any additional fields that are not supported (such as or ).target\_weightage

### **Layer B — Calculator Domain Logic**

If the structure is intact, the status of the incoming objects is checked:

* **Upstream Status Propagation:**  
  * If the case is, the calculation continues.TDEEResultOK  
  * If it is his condition, the calculator is issued.INCOMPLETEINCOMPLETE  
  * If it is his condition, the calculator is issued.INVALIDINVALID  
  * If it is his condition, the calculator is issued.ERRORERROR  
* **Mathematical verification (input):** If the TDEE object has a status of OK but has a non-positive value (zero or less) or a non-finite value (NaN, +Infinity, -Infinity), the calculator returns `status = ERROR` and does not produce a valid numerical target. This check validates the TDEE input value; TDEE value validity remains owned by the `tdee-v1` policy.
* **Post-calculation target validity (output domain invariant):** After computing `target_calories_kcal = TDEE + Goal Adjustment`, the calculator MUST validate the derived target before applying any safety flag. If `target_calories_kcal <= 0`, the result is `status = ERROR`, `target_calories_kcal = null`, and `issues` contains exactly `NEGATIVE_OR_ZERO_TARGET`. This validation MUST be evaluated BEFORE the low-calorie review rule in Section 15. Regardless of the upstream reason for a low positive TDEE, the Calorie Target calculator MUST NOT emit a non-positive calorie target. This is an engineering/domain invariant of the Calorie Target layer that protects its own output domain; it is not a claim that a clinical guideline explicitly defines this exact software rule, and it does not add, modify, or reinterpret any RMR or TDEE validation rule.
* **Missing Target:** The absence of a goal type is programmatically treated as a structural error within Class A. The goal of "maintenance" is never assumed in the absence of an actual objective.

## **15\. Low-Calorie Review Policy**

This rule applies only AFTER the Section 14 post-calculation validity check has accepted a positive derived target (`target_calories_kcal > 0`). Non-positive targets never reach this rule; they are rejected upstream with `NEGATIVE_OR_ZERO_TARGET`.

The low-calorie rule has been reformulated to clarify its role as an issue-specific "Engineering Review Trigger," not as a universal physiological or medical minimum.calorie-v1  

**If `0 < target_calories_kcal < 1200`:**

* status = OK.  
* Keep the exact mathematical target (e.g., 1199, 1000, or 1) — all are mathematically positive and therefore valid outputs of this calculator under the existing rule, unless another policy explicitly rejects them.  
* **Do not** clamp or raise the value to 1200 (No clamping).  
* Append `LOW_CALORIE_REVIEW_REQUIRED` to `safety_flags`.  
* Maintain the final result as a mathematically accurate value available to the upper layers.

**If `target_calories_kcal >= 1200`:**

* status = OK.  
* No low-calorie safety flag is added; `safety_flags` remains empty for this rule.

The number 1200 represents a conservative, context-limited engineering review threshold chosen for this foundational component that lacks awareness of physiological data (such as gender or age). It is NOT a physiological minimum, NOT a universal clinical minimum, and NOT a calorie floor. Positive values below 1200 remain mathematically valid, are preserved exactly, and are routed to upper review layers solely via the flag. This policy introduces no minimum positive calorie floor. The higher Safety/Review layer in the system will later use this tag to integrate into the broader clinical context.

**Zero and negative target semantics:** A zero-calorie value is not accepted as a derived daily calorie target by this general nutrition-planning calculator. Fasting and other zero-intake interventions are distinct physiological/intervention contexts and are outside the responsibility of the Calorie Target calculation. Negative dietary energy intake is not a meaningful dietary calorie target within the nutrition-planning domain. The purpose of the invariant is to prevent this calculator from producing a non-actionable target for downstream nutrition planning — not to assert that zero calorie intake is universally invalid in nutrition.

## **16\. Output Contract**

The structure is designed to include only the fields that this calculator owns. If the calculation is unsuccessful, the final target value is null.CalorieTargetResult

| Field | Description and Significance |
| ----: | ----- |
| status | Implementation Status: , , , .OKINCOMPLETEINVALIDERROR |
| target\_calories\_kcal | The correct and accurate mathematical result of the daily goal (Nullable; null when status is not OK, including when the post-calculation invariant rejects `target <= 0`). |
| tdee\_kcal\_used | Original daily spend value used. |
| goal\_type\_used | The type of goal used in the calculation. |
| calorie\_adjustment\_kcal | Actual mathematical adjustment applied (example: \-500). |
| policy\_version | Fixed: .calorie-v1 |
| issues | A text list of logical error codes from layer B (if any), including `NEGATIVE_OR_ZERO_TARGET` when the post-calculation invariant rejects a non-positive target. |
| safety\_flags | A matrix to insert into it when necessary.LOW\_CALORIE\_REVIEW\_REQUIRED |
| traceability | Deterministic trace data (e.g. ). Completely free of timestamps.correlation\_id |

## **17\. Architectural Constants (Invariants)**

* **Determinism and repetition:** Repeating the execution of a function with the same input produces the same output accurately without any deviation.  
* **Metadata isolation:** Manipulation of a field that does not affect the flow of operations at all.correlation\_id  
* **Proper logical order:** For the same TDEE adopted: Strictly.weight\_loss \< maintenance \< weight\_gain  
* **Non-positive target rejection (post-calculation invariant):** For any accepted result (`status = OK`), `target_calories_kcal > 0`. If `target_calories_kcal <= 0`, then `status = ERROR`, `target_calories_kcal = null`, and `issues` contains `NEGATIVE_OR_ZERO_TARGET`. This check runs before the low-calorie review rule. No calorie floor is implied: every positive target remains acceptable, including values below 1200.

## **18\. Test Matrix**

### **Structural Contract Tests**

All of these conditions should result in (failing to):ValidationErrorPydantic

* tdee\_result \= None (Absence of the Being).  
* goal\_type \= None (or the absence of a field).  
* Pass an unsupported value in (Enum validation).goal\_type  
* Passing an unsupported field such as ().target\_weight \= 75extra="forbid"

### **Layer B Tests (Domain Logic)**

* **The Right Response:**  
  * TDEE OK (2500) \+ maintenance ➔ , .target \= 2500status \= OK  
  * TDEE OK (2500) \+ weight\_loss ➔ , .target \= 2000status \= OK  
  * TDEE OK (2500) \+ weight\_gain ➔ , .target \= 3000status \= OK  
  * TDEE OK (2500) \+ muscle\_gain ➔ , .target \= 3000status \= OK  
* **Upstream Propagation:**  
  * TDEE INCOMPLETE ➔ The calculator returns.INCOMPLETE  
  * TDEE INVALID ➔ The calculator returns.INVALID  
  * TDEE ERROR ➔ The calculator returns.ERROR  
* **TDEE Errors (input):**  
  * TDEE is non-positive (zero or less) ➔ ERROR  
  * TDEE is non-finite (NaN, +Infinity, -Infinity) ➔ ERROR  
* **Post-calculation Target Validity (Rev1.2):** (validation evaluated BEFORE the low-calorie rule)  
  * TDEE = 500, goal = weight\_loss (adjustment -500) ➔ target = 0 ➔ status = ERROR, target = null, issue = `NEGATIVE_OR_ZERO_TARGET`  
  * TDEE = 400, goal = weight\_loss (adjustment -500) ➔ target = -100 ➔ status = ERROR, target = null, issue = `NEGATIVE_OR_ZERO_TARGET`  
  * TDEE = 1699, goal = weight\_loss (adjustment -500) ➔ target = 1199 ➔ status = OK, target = 1199, safety\_flags = [`LOW_CALORIE_REVIEW_REQUIRED`]  
  * TDEE = 1700, goal = weight\_loss (adjustment -500) ➔ target = 1200 ➔ status = OK, target = 1200, safety\_flags = []  
  * TDEE = 1500, goal = weight\_loss (adjustment -500) ➔ target = 1000 ➔ status = OK, target = 1000, safety\_flags = [`LOW_CALORIE_REVIEW_REQUIRED`]  
  * TDEE = 2000, goal = maintenance (adjustment 0) ➔ target = 2000 ➔ status = OK, target = 2000, safety\_flags = []  
  * TDEE = 2000, goal = weight\_gain (adjustment +500) ➔ target = 2500 ➔ status = OK, target = 2500, safety\_flags = []  
* **Threshold 1200 (Engineering Trigger; applies only to positive targets):**  
  * TDEE \= 1700, Goal weight\_loss ➔ Mathematical Goal \= 1200, safety\_flags blank  
  * TDEE \= 1699, Goal weight\_loss ➔ Mathematical Goal \= 1199, insert `LOW_CALORIE_REVIEW_REQUIRED`  
  * TDEE \= 1500, Goal weight\_loss ➔ Sporting Goal \= 1000 (No Clamp Restriction), insert `LOW_CALORIE_REVIEW_REQUIRED`

## **19\. Scientific Basis vs. Engineering Decisions**

This document clearly distinguishes between contextual scientific evidence and the deterministic engineering decisions adopted in this edition:

### **A. Scientific Context & Evidence**

* **Energy Deficit:** Classical research (e.g., Wishnofsky, 1958) has shown that a pound of adipose tissue contains approximately 3,500 calories. However, dynamic models of modern energy balance led by Kevin Hall (National Institutes of Health) have demonstrated that the assumption that a 500-calorie deficit will lead to linear and sustained weight loss is an overestimation of about 100% long-term outcomes due to metabolic adaptation.  
* **Heat Excess and Muscle Hypertrophy:** General sports nutrition literature suggests that providing a calorie surplus of 250 to 500 calories can provide a supportive environment for increasing lean mass in conjunction with resistance training. The ISSN position stand on diets and body composition supports the principle that a controlled surplus supports lean mass gains, but does not explicitly codify 250–500 kcal as a universal standard.  
* **Clinical threshold of 1200:** Clinical obesity management guidelines (e.g., NICE CG189, NIH/NHLBI) indicate that diets providing 1000–1200 kcal/day for women (or slightly higher for men) often require medical supervision to ensure nutritional adequacy.  
* **Dietary intake vs. energy balance:** Established nutritional and physiological concepts distinguish dietary energy intake from energy balance. A negative energy balance does not imply negative dietary energy intake. Very-low-energy dietary interventions still prescribe positive energy intake values. Fasting is a distinct physiological/intervention context with its own supervisory requirements.

### **B. Engineering Decisions for V1**

Based on the strict distinction between comprehensive science and software limitations, this policy declares the following courses for V1:

1. **Fixed adjustment (±500):** Adjusting by 500 kcal/day up or down (to lose or gain weight/muscle) is a **V1 operational baseline parameter** and should not be interpreted as a universal physiological law or guaranteed weight-loss rate.  
2. **Review threshold (1200):** The number 1200 is used as a V1 Engineering Review Trigger to compensate for the absence of clinical context in this component. It does not represent a medical diagnosis or a fixed global minimum that applies equally to both genders. It is not a calorie floor: positive targets below 1200 remain valid outputs and are preserved exactly.  
3. **Non-positive target invariant (`target <= 0`):** For calorie-v1, a derived `target_calories_kcal <= 0` is defined as an invalid output of the Calorie Target domain and returns `status = ERROR` with issue `NEGATIVE_OR_ZERO_TARGET` and `target_calories_kcal = null`. This is an engineering/domain invariant, strongly consistent with established nutritional concepts, and is **not** a claim that a clinical guideline (WHO, NICE, NIH, or any other authority) explicitly defines this exact software behavior. A zero-calorie value is not accepted as a derived daily calorie target by this general nutrition-planning calculator; fasting remains a distinct intervention context outside this calculator's responsibility. Negative dietary energy intake is not a meaningful dietary calorie target in the nutrition-planning domain. No minimum positive calorie floor is introduced: every positive target, including 1 kcal, remains subject only to the existing low-calorie review rule unless another policy explicitly rejects it.

## **20\. Integration Workflow**

The calculator integrates into the purely mathematical core path. After generating the final value of the spending, it is received via the structural contract. The calculation is done and the result is passed on to the macronutrient calculators. Finally, an independent Nutrition Safety Layer makes a reading to take appropriate action (e.g., requesting a human audit), while maintaining the transparency of the calculation produced by this calculator.TDEECalculatorTDEEResultGoalTypeCalorieTargetResultsafety\_flags

## **21\. Revision History**

* **Rev 1.0:** Policy Foundation Version (partially repealed).  
* **Rev 1.1:**  
  * Removed the unsupported universal >3500 kcal/day high-calorie review rule.  
  * Reframed the 1200 kcal/day threshold as an Engineering Review Trigger, stripping it of medical minimum claims.  
  * Enforced strict structural verification (Pydantic `extra="forbid"`) to reject redundant fields and convert absent `tdee_result` into a Layer A structural error.  
  * Clarified the distinction between structural contract errors (Layer A) and domain logic errors (Layer B).  
  * Separated contextual scientific evidence from V1 deterministic engineering decisions.  
* **Rev 1.2 (current version):**  
  * Added an explicit post-calculation target validity invariant: after `target_calories_kcal = TDEE + Goal Adjustment`, a derived value of `target_calories_kcal <= 0` returns `status = ERROR`, `target_calories_kcal = null`, and issue `NEGATIVE_OR_ZERO_TARGET`, evaluated before the low-calorie review rule.  
  * Non-positive calculated targets now produce ERROR; positive targets below 1200 remain allowed and continue to receive the existing `LOW_CALORIE_REVIEW_REQUIRED` review flag with exact value preservation.  
  * No calorie floor was introduced: 1200 kcal remains an engineering review threshold only, and every positive target (including 1 kcal) stays valid under the existing rule.  
  * No high-calorie threshold was introduced; the >3500 kcal/day rule remains removed.  
  * Documented all seven required boundary examples (targets 0, -100, 1199, 1200, 1000, 2000, 2500) in the Test Matrix.

## **22\. Final Implementation Checklist**

* \[ \] Verify an application to strictly prevent excessive fields in the input.extra="forbid"  
* \[ \] Ensure that the absence or issuance and does not result in a normal error state.tdee\_resultgoal\_typeValidationErrorCalorieTargetResult  
* \[ \] Make sure that the and and incoming states of the TDEE are passed correctly.INCOMPLETEINVALIDERROR  
* \[ \] The code is free of any decimal rounds (using Integer Arithmetic exclusively).  
* \[ \] Verify the post-calculation invariant: if `target_calories_kcal <= 0` after `TDEE + adjustment`, return `status = ERROR`, `target_calories_kcal = null`, and issue `NEGATIVE_OR_ZERO_TARGET`, evaluated before the low-calorie rule.  
* \[ \] The code is free of any clamping of positive results below 1200, and the actual number is produced.  
* \[ \] Make sure to add correctly only if the calculated score is positive and less than 1200.LOW\_CALORIE\_REVIEW\_REQUIRED  
* \[ \] Confirm no calorie floor, no minimum positive calorie floor, and no >3500 kcal high-calorie rule exist anywhere in the implementation.  
* \[ \] Successfully bypass all the cases mentioned in the "Test Matrix".

#### **References**

> 1. Wishnofsky M. Caloric equivalents of gained or lost body weight. *American Journal of Clinical Nutrition*. 1958;6(5):478–490.
> 2. Hall KD, Heymsfield SB, Kemnitz JW, Klein S, Speakman JR, Stellingwerff T, Trento T, Martin CK, Thomas DM, Chow CC. Energy balance and its body weight implications: the formal energy balance-body weight relationship. *International Journal of Obesity*. 2011;35:1–9.
> 3. Thomas DM, Martin CK, Letexier D, et al. A mathematical model of weight change with adaptation. *Annals of the New York Academy of Sciences*. 2013;1264:52–68.
> 4. Aragon AA, Schoenfeld BJ, Wildman R, et al. International society of sports nutrition position stand: diets and body composition. *Journal of the International Society of Sports Nutrition*. 2017;14:16.
> 5. National Institutes of Health / National Heart, Lung and Blood Institute. Clinical Guidelines on the Identification, Evaluation, and Treatment of Overweight and Obesity in Adults. NIH Publication No. 00-4084. 2000.
> 6. National Institute for Health and Care Excellence (NICE). Obesity: identification, assessment and management. Clinical Guideline CG189. 2014 (updated 2024).
> 7. Iraki J, Fitschen P, Aragon A, et al. Nutrition recommendations for bodybuilders in the off-season: a narrative review. *Sports*. 2019;7(7):154.
> 8. Raynor HA, Champagne FM. Higher protein diets: identifying the role for protein in weight loss and maintenance. *Current Obesity Reports*. 2016;5:391–398.