import json
import re
import random
import os

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
                        'customer_text': p['customer_text'],
                        'brand_text': p['brand_text']
                    })

    random.seed(42)
    sampled = random.sample(pairs, min(300, len(pairs)))

    # Provisional Intents (8-label taxonomy, PLAN_PROMOTION removed)
    intents = {
        'ACCOUNT_ACCESS': ['account', 'login', 'password', 'facebook', 'email', 'hacked'],
        'SUBSCRIPTION_BILLING': ['premium', 'family', 'charge', 'pay', 'billing', 'ads', 'cancel', 'subscribe', 'money', 'promotion', 'offer', 'deal'],
        'APP_TECH_ISSUE': ['app', 'crash', 'freeze', 'loading', 'offline', 'download', 'update', 'android', 'iphone', 'ios', 'bug', 'glitch', 'bluetooth', 'desktop', 'mac', 'windows', 'working', 'broken'],
        'CONTENT_CATALOG': ['song', 'playlist', 'album', 'podcast', 'lyrics', 'missing', 'artist', 'track'],
        'FEATURE_FEEDBACK': ['feature', 'bring back', 'add', 'ui', 'design', 'update ruined'],
        'ARTIST_SUPPORT': ['my artist page', 'my release', 'distributor'],
        'GENERAL_HOW_TO_INFO': ['how to', 'how do i', 'what is', 'where is', 'how can i', 'student', 'hulu', 'eligible']
    }

    # Complex Edge Cases
    edge_cases = {
        'general how-to/information': set(),
        'plan eligibility/promotions': set(),
        'geographic availability': set(),
        'ambiguous/insufficient context': set(),
        'conversational follow-up/closure': set(),
        'multi-intent': set(),
        'feature removed vs feature broken': set(),
        'content availability vs technical issue': set(),
        'account/security vs billing': set(),
        'target message depends strongly on prior thread context': set()
    }

    def clean(t): return re.sub(r'@[A-Za-z0-9_]+', '', t.lower())

    results = []
    provisional_counts = {k: 0 for k in intents.keys()}
    provisional_counts['UNKNOWN'] = 0

    for i, p in enumerate(sampled, 1):
        tid = p['thread_id']
        twid = p['tweet_id']
        text = p['customer_text']
        c_text = clean(text)
        
        # Get prior context
        th = dev_threads[tid]
        msgs_sorted = sorted(th['messages'], key=lambda x: x['tweet_id'])
        context_msgs = [m for m in msgs_sorted if m['tweet_id'] < twid]
        context_str = " | ".join([f"{'C' if m['inbound'] else 'B'}: {m['text']}" for m in context_msgs])
        if not context_str:
            context_str = "None"
        
        # Determine provisional intent
        matched_intents = []
        for k, words in intents.items():
            if any(w in c_text for w in words):
                matched_intents.append(k)
        
        if len(matched_intents) == 1:
            prov = matched_intents[0]
        elif len(matched_intents) > 1:
            prov = matched_intents[0] # Pick first, but flag as multi
            edge_cases['multi-intent'].add(twid)
            if 'ACCOUNT_ACCESS' in matched_intents and 'SUBSCRIPTION_BILLING' in matched_intents:
                edge_cases['account/security vs billing'].add(twid)
            if 'CONTENT_CATALOG' in matched_intents and 'APP_TECH_ISSUE' in matched_intents:
                edge_cases['content availability vs technical issue'].add(twid)
        else:
            prov = 'UNKNOWN'
            
        provisional_counts[prov] += 1
        
        # Flag other edge cases
        if any(w in c_text for w in ['how to', 'how do i', 'what is', 'where is']):
            edge_cases['general how-to/information'].add(twid)
        if any(w in c_text for w in ['student', 'hulu', 'eligible', 'promotion', 'offer', 'deal']):
            edge_cases['plan eligibility/promotions'].add(twid)
        if any(w in c_text for w in ['country', 'available in', 'region', 'uk', 'us', 'usa']):
            edge_cases['geographic availability'].add(twid)
        if len(c_text.strip()) < 20 or (not c_text.replace('http', '').replace(':', '').replace('/', '').strip()):
            edge_cases['ambiguous/insufficient context'].add(twid)
        if any(w in c_text for w in ['thanks', 'it works', 'fixed', 'no problem', 'resolved', 'yep', 'got it']):
            edge_cases['conversational follow-up/closure'].add(twid)
        if any(w in c_text for w in ['bring back', 'used to', 'removed']) and any(w in c_text for w in ['not working', 'broken', 'crash']):
            edge_cases['feature removed vs feature broken'].add(twid)
        if len(context_msgs) > 1 or c_text.strip().startswith(('yes', 'no', 'it still', 'it is')):
            edge_cases['target message depends strongly on prior thread context'].add(twid)
            
        # Clean text for table display (remove newlines)
        disp_text = text.replace('\\n', ' ').replace('\\r', '')
        disp_context = context_str.replace('\\n', ' ').replace('\\r', '')
        if len(disp_context) > 100: disp_context = disp_context[-100:] + '...'
        
        results.append(f"| {i} | {twid} | `{disp_context}` | {disp_text} | {prov} | |")

    # Write output
    with open('discovery/HUMAN_REVIEW.md', 'w', encoding='utf-8') as f:
        f.write("# Discovery Sample - Human Review\n\n")
        
        f.write("## Heuristic/Provisional Group Counts\n")
        f.write("*Note: These are based on simple keywords and are NOT ground truth.*\n\n")
        for k, v in provisional_counts.items():
            f.write(f"- **{k}**: {v}\n")
        
        f.write("\n## Edge Case Identification\n")
        for k, ids in edge_cases.items():
            f.write(f"### {k}\n")
            if ids:
                f.write(f"Example IDs: {', '.join(map(str, list(ids)[:10]))}{' ...' if len(ids)>10 else ''} (Total: {len(ids)})\n")
            else:
                f.write("None detected heuristically.\n")
                
        f.write("\n## 300 Examples for Manual Review\n\n")
        f.write("| Ex | Tweet ID | Prior Context (Truncated) | Customer Message | Provisional Group | Your Notes/Gold Label |\n")
        f.write("|---|---|---|---|---|---|\n")
        for r in results:
            f.write(r + "\n")

if __name__ == '__main__':
    main()
