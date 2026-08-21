import csv
import json
import os
import time
from pathlib import Path

import pyTigerGraph as tg
from dotenv import load_dotenv

load_dotenv()

DATA_DIR = Path(__file__).parent.parent / "data"
BATCH_SIZE = 1000
GRAPH_NAME = "BenchmarkGraph"


def get_conn():
    conn = tg.TigerGraphConnection(
        host=os.environ["TIGERGRAPH_HOST"],
        graphname=GRAPH_NAME,
        username=os.environ["TIGERGRAPH_USER"],
        password=os.environ["TIGERGRAPH_PASSWORD"],
    )
    conn.getToken(conn.createSecret())
    return conn


def setup_schema(conn) -> None:
    schema_gsql = f"""
    USE GLOBAL
    CREATE VERTEX User (PRIMARY_ID id INT, id INT) WITH primary_id_as_attribute="TRUE"
    CREATE DIRECTED EDGE FOLLOWS (FROM User, TO User)
    CREATE GRAPH {GRAPH_NAME} (User, FOLLOWS)
    """
    try:
        conn.gsql(schema_gsql)
    except Exception:
        pass

    index_gsql = f"USE GRAPH {GRAPH_NAME}\nCREATE INDEX user_id_idx ON Vertex User(id)"
    try:
        conn.gsql(index_gsql)
    except Exception:
        pass


def load_nodes(conn, node_ids: list[int]) -> float:
    start = time.perf_counter()
    for i in range(0, len(node_ids), BATCH_SIZE):
        batch = {str(nid): {"id": nid} for nid in node_ids[i : i + BATCH_SIZE]}
        conn.upsertVertices("User", batch)
    return time.perf_counter() - start


def load_edges(conn, edges: list[tuple[int, int]]) -> float:
    start = time.perf_counter()
    for i in range(0, len(edges), BATCH_SIZE):
        batch = edges[i : i + BATCH_SIZE]
        edge_data = [(str(s), str(d), {}) for s, d in batch]
        conn.upsertEdges("User", "FOLLOWS", "User", edge_data)
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
