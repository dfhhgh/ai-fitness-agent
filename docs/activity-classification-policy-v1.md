# **AI Fitness — Activity Classification Policy**

## **Phase 2.2.1b — Research & Policy Specification (Revision 3 — Final)**

## **1\. Executive Summary**

This specification establishes the definitive, deterministic Activity Classification Policy for the AI Fitness platform, designated under policy version activity-v11. Revision 3 performs three critical consistency cleanups on the approved Revision 2 framework, rendering the system fully implementation-ready for deterministic software development1:

> 1. **Mandatory Daily Movement Input (Strict "No Silent Defaults")**: Non-occupational daily movement (daily\_movement) is established as a required input field in the classifier contract1. Missing, null, or unknown values for daily\_movement immediately halt execution and trigger an INCOMPLETE status with the INCOMPLETE\_ACTIVITY\_DATA issue code1. The system strictly prohibits defaulting missing movement to MODERATE or treating missing data as "no adjustment"1. An explicit input of MODERATE represents a valid, known input that results in zero numeric baseline adjustment (+0)1.  
> 2. **Simplified Activity Classifier Status Hierarchy**: The primary status model of the ActivityClassifier is streamlined to four mutually exclusive states: OK, INCOMPLETE, CONFLICT, and ERROR1. Ambiguous downstream statuses such as WARNING and REVIEW\_REQUIRED are completely removed from this module and deferred to downstream Nutrition Assessment and Safety components1. Status responses follow a strict structure combining a primary status with an array of structured issues (e.g., INCOMPLETE\_ACTIVITY\_DATA, ACTIVITY\_CONFLICT, INVALID\_ACTIVITY\_DATA)1.  
> 3. **Public Semantic Enum for Occupational Activity**: The public ActivityClassificationInput contract replaces the legacy integer exposure (0–3) with a semantic enum (SEDENTARY, LIGHT\_MANUAL, ACTIVE\_MANUAL, HEAVY\_MANUAL)1. The mapping of semantic occupation enums to internal baseline scores (0, 1, 2, and 3 respectively) is encapsulated strictly as an internal implementation detail of the classifier1.

All foundational core mechanics from prior specification iterations remain unchanged: the Weekly Exercise Score (WES) continues to function as an engineered volume proxy using proxy intensity scores (0, 2, 4, 7\) and engineering volume thresholds (600 and 1800 units)1. The baseline adjustment heuristic remains strictly limited to SEDENTARY \+ HIGH daily movement (+1), with the heavy job downgrade remaining permanently removed1. Physical Activity Level (PAL) factors map directly from final clamped scores (0 to 3\) to values of 1.20, 1.35, 1.55, and 1.75, where 1.75 serves as the system's structural engineering cap1. All clinical, safety, eating disorder, pregnancy, and age checks are fully decoupled from activity classification and assigned to downstream safety layers1.

## **2\. Research Context & Architectural Boundaries**

The primary objective of the ActivityClassifier is to execute a completely deterministic, non-probabilistic mapping from a user's physical lifestyle facts to an engineered Physical Activity Level (PAL) multiplier1. In modern automated nutrition and metabolic planning systems, activity classification frequently suffers from two distinct failure modes: probabilistic unpredictability driven by Large Language Model (LLM) decision layers, and silent data corruption driven by fallback defaults1.  
To guarantee zero regression, operational auditability, and mathematical reproducibility, this policy strictly isolates natural language understanding from deterministic business logic1. The system boundary mandates that natural language parsing occurs upstream in an Activity Normalizer component1. The deterministic ActivityClassifier receives strongly typed semantic inputs and evaluates them without relying on probabilistic inference, fallback defaults, or implicit assumptions1.  
The architectural flow follows a strict unidirectional pipeline:

> 1. **ClientProfile & Interview Data:** Raw user dialogue and qualitative responses are gathered during intake1.  
> 2. **Activity Normalizer:** An upstream component parses natural language descriptions into standardized semantic enums and typed integers, leaving the underlying profile untouched1.  
> 3. **ActivityClassificationInput:** A strictly typed object is passed directly to the classifier engine1.  
> 4. **ActivityClassifier:** A pure, deterministic calculation engine evaluates inputs against policy rules without side effects1.  
> 5. **ActivityClassificationResult:** A structured payload containing the calculation status, active issue codes, computed category, and corresponding PAL factor is returned1.  
> 6. **Nutrition Assessment & Safety:** Downstream modules consume the activity factor to establish caloric targets while evaluating clinical risks, pregnancy, age constraints, and eating disorder indicators separately1.

The system strictly enforces the principle of "No Silent Defaults"1. Every input attribute must be explicitly present, strongly typed, and logically coherent1. If an input attribute is missing, classification halts instantly with an INCOMPLETE state, forcing upstream orchestration layers to solicit missing facts from the user rather than guessing metabolic parameters1.

## **3\. Scientific Background**

### **3.1 Physical Activity Level (PAL) Multipliers**

Physical Activity Level (PAL) represents the ratio of Total Daily Energy Expenditure (TDEE) to Resting Metabolic Rate (RMR) over a 24-hour cycle1. FAO/WHO/UNU metabolic frameworks categorize free-living human populations into distinct PAL ranges1:

* **Sedentary / Inactive Lifestyle:** PAL values ranging between 1.40 and 1.69, typical of desk-bound occupations with minimal non-work walking or leisure exercise1.  
* **Active / Moderately Active Lifestyle:** PAL values ranging between 1.70 and 1.99, characteristic of manual occupations or sedentary workers engaging in regular structured physical training1.  
* **Vigorous / Highly Active Lifestyle:** PAL values ranging between 2.00 and 2.40, observed in heavy manual laborers or competitive athletes1.

In this system, the active category factor is pinned to 1.751. It is an intentional engineering decision to set 1.75 as the system's maximum operational cap for non-athlete metabolic planning, rather than a physiological ceiling of human energy expenditure1.

### **3.2 Domains of Human Energy Expenditure**

Human daily energy expenditure is partitioned across four principal behavioral domains1:

> 1. **Occupational Activity:** Physical workload required during primary employment1.  
> 2. **Transportation & Commuting:** Energy expended traveling to and from daily destinations1.  
> 3. **Household & Non-Exercise Activity Thermogenesis (NEAT):** Spontaneous, non-structured physical movement including chores, posture maintenance, and incidental walking1.  
> 4. **Voluntary Exercise & Sports:** Planned, structured physical training sessions1.

Because total daily expenditure is additive across these domains, an activity classification algorithm must evaluate both occupational baselines and non-occupational behaviors without double-counting energy expenditure1.

### **3.3 Occupational Activity Stratification**

Occupational physical demands establish the baseline daily metabolic expenditure1. Mean energy requirements across occupational categories are classified into standard intensity bands1:

* Desk-bound office work (\~1.5 METs)1.  
* Light standing/walking professions such as retail or healthcare (\~2.0–3.5 METs)1.  
* Active physical labor such as light construction or warehousing (\~3.5–5.0 METs)1.  
* Heavy agricultural or structural labor (![][image1] METs)1.

### **3.4 Non-Exercise Activity Thermogenesis (NEAT) and Daily Movement**

NEAT encompasses all energy expended that is not sleeping, eating, or sports-like exercise1. Intra-individual NEAT can vary by up to 2,000 kcal/day between individuals of similar body mass working identical desk jobs1. The daily\_movement variable captures non-work, non-exercise movement (e.g., active commuting, housework, elevated step counts)1. Because precise continuous NEAT tracking requires accelerometer wearables, this policy utilizes daily\_movement as a categorical qualitative modifier (LOW, MODERATE, HIGH)1.

### **3.5 Structured Exercise and Guidelines**

Public health guidelines from the World Health Organization (WHO) and American College of Sports Medicine (ACSM) recommend that adults achieve 150 to 300 minutes of moderate-intensity aerobic exercise, or 75 to 150 minutes of vigorous-intensity aerobic exercise per week (or an equivalent combination)1. Achieving minimum guidelines corresponds to roughly 500 to 1,000 MET-minutes per week1.

### **3.6 Metabolic Equivalents (METs) vs. Engineered Volume Proxies**

A standard Metabolic Equivalent (MET) is defined as the ratio of the working metabolic rate to the resting metabolic rate, where 1 MET equals an oxygen consumption of ![][image2] (approximately ![][image3])1. True scientific volume is measured in net MET-minutes:  
![][image4]  
Because standard user intake forms collect simplified categorical intensity estimates rather than exact activity codes from the Compendium of Physical Activities, calculating true scientific MET-minutes is unfeasible1. Therefore, this policy utilizes the Weekly Exercise Score (WES) as an engineered proxy for exercise volume1. WES relies on proxy intensity scores (2, 4, 7\) designed to approximate absolute MET levels without claiming physiological exactness1.

### **3.7 Fixed Multiplier Systems**

In applied dietetics, daily caloric targets are derived by multiplying Resting Metabolic Rate (RMR) by a discrete PAL factor1. The fixed factors adopted in this policy—1.20 (Sedentary), 1.35 (Light), 1.55 (Moderate), and 1.75 (High)—represent engineering midpoints corresponding to standardized metabolic bands1.

| Activity Level | Internal Score | PAL Multiplier | Representative Physical Description |
| :---- | :---- | :---- | :---- |
| **Sedentary** | 0 | **1.20** | Desk job, low non-work movement, minimal or no structured exercise1. |
| **Light** | 1 | **1.35** | Light manual work OR desk job with high daily movement / moderate exercise upgrade1. |
| **Moderate** | 2 | **1.55** | Active manual work OR light baseline with significant structured exercise upgrade1. |
| **High** | 3 | **1.75** | Heavy manual labor OR active baseline with major structured exercise upgrade (System Cap)1. |

## **4\. Evidence Review**

A review of physiological literature and system engineering constraints validates the core logic of the activity-v1 policy model:

* **Intensity Score Proxies:** Assigning unitless scores of 2 (Light), 4 (Moderate), and 7 (Vigorous) aligns logically with physical effort thresholds1. Light activity spans 2.0–2.9 METs, Moderate spans 3.0–5.9 METs (midpoint \~4.0), and Vigorous spans 6.0–8.9 METs (midpoint \~7.0)1.  
* **Exercise Upgrade Anchors (600 and 1800 WES Units):** A user performing 150 minutes per week of moderate activity (150 min ![][image5] 4 proxy score) generates exactly 600 WES units1. This cleanly mirrors the WHO baseline physical activity recommendation1. An upper threshold of 1800 WES units corresponds to triple the baseline recommendation (e.g., \~260 minutes of vigorous training weekly), providing a logical cutoff for a full \+2 category upgrade1.  
* **Asymmetric Daily Movement Heuristic:** Research demonstrates that high non-occupational movement (elevated step counts, walking commutes) significantly elevates energy expenditure in sedentary office workers, justifying a \+1 baseline upgrade (SEDENTARY \+ HIGH ![][image6] baseline score 1\)1. Conversely, studies on heavy manual laborers show that low non-work activity reflects physiological exhaustion rather than metabolic reduction; thus, penalizing heavy workers for low leisure movement is biologically invalid1. The decision to eliminate the heavy-job downgrade while retaining the sedentary-high upgrade is both scientifically sound and robust1.

## **5\. Comparison of Candidate Classification Approaches**

To ensure optimal operational trade-offs, candidate classification models were evaluated against system design criteria:

| Candidate Model | Methodological Summary | Core Strengths | Critical Limitations | Selection Outcome |
| :---- | :---- | :---- | :---- | :---- |
| **Occupation-Only Model** | Classifies activity purely based on occupational title or daily job demand1. | Extremely simple; zero user cognitive load regarding exercise reporting1. | Ignores structured athletic training completely; undercounts active individuals working desk jobs1. | Rejected (Insufficient metabolic accuracy)1. |
| **Direct MET-Minute Summation** | Requires logging explicit activity types mapped to Compendium MET tables1. | Scientifically precise; aligns directly with clinical exercise literature1. | High user friction; fragile input dependency; vulnerable to extreme user reporting errors1. | Rejected (Unsuitable for rapid onboarding intake)1. |
| **Baseline \+ Upgrade Model (Chosen)** | Combines occupational baseline score with daily movement modifier and engineered exercise upgrade1. | Deterministic, simple, balanced; captures all expenditure domains without double counting1. | Relies on engineered proxy thresholds (600/1800) rather than exact biometric tracking1. | **Selected for Policy activity-v1**1. |

## **6\. Recommended Engineering Model**

The deterministic activity-v1 engine executes a sequential, 9-step evaluation pipeline1:

> 1. **Input Structural Validation:** Validate that all schema attributes conform to required types, ranges, and allowed enum values1. Any violation immediately emits status \= ERROR and issue INVALID\_ACTIVITY\_DATA1.  
> 2. **Missing Data Inspection:** Verify that all required fields are populated1. If occupational\_activity or daily\_movement is null/missing, or if training duration/intensity is missing when training\_days\_per\_week \> 0, execution halts instantly with status \= INCOMPLETE and issue INCOMPLETE\_ACTIVITY\_DATA1.  
> 3. **Logical Conflict Validation:** Inspect inputs for contradictory states (e.g., training\_days\_per\_week \= 0 combined with non-zero duration or explicit exercise intensity)1. Any logical contradiction halts execution with status \= CONFLICT and issue ACTIVITY\_CONFLICT1.  
> 4. **Internal Baseline Mapping:** Map the semantic occupational\_activity enum to its internal numeric baseline score (![][image7])1.  
> 5. **Daily Movement Adjustment:** Apply the asymmetric NEAT heuristic1. If occupational\_activity \== SEDENTARY AND daily\_movement \== HIGH, increment baseline score by \+1 (![][image8])1. For all other valid combinations (including explicit daily\_movement \== MODERATE or LOW), adjustment is \+0 (![][image9])1.  
> 6. **Weekly Exercise Score Calculation:** Compute exercise volume units (![][image10]) using proxy intensity weights1.  
> 7. **Exercise Upgrade Determination:** Map calculated ![][image10] to upgrade units (![][image11]) based on defined volume thresholds1.  
> 8. **Final Score Calculation & Clamping:** Calculate raw score (![][image12]) and clamp to the maximum internal score of 3 (![][image13])1.  
> 9. **Result Formatting:** Map ![][image14] to the corresponding public string category and PAL factor, returning status \= OK with an empty issues array1.

## **7\. Activity Input Contract**

The public ActivityClassificationInput structure defines the mandatory contract for the classifier1. Silent fallback defaults are strictly forbidden1.

| Field Name | Data Type / Enum Values | Required | Semantic Rules & Null Behavior |
| :---- | :---- | :---- | :---- |
| occupational\_activity | Enum: SEDENTARY, LIGHT\_MANUAL, ACTIVE\_MANUAL, HEAVY\_MANUAL | **Yes** | Mandatory. Represents primary occupational physical demand. If missing/null ![][image6] status \= INCOMPLETE1. |
| daily\_movement | Enum: LOW, MODERATE, HIGH | **Yes** | Mandatory. Captures non-work, non-exercise movement. If missing/null ![][image6] status \= INCOMPLETE1. |
| training\_days\_per\_week | Integer range: 0 to 7 | **Yes** | Mandatory count of structured exercise days per week. If missing/null ![][image6] status \= INCOMPLETE1. |
| training\_duration\_minutes | Integer ![][image15] | **Conditional** | Required if training\_days\_per\_week \> 0\. If missing/null when days \> 0 ![][image6] status \= INCOMPLETE. Must be null or 0 when days \= 01. |
| exercise\_intensity | Enum: NONE, LIGHT, MODERATE, VIGOROUS, null | **Conditional** | Required if training\_days\_per\_week \> 0 (must be LIGHT, MODERATE, or VIGOROUS). If missing/null when days \> 0 ![][image6] status \= INCOMPLETE. If NONE when days \> 0 ![][image6] status \= CONFLICT. May be NONE or null when days \= 01. |

### **Semantic Rules for Exercise Nullability**

* NONE represents an explicit, affirmative user declaration of "zero structured exercise"1.  
* null represents an uncollected, missing, or unknown piece of information1.  
* If training\_days\_per\_week \== 0, exercise\_intensity may be explicitly set to NONE or left null without halting classification1.  
* If training\_days\_per\_week \> 0, exercise\_intensity MUST be an explicit non-zero intensity (LIGHT, MODERATE, or VIGOROUS)1. Passing null yields INCOMPLETE, while passing NONE yields CONFLICT1.

