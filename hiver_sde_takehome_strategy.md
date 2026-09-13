# Hiver SDE Intern Take-Home — Golden Dataset + AI Support Agent Strategy

## 0. The Core Goal

The Hiver assignment is testing whether you can:

> **turn a messy real-world dataset into a working AI system and prove it works.**

The assignment explicitly says:

> **“The proof is worth more than the system.”**

So the goal is NOT to build the fanciest agent possible.

The goal is to show a clean, defensible pipeline:

```text
MESSY REAL-WORLD DATA
        ↓
UNDERSTAND IT
        ↓
STRUCTURE IT
        ↓
DEFINE THE PROBLEM
        ↓
BUILD AI SYSTEM
        ↓
EVALUATE IT PROPERLY
        ↓
UNDERSTAND WHERE IT FAILS
```

There are two major pieces:

1. Build a strong **golden evaluation dataset**
2. Build a **Hiver-style customer-support agent** that can classify, retrieve, resolve, and escalate

The golden dataset and the agent should be designed together.

---

# 1. What Hiver Is Asking For

The take-home requires choosing one brand from the Customer Support on Twitter dataset and building an AI support agent that can:

1. Classify incoming customer messages into a small set of intents defined from the data
2. Draft a reply grounded in how that brand historically resolved similar issues
3. Decide whether the message should be auto-handled or escalated to a human, with a stated reason

The deliverables include:

- A runnable repo
- A **150–250 example hand-labelled golden evaluation set**
- A short note explaining how the set was sampled and labelled
- An automated evaluation harness
- An LLM-as-judge rubric
- Evidence showing how well the LLM judge agrees with a human
- At least two baselines
- Failure analysis with the top 5 failure modes
- A mandatory section: **“What is misleading about my headline number?”**
- What you would do with one more week
- A decision log with 10–15 non-obvious decisions

The system only needs to operate on a reasonable subsample. Hiver will not run it on the entire ~3M-row dataset.

---

# 2. What We Learned From the Hiver Approach

The Hiver video approach, as summarized from the video, is roughly:

```text
Incoming support message
        ↓
AI Tagging / Classification
        ↓
Sentiment Analysis
        ↓
Information Extraction
        ↓
Context / Knowledge retrieval
        ↓
Autonomous Resolution
        ↓
Human escalation when required
```

For the take-home, mirror the logic rather than trying to reproduce Hiver's entire production infrastructure.

A practical version is:

```text
Incoming Twitter message
        ↓
Intent classification
        ↓
Information extraction
        ↓
Sentiment / tone
        ↓
Retrieve similar historical cases
        ↓
Check whether evidence is sufficient
        ↓
Generate grounded response
        ↓
Auto-handle OR escalate
```

This gives the project a clear Hiver-style architecture.

---

# 3. Do NOT Over-Engineer the Agent

Do not build an unnecessarily complicated multi-agent system.

Avoid:

```text
Agent
 ├── Agent 1
 │    └── Agent 2
 ├── Agent 3
 └── Agent 4
```

A controlled, modular pipeline is better:

```text
                 ┌───────────────────┐
                 │ Customer Message  │
                 └─────────┬─────────┘
                           ↓
                 ┌───────────────────┐
                 │ Intent Classifier │
                 └─────────┬─────────┘
                           ↓
                 ┌───────────────────┐
                 │ Info Extraction   │
                 └─────────┬─────────┘
                           ↓
                 ┌───────────────────┐
                 │ Sentiment / Tone  │
                 └─────────┬─────────┘
                           ↓
                 ┌───────────────────┐
                 │ Historical Case   │
                 │ Retrieval         │
                 └─────────┬─────────┘
                           ↓
                 ┌───────────────────┐
                 │ Evidence /        │
                 │ Confidence Check   │
                 └─────────┬─────────┘
                           ↓
                    ┌──────┴──────┐
                    ↓             ↓
              AUTO-HANDLE      ESCALATE
                    ↓             ↓
             Grounded Reply   Escalation Reason
```

This is easier to build, evaluate, debug, and explain in an interview.

---

# 4. Recommended Tech Stack

Keep infrastructure simple.

## Backend

**Python + FastAPI**

Why:

- Lightweight
- Easy to structure
- Good for an AI API
- Easy to run locally

## LLM

Use a strong but reasonably priced model for the actual pipeline.

A practical option is:

**GPT-4o-mini**

Use a stronger model for evaluation/judging if needed.

## Embeddings

**text-embedding-3-small**

