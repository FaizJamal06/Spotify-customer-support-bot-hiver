# Hiver Take-Home: Final Design & Experiment Plan (v3)

---

## 1. Data Partitions

All SpotifyCares conversation threads are split into **three disjoint pools**.
The split is at the **thread level**: every tweet in a conversation goes to the same pool.

```
All SpotifyCares threads (~27K conversations)
  │
  ├── DEVELOPMENT POOL  (~15%, ~4K threads)
  │     Used for: taxonomy discovery, pilot labeling,
  │               few-shot example selection, TF-IDF training
  │     Never used for: evaluation, retrieval index
  │
  ├── RETRIEVAL POOL    (~65%, ~18K threads)
  │     Used for: building the historical retrieval index
  │     Never used for: taxonomy decisions, training, evaluation
  │
  └── TEST POOL         (~20%, ~5.5K threads)
        Used for: golden evaluation set sampling (200 examples)
        Never used for: taxonomy decisions, training, retrieval index,
                        few-shot examples, architectural decisions
        Untouched until final evaluation
```

### Named data subsets within each pool

| Name | Source pool | Size | Purpose |
|---|---|---|---|
| **Discovery sample** | DEVELOPMENT | 300 customer messages | Manual inspection for taxonomy development |
| **Pilot labels** | DEVELOPMENT | 100 examples (subset of discovery sample, or additional) | Labeled with frozen taxonomy; used to train TF-IDF+LogReg and select few-shot examples |
| **Few-shot examples** | Pilot labels (DEVELOPMENT) | 3-5 per intent (~25-40 total) | Drawn from pilot labels; used in LLM classification prompt |
| **Retrieval index** | RETRIEVAL | All (customer_msg, brand_reply) pairs from retrieval-pool threads | Embedding index for historical retrieval |
| **Golden evaluation set** | TEST | 200 annotated examples | Final evaluation; no data from this set influences any design decision |
| **Judge calibration subset** | Golden evaluation set (TEST) | 40 examples (subset of golden 200) | Human-graded for judge-human agreement analysis |

### Why three pools instead of two

With a two-pool split (retrieval + test), taxonomy discovery would have to use either retrieval data (which contaminates retrieval) or test data (which contaminates evaluation). A three-way split keeps all three concerns cleanly separated:

- **Development** data is explored, inspected, and labeled — it's "seen" data
- **Retrieval** data is indexed but never directly inspected for taxonomy/design decisions
- **Test** data is sealed until evaluation

---

## 2. Data Flow Dependency Graph