## **8\. Activity Classification Algorithm**

The deterministic classification procedure evaluates inputs systematically across strict validation phases:

> 1. **Structural and Type Checks:** Ensure all incoming attributes match specified primitives and enums1. Out-of-bounds numeric values or unrecognized string keys immediately fail with status \= ERROR and issue code INVALID\_ACTIVITY\_DATA1.  
> 2. **Input Completeness Verification:** Verify the explicit presence of mandatory fields (occupational\_activity, daily\_movement, training\_days\_per\_week)1. If training\_days\_per\_week \> 0, verify that duration and intensity are populated1. Any missing field halts classification with status \= INCOMPLETE and issue code INCOMPLETE\_ACTIVITY\_DATA1.  
> 3. **Logical Coherence Verification:** Check for incompatible state combinations (e.g., non-zero training duration with 0 training days, or NONE exercise intensity with \>0 training days)1. Incompatibilities yield status \= CONFLICT and issue code ACTIVITY\_CONFLICT1.  
> 4. **Baseline Mapping:** Convert occupational\_activity to its numeric equivalent: SEDENTARY maps to 0, LIGHT\_MANUAL maps to 1, ACTIVE\_MANUAL maps to 2, and HEAVY\_MANUAL maps to 31.  
> 5. **Daily Movement Heuristic:** Evaluate non-work movement1. If occupational baseline is 0 (SEDENTARY) and daily\_movement is explicitly HIGH, increment baseline score to 11. All other movement values (MODERATE, LOW) yield zero adjustment (+0)1.  
> 6. **WES Volume Calculation:** Compute ![][image16], using weights of 2 for LIGHT, 4 for MODERATE, and 7 for VIGOROUS1.  
> 7. **Upgrade Scoring:** Assign exercise upgrade ![][image17] for ![][image18], ![][image19] for ![][image20], and ![][image21] for ![][image22]1.  
> 8. **Final Score Clamping:** Calculate raw score ![][image12] and clamp to maximum 3 (![][image13])1.  
> 9. **Output Formulation:** Map ![][image14] to string category and PAL factor: 0 ![][image6] (sedentary, 1.20), 1 ![][image6] (light, 1.35), 2 ![][image6] (moderate, 1.55), 3 ![][image6] (high, 1.75)1. Return payload with status \= OK and empty issues array1.

## **9\. WES Definition**

The Weekly Exercise Score (WES) quantifies structured exercise volume using an engineered numerical proxy1. It is defined mathematically as:  
![][image23]  
Where:

* ![][image24] \= training\_days\_per\_week (integer, ![][image25])1  
* ![][image26] \= training\_duration\_minutes (integer, ![][image27])1  
* ![][image28] \= intensity\_score derived from the exercise\_intensity enum1

The proxy intensity score weights are mapped as follows:

* NONE ![][image6] 0  
* LIGHT ![][image6] 2  
* MODERATE ![][image6] 4  
* VIGOROUS ![][image6] 7

### **Operational Properties of WES**

* **Proxy Units:** Output values are designated strictly as *WES units* or *exercise-volume units*1. WES must not be labeled as gross MET-minutes, net MET-minutes, or kilocalories1.  
* **No Resting Subtraction:** Unlike clinical net MET calculations (![][image29]), WES uses direct multiplication to maintain deterministic computational simplicity1.  
* **Symmetry:** WES treats frequency and session duration as linearly interchangeable volume components (e.g., 2 days ![][image5] 60 min ![][image5] 4 \= 480 units; 4 days ![][image5] 30 min ![][image5] 4 \= 480 units)1.

## **10\. Baseline Occupational Classification**

Occupational physical demands map directly to internal baseline scores1. Public input contracts must expose only the semantic enum1.

| Public Semantic Enum (occupational\_activity) | Internal Baseline Score (B) | Qualitative Occupational Criteria |
| :---- | :---- | :---- |
| SEDENTARY | 0 | Desk jobs, software engineering, driving, sitting administrative work1. |
| LIGHT\_MANUAL | 1 | Retail sales, teaching, standing healthcare roles, light assembly1. |
| ACTIVE\_MANUAL | 2 | Warehousing, active trade crafts, commercial kitchen staff, postal delivery1. |
| HEAVY\_MANUAL | 3 | Heavy construction, primary agriculture, structural masonry, forestry1. |

The numeric scores (0, 1, 2, 3\) are encapsulated internally within the classifier implementation1. Upstream client schemas must interface solely via the semantic string keys1.

## **11\. Daily Movement Adjustment**

The daily\_movement input captures non-occupational, non-exercise daily physical activity (e.g., active commuting, chores, household walking)1. The adjustment logic is defined as:

* occupational\_activity \= SEDENTARY AND daily\_movement \= HIGH ![][image6] \+1 baseline adjustment1.  
* All other valid combinations ![][image6] \+0 baseline adjustment1.

| occupational\_activity | daily\_movement | Adjustment (Badj​−B) | Resulting Adjusted Baseline (Badj​) | Rationale |
| :---- | :---- | :---- | :---- | :---- |
| SEDENTARY | LOW | \+0 | 0 | Standard sedentary profile1. |
| SEDENTARY | MODERATE | \+0 | 0 | Typical non-work movement; baseline remains sedentary1. |
| SEDENTARY | HIGH | \+1 | 1 | High NEAT elevates baseline from sedentary to light1. |
| LIGHT\_MANUAL | LOW / MODERATE / HIGH | \+0 | 1 | Occupational demand dominates; no NEAT modifier applied1. |
| ACTIVE\_MANUAL | LOW / MODERATE / HIGH | \+0 | 2 | Occupational demand dominates; no NEAT modifier applied1. |
| HEAVY\_MANUAL | LOW / MODERATE / HIGH | \+0 | 3 | Maximum baseline reached; low movement does NOT cause downgrade1. |
| Any valid value | null / Missing | **N/A** | **HALT** | Triggers status \= INCOMPLETE (INCOMPLETE\_ACTIVITY\_DATA)1. |

### **Explicit Input vs. Missing Data Distinction**

* Setting daily\_movement \= MODERATE is a valid, explicit input that yields a \+0 numerical adjustment1.  
* Leaving daily\_movement \= null (or omitted) is an incomplete input state that halts execution and returns INCOMPLETE1. Missing movement data is never implicitly converted to MODERATE or \+01.

## **12\. Exercise Upgrade Rules**

Calculated WES units map to discrete upgrade points (![][image30]) applied on top of the adjusted baseline score1:  
![][image31]

### **Clamping Mechanics**

The raw unclamped score is computed as ![][image12]1. To maintain system boundary integrity, the final score is clamped to a maximum internal score of 3:  
![][image32]  
For example, a user with occupational\_activity \= HEAVY\_MANUAL (baseline \= 3\) and daily\_movement \= MODERATE (adjustment \= 0\) who generates 1200 WES units (upgrade \= 1\) achieves an unclamped score of ![][image33]1. Clamping restricts the final score to 3 (high, factor 1.75)1.

## **13\. Activity Factors**

The final calculated score (![][image34]) maps deterministically to the output activity category string and standard PAL multiplier1:

| Final Score (Sfinal​) | Output Activity Category | PAL Factor | Operational System Meaning |
| :---- | :---- | :---- | :---- |
| 0 | sedentary | **1.20** | Minimal physical energy expenditure across all domains1. |
| 1 | light | **1.35** | Light physical expenditure; baseline desk worker with moderate exercise or high NEAT1. |
| 2 | moderate | **1.55** | Moderate physical expenditure; active worker or light worker with consistent exercise1. |
| 3 | high | **1.75** | High physical expenditure; heavy manual labor or active worker with major exercise volume1. |

The factor 1.75 serves as the fixed engineering ceiling for activity-v11. Sub-category calculations or athlete-specific PALs beyond 1.75 are outside the scope of this policy1.

## **14\. Missing Data Policy (INCOMPLETE)**

To enforce the "No Silent Defaults" policy, missing mandatory fields halt evaluation immediately1.

### **Response Structure for Incomplete Requests**

When required information is missing, the classifier returns:

* status: INCOMPLETE  
  \[cite: 1\]  
* issues: \["INCOMPLETE\_ACTIVITY\_DATA"\]  
  \[cite: 1\]  
* All output calculation metrics (activity\_category, activity\_factor, baseline\_score, daily\_movement\_adjustment, wes\_units, upgrade\_score, final\_score): null  
  \[cite: 1\]  
* policy\_version: "activity-v1"  
  \[cite: 1\]

### **Incomplete Triggers**

The classifier returns status \= INCOMPLETE and issue INCOMPLETE\_ACTIVITY\_DATA whenever1:

> 1. occupational\_activity is null, missing, or uncollected1.  
> 2. daily\_movement is null, missing, or uncollected1.  
> 3. training\_days\_per\_week is null, missing, or uncollected1.  
> 4. training\_days\_per\_week \> 0 AND training\_duration\_minutes is null or missing1.  
> 5. training\_days\_per\_week \> 0 AND exercise\_intensity is null or missing1.

Incomplete requests must be returned to upstream user-interface orchestration layers to prompt the user for missing facts1.

## **15\. Conflict Policy (CONFLICT)**

An input payload containing logically impossible or mutually exclusive statements yields a CONFLICT status1.

### **Response Structure for Conflicting Requests**

When logical contradictions occur, the classifier returns:

* status: CONFLICT  
  \[cite: 1\]  
* issues: \["ACTIVITY\_CONFLICT"\]  
  \[cite: 1\]  
* All output calculation metrics (activity\_category, activity\_factor, baseline\_score, daily\_movement\_adjustment, wes\_units, upgrade\_score, final\_score): null  
  \[cite: 1\]  
* policy\_version: "activity-v1"  
  \[cite: 1\]

### **Conflict Triggers**

The classifier returns status \= CONFLICT and issue ACTIVITY\_CONFLICT whenever1:

> 1. training\_days\_per\_week \== 0 AND training\_duration\_minutes \> 0 (claiming positive session duration despite zero exercise days)1.  
> 2. training\_days\_per\_week \== 0 AND exercise\_intensity IS IN \[LIGHT, MODERATE, VIGOROUS\] (claiming active exercise intensity despite zero exercise days)1.  
> 3. training\_days\_per\_week \> 0 AND exercise\_intensity \== NONE (claiming zero exercise intensity despite active exercise days)1.

Data conflicts represent logical errors in intake collection and must be resolved by re-interviewing the user1.

## **16\. Validation Rules & Error Handling (ERROR)**

Structural validation verifies that input types, numeric ranges, and semantic enum strings adhere strictly to contract constraints1.

### **Response Structure for Validation Errors**

When structural validation fails, the classifier returns:

* status: ERROR  
  \[cite: 1\]  
* issues: \["INVALID\_ACTIVITY\_DATA"\]  
  \[cite: 1\]  
* All output calculation metrics (activity\_category, activity\_factor, baseline\_score, daily\_movement\_adjustment, wes\_units, upgrade\_score, final\_score): null  
  \[cite: 1\]  
* policy\_version: "activity-v1"  
  \[cite: 1\]

### **Validation Error Triggers**

The classifier returns status \= ERROR and issue INVALID\_ACTIVITY\_DATA whenever1:

> 1. The payload is malformed or unparseable1.  
> 2. training\_days\_per\_week is not an integer or falls outside ![][image35]1.  
> 3. training\_duration\_minutes is non-numeric or negative (![][image36])1.  
> 4. Any enum field contains an unrecognized string value (e.g., occupational\_activity \= "DESK\_JOB")1.

### **Removal of Legacy Statuses**

The legacy statuses WARNING and REVIEW\_REQUIRED are completely removed from ActivityClassifier1. Out-of-band values (such as extreme exercise durations ![][image37] minutes) execute standard mathematical processing within ActivityClassifier1. Downstream Nutrition Safety modules are responsible for flagging extreme athletic behaviors for clinical review1.

## **17\. Edge Cases**

* **Zero Days with Null Duration and Null Intensity:** Valid explicit no-exercise state (![][image38], ![][image39], ![][image40]). Yields status \= OK, ![][image41], upgrade=01.  
* **Zero Days with Null Duration and Explicit NONE Intensity:** Valid explicit no-exercise state (![][image38], ![][image39], ![][image42]). Yields status \= OK, ![][image41], upgrade=01.  
* **Missing Daily Movement with Complete Exercise Profile:** Triggers status \= INCOMPLETE (INCOMPLETE\_ACTIVITY\_DATA). Classification halts immediately despite complete exercise data1.  
* **Explicit MODERATE Movement:** Valid complete input1. Yields ![][image9] (+0 adjustment) and permits execution to complete with status \= OK1.  
* **Extreme Exercise Volume:** A user reporting 7 days/week, 120 minutes/session at VIGOROUS intensity (![][image43] units) achieves upgrade=21. Clamping restricts the final score to 3 (high, factor 1.75) without throwing an error1.  
* **Heavy Labor with LOW Movement:** An input of occupational\_activity \= HEAVY\_MANUAL and daily\_movement \= LOW retains baseline score 31. No negative adjustment is applied1.

## **18\. Decision Table**

The following matrix provides authoritative test vectors for implementation verification1:

| Case \# | occupational\_activity | daily\_movement | training\_days | duration\_min | exercise\_intensity | Baseline (B) | Movement Adj | WES Units | Upgrade (U) | Final Score | Category | Factor | Status | Issues |
| :---- | :---- | :---- | :---- | :---- | :---- | :---- | :---- | :---- | :---- | :---- | :---- | :---- | :---- | :---- |
| **1** | SEDENTARY | LOW | 0 | null | NONE | 0 | 0 | 0 | 0 | 0 | sedentary | 1.20 | OK | \[\] |
| **2** | LIGHT\_MANUAL | MODERATE | 0 | null | NONE | 1 | 0 | 0 | 0 | 1 | light | 1.35 | OK | \[\] |
| **3** | ACTIVE\_MANUAL | LOW | 0 | null | NONE | 2 | 0 | 0 | 0 | 2 | moderate | 1.55 | OK | \[\] |
| **4** | HEAVY\_MANUAL | HIGH | 0 | null | NONE | 3 | 0 | 0 | 0 | 3 | high | 1.75 | OK | \[\] |
| **5** | SEDENTARY | HIGH | 0 | null | NONE | 0 | \+1 | 0 | 0 | 1 | light | 1.35 | OK | \[\] |
| **6** | SEDENTARY | LOW | 2 | 30 | LIGHT | 0 | 0 | 120 | 0 | 0 | sedentary | 1.20 | OK | \[\] |
| **7** | LIGHT\_MANUAL | HIGH | 3 | 40 | MODERATE | 1 | 0 | 480 | 0 | 1 | light | 1.35 | OK | \[\] |
| **8** | LIGHT\_MANUAL | HIGH | 4 | 60 | MODERATE | 1 | 0 | 960 | 1 | 2 | moderate | 1.55 | OK | \[\] |
| **9** | ACTIVE\_MANUAL | MODERATE | 5 | 30 | VIGOROUS | 2 | 0 | 1050 | 1 | 3 | high | 1.75 | OK | \[\] |
| **10** | SEDENTARY | MODERATE | 4 | 60 | MODERATE | 0 | 0 | 960 | 1 | 1 | light | 1.35 | OK | \[\] |
| **11** | HEAVY\_MANUAL | MODERATE | 1 | 120 | LIGHT | 3 | 0 | 240 | 0 | 3 | high | 1.75 | OK | \[\] |
| **12** | SEDENTARY | LOW | 0 | null | MODERATE | — | — | — | — | — | null | null | CONFLICT | \["ACTIVITY\_CONFLICT"\] |
| **13** | SEDENTARY | LOW | 0 | 30 | NONE | — | — | — | — | — | null | null | CONFLICT | \["ACTIVITY\_CONFLICT"\] |
| **14** | SEDENTARY | LOW | 3 | 50 | NONE | — | — | — | — | — | null | null | CONFLICT | \["ACTIVITY\_CONFLICT"\] |
| **15** | LIGHT\_MANUAL | MODERATE | 2 | null | MODERATE | — | — | — | — | — | null | null | INCOMPLETE | \["INCOMPLETE\_ACTIVITY\_DATA"\] |
| **16** | LIGHT\_MANUAL | null | 2 | 30 | MODERATE | — | — | — | — | — | null | null | INCOMPLETE | \["INCOMPLETE\_ACTIVITY\_DATA"\] |
| **17** | SEDENTARY | MODERATE | 0 | null | null | 0 | 0 | 0 | 0 | 0 | sedentary | 1.20 | OK | \[\] |
| **18** | HEAVY\_MANUAL | LOW | 6 | 90 | VIGOROUS | 3 | 0 | 3780 | 2 | 3 | high | 1.75 | OK | \[\] |
| **19** | SEDENTARY | HIGH | 5 | 60 | VIGOROUS | 0 | \+1 | 2100 | 2 | 3 | high | 1.75 | OK | \[\] |
| **20** | INVALID | LOW | 3 | 45 | LIGHT | — | — | — | — | — | null | null | ERROR | \["INVALID\_ACTIVITY\_DATA"\] |

