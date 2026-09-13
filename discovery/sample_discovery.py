import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
import json
import random
from pathlib import Path

def main():
    random.seed(42)
    
    # Paths
    base_dir = Path(__file__).parent.parent
    threads_path = base_dir / "data" / "generated" / "spotify_threads.jsonl"
    split_path = base_dir / "data" / "generated" / "pool_split.json"
    out_path = base_dir / "discovery" / "discovery_sample.md"
    
    # Load dev thread IDs
    with open(split_path, 'r', encoding='utf-8') as f:
        split_data = json.load(f)
        dev_ids = set(split_data["dev_thread_ids"])
        
    print(f"Loaded {len(dev_ids)} DEV thread IDs.")
    
    # Collect all pairs from DEV threads
    dev_threads = {}
    all_dev_pairs = []
    
    with open(threads_path, 'r', encoding='utf-8') as f:
        for line in f:
            if not line.strip(): continue
            th = json.loads(line)
            tid = th["thread_id"]
            if tid in dev_ids:
                dev_threads[tid] = th
                for p in th["customer_brand_pairs"]:
                    # attach thread info so we can reconstruct context later
                    all_dev_pairs.append({
                        "thread_id": tid,
                        "pair": p
                    })
                    
    print(f"Collected {len(all_dev_pairs)} pairs from DEV pool.")
    
    # Sample 300
    sample_size = min(300, len(all_dev_pairs))
    sampled_pairs = random.sample(all_dev_pairs, sample_size)
    print(f"Sampled {sample_size} pairs for discovery.")
    
    # Generate markdown
    with open(out_path, 'w', encoding='utf-8') as f:
        f.write("# Intent Discovery Sample (300 pairs)\n\n")
        
        for i, sp in enumerate(sampled_pairs, 1):
            tid = sp["thread_id"]
            pair = sp["pair"]
            th = dev_threads[tid]
            
            # Find the index of the brand's response in the thread messages
            # We want to show the context leading UP to the customer message
            msgs = th["messages"]
            
            # Sort messages chronologically
            # created_at format: "Wed Nov 29 00:25:40 +0000 2017"
            # It's easier to sort by tweet_id since twitter IDs are mostly chronological
            msgs_sorted = sorted(msgs, key=lambda x: x["tweet_id"])
            
            cust_tid = pair["customer_tweet_id"]
            brand_tid = pair["brand_tweet_id"]
            
            # Context is any message before the brand_tid
            context_msgs = [m for m in msgs_sorted if m["tweet_id"] <= cust_tid]
            
            f.write(f"## Example {i} (Thread {tid}, Tweet {cust_tid})\n\n")
            
            if len(context_msgs) > 1:
                f.write("**Prior Context:**\n")
                for m in context_msgs[:-1]:  # all except the final customer message
                    author = "CUSTOMER" if m["inbound"] else "BRAND"
                    f.write(f"> [{author}] {m['text']}\n")
                f.write("\n")
                
            f.write("**Customer Message (To classify):**\n")
            f.write(f"> {pair['customer_text']}\n\n")
            
            f.write("**SpotifyCares Response (For reference):**\n")
            f.write(f"> {pair['brand_text']}\n\n")
            
            f.write("---\n\n")

    print(f"Saved discovery sample to {out_path}")

if __name__ == "__main__":
    main()
