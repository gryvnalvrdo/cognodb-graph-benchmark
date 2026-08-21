import csv
import random
from pathlib import Path

DATA_DIR = Path(__file__).parent
TARGET_NODE_SAMPLE = 28000  # ~0.36 fraction of 77,360 -> ~130k edges retained

def trim():
    with open(DATA_DIR / "nodes.csv") as f:
        all_ids = [int(row["id"]) for row in csv.DictReader(f)]

    sample_ids = set(random.sample(all_ids, min(TARGET_NODE_SAMPLE, len(all_ids))))

    kept_edges = []
    with open(DATA_DIR / "edges.csv") as f:
        for row in csv.DictReader(f):
            src, dst = int(row["source_id"]), int(row["target_id"])
            if src in sample_ids and dst in sample_ids:
                kept_edges.append((src, dst))

    with open(DATA_DIR / "nodes_sample.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["id"])
        w.writerows([[i] for i in sorted(sample_ids)])

    with open(DATA_DIR / "edges_sample.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["source_id", "target_id"])
        w.writerows(kept_edges)

    print(f"Sampled {len(sample_ids)} nodes, {len(kept_edges)} edges "
          f"(target range: 100k-500k)")

if __name__ == "__main__":
    trim()