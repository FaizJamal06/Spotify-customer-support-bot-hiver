import pandas as pd
import random
import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

df = pd.read_csv('twcs.csv')

# SpotifyCares messages
spotify = df[df['author_id'] == 'SpotifyCares']
# Customer messages SpotifyCares replied to
cust_ids = spotify['in_response_to_tweet_id'].dropna().astype(int).tolist()
cust_msgs = df[df['tweet_id'].isin(cust_ids)]

print("=== SAMPLE CUSTOMER MESSAGES TO SpotifyCares ===")
print()
random.seed(42)
sample_indices = random.sample(range(len(cust_msgs)), 40)
for i, idx in enumerate(sample_indices):
    row = cust_msgs.iloc[idx]
    replies = spotify[spotify['in_response_to_tweet_id'] == row['tweet_id']]
    print(f"--- Example {i+1} ---")
    print(f"Customer ({row['author_id']}): {row['text'][:400]}")
    if len(replies) > 0:
        reply = replies.iloc[0]
        print(f"SpotifyCares: {reply['text'][:400]}")
    print()

print("=" * 60)
print()

# Temporal coverage
print("=== TEMPORAL COVERAGE ===")
spotify_all = df[(df['author_id'] == 'SpotifyCares') | (df['tweet_id'].isin(cust_ids))]
dates = pd.to_datetime(spotify_all['created_at'], errors='coerce')
print(f"Earliest: {dates.min()}")
print(f"Latest: {dates.max()}")
print(f"Date range: {dates.max() - dates.min()}")
print()

# Text length analysis
print("=== TEXT LENGTH ANALYSIS ===")
cust_lengths = cust_msgs['text'].str.len()
brand_lengths = spotify['text'].str.len()
print("Customer message length:")
print(cust_lengths.describe())
print()
print("SpotifyCares response length:")
print(brand_lengths.describe())
print()

# Response patterns
print("=== COMMON RESPONSE PATTERNS ===")
# Check for DM redirects
dm_patterns = spotify['text'].str.contains('DM|direct message|inbox|private message', case=False, na=False)
print(f"Responses mentioning DM/inbox: {dm_patterns.sum()} ({dm_patterns.sum()/len(spotify)*100:.1f}%)")

link_patterns = spotify['text'].str.contains('http|https|link', case=False, na=False)
print(f"Responses with links: {link_patterns.sum()} ({link_patterns.sum()/len(spotify)*100:.1f}%)")

sorry_patterns = spotify['text'].str.contains('sorry|apologize|apologies', case=False, na=False)
print(f"Responses with apology: {sorry_patterns.sum()} ({sorry_patterns.sum()/len(spotify)*100:.1f}%)")

# Check for common keywords in customer messages
print()
print("=== COMMON CUSTOMER ISSUE KEYWORDS ===")
keywords = ['premium', 'account', 'password', 'login', 'play', 'song', 'playlist',
            'offline', 'download', 'family', 'student', 'charge', 'payment', 'refund',
            'cancel', 'subscription', 'ads', 'free', 'error', 'crash', 'bug', 'update',
            'device', 'phone', 'app', 'connect', 'bluetooth', 'speaker', 'shuffle',
            'repeat', 'recommend', 'discover', 'hacked', 'stolen']
for kw in keywords:
    count = cust_msgs['text'].str.contains(kw, case=False, na=False).sum()
    if count > 50:
        print(f"  '{kw}': {count} ({count/len(cust_msgs)*100:.1f}%)")
