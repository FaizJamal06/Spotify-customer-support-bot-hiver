import json
import re
import random
import sys
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

def clean(t): return re.sub(r'@[A-Za-z0-9_]+', '', t.lower())

def main():
    # Load dev threads
    with open('data/generated/pool_split.json', 'r', encoding='utf-8') as f:
        dev_ids = set(json.load(f)['dev_thread_ids'])

    dev_threads = {}
    pairs = []
    with open('data/generated/spotify_threads.jsonl', 'r', encoding='utf-8') as f:
        for line in f:
            if not line.strip(): continue
            th = json.loads(line)
            if th['thread_id'] in dev_ids:
                dev_threads[th['thread_id']] = th
                for p in th['customer_brand_pairs']:
                    pairs.append({
                        'thread_id': th['thread_id'],
                        'tweet_id': p['customer_tweet_id'],
                        'author_id': p.get('customer_author_id', 'unknown'),
                        'text': p['customer_text']
                    })

    random.seed(42)
    sampled = random.sample(pairs, min(300, len(pairs)))

    # Provisional Intents (8-label taxonomy, PLAN_PROMOTION removed)
    intents = {
        'ACCOUNT_ACCESS': ['account', 'login', 'password', 'facebook', 'email', 'hacked'],
        'SUBSCRIPTION_BILLING': ['premium', 'family', 'charge', 'pay', 'billing', 'cancel', 'subscribe', 'money', 'refund', 'promotion', 'offer', 'deal'],
        'APP_TECH_ISSUE': ['app', 'crash', 'freeze', 'loading', 'offline', 'download', 'update', 'android', 'iphone', 'ios', 'bug', 'glitch', 'bluetooth', 'desktop', 'mac', 'windows', 'working', 'broken', 'error'],
        'CONTENT_CATALOG': ['song', 'playlist', 'album', 'podcast', 'lyrics', 'missing', 'track', 'available', 'removed'],
        'FEATURE_FEEDBACK': ['feature', 'bring back', 'add', 'ui', 'design', 'ruined'],
        'ARTIST_SUPPORT': ['my artist page', 'my release', 'distributor', 'my music'],
        'GENERAL_HOW_TO_INFO': ['how to', 'how do i', 'what is', 'where is', 'how can i', 'student', 'hulu', 'eligible']
    }

    results = []

    for i, p in enumerate(sampled, 1):
        tid = p['thread_id']
        twid = p['tweet_id']
        text = p['text']
        c_text = clean(text)
        
        # Context
        th = dev_threads[tid]
        msgs_sorted = sorted(th['messages'], key=lambda x: x['tweet_id'])
        context_msgs = [m for m in msgs_sorted if m['tweet_id'] < twid]
        context_str = " | ".join([f"{'C' if m['inbound'] else 'B'}: {m['text']}" for m in context_msgs])
        if not context_str:
            context_str = "None"
            
        # Intent Matching
        matched_intents = []
        for k, words in intents.items():
            if any(w in c_text for w in words):
                matched_intents.append(k)
                
        # Provisional group
        if matched_intents:
            prov = matched_intents[0]
        else:
            prov = 'UNKNOWN_OTHER'

        # Subtype flags for UNKNOWN_OTHER (overlapping)
        subtype_flags = []
        if len(c_text.strip()) < 20 or not c_text.replace('http', '').replace(':', '').replace('/', '').strip():
            subtype_flags.append('ambiguous/insufficient_context')
        if any(w in c_text for w in ['thanks', 'it works', 'fixed', 'no problem', 'resolved', 'yep', 'got it', 'thank you', 'awesome']):
            subtype_flags.append('conversational/closure')
        if not matched_intents and not subtype_flags:
            subtype_flags.append('irrelevant/off-topic')

        # Issues/Boundaries
        boundaries = []
        if 'ACCOUNT_ACCESS' in matched_intents and 'SUBSCRIPTION_BILLING' in matched_intents: boundaries.append('account vs billing')
        if 'CONTENT_CATALOG' in matched_intents and 'APP_TECH_ISSUE' in matched_intents: boundaries.append('content vs tech')
        if 'FEATURE_FEEDBACK' in matched_intents and 'APP_TECH_ISSUE' in matched_intents: boundaries.append('feature vs tech')
        if 'GENERAL_HOW_TO_INFO' in matched_intents and 'SUBSCRIPTION_BILLING' in matched_intents: boundaries.append('plan how-to vs billing')
        if 'ARTIST_SUPPORT' in matched_intents and 'CONTENT_CATALOG' in matched_intents: boundaries.append('artist vs content')
        if 'GENERAL_HOW_TO_INFO' in matched_intents and 'ACCOUNT_ACCESS' in matched_intents: boundaries.append('how-to vs account')
        if any(w in c_text for w in ['country', 'available in', 'region', 'uk', 'us', 'usa', 'india']): boundaries.append('geography as modifier')
        if len(matched_intents) > 1: boundaries.append('multi-intent')
        if len(context_msgs) > 1 or c_text.strip().startswith(('yes', 'no', 'it still', 'it is')): boundaries.append('context-dependent')
        
        bound_str = ", ".join(boundaries) if boundaries else ""
        sub_str = ", ".join(subtype_flags) if prov == 'UNKNOWN_OTHER' else ""
        
        disp_text = text.replace('\\n', ' ').replace('\\r', '')
        disp_context = context_str.replace('\\n', ' ').replace('\\r', '')
        if len(disp_context) > 100: disp_context = disp_context[-100:] + '...'
        
        results.append(f"| {i} | {twid} | `{disp_context}` | {disp_text} | {prov} | {bound_str} | {sub_str} | |")

    with open('discovery/HUMAN_REVIEW.md', 'w', encoding='utf-8') as f:
        f.write("# Discovery Sample - Human Review Table\n\n")
        f.write("Please review the provisional groups and fill in the **Human Decision / Gold Label** column.\n\n")
        f.write("| Ex | Tweet ID | Prior Context (Truncated) | Customer Message | Provisional Group | Potential Issue/Boundary | UNKNOWN Subtype Flags | Human Decision / Gold Label |\n")
        f.write("|---|---|---|---|---|---|---|---|\n")
        for r in results:
            f.write(r + "\n")

if __name__ == '__main__':
    main()