## **19\. Science vs. Engineering Classification**

To maintain clarity for auditing and future refinement, policy rules are classified by their grounding rationale1:

* **Evidence-Based Physiological Concepts:**  
  * PAL Multiplier Concept (TDEE / RMR ratio)1.  
  * Domain partitioning of daily energy expenditure (Work, Commute, NEAT, Exercise)1.  
  * Absence of metabolic downgrade for heavy manual laborers reporting low leisure movement1.  
* **Evidence-Informed Engineering Anchors:**  
  * WES volume thresholds (600 and 1800 units), derived from WHO/ACSM recommendations (150–300 min/week moderate physical activity)1.  
  * Intensity score weights (2, 4, 7), which approximate midpoint standard MET bands1.  
* **Pure System Engineering Conventions:**  
  * Four-tier score model (![][image44]) and discrete PAL factor mappings (1.20, 1.35, 1.55, 1.75)1.  
  * Asymmetric NEAT heuristic (SEDENTARY \+ HIGH ![][image6] \+1 baseline upgrade)1.  
  * System factor cap set strictly at 1.751.  
  * Pure deterministic state validation model (OK, INCOMPLETE, CONFLICT, ERROR) and strict "No Silent Defaults" enforcement1.

## **20\. Limitations**

> 1. **Categorical Granularity:** Discrete four-tier PAL steps (1.20, 1.35, 1.55, 1.75) introduce step-function transitions for borderline exercise volumes1.  
> 2. **Proxy Intensity Standard:** WES relies on self-reported categorical exercise intensity rather than direct biometric heart-rate tracking or continuous accelerometer load monitoring1.  
> 3. **Upper Bound Cap:** Highly trained endurance athletes expending ![][image45] PAL are capped at 1.75 within this classifier, requiring specialized athletic handling downstream1.

## **21\. Validation Plan**

Implementation readiness must be validated against an automated unit-test suite1:

> 1. **Decision Table Test Suite:** Implement 100% code coverage across all 20 test vectors defined in Section 181.  
> 2. **Contract Boundary Integrity:** Assert that passing missing mandatory attributes (daily\_movement \= null or occupational\_activity \= null) never evaluates to status \= OK or applies implicit defaults1.  
> 3. **Conflict Matrix Coverage:** Verify that every invalid combination of training days, durations, and intensity enums yields status \= CONFLICT with issue code ACTIVITY\_CONFLICT1.  
> 4. **Validation Bounds:** Assert that numeric out-of-range inputs (e.g., training\_days\_per\_week \= 8\) emit status \= ERROR with issue code INVALID\_ACTIVITY\_DATA1.

## **22\. Policy Versioning**

This specification defines version activity-v11. The system field binding is defined as policy\_version \= "activity-v1"1. Any modification to WES intensity weights, volume thresholds (600/1800), baseline mapping enums, or PAL factor outputs requires incrementing the major policy version string (e.g., activity-v2) to preserve backwards compatibility for historical metabolic plans1.

## **23\. Implementation Contract**

The deterministic ActivityClassifier input and output contracts are defined below using standard schema criteria1:

### **Input Contract Criteria**

* occupational\_activity: String enum, required. Allowed values: "SEDENTARY", "LIGHT\_MANUAL", "ACTIVE\_MANUAL", "HEAVY\_MANUAL"1.  
* daily\_movement: String enum, required. Allowed values: "LOW", "MODERATE", "HIGH"1.  
* training\_days\_per\_week: Integer, required. Allowed range: 0 to 71.  
* training\_duration\_minutes: Integer or null, conditionally required (must be populated if training\_days\_per\_week \> 0\)1.  
* exercise\_intensity: String enum or null, conditionally required. Allowed values: "NONE", "LIGHT", "MODERATE", "VIGOROUS", null1.

### **Output Contract Criteria**

* status: String enum, required. Allowed values: "OK", "INCOMPLETE", "CONFLICT", "ERROR"1.  
* issues: Array of strings, required. Allowed items: "INCOMPLETE\_ACTIVITY\_DATA", "ACTIVITY\_CONFLICT", "INVALID\_ACTIVITY\_DATA"1.  
* activity\_category: String enum or null. Values: "sedentary", "light", "moderate", "high", or null1.  
* activity\_factor: Number or null. Values: 1.20, 1.35, 1.55, 1.75, or null1.  
* baseline\_score: Integer or null (0 to 3\)1.  
* daily\_movement\_adjustment: Integer or null (0 or 1\)1.  
* wes\_units: Integer or null (![][image15])1.  
* upgrade\_score: Integer or null (0 to 2\)1.  
* final\_score: Integer or null (0 to 3\)1.  
* policy\_version: String, required. Value: "activity-v1"1.

## **24\. Final Recommendation**

The Activity Classification Policy (Phase 2.2.1b — Revision 3 — Final) is fully specified, internally consistent, and approved for production engineering implementation1. Developers must implement the classifier as a functional, stateless module adhering strictly to activity-v11. All downstream consumer platforms must enforce the strict boundary separation specified herein: upstream components handle user dialogue parsing into standard semantic enums, while downstream modules handle clinical safety and nutrition reviews1.

## **Final Policy Checklist**

Confirm:

* \[✓\] WES terminology is correct.  
* \[✓\] WES remains an engineering proxy.  
* \[✓\] 600/1800 remain engineering thresholds.  
* \[✓\] No silent defaults.  
* \[✓\] daily\_movement is required.  
* \[✓\] missing daily\_movement ![][image6] INCOMPLETE.  
* \[✓\] NONE ![][image46] missing.  
* \[✓\] INCOMPLETE ![][image46] CONFLICT.  
* \[✓\] Activity status \= OK / INCOMPLETE / CONFLICT / ERROR.  
* \[✓\] occupation is semantic enum, not numeric public input.  
* \[✓\] numeric occupation score is internal only.  
* \[✓\] daily movement \+1 heuristic remains unchanged.  
* \[✓\] heavy \+ low downgrade remains removed.  
* \[✓\] 1.75 is an engineering/system cap.  
* \[✓\] Nutrition Safety is separate.  
* \[✓\] policy version \= activity-v1.  
* \[✓\] document is implementation-ready.

#### **المصادر التي تم الاقتباس منها**

> 1. revsion2.md

[image1]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAADAAAAAZCAYAAAB3oa15AAACLUlEQVR4Xu2WTyhmURiHX6EhjDQiRaHZ2Gg0NSIWLKQQkWYWU0JNk43F1ExTsrOSFLKQmtWksLGwRhYUyQI7aTQbaqyt8Pv1OjPnnnuv797PsLpPPZtzzv2+9z1/3nNEEhISnop+2AjzYQYsgR/hG3tQCBxfD2fgPOyAmZ4RDi1wF36A2U5fOmTBZXjruAILrXFBMPivcAtWwVfwJ1yQFLHlwiF4CIdhnrc7NovwCJ7DVYkwi/e8hRewyWqrhr9gu9UWCrPkSuzDMfjS2x2ZWdFg4jIhGmyZ1VYAt+EP0RWKBGerVfTDSdGljEM6CeTAdfEnwHO0CfdgkdUeCXOgNuCceH/4ITh2Gh7A33AH1nlG+DGBhiXgtsfiBRwXDea10xcEl/u7/Nv3rEBX8N3fEX4YHIN0A31UAvbhHpXoh5v71j605aLJL4lWqSBK4an4A00rAQbKgLkF/kd5NbPLABloEGGBhrUHwqrD6sN7oVuilT6XQXgDP1ttYdvDhivDkuuOMQmwoHBlA+EHPHg8rLxB0wnc8E304rITMFtoUzQgwv+oFK0+Bn77B9ZYbcXwWPRmDqQTrsFaiVFnH6BBdDLsbfceXsM+q40XJhO1zwULBBPltjU0w0vR330WOAlfRFeTQXLmOKsj932GLtGk+HSw23vhGfwEB+CJ+L99FipgD2yT1G8gF16cTJCmvES51KwMPAep5KvyMefjSeATl6+9KE5JeBVJSEhIiMcdydBp0d2Zc+IAAAAASUVORK5CYII=>

[image2]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAALkAAAAZCAYAAABtsY+yAAAFVElEQVR4Xu2aSagdRRSGf1FBcTaiOPGeGOKAIw4gogQJERGDGgOCrpxxoag4EHFauHARBREXIjghjhsJDohoQFBRcMIBHDCKCi6iKCgYx/Nxqrh1+/Xt7vu675RXP/y8e6urq+uc+vvUqXOflDHt2MV4iXHP4oUlgu2NZxmPK17ImH0sMz5l3Gj8zLh//+UlgfVy+781nlO4lrEN4QTjh1qaIge7Gjcpi3zk2NG4b/g7bmSRdyjy3Y3XGh8y3mVcYdyur0c5jjauk4uA/kzqNONFaacOwXPeNv5X4I/GVUm/LkA+/IJ8/N/lghs3pk3krDFnhKeNBxWujQKdifxY+UArjXsZrzRuNd6geqFfqIWC+06jPyjg4O/l+dqoBXC+uhP5DsZr5MGkjHfIFzZi2kQeRcc6L1Z4p2uh3ZEPGo/ode1O5Pcb/zGuCd8R+nvGLep/YBl4+NeB78h3A3aFUYNFR+DjEDk2diXyYTFtIgenGm+U73SjRmci3yB/My8N33czvmn8TR7lq8DDby42jgFR5JvUH/lGgSzyyaEzkXOg2kdekwRHGX9RMwEtRuSMSbqxWr5T8PwTjecaDw59SJM4F1wQ+sS5RUxK5MyL8h7Ph/up/0C6h9wu7on9bjNeXuhXh53k0fJl41/G5+X14rZo63vq9XNy+w4MbU3GXAyw93G57zmH4Q/80hqkGk+qeV6NsY8ZX5GnLN/IF7QoyhQY/4N89yAPe0J+UL1VbtBlof1641Wh7wPyfDZiUiLHyc/J506K94ZxPvQ7W35O4CxzhfEr41vyFG6zpiMat/X91aEtzcnrxlwb+k0c5FecmBE3Yj1T1UKNwNDXjXuH78vlC32Tqg+t8eD4uTwagpgm/Smv0ETcrYW596REjk23yF/s9OyBDdjCXCPWG38yHim3bVrQ1vcnGf9QfwpRNeaL6igCd4nD5SU53si6wwWTTw1ABOwEGHxI0l5EFCmH3oiYf+GYVBSkQ0VH14mcLbNq7kQf5kj0rQOLSZTinjvlJdZi6sELwIuQpm585r4u0owmaGpTW99HW1ORV40Jy9ZooohCZYHYsoYFUa5ucaNTUlEMckqZo+tEzrPJ4QbhYfkcNxQvlCCKHAH9bXxWC0VO/f4T4yPq7WBE8rqXvUs0tamt76tE3mTMsYPFui4wXbgYhRDsIKyQ52IbjTsn7VHkqROKGMYpZY6uEzm1/qrnk2pQr03nPQiM86+8+rROfhAse/nJvTmws8XfrmZRtUs0tamt72dO5HHCMeeMiEJNtx8qBweoF6nivanIucYuUByviGGcUuboKpEzl5dUvZMMAxYz2kMg4HCFmI9P+jAHfEZuSlRnflOXhwa09f3MiZwSz5fGR+UiBsuM76p/IWn7SH4wOSW00R9Bz4fvgM8cXBFCcUtPEQ8qbOkRg5yC47ao/4epeD8/WvHjVQTRjF/NqPFXvWTDIBU5mJNXkV5Tz2fk/6/KgwKlN0iOfKiaHeDHiba+LxP5MGNOBEQ8yl33yH+m5zT8a2iPYJJExy/kixxBPfR9uXH8XL1ZXqWJi18Gtvqt8p0C8kJdbPw5aeMzben/qXAPeTaHo/R+PuNgSnqxrbgwiwHCfUa9cXnOvXI743O4RlmNHYx0hbQmXoskV5/TdKCN77kX++P92H5faG8y5ipNGGytK+URiLyuKgoXgRhWyyPXvKpLh9sq1sh3uuVJG344xvip+tO+jIyZBJUNcvIysMuR2lSVNDMyph4ny/P089TLwYnkZ8hTvLWhLSNjpkGFgRo1acsHxo/ldfPD0k4ZGRkZGRkZGRkZGRlLCf8DomyQ4I84EXQAAAAASUVORK5CYII=>

[image3]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAKEAAAAZCAYAAABZyE6uAAAFAUlEQVR4Xu2aa8hlUxjH/0KRwYRITCYZlyQkU9SY+cAgkctM5oN84AO5lcuYi6khHxiFD24RipIkMx8wk0vTEaFJTabRlEvzKpcQSijK5fl59rLX3s689jln7bPnzKx//TvvWWudvZ+11n8/l7VfKaNLHGq80rhPvWPCsKfxfOMp9Y6MnRfHGV82vmLsGWdUeicLK+Vz+dx4Ya0vYwLApvU02SIE2N9ThyKcWXAc2MN4sNJuGtfimlx73GhDhIR2wjwhclxILsLZxiX1xj5YaPzD+JfxmVpfG7hefi+4rNY3DE4yfiu/Xk9phdAUKUWI8LbK50NoPLza3SqSiPAE43XGjXJhNRXV/sa31Xz8qJgjF04KEQK833NKJwSusdr4xA54k3Gvf0enFSFgPmuURoRn6b/2Bz4q10xAMhFebDzT+IWaiyrcvOn4UcHCssCpRAiwvad0QhgEqUUIWJsUIhwESUQYEDa5qaiyCEdDFmEfjCpCkmKuEVgvWGYZrzHeZTzHuG/UR3FwSdG3uPheR9si3Nt4mEr744KFRJ+Isch4WjH2AuMDxmOLMU3ButxrfM/4i/FZpTtji0XIehPhCK3YG8D9j5KL5ki5/QuN+0VjmoLzQexnHsxnqUY89xxVhPONv8uT42+MNxftLMAq43bjpcbj5Un06/JrnGj8Tp7PYAMHuPyesTHaFiGb8aXc/p+N98kX9EDji8ZX5UXb00X/cnlOnNKeUYEtpFSs5d1ye981vimfB2BfWF/m+bzxcfm8Oe+LHUMnGFWEs43vyL1c8CDgcrk4zyu+42E+LMjfZxh/Mz5Z9PPbh41TxiOKNtC2CNmkDcarVD3iuMH4tfHo4jveg42+X+49Yi/TNVgbxIXNATzMfxrPjtrw5nivdfI94CFjPnHh1AmGFSFP2enFJ14tRhjzkfGQWntw24juIFU3k8VkkVisgCYi5BoI+H25WP4PzPUzeTjEExCW6mAM9+X+INjBfIcJYYNikDmxNt+rWr0SdhFmnLMFEU63lp1gWBEyGSb+q3FePEDlNXuaPgFncR+RC4LN/UDDiZCcjmtw1LSg2tUXzJWxX8m9xRXV7n9wrfEnlbYET3hnGNAyBplTnBMG7BYi5Aklz0M85HocnAY0EeG58hyLJD/kJMN6QnCM8WQ1ewsSvNyp8jMwctO6N+e+zIvE+2r5eSrhK+RY40DTOQ0qwiQVbUoMK8Iwfq7xR+NjKnMLPkl+45wqAOFyTxL+bfInPiCIkMruNnnYayrCQYDtPflcqBg/VlkwBbBR3JM2bIir5p0Nu4wIeYvQZJHrIgQr5WHjsqgtiPMelQk/G0mVyTECIpxSWYTgDcnPWCSKnAdVCqBNEYLFcvtvV7kGHEN8Kq/aOaKBC7Rjz94lWH9ShTh3nE6Et0RtnYKqCcPDu+BwRLFF/o61H/jNDyrH40Fo4zO0bVYZmucbPynanjKuV3k2xiebTMgjJK41XiSvnrnHjfK8DJvCtQmNcdgfFMwrtpX7cKa2IWpjTRjHw4FtoT3mrWr2wLYN1mKTSrs4jVhqfEHlvvLJ94eK/jCWfDiunHdpsFl4wH7/5dGvj8+ujz/wdq8ZV6hqM+nBHfINjCvRjIzkoBiYUrVACiDkkR4QrjMyWgOemBThJVXD/wHy/yZ5Q+OtkjN2UxCGeU/8ljyn5QwTUqh0/porIyMjIyMjIyMjY9LxNzlQS2kEHs6fAAAAAElFTkSuQmCC>

