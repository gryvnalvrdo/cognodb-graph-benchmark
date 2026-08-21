import csv
import json
import time
from pathlib import Path

import kuzu

DATA_DIR = Path(__file__).parent.parent / "data"
DB_PATH = Path(__file__).parent.parent / "data" / "kuzu_db"
BATCH_SIZE = 5000


def get_db():
    return kuzu.Database(str(DB_PATH))


def get_conn(db=None):
    if db is None:
        db = get_db()
    return kuzu.Connection(db)


def setup_schema(conn) -> None:
    try:
        conn.execute("CREATE NODE TABLE User(id INT64, PRIMARY KEY(id))")
    except Exception:
        pass
    try:
        conn.execute("CREATE REL TABLE FOLLOWS(FROM User TO User)")
    except Exception:
        pass


def load_nodes(conn, node_ids: list[int]) -> float:
    start = time.perf_counter()
    for i in range(0, len(node_ids), BATCH_SIZE):
        batch = node_ids[i : i + BATCH_SIZE]
        params = [{"id": nid} for nid in batch]
        conn.execute("UNWIND $rows AS row CREATE (:User {id: row.id})", {"rows": params})
    return time.perf_counter() - start


def load_edges(conn, edges: list[tuple[int, int]]) -> float:
    start = time.perf_counter()
    for i in range(0, len(edges), BATCH_SIZE):
        batch = edges[i : i + BATCH_SIZE]
        params = [{"src": s, "dst": d} for s, d in batch]
        conn.execute(
            "UNWIND $rows AS row "
            "MATCH (a:User {id: row.src}), (b:User {id: row.dst}) "
            "CREATE (a)-[:FOLLOWS]->(b)",
            {"rows": params},
        )
    return time.perf_counter() - start


def run(dry_run: bool = False) -> dict:
    print("[kuzu] Initializing ...")
    db = get_db()
    conn = get_conn(db)

    with open(DATA_DIR / "nodes.csv") as f:
        nodes = [int(row["id"]) for row in csv.DictReader(f)]
    with open(DATA_DIR / "edges.csv") as f:
        edges = [(int(r["source_id"]), int(r["target_id"])) for r in csv.DictReader(f)]

    print(f"[kuzu] {len(nodes):,} nodes | {len(edges):,} edges")

    if dry_run:
        print("[kuzu] dry-run: OK")
        return {}

    setup_schema(conn)

    t_nodes = load_nodes(conn, nodes)
    t_edges = load_edges(conn, edges)

    return {
        "platform": "kuzu",
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
