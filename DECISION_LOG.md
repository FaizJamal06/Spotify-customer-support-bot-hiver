# Decision Log

1. **Brand Selection: SpotifyCares**
   - *Alternatives considered*: AppleSupport, AmazonHelp, Uber_Support, TMobileHelp.
   - *Why we chose it*: SpotifyCares has high response diversity (77.2% unique), moderate DM redirect rate (31.8%), and rich interaction depth compared to other brands (e.g., TMobileHelp had 82.9% DM redirects).
   - *Evidence*: `analyze_brands.py` run on a subset (results in past conversation logs).
   - *Tradeoff*: Spotify's dataset is somewhat smaller than AppleSupport, but higher quality for generation tasks.

2. **Thread-Level Splitting**
   - *Alternatives considered*: Tweet-level or pair-level splitting.
   - *Why we chose it*: Prevents leakage where a customer's follow-up tweet in the test set has context embedded in the retrieval index.
   - *Evidence*: Standard practice for conversational data.
   - *Tradeoff*: Reduces effective independent samples slightly but guarantees clean isolation.

3. **Three-Way Data Split (Development / Retrieval / Test)**
   - *Alternatives considered*: Two-way split (Retrieval / Test).
   - *Why we chose it*: Ensures the taxonomy discovery and pilot labeling are done on "seen" data without contaminating the retrieval index or the sealed golden evaluation set.
   - *Evidence*: Architecture design requirement.
   - *Tradeoff*: Reduces the size of the retrieval pool and test pool slightly.

4. **UNKNOWN Intent**
   - *Alternatives considered*: Forcing the classifier to pick the closest defined intent.
   - *Why we chose it*: Improves safety. Ambiguous, off-topic, or non-English messages map to a safe "escalate" action.
   - *Evidence*: Take-home policy / best practice.
   - *Tradeoff*: May lower nominal classification accuracy if overused, but increases operational safety.

*(Note: Additional decisions will be added as implementation progresses.)*