[image4]: <data:image/png;base64,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>

[image5]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAABAAAAAZCAYAAAA4/K6pAAAAj0lEQVR4XmNgGAXDDHADsTi6IBJgBGIpIGZGl4ABUSBeBcQm6BIMEM0JQDwZiFlRpVCBDBDvAGIzJDGiNcMAsiEka4YBmCFTGMjQDAIgm4uA+DUQW6HJEQQgzTkMEJvlgHg9A2qY4AXImmHOlmAg0hCQ5iwgnsCA6WeiDNEC4iYGTM0wIATEXVB6FIwCFAAAf0YRLC1qw90AAAAASUVORK5CYII=>

[image6]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAABUAAAAYCAYAAAAVibZIAAAAdklEQVR4XmNgGAWjYMABBxCnATEPugQlgBGIW4HYGF2CUgAysBeIWdAlKAEg1xYAcRyUjRUIALEkiVgOiOcD8WQg5mOgEjAB4tVALIMuQS4QBuLFQCyPLkEJyALiCHRBSgAonU4FYml0CUoAKLZ5ofQoGAX0AAA5bAi7Yfn2hgAAAABJRU5ErkJggg==>

[image7]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAIMAAAAaCAYAAACU9O/tAAAFL0lEQVR4Xu2ZachtUxjH/zJEZOiKhFy6SMqQKTckyRjJLL5JfDGHIlwhQz4gmTKXMZIPJIk3fFDKULhF6pIIoYQye36es5y911lrT2d7O96zf/Xvfdv7nLX3WusZ15EGBgYGlgrrm7YybRTfmEPWMi0zbWlaN7q3pNnE9KjpB9Pdpj3Kt+eSdUxHmB6Rr8sV6skoVpo+M/1V0I+mL0b//2F63rRT+MIis8r0tWnH6HpgY9P5pntNV8qjxzTsaTosvtiCnU03y9/nYnV7Hzx/P9PtpjtNJ5k2LH1izIGmn02nxjemgQcz6D7RdTbhE9Nq0zbRvcXgYdOC0ulhO9N7prPkaeRI00emfYsfagALf6npLbkDXFa+3ZgTTM+Ydpdv0jumX03HFz9UA15/m+l6+Xqz/q+Z3pfPNwZj+1Td33kCFnrB9IFp8/Ktf2BDWKRj4hs1ELrIa7xwELkOy29KzhhYtPtMT4/+D7CIL5o2KFyrA2NgbkeZflK3hWWer5sO1Xh+K+QR9mPTtqNrdexi+tb0ksZzPl2+/jhsTO/GsIPpS9ODmtyoYCi/mPYv38pC6L7V9K7pfnnIvMZ0oulglTevjpwxhHeOFwEvZEP3iq43ge90NYbwXaIohgGsJfUOG0nUagJp5it5xMNxgDkxBsYf07sxHCt/2NnxDeMUed1wh5ptIpb9iukQTRpWF3LGgAf+qclFwMOZC97UlmmMgUKXFIFDFd+1S1TdVOMxWEPWnrmm0k3vxkBoxfOx3hDOyU9Xy630NNPa/346DxNgQdrm7CpyxhA2PV6E3PUmTGMMKTaT1yGsIR7fFgzhcNN3pluU7hh6NYaQBr6RWzUhHRHeqSGuk4f9JtDu0Ob0Bd72pulZeYFYhMmnNn2WjCFEVYrTtlGSyEeXRyd1j9K1HIQ1elzNInclVfXCcnkOfNu0RflWElq841QuGGMRAutg46miHzN9KE89MRcpvemzYgxE1tXy1jjl0U0hIt9g+l5uICn2lu/hjfIOpEkUT1JVL0DIeU0KoAvlXhyiS0qXaNLLYw4yPSdvE4/WpJFCbtNz15vQlzHgrZzN4BydN6YA7T5tP+1lyinpnC6QRxG6q85nQrnzBeAhtGkULzmrLEK/j3H1xUp5vuTwJuYA02+a3LhgDKliq44+jCEYAikiGDHG3fTkdDf5nvA3EOqCVJdEarhL7ji0sp2pO1/g4ITCstjzVrGrvP1p0+NXwUSx9AVNPn9r0xpN9t5EOPr0YmohNTVJT3XGUDcO6YCWOjZE6q6is1WNEyIxfwPhveJ5QTCUy6PrrQkHHPTCxVBMaCMtkKdyJ18pGIM0cJWmy5NFct0Ez7pWXjzhjcAzn1K5mAp9++em7UfXcoRFTy1s3Tg8e5XceSj8gvj8GnltBnXjYIgU8xTjgTPkBkIEiIvEqbsJPJ4BeACi4uXlwsv/Lp/AuWrv5RjSeaZX5c+pqw/qyBkDYAQvmJ6UG+8DpjdUPjbnfw5wSHW5Xv8cjX+LCSI9caIYcnTdOMGQimME0V7SZkLdOMwJY37ZdKY8RfJb0ROjezFTG8NiwEsyETy36CkPqZ2BVBkDYHxsBKeb/M0VbNQzTYrgOhZjHKLecnlnhqqOsv8XxtAXdcbQBEIrhzapsNyGWRsH5s4YimG2C+Tfm5RuUdswa+MAaYfUPhfGQKtKC0mxmPtNvwq88GSl820bZm0cWCYv/jlwiruMJcsK+e8n/AqaOnOYN9aT/1xAPcbBFkYxMDAwMDAwMPCf8Te/wDZiHQim8gAAAABJRU5ErkJggg==>

[image8]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAEoAAAAaCAYAAAAQXsqGAAACf0lEQVR4Xu2YvWsUURTFT4iRiKKiogiCQVBIYRUs/OpsLBQVQYNN0EITtAmEVCJE0yhYJFooiloICjYWfiAS9i8QkYiVoCJKELFRQYiac3LnZWce2d3JM8lm3Hfgx8zOfbOTd+a+++4GiIqKiiqOdpAP5G+K7+RTcv6bPCJb3A3/gdrIUf9iXg2Rn2Sbd30zeUvekA1erEhqJz1kBPby72TD+bSMlMhrsiYbmpS+VNm1zw8USDLqAGwFfUSgUZvIZ3KLNHkxZ+Ivsj0bKqTWk/cINGo/LGNO+gHqCCxVr5BFXqyI+iejBmEZsxf2RWIjOUfGSCdpnhpdbAUb5ZbWF9jSu55wE1azLpDlbvA86SxsJ87LU7Jq8s7aCjaqWn1qg+14L8jabKiidsFaixLsJWi59pGDqTH1VLBR1eqT5HY8Lcu80u5YghnVSm6TM6l4PRVsVKX+SVoCS+s/ZI8Xq6a0USHSfa5W5kHZnreGBhlVq3/aDSvyz2Bj1YdcJtdIN2kpD8VOco/cIJdQNkqZeJ9cnBpZW1vJ4RmgZ+il5lGQUWrCvpK7yNYnvR09/BsZhe2AS8kT0gsbO0xOJONl6GOyIvnchWxGHcMM/7A5lDPKn/O00sQ02P22U5+kblU7iI7j5B2srvhvah1saelB/ck1ZZFaDCd/6elzvY1S6dDcNNf0b9pXsAyeNWmZXU1YDTPJGSUT3Lm0EI2aN3WQl7DUlZRBA7BldZo8QLlzP4QGNkr15yGsUKuQ66hNQOeKyQiZp7qlWvYD1jiqPWgoo5xWwiY/nVzftBi2VLUB6NiQRuWVTHoO2xDOk1PZcFRa+t+P6thxZHuuqKioqEqaAJaBlLdaKyIyAAAAAElFTkSuQmCC>

[image9]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAFAAAAAaCAYAAAAg0tunAAACWklEQVR4Xu2Yu2sVQRTGPzGKEomiIRIIKAEFCyux0CRdmhQGDYKIjWihgjaCWIngo1GwyKNQDGohREhjkShicf8CsTCkElREEREbFQRf35ezk7s7mrt74+hmYX7w4z7OXHbP2ZkzkwCRSCQSceymr+jPlJ/om+T9dzpFt7ofVJx/lu8w/UJ3et9voc/pLO3yYlUmaL5raI3O0PZsaI47sKezxw9UlOD5dtO39BZd5sXcxb7SXdlQZQme7yCs4sf8ADkA6wujtMWLVZXg+V6GVXyAdiZuoufpO3qQLp8fXX2C5uum7HvYlL6ROA7rEZdomxv8nzgH2ymL+pCun/tlPsHzbdQPNsN2pCe0IxtakF7YkaAGu1ktgzN0X2pMmYTOt2E/EG5H0nQvinavGqyAq+hteioVL5Pg+S50HhKrYcvjB+33Yo1IF3Ax6HeuNxVRs6Vozwqab955qA/WbB/Bxu6l1+h1eoKuqA9FD52gN+lV1AuoJ3mPXpkfmc92ur8JdQ0ln0ez+eayjX6gd5HtB3qauqmP9Blsh2qlD+hp2NgRejQZrwtP07XJ58PIzsBDsKVRNs3k2xAl/BL1vwV17nkN29H0+o2+gPUt/8luhC1R3cTZ5DvNOh0NHP4S1ucyC/g3+QZDy3UscQOseK6AKo57L5ZaAZcEO+hTWNMWmnEXYMvzJJ1E/eQ+hFjA31B/uw/bILSB6FXNWO8VU4FUVPVF9crPsAOxjjGxgCnWwYryJ9y5byVsyWvj0Wss4CJQ8R7DGvNFejwbjhRB//1VnzyC7JkxEolEyuIXTf628LA122UAAAAASUVORK5CYII=>

[image10]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAADMAAAAaCAYAAAAaAmTUAAAC7ElEQVR4Xu2WS8hOURSGX6EIySWXkM8lJXKdMlCIAUkZMTMwMZCSXGKAyECElEQMMDAxICH+MnAtE1JKoaQUAzFA4X2/tdd/1r+/853zD5idp946Z699zllr7b3WPkBDQwMZSM2g1lGz0/0Aama67sNY6iH1J+gjtZiaTD3PbK+pWe0ngU2Z7To1LNmEru9mc7rpDTXeHutFzr+gLlEbqbNUD3WSOl5M62Qn7KVbcwPZDbOtzw1kHnWPamXjESXmO3WNGpTZFPBh6gE1IowvhAW4MowJJfA3tTYb74Mil8MKKseD0ZyIlnsvtSIbz6l6t1Cwl6kh6V4BX6FOwb4R0W55Blu1rqyBfVCOR1qwDJU5M4c6Sg3OxnPOUb+oJWFsEjU1XSuYY8E2HbbVc1/EROoiNTw3RJbDlk8THWXlIGx/5sEoe9oeCqiKUdRT6i0sAGcHtTpdt6hlhal3W6o+VeiRobCtXYm/IAajsSOwWlEw0baU2oXObZAzn/pK3aSmwDKrIJ7AVqCMkdQjFM3hA3UC5k/d99p4MOo+KkptHb1AmckD1RKfgTlXh9fLF+p90k/qBooaKWMB9QqdXW9bnNQNZewdrPXJWRW1P5gHKge3JFsVyuIFdNaLVvpQuPfklaFV2kDdhwXzEnacVOLBaH9rNc5T45JNneMzLFAdYKdRU4AJr5f8DFH7V40KOauA3a5vjk7XEdXKLZiP8rUS/7Am74dlw/FAdRbsQ30rdqrOF0ertCfcq9XHVYxom8tH+VqJMt0D62hXYZlwPBgts/p/ty2R4/WyPTckxsAaw9x0Lx9uo1i1iOaqaeTHQyn+6/ED1qkiHqiyrGz3h2714ja1Vzmn5Piq+fmi52LC9A+mznkHti37hZZRB1y+JTyYA6hvjUqKVvYbig4UO9mnMK5dsMoea6NfFAWnfy91MjWJzdRj2FadUEytR1nv1ikWobww/yXTUPyoqiHor0R/yy3UJ7GhoaGhoeG/8heaI6tmG4KoHQAAAABJRU5ErkJggg==>

[image11]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAG8AAAAaCAYAAAC5KgISAAAElUlEQVR4Xu2Za6imUxTHl4wi4zqaIcQgZpgPJsxEynxA+eCSkeRSU9NEMtM0H0xTytTkg3HJJQnlViJCilzjxBeNoplyaZDIpRRKSOTy/7Xenf3us5/n3e9+XjrneH7175x37/fsZz9r7b3W2vuY9fT09JRyoLRI2ivtmEXsKS0ciN/nPCdLH0qfSNdLhwx3zyr2kS6TnpV+lK6S9hj6RiE3S79Jf0XaKR0/6D9D+inq+0O6dtD3X3GA9Lb5yzbtuBOk7dL90uXmBqqF3XCpdHTSXgrPZg7M5S7pbGveYVdKv0inpx2lEIY+NV/Z/J7CqnhUWm/Nk/g3OUz6XNqcdgxYLX1gvjvnS9ukV82dXgoGP1+6U/pK+lk6ZegbZfDMZ6R10rHSjeYL/sVBXwrP4Fk8u4ozpd+lxyy/ffeTnpSOSTsKwaA4IBZtpbQ570jpY+mKqO0g6R3puqhtFDjvPGmVucFrncczWej7Dz5jTxYTUSs3/87Ou9p8cH7mWCo9ZeMZHE6U3pBeMw8hiJB7ifmYpbQ5D6elhsZgLMQpG3/OwHPSMUt5xNyWm6K208xDI3bYN2qHTs4LL9o22QvMV08pjLnGfLceMdxVRZvzyCm5uWPEb6wuWnRx3kXS+9I5UVtw0JRNX0ydnEfVxsNQUwV3h7kDS2FCT1s+xtfQ5jyclDN0U3sJXZyXg+jAbrwt7bCOzgtb+iHL5ztWyuNWvoIZg6qvunrKwFjMcW3SztymLG/omeI8FvCb0m7pqKQPFktfSluT9iJG5TuchvPS7d4E37tHWmLTi5RYe4c/aIED+SrzSpLFleYLPpNHcoaeCc5jIXMm5WzaluMvlr4zL3Y4uOc20TRCvmNVswNzjJvvcB65DmOHIiUnKrs25kkbpPek58zL7hxNTmpqL2FSzlstvWWjz4tUpreYO/A+cweOJIQdznhN57vbzVd/Kewodt7haUclnCu3SN9Ly5M+uMnyhsZ5hKOagmkSzsNxnO0OHnzG1uS+NOLQ/or0uv3z3SJC2GF1cJZLWSk9YM23Gk0QgpvCcA2EbirHXMFCZOAQzC1GAAO9MFAwVrhPTI2Xo8152IJx2myywjyixQUbYZMLgDQkhoKF0Dk215hv12VJO2H0ecsn2VEwaUJnbNAutFWbC6QdNpzwjzPfddwfBih2yO3kb0JyGzynKZVQMTLO1qQ9gJPIcd9KX0QichAlUoLzqqpNVtCt0g/SDeYv+bL5ofzQ6HvjQgjAUIRQ8lWXa7U258Gp0mfmxQEXANyucGcb7w6M86t5imC8FKLQE+ZGxjlBX5unjsBG6U/ziJUr4gjX8d/Him+BAp2cF+CaiQMmg+TyXw2ECCZHuPjIhlciN+mljHIeYPxzzd+Bd8lByLzbur8f52HGSavfGibivJlMifNKWGweZUaFzVFw7mSXT4L/jfNyOaMUwjaOi6+taiBUPiidlHZUQl4lv85Z57FT7jXPy5wPa/InC+BCm17tjQsFyVlpYyVEAm5f3rXCs91sBYdRvT4s7bJ8GT9boJh7ybzo4Z+xk8idPT09PT09c5K/AW1t+GFY0tOzAAAAAElFTkSuQmCC>

