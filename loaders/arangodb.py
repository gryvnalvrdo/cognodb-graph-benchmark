import argparse
import csv
import json
import os
import time
from pathlib import Path

from arango import ArangoClient
from dotenv import load_dotenv

load_dotenv()

DATA_DIR = Path(__file__).parent.parent / "data"
BATCH_SIZE = 1000


def get_db():
    client = ArangoClient(hosts=os.environ["ARANGODB_URL"])
    return client.db(
        os.environ.get("ARANGODB_DB", "benchmark"),
        username=os.environ["ARANGODB_USER"],
        password=os.environ["ARANGODB_PASSWORD"],
    )


def setup_collections(db) -> None:
    if not db.has_collection("users"):
        db.create_collection("users")
        db.collection("users").add_persistent_index(fields=["id"], unique=True)
    if not db.has_collection("follows"):
        db.create_collection("follows", edge=True)


def load_nodes(db, node_ids: list[int]) -> float:
    col = db.collection("users")
    start = time.perf_counter()
    for i in range(0, len(node_ids), BATCH_SIZE):
        batch = [{"_key": str(nid), "id": nid} for nid in node_ids[i : i + BATCH_SIZE]]
        col.import_bulk(batch, on_duplicate="ignore")
    return time.perf_counter() - start


def load_edges(db, edges: list[tuple[int, int]]) -> float:
    col = db.collection("follows")
    start = time.perf_counter()
    for i in range(0, len(edges), BATCH_SIZE):
        batch = [
            {"_from": f"users/{s}", "_to": f"users/{d}"}
            for s, d in edges[i : i + BATCH_SIZE]
        ]
        col.import_bulk(batch, on_duplicate="ignore")
    return time.perf_counter() - start


def run(dry_run: bool = False) -> dict:
    print("[arangodb] Connecting ...")
    db = get_db()

    with open(DATA_DIR / "nodes.csv") as f:
        nodes = [int(row["id"]) for row in csv.DictReader(f)]
    with open(DATA_DIR / "edges.csv") as f:
        edges = [(int(r["source_id"]), int(r["target_id"])) for r in csv.DictReader(f)]

    print(f"[arangodb] {len(nodes):,} nodes | {len(edges):,} edges")

    if dry_run:
        print("[arangodb] dry-run: connectivity OK")
        return {}

    setup_collections(db)
    t_nodes = load_nodes(db, nodes)
    t_edges = load_edges(db, edges)

    return {
        "platform": "arangodb",
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
