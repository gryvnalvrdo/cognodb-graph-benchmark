import argparse
import csv
import json
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

sys.path.insert(0, str(Path(__file__).parent.parent))
from loaders.driver_bolt import create_indexes, get_driver, load_edges_batch, load_nodes_batch

DATA_DIR = Path(__file__).parent.parent / "data"


def run(dry_run: bool = False) -> dict:
    print("[memgraph] Connecting ...")
    driver = get_driver("MEMGRAPH")

    with open(DATA_DIR / "nodes.csv") as f:
        nodes = [int(row["id"]) for row in csv.DictReader(f)]
    with open(DATA_DIR / "edges.csv") as f:
        edges = [(int(r["source_id"]), int(r["target_id"])) for r in csv.DictReader(f)]

    print(f"[memgraph] {len(nodes):,} nodes | {len(edges):,} edges")

    if dry_run:
        print("[memgraph] dry-run: connectivity OK")
        driver.close()
        return {}

    create_indexes(driver)
    t_nodes = load_nodes_batch(driver, nodes)
    t_edges = load_edges_batch(driver, edges)
    driver.close()

    return {
        "platform": "memgraph",
        "load": {
            "node_count": len(nodes),
            "edge_count": len(edges),
            "node_load_sec": round(t_nodes, 3),
            "edge_load_sec": round(t_edges, 3),
            "nodes_per_sec": round(len(nodes) / t_nodes, 1),
            "edges_per_sec": round(len(edges) / t_edges, 1),
            "total_load_sec": round(t_nodes + t_edges, 3),
        },
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    print(json.dumps(run(dry_run=args.dry_run), indent=2))