[image12]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAI4AAAAaCAYAAABhCmRdAAAE30lEQVR4Xu2aa6hlYxjH/3LJYFxmBrmUS1IYmUIauRyFSHxgymgGH5AaQi5hUHLJJR/cikShXJJbGY0x0oka11yKklJDLh9kSuHDlMvzO896rbXfs9591l57zzmzdu+v/p193netffb7rOd9Lu8+UiaTyWQynWUX04TpdNNuxdhC057hgkymyvamW03fma4yrTJ9YnrA9J7psPLSzrOD6SnTZtO/Ff1s+qN4/ZPpSrldusYppl/Vu7ZNpguL+QWm96P5V007F/ON2c70mOlF9d5MpPnYNCmPROMGm+E303OmbSrj28o3EQa9rjLeNZ40/WM6I54oONf0pmnXeKIpS03fmxbHE8Zq08Px4Jhwjtw5Lo8njKNNf2puN801pjPjwYbsIc8YP5r2j+YCPNsV8eAg3K30H7hBbuBxhHXjHDhJTHCqF+QReS640XR2PNiQEE2JKDtGc8DY86pfe2OekRvpZnmYrnKIPCeOG0SRSdPXpkW9U1NNAXUddcJR0dxsMozjkIZ4prxHHfuZXpJHptYsV1kk/W1613SJhsh9HeBg0y/yonBf0z6FTjR9VozXReDZZBjHobygvjk1nihg/An11nYDQ+dwj9xpqpX2l5o74xHpPjX9MIAumLqzGSEVvS03YNAaecdxkoY06gho6zjz5WvYKI8sdfDeQ9U3VUhT5Mb7TL8rXTiOA6n6BmchZbP2y6K5FDvJOxg2XnjQ2PFBeWc6E2zcvVVGvaA7TRfVjO+l6SVFlZnqG2o2jiPitTeGP87OrttZtHCEulSO7DL96hsIHdU7an62Ed4zOA4pj5TfJGIfr96oF0TEjSMiesh0IDcmCPXN6niiYOj6hjz/iOq7hmC8kYWzAcGp2Vnxbuunpm1z6vwmEDZNasfWETvOKGibqrgPx0m18qzv3nhwEMjzb6jeOCtN38ojEi35Ovm5AtezQ/gK4i7T/fIwfajfNvVhw864tPJ6qfx9eJ1aUBV2+lmmZQOo6el2v/Mb0ga7kbTDdal1Ap+Rg0LqottNn8sf9O7yB4PNjgwXt6Ct41xr+st0bDwh7xg5YuC5tibk+eOicd6Uwvi84nfyNJ0GR/B3yI+u8Voci9zMwSFhPeRzotTL8khG2Aw7G+fh64y6XT6b0HHUGZbPz2cNJ8Z8ztQ6cTCuPX/qztJG4UGTBtZriDpC7R3nCPlRAs+rCscqz8qfSWsIra+Yrpfnel7TglPQbZQbJDxgrn1d042A8Y6RF5GcUpIu4CDTh/JUeIvc8ORV2v6mUWHUEFWfVvldFNqksiPj9WZ59Djcb/mfunVyvoPdWCPEqSpls0Fo6zhAtKbBwVHYyI/LHfvk6kVtmKcyXAXDEO4nND111RmB6z8ynSYvACdVOg6RhnB4k+lq06Nyp7yimOsSqXViiy+K17C1OQ6QSvkvh5DG+3ViW4Q6I3DaHDoudt0GeWoLOZ36gAKUb2oJ91/Jd0HXSK1zQt71nFDMzZefnYzScagl5ypCDw3R5zZ5KH9NZWFLnmQnXixPR+Rz0t0BxTypia6E2mCRaa08hXWNfuvEFtQ8pALqRWz0gWmJRuM4YwspjoIrVexWUx5hM3Xd1k6/dRL+KYT5yRr5SfTJjpMZCKLQN/IO8i35WVQmMyNEHc67+LqgeuaTyWQymUxmy/Mf2SANtAatVgYAAAAASUVORK5CYII=>

[image13]: <data:image/png;base64,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>

[image14]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAACkAAAAaCAYAAAAqjnX1AAACG0lEQVR4Xu2WTUhUYRSGT2RQZAVFC6Ego02QEGRE0MJV1KJaFGY/OwkjooU/RNFCiIigoD8oIhB3QWhBQrSJqJ2G1EKQIEqwTbsWQpvU5/V8l7kelBlx6AbNCw/3nu+7zLxz5pxzP7OaappTPbTAQdiQ1jbB5uyBIrUKrsFXuAQXYARuw3vYWXq0GNXBI3gGa3PryuAwvDPPcKHaDxOwK26gq3A/LhahGzAJW+IG6oGjcbEI9cMMXIGVYW8HbAxrhajN3KT4A2+hHdbnHypa6uyb5gYzs+KzzS8BZVnNFLP9V6Uv16i5Bb/MjXakvWZ4AW/gCdyxhWu4UqkPlJQjcSNKplRzK+IGOgTTcBlWw3M4ALvhFHyw5c9O9UJZk9vhgfmcjNoDU3DGfEa+TGvVVEUmNVpemWcq6ix8ga1wHn6Y/92611gahCbYBg/NS6A1revFkL1G95nP2XvQa/NfFhWZVF0oW/qgvFQCaprjKY6ZXAdDuXiv+ZxVOUhPoTPdP06xdNG8ljOVNakvHoBuGEv3Gjt34TuctFKtRpMx1vUTNKRYdSwy6aCiA4saUsYylTW5xjxjkkaQuveE+Qko/v3RVIwXM6kf2WWegEZzQ0syuRRFUzFezKRirWfPqQllTFfVZtVMKqs6ZPyE13AsFytDqkNdf5s3yGkYT8iAmqjPvJSuw6h5L5yDb/ARDts/IGW+8KNeTTX9F5oFFo1qMJlW8ZsAAAAASUVORK5CYII=>

[image15]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAACAAAAAZCAYAAABQDyyRAAABa0lEQVR4Xu2VsStFYRiHX0mISIoUi5RNilI2kkkoBrGxKptJUjIgi0w2gz/AYKLcsgjJZDFYlL/AqDw/h3zf8Z17z7k3Sp2nnrq97+2+7z3nd75jlpPzu/TiDh7iPNb77W9G8ArnsCbWK5cZfMB+bMRNPMNm90su2m4R73EJG/x2JrrwERecWgve4LJTC6IroCtxi2vY5LdTocGvOODUqvAYCxZdkZJU4yhe4i62+u2i7NvPBcQRvmB3rF4UbT6EF3iAHX47iAYlLRCqp6IW1/EZe2I9F13egoUHlbWAG84VKx1O9c8tPCjTAvohDbyz7I9n0qCkuodSr/TrXJiyKIxZ2bLwIC2gW9gZq3+gcClkCtuwlTf4i0l8wzGnVoenn+qzxwSeYJ9Fqa8UPbLXuOHUFFz9e93OP2EQn3AVZy06BbctW5YqRkEex2mLjudEtFW7RTkoZZtVlo8gemPplZnGPUt3Gubk/A/eARC2QlJ69+/bAAAAAElFTkSuQmCC>

[image16]: <data:image/png;base64,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>

[image17]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAADYAAAAaCAYAAAD8K6+QAAAB2UlEQVR4Xu2WPyiGQRzHf0IpDP4UBomklE0SUUYlf5KByaCQsrLYZFCSDAYGpaQwMigDGVkMmCSyULJgIPH9Pffc2z333D3va/A80n3q0/v0u3vu7nf33t1D5HA44mAevsMvxXNY55e3whel7BNO+GVxkgWb4TJcgV0wO1DDQBm8hlf+sw43ugEnKYPGfgHufwoew2pYAjfhKsxV6oVogx8kKnMjOoVwG9boBTHRCB9IjFPCY7mFnUosxBiJvxn/mqiHO7BAL4iJORJJVCgxnuwTuE7mxfCCvFKvJGbGRA+c1YMxkQf3KZwYT/IRPIVFSjxFKbzw5WcTSySSSwKZgC0xPZ6iCb6RfUm5gS3KfH8NwbsfeAZrvTfN8KB58HoCaRNLt784IU4sqf0lT2w9gcjE5P7iFeOVM5Hk/mJsCdjiHrKQZ8R2fy3CDi0eBW927ihTud+ouygH7lI4ATl2Phn5hAyQDw/JUkjipl+j6I51quDAD+yFxd6bdqbhE4lrRyIPPf4SMTJO4qUGLc5/zT0SA00aPlzu4aASa4ePsEWJBeDVWIDPcAaOwAMSF3K5Ui9p+uENHIXD8JLEN6vpJA9QCftgN5n321+AvxF5fCw/OxwOh8Px7/gGsNBk9GRA17AAAAAASUVORK5CYII=>

[image18]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAG4AAAAaCAYAAABW6GksAAAFHUlEQVR4Xu2YW+hnUxTHv2KK3GLkEpq/SyORu7ygXOPBJUxpzBPFiyLlLhQyKA1jmtIgyuXBi4dBRuZXHlzDg6FILo0U8aDxwOSyPrPOmrN++3fO+V3+/6ZwPvWt32/vfc5v77XWXnvtn9TT09PT8x9gZ9MRpktNR1ffdzIdWX3+37Kf6R3T30k/mE42HWL6uOj7wrR025PSiqLvFdPuVR/w+c1iTJu+Mh3gj20HR31qes50lelJ08C02rSqHrbD2c20XD6fB+R2KjnK9LB8DGN5piS/h7E8MzW3yg14fdlh3CHvu6zsMI4zvWWaK9ozBMFvppdNuxR9OPdB09umPVP7iXJnnp/agGD5y3Rx0b6jIJg+Md0ud9gy0/um/dOYy02fmU4w7WG6z7TBtHcaw2fa6GMMY3mGZ6eCiMY5OLAkHMeYDCnrLtN5RXtJ17sBx75g2rX6jnNfND0h/40MxvpQbsCFgHSbA6YLnEMGwGnMKzIKQcka4FDTlxq21T6mDzS8KbAFbfQFPPO5RjNPJxfJjYuTMnPyyG8y/DHyLb6oaC9ZZ9pqOj21HWxaUn1m0Y+mvsPl6bqcCxxkelYepfOBNHW1fPdcUfS1wfp/1nDQnGO6TXUqxPjZkYCTn5eneeYdjmQdmVNNWzRlNjlXnoLyy/jB++XnSek4dgUpDud1EZP8Ru6s4GbThdXnOdNZddf21Mp5ShGSwUCk51nZS54l3pUXPOOCLiC18QxrWVyJHVgWSI9r1HGAXQlGghLHEwCl42LdnJsTEw/ll9G2Un624bjcd4bqlNHF8aZfTa/K0wg7BodxLrCIJsJIUbh8b3pMPp9xv9cGhn5EfpaerVGDjyOMzbzWmO6UF0mb5OdTgI3aHBftTbaGtvZO4iFyNrmbSMRYRHz5Qrb7WrkjxhHn2y+m7yr9YVqv+kxrAmOQ73PliW7MgyaAQOGs3Gg6TbM7PmxAVooijXc9JJ8nZy92GVTjuhwXx1LpoNLOE8ECv1Wdhyk4wkilU3HGdVVfFyzsGY2ebyw8p4MIlCbYfcvkhmexRDhXmHEcZnrK9Jo8tc7qsCBsUP5+OAF7NBUrQXYcGWfBHUcOZ5c9rbrEjTQxkF+G12iy4iDOt/KORnXFmQo4BudGP7+5b/U5w9n2unyOzLULDMg7MeJMd6MGIuUPNLz2cvdkB2Vye5uD2to7CSNjmHvkUR6EUzkf7tb48j+IiTTd3wJ2H+dFQOGQd2eGBZUldBd5180nTQKBRQAO1O04Mkmb4zbLU2pUzaWDwl5N1XQrkZ/J4S9p+KYfjmOC3K/a0lpJnG83lR0Vi+VFy7HVd+bwhurdmGEsBU15JZkE5k+W4B+iWQoTiLtlGTg5VQKl/J8aXgNn+fpKfA5bx/eAZzj/m9bfSuTn3+UVY6br0G2D6G4636KPcwdHYIzYjRGJPJeDA0NTwW7Q8L8P05KvApdoegeSaX5SbQPWkYsTiAC7t/oOHD3stitT2wp5oUZWAN7FvyjMbeo1snXXaTStheN48bh0QwCwY7lIEokoV5Q/pnZ29wX+2DaIVhy5Wm4M0s41pvfk6fbAeui8YI43mD6SG3PSDMI4HP+16Vr5PHHIKXlQ9Z0xt8gv9+xSHJx/h89U5hvl90lsu0nDV4uJIZLaKraT1Fw0LCREH0YFzhTSEIua0/iAmQWMh+OmvWJwDWJe/I8a8y2hnX7GtV2bWNNSuXPP1OQB1NPT09PT09PT09PT0/Mv4x9NaTh/ODzs1wAAAABJRU5ErkJggg==>

[image19]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAADYAAAAaCAYAAAD8K6+QAAABfklEQVR4Xu2WzysFURTHj6QIJcmPoleSUnZIycI/8Ly3ULJTFqT8B3ZWSrK38KNEbG2UhbK1sdBbWZCtbLAg8f2+O6+m033Pmc3MLO6nPr3pnpnmfTv3dEckEAikwTb8gr8x7+FoVJ+B77HaD1yPalnQBpdhl1r30gcfYSW61jTBY7gBm1UtDbrhIjyEb/AJDsRvqMcs/IYn4kJoOuE5HNaFlGCwEpyEZ5Ig2Kq4bcZfH2PwAnboQgYciTEYO8ROfcAJVasxD7f0YkaYg/XAh0he+9gTFy4PmINNwU94IP754vY7Fft8LcHnBN7BkeqTNszB/psvBmKwPMwXMQWrzRc7xs75yNN8EVMwduFG3BlW7/zahXNqvRGt4l5qle9tqT5pwxSsHV7DW3FnlWYa7kuyFxfgQgJ5PvGcsmIKRtbgKxxX69yal+L+aJ5gsBc4qAsadmNH3KfKJlyBV+IO5P7YfVnSK25X6W9WBmRjGjIEy7Ao/nkLBAKBQCCQAn+nVlZJ6n9O9AAAAABJRU5ErkJggg==>

[image20]: <data:image/png;base64,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>

[image21]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAADYAAAAaCAYAAAD8K6+QAAAB2ElEQVR4Xu2VPyhFURzHf5Ii/0oKgwgpZRNKBgOjP8WCUSKxGFiUQQaFMDKIkqJMSsrwYrUYpMRiVFgwkPh+37n3ufd03n33De4znE99eu+d37nvnn+/8xOxWCxRsAQ/4LfHK1jvxNvgqyf2BSecWJTkwSG4CTdgJ8z29TBQBu/hjfNdJwvuwikJ8Wd/QDE8gqOwFs6LWuATJ5aUdvgJ90RNQqcQHsAaPRARk6IWtsj5zTEuiDpBs24nE2OiOvHTRAM8hAV6ICJ2RI1v2tPWDN/hGcz3tCfg7LlTb7BJi7n0iFqhTNEHr2GXp41j5ZhjkmTBS0U9RPndxJqoyf0nhkXt4ooecHG3dFvM+cXV2Jfw+TUIH9LwEtbFnwwPL4xzeAurtFiCVPnFCXFixu3OAFz8GXgnKveNuPnFHePOmch0fun0wwtYrbX74C7ERNWwZPVrFXZo7UHkwoo05Htz4k+mhpNi7SpxfnP8zDW+0wevSV6XXAHWKp1WuCXhX0x45gfSsFd+BxpEi6jT5S3IPIrrYr4bZBw+wUatnUfzWAKSM0I4AebUo/gvnme46Onng7uxDF/gHByBp6IKcrmnXyZxC7RJHsVAKkUVwm4x55vFYrFYLJYI+AGXWGKA8f8OCQAAAABJRU5ErkJggg==>

