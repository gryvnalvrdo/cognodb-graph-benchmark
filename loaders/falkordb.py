import argparse
import csv
import json
import os
import time
from pathlib import Path

from dotenv import load_dotenv
from falkordb import FalkorDB

load_dotenv()

DATA_DIR = Path(__file__).parent.parent / "data"
BATCH_SIZE = 500


def get_graph():
    client = FalkorDB(
        host=os.environ["FALKORDB_HOST"],
        port=int(os.environ.get("FALKORDB_PORT", 6379)),
        password=os.environ.get("FALKORDB_PASSWORD"),
    )
    return client.select_graph(os.environ.get("FALKORDB_GRAPH", "benchmark"))


def create_index(graph) -> None:
    try:
        graph.query("CREATE INDEX ON :User(id)")
    except Exception:
        pass


def load_nodes(graph, node_ids: list[int]) -> float:
    start = time.perf_counter()
    for i in range(0, len(node_ids), BATCH_SIZE):
        batch = node_ids[i : i + BATCH_SIZE]
        graph.query("UNWIND $batch AS row MERGE (:User {id: row.id})", {"batch": [{"id": nid} for nid in batch]})
    return time.perf_counter() - start


def load_edges(graph, edges: list[tuple[int, int]]) -> float:
    start = time.perf_counter()
    for i in range(0, len(edges), BATCH_SIZE):
        batch = edges[i : i + BATCH_SIZE]
        graph.query(
            "UNWIND $batch AS row "
            "MATCH (a:User {id: row.src}), (b:User {id: row.dst}) "
            "MERGE (a)-[:FOLLOWS]->(b)",
            {"batch": [{"src": s, "dst": d} for s, d in batch]},
        )
    return time.perf_counter() - start


def run(dry_run: bool = False) -> dict:
    print("[falkordb] Connecting ...")
    graph = get_graph()

    with open(DATA_DIR / "nodes.csv") as f:
        nodes = [int(row["id"]) for row in csv.DictReader(f)]
    with open(DATA_DIR / "edges.csv") as f:
        edges = [(int(r["source_id"]), int(r["target_id"])) for r in csv.DictReader(f)]

    print(f"[falkordb] {len(nodes):,} nodes | {len(edges):,} edges")

    if dry_run:
        print("[falkordb] dry-run: connectivity OK")
        return {}

    create_index(graph)
    t_nodes = load_nodes(graph, nodes)
    t_edges = load_edges(graph, edges)

    return {
        "platform": "falkordb",
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