or an equivalent inexpensive embedding model.

## Vector Database

Use:

- **ChromaDB**, or
- **FAISS**

For a take-home, ChromaDB is convenient because it requires little setup.

## Database

**SQLite**

Enough for:

- conversation history
- agent outputs
- evaluation metadata
- escalation decisions

There is no reason to introduce PostgreSQL unless there is a specific need.

## Data Processing

- Python
- pandas
- NumPy
- scikit-learn

## Evaluation

Python + a custom evaluation harness.

---

# 5. Overall Data Pipeline

Start with the ~3M tweet dataset and narrow it down.

```text
3M Twitter conversations
        ↓
Filter to ONE brand
        ↓
Reconstruct conversations/threads
        ↓
Remove obvious garbage
        ↓
Explore the data
        ↓
Identify common customer problems
        ↓
Define intents
        ↓
Create labelling guidelines
        ↓
AI-assisted pre-labelling
        ↓
Human validation
        ↓
Refine labelling process
        ↓
Create stratified golden set
```

---

# 6. Step 1 — Choose ONE Brand

Do not try to build across dozens of brands.

Choose a brand that has:

- Enough conversations
- Many recurring customer problems
- Enough brand responses
- Enough historical support interactions
- Useful variation in customer behaviour

The selected brand becomes the focus of the entire project.

---

# 7. Step 2 — Understand the Conversations

Before defining intents, inspect the actual conversations.

Look for:

- Common customer problems
- Recurring resolutions
- Conversation length
- Number of turns
- Customer vs brand messages
- Incomplete conversations
- Duplicate tweets
- Spam/noise
- Ambiguous cases
- Cases with useful brand responses
- Cases that appear unresolved

Do not immediately ask an LLM to invent your taxonomy.

Derive it from the actual data.

---

# 8. Step 3 — Define Your Intent Taxonomy

You might eventually end up with something like:

```text
REFUND
PAYMENT_ISSUE
DELIVERY
ACCOUNT_ACCESS
TECHNICAL_SUPPORT
CANCELLATION
COMPLAINT
OTHER
```

But these are only examples.

The actual intents should come from the selected brand's data.

Keep the taxonomy relatively small.

Too many overlapping intents make classification and evaluation harder.

---

# 9. Create Clear Labelling Guidelines

This is one of the most important parts of the annotation process.

For every intent define:

- Intent name
- Definition
- What belongs in the intent
- What does NOT belong
- Borderline cases
- Examples

Example:

```yaml
refund:
  description: >
    Customer requests money back for a completed purchase.

  include:
    - explicit refund requests
    - requests to return money
    - asking whether a purchase can be refunded

  exclude:
    - payment failures
    - questions about whether a payment went through
    - general order status questions
```

This guideline becomes the source of truth for both human and AI annotation.

---

# 10. AI-Assisted Pre-Labelling

Do not manually label thousands of examples.

Use an LLM to create a first-pass annotation.

This is what was meant by:

> “synthetic labelling to get a first cut”

It does NOT mean generating fake customer conversations.

It means:

```text
Real conversation
        ↓
LLM
        ↓
First-pass label
```

Example output:

```json
{
  "intent": "payment_issue",
  "confidence": 0.94,
  "reason": "Customer reports being charged twice for the same order."
}
```

The LLM should receive your intent definitions and examples.

---

# 11. Add a Short Justification

Instead of asking only:

```text
What is the intent?
```

ask for:

```text
What is the intent?

Give a short justification based only on the conversation.
```

Example:

```json
{
  "intent": "refund",
  "confidence": 0.91,
  "reason": "Customer explicitly requests money back after a purchase."
}
```

This is useful because when the model is wrong, you can inspect why.

Do not overcomplicate this with huge chains of reasoning. A concise rationale/evidence field is enough.

---

# 12. Validate the AI Labelling

Do NOT blindly trust the LLM-generated labels.

Take a manually reviewed sample.

For example:

```text
100 AI-labelled examples

Correct: 92
Incorrect: 8

Approximate agreement: 92%
```

Inspect the errors.

You may find problems such as:

```text
REFUND ↔ PAYMENT_ISSUE
DELIVERY ↔ ORDER_STATUS
COMPLAINT ↔ TECHNICAL_SUPPORT
```

Then improve your definitions and prompt.

---

# 13. Iterative Annotation Loop

Use this loop:

