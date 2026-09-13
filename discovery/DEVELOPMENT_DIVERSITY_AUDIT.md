# Development Pool Diversity Audit

## 1. Full Development Pool Overview
- **Total Pairs**: 6481
- **Total Threads**: 4242
- **Unique Customers**: 4388
- **Date Coverage**: 2015-01-14 to 2017-12-03

## 2. Thematic Distribution Comparison (Heuristic)
*Note: These counts are generated via simple keyword heuristics and are strictly provisional. They are NOT ground truth labels.*

| Theme | Full Dev Count | Full Dev % | Discovery 300 Count | Discovery % | Difference |
|---|---:|---:|---:|---:|---:|
| PLAN_PROMOTION *(removed — see DECISION_LOG #5)* | 120 | 1.9% | 4 | 1.3% | -0.5% |
| ACCOUNT_ACCESS | 944 | 14.6% | 46 | 15.3% | +0.8% |
| APP_TECH_ISSUE | 1408 | 21.7% | 70 | 23.3% | +1.6% |
| CONTENT_CATALOG | 870 | 13.4% | 35 | 11.7% | -1.8% |
| UNKNOWN_OTHER | 2132 | 32.9% | 99 | 33.0% | +0.1% |
| SUBSCRIPTION_BILLING | 784 | 12.1% | 36 | 12.0% | -0.1% |
| GENERAL_HOW_TO_INFO | 65 | 1.0% | 3 | 1.0% | -0.0% |
| FEATURE_FEEDBACK | 133 | 2.1% | 4 | 1.3% | -0.7% |
| ARTIST_SUPPORT | 25 | 0.4% | 3 | 1.0% | +0.6% |

## 3. Edge Case Estimation
| Category | Full Dev Est. % | Discovery Est. % | Diff |
|---|---:|---:|---:|
| actionable | 61.2% | 63.0% | +1.8% |
| ambiguous | 9.7% | 11.7% | +1.9% |
| conversational | 11.5% | 9.0% | -2.5% |
| context-dependent | 47.4% | 50.7% | +3.3% |
| multi-intent | 27.2% | 28.7% | +1.5% |

## 4. UNKNOWN_OTHER Subtype Comparison
| Subtype | Full Dev % of UNK | Discovery % of UNK |
|---|---:|---:|
| ambiguous | 29.6% | 35.4% |
| conversational/closure | 18.6% | 18.2% |
| context-dependent | 144.1% | 153.5% |
| irrelevant/off-topic | 39.9% | 35.4% |

## 5. Diversity Check (300 Sample)
- **Unique Threads**: 288 / 300
- **Unique Customers**: 288 / 300
- **Short Threads (len=2) in Sample**: 41.3%

## 6. Boundary Cases Coverage (in 300 Sample)
- **account vs billing**: 21 examples
- **content vs tech**: 22 examples
- **feature vs tech**: 8 examples
- **plan vs billing**: 10 examples
- **artist vs content**: 2 examples
- **how-to vs account**: 7 examples
- **geography modifier**: 103 examples
- **multi-intent**: 86 examples
- **context-dependent**: 119 examples
- **ambiguous**: 22 examples

## 7. Assessment & Next Steps
### Assessment
**A. Discovery sample is sufficiently diverse**

*Reasoning*: The 300-example sample closely matches the heuristic thematic distribution of the overall DEV pool. It contains enough unique threads and captures boundary cases at similar rates to the full pool.

## What this means for me (User)
- Do not review the current `HUMAN_REVIEW.md` yet. Let's decide if we want to proceed with resampling based on this audit.
- Pay attention to the UNKNOWN_OTHER subtypes: if too many are just 'thanks' or ambiguous links, we aren't learning anything about the taxonomy from them.