```
┌──────────────────────────────────────────────────────────────────────────┐
│                                                                          │
│  twcs.csv                                                                │
│    │                                                                     │
│    ▼                                                                     │
│  Filter to SpotifyCares + Reconstruct threads                            │
│    │                                                                     │
│    ▼                                                                     │
│  Thread-level 3-way split (seed=42)                                      │
│    │                    │                    │                            │
│    ▼                    ▼                    ▼                            │
│  ┌────────────┐   ┌──────────────┐   ┌─────────────┐                    │
│  │ DEVELOPMENT│   │  RETRIEVAL   │   │    TEST     │                    │
│  │   POOL     │   │    POOL      │   │    POOL     │                    │
│  │  ~15%      │   │   ~65%       │   │   ~20%      │                    │
│  └─────┬──────┘   └──────┬───────┘   └──────┬──────┘                    │
│        │                 │                   │                            │
│        ▼                 │                   │                            │
│  ┌────────────┐          │                   │                            │
│  │ Discovery  │          │                   │                            │
│  │ sample     │          │                   │                            │
│  │ (300 msgs) │          │                   │                            │
│  └─────┬──────┘          │                   │                            │
│        │                 │                   │                            │
│        ▼                 │                   │                            │
│  Manual inspection       │                   │                            │
│  → Draft taxonomy        │                   │                            │
│  → Freeze taxonomy       │                   │                            │
│        │                 │                   │                            │
│        ▼                 │                   │                            │
│  ┌────────────┐          │                   │                            │
│  │ Pilot      │          │                   │                            │
│  │ labels     │          │                   │                            │
│  │ (100 msgs) │          │                   │                            │
│  └──┬─────┬───┘          │                   │                            │
│     │     │              │                   │                            │
│     │     ▼              │                   │                            │
│     │  Few-shot          │                   │                            │
│     │  examples          │                   │                            │
│     │  (3-5/intent)      │                   │                            │
│     │     │              │                   │                            │
│     ▼     │              ▼                   │                            │
│  ┌──────┐ │     ┌──────────────┐             │                            │
│  │TF-IDF│ │     │ Retrieval    │             │                            │
│  │+LR   │ │     │ index        │             │                            │
│  │train │ │     │ (embeddings) │             │                            │
│  └──┬───┘ │     └──────┬───────┘             │                            │
│     │     │            │                     ▼                            │
│     │     │            │              ┌─────────────┐                    │
│     │     │            │              │ Golden set   │                    │
│     │     │            │              │ sampling     │                    │
│     │     │            │              │ (200 msgs)   │                    │
│     │     │            │              └──────┬──────┘                    │
│     │     │            │                     │                            │
│     │     │            │              Human annotation                   │
│     │     │            │              (frozen taxonomy)                  │
│     │     │            │                     │                            │
│     │     │            │                     ▼                            │
│     │     │            │              ┌─────────────┐                    │
│     │     │            │              │ Golden 200   │                    │
│     │     │            │              │ (annotated)  │                    │
│     │     │            │              └──────┬──────┘                    │
│     │     │            │                     │                            │
│     ▼     ▼            ▼                     ▼                            │
│  ╔══════════════════════════════════════════════════╗                    │
│  ║          EVALUATION (all experiments)            ║                    │
│  ║                                                  ║                    │
│  ║  Exp 1: Classification (majority vs LR vs LLM)  ║                    │
│  ║  Exp 2: Confidence calibration                   ║                    │
│  ║  Exp 3: Retrieval k-ablation                     ║                    │
│  ║  Exp 4: Judge calibration (40 subset)            ║                    │
│  ║  Exp 5: Triage evaluation                        ║                    │
│  ╚══════════════════════════════════════════════════╝                    │
│                                                                          │
└──────────────────────────────────────────────────────────────────────────┘
```

### Arrows that do NOT exist (prohibited data flows)

| From | To | Why prohibited |
|---|---|---|
| TEST pool → taxonomy decisions | Would bias taxonomy toward test distribution |
| TEST pool → few-shot examples | Would leak test examples into classification prompt |
| TEST pool → TF-IDF training | Would leak test text into feature extraction |
| TEST pool → retrieval index | Would let system retrieve the answer directly |
| DEVELOPMENT pool → retrieval index | Would contaminate retrieval with "seen" development data |
| Golden set → any design decision | Golden set is a final test; design must be frozen first |

---

## 3. Per-Experiment Data Access Rules

### Experiment 1: Classification Comparison

| System | Allowed to see | Must NOT see |
|---|---|---|
| Majority baseline | Pilot labels (for majority class count) | Golden 200 labels |
| TF-IDF + LogReg | Pilot labels (100 texts + labels for training); TF-IDF fit on pilot texts only | Golden 200 texts/labels; retrieval pool; test pool |
| LLM few-shot | Few-shot examples (from pilot labels); intent definitions (from taxonomy) | Golden 200 texts/labels; pilot label distribution |

**Evaluated on**: Golden 200 (test pool). Gold labels compared to predictions.

### Experiment 2: Confidence Calibration

| Input | Source |
|---|---|
| (predicted_intent, confidence) | LLM classifier output from Experiment 1 |
| gold_intent | Golden 200 annotations |

**No additional data access.** This experiment uses only the outputs already produced in Experiment 1.

### Experiment 3: Retrieval k-Ablation

| Component | Allowed to see | Must NOT see |
|---|---|---|
| Retrieval index | Retrieval pool (customer, brand_reply) pairs | Development pool; test pool |
| Generation prompt | Customer text from golden 200; retrieved pairs from retrieval pool; classified intent from Exp 1 | Gold SpotifyCares response; gold labels |
| LLM judge | Customer text; generated reply; retrieved evidence | Gold SpotifyCares response; gold labels |