[image22]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAHgAAAAaCAYAAAB8WJiDAAAFmklEQVR4Xu2ZacimUxjH/0KRsY4MIe9Ys409JUuE+GDJUmKS8kFJRjRkiSlkK2FIWaMs4YsythFv+WAtJYMsWSJFfBAfkOX6uc713uc5c2/P80zNxP2vf/M+Z7nvc67/uZZzjzRgwIABAwZMjPWNuxhPNe6Zfq9n3DX9PaADWxvfMP6d8TvjQcYdjO8VfZ8Yd/93prS46HvWuEnqA/z9SjGmiZ8bF/i0OSDoB8ZHjecY7zPOGpcb76iGrRXMGM8qGzPsYbxVvmbslNslsLHxbPkYxjKnDvmzGM+8sXGF3NAXlR2Gq+R9p5UdhkXGV+UbbgKH5VfjM8YNij42fpPxdeOmWfsBctGPz9oAxvrLeHLRnoNnPmC837iw6JsGHLgL5fv90/jIaPccTjc+JR+Pk1xsfMe4UzZmc+NK4/XGecb9jR/K5+bgN+30M47xzGP+WMBDEBGhS4TAjMlBqLzGeFzRXqLt2YAD8Lhxo/SbQ/CE8W75O3JgsHflxusCJ//pxL20+rPGBe8kVRxm/Eb1AhOFXpSvM8B72cuyrA1bIPqWWRt2+khVJNvR+GlqDzCeeXWO2IqT5CIgZo4ZuSfVCbS3PHRsWLSXwJv+MB6etW2v6kQj8O1Z387yNFGuBWwnNyynuS/wYrz5NeOhml5o1vCV6gVmLx8bdyvasR12ACFSOf8Q4y+qohPCEvl4ZoC1PyZPVePYQMfKQ1/+Uh52gzzflQLjZYRWRG5DbOZLuaiBpcYT098zxqOrrrmQTr6nmMpB/iEtTIL5xtvk6eAYTV6ktQkch/Mz41GpjXD6sirhiAQ/avX5se8b0++70u9cYMA83sG7eiMenr+UtpvluReB874jjFeq2xv2M/5sfF4ecjAOwr6t5gVikDdVFWDfGu+Ur6frfX2wmTy18I5TNL7QbQKzvstVrf1hefF5WeoDdbaua+ffJoHr2lsRD6fqpUgh7GJUPKh8MaHhXrlgXYj8+5Px68TfjStU5dw6UFSQj8JQwUvyQVNiX3mUoHAZB20CAw4MXhhr/kFep4TAkQ7L+bmdsfFs+l0KOZHAsehZ+cNZUBizFB/RLkh9bWBDnOAy/xIRIgyBOFB1wJvPlOdPjLJKfrWbBlF8PScP92H4vmgTmGdRABGSKcbwXtZN1X1uGkME6xIYm2DvOiGnEph8idc+ZNwm9UXOmJV/dLhH/RJ85N/yjosByPkAATkE0c87t0p/5yD3Up2yRtY6LjA8Yr5gfFDTXZ/aBMYxuLtHdMObubsiSFTIZUQMlO1NQja1tyLEYOHXyb0mEBuiOLlW3deiQCy47v4bwJuvzn6TG3Nvz8HGyqtFFxCWypkIwFVlksNRok1gKmWKoxInyNMUNolCrJwf9orbA1GuTkjmcU3Lr2KdiJhPJf2kRr+WxIYIK9xPm8Jpici/l5YdCfPlxdc+6TdrILSFd+dgLIVZeVVrAp5DAUUhxaFh/ppCm8C05eknkN/fw9YrNFqHsG/qk9g/VTehPbcH45lXzu1ExPzf5BVyjraE3wQ8py7/Rh/hEsE4MOHdcbKZlx8ixKJiX6l+X3D4IsZdcYnqPxFOixCYd7CXHIiySn71CzDmPPnHnNjrYnnBuTAbQ7HHgYw9xqFeln4D0ife2/aZtBGcPkJMGU5DYBZQbqgEBiUCcGGPKjKvoL/P2okWhK4AxkHw5fJ8hSecb3xLHua3rYauFeBJGBevij2wz/flFTngMHJNomYhchDFKOhe0uj6OcDcREgdfB3DthwMbg85DjZ+IX/mGfIUdYv6R9ER4J1NFeqBqi9+1iQ4zeFxFCNcJ9j8jLoP1roGvI/1Iwr/OVO3ftroY8yRahYNm/BNHlv0uZr+L7CFPJT2YZ8bwYB1CBQfS+X/vdaHE+WzAQMGDBgwYMCAAQMG/BfxDxVWWBikR3PIAAAAAElFTkSuQmCC>

[image23]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAmwAAAAxCAYAAABnGvUlAAADvUlEQVR4Xu3cS6i1UxgH8EdRbiWX3NVHJkpRrokoJhIZmDH4ZoQMpJRSUgYMTCSSQjKRSC7J6MQMUxOSj5RSUsKAXNb/vO9rv3udvffBd0bO71dPe6/17rPfc9aZ/HvW2rsKAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAD4Pzm51XWtjm51RqsTlq4CALCrn1u9Nxtf1uqVVkfM5t7oxnF8q29bnTebu6mGn49cf7/VUeP4/FYv1M73OVzPt7p6Nn6z1eWz8V74stUf3Vz+jgdq5xocrktq+J8k4AIAbPuq1YezcULVVg2BK45pdWC6OHNjq8fG53nNxTX8zGnj3Gu1/L6RMLKXLmj1fasju/nM5VrvnH6iOa6f6OS9r69hneYeGeenNVhlWou5M/uJTtb/t34SANjfPq3lMPJcLQe2WxeXliSo3DI+TxB7soau0NQZ2mr1ey131BLs9lLu/2c/2fxSi07f3B216PjF6TV0Dzc5q9XZNYTPebhLV+/OGoLrOq9246zFU91c7+NWX/STAMD+ttXqx/H57TUEtQS4nDe7r9YHtmwFfj3Wqo5WzqplazWBKvXu8uW/fVKL91lVm2zVEDjnErA2bVPeW0NoSlj7J1unD46P2XpNcIuHWp1Sw71369Bluzn3OVi7h7XIWt3fTwIA+9tLNZyZOrXV0zUEtgS4i1o9W+u7YvPO1uutTqzl7tXkyla/1s4zYHshQTFbr3M3tHqn1p8BS5croe2t/sIaz4yPCW7Tlm5C7HTWbDcJeQltCWur1mcuv1u2Q+dn8gAAtrc2E76eqEWgyJbiPbX+AwLTBw56L4+PfeC4udafy0pQTDdvXW2yKtz8UJuD0RSgDtbm100eHx9zn7tq6K5Fuoer1qA3dfSy9bpbRy8hMAG0P5MHAOxz2X5LYJuHs4ynrcBVcnZsftg+X92RUHJuDWEjoePA7PpntXtY+bcurOVwk67Xodr8tSEJa5fOxgdr8zblSbU4C5fw+EEt3j9hcdMHDuLu2nlmbt06ZP3zgYM+gAIAbHe/Pu/mPqohhK3yXQ2BLtucOWP2zTieQl/OkOXrPA61erGGLddra2/ljF3ulw815P75nd5udcX8RSs83I3z+97WzU0Szqa/69gauorXjNemNUhdNc6t8mg/UUMns5e1/qkW67q1dBUAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAgP/sL84akhiEE5X4AAAAAElFTkSuQmCC>

[image24]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAABIAAAAZCAYAAAA8CX6UAAAA+UlEQVR4Xu3Tv0sCcRjH8UdQUFRcBIWcGgShLdSlhsA5on/C/0caW9oaWoSChgbRv0FcKwJByKYCk9L38Xi/HtPLzeE+8ILjPndf+D53X5E4u+YMYywCppisrr9xj6r7QlSuMceJuV9BFx9omG4teQwwRNF0TkoY4REZ04VSwzvukDSdmxvRZ5xnN+ZcdB5tWwTiLPSFui2C6cjf83GTxRM+cWw6Lzn0ZPN8nBzgWfTrHoYrP/+ZTwu/eEDadF6i5pPAlehCl6bzEvXZy+iLzqdgulCORH80u60ULkTncitbFjnFi/hH4gdveBU9GjPRY9EU3VqcOPufJU75NY0EHNwQAAAAAElFTkSuQmCC>

[image25]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAF0AAAAaCAYAAADVLFAXAAADPklEQVR4Xu2YS8hNURTHl1BeeUcGkkdEQgkTDGRA8ghFSDIxUUYoKQOZkImU8iiPZEAxIIoiJkqZYSqJEUoMkMf/37q7e+66+5y9z76nm9i/+k32Pt939153rbX3uSKZTCaT+RcZCrfBs/A4nNU53XeGwavwO/zd8id8Wxh7DffCwfonfWcVvAznwknGiRJY1yh4Hx6FI+AC+BJuKj7UA1zEaXgbjjZzIebDz/AGHFQYHyiaJF9FE6Vyg5GMhIfhYzjdzPk4KO2EsH6As9uPdsM/fgbHFMa2w1ei31gqU+EFeBfOgwM6p6PYKLqJPXaiBTP9l2jWpTIOnoBP4ArRLzSG8/Cm6JfuPCdagQekYr8MNAN+yYwvgl/gOjMegh/EADPQzM5e29Qp+AMutRMtFopmO5+ri0sKZvYSqQiSB3aEM3C8Gef/uSLarkthCbAUbNDdZo6Z8TK4YH7gQ9FWMrlzOglu7BF8Id2bc7h1sv/HBo2JcL3lHIn/uyIMKvdbbHkTRBNtSmHMi1t0WdDtuIWluEa0NFmiLNWmcAlh+3mR1aLtJ7ROlxSsQGY3s7xJuD5W2xY74WOt+BcdG/T98B1cbCcagK2tqp8Td5iFKnK96IHMMyIls0MsE72M8FISpCxTYoNOXG/s5cD0EernQ+Ad0YN0pZnzkXpghmCWX5Ma50pZcMvGq3BXQ/b1ugeTJaaf8378SfQ5Ph+Luxo+Fa2AXoPv1sEbXxTT4HvpDq4L+iEzHkMxo9jvUzYV6ucc4+2Bm01tbcPhPvgc7pTAjaMCtj92C7bqKFxGsUxZrg6WK9/8Ysq2jOKmtkq9F5iq+zkraJdoUjTxAsd1cX1cJ9fLddeB9/WqNuhlB3wj7ROdm+LbKcsv6mAIwAzaDW/BsWbOBz+fbcq3EV5F+RLCDOd51CSsSLabe3CGmSvDnStMAHaHaPhNs1TZizeIBpy9lD8H9BNu4KLoS5l7nf4omhD0m7Tf9tiX/wZYFQ8kIeiE2TUTbobLpV4r+N/hyxArMuXsSoLZaX9hK5MHbC83ml5gEvF3JLsmn3yz7FsAU2BfLf7gU+URqXe1axK2SrueMk+KBj+TyWQymUwmI38A4ZSyGTlYx9sAAAAASUVORK5CYII=>

[image26]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAABYAAAAaCAYAAACzdqxAAAABTUlEQVR4Xu2ULUsEURSGj2BQ0KKCQcNiM4pY/ACDRo3rD7CYLWrbYhBEMBtFLEYFEYN/wigYXDaJIGpQ/HjeOfeye/cDdwymeeBhhz2HM2feubtmBf/NLNbwO3iLI0lHyjJ+mvfq8xqHk44m9rGKDzjeVItowCk+4xn2puVWBvAYD/EVp9NyRg9u4A5+4WZabs8EHmHZ/BFX0nLGlPngbfzA+bTcnlXzTWbwzVq36ccKjuEF3uFoY0MnKriEk/iIu0nVbM28rsH3ljNfvTBtoW1OzDMVJdwyH6ThufPtM7/JTVDXGqahJW/NrnPnK7Slto0ZakPFIHTjP+UbUb7KeRH3zF+cUFQ6413nqwOvOCLKTydDA3TEIrnyncNzHGz4TmdYZ1nxxBco9CS/5ruAT1b/f3jH9VDTr+7K6r//A3wJfbH3EodCvaCgoBt+AHZzRnAvsxTcAAAAAElFTkSuQmCC>

[image27]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAADwAAAAaCAYAAADrCT9ZAAACo0lEQVR4Xu2XTYhNYRjH/zKKfBVqEjXDRuwklI+SzGIWMyShrJDYKRsUzS1ZTKRoVkNqmiZhlkhSFAsLicVsppQFzWpSwoJ8/P/3OW/3vO85Z+455xppnF/9urf3Pd3O8z4f51ygoqJiJrGFTtBfkWN0mXeFTxf9AbtWn4/pUu+Kv8MiepIO0vN0ub/dnMv0A31PVwZ7DgV2i36io7TN307lMH1Cd9LZwV5ZOugbeozOpd10nG6KXzQVC+gwvUq/0A3+dp1Z9AQ9S3/SU/72lCgb5+gLuofO8bcLoUO+geSBX6QP6bzYWiar6XW6H1aqPf52nfWwgM/Q73Sbv52L+bAyfE2PIOfNBehe1YKng/W9yE5Wgl5Y5jbSr0hmTzdWoyvoffqWtscvKIgyfJC+gh2ADiIvu2AVFgasJClZh4L1VGqwH1pLJ2HlEecAbF8Bv0OynMqint4NK3WVvEq/GS6wrIDD9QSufzWolDVlbwTWs6IT9iMK0J1uWAGtokCHYIEvCfZCdC9pgeUO2PWvpp2Cfxqp7wpSP9Bpl9a/l+3fNNwwewkr8TzDTIedFljugF3/CmVV2XU9qoyqnIUO5E/0r9Dj7RJ9huKPq6zAstYT1GCBOdS/6uMdtB+NSaqS1zO6lf7Vy8EA7Lm8GY22KYKqS1UWBuYC1rTORGWrFwmVtUMlo0mtwPQocrTSv2vo3ch1KBeoww3Oa8H6cViiNHgz2Urv0YWxNXdSKvP4jSnzZfpXjx3NiFXhRkl0TxdgA25xtKbevwNLXmr1bacf0Xh//kaPRnt6cD9C4/34Cv0cXeeu1RtNs2k6nSjQB/Q27LXyJn2O7FfiGYEGnZKzL/osMvimFU13Das8qqpa6e9/ApWc/sLlsQ82SCsqKioq/ht+A8AeiHtOVSx/AAAAAElFTkSuQmCC>

[image28]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAsAAAAZCAYAAADnstS2AAAAc0lEQVR4XmNgGPogEojfAfF/JPwFiDOQFSEDRiCeD8T/gNgFTQ4DCALxaSB+AMTSqFKYwBiIvwLxGiBmQZPDANEMELcWoUugA5h7fwOxDZocBoC59y4Qi6PJYQDauJf6QRYLxM8YUKP4FRAnIysaBYMUAAD9Px2F6V8OKAAAAABJRU5ErkJggg==>

