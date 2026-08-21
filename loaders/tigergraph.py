import csv
import json
import os
import time
from pathlib import Path

import pyTigerGraph as tg
from dotenv import load_dotenv

load_dotenv()

DATA_DIR = Path(__file__).parent.parent / "data"
BATCH_SIZE = 500


def get_conn():
    host = os.environ["TIGERGRAPH_HOST"]
    user = os.environ["TIGERGRAPH_USER"]
    password = os.environ["TIGERGRAPH_PASSWORD"]
    graph = os.environ.get("TIGERGRAPH_GRAPH", "BenchmarkGraph")

    conn = tg.TigerGraphConnection(
        host=host,
        graphname=graph,
        username=user,
        password=password,
        tgCloud=True,
        useCert=True,
    )
    secret = conn.createSecret()
    token = conn.getToken(secret)
    conn.apiToken = token[0] if isinstance(token, (list, tuple)) else token
    return conn


def setup_schema(conn) -> None:
    graph = os.environ.get("TIGERGRAPH_GRAPH", "BenchmarkGraph")
    try:
        conn.gsql(
            f"USE GRAPH {graph}\n"
            "CREATE VERTEX User (PRIMARY_ID id INT, id INT) "
            'WITH primary_id_as_attribute="TRUE"\n'
            "CREATE DIRECTED EDGE FOLLOWS (FROM User, TO User)\n"
            f"ADD VERTEX User, EDGE FOLLOWS TO GRAPH {graph}"
        )
    except Exception as e:
        print(f"[tigergraph] schema note: {e}")


def load_nodes(conn, node_ids: list[int]) -> float:
    start = time.perf_counter()
    for i in range(0, len(node_ids), BATCH_SIZE):
        batch = {str(nid): {"id": nid} for nid in node_ids[i : i + BATCH_SIZE]}
        conn.upsertVertices("User", batch)
    return time.perf_counter() - start


def load_edges(conn, edges: list[tuple[int, int]]) -> float:
    start = time.perf_counter()
    for i in range(0, len(edges), BATCH_SIZE):
        batch = [(str(s), str(d), {}) for s, d in edges[i : i + BATCH_SIZE]]
        conn.upsertEdges("User", "FOLLOWS", "User", batch)
    return time.perf_counter() - start


def run(dry_run: bool = False) -> dict:
    print("[tigergraph] Connecting ...")
    conn = get_conn()

    with open(DATA_DIR / "nodes.csv") as f:
        nodes = [int(row["id"]) for row in csv.DictReader(f)]
    with open(DATA_DIR / "edges.csv") as f:
        edges = [(int(r["source_id"]), int(r["target_id"])) for r in csv.DictReader(f)]

    print(f"[tigergraph] {len(nodes):,} nodes | {len(edges):,} edges")

    if dry_run:
        print("[tigergraph] dry-run: connectivity OK")
        return {}

    setup_schema(conn)
    t_nodes = load_nodes(conn, nodes)
    t_edges = load_edges(conn, edges)

    return {
        "platform": "tigergraph",
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
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    print(json.dumps(run(dry_run=args.dry_run), indent=2))