```text
Define intents
      ↓
LLM pre-labels
      ↓
Human checks sample
      ↓
Find errors
      ↓
Improve definitions/prompt
      ↓
LLM labels again
      ↓
Human checks again
      ↓
Final annotation process
```

This is a strong engineering story for the report.

---

# 14. The Golden Set

The assignment requires:

> **150–250 hand-labelled examples**

A practical target is around **200 examples**.

The final golden set should be genuinely human-verified.

The best description of the workflow is:

> We used an LLM-assisted annotation process to accelerate initial labelling, then manually reviewed and corrected the final evaluation set.

Do NOT present the golden set as:

> “Claude generated 200 labels.”

The AI is assisting the annotation process.

The final evaluation set is human verified.

---

# 15. Why Random Sampling Alone Is Not Enough

Do not simply select:

```text
200 random tweets
```

and call them your golden set.

A random sample can accidentally contain:

- Mostly easy examples
- Mostly one intent
- Mostly short messages
- Mostly neutral customers
- Very few complex conversations
- Very few ambiguous cases

Your agent may then look better than it really is.

Instead, use **stratified sampling**.

---

# 16. Stratification Dimensions

Your golden set should cover important variations.

## Intent

Make sure all important intents are represented.

```text
REFUND
PAYMENT
DELIVERY
...
```

## Message/conversation size

```text
Short
Medium
Long
```

## Number of turns

```text
1 turn
2–3 turns
4–6 turns
7+ turns
```

## Complexity

```text
Simple
Moderate
Complex
```

## Tone

```text
Neutral
Confused
Frustrated
Angry
```

## Other useful dimensions

Consider:

```text
Clear vs ambiguous
Complete vs incomplete context
Single issue vs multiple issues
Normal wording vs unusual wording
```

The goal is not perfect mathematical balance.

The goal is:

> **Make the evaluation set representative of the situations your agent needs to handle.**

---

# 17. Use Python for Objective Stratification

Not every property requires an LLM.

Use deterministic code wherever possible.

Python can determine:

```text
message length
number of turns
number of messages
brand
date
conversation size
```

Interpretive properties can use LLM assistance:

```text
tone
complexity
ambiguity
```

The principle is:

> **Use normal code wherever the property is objective. Use an LLM where interpretation is actually required.**

This is a good engineering decision to demonstrate.

---

# 18. Golden Set Isolation

This is extremely important.

Do not accidentally put the golden evaluation examples into the RAG knowledge base and then test the exact same examples.

Bad:

```text
Golden example
      ↓
Vector DB
      ↓
Exact same conversation retrieved
      ↓
Looks correct
```

Instead:

```text
TRAINING / KNOWLEDGE DATA
        ↓
RAG corpus

GOLDEN SET
        ↓
NEVER USED TO BUILD THE SYSTEM
        ↓
Evaluation only
```

This prevents leakage and makes your results credible.

---

# 19. What Should Be in the RAG Knowledge Base?

Do not reduce everything to only:

```json
{
  "input": "...",
  "intent": "...",
  "response": "..."
}
```

The Twitter dataset contains conversations and context.

Preserve useful historical information.

For example:

```json
{
  "conversation_id": "123",
  "brand": "chosen_brand",
  "customer_message": "...",
  "conversation_context": [
    "...",
    "...",
    "..."
  ],
  "intent": "refund",
  "brand_response": "...",
  "resolution": "...",
  "resolved": true
}
```

The RAG system should answer:

> **“How did this brand historically resolve similar problems?”**

not simply:

> “What tweet looks semantically similar?”

This makes the RAG system much more aligned with the assignment.

---

# 20. The Hiver-Style Agent

The agent architecture mirrors the Hiver product vision while staying focused and defensible. The actual system flow is:

```text
Customer Message
        ↓
Intent Classification
        ↓
Deterministic Triage / Escalation Decision
        ↓
Historical Interaction Retrieval
        ↓
Evidence Sufficiency Check
        ↓
AUTO-HANDLE → Grounded Reply
       OR
HUMAN ESCALATION → Reason
```

**Key Architectural Principles:**
- **Intent is a first-class evaluated component.** The 8-label frozen taxonomy drives the core routing.
- **Triage/escalation is a first-class evaluated component.** The system deterministically decides what is safe to auto-handle versus what must be escalated.
- **Retrieval is used for grounding.** The system retrieves historical customer-support interactions and brand responses (with observable resolution evidence where available) to ground response generation.
- **Sentiment and Information Extraction are optional.** We will only add a sentiment layer or a heavyweight information extraction stage if downstream evaluation proves a concrete need for them. The architecture must remain intentionally simple and modular.

