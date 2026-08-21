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

GRAPH_NAME = "BenchmarkGraph"
NODE_BATCH_SIZE = 2000
EDGE_BATCH_SIZE = 2000


def get_graph():
    host = os.getenv("FALKORDB_HOST", "localhost")
    port = int(os.getenv("FALKORDB_PORT", "6379"))
    db = FalkorDB(host=host, port=port)
    return db.select_graph(GRAPH_NAME)


def create_indexes(graph):
    # Index on :User(id) -- mirrors the index used on the other Cypher platforms,
    # so point-lookup / filtered-lookup comparisons stay apples-to-apples.
    graph.query("CREATE INDEX FOR (n:User) ON (n.id)")


def load_nodes_batch(graph, nodes: list[int]) -> float:
    t0 = time.perf_counter()
    for i in range(0, len(nodes), NODE_BATCH_SIZE):
        batch = nodes[i:i + NODE_BATCH_SIZE]
        graph.query(
            "UNWIND $ids AS id CREATE (:User {id: id})",
            {"ids": batch},
        )
    return time.perf_counter() - t0


def load_edges_batch(graph, edges: list[tuple[int, int]]) -> float:
    t0 = time.perf_counter()
    for i in range(0, len(edges), EDGE_BATCH_SIZE):
        batch = edges[i:i + EDGE_BATCH_SIZE]
        pairs = [{"src": s, "dst": d} for s, d in batch]
        graph.query(
            "UNWIND $pairs AS pair "
            "MATCH (a:User {id: pair.src}), (b:User {id: pair.dst}) "
            "CREATE (a)-[:FOLLOWS]->(b)",
            {"pairs": pairs},
        )
    return time.perf_counter() - t0


def run(dry_run: bool = False) -> dict:
    print("[falkordb] Connecting ...")
    graph = get_graph()

    if dry_run:
        graph.query("RETURN 1")
        print("[falkordb] dry-run: connectivity OK")
        return {}

    with open(DATA_DIR / "nodes.csv") as f:
        nodes = [int(row["id"]) for row in csv.DictReader(f)]
    with open(DATA_DIR / "edges.csv") as f:
        edges = [(int(r["source_id"]), int(r["target_id"])) for r in csv.DictReader(f)]

    print(f"[falkordb] {len(nodes):,} nodes | {len(edges):,} edges")

    # Safety: clear any pre-existing graph with this name before loading,
    # so re-runs stay idempotent (CREATE, not MERGE, is used above for load speed).
    try:
        graph.delete()
    except Exception:
        pass
    graph = get_graph()

    create_indexes(graph)
    t_nodes = load_nodes_batch(graph, nodes)
    t_edges = load_edges_batch(graph, edges)

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