import json
import re
import random
from collections import defaultdict
from datetime import datetime
import sys
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

def clean(t): return re.sub(r'@[A-Za-z0-9_]+', '', t.lower())

def analyze_dataset():
    # 1. Load split data
    with open('data/generated/pool_split.json', 'r', encoding='utf-8') as f:
        dev_ids = set(json.load(f)['dev_thread_ids'])

    dev_threads = {}
    all_dev_pairs = []
    
    dates = []
    
    with open('data/generated/spotify_threads.jsonl', 'r', encoding='utf-8') as f:
        for line in f:
            if not line.strip(): continue
            th = json.loads(line)
            if th['thread_id'] in dev_ids:
                dev_threads[th['thread_id']] = th
                
                # Extract dates
                for msg in th['messages']:
                    # Wed Nov 29 00:25:40 +0000 2017
                    try:
                        dt = datetime.strptime(msg['created_at'], "%a %b %d %H:%M:%S +0000 %Y")
                        dates.append(dt)
                    except:
                        pass
                
                for p in th['customer_brand_pairs']:
                    all_dev_pairs.append({
                        'thread_id': th['thread_id'],
                        'tweet_id': p['customer_tweet_id'],
                        'author_id': p.get('customer_author_id', 'unknown'),
                        'text': p['customer_text']
                    })

    # Sample exactly like the original
    random.seed(42)
    sample_size = min(300, len(all_dev_pairs))
    sampled_pairs = random.sample(all_dev_pairs, sample_size)
    sampled_ids = {p['tweet_id'] for p in sampled_pairs}

    # Heuristics (8-label taxonomy, PLAN_PROMOTION removed)
    intents = {
        'ACCOUNT_ACCESS': ['account', 'login', 'password', 'facebook', 'email', 'hacked'],
        'SUBSCRIPTION_BILLING': ['premium', 'family', 'charge', 'pay', 'billing', 'cancel', 'subscribe', 'money', 'refund', 'promotion', 'offer', 'deal'],
        'APP_TECH_ISSUE': ['app', 'crash', 'freeze', 'loading', 'offline', 'download', 'update', 'android', 'iphone', 'ios', 'bug', 'glitch', 'bluetooth', 'desktop', 'mac', 'windows', 'working', 'broken', 'error'],
        'CONTENT_CATALOG': ['song', 'playlist', 'album', 'podcast', 'lyrics', 'missing', 'track', 'available', 'removed'],
        'FEATURE_FEEDBACK': ['feature', 'bring back', 'add', 'ui', 'design', 'ruined'],
        'ARTIST_SUPPORT': ['my artist page', 'my release', 'distributor', 'my music'],
        'GENERAL_HOW_TO_INFO': ['how to', 'how do i', 'what is', 'where is', 'how can i', 'student', 'hulu', 'eligible']
    }

    def categorize(p):
        text = p['text']
        c_text = clean(text)
        
        matched_intents = []
        for k, words in intents.items():
            if any(w in c_text for w in words):
                matched_intents.append(k)
        
        tid = p['thread_id']
        twid = p['tweet_id']
        th = dev_threads[tid]
        msgs_sorted = sorted(th['messages'], key=lambda x: x['tweet_id'])
        context_msgs = [m for m in msgs_sorted if m['tweet_id'] < twid]
        
        is_ambiguous = len(c_text.strip()) < 20 or not c_text.replace('http', '').replace(':', '').replace('/', '').strip()
        is_closure = any(w in c_text for w in ['thanks', 'it works', 'fixed', 'no problem', 'resolved', 'yep', 'got it', 'thank you', 'awesome'])
        is_context = len(context_msgs) > 1 or c_text.strip().startswith(('yes', 'no', 'it still', 'it is'))
        is_multi = len(matched_intents) > 1
        
        # Subtype assignment
        subtype = None
        if is_closure: subtype = 'conversational/closure'
        elif is_ambiguous: subtype = 'ambiguous'
        elif is_context and not matched_intents: subtype = 'context-dependent'
        elif not matched_intents: subtype = 'irrelevant/off-topic'
        
        if matched_intents:
            primary = matched_intents[0]
        else:
            primary = 'UNKNOWN_OTHER'
            
        boundary = []
        if 'ACCOUNT_ACCESS' in matched_intents and 'SUBSCRIPTION_BILLING' in matched_intents: boundary.append('account vs billing')
        if 'CONTENT_CATALOG' in matched_intents and 'APP_TECH_ISSUE' in matched_intents: boundary.append('content vs tech')
        if 'FEATURE_FEEDBACK' in matched_intents and 'APP_TECH_ISSUE' in matched_intents: boundary.append('feature vs tech')
        if 'GENERAL_HOW_TO_INFO' in matched_intents and 'SUBSCRIPTION_BILLING' in matched_intents: boundary.append('plan how-to vs billing')
        if 'ARTIST_SUPPORT' in matched_intents and 'CONTENT_CATALOG' in matched_intents: boundary.append('artist vs content')
        if 'GENERAL_HOW_TO_INFO' in matched_intents and 'ACCOUNT_ACCESS' in matched_intents: boundary.append('how-to vs account')
        if any(w in c_text for w in ['country', 'available in', 'region', 'uk', 'us', 'usa', 'india']): boundary.append('geography modifier')
        if is_multi: boundary.append('multi-intent')
        if is_context: boundary.append('context-dependent')
        if is_ambiguous: boundary.append('ambiguous')
        
        return {
            'primary': primary,
            'subtype': subtype,
            'is_actionable': primary != 'UNKNOWN_OTHER' and not is_closure and not is_ambiguous,
            'is_multi': is_multi,
            'boundary': boundary,
            'is_ambiguous': is_ambiguous,
            'is_closure': is_closure,
            'is_context': is_context,
            'thread_len': len(th['messages'])
        }

    # Run analysis on all
    full_stats = defaultdict(int)
    full_edge = defaultdict(int)
    full_boundary = defaultdict(int)
    
    for p in all_dev_pairs:
        r = categorize(p)
        full_stats[r['primary']] += 1
        if r['primary'] == 'UNKNOWN_OTHER' and r['subtype']: full_edge[r['subtype']] += 1
        for b in r['boundary']: full_boundary[b] += 1
        
        full_edge['actionable'] += 1 if r['is_actionable'] else 0
        full_edge['multi-intent'] += 1 if r['is_multi'] else 0
        full_edge['ambiguous'] += 1 if r['is_ambiguous'] else 0
        full_edge['conversational'] += 1 if r['is_closure'] else 0
        full_edge['context-dependent'] += 1 if r['is_context'] else 0

    # Run analysis on sample
    sample_stats = defaultdict(int)
    sample_edge = defaultdict(int)
    sample_boundary = defaultdict(int)
    sample_threads = set()
    sample_customers = set()
    sample_lengths = defaultdict(int)
    
    for p in sampled_pairs:
        r = categorize(p)
        sample_stats[r['primary']] += 1
        if r['primary'] == 'UNKNOWN_OTHER' and r['subtype']: sample_edge[r['subtype']] += 1
        for b in r['boundary']: sample_boundary[b] += 1
        
        sample_edge['actionable'] += 1 if r['is_actionable'] else 0
        sample_edge['multi-intent'] += 1 if r['is_multi'] else 0
        sample_edge['ambiguous'] += 1 if r['is_ambiguous'] else 0
        sample_edge['conversational'] += 1 if r['is_closure'] else 0
        sample_edge['context-dependent'] += 1 if r['is_context'] else 0
        
        sample_threads.add(p['thread_id'])
        sample_customers.add(p['author_id'])
        sample_lengths[r['thread_len']] += 1

    # Date ranges
    date_min = min(dates).strftime('%Y-%m-%d') if dates else 'N/A'
    date_max = max(dates).strftime('%Y-%m-%d') if dates else 'N/A'
    
    unique_cust_full = len(set(p['author_id'] for p in all_dev_pairs))

    # Writing Markdown
    with open('discovery/DEVELOPMENT_DIVERSITY_AUDIT.md', 'w', encoding='utf-8') as f:
        f.write("# Development Pool Diversity Audit\n\n")
        f.write("## 1. Full Development Pool Overview\n")
        f.write(f"- **Total Pairs**: {len(all_dev_pairs)}\n")
        f.write(f"- **Total Threads**: {len(dev_threads)}\n")
        f.write(f"- **Unique Customers**: {unique_cust_full}\n")
        f.write(f"- **Date Coverage**: {date_min} to {date_max}\n\n")

        f.write("## 2. Thematic Distribution Comparison (Heuristic)\n")
        f.write("*Note: These counts are generated via simple keyword heuristics and are strictly provisional. They are NOT ground truth labels.*\n\n")
        
        f.write("| Theme | Full Dev Count | Full Dev % | Discovery 300 Count | Discovery % | Difference |\n")
        f.write("|---|---:|---:|---:|---:|---:|\n")
        
        for k in intents.keys() | {'UNKNOWN_OTHER'}:
            fc = full_stats[k]
            fp = (fc / len(all_dev_pairs)) * 100
            sc = sample_stats[k]
            sp = (sc / 300) * 100
            diff = sp - fp
            f.write(f"| {k} | {fc} | {fp:.1f}% | {sc} | {sp:.1f}% | {diff:+.1f}% |\n")
            
        f.write("\n## 3. Edge Case Estimation\n")
        f.write("| Category | Full Dev Est. % | Discovery Est. % | Diff |\n")
        f.write("|---|---:|---:|---:|\n")
        
        cats = ['actionable', 'ambiguous', 'conversational', 'context-dependent', 'multi-intent']
        for c in cats:
            fp = (full_edge[c] / len(all_dev_pairs)) * 100
            sp = (sample_edge[c] / 300) * 100
            f.write(f"| {c} | {fp:.1f}% | {sp:.1f}% | {sp-fp:+.1f}% |\n")

        f.write("\n## 4. UNKNOWN_OTHER Subtype Comparison\n")
        f.write("| Subtype | Full Dev % of UNK | Discovery % of UNK |\n")
        f.write("|---|---:|---:|\n")
        
        unk_full = full_stats['UNKNOWN_OTHER'] or 1
        unk_sample = sample_stats['UNKNOWN_OTHER'] or 1
        
        subtypes = ['ambiguous', 'conversational/closure', 'context-dependent', 'irrelevant/off-topic']
        for s in subtypes:
            fp = (full_edge[s] / unk_full) * 100
            sp = (sample_edge[s] / unk_sample) * 100
            f.write(f"| {s} | {fp:.1f}% | {sp:.1f}% |\n")

        f.write("\n## 5. Diversity Check (300 Sample)\n")
        f.write(f"- **Unique Threads**: {len(sample_threads)} / 300\n")
        f.write(f"- **Unique Customers**: {len(sample_customers)} / 300\n")
        
        len2_pct = (sample_lengths[2] / 300) * 100
        f.write(f"- **Short Threads (len=2) in Sample**: {len2_pct:.1f}%\n")
        
        f.write("\n## 6. Boundary Cases Coverage (in 300 Sample)\n")
        bounds = ['account vs billing', 'content vs tech', 'feature vs tech', 'plan vs billing', 'artist vs content', 'how-to vs account', 'geography modifier', 'multi-intent', 'context-dependent', 'ambiguous']
        for b in bounds:
            f.write(f"- **{b}**: {sample_boundary[b]} examples\n")
            
        f.write("\n## 7. Assessment & Next Steps\n")
        
        # Simple heuristic assessment
        if sample_stats['UNKNOWN_OTHER'] > 120 or abs((sample_stats['UNKNOWN_OTHER']/300) - (full_stats['UNKNOWN_OTHER']/len(all_dev_pairs))) > 0.1:
            f.write("### Assessment\n**C. Discovery sample should be resampled**\n")
            f.write("\n*Reasoning*: The sample heavily skews towards UNKNOWN_OTHER or deviates significantly from the true distribution of the development pool. Since random sampling can cluster heavily in conversational/closure text in support datasets, stratifying by provisional groups is recommended to ensure all boundary cases and minority intents are sufficiently covered for manual discovery.\n")
            
            f.write("\n### Proposed Resampling Strategy\n")
            f.write("1. **Stratified by intent**: Sample ~20-30 examples from each provisional top-level intent to guarantee coverage.\n")
            f.write("2. **Cap UNKNOWN_OTHER**: Limit conversational/ambiguous/off-topic to 10% of the sample so they don't drown out actionable support tickets.\n")
            f.write("3. **Force Boundary Cases**: Ensure at least 5 examples of every boundary case (e.g., account vs billing, feature vs tech).\n")
            f.write("4. **Thread Diversity**: Limit to 1 example per thread, max 1 example per customer.\n")
        else:
            f.write("### Assessment\n**A. Discovery sample is sufficiently diverse**\n")
            f.write("\n*Reasoning*: The 300-example sample closely matches the heuristic thematic distribution of the overall DEV pool. It contains enough unique threads and captures boundary cases at similar rates to the full pool.\n")
            
        f.write("\n## What this means for me (User)\n")
        f.write("- Do not review the current `HUMAN_REVIEW.md` yet. Let's decide if we want to proceed with resampling based on this audit.\n")
        f.write("- Pay attention to the UNKNOWN_OTHER subtypes: if too many are just 'thanks' or ambiguous links, we aren't learning anything about the taxonomy from them.\n")

if __name__ == "__main__":
    analyze_dataset()