---

# 21. Stage 1 — Intent Classification

Example:

Customer:

> “I've been charged twice for the same order”

Output:

```json
{
  "intent": "payment_issue",
  "confidence": 0.94
}
```

The classifier should use your defined taxonomy.

---

# 22. Stage 2 — Information Extraction

Extract structured information that downstream steps may need.

Example:

```json
{
  "order_id": null,
  "issue": "duplicate_charge",
  "requested_action": "refund",
  "important_entities": []
}
```

If an order number exists:

```json
{
  "order_id": "12345",
  "issue": "delivery_delay"
}
```

This mirrors the information-extraction concept in the Hiver approach.

---

# 23. Stage 3 — Sentiment / Tone

You do not need an elaborate sentiment model.

A simple classification can be enough:

```text
neutral
confused
frustrated
angry
```

Tone can help inform escalation.

For example:

```text
intent = refund
tone = angry
```

may deserve more caution than:

```text
intent = refund
tone = neutral
```

Do not automatically assume “angry = escalate” without testing it. Treat it as a policy that can be evaluated.

---

# 24. Stage 4 — Retrieve Historical Resolutions

Use:

```text
customer message
+
conversation context
+
intent
```

to retrieve historical cases.

Retrieve several candidates, such as the top 5.

Prefer cases that:

- Have the same/similar intent
- Are semantically similar
- Were successfully resolved
- Contain useful brand responses
- Provide clear evidence for what to do

---

# 25. Stage 5 — Evidence Sufficiency Check

Do not blindly do:

```text
retrieve → generate
```

Instead:

```text
Retrieve
   ↓
Is evidence sufficient?
   ↓
YES              NO
 ↓                ↓
Generate        Escalate
```

Example:

```json
{
  "can_auto_handle": true,
  "reason": "Multiple similar historical support interactions were retrieved and provide sufficient evidence for the requested resolution."
}
```

Or:

```json
{
  "can_auto_handle": false,
  "reason": "The request is ambiguous and no sufficiently similar historical resolution was found."
}
```

This makes the agent safer and more explainable.

---

# 26. Stage 6 — Grounded Response Generation

The response generator should receive:

- The target customer message
- Relevant preceding context (using `created_at` chronology)
- The predicted intent
- Retrieved historical customer-support interactions
- Historical SpotifyCares responses associated with those interactions
- (Relevant extracted information only if a downstream need is established)

The prompt strictly requires the LLM to:
- Answer the customer's actual issue
- Use historical evidence for how similar requests were handled
- Follow observed support behavior
- Avoid inventing policies
- Avoid inventing refunds
- Avoid inventing timelines
- Avoid inventing unsupported facts
- **Abstain or escalate when evidence is insufficient**

**Conceptual Distinction:**
- **BAD**: "Find a similar tweet and imitate it."
- **GOOD**: "Use relevant historical customer-support interactions and SpotifyCares responses as evidence for how similar requests were handled."

We must use cautious wording: these are "historical support interactions, with resolution evidence where observable," not universally confirmed "resolved cases."

---

# 27. Stage 7 — Escalation

Start simple.

Potential escalation rules:

```text
ESCALATE if:

intent = OTHER

OR confidence < threshold

OR retrieval evidence is insufficient

OR request is highly ambiguous

OR multiple unresolved issues are present

OR the case appears too risky for automatic handling
```

Otherwise:

```text
AUTO-HANDLE
```

The exact thresholds should be determined experimentally.

A good decision log might document:

> We initially used sentiment as a hard escalation rule, evaluated the effect, and changed it based on observed false escalations.

---

# 28. Full Agent Architecture

```text
                    ┌───────────────────┐
                    │ Customer Message  │
                    └─────────┬─────────┘
                              ↓
                  ┌──────────────────────┐
                  │ Intent Classification│
                  └──────────┬───────────┘
                             ↓
                  ┌──────────────────────┐
                  │ Information          │
                  │ Extraction            │
                  └──────────┬───────────┘
                             ↓
                  ┌──────────────────────┐
                  │ Sentiment / Tone     │
                  └──────────┬───────────┘
                             ↓
                  ┌──────────────────────┐
                  │ Historical Case      │
                  │ Retrieval            │
                  └──────────┬───────────┘
                             ↓
                  ┌──────────────────────┐
                  │ Evidence / Confidence│
                  │ Check                │
                  └──────────┬───────────┘
                             ↓
                    ┌────────┴────────┐
                    ↓                 ↓
              AUTO-HANDLE          ESCALATE
                    ↓                 ↓
             ┌─────────────┐    ┌────────────┐
             │ Grounded    │    │ Reason for │
             │ Response    │    │ Escalation │
             └─────────────┘    └────────────┘
```

