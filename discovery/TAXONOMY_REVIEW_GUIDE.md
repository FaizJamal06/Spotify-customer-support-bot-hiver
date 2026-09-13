# Intent Annotation Manual — Spotify Customer Support

**Status**: Frozen annotation guide for golden-set preparation.
**Taxonomy version**: 8-label frozen taxonomy (Decision Log #5).
**Last updated from**: 300-example discovery review (`HUMAN_REVIEW_labeled.md`), with 4 edge cases resolved.

### Revision Notes
This revision restores and clarifies operational rules for:
- Used-to-work / removed capabilities vs technical malfunctions
- Recommendation and personalization complaints vs metadata errors
- Technical errors inside account/billing/signup workflows
- Artist metadata and profile management edge cases
- Short continuation messages using preceding context
- Decision-tree numbering not being semantic priority

---

## Core Principle

> **Classify the customer's PRIMARY SUPPORT NEED, not the topic, keyword, object, or noun mentioned in the message.**

The question to ask yourself is:

> **"What support action would most directly resolve what the customer is asking?"**

Common traps to avoid:
- Talking about a **playlist** does not automatically mean CONTENT_CATALOG.
- Mentioning **Premium** does not automatically mean SUBSCRIPTION_BILLING.
- Mentioning an **artist** does not automatically mean ARTIST_SUPPORT.
- Mentioning a **feature** does not automatically mean APP_TECH_ISSUE.
- Mentioning an **account** does not automatically mean ACCOUNT_ACCESS.

Always trace the complaint or request to the underlying support action, not the surface-level keywords.

---

## Decision Tree (Support-Action Based)

Use this as a guide, not a mechanical checklist. Specific boundary rules and primary-support-action reasoning always override keyword matching.

```
1. Is this PURELY closure, irrelevant chatter, or genuinely uninterpretable?
   → UNKNOWN_OTHER
   (But see Edge Case 4: if the customer is still making an actionable
    request, use the substantive intent instead.)

2. Is the primary problem account access, login, password, hacked account,
   or identity?
   → ACCOUNT_ACCESS
   (But see Edge Case 1: if account compromise is mentioned but the
    customer's primary requested action is stopping/disputing a charge,
    use SUBSCRIPTION_BILLING.)

3. Is the primary problem a charge, refund, subscription status, or paid
   entitlement?
   → SUBSCRIPTION_BILLING

4. Is the customer acting as/for an artist with a creator-side issue?
   → ARTIST_SUPPORT

5. Is the content itself missing, unavailable, removed, or has incorrect
   metadata?
   → CONTENT_CATALOG

6. Is an existing product capability malfunctioning (crash, freeze, error,
   broken behavior)?
   → APP_TECH_ISSUE
   (But see Edge Case 2: "fix your app" defaults here unless the customer
    explicitly requests a design/behavior change.)

7. Is the customer requesting a product/feature/policy change?
   → FEATURE_FEEDBACK

8. Is the customer asking a how-to, eligibility, or general information
   question?
   → GENERAL_HOW_TO_INFO

9. If none of the above fit reliably:
   → UNKNOWN_OTHER
```

**Important**: Use the category that best matches the customer's primary support action. The numbering/order of the sections is for reference only and is not a priority ranking.

**Note on non-English messages** (Edge Case 3): The decision tree applies equally to messages in any language. Translate first, then classify.

---

## 1. ACCOUNT_ACCESS

**Definition**: The customer's primary problem is authentication, login, password/account recovery, hacked or compromised account, account identity, or inability to access or manage their account.

**Use this when...**
- The customer cannot log in or access their account
- The customer's account was hacked, compromised, or has unauthorized activity
- The customer needs to recover their password or account credentials
- The customer cannot link/unlink a Facebook or social account
- The customer's account identity or settings are inaccessible

**Do NOT use this when...**
- The word "account" appears but the actual problem is a charge or subscription → SUBSCRIPTION_BILLING
- The customer is asking a how-to question about a normal feature → GENERAL_HOW_TO_INFO
- The customer mentions "account" but the real issue is managing an artist profile → ARTIST_SUPPORT
- The customer's actual question is informational (how something works, what's set up, etc.) and an access symptom is mentioned only as background context, not as the thing being asked to be fixed → GENERAL_HOW_TO_INFO (post-golden clarification)

**Primary support action test**: Would the agent primarily need to help restore access, reset credentials, or investigate unauthorized activity?

**Positive examples**:
- *"I can't log in to my account"* → ACCOUNT_ACCESS
- *"My account was hacked, someone added playlists I didn't create"* → ACCOUNT_ACCESS (Ex 11)
- *"I deleted my Facebook and now I can't log in"* → ACCOUNT_ACCESS (Ex 46)
- *"I can't figure out the email I used to create my account"* → ACCOUNT_ACCESS (Ex 203)
- *"Having trouble adding my wife to Family — we get an error saying no Spotify account connected to our Facebook"* → ACCOUNT_ACCESS (Ex 60)
- *"My Spotify account reverted back to an old version. Lost all playlists."* → ACCOUNT_ACCESS (Ex 257)