**Evaluated on**: Golden 200. Same examples across all k conditions.

### Experiment 4: Judge Calibration

| Component | Allowed to see |
|---|---|
| LLM judge | Same inputs as Experiment 3 (customer text, generated reply, retrieved evidence) |
| Human grader | Same inputs as LLM judge (customer text, generated reply, retrieved evidence); same rubric |
| Agreement analysis | Both LLM and human scores for the 40-example subset |

**Neither the judge nor the human sees**: gold SpotifyCares response, gold intent label, gold triage label.

### Experiment 5: Triage Evaluation

| Component | Allowed to see |
|---|---|
| Triage rules | Classified intent + confidence (from Exp 1); customer text (from golden 200) |
| Evaluation | Triage predictions vs. gold triage labels (from golden 200 annotations) |

---

## 4. Intent Discovery Procedure (Revised)

### Data source: DEVELOPMENT pool only

**Step 1**: Sample 300 customer messages from development-pool threads. Not from test pool.

**Step 2**: Read each message. Write a free-text note describing the required support action.

**Step 3**: Group bottom-up by support action. Merge operationally identical groups. Split groups requiring different actions.

**Decision rules**:
- A valid intent must appear in ≥10 of the 300 examples (≥3.3%)
- A valid intent must be distinguishable by a human annotator (target: >85% self-consistency on re-test)
- Every intent must map to a distinct support workflow

**Step 4**: Add UNKNOWN as a valid intent category (see §7).

**Step 5**: Pilot-label 100 development-pool examples against the frozen taxonomy. These 100 serve as:
- Training data for TF-IDF + LogReg baseline
- Source of few-shot examples for LLM classifier
- Validation that the taxonomy is applicable

**Step 6**: Freeze the taxonomy. No changes after this point.

**Starting hypothesis**: 6-8 intents based on Phase 1 data analysis. The actual number is determined by this procedure, not pre-decided.

---

## 5. Golden Set: Sampling & Annotation

### Sampling

**Source**: TEST pool only (never touched before this point).

**Coverage heuristic** (for sampling diversity, NOT for labeling):
```python
coverage_groups = {
    'account_kw':   ['account', 'login', 'password', 'hack', 'email'],
    'payment_kw':   ['charge', 'payment', 'refund', 'billing', 'cancel'],
    'playback_kw':  ['play', 'crash', 'bug', 'error', 'freeze', 'audio'],
    'content_kw':   ['song', 'album', 'artist', 'playlist', 'missing'],
    'plan_kw':      ['premium', 'student', 'family', 'hulu', 'free', 'ads'],
    'no_match':     []
}
# These keywords determine which bin a message is SAMPLED from.
# They do NOT determine the gold label.
```

Sample 200 messages ensuring:
- At least 20 from each coverage group
- At least 20 from the `no_match` group (tests coverage completeness)
- 10-15 deliberately challenging: messages <20 chars, multi-keyword, thread follow-ups

### Annotation

Each example is annotated using the frozen taxonomy from Step 6 of §4.

| Field | Type | Notes |
|---|---|---|
| `example_id` | int | Unique |
| `tweet_id` | int | For traceability |
| `customer_text` | string | The customer tweet |
| `thread_context` | string or null | Prior thread messages, if any |
| `gold_intent` | enum | From frozen taxonomy, including UNKNOWN |
| `gold_triage` | enum | AUTO_HANDLE or ESCALATE |
| `escalation_reason` | string or null | If ESCALATE, why (using tiered framework from §8) |
| `difficulty` | EASY / MEDIUM / HARD | Annotator confidence |
| `notes` | string | Free-text |

**What the annotator does NOT see during annotation**:
- The coverage-group keyword that caused sampling
- The SpotifyCares actual response
- Any system prediction

### Annotation terminology (corrected)

**Intra-annotator consistency** (what we can measure with one person):
- The same annotator labels 40 of the 200 examples a second time, ≥48 hours later
- Compute Cohen's κ between the two passes
- This measures how consistent the annotator is with themselves
- It does NOT measure whether the labels are correct