[image29]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAKEAAAAaCAYAAADfXDwAAAAFlklEQVR4Xu2aa6htUxTHh1CuR56R0D2E0nWjPPIsRSJ5RCIk+eKRyLuQzk2K5BGKkOuRKDefXOVRjkeIT0SUdJFHFEr4QB7jd8Ya7bHmmWvtufc5Z59zMn/17+w951przzXnf4055lxHpFKpVCp5tlVtlRZWxmJL1fZpYaWfg1XrpXbcQoEJ71OdmVZU8uypel21Jq1QdlK9qvq30T+qE1pHtNlV9bEMjv9WdWxTd00oH6aTVRervi7UR6q1MnlWqS5S7ZCUw86ql1SHpxXLnM3E+v45MW8sOvwgT+x0Up6C8TaJmbDr6eZa16m+UH2v2qddPQtT/ozk6zdXnaL6RnWM2ADepdqtqd9G9ZrqF9WBTRkR5zzV5zKhDhN7MM9RPSHWlq9Uu8cDAiepXhG775WCjxHB4NR21eLAYH7W/O3jRtXtql+bzzl44m9WfSJmFkyTgvEw4IzkB4ay51WniaUHRBqn61wM8Ixqu1C2mGDC01WHikWLPhOS3ryjOjetWOYcrbpe8mO44GCojdK/INlC9ZDqeLEOf7JdPQummBY75ncxw+ZgmuUJi/UYjZyUSMp1HlddK2bESO5cwJx3i50/aeiLPhMC7d0g1o990P6p5m8XTPETMcakwHgY8Ka0ImEP1VNi091bko9yF4pNoZfIIKfLwYBQHw12iOqe5jNtOlt1uViHR3Lnwv6qs5KySVFiQvqCY4alC5iUsbha8kY8QGy8VqcVCaQopDDMTMc136dUZ4j1NWkP0L9MtxwTgxD5Lb9BHWMPBAfaf6JYO7gmMwHX3Ks5ZizoODpn2LyPue6UgWk/UO0Y6vcVi6jcHFNoLt8Dz+l+Uh0p9vvcELnf+eG4HH5u17WXihITMvDkuYelFRkYXPJgpsJoxFIDwpTqDbEH9j3Vw2KLQgIF+fpjqqtUD4qlCeSsH8rgISEAsKCMOSFm87JHVE+LjRnpFzPf2EGAzvlBzGR9YDBfjHADdKg3mE7j6eX7LlKWD/4pg1Xtz2KmpJP76MoHl5oSE5Y+7E5qxFEM6HAeeTILSRZHDmOFkW5rjgHG/y9pt48H5o+kjDFm7D+VwWKRPJzZcVhK1wkmxAj87cLzQTcJhsT5fg5TDU8JUNaXDzKNpjkdN/aCDCIrA5AzcO7cUugcjFAipqjcVNjFKCYcFu0jbsRHZXQDOrSNoEBwcBg/zBWjso9bNFyuzO/j/lDmK2k0VnAoMaHng77yJCJ6zsee4LRYh0FpPhjrD1KtC98J7/HJdfzcNB8sgd9jCinRHZLf8+tiFBMyJY4COdd3qltktAfDoW0z0jZHGkQgZ7hcmd9H3B2ZiAk9H4zfCd2XioX2NU25h/+unM0b21UPJLjkGulbm5Jzl4pRTFg6HQO7BS+r9lPdKnNzxBJWhAkZUJ60rsgF/GCcRohc7BXyFuWyUF6aD3bV08HkKVekFbJ880EoMWFJP0fcgD4FM9OMY8QVYUI3DtNoDjZlWbnG/MEb8qa0I5ZHyK6crS+nIw97QPWlau921Sx95y41DHRcqOWg/1iVDlt8AQZ8UebmgKMakWOYmVg0eCoFfSaMPsiZ0BcmzIDOvE1IQ9dLO9EETIHJGHgXbwa2FvuhjTJ4H8zrvB+TYzepjmrqmbZjfVwZc0N/hzq2DLyDuT4D91uoR6ym2XboG/TFhlyYwY1t4z64H+43hZlkRoYPEv3LYmR1WtHAFtiVMujbLtaK9Z23jXZeoHo3lDEO7M0iPns5b6sICF7Gfd0rdl/xuPfFrsl4xLHBDyPDPhEXjPt+lYWD3YVnZfi7+f81RL23Jb8ircwfNvKJ3Pyt9EDORRhelVZU5gWpxTrVDc3nSg90EAlvadJbKYO8doPM3XKqdMDqi/8FPCKtqIwFm/ys5qsBK5VKpVKpVCqVDv4DtlZzwD7MgbAAAAAASUVORK5CYII=>

[image30]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAABAAAAAaCAYAAAC+aNwHAAAA/0lEQVR4XmNgGAUw0AnEv4D4PxK+CMRqUHkrIP6CJPcXiLOgcnAgDsR3gfg6lI0OGIF4ERDnAjEzmhwY2ADxbyBeygBRjA54gXgVECuhS8BAOgPEeSAaG9AE4tVAzIMuAQIgG0E2fwViYzQ5GPAD4mZ0QRgQAeKrUAxiYwMTGCCGYAWmQPwNiOczYPc/yNnLGSjwP0gjyAC8/ge5AOQSbACv/0GmHmCApAFc8d8HxA5o4nDADcR7gPgwAySu0YE5EM8GYlZ0CWSQAcRvgVgHTRzkpS1ALI8mjgFApvcA8XsgrgHiZCDeyQBJOBJI6ggCWSAOAGJfBuzhMQpGAVYAAGitK8jq9lHNAAAAAElFTkSuQmCC>

[image31]: <data:image/png;base64,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>

[image32]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAmwAAAAxCAYAAABnGvUlAAAEIUlEQVR4Xu3cS6jtUxwH8CWPPENeifJIygTlVaIMJBMSChkYGHgMDHSlRF1JkkgMlBQGDETIq6ScMlBIDGRCSSKUMiCPPNa3/3+d//+u7j7ncvft3M79fOrXXnut899n7z369lvrv0sBAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAACATePwWnv1kxtk334CAGCRS2rtP44PnS9sMglIV/aT1cG1LirTZz9qWtqlniub+/sGAJbg7Vr3jeNTan1bdp/u045I0FqpdVk3v8iH/UT1RK2DxvERtT4ow+suU97fGWUIgr+VKTQeUOu19kcAAL19ar1X65DZ3OOz8WZzXK2L+8nqm+75Hd3zZXi5DB28yP/7cloqJ9e6YPYcAGBVukh/1bpmNnf6bLyR8t6Or3VaGbYxrxjn0/27epyPw2qdUIYwtuiaJmEt671/au09e55O47Jlu7l1Lv+u9dRsLd29u2bPAQC2kTNUCSypN8u0FZgAMw8xOyMB6KNaXy+o66Y/3UbC1ee1jilDF/D3WheOa/fXOnYcn1OmLdH+mjfKdDbv2TJ0FXsPlOk7+LRsP9QtQ7qZ6a5la7Tfdl4py9+GBQA2kXSjnixD5yddqLPLsIX34ri2ngNr/VzrrH5hJyWQPTaOE2bm27d3juuR/9sCW3/NyvgYCWyLpCv3YBlC203d2rL9WmtrN5ezdbl7FQBgVc5M3d3N/TnOv1L+e/ha65p06o4uQ5jaXi3qLGUtwSz68LVWYFt0TR/YcnasP7P3S63ru7ll2FqmrlreR4Lh3EpZ/D0AAHuodM/mB9/Pr3XuOG7hK1uNLURk6zIBJ3eV5szVW2UIIC3wrBXY/q9sTbazXX34Sihr59jmgW2ta9I5O3IcR7ZVE9CabN1eNY6zdflCrVPLdN7s4TJsqea7y2fPdnKcNz4239c6qZv7qUzdytyJm23bJq/VuoIAAKsSvG6v9UytG2p9Nltr4SvVws7KOJ53qRKSWmhZdmC7udYfZehE5Wc2EngyzuP74zjrj4yPuXlirWsi76+FvHip1pbx8dFaX5WpC5bP0+R30vI7de2zX1uGn/94twzhtZ2Ra3IOrv+ZkVvLECTTvfui1pmztWyFXj57DgCwrvUCW+Y/GefTpUoIWXZg21VyY8WOaIEtW6ztc+WzJ6Al1K2Maznr10sXru+wLZLXyu/gtaAIALCudIt+KMOW5/O17inDVumPZegQfVeGc26v1rql1kO1bhvX07Xb3b3eT2zHiWX4DvKYbcyna91Y6+My3WWareCErHnHsbm07HgAyzbsO/0kAMCe7t5a+/WTGyThDgAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAGBj/AskO5ybhwGxVAAAAABJRU5ErkJggg==>

[image33]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAFMAAAAZCAYAAABNcRIKAAACNUlEQVR4Xu2XzytmURjHH02Kxo/xI6WIlagRE7GTnZRYIJZqFjM7zVhYWVjKzCzGjjQjKTsbU7NUdvwDCguSHSI2psl8v845vI7rdc7t7d5J51Ofeu+5P97nPvc+zzlXJBAIBAJxKIHjcB5OwwaY9+CI5CiEY/CNNZ4mdXAVVtk7bFrgBuyGZfADvIYTklxCy+EI/AnP4AGszjwgRfLhD3GM6Tv8C/v1NhO6DU9gkznIET6YL/agA0zmAGwX9QY4BZ4Qw/CPOMb0Fd7A93q7GG7CC1HJ8aENztmDniyJY+AJUC+q9a2LY0x8jSvhK739VlSpbcAiPebKS0om88IXrUNixsSJaAUewlZrnwsvKZmD8LOoecMrpteiehWTuA975P5N9SGNZE6JitvV36J6dDY4ey/AUr3tG9MdjfAYLotKchR8WhWiLp4pH8JixDgtuD3zeWIHniNY3pxEOzPGYsfERLHUOSl9tPYZuN6aFdWcM12DOxHjtPf2zOeJHXiO4KrGlLfBKSY+hU9a/jZMikomL+JDGmXOSdKugmzyRcjWwr7J49bAdTfzwYplO4ysWN78lZa/Dbwhnsw1qA9pJLMZDnnICuFXlg9OMdXCXVFfHqbZshduiVoevdNjruQqmUewxt6REqbtOcXEJ7UHZ+Ao/AXP9bgvcZPJ0uOHwqWoiqD8KuMNPNW3k4D/fSr3MbHcnyxzA2fablFl0CUP+6cPcZMZiIA9pc8eDAQCgUAgEPj/+QfcaoYd1pSBhgAAAABJRU5ErkJggg==>

[image34]: <data:image/png;base64,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>

[image35]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAACsAAAAZCAYAAACo79dmAAAB7UlEQVR4Xu2VPShGURzG/0KR74+SyUcW2Rik2CgfMbDYDIoyobAaGAwMBskig8jHqAzSKyMjNokslFHJwvN07q1zz7039573y/D+6td57/+czn3ue+85RyRHesmDNbDeaXmdDSolQoZSeAb34QIs8nZnjEm4C49EZQqEHXuinkqHT9cJN+EWHIL5nhHR4dyncND5beqGY7uiXfsICsugi/AKNol6Nfznd2ChNi4qHfAT/oQ47YyzCsvJ32C3VmuGz7Bfq0VlGN6KeljdBLyAFc44q7CrooLptTJ4Leq7Cl0AIczBXqPGgMewTavFDssFxgVnhuW4BLyBVVo9Cu2wWrvmw67BMa1GYod1Q4WFNes2jMBt8X//scOyZSAzVKrCcrFewi6zQyzC1sFH8YdKVdhxeAdrzQ6xCBsWKqweh2J4Dk9ggdFHYoflJJzMDOWG5Y7AncGGVvgh6n5BxA5LlkRNysld+NruRZ1oLlwgDU7rwlOuUYKP7QFRhwC3xiCswrbAV1Hfl0sPfBfvwlgXdfNlrcYznrUD8b9qnlTs458RhFVYMgqf4BScgA9wRrwHwiz8Fu9+ydPqS9RxrY8l85KmsITbDG9O+TtZSmAfLDc7HJIKm2lyYdPFn2H5HR3CF6fldTbYkOxnyPG/+QXJ4W39u/7vDgAAAABJRU5ErkJggg==>

[image36]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAACAAAAAZCAYAAABQDyyRAAABU0lEQVR4Xu2VsStFURjAP0kRkWRQDKRsUpSZZOQVg/gHDMpmMigZsMmkDAYWswyUVxZRRouBQfkLjMrvczydc949755380znV7+6fd+9fd/57jn3iiQSjWUE9/AIl7HNTTeWBXzCMezAbbzCLvumIrRjix/0GMBnXLFi3fiAa1asLnSc53iGvV7ORwt/4LgVa8JTLIuZSBT60CTe4KGYlcVwINUNKCf4jkNevIpmnMZb3MceN52LFgo1kBX/RQvP4x1uYqebjkLHW5bsQsEGdFMt4SOui9loRdFnryW7ULCBKXzFVfmbsxoqFIp/Y09hQ4qNv8KOZBfSBt6w34s7VPaBntkiG1CZw0+csWKtePGjXufiH8E+N10Tbfoet6zYsJjV65TrQhsZxUs8xkE3HWQCX8S8zkUxE92V/K9oTbS4/lx0NTHoiZjFksR/xBKJxP/yBUi0Oj3y5ZVlAAAAAElFTkSuQmCC>

[image37]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAADUAAAAZCAYAAACRiGY9AAACfUlEQVR4Xu2WX2hOcRjHv0KzxiRsKTVbbixtStLWFC5EaLVki9qK2mopF4pI25ULNEVy4UYulAspLSU3/pVWxFzMhSYRiuJuu+X77dnPe87v3e+857zvaOp869Pe8/tz9nzP8/yec4BcuXL9b1pIDpJ13rhTNTlErpMLpJksiK2w663kCrlG9sLum6gdZIz0kMXeXDlSoPvJZfKFTJHNsRWm5eQu6SVrSCt5Sk6gYEx/T5InpJGsJLdgD6FkrArkCBknR0lNfDqTdK89ZDsZRtjUMXLGG9tIXsMMSNr3jXT8WQE0kY9kd2QsUXKvjL0kZ0ltfDqzTiFs6iY5j3i5KWMypaxJ52AGNO60jDwjN1BcqolSze6Ebb4IS3s5SjKlgH/BzoqrjG5ynywlS2Z++6Y095i8ICsi46nlDukjchXxm6dRkqkG8g5mbBJmUg9R45ILPmTKH8+sKjJEPpP13lySkkxJG8gnmDGhknQlr4AVuB98xaaiDeQ4sjeQJFNrYZkZgHVArZOx57ByryfvURx82aYUvEy8QmWtPmRKD2sUNu8kk/dgxtQZQ8GHxoNS6tX19N7qRIqXXAmFTKm76Typ/KKS2QewMlxE7qA4eGdKWVYnDEqb1AjUENpRuRmnkCldv4W9c3zp3aWOKGn/D8TNryITKKyZVftgaW9Bxr6fQgpqmmzxxvW0H5LTiP/P1bAstM1cqympOekIOG0j31FY80+k83ib/EShq4mv5FJknQJ+AzN3GJYhZUBNI2q0i3wg/aQPluFBb828kspcpXiA7EK4u6ob6ntSpPoQUGdT+9S5KkUd5u68/VVtgn31pmEEKdtorly5cs1b/QbfwYPMI5Ij3gAAAABJRU5ErkJggg==>

[image38]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAADcAAAAaCAYAAAAT6cSuAAAB10lEQVR4Xu2WyytFURSHl6IIyaMQUhIpA/KaMFAyRBh4/AEmxsZKBgxlJBMDZWCiKMXgxgxTDAw8UkphRCGP37rLYd99zz6Pcu5N9ldf3dY659679t5r701ksVjSSTe8gR+K9/D26/ML3IR1zgtpoh7OwyU4BnMS094sw1fYqcUr4QZ8gO1aLlUMwRPYBPPgDNyBBepDJvLhPjyGJVqOKYWncJtCjtgvUAXP4LgSK4SHcFKJGWmAd3AdZmo5hxWSZ/jZVMJFPcIWJZYBV2GMZCY96SPprwk9ocDFPcE2PRExC5RcHMP/h/eKGi2eBH+BW7855MJdcv+RqOEi3H7XFE+ApzVG5n5jKuAF+Y/UKLwK4RGsjb/pjvPf3IoIVFyQfuuB73ALZmu5KPFaMYGK8+s3bt5FkuIGtVwqMBVhiifg12/NJGccH55ZWk6HZ7U8hHzE+H3nLLkXwcVdk5zDrvidb2Vwj2RpBDkwq+FwCPthUfxNM7yy3khaw4EHkVvEs00aSWZF7zcezQGSTWSNghUWFcXwAE4rMd6EeNZGlNg3XfCSfu6SPDL8MO9gfKd8JrlPdpD0XLpphedwimTG+XYyR/5L+s/AO2cvyYriK5nFYrFYLP+OT96MclxFxKbUAAAAAElFTkSuQmCC>

