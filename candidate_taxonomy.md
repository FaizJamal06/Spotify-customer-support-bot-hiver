# Candidate Intent Taxonomy

> **SUPERSEDED — HISTORICAL DRAFT.** This document predates the taxonomy freeze.
> The taxonomy is now frozen at exactly these 8 labels (confirmed unchanged after
> a post-golden review — see `DECISION_LOG.md` #22). The authoritative rulebook is
> `discovery/TAXONOMY_REVIEW_GUIDE.md`; this file is kept only as a record of the
> early candidate design and the reasoning for dropping `PLAN_PROMOTION`.

*Status (historical, as originally written): CURRENT CANDIDATE TAXONOMY (not final/frozen). Subject to human review and approval.*

Based on the manual analysis of 300 sampled customer messages from the `DEVELOPMENT` pool, followed by human review and consolidation, the following 8-label candidate taxonomy is proposed.

---

## Candidate Intents & Definitions

| # | Candidate Intent | Definition | Typical Support Action |
|---|---|---|---|
| 1 | **ACCOUNT_ACCESS** | Primary problem is authentication, login, password/account recovery, hacked or compromised account, account identity, or inability to access/manage the account itself. | Direct to DM to securely verify email and check account backend. |
| 2 | **SUBSCRIPTION_BILLING** | Primary problem is payment, charges, refunds, billing errors, subscription status, paid entitlement, or Premium access after purchase. | Direct to DM to check payment history and adjust subscription state. |
| 3 | **APP_TECH_ISSUE** | An existing product capability is malfunctioning. Examples include crashes, freezes, playback failures, Bluetooth issues, syncing problems, broken sharing, or downloads disappearing unexpectedly. | Ask for device/OS/app version, suggest clean reinstall or cache clearing. |
| 4 | **CONTENT_CATALOG** | The content itself is missing, unavailable, removed, or incorrectly represented. Examples include missing songs/albums, unavailable tracks, incorrect lyrics, incorrect tracklists, album artwork, artist/catalog metadata. | Explain label licensing rules, ask for the URI of the affected track. |
| 5 | **FEATURE_FEEDBACK** | The customer wants Spotify to add, remove, restore, redesign, or change product functionality. Examples include requests to bring back preview, add an alarm clock, restore search, add artist blocking, add 2FA, etc. | Thank them for feedback, direct them to the Spotify Community Idea board. |
| 6 | **ARTIST_SUPPORT** | Creator/artist-side issues concerning artist profiles, ownership, incorrect tracks on artist pages, distributor/release workflows, artist metadata, or creator-side support. | Direct them to the specialized Spotify For Artists support team/portal. |
| 7 | **GENERAL_HOW_TO_INFO** | Questions asking how to use Spotify, where to find something, how a normal capability/process works, or general eligibility/availability information that does not involve a billing error. | Provide instructions or link to relevant help article. |
| 8 | **UNKNOWN_OTHER** | Messages that genuinely do not fit the taxonomy or cannot be assigned reliably. Uses overlapping internal diagnostic flags: `ambiguous`, `conversational/closure`, `irrelevant/off-topic`, `context_dependent`. | If vague: ask for details. If off-topic/thanks: friendly acknowledgment. |

---

## Historical Note

An earlier 9-label candidate taxonomy included `PLAN_PROMOTION` as a separate top-level intent. After human review of the 300-example discovery sample, this was removed because:
- Too few clearly distinct examples existed to justify a separate class.
- Plan-related messages split cleanly into two existing categories:
  - **GENERAL_HOW_TO_INFO** when the question is informational/eligibility/how-to.
  - **SUBSCRIPTION_BILLING** when the primary issue is payment, charge, refund, entitlement, or subscription state.

---

## Representative Real Examples

### 1. ACCOUNT_ACCESS
> **ID 1269745**: "@115888 #HackedAgain Someone that I don't know has added new music and controlling music playing on my device. Seriously second time hacked"

### 2. SUBSCRIPTION_BILLING
> **ID 2364839**: "@SpotifyCares Hi, I have subscribed to premium and my account was debited £9.99 on 4 Nov but in the app I can only use free."

### 3. APP_TECH_ISSUE
> **ID 2028406**: "@SpotifyCares Since the last iOS update, I can't stream to my car via Bluetooth (R-link). Reset, paired again, no joy. Works w/o bluetooth!"

### 4. CONTENT_CATALOG
> **ID 822275**: "Now that I'm down a Cash Money rabbit hole, someone tell @115888 their The Heart Of Tha Streetz tracklist is off."

### 5. FEATURE_FEEDBACK
> **ID 2448604**: "@115888 bring back the hold to preview feature please god"

### 6. ARTIST_SUPPORT
> **ID 303156**: "@SpotifyCares songs that aren't mine keep getting posted to my artist page every other week. Can you please review songs before you post them freely?"

### 7. GENERAL_HOW_TO_INFO
> Example: "How do I create a playlist?"
> Example: "Am I eligible for the student discount?"

### 8. UNKNOWN_OTHER
> **ID 1914386**: "@115888 October 26th, 60 degrees, partly cloudy; listen to Iron and Wine's Around The Well" *(irrelevant/off-topic)*
> **ID 1159704**: "@SpotifyCares Yep, seems to have fixed it. Ta!" *(conversational/closure)*

---

## Geography Rule

Geography is a **modifier**, not a top-level intent. If geography is a condition attached to another issue, keep the underlying intent:
- "Why isn't this album available in the UK?" -> CONTENT_CATALOG + region=UK
- "Why doesn't Spotify exist in India?" -> GENERAL_HOW_TO_INFO + region=India
- "My Canadian card isn't accepted" -> SUBSCRIPTION_BILLING + region=Canada