**Inter-annotator agreement** (requires a second person):
- If a second annotator is available, they independently label a 30-40 example subset using the same guidelines
- Compute Cohen's κ between the two annotators
- This measures whether the taxonomy and guidelines are clear enough for two people to agree

**Recommendation**: Perform intra-annotator consistency (same person, 40 examples, two passes). If a second person is available, also perform inter-annotator agreement on 30 examples. Report whichever is available. Clearly label which type of agreement is being reported.

---

## 6. Three Classifiers — No Assumed Winner

### Majority Baseline

```python
def majority_baseline(pilot_labels):
    majority_class = Counter(pilot_labels).most_common(1)[0][0]
    return lambda text: majority_class
```

Training data: pilot labels (count only).
Expected performance: ~15-25% macro F1 (depends on class balance).
Purpose: absolute floor.

### TF-IDF + Logistic Regression

```python
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline

clf = Pipeline([
    ('tfidf', TfidfVectorizer(max_features=5000, ngram_range=(1, 2))),
    ('lr', LogisticRegression(max_iter=1000, class_weight='balanced'))
])
clf.fit(pilot_texts, pilot_labels)  # 100 examples from DEVELOPMENT
```

Training data: 100 pilot-labeled examples from development pool.
TF-IDF vocabulary: fit on pilot texts only.
Expected performance: unknown — 100 training examples is small, but the task may be easy enough.
Purpose: tests whether a classical ML pipeline is competitive.

### LLM Few-Shot

Few-shot examples: 3-5 per intent, drawn from pilot labels (development pool).
Model: configurable (initially gpt-4o-mini).
Temperature: 0 for reproducibility.
Output: `{intent, confidence, reasoning}` with UNKNOWN as valid intent.

Expected performance: unknown — likely better than LogReg due to pre-trained knowledge, but this is a hypothesis.

### What we do NOT assume

- We do not assume the LLM wins. If TF-IDF+LogReg matches or beats the LLM on 100 training examples, that is a meaningful and reportable finding. It would suggest that the intent categories are lexically distinguishable and don't require deep semantic understanding.
- We do not assume the LLM confidence is useful. Experiment 2 determines this.

### Evaluation

All three classifiers evaluated on the same golden 200 examples.
Metrics: macro F1, per-class precision/recall/F1, confusion matrix, accuracy (for reference).
The winner is whichever achieves the highest macro F1. If the difference is small (<3 points), we report them as comparable and discuss why.

---

## 7. UNKNOWN Intent — Policy Statement

### Status: STATED TAKE-HOME POLICY, not a dataset-derived fact

UNKNOWN is included as a valid intent category because:

1. **Any real classifier will encounter messages it cannot classify.** A system without an UNKNOWN category must force every ambiguous message into a defined bucket, which guarantees wrong classifications on edge cases.

2. **UNKNOWN maps to a clear support action: escalate to a human.** This is a policy choice — we are choosing to escalate uncertainty rather than guess.

3. **This is a design decision for the take-home**, not a claim about what Spotify's actual support system does. The real SpotifyCares might handle ambiguous messages differently.

### How UNKNOWN is used

- The LLM classifier can output UNKNOWN
- The triage rules automatically escalate UNKNOWN messages (Tier 1 safety rule)
- In evaluation, we track: how often UNKNOWN is predicted, what the gold labels actually are for UNKNOWN-classified messages, and whether UNKNOWN is catching genuinely ambiguous cases or misclassifying clear ones

---

## 8. Triage Policy — Three Tiers (Revised)

#### Tier 1: Safety Principles (non-negotiable policy decisions)

| Rule | Justification | Status |
|---|---|---|
| UNKNOWN intent → ESCALATE | Policy: do not auto-respond when uncertain | Take-home policy |
| Security language detected → ESCALATE | Principle: security issues require human judgment | Universal safety |
| Legal language detected → ESCALATE | Principle: legal risk requires human judgment | Universal safety |

#### Tier 2: Empirically-Determined Rules (set by experiments)