[image39]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAFQAAAAaCAYAAAApOXvdAAACpklEQVR4Xu2YT6iMURjGH6EIEboSZRILCwuJhT91FSuxkPxZW1AWIuJazcZCia6sWEgSYkkki2FjY2tDCpFSKGFB/jzPvOftO8dk7nzX3Jn75Tz1a74558yZ732+c973zABZWVlZ/70mkgEyJWqbQOaQ6VHbiFpD3pJfgSdkbjIi1SbyAzZWr/dhX1plnUMR/5bQtj9qOxraSukUeUNek4V/9Llk3FXyidwkk9LuSmsD+Y7CUGkpeYdRGKolfZkMky9kZdrdlJb/PjJEfpJDaXflpZgVe2zofPISozB0MblAdiBd9rFWwAw9BnuS69Luyqurhm6FrbxV5CtaV99UUicLyG3ynMyLB/RQs8giWOC6HxWRwfA+zuWTYfe4OvQrPXnh0VbeTGb7YHTZ0DrZSJaR9+RE0gvshPUrgBfob/48SD7CdpLu8yLZRc6SDzADpRp5EMY1YGlND+Ma+YbW1NY1Qz1/qhDpiWr1XYHlTKkGm1AGytQy+XMJeUxelWB385Pt5TvpLmz3SLp/FVQZ61IMiqWB9OijeMbMUM+f2jr60kZA1zJRk9VsaPN6PORPD35v1ObBX4raJL1voIeGev6U/Il6jtSK1HaXZHi/86erXfB9N7QOM86lvKQ8OkhOonVLlcmfXgR0Y53Sya+SdsH31VB9iQ7q2vYu5UflJxmno5KrbP6UpsGq6fYSqDCOpHbBd2LocYyRoWvJLTIjatOEqoxDKAqTpJU7HvKn5EVpW9T2N0NVpOI0NZM8hH1e87j+ydD1KI4eQseIPaFPE99DcaY7TT6HcT5W1TU+w/VSZ1D8lyBukCNI7/EpWR7G6/UZuUPOw3bk4Wisfh0qRsWl95r7OjmAdM5HsPSVheJfI6FrFVitWB3+s7KysrKysrKysiqp30Xjx2cvaMGoAAAAAElFTkSuQmCC>

[image40]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAEgAAAAaCAYAAAAUqxq7AAAB6UlEQVR4Xu2XzStEURjGX6Eo5atIFBtLK7FSLGwkG1mQrCwoKyKlLK3F0kYWoihLlsPGwn9ACsnCgg0W5ON5eu/bnHvHYMbMmNH51S/NOWeue557zzvniHg8Hk9GKIK1sCLSzs9sZ/+3jMA7+O74ACfdQQXIlMTnMx+0tcHboC0micElhUmuwzfYG+krZFpFA7GASCnckxQDqoYn8AI2hrsKmgZ4KeGAyIakGFA7fIS7sCTSV8hkLKBR0XU5E+3IEVWwGQ6IvsFlsCf4zGJqcHnUw86gnw+zGNaJLqd+WGODJUMBWf15gV2RvlwxDe9FH9KS6P0Mw1XRHxAGQlrgYTAuJjpBhrsNn0VXAVeDkZGArP6ciz6dn7AIr1LwQMJP9jM64JPo2PKgrQleiwZl8IFuSuIEGUJWAsqX+mP3MeG02QQ5IZfPJpi1gP66/hgWEOuO8ecB8XVNp/7wwvznP5VFlMX0K/IyoHT3P9yRDqVgn8TrSjJ+G9CCZCGgfKk/xIr0oNOWLCAWbfdHpRIeiX6f1zHSDmgM3kj4/MUt+bg7KIcsw1eJ38sOnBM9E1rbqeibS/j3DO7DNbgFZ52xK6JnSff7x7Bb9DrWxi3EfzpahWD95CbSTuXcXPKN4mbS4/F4PB6Px5MGH9qvn/nRJE+YAAAAAElFTkSuQmCC>

[image41]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAFkAAAAaCAYAAADcx/BtAAADv0lEQVR4Xu2YS6hOURTHl1CE5JFH6H4ekcgzM5RCDDzyGHjMDEwMpKSLGCAyEF1SEjHAwMSAhLhl4FkmHqUUSkoxEAMU1u+us+7Z9ne+8x3hiM6v/nXO3vs7Z++111p7nU+koqKi4r+hq2q0aqlqfHLfRTUmuf4nGKi6pfoW6LVqumq46kHU91Q1tuOXImujvguqXkkfcH0tGtNIz1SD7WedYNSHqtOqNapjqnZVm+pgOqxUeqpWi81lv2rcj935bBFb7Ia4Q9kq1rcs7lAmqa6ralF7CBv2UXVe1S3qYyP2qm6q+gTtU8UMPz9oAzb2q2px1F4GfVVXVbtUvVVTVI9Vy8NBeeApGBJjx7iRGRNC2G5XzYvaY/KeDWzCGVWP5J6NOKs6LPaOEKLrvpiXlw3zv6fqF7SxtidSH4WZLBIzBAYNqYl5VJaRJoiFTPeoPea46otqZtA2TNWSXGPkA0HfKLGUFc8FhqpOiXlSmWBYDMy7Q2aoPkjByJorFobhQ/Ci3WL5LzYy3kaYY+g8fHLPxQzrbFYtTK5rqjlpV2d6If9zwIWQE0lRZUPkvJV6I/tc90Ttmfjg8CG07RPLxRg57JulapX6cI6ZrHqvuqQaIeaJGPeumMdmQe67Lemh+Ep1SGw+zd73p8iyT157Jj6YaoDDiBTAwvCk+EGE6lExozXD8/E71ctEn1UXJc3BWXCokOvCCgRtDAc1YJWk7yoicnwcMTGeTmNjxrbJBQ97IVYiYUQOM19QvAEYbn3Slwded1Lq8zGREYaXb2oWePVK1Q2xRT4SKzvLhuj7bUYmf7KrJ1SDkj7PR+1iHwZHpNjB4/k4roEpEzkDACOyEd7PO/sn1yHk4stic2SuZdPImI3aM3GDsIidYt7j+AZQy+6Q5iWb4xPIqo8dvHpbcE9JGHp9CAuJS6gsSEPMuajY4EaR5HjFExvT15hVCdWBZ7aLVRjnxDzHcSMTLtSvzSbkeD7eFHckDBA7ECcm98zhiqReHsJYDsu4jMyiRbXiJ7REsqMnxO0TnyXMlTMma851+CfwJ7HKIcRfwI6xc0VolI+9jzIMo7Fp7uXuLfwu3Ej+o2gV+9oivfwt+NrkoByZ3LMOvv6ohArPi1DgwyEObTcyD+TBebBZRAIFulcEYWXxJmgnahbYzzqgoMfobWKVBYfjOtUdsZQzJB36V2Djqao4hPnDCntwEFMJFQYvbXRyT5PmIfWr4CFsEpAnKZtYTE2ab25ZMA/+ICPNzJbiqbOioqKioqKioqKiIuA7EvXkmqeGNXwAAAAASUVORK5CYII=>

[image42]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAGMAAAAaCAYAAACjFuKcAAADLElEQVR4Xu2YTahNURTH/0JRPkL5iHo9GZJ8xIR6A8SAAQr5mBgw9pkXI3P5GkjqZYqJTJAkZkyVUuqRFIUJA8nH+ltn99ZZd99z7tlyXNm/+te9Z5179t5rrb32OhfIZDKZzF9kimhItF20UjSxZO1zdok+iH4YfRIdtDf9Yc6gPIezonHGvkT0ztipi8ZOpokuiF6IhqHBOC96KzqMzqCkjnncXavSViTASYyIvovWOVubhDl8E21xNs6RiXNDNNnZFoieiO6LZjrbItFz0WV0BoSkjsmAxxw+XrQWmhQMXGNmQBczKppfNrUKM/uI6IvoGdTJlhXQeyx00i3RG6jjY2yEOvsYytlPUsYkYYds9oaCndAEaAwH/AzNgAnO1iZcNOv8aehCfTbHHENHM7OZ4d7RgZBsr0WDzpYyJokFg7tyefF5IfR3jf25G/rgQ97QMpw8Fz9L9BiazduM3TsmlFfO/YC5HuMq4vc1HTMQC4a9l40E/TppzFxPWNBX0Rpna5vgGLIaultZ7weKa94xXPADdDolRqjxV9z1pmMGQjD2ieZB72dTwKAnE7YwD5w5ztaNU6JXDXQbnQdrDOsYJskJ6IKZLCwd3jF0wsvinrpgBOd5ZzUdMxCex46Ma2QJ5K7yz28EB+uH84JYx5DponvQM2FHYbOOmSp6hN6CwTa3LhikbsxArEzx/LI7jyWqUZnql/OCeMeQVaKP0G6JHYp1jD0zqtpIJhmTLbbOpmMGYsHwgTsq2mS+V5J6XrBWs0T0qtnQ/ruOmGM4R7akXDhf4C6Vzb+cRVvVzma7Pgp18OKyKWlMEguGhc/gS+JSb+hG6vsF3075hturmB3+pSlGzDGEwb+LeJkJNpba2G/JHuhv2b7SSZaUMUldMAZFD6HJ2BOcRL+cFzzg74jWe0PBMmhmxxwzAO2AuPi5zhZKznXoeWD5nTG7vYETBuImtNNjUCvZC62HfFgQ/4fZb29qkXMoz+UptLR5+H/ZiL9YwCBcE70XncTYf1P8zpLjd2bqmPzu/7OiL21HFa7HgvhfwezfAA3GEBp2M5lMJpPJZDKZTCbzr/MTfeEJ8tEw3v8AAAAASUVORK5CYII=>

[image43]: <data:image/png;base64,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>

[image44]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAIAAAAAaCAYAAAB/w1TuAAAFRElEQVR4Xu2Za8hlUxjH/xOK3K9DUV7JLUJuETof5FJIRgzmw0QiicYYIgqTXEIuifCBJD6MUm65xDG+uHwQxcilkMgHRCgjl+fXc1bv2uvd++y19z7zdmbe/at/55y19l577bWe9TzPWkfq6enp2RhYZNrZtJtps6RuIbKNaY/R5waBhgemk03bj8qYgF3DBfPIaaYfTR+aLjJtXaxekBxous30telV0+6F2g5sYbrR9JXpStPlpg9Md5vWyh88n8yYvjPdKfcCKVuZLjA9arrLtH+xujF7m5amhQ1gVd4k788tpn2L1dlsZ7pKs+3sp/L3Z1G+b3rGtHlS1xgaeNj0rIqrLDxkqA3ocio4wvSH6Yy0Qu6ZXjetlvfrMNOnpiXxRRlg1Bj6m6Z/TE8Wq7M5Wt6fE0yHml4y/WdaqfLJq4J7h3IPvKPpUtN6VbdDf4eawNwca/rGdHBaYdxgeiAtrIFYTcxmVQQ1jeHjDOA6uXdikAIXmtaZFkdldWAAZ5mOk3ubNgaAJ3peHqLC+4WFQ/95j1wYZwzxzNFv3o/3/EnlHnhiBkBMYQD2TCuMVZrtUB0MBtd/Iu9ccM+4VuI59blUGUAYlHSyjjL9rvy+xmCgLIC0zRzCvb/JV3CAhYMXuDoqq+Me+T0Xj35va3pHc9sOTMwAaIgHX6+5q5RYtlNSVgbJyIvyuJy20YYqA2AlsCLSyQrXY8xN6WIA5E73yxMy2gngpRhTPnOhrV00O3545F9UPckTMwBWKJ1FuCBiIlZIQpIDOcRDah6Dx1FlAKE8nayq8hy6GEAZjMca+VgOilXZMPZPm76V5zhlTMwAsLzb5R0OhoA+UnlYSMFSMYDO2WgERvm35g4gBkHf0smaJgM4Rt4XQiBj2wSScJJxJp4d2Smq9qg3y0P3TFLeGh6Ei2Xr9at8oMlE62BS2DrGSV8qEqNF4YYKqOe6c00/yLel6QCSS0yzAbBDecP0lLqfWxxg+l7VbfGsV0xvy3OELYvV9TDhxPiyiTnV9K/yYhgG8Jrc4qt0h2mHcEMFuLJb5dn8Y/J4mFI10VXlOUzKADDWR0z3qlnCWwXzQhjA4C9L6oD6gfygDJ1TqM1gH9ODKnfdYUDZXtVxkmlFWtgBBu9xuSGkIYg+4x3SyQr9JftuyiQMIEx+nEjjTTlRzYH7GUMUe72QTJb1jR0P73yeyhdxLTTwgspdxzLT56a90ooS2ONzIsXnpDhengOkSSBeYig/bIn7jRGuH30GuDYn9NQZQF07lK+UT158DeHz7Oj3uHaCASO+B+gTBlB2FkMd20S2i61gy8QDSVpiCAskgEuS8nFwLau2LFa1IQxIagCAcZIkzYx+M6CrTe+q+P8F7/CX/KBrHMEAcLfp5NS1w/XLTX/KEzL6FfSz3JChrh0W2hemJ1R8Bw6U2AoePiqLwQCGarkL4KbnTNfID274ztbvPvkfDU3dCteebnpPbvWtOhUxzgBwkRxdvyU/yWPyeYd4u8TzX5bnMaui8hi8BZMW7344TPrYdMjomrp2gvHEu6cgQhUhC+raARLcL+VJOLsgvBzJOOVldDIA4iwrHRjQI+VJxEDlISEX9q8YEplwvBo4K8eicxlnAIDB8UcJfT5Rc3cLASb5irSwBfPVDmM/UP17QScDmHbqDCCXa1Xucpsybe3AgjCAnF1IFeyNyUu6bsmmrR3AA5KzDLWJGgAvxdkCp2HE9ib5SADvkW4j2zBt7RAWLpHvevjcZGGlEAvXyDP8SQzexs75ps/kf0AdpHYLo6enp6enp2eB8j9ugyWfbOzqfQAAAABJRU5ErkJggg==>

[image45]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAADAAAAAZCAYAAAB3oa15AAACBElEQVR4Xu2WyysGURiHX6EoiihE+VxKNjZuKXYWJBssLJSFWPgDWFpJtq7lkpUUyoYsKNedkgV2EilRWCllwe/XmfGdOWZ8F0PSPPXUN+85Z3rPnMv7iQQEBPwUibAFTll2wFRHD28SYC0cEzWW7+H7fo1kOA6HYAnshc/wFBZq/dxg8gNwDxbBLLgIZ0S915UUS79ogtswX4t1wTc4B5O0uEklvIP1WqwYXol6ryvssAVHRc34uwxKOFmbAngDL2COFjcZFpVsnhZLhwdwQdQKucKGCrgJ50UtX7xUwRPYp8WYEBMzk9PhLtiQz33S4C48gpla3JMyuGLJ337ALfEK18R7u9qJek3AjEeEq8DV2Bd1K3guXwR4+Lj8T7DGaNPxWqW4J2DDQZMS/0Ta4S1sNBsMeDZ4RsxEvz0BwsM9DQ9hyNn0Jfzix7DabHDBK1GveFRwwATckdi/PpPnhEutZ16fvE4zPno4YfuqfE7UngBvIt5IUcH9PwvXRd1OsSROWLCYjF64skUVJDsJVteQOA81r+AHWK7FOO5MVGX+Eibpx1WaK+q8PMJrzXu4LOFC1iOqXixpMa4W60Wn9UwaRI2t02IOmDi3B7cJt0vM+8zALmRuslDZtMIXUX8d9BVug5ei6kg3PIf9Rh8HzXBE/KnCfsFcOEH6l/IKCAgI+E+8A79YZHWdIvbgAAAAAElFTkSuQmCC>

[image46]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAABAAAAAZCAYAAAA4/K6pAAAAOUlEQVR4XmNgGAWjYLAAISDeAcSPSMC1YJ2DBjACsTAQS5KABcA6oYAViJ2BOIQEbA7WOQpGwaABAA3SEFBWOsY4AAAAAElFTkSuQmCC>