**Near-miss / negative examples**:
- *"I paid for Premium but I'm still on Free"* → SUBSCRIPTION_BILLING (the problem is the paid entitlement, not access)
- *"Why have you taken unauthorised money from my account?"* → SUBSCRIPTION_BILLING (the primary issue is the charge) (Ex 7)
- *"How do I link Spotify to Google Assistant?"* → GENERAL_HOW_TO_INFO (Ex 250)
- *"How do I change my password?"* → ACCOUNT_ACCESS (password recovery IS an access issue)
- *"Someone hacked my account and now I'm being charged for Family — stop the charge"* → SUBSCRIPTION_BILLING (the primary requested action is stopping the unwanted charge; see Edge Case 1)
- *"Need to cancel my account. Problem is no idea what email was used. Tried them all. How can I cancel."* → ACCOUNT_ACCESS (the obstacle is an identity-verification problem Spotify itself must resolve before anything else can happen; post-golden clarification)
- *"I need to cancel a prime account but I can't login at all because my Facebook associated with it is gone."* → SUBSCRIPTION_BILLING (the obstacle is outside Spotify's control and there is nothing for Spotify to verify or restore; the stated request — cancellation — is the next support action; post-golden clarification)
- *"How can I know which address is set up in my account? I signed up for a family plan but some members can't sign in."* → GENERAL_HOW_TO_INFO (the stated question is informational; the access symptom is background, not the ask; post-golden clarification)

**Boundary rule vs SUBSCRIPTION_BILLING**: If the customer mentions both access/compromise AND billing problems, classify based on the customer's **primary requested action**, not the root cause:
- If the customer's main request is to regain access, reset credentials, or investigate unauthorized activity → ACCOUNT_ACCESS
- If the customer's main request is to stop, dispute, or reverse an unauthorized charge or subscription change → SUBSCRIPTION_BILLING
- Security/hacking does NOT automatically override billing. "Hacked" can be the root cause while the primary support need is billing.
- **Cancellation/billing actions blocked by an access problem** (post-golden clarification): When the customer's stated action is a billing action (cancel, downgrade, refund) and an access problem is named only as the obstacle preventing it, distinguish the *kind* of obstacle:
  - If resolving the obstacle requires Spotify to perform an identity/access-verification step (e.g., the customer doesn't know which email/account is theirs) → that verification step is itself the next support action → ACCOUNT_ACCESS.
  - If the obstacle is outside Spotify's control (e.g., a deleted third-party linked account) and there is nothing for Spotify to verify or restore → the next support action is the customer's stated request → SUBSCRIPTION_BILLING.

---

## 2. SUBSCRIPTION_BILLING

**Definition**: The customer's primary problem is a payment, charge, refund, billing error, subscription status, paid entitlement, or Premium access not working after purchase.

**Use this when...**
- The customer was charged incorrectly or unexpectedly
- The customer paid for Premium but is still getting the Free experience
- The customer wants a refund
- The customer's subscription status is wrong (e.g., downgraded to Free, upgraded without consent)
- The customer is disputing a specific price, discount, or entitlement
- The customer is being double-charged

**Do NOT use this when...**
- The customer is asking general questions about plans, pricing, or eligibility → GENERAL_HOW_TO_INFO
- The customer is requesting Spotify change its pricing policy → FEATURE_FEEDBACK
- The customer mentions "Premium" but the actual problem is a login issue → ACCOUNT_ACCESS
- The customer mentions "$" or "paying" but is really complaining about a broken feature → APP_TECH_ISSUE

**Primary support action test**: Would the agent primarily need to investigate a charge, adjust a subscription, process a refund, or verify a paid entitlement?

**Positive examples**:
- *"I paid for Premium but I'm still on Free"* → SUBSCRIPTION_BILLING (Ex 3)
- *"Why have you taken unauthorised money from my account?"* → SUBSCRIPTION_BILLING (Ex 7)
- *"I'm being charged $10 instead of the student price of $5"* → SUBSCRIPTION_BILLING (Ex 220)
- *"I appear to have been paying twice a month"* → SUBSCRIPTION_BILLING (Ex 127)
- *"My account was upgraded to Family without my consent"* → SUBSCRIPTION_BILLING (Ex 14)
- *"Tried to get premium on a promotion that didn't work but am being charged monthly"* → SUBSCRIPTION_BILLING (Ex 104)

**Near-miss / negative examples**:
- *"Can I get the student discount?"* → GENERAL_HOW_TO_INFO (no disputed charge) (Ex 264)
- *"Give loyal customers the same deals as new ones"* → FEATURE_FEEDBACK (requesting policy change) (Ex 158)
- *"I don't pay £10 for nothing"* → APP_TECH_ISSUE (context shows app malfunction, money is secondary frustration) (Ex 61)
- *"I can't log in and I'm still being charged"* → evaluate primary need; if locked out, ACCOUNT_ACCESS

**Boundary rule vs GENERAL_HOW_TO_INFO**: If there is a specific disputed charge, wrong amount, missing entitlement, or refund request → SUBSCRIPTION_BILLING. If the customer is asking how something works, what it costs, or whether they're eligible → GENERAL_HOW_TO_INFO.

---

## 3. APP_TECH_ISSUE

**Definition**: An existing product capability is malfunctioning. The customer expects something to work and it is broken: crashes, freezes, playback failures, Bluetooth issues, syncing problems, downloads disappearing, error messages, performance degradation.

**Use this when...**
- The app crashes, freezes, or shows error messages
- Playback fails, stutters, or stops unexpectedly
- Downloaded songs disappear or desync
- Bluetooth/Connect/casting stops working
- A feature that should work is broken (sharing, search, queue, etc.)
- The web player or desktop app fails to load or respond

**Do NOT use this when...**
- The customer wants Spotify to ADD, CHANGE, or RESTORE a feature → FEATURE_FEEDBACK
- Content is missing from the catalog (not a malfunction) → CONTENT_CATALOG
- The customer is asking how to use a feature → GENERAL_HOW_TO_INFO
- The customer mentions a "broken" feature but is actually requesting a design change → FEATURE_FEEDBACK

**Primary support action test**: Would the agent primarily need to troubleshoot, debug, or escalate a technical malfunction?

**Positive examples**:
- *"Spotify keeps crashing on my Android"* → APP_TECH_ISSUE (Ex 126)
- *"My downloaded songs keep disappearing"* → APP_TECH_ISSUE (Ex 136)
- *"Can't play in Chrome, getting errors"* → APP_TECH_ISSUE (Ex 73)
- *"The pause/play glitch — every time I pause, it gets stuck when I hit play"* → APP_TECH_ISSUE (Ex 194)
- *"Sharing function from iOS to Android on WhatsApp not working"* → APP_TECH_ISSUE (Ex 20)
- *"Not on my phone, just my computer! Rebooting does nothing"* → APP_TECH_ISSUE (Ex 8)

**Near-miss / negative examples**:
- *"You've ruined everything removing preview"* → FEATURE_FEEDBACK (removed feature, not malfunction) (Ex 18)
- *"Song download limits? C'mon. Get with the times."* → FEATURE_FEEDBACK (wants the limit changed) (Ex 21)
- *"When will you optimize for iPhone X?"* → FEATURE_FEEDBACK (requesting new capability) (Ex 209)
- *"Why isn't this album available?"* → CONTENT_CATALOG (content issue, not malfunction)

**Boundary rule vs FEATURE_FEEDBACK (Removed/Changed vs Malfunction)**: Ask yourself: *"Is the capability absent/changed by design, or is it present but malfunctioning?"*
- Consistently absent, deliberately removed, restored-from-past-state request, or clearly changed by product design → FEATURE_FEEDBACK (e.g., *"Did you remove one-song-repeat?"*, *"What happened to preview?"*, *"Bring back preview"*).
- Intermittent, inconsistent, error-like, crashing, freezing, or otherwise malfunctioning behavior → APP_TECH_ISSUE (e.g., *"The repeat button is there but doesn't work half the time"*, *"Repeat keeps failing randomly"*).
- **Update timing alone is not evidence of a deliberate change** (post-golden clarification): a new problem that started right after an app update is, by itself, still presumptively a malfunction/regression → APP_TECH_ISSUE, not evidence of an intentional design change. Apply FEATURE_FEEDBACK only when the customer explicitly objects to the new behavior as a choice (e.g., asks for it to be reverted or made optional) — not merely because the timing coincides with an update. (e.g., *"This didn't happen before I updated my phone yesterday. Is there any way around this?"* → APP_TECH_ISSUE, not FEATURE_FEEDBACK, since there is no explicit objection to a design choice.)
Do NOT classify a request as APP_TECH_ISSUE merely because the requested change concerns an existing feature.

**Boundary rule vs ACCOUNT_ACCESS / SUBSCRIPTION_BILLING (Technical flow errors)**: The object or context of a workflow does not automatically determine the label; classify what the customer actually needs help accomplishing.
- If the customer cannot complete a payment/subscription/entitlement task because of a billing/subscription problem → SUBSCRIPTION_BILLING (e.g., *"I'm trying to subscribe but the payment is being declined"*, *"I can't change my billing details because the billing page throws an error"*).
- If the customer cannot access/control/recover their account → ACCOUNT_ACCESS (e.g., *"I can't log in to my account"*).
- If a technical malfunction prevents an otherwise ordinary product action and there is no primary billing/account issue → APP_TECH_ISSUE (e.g., *"I'm trying to download a song and the app crashes"*, *"The signup page crashes every time I try to continue"*).

---

## 4. CONTENT_CATALOG

**Definition**: The content itself is missing, unavailable, removed, or incorrectly represented. This concerns the catalog of music/podcasts available on Spotify, not the product's technical functionality.

**Use this when...**
- A specific song, album, or podcast is missing from Spotify
- Content was previously available and has been removed
- Content metadata is wrong (wrong lyrics, wrong tracklist, wrong artwork, wrong album cover)
- The customer is asking why specific content is unavailable in their region
- The customer wants specific content added to Spotify's catalog
- The customer wants a specific song/album that already exists on Spotify placed onto a specific existing playlist (e.g., a curated/editorial playlist) (post-golden clarification)

**Do NOT use this when...**
- The customer wants Spotify to change a product behavior involving content → FEATURE_FEEDBACK
- Content exists but fails to play due to a technical error → APP_TECH_ISSUE
- The customer is acting as an artist with a creator-side issue → ARTIST_SUPPORT
- The customer is asking how to find or use content → GENERAL_HOW_TO_INFO

**Primary support action test**: Would the agent primarily need to investigate catalog availability, report a licensing issue, or correct content metadata?

**Positive examples**:
- *"Why isn't this album available in the UK?"* → CONTENT_CATALOG (Ex 50)
- *"I was wondering why 'Wherever I Go' by Hannah Montana isn't on Spotify"* → CONTENT_CATALOG (Ex 28)
- *"Why is the Charlotte Gainsbourg album cover just a white square?"* → CONTENT_CATALOG (Ex 216)
- *"The Heart Of Tha Streetz tracklist is off"* → CONTENT_CATALOG (Ex 143)
- *"When's lemonade going on Spotify?"* → CONTENT_CATALOG (Ex 110)
- *"Why isn't #flicker on Spotify?"* → CONTENT_CATALOG (Ex 232)

**Near-miss / negative examples**:
- *"Give users an option to exclude re-releases from Release Radar"* → FEATURE_FEEDBACK (product behavior change)
- *"Let me block artists from playlists"* → FEATURE_FEEDBACK (new capability request)
- *"You should have a playlist called Shitstorm Shuffle"* → FEATURE_FEEDBACK (Ex 186)
- *"Song exists but won't play, just skips"* → APP_TECH_ISSUE (technical failure)

**Boundary rule vs FEATURE_FEEDBACK**: Ask: *"Is the content itself wrong/missing, or is the customer asking Spotify to change how the product handles content?"* If a song is missing → CONTENT_CATALOG. If the customer wants a new way to browse, sort, filter, or manage content → FEATURE_FEEDBACK. If the customer wants an already-available song placed onto a specific existing playlist (e.g., a curated/editorial playlist) → CONTENT_CATALOG, a placement request about that content — distinct from a request for a new general capability (e.g., "let me exclude songs by language" or "let me sort playlists alphabetically"), which remains FEATURE_FEEDBACK. (post-golden clarification; e.g. *"I think 'Lemon' would be perfect on the 'Today's Top Hits' Playlist... can you add it"* → CONTENT_CATALOG.)

**Boundary rule vs APP_TECH_ISSUE**: Ask: *"Is the CONTENT wrong/unavailable, or is SPOTIFY malfunctioning while handling the content?"* Song not available anywhere → CONTENT_CATALOG. Song exists but won't play, errors when streaming → APP_TECH_ISSUE.

---

## 5. FEATURE_FEEDBACK

**Definition**: The customer wants Spotify to add, remove, restore, redesign, or change product functionality, behavior, or policy.

**Use this when...**
- The customer requests a new feature (*"please add an alarm clock"*)
- The customer requests a new option/setting/control (*"give us an option to..."*)
- The customer wants a removed feature restored (*"bring back preview"*)
- The customer wants existing behavior changed (*"stop putting random bands in my recently listened"*)
- The customer wants a product redesign (*"your Roku app has no functionality"*)
- The customer wants a policy change (*"give loyal customers the same deals as new ones"*)
- The customer criticizes a deliberate design decision, not a bug
- Complaints about recommendation quality, personalization, algorithmic recommendations, relevance, repeated recommendations, or unwanted recommended content (challenging product behavior or asking Spotify to change it)

**Signal phrases**:
- "please add...", "you should let users...", "give us an option to..."
- "bring back...", "why can't Spotify allow...", "it would be better if..."
- "Spotify should...", "Spotify needs to...", "when will you add..."

**Do NOT use this when...**
- An existing feature is broken/crashing → APP_TECH_ISSUE
- Content is missing from the catalog → CONTENT_CATALOG
- The customer is asking how to use an existing feature → GENERAL_HOW_TO_INFO

**Primary support action test**: Would the agent primarily need to log feedback, acknowledge a feature request, or forward the suggestion to a product team?

**Positive examples**:
- *"Bring back the hold-to-preview feature"* → FEATURE_FEEDBACK (Ex 207)
- *"Please add an alarm clock to the app"* → FEATURE_FEEDBACK (Ex 224)
- *"Can I blacklist certain bands from shuffle and radios?"* → FEATURE_FEEDBACK (Ex 38)
- *"When are you going to get music videos?"* → FEATURE_FEEDBACK (Ex 77)
- *"Stop putting random bands in my recently listened to"* → FEATURE_FEEDBACK (Ex 187)
- *"Your Roku app is terrible, no functionality"* → FEATURE_FEEDBACK (design criticism, not a bug) (Ex 26)
- *"This new update is confusing as fuck"* → FEATURE_FEEDBACK (criticizing design, not reporting a crash) (Ex 195)
- *"Would love language switching in the mobile app"* → FEATURE_FEEDBACK (Ex 228)
- *"Is there a way to put playlists in alphabetical order?"* → FEATURE_FEEDBACK (Ex 293)
- *"Remove my music limits! It's dumb."* → FEATURE_FEEDBACK (wants limits changed) (Ex 47)

**Near-miss / negative examples**:
- *"The app keeps crashing"* → APP_TECH_ISSUE (malfunction, not a design request)
- *"Downloaded songs disappeared"* → APP_TECH_ISSUE (not a design choice)
- *"Why isn't this album available?"* → CONTENT_CATALOG (missing content, not a feature request)
- *"How do I create a playlist?"* → GENERAL_HOW_TO_INFO

**Boundary rule vs APP_TECH_ISSUE**: This was the single largest source of mismatch in the 300-example review (16 cases). See the "Removed/Changed vs Malfunction" rule in the APP_TECH_ISSUE section.

**Boundary rule vs CONTENT_CATALOG / ARTIST_SUPPORT (Recommendations vs Metadata)**: Complaints about algorithmic recommendations or personalization behavior are FEATURE_FEEDBACK (e.g., *"Stop putting random bands in my recently listened to"*, *"Why does Spotify keep recommending the same artists?"*, *"Let me control what appears in Release Radar"*). Factual metadata/content errors remain CONTENT_CATALOG (e.g., *"The album cover is wrong"*) or ARTIST_SUPPORT (e.g., *"My artist bio is incorrect"*).

---

## 6. ARTIST_SUPPORT

**Definition**: Creator/artist-side issues concerning artist profiles/page management, ownership, attribution, incorrect tracks on artist pages, distributor/release workflows, artist-side metadata, artist bios, band-name collisions, or creator-side support.

**Use this when...**
- The customer is acting as or on behalf of an artist/creator
- The issue is about artist profile ownership or attribution
- Wrong songs appear on the customer's artist page
- The issue involves distributor or release workflows
- The customer is managing artist-side metadata or correcting artist bios/band-name collisions

**Do NOT use this when...**
- An artist is merely mentioned but the issue is listener-facing → use the appropriate listener category
- The customer wants a song/album added to the catalog from a listener perspective → CONTENT_CATALOG
- The customer mentions an artist name while reporting a playback bug → APP_TECH_ISSUE

**Primary support action test**: Would the agent primarily need to route the issue to the Artist Services team or help with a creator-side workflow?

**Positive examples**:
- *"Songs that aren't mine keep getting posted to my artist page"* → ARTIST_SUPPORT (Ex 43)
- *"I've been managing a wrong artist profile. How do I remove it from my account?"* → ARTIST_SUPPORT (Ex 298)
- *"Can you fix the problem I mentioned by email? This blocks the release of one of my artists."* → ARTIST_SUPPORT (Ex 10)
- *"I've seen errors in bios. Do you do anything for band name collisions?"* → ARTIST_SUPPORT (Ex 281)

**Near-miss / negative examples**:
- *"Why isn't this artist's song available?"* → CONTENT_CATALOG (listener perspective)
- *"Mentioning @artist in a complaint about playback"* → APP_TECH_ISSUE
- *"My music stops playing when I go on Twitter"* → APP_TECH_ISSUE (Ex 273, despite provisional label ARTIST_SUPPORT)

**Boundary rule vs CONTENT_CATALOG**: An artist being mentioned is NOT enough. The support action must concern the artist's creator-side presence or workflow. If the issue is about catalog availability from a listener's perspective → CONTENT_CATALOG. Do NOT remove ARTIST_SUPPORT merely because it is rare — the discovery sample contains distinct creator-side workflows that justify the category.

---

## 7. GENERAL_HOW_TO_INFO

**Definition**: The customer is asking how to use Spotify, where to find something, how a normal capability/process works, or asking general eligibility/availability information that does not involve a billing error.

**Use this when...**
- *"How do I...?"*
- *"Where do I find...?"*
- *"Can I...?"*
- *"Is it possible to...?"*
- *"What does X mean?"*
- *"Am I eligible for...?"*
- General plan/pricing information with no disputed charge
- How to enroll in or use a promotion/discount

**Do NOT use this when...**
- The customer has a specific billing problem → SUBSCRIPTION_BILLING
- The customer is trying to do something and it's broken → APP_TECH_ISSUE
- The customer wants a feature that doesn't exist → FEATURE_FEEDBACK

**Primary support action test**: Would the agent primarily need to explain, instruct, or point the customer to documentation?

**Positive examples**:
- *"How do I set parental controls?"* → GENERAL_HOW_TO_INFO (Ex 44)
- *"How do I link Spotify to Google Assistant?"* → GENERAL_HOW_TO_INFO (Ex 250)
- *"Can I transfer premium to another account?"* → GENERAL_HOW_TO_INFO (Ex 137)
- *"What does it mean to download on Spotify? Can we download for free?"* → GENERAL_HOW_TO_INFO (Ex 160)
- *"Do I have to buy Premium to hear these songs?"* → GENERAL_HOW_TO_INFO (Ex 36)
- *"What if I'm a student and already have premium?"* → GENERAL_HOW_TO_INFO (Ex 264)
- *"How do I disable Spotify Connect?"* → GENERAL_HOW_TO_INFO (Ex 231)

**Near-miss / negative examples**:
- *"I can't log in"* → ACCOUNT_ACCESS (not a how-to question)
- *"I was charged full price for student Premium"* → SUBSCRIPTION_BILLING (disputed charge)
- *"The download button doesn't work"* → APP_TECH_ISSUE (malfunction)
- *"Downloaded songs disappear"* → APP_TECH_ISSUE (malfunction)

**Boundary rule vs APP_TECH_ISSUE**: *"How do I download?"* → GENERAL_HOW_TO_INFO. *"I'm trying to download and it doesn't work"* → APP_TECH_ISSUE. The line is: asking how vs. trying and failing.

**Boundary rule vs SUBSCRIPTION_BILLING**: If there is no specific charge, refund, or entitlement dispute and the customer is simply asking about plans, pricing, or eligibility → GENERAL_HOW_TO_INFO. If there IS a specific financial problem → SUBSCRIPTION_BILLING.

---

## 8. UNKNOWN_OTHER

**Definition**: Messages that genuinely do not fit any taxonomy category, or whose intent cannot be determined reliably from the target message and all available preceding context.

**UNKNOWN is a last resort.** Do NOT use it just because:
- The message is short (short ≠ UNKNOWN)
- The message uses unusual language, slang, or emoji
- The message is emotional or angry
- The message is in a non-English language (see Edge Case 3: translate first, then classify)
- The English is messy or has typos
- The message mentions a past feature or expresses disappointment (see Edge Case 4: distinguish closure from actionable requests)

**Use this when...**
1. The message genuinely fits no taxonomy category, OR
2. The intent cannot be determined reliably even using all available preceding thread context

**Diagnostic flags** (overlapping — a message can have multiple):

| Flag | Use when... | Example |
|---|---|---|
| `ambiguous` | The message could mean multiple things and you cannot tell which | *"hello"* (Ex 56), *"How?"* with no useful context (Ex 164) |
| `conversational/closure` | The customer is **primarily** thanking, confirming, or closing a conversation and is **not** making an actionable new request | *"Thanks, it worked!"* (Ex 49), *"Ok, thankyou for the response :)"* (Ex 32), *"Aw man I used to love that feature 😔 thanks tho"* (Ex 226) |
| `irrelevant/off-topic` | The message has no support request and is unrelated chatter | *"October 26th, 60 degrees, partly cloudy; listen to Iron and Wine"* (Ex 5) |
| `context_dependent` | The intent depends entirely on unseen/unavailable context | *"Roughly 2000"* (Ex 275), *"I'll have a go tomorrow night"* (Ex 80) |

**Negative examples** (things that are NOT UNKNOWN):
- *"What the hells going on with my hulu account?"* — looks messy, but it's ACCOUNT_ACCESS (Ex 168)
- *"spotify please😩😤"* — emotional and short, but context showed it's UNKNOWN_OTHER (Ex 172)
- *"Not on my phone, just my computer! Rebooting does nothing"* — context-dependent but clearly APP_TECH_ISSUE from preceding thread (Ex 8)
- *"When's lemonade going on Spotify?"* — looks casual but it's CONTENT_CATALOG (Ex 110)
- *"You work with Alexa, right??"* — short and phrased as idle chat, but names a specific, concrete integration/compatibility topic → GENERAL_HOW_TO_INFO, not UNKNOWN_OTHER (post-golden clarification)

---

## Promotion/Discount Boundary (Frozen Rule)

Since PLAN_PROMOTION was removed as a top-level intent (Decision Log #5), promotion/discount cases follow a strict three-way boundary:

| Situation | Intent |
|---|---|
| Customer disputes a specific price, charge, discount, or entitlement | SUBSCRIPTION_BILLING |
| Customer wants Spotify to introduce/change a promotion/loyalty policy | FEATURE_FEEDBACK |
| Customer asks how to enroll, use, or understand an existing promotion | GENERAL_HOW_TO_INFO |

**Examples**:
- *"Tried to get premium on a promotion but am being charged monthly"* → SUBSCRIPTION_BILLING (Ex 104)
- *"Why don't loyal customers ever get discount offers?"* → FEATURE_FEEDBACK (Ex 277)
- *"Am I eligible for the student discount?"* → GENERAL_HOW_TO_INFO
- *"Trying to get student discount shouldn't be this tedious"* → GENERAL_HOW_TO_INFO (frustration with enrollment process, not a charge dispute) (Ex 82)

---

## Multi-Intent Rule

Assign exactly **ONE** primary top-level intent.

When a message contains multiple issues, assign the intent based on the issue that should drive the **next support action**. Do not assign multiple labels.

**Tie-breaker** (use ONLY when two issues are genuinely equally explicit):
1. Security / account-access issues
2. Billing / payment / subscription issues
3. Technical / product issues
4. Feature feedback or informational requests

**Important**: This priority order is a tie-breaker, NOT an automatic precedence rule.
- Do NOT make "money mentioned" automatically override everything.
- Do NOT make "hacked" automatically override everything (see Edge Case 1).
- If one issue is clearly the customer's main requested action, use that intent regardless of the general priority order.

**Examples**:
- *"I can't log in and I'm still being charged"* → evaluate primary need; if locked out → ACCOUNT_ACCESS
- *"Someone hacked my account and I'm being charged for Family — stop the charge"* → SUBSCRIPTION_BILLING (primary action is stopping the charge, even though hacking is the root cause)
- *"My app crashes AND you charged me twice"* → SUBSCRIPTION_BILLING (billing urgency tie-breaks tech)
- *"Bring back the old UI! Also downloads don't work."* → APP_TECH_ISSUE (broken download requires immediate troubleshooting)

---

## Geography

Geography is a **modifier**, not a top-level intent. If geography is just a condition attached to another issue, keep the underlying intent:

- *"Why isn't this album available in the UK?"* → CONTENT_CATALOG + region=UK
- *"Why doesn't Spotify exist in India?"* → GENERAL_HOW_TO_INFO + region=India
- *"Why isn't my Canadian card accepted?"* → SUBSCRIPTION_BILLING + region=Canada

Only attach a geography modifier when the country/region materially affects the interpretation. Do NOT add a geography flag merely because a country name appears.

---

## Target Message Context

Always classify the intent of the **TARGET customer message**.

You may use all available context occurring **before** the target message to interpret it, especially for messages like:
- *"How?"*
- *"Still doesn't work"*
- *"iPhone 7"*
- *"I'll try that"*
- *"What about this?"*
- *"same issue"*

**Operational Rule for Short Continuations**:
1. First inspect all preceding context available before the target.
2. If the preceding context gives enough information to identify the general support category, classify the target under that intent.
3. Mark `context_dependent` when appropriate.
4. Use UNKNOWN_OTHER only when the intent genuinely remains undetermined after reviewing all allowed preceding context.
*(Important: Short message ≠ UNKNOWN_OTHER. Context-dependent message ≠ UNKNOWN_OTHER by default. Do not use future messages to resolve ambiguity).*

**You must NOT use:**
- Later customer messages
- Later thread messages
- Spotify's response to the target
- Eventual resolution
- Gold/reference answers

**Critical**: Do not infer the intended issue from Spotify's eventual response. The annotator should not look at what SpotifyCares said next to decide the intent.

When context is needed, click **"View full thread"** in the pilot workbook to see all preceding messages.

---

## Resolved Edge Cases

The following four edge cases were identified during the guide revision and have been resolved with explicit operational rules.

### Edge Case 1 — Account Compromise + Billing

**Rule**: When a message involves both account compromise/hacking AND a billing/subscription complaint, classify based on the customer's **primary requested action**, not the root cause.

| Situation | Label |
|---|---|
| Primary request is to regain access, reset credentials, or investigate the breach | ACCOUNT_ACCESS |
| Primary request is to stop, dispute, or reverse an unwanted charge or subscription | SUBSCRIPTION_BILLING |

Do NOT automatically give ACCOUNT_ACCESS priority merely because "hacked" or "compromised" appears. Security is the root cause, but the customer's actual support need determines the label.

**Blocker vs demand** (post-golden clarification): When a message contains both a stated blocker preventing self-resolution (e.g., "no way to change my password") and a stated demand (e.g., a refund/compensation ask, however informally styled, such as a hashtag), the concrete blocker takes precedence — resolving it is the more direct next support action, regardless of whether the demand is phrased in prose or as an informal hashtag/caps.

**Examples**:
- *"Someone hacked my account and I cannot access it"* → ACCOUNT_ACCESS (primary need: restore access)
- *"someone's hacked my account and apparently there's no way for me to change my password! #crock #fixthis #givememumoneyback"* → ACCOUNT_ACCESS (the stated blocker — cannot change password — is the concrete next support action; the hashtag demand does not override it; post-golden clarification)
- *"My account was hacked, someone added playlists and is controlling music on my device"* → ACCOUNT_ACCESS (primary need: investigate breach, restore control) (Ex 11)
- *"I reported illegal activity on my account so you blocked me — give me access back"* → ACCOUNT_ACCESS (primary need: restore access despite the billing side-effect) (Ex 145)
- *"My account was fraudulently upgraded to Family and I'm being charged — stop the charge!"* → SUBSCRIPTION_BILLING (primary need: stop the unwanted subscription/charge) (Ex 14)
- *"Why have you taken unauthorised money from my account?"* → SUBSCRIPTION_BILLING (primary need: investigate and reverse the charge) (Ex 7)
- *"Had fraudulent activity on my account, was asked to prove I'm the real payer"* → ACCOUNT_ACCESS (primary need: verify identity and restore control) (Ex 286)

**Historical note**: Ex 14 (Gold: SUBSCRIPTION_BILLING) is consistent with this rule — the customer's explicit request was "I don't want to pay for a family account," making the billing dispute the primary support need.

---

### Edge Case 2 — Vague "Fix Your App" Messages

**Rule**: When a message uses vague language like "fix your app" without specifying whether the problem is a malfunction or a design complaint:

| Situation | Label |
|---|---|
| Message implies something is broken/malfunctioning, or there is no clear evidence of a design complaint | APP_TECH_ISSUE (default) |
| Message explicitly criticizes a design decision, update, or product change | FEATURE_FEEDBACK |
| Message is completely uninterpretable even after reviewing all preceding context | UNKNOWN_OTHER |

The default assumption for "fix your app" is APP_TECH_ISSUE because the word "fix" implies a malfunction, and the natural support action is troubleshooting. Only classify as FEATURE_FEEDBACK when there is explicit evidence that the customer is reacting to a deliberate design/product change.

**Examples**:
- *"fix your app please"* → APP_TECH_ISSUE (implies malfunction; default to troubleshooting) (Ex 279)
- *"Any insight to the updates coming? There's just so much wrong with the app right now"* → APP_TECH_ISSUE (implies current malfunction) (Ex 31)
- *"This new update is confusing as fuck"* → FEATURE_FEEDBACK (explicitly criticizes a design change, not a crash/error) (Ex 195)
- *"Your Roku app is terrible, no functionality. Do better."* → FEATURE_FEEDBACK (criticizes missing functionality as a design gap, not a bug) (Ex 26)
- *"Seriously sort your shit out" (with context about shuffle repeating same artists)* → UNKNOWN_OTHER (too vague even with context) (Ex 19)

**Key distinction**: "Fix" + broken behavior = APP_TECH_ISSUE. "Fix" + deliberate design choice = FEATURE_FEEDBACK. "Fix" + no interpretable context = UNKNOWN_OTHER.

---

### Edge Case 3 — Non-English Messages

**Rule**: Non-English messages are NOT automatically UNKNOWN_OTHER. Apply this procedure:

1. **Translate** the target message and relevant preceding context using any available translation tool.
2. Translation may only be used to understand what the customer is saying. Do NOT translate Spotify's response to the target or any post-target messages (this would leak resolution information).
3. After translation, **apply the same taxonomy rules** as for English messages.
4. If the message remains genuinely ambiguous or uninterpretable even after translation → UNKNOWN_OTHER + appropriate diagnostic flags.

**Examples**:
- Turkish: *"Premium alınmıyor"* ("Premium can't be purchased") → SUBSCRIPTION_BILLING (Ex 91)
- Indonesian: *"Sudah berlangganan premium tapi tidak bisa download"* ("Subscribed to premium but can't download") → APP_TECH_ISSUE (Ex 244)
- Swedish: *"Kan inte logga in på mitt konto, men pengar dras ändå"* ("Can't log in, but money is still being deducted") → ACCOUNT_ACCESS (primary need is access; Ex 205)
- Indonesian: *"Kapan spotify diskon untuk pelajar bayarnya ga pake kartu kredit?"* ("When will student discount not require credit card?") → GENERAL_HOW_TO_INFO (Ex 201)
- Filipino: *"Bawal bdo?"* ("Is BDO not allowed?") → UNKNOWN_OTHER (genuinely ambiguous even after translation; Ex 289)

---

### Edge Case 4 — Conversational Closure with Feedback Signal

**Rule**: Classify based on the customer's **function** at the point of the target message, not incidental keywords.

| Situation | Label |
|---|---|
| The message primarily closes or acknowledges the conversation, even if it mentions a past feature or expresses disappointment | UNKNOWN_OTHER + `conversational/closure` |
| The message is still making an actionable request or explicitly asking Spotify to change something | The applicable substantive intent (e.g., FEATURE_FEEDBACK) |

Mentioning a past feature or expressing disappointment does NOT by itself create FEATURE_FEEDBACK. The customer must be making a forward-looking, actionable request.

**Test**: Ask yourself: *"If I were the support agent, would I need to take any further action, or has the customer closed the conversation?"*

**Sarcasm** (post-golden clarification): Gratitude phrased with sarcasm or irony — e.g., thanking the company for a partial, minimal, or grudging remedy to an ongoing billing or service problem — is not genuine closure. Classify by the underlying substantive issue being sarcastically referenced (e.g., a billing/credit complaint), not as UNKNOWN_OTHER.

**Examples — UNKNOWN_OTHER (closure)**:
- *"Aw man I used to love that feature 😔 thanks tho"* → UNKNOWN_OTHER + conversational/closure (acknowledges the situation, does not request action) (Ex 226)
- *"Thanks, I already have. Just wondered if there's any progress, as it was requested more than 5 years ago!!"* → UNKNOWN_OTHER + conversational/closure (despite asking about progress, the primary function here is thanking the agent and closing the current interaction) (Ex 131)
- *"I know it reloads... it's been doing amazingly perfect for 1.5 years... I'd just like to give better feedback if possible"* → UNKNOWN_OTHER + conversational/closure (reflecting and praising past performance, not making an immediate actionable request for a product change) (Ex 249)

**Examples — FEATURE_FEEDBACK (actionable)**:
- *"Bring back the hold-to-preview feature please god"* → FEATURE_FEEDBACK (explicit forward-looking request) (Ex 207)
- *"Please add an alarm clock to the app"* → FEATURE_FEEDBACK (explicit request)

**Examples — sarcastic (not genuine closure)** (post-golden clarification):
- *"Would like to thank @SpotifyCares for being nice enough to credit the month we weren't able to use the service due to #HurricaneMaria."* → SUBSCRIPTION_BILLING (sarcastic gratitude referencing an under-remedied billing/service problem, not genuine closure)

---

## Lessons from the 300-Example Discovery Review

Analysis of 300 human-labeled discovery examples revealed the following recurring boundary patterns. These observations informed the rules above.

### Most frequent mismatch directions

| Heuristic → Human Label | Count | Pattern |
|---|---|---|
| APP_TECH_ISSUE → FEATURE_FEEDBACK | 16 | Heuristic confused design requests with bugs |
| UNKNOWN_OTHER → FEATURE_FEEDBACK | 11 | Informal feature requests looked like noise |
| ACCOUNT_ACCESS → SUBSCRIPTION_BILLING | 10 | "Account" keyword triggered wrong label |
| CONTENT_CATALOG → FEATURE_FEEDBACK | 8 | Product behavior changes about content |
| UNKNOWN_OTHER → GENERAL_HOW_TO_INFO | 7 | Short or casual how-to questions |
| UNKNOWN_OTHER → APP_TECH_ISSUE | 6 | Context-dependent tech issues |
| UNKNOWN_OTHER → CONTENT_CATALOG | 6 | Casual catalog questions |
| ACCOUNT_ACCESS → GENERAL_HOW_TO_INFO | 6 | How-to questions mentioning "account" |
| SUBSCRIPTION_BILLING → GENERAL_HOW_TO_INFO | 5 | Plan info questions vs billing disputes |
| SUBSCRIPTION_BILLING → APP_TECH_ISSUE | 5 | Tech issues while subscribing |
| SUBSCRIPTION_BILLING → FEATURE_FEEDBACK | 5 | Policy complaints framed as billing |

### Key recurring lessons

1. **FEATURE_FEEDBACK is systematically under-detected by keywords.** The heuristic classified many design requests and product complaints as APP_TECH_ISSUE, CONTENT_CATALOG, or UNKNOWN_OTHER. Feature feedback often looks like a complaint, not a formal request. Signal phrases ("please add", "bring back", "you should") are more reliable than topic nouns.

2. **"Account" does not mean ACCOUNT_ACCESS.** 10 examples labeled ACCOUNT_ACCESS by the heuristic were actually SUBSCRIPTION_BILLING when the human examined the actual complaint (wrong charges, missing entitlements). The word "account" appears in nearly every billing message but the support action is billing-related.

3. **Short or casual messages need context, not UNKNOWN.** Many messages labeled UNKNOWN_OTHER were actually classifiable using preceding thread context — they were tech issues, content questions, or how-to questions expressed informally.

4. **Content topic vs product behavior.** When a customer mentions a playlist, an album, or a content feature, the question is whether they want the CONTENT fixed (missing, wrong metadata) or the PRODUCT changed (new sorting, new filtering, new behavior).

5. **"Paying customer" frustration ≠ billing issue.** Several messages mention paying or Premium as emotional emphasis while actually reporting a technical problem or requesting a feature change. Trace the actual support need.

### Historical annotation inconsistencies

A small number of decisions in the 300-example review may be inconsistent with the tightened rules above. These are expected in any early-stage annotation pass and should not be treated as evidence that the taxonomy needs further changes. The rules above represent the intended standard going forward.

---

## Important Reminders

- **Golden-Set Integrity**: This guide is the rulebook for the FINAL GOLDEN SET. Annotators must assign the human gold label independently.
- Do NOT pre-fill or silently copy the provisional "Human Decision / Gold Label" column or use model predictions to decide gold labels. Provisional/historical labels are not authoritative. Examples in this guide are instructional evidence, not a license to copy labels mechanically.
- If you are genuinely uncertain after applying the rules and reviewing context, use UNKNOWN_OTHER with appropriate diagnostic flags. It is better to honestly flag uncertainty than to force an unreliable label.
- This guide applies to GOLDEN-SET annotation. The taxonomy is frozen at 8 labels.