| Rule | Determined by | Status |
|---|---|---|
| Low confidence → ESCALATE (if threshold exists) | Experiment 2: calibration | Hypothesis: may be adopted or abandoned |
| Specific intents → ESCALATE by default | Experiment 5 + analysis of golden set: which intents have DM-redirect as the dominant historical response? | Hypothesis |

#### Tier 3: Stated Assumptions (for transparency)

| Rule | Assumption |
|---|---|
| Anger keywords → ESCALATE | Assumes keyword detection of extreme frustration is useful; may produce false positives on quoted text or sarcasm |

Every rule is labeled with its tier in the output.

---

## 9. Retrieval k-Ablation + Manual Inspection

### Experimental conditions

| Condition | k | Retrieved pairs |
|---|---|---|
| A | 0 | None — LLM generates from general knowledge |
| B | 1 | Single most-similar pair |
| C | 3 | Three most-similar pairs |
| D | 5 | Five most-similar pairs |

All conditions use:
- Same 200 golden examples
- Same LLM model
- Same prompt template (only the retrieval section varies)
- Same temperature (0)
- Same LLM judge

### Prompt for k=0

```
You are a customer support agent for Spotify on Twitter.

CUSTOMER MESSAGE: {customer_text}
CLASSIFIED INTENT: {intent}

Draft a helpful, friendly reply under 280 characters.
If you cannot resolve the issue directly, suggest the customer
send a DM for private assistance.
Do not fabricate specific URLs or troubleshooting steps.
```

### Prompt for k>0

```
You are a customer support agent for Spotify on Twitter.

CUSTOMER MESSAGE: {customer_text}
CLASSIFIED INTENT: {intent}

SIMILAR PAST CONVERSATIONS (how Spotify support has handled similar issues):
{for i, (cust, reply) in enumerate(retrieved_pairs):}
  Example {i+1}:
    Customer: {cust}
    Spotify support: {reply}

Draft a reply consistent with how Spotify support historically responds.
Use the examples above as evidence for your response style and content.
Keep it under 280 characters.
Do not fabricate information not supported by the historical examples.
```

### Metrics per condition

- LLM judge scores: Relevance (1-5), Groundedness (1-5), Helpfulness (1-5), Tone (1-5)
- Mean per dimension per condition
- Paired comparison: k=0 vs best k>0, Wilcoxon signed-rank test

### Manual retrieval inspection

For 20 randomly sampled golden examples, manually inspect the top-5 retrieved pairs and assess:

| Question | Record |
|---|---|
| Is the most-similar retrieved customer message actually about the same issue? | yes/no + notes |
| Is the retrieved SpotifyCares response substantive or a DM redirect? | substantive / DM-redirect / other |
| Would a human use this evidence to draft a better response? | yes / partially / no |
| Does similarity score correlate with actual usefulness? | qualitative observation |

This inspection determines whether high cosine similarity translates to actual retrieval utility, or whether the embeddings are matching surface features (e.g., "@SpotifyCares help") rather than issue semantics.

Report: Include a table of 5-10 representative retrieval examples with the inspection notes. This is more convincing than aggregate statistics alone.

---

## 10. LLM Provider (Lightweight)

One abstract interface. One concrete implementation. No framework.

```python
class LLMProvider:
    """Single interface for all LLM calls."""
    
    def __init__(self, classify_model, generate_model, judge_model,
                 api_key, cache_dir="cache/"):
        self.classify_model = classify_model
        self.generate_model = generate_model
        self.judge_model = judge_model    # different model reduces self-preference bias
        self.api_key = api_key
        self.cache = DiskCache(cache_dir)  # cache responses for reproducibility
    
    def classify(self, customer_text, few_shot_examples, 
                 intent_definitions) -> dict:
        """Returns {"intent": str, "confidence": float, "reasoning": str}"""
        ...
    
    def generate_reply(self, customer_text, intent, triage_decision,
                       retrieved_pairs) -> dict:
        """Returns {"reply": str, "grounding_notes": str}"""
        ...
    
    def judge(self, customer_text, generated_reply,
              retrieved_evidence, rubric) -> dict:
        """Returns {"relevance": int, "groundedness": int,
                    "helpfulness": int, "tone": int, "reasoning": str}"""
        ...
```

