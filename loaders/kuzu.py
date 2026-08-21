import csv
import json
import os
import time
from pathlib import Path

import kuzu

DATA_DIR = Path(__file__).parent.parent / "data"
DB_PATH = Path(__file__).parent.parent / "data" / "kuzu_db"


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


def run(dry_run: bool = False) -> dict:
    import shutil

    print("[kuzu] Initializing ...")

    if DB_PATH.exists():
        shutil.rmtree(DB_PATH)

    db = get_db()
    conn = get_conn(db)

    nodes_csv = DATA_DIR / "nodes.csv"
    edges_csv = DATA_DIR / "edges.csv"

    with open(nodes_csv) as f:
        node_count = sum(1 for _ in csv.DictReader(f))
    with open(edges_csv) as f:
        edge_count = sum(1 for _ in csv.DictReader(f))

    print(f"[kuzu] {node_count:,} nodes | {edge_count:,} edges")

    if dry_run:
        print("[kuzu] dry-run: OK")
        return {}

    setup_schema(conn)

    nodes_path = str(nodes_csv).replace("\\", "/")
    edges_path = str(edges_csv).replace("\\", "/")

    print("[kuzu] Loading nodes via COPY FROM ...")
    t0 = time.perf_counter()
    conn.execute(f"COPY User FROM '{nodes_path}' (header=true)")
    t_nodes = time.perf_counter() - t0

    print("[kuzu] Loading edges via COPY FROM ...")
    t1 = time.perf_counter()
    conn.execute(
        f"COPY FOLLOWS FROM '{edges_path}' "
        f"(header=true, from='source_id', to='target_id')"
    )
    t_edges = time.perf_counter() - t1

    return {
        "platform": "kuzu",
        "load": {
            "node_count": node_count,
            "edge_count": edge_count,
            "node_load_sec": round(t_nodes, 3),
            "edge_load_sec": round(t_edges, 3),
            "nodes_per_sec": round(node_count / t_nodes, 1),
            "edges_per_sec": round(edge_count / t_edges, 1),
            "total_load_sec": round(t_nodes + t_edges, 3),
        },
    }


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    print(json.dumps(run(dry_run=args.dry_run), indent=2))
