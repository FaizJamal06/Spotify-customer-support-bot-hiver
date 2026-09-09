import pandas as pd
import random
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

df = pd.read_csv('twcs.csv')

# Efficient thread analysis using vectorized operations
print("=== EFFICIENT THREAD/CONVERSATION ANALYSIS ===")

# For SpotifyCares: count conversation pairs
spotify = df[df['author_id'] == 'SpotifyCares'].copy()
spotify_inbound_ids = spotify['in_response_to_tweet_id'].dropna().astype(int)

# How many SpotifyCares messages are part of multi-turn threads?
# A SpotifyCares message that is also replied to by a customer
spotify_tweet_ids = set(spotify['tweet_id'].tolist())
customer_replies_to_spotify = df[(df['inbound'] == True) & (df['in_response_to_tweet_id'].isin(spotify_tweet_ids))]
print(f"Customer messages that reply to SpotifyCares: {len(customer_replies_to_spotify)}")
print(f"This indicates multi-turn conversations")

# Approximate conversation length by counting reply chains
# For a sample of SpotifyCares conversations, count the back-and-forth
print("\n=== CONVERSATION DEPTH ANALYSIS (sampled) ===")

# Build efficient parent lookup
parent_lookup = {}
for _, row in df[df['in_response_to_tweet_id'].notna()].iterrows():
    parent_lookup[row['tweet_id']] = int(row['in_response_to_tweet_id'])

# Trace conversation depth for a sample
random.seed(42)
sample_spotify = spotify.sample(min(1000, len(spotify)))
depths = []
for _, row in sample_spotify.iterrows():
    depth = 0
    current = row['tweet_id']
    visited = set()
    while current in parent_lookup and current not in visited:
        visited.add(current)
        current = parent_lookup[current]
        depth += 1
    depths.append(depth)

s = pd.Series(depths)
print(f"Conversation depth (from SpotifyCares message to root):")
print(f"  Mean: {s.mean():.1f}, Median: {s.median():.0f}, Max: {s.max()}")
print(f"  Distribution:")
for d in range(0, min(int(s.max()) + 1, 10)):
    count = (s == d).sum()
    print(f"    Depth {d}: {count} ({count/len(s)*100:.1f}%)")
if s.max() >= 10:
    count = (s >= 10).sum()
    print(f"    Depth 10+: {count} ({count/len(s)*100:.1f}%)")

# Brand comparison - focus on top candidates
print("\n\n=== DETAILED BRAND COMPARISON ===")
top_brands = ['SpotifyCares', 'AppleSupport', 'AmazonHelp', 'Uber_Support', 
              'TMobileHelp', 'XboxSupport', 'hulu_support', 'AskPlayStation']

for brand in top_brands:
    brand_out = df[(df['author_id'] == brand) & (df['inbound'] == False)]
    cust_ids = brand_out['in_response_to_tweet_id'].dropna().astype(int)
    cust_msgs = df[df['tweet_id'].isin(set(cust_ids.tolist()))]
    
    # DM redirect rate
    dm_rate = brand_out['text'].str.contains('DM|direct message|inbox', case=False, na=False).mean()
    
    # Link rate
    link_rate = brand_out['text'].str.contains('http', case=False, na=False).mean()
    
    # Average response length
    avg_resp_len = brand_out['text'].str.len().mean()
    
    # Unique response diversity (lower = more templated)
    unique_responses = brand_out['text'].nunique()
    response_diversity = unique_responses / len(brand_out)
    
    # Customer message diversity
    unique_cust = cust_msgs['text'].nunique() if len(cust_msgs) > 0 else 0
    
    print(f"\n--- {brand} ---")
    print(f"  Outbound messages: {len(brand_out)}")
    print(f"  Unique customer messages replied to: {len(cust_msgs)}")
    print(f"  DM redirect rate: {dm_rate*100:.1f}%")
    print(f"  Link rate: {link_rate*100:.1f}%")
    print(f"  Avg response length: {avg_resp_len:.0f} chars")
    print(f"  Response diversity: {response_diversity:.3f} ({unique_responses} unique / {len(brand_out)} total)")
    print(f"  Unique customer messages: {unique_cust}")

# Duplicate analysis for SpotifyCares
print("\n\n=== SpotifyCares DUPLICATE RESPONSE ANALYSIS ===")
from collections import Counter
# Normalize responses (strip @mentions)
import re
normalized = spotify['text'].apply(lambda x: re.sub(r'@\S+', '', x).strip() if isinstance(x, str) else '')
resp_counts = Counter(normalized.tolist())
print("Top 15 most repeated response patterns (after removing @mentions):")
for text, count in resp_counts.most_common(15):
    print(f"  [{count:>4}x] {text[:120]}")

# What fraction of responses are near-duplicates?
single_use = sum(1 for c in resp_counts.values() if c == 1)
print(f"\nUnique (single-use) responses: {single_use} ({single_use/len(spotify)*100:.1f}%)")
print(f"Repeated responses: {len(spotify) - single_use} ({(len(spotify) - single_use)/len(spotify)*100:.1f}%)")