To switch providers: replace the API call implementation inside each method. The interface and caching remain unchanged.

---

## 11. Complete Experiment Dependency Table

| Experiment | Inputs | Data sources allowed | Must NOT see | Outputs |
|---|---|---|---|---|
| **Data prep** | twcs.csv | Full dataset | — | Three disjoint thread pools |
| **Taxonomy discovery** | 300 customer messages | DEVELOPMENT pool only | RETRIEVAL, TEST | Draft taxonomy |
| **Pilot labeling** | 100 messages + taxonomy | DEVELOPMENT pool only | RETRIEVAL, TEST | Labeled pilot set |
| **Golden annotation** | 200 messages + taxonomy | TEST pool only | System predictions, SpotifyCares responses | Annotated golden set |
| **Retrieval index** | (customer, reply) pairs | RETRIEVAL pool only | DEVELOPMENT, TEST | Embedding index |
| **Exp 1: Classification** | Golden 200 texts | Pilot labels (training), golden texts (prediction) | Golden labels (until scoring) | Predictions + metrics |
| **Exp 2: Calibration** | Exp 1 outputs + golden labels | Exp 1 predictions, golden labels | — | Calibration curve, threshold or null |
| **Exp 3: k-ablation** | Golden 200 texts, retrieval index | Retrieval pool (index), golden texts | Gold SpotifyCares response, golden labels | Generated replies per k, judge scores |
| **Exp 4: Judge calibration** | 40-example subset, LLM judge scores, human scores | Exp 3 outputs (for 40 examples) | Gold labels, gold SpotifyCares response | Agreement statistics |
| **Exp 5: Triage** | Exp 1 + Exp 2 outputs, golden triage labels | Classification predictions, calibrated threshold, golden triage labels | — | Triage metrics |

### Critical isolation rule

> **The golden 200 annotations influence ZERO design decisions.** The taxonomy is frozen before golden annotation begins. The classifier is configured before golden evaluation. The retrieval index is built before golden evaluation. The triage rules are set (with Tier 2 thresholds from calibration) before triage evaluation. The golden set is a **final exam**, not a development tool.

---

## 12. Ordered Implementation Plan

| # | Phase | Task | Data used | Depends on | Hours |
|---|---|---|---|---|---|
| 1 | Data | Filter SpotifyCares, reconstruct threads | Full CSV | — | 2-3 |
| 2 | Data | Three-way thread-level split + leakage verification | All threads | #1 | 1 |
| 3 | Discovery | Sample 300 from DEVELOPMENT, manual inspection | DEVELOPMENT | #2 | 3-4 |
| 4 | Discovery | Draft taxonomy, freeze | Discovery notes | #3 | 1-2 |
| 5 | Discovery | Pilot-label 100 from DEVELOPMENT | DEVELOPMENT | #4 | 2 |
| 6 | Data | Compute embeddings for RETRIEVAL pool | RETRIEVAL | #2 | 1 |
| 7 | Data | Build retrieval index | RETRIEVAL embeddings | #6 | 0.5 |
| 8 | Annotation | Sample 200 from TEST, annotate golden set | TEST | #4 | 5-6 |
| 9 | Annotation | Re-annotate 40 (intra-annotator), compute κ | Golden subset | #8 | 2 |
| 10 | Pipeline | LLM provider (classify, generate, judge) | — | — | 2-3 |
| 11 | Pipeline | TF-IDF + LogReg baseline | Pilot 100 (train) | #5 | 1 |
| 12 | Pipeline | Majority baseline | Pilot 100 (count) | #5 | 0.5 |
| 13 | Pipeline | Triage rules (Tier 1 only initially) | — | #4 | 1 |
| 14 | Pipeline | Retrieval module | Retrieval index | #7 | 1 |
| 15 | Pipeline | Reply generator | — | #10, #14 | 2 |
| 16 | Eval | Exp 1: Run all 3 classifiers on golden 200 | Golden 200, pilot labels | #8, #10, #11, #12 | 2 |
| 17 | Eval | Exp 2: Confidence calibration | Exp 1 outputs | #16 | 1 |
| 18 | Pipeline | Update triage rules (add Tier 2 if calibration supports it) | Exp 2 results | #17 | 0.5 |
| 19 | Eval | Exp 3: Retrieval k-ablation (k=0,1,3,5) | Golden 200, retrieval index | #15, #16 | 3-4 |
| 20 | Eval | Manual retrieval inspection (20 examples) | Exp 3 retrieval results | #19 | 1-2 |
| 21 | Eval | LLM judge on all conditions | Exp 3 outputs | #10, #19 | 2 |
| 22 | Eval | Exp 4: Human grades 40 examples, agreement analysis | Exp 3 outputs (40 subset) | #21 | 3 |
| 23 | Eval | Exp 5: Triage evaluation | Exp 1 outputs, golden triage labels | #18, #16 | 1 |
| 24 | Analysis | Failure analysis (top 5) | All experiment outputs | #16-#23 | 2-3 |
| 25 | Report | Report + decision log + "misleading headline" | All results | #24 | 3-4 |
| 26 | Repo | README + reproducibility verification | All | #25 | 1-2 |

