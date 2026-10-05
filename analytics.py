import sqlite3
from collections import Counter
from scraper import DB_PATH

def compute_3digit_metrics(limit=120):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("""
        SELECT last_three_first_prize, suffix_3digits 
        FROM draws 
        WHERE last_three_first_prize IS NOT NULL 
        ORDER BY id DESC LIMIT ?
    """, (limit,))
    rows = cur.fetchall()
    conn.close()

    if not rows:
        return None

    fp_trio_list = [r[0] for r in rows if r[0] and len(r[0]) == 3]

    p1_counts = Counter([num[0] for num in fp_trio_list])
    p2_counts = Counter([num[1] for num in fp_trio_list])
    p3_counts = Counter([num[2] for num in fp_trio_list])

    top_p1 = [d for d, _ in p1_counts.most_common(3)] or ["0", "1", "2"]
    top_p2 = [d for d, _ in p2_counts.most_common(3)] or ["0", "1", "2"]
    top_p3 = [d for d, _ in p3_counts.most_common(3)] or ["0", "1", "2"]

    projected_triplets = []
    for h in top_p1:
        for t in top_p2:
            for u in top_p3:
                score = p1_counts.get(h, 0) + p2_counts.get(t, 0) + p3_counts.get(u, 0)
                projected_triplets.append((f"{h}{t}{u}", score))

    projected_triplets.sort(key=lambda x: x[1], reverse=True)

    all_suffixes = []
    for r in rows:
        if r[1]:
            all_suffixes.extend(r[1].split(","))
    suffix_counts = Counter(all_suffixes).most_common(5)

    return {
        "sample_size": len(fp_trio_list),
        "hot_combinations": [item[0] for item in projected_triplets[:5]],
        "hot_suffixes": [num for num, _ in suffix_counts],
        "positional_distribution": {
            "hundreds": dict(sorted(p1_counts.items())),
            "tens": dict(sorted(p2_counts.items())),
            "units": dict(sorted(p3_counts.items()))
        }
    }
