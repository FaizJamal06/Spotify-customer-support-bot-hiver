import json
import random
import re

def main():
    with open('data/generated/pool_split.json', 'r', encoding='utf-8') as f:
        dev_ids = set(json.load(f)['dev_thread_ids'])

    pairs = []
    with open('data/generated/spotify_threads.jsonl', 'r', encoding='utf-8') as f:
        for line in f:
            if not line.strip(): continue
            th = json.loads(line)
            if th['thread_id'] in dev_ids:
                for p in th['customer_brand_pairs']:
                    pairs.append((th['thread_id'], p['customer_tweet_id'], p['customer_text'], p['brand_text']))

    random.seed(42)
    sampled = random.sample(pairs, min(300, len(pairs)))

    # A slightly expanded heuristic grouping
    categories = {
        'ACCOUNT_ACCESS': lambda t: any(w in t.lower() for w in ['account', 'login', 'password', 'facebook', 'email', 'hacked']),
        'SUBSCRIPTION_BILLING': lambda t: any(w in t.lower() for w in ['premium', 'family', 'charge', 'pay', 'billing', 'ads', 'student', 'cancel']),
        'APP_BUG_CRASH': lambda t: any(w in t.lower() for w in ['app', 'crash', 'freeze', 'loading', 'offline', 'download', 'update', 'android', 'iphone', 'ios', 'bug', 'glitch']),
        'CONTENT_PLAYBACK': lambda t: any(w in t.lower() for w in ['song', 'playlist', 'album', 'podcast', 'lyrics', 'play', 'shuffle', 'missing', 'artist']),
        'SERVICE_OUTAGE': lambda t: any(w in t.lower() for w in ['down', 'working', 'broken', 'server', 'connect']),
        'FEATURE_FEEDBACK': lambda t: any(w in t.lower() for w in ['feature', 'bring back', 'add', 'why did you remove', 'ui', 'design']),
    }

    categorized = {k: [] for k in categories}
    categorized['UNKNOWN_OR_OTHER'] = []

    for p in sampled:
        text = p[2]
        matched = False
        # Assign to the first category that matches
        for k, func in categories.items():
            if func(text):
                categorized[k].append(p)
                matched = True
                break
        if not matched:
            categorized['UNKNOWN_OR_OTHER'].append(p)

    with open('discovery/candidates.txt', 'w', encoding='utf-8') as f:
        for k, items in categorized.items():
            f.write(f'\\n--- {k} (Freq: {len(items)}/300, {len(items)/300*100:.1f}%) ---\n')
            for i in items[:5]: # Show up to 5 examples
                f.write(f'ID {i[1]}: {i[2]}\n')

if __name__ == '__main__':
    main()