**Total: ~40-48 hours**

---

## 13. Leakage Verification (Automated)

```python
def verify_all_isolation(dev_pool, ret_pool, test_pool, 
                         retrieval_index, golden_set, pilot_set):
    """Run before any experiment. Hard stop on failure."""
    
    dev_threads  = {t.thread_id for t in dev_pool}
    ret_threads  = {t.thread_id for t in ret_pool}
    test_threads = {t.thread_id for t in test_pool}
    
    # 1. Three pools are disjoint
    assert dev_threads.isdisjoint(ret_threads),  "LEAK: dev ∩ retrieval"
    assert dev_threads.isdisjoint(test_threads),  "LEAK: dev ∩ test"
    assert ret_threads.isdisjoint(test_threads),  "LEAK: retrieval ∩ test"
    
    # 2. Tweet-level disjointness
    dev_tweets  = {t.tweet_id for t in dev_pool}
    ret_tweets  = {t.tweet_id for t in ret_pool}
    test_tweets = {t.tweet_id for t in test_pool}
    assert dev_tweets.isdisjoint(ret_tweets)
    assert dev_tweets.isdisjoint(test_tweets)
    assert ret_tweets.isdisjoint(test_tweets)
    
    # 3. Retrieval index only contains retrieval-pool tweets
    index_tweets = {p.tweet_id for p in retrieval_index}
    assert index_tweets.issubset(ret_tweets), "LEAK: non-retrieval tweet in index"
    
    # 4. Golden set only contains test-pool tweets
    golden_tweets = {ex.tweet_id for ex in golden_set}
    assert golden_tweets.issubset(test_tweets), "LEAK: non-test tweet in golden set"
    
    # 5. Pilot labels only contain development-pool tweets
    pilot_tweets = {ex.tweet_id for ex in pilot_set}
    assert pilot_tweets.issubset(dev_tweets), "LEAK: non-dev tweet in pilot set"
    
    # 6. No pilot tweets in retrieval index
    assert pilot_tweets.isdisjoint(index_tweets), "LEAK: pilot tweet in index"
    
    # 7. Near-duplicate warning (not hard stop)
    near_dupes = find_near_duplicates(golden_set, retrieval_index, threshold=0.95)
    if near_dupes:
        print(f"INFO: {len(near_dupes)} near-duplicate pairs (cosine>0.95)")
        print("Natural overlap — report count in 'misleading headline' section")
    
    print("All isolation checks passed.")
```

---

## 14. Repo Structure (Final)