---

# 29. Evaluation Is the Center

Evaluation is NOT a final step after building the agent; it is a first-class design constraint that determines what the agent is allowed to claim.

> **"The proof is worth more than the system."**

The project must be evaluated as multiple measurable components, rather than relying on one headline metric:
- **A. Intent classification**
- **B. Escalation / auto-handle decision**
- **C. Response quality**
- **D. LLM-judge reliability**

The final report will separate component-level results and honestly discuss limitations.

---

# 30. Intent Classification Metrics

Intent evaluation tests the frozen 8-label Spotify taxonomy on the isolated human-annotated golden set. 

Required intent metrics:
- **Accuracy**
- **Macro F1** (Crucial because customer support intents have uneven prevalence; a majority class shouldn't mask poor performance on rare classes like ARTIST_SUPPORT)
- **Per-intent precision**
- **Per-intent recall**
- **Confusion matrix**

The golden set must remain strictly isolated from model-development and retrieval data to avoid leakage.

---

# 31. Response Evaluation

Use an LLM judge to evaluate generated responses.

Possible criteria:

## Relevance

Does the response address the customer's actual issue?

## Groundedness

Is the response supported by historical evidence?

## Correctness

Does it avoid unsupported claims?

## Brand consistency

Does it resemble how the brand historically responds?

## Helpfulness

Would the response actually help the customer?

A simple 1–5 score can work.

---

# 32. Validate the LLM Judge

The assignment explicitly asks for:

> evidence of how well your judge agrees with a human

Therefore:

```text
30–50 sample responses
        ↓
Human evaluation
        ↓
LLM judge evaluation
        ↓
Compare scores
```

Measure agreement/correlation using an appropriate method for your scoring setup.

Do not simply say:

> “GPT-4o judged the responses.”

Show that the judge itself is reasonably trustworthy.

---

# 33. Evaluate Escalation Separately

Measure whether the agent correctly decides:

```text
AUTO-HANDLE
vs
ESCALATE
```

Useful metrics:

```text
Escalation precision
Escalation recall
False auto-handle rate
False escalation rate
```

Pay particular attention to:

> **False auto-handle rate**

Automatically handling a case that should have gone to a human may be much worse than unnecessarily escalating a case.

This is a strong product-oriented evaluation angle.

---

# 34. Baselines

The point of baselines is not sophistication. The point is to establish whether the complex AI approach actually improves over simple alternatives.

**Required Baselines:**

- **BASELINE 1 — TRIVIAL**: A majority-class intent classifier.
- **BASELINE 2 — SIMPLE**: A TF-IDF + Logistic Regression intent classifier.

Compare the final intent classifier against both. Keep retrieval baselines equally simple.

**What NOT to Build:**
Do not over-engineer. Do not add fine-tuning, FAISS (unless proven necessary by scale), rerankers, multi-agent orchestration, complex vector databases, separate sentiment models, or unnecessary model stacks. Demonstrate engineering judgment, not maximum infrastructure.

---

# 35. Failure Analysis

Do not invent your failure modes before evaluation.

Run the system and inspect actual failures.

Possible examples:

```text
1. Ambiguous refund vs payment intents
2. Long conversations lose important context
3. No sufficiently similar historical case
4. Angry customers cause unnecessary escalation
5. Agent invents resolution details
```

For each failure mode document:

```text
Failure
   ↓
Real example
   ↓
Why it happened
   ↓
Hypothesis
   ↓
Potential fix
```

This is exactly the type of reasoning Hiver wants.

---

# 36. “What Is Misleading About My Headline Number?”

This section is mandatory and should be taken seriously.

Suppose:

```text
Intent accuracy = 94%
```

That sounds great.

But maybe:

```text
70% of the data = delivery issues
```

So the model could be excellent at delivery and bad at everything else.

Or:

```text
94% intent accuracy
but
12% false auto-handle rate
```

The latter could be much more concerning.

Your report should explicitly say:

> **“Our headline metric overstates real-world performance because…”**

This shows that you understand evaluation rather than just chasing a high number.

---

# 37. Decision Log

Create:

```text
DECISIONS.md
```

Document 10–15 non-obvious decisions.

Examples:

```text
1. Selected Brand X because it had sufficient resolved conversations.

2. Limited the taxonomy to 7 intents to reduce overlap.

3. Used LLM-assisted annotation to scale the initial labelling.

4. Human-verified the final golden set.

5. Stratified the evaluation set across intent, conversation length and tone.

6. Kept the golden set isolated from the RAG corpus.

7. Used Chroma instead of a hosted vector database to keep reproduction simple.

8. Used deterministic rules for initial escalation logic.

9. Used an LLM judge only after validating its agreement with humans.

10. Used resolved historical conversations as retrieval evidence.

11. Used Python for objective stratification features instead of asking an LLM to infer them.

12. Chose a small intent taxonomy instead of attempting to reproduce every possible customer issue.

13. Used an evidence sufficiency check before response generation.

14. Focused evaluation on false auto-handles rather than only overall response quality.

15. Evaluated actual failure cases and iterated based on observed errors.
```

---

# 38. Suggested Repository Structure

```text
hiver-support-agent/
│
├── data/
│   ├── raw/
│   ├── processed/
│   ├── knowledge_base/
│   └── golden/
│
├── src/
│   ├── ingestion/
│   ├── cleaning/
│   ├── conversation_builder/
│   ├── annotation/
│   ├── retrieval/
│   ├── classification/
│   ├── agent/
│   ├── escalation/
│   └── evaluation/
│
├── prompts/
│   ├── intent_classifier.txt
│   ├── information_extraction.txt
│   ├── response_generator.txt
│   └── judge.txt
│
├── tests/
│
├── notebooks/
│
├── DECISIONS.md
├── README.md
├── REPORT.md
└── requirements.txt
```

Keep the project modular without making it huge.

---

# 39. Recommended Golden Dataset Workflow

## Phase 1 — Explore

```text
Pick brand
↓
Explore conversations
↓
Reconstruct threads
↓
Clean obvious garbage
↓
Identify common intents
```

## Phase 2 — Annotation

```text
Write intent definitions
↓
Create annotation prompt
↓
AI-label a large working sample
↓
Manually inspect ~100
↓
Fix taxonomy/prompt
↓
Repeat
```

## Phase 3 — Golden Set

```text
Define stratification dimensions
↓
Generate candidate evaluation pool
↓
Select ~250 diverse examples
↓
Manually verify every candidate
↓
Finalize ~200 golden examples
```

## Phase 4 — Agent

```text
Historical data
↓
Knowledge base
↓
Intent
↓
Information extraction
↓
Tone
↓
Retrieval
↓
Evidence check
↓
Escalation / response
```

## Phase 5 — Evaluation

```text
Golden set
↓
Baseline 1
↓
Baseline 2
↓
Your system
↓
Failure analysis
↓
Improve
↓
Re-evaluate
```

---

# 40. The North Star: Project Philosophy & Principles

This project is guided by four principles that tie everything together, connecting the advice we received from external experts to the actual implementation:

1. **Structure predictable/objective data with deterministic code.** (From the First Person / Structured-Data Principle: e.g., chronological `created_at` sorting, thread reconstruction, clear isolation boundaries).
2. **Use LLMs where interpretation/semantic judgment is actually required.** (e.g., assessing conversational context, generating grounded responses).
3. **Use AI to accelerate annotation, but keep humans in the evaluation loop.** (From the Second Person / Annotation Principle: AI makes the first pass, humans own the final evaluation labels based on a clear, frozen 8-label taxonomy).
4. **Make the agent's decisions measurable and prove where it works and fails.**

Connected directly to the Hiver assignment, the agent must:
- Classify the customer's primary support action
- Determine whether the case can be handled safely
- Retrieve evidence from historical support interactions
- Ground the reply
- Escalate when evidence/confidence is insufficient
- Prove performance with a human-verified golden set and simple baselines

> **Code what can be deterministic. Use LLMs where interpretation is needed. Keep humans in the evaluation loop. Make the agent's decisions measurable.**

**The Final Story:**
The project is NOT primarily: *"I built a cool RAG chatbot."*

The project IS:
*"I took noisy real-world customer-support conversations, reconstructed useful cases, derived a compact taxonomy from the data, created clear annotation rules, used AI-assisted annotation responsibly, built a leakage-controlled golden evaluation set, built a grounded Hiver-style support pipeline, compared it against simple baselines, validated the evaluator against humans, and analyzed where the system can and cannot be trusted."*

*(End of Strategy Document)*