```
hiver-spotify-support-agent/
├── README.md                          # Reproduce headline results in <15 min
├── requirements.txt                   # Pinned versions
├── config.py                          # Model names, seeds, pool fractions
│
├── data/
│   ├── prepare.py                     # Filter + thread reconstruction
│   ├── split.py                       # Three-way thread-level split
│   └── verify_isolation.py            # Automated leakage checks
│
├── discovery/
│   ├── sample_discovery.py            # Sample 300 from DEVELOPMENT
│   ├── intent_taxonomy.md             # Frozen taxonomy + definitions
│   └── pilot_labels.jsonl             # 100 labeled examples (DEVELOPMENT)
│
├── golden_set/
│   ├── sample_golden.py               # Stratified sampling from TEST
│   ├── golden_200.jsonl               # Annotated evaluation set
│   ├── annotation_guidelines.md       # Labeling rules
│   └── consistency_check.py           # Intra-annotator κ on 40 re-labeled
│
├── pipeline/
│   ├── llm_provider.py                # LLM interface + concrete implementation
│   ├── classifier.py                  # LLM few-shot classification
│   ├── triage.py                      # Tiered escalation rules
│   ├── retrieval.py                   # Embedding + cosine similarity retrieval
│   └── generator.py                   # LLM reply generation
│
├── baselines/
│   ├── majority_baseline.py           # Always predict majority class
│   └── tfidf_logreg.py                # TF-IDF + LogReg on pilot data
│
├── evaluation/
│   ├── run_classifiers.py             # Exp 1: three-way comparison
│   ├── calibration.py                 # Exp 2: confidence calibration
│   ├── run_k_ablation.py              # Exp 3: k=0,1,3,5
│   ├── retrieval_inspection.py        # Manual inspection helper (20 examples)
│   ├── judge.py                       # LLM-as-judge
│   ├── judge_calibration.py           # Exp 4: human-judge agreement
│   ├── triage_eval.py                 # Exp 5: triage metrics
│   └── failure_analysis.py            # Top-5 failure modes
│
├── report/
│   └── report.md
├── decision_log.md
│
└── cache/                             # Disk-cached LLM responses
    └── .gitkeep
```

---

## 15. What NOT to Build

| Component | Why not |
|---|---|
| FAISS / vector database | ~25K vectors; brute-force cosine similarity sufficient |
| Fine-tuned classifier | No large labeled set; 100 pilot examples not enough for fine-tuning |
| Separate sentiment model | Captured by LLM classification or keyword heuristics |
| Cross-encoder reranker | Must first prove retrieval helps at all (Exp 3) |
| Multi-provider abstraction | One provider class is enough; swapping is a method-level change |
| Banking77 integration | Wrong domain; no evidence of transfer value |
| Web UI | Not required |
| Automated clustering for taxonomy | Manual inspection of 300 examples is more reliable and more defensible |
| Self-critique / reflection loops | Unjustified complexity; no evidence of value |

---

## 16. Self-Challenge (Final)

| Question | Answer |
|---|---|
| Can taxonomy decisions leak into the golden set? | No. Taxonomy is built from DEVELOPMENT pool. Golden set is from TEST pool. |
| Can few-shot examples leak? | No. Few-shot examples are from pilot labels (DEVELOPMENT). Golden set is from TEST. |
| Can retrieval leak? | No. Retrieval index is from RETRIEVAL pool. Golden set is from TEST. |
| Can TF-IDF vocabulary leak? | No. TF-IDF is fit on pilot texts (DEVELOPMENT only). |
| Is every threshold empirically determined? | Yes. Confidence threshold from Experiment 2. Retrieval k from Experiment 3. Triage Tier 2 rules from Experiment 5 analysis. |
| What if TF-IDF+LogReg beats the LLM? | Report it honestly. Discuss why (perhaps the intents are lexically simple). Still use LLM for generation (no classical alternative for open-ended text generation). |
| What if retrieval doesn't help? | Report it honestly. Discuss what kind of data would make retrieval valuable. Still include the ablation as evidence — a null result is a valid finding. |
| What if judge-human agreement is low? | Report it with the raw numbers and qualitative analysis of disagreements. Discuss which dimensions are most/least reliable. Do not hide the finding. |
| Is the system explainable in a live interview? | Yes: 3 data pools, 5 pipeline steps, 5 experiments. Each has one purpose. |
| Can results reproduce in <15 minutes? | Yes: evaluation runs on 200 cached examples. Classification + generation + judging ≈ 10 minutes with cached LLM calls. |
