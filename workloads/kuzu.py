import random
import threading
import time
from typing import Callable

import kuzu
import numpy as np

from loaders.kuzu import get_db, get_conn

WARMUP_ITERATIONS = 10
BENCH_ITERATIONS = 100


def _percentiles(latencies_ms: list[float]) -> dict:
    arr = np.array(latencies_ms)
    return {
        "p50_ms": round(float(np.percentile(arr, 50)), 3),
        "p95_ms": round(float(np.percentile(arr, 95)), 3),
        "mean_ms": round(float(np.mean(arr)), 3),
        "min_ms": round(float(np.min(arr)), 3),
        "max_ms": round(float(np.max(arr)), 3),
        "iterations": len(latencies_ms),
    }


def _run_latency(fn: Callable, node_ids: list[int]) -> list[float]:
    for _ in range(WARMUP_ITERATIONS):
        fn(random.choice(node_ids))
    latencies = []
    for _ in range(BENCH_ITERATIONS):
        nid = random.choice(node_ids)
        t0 = time.perf_counter()
        fn(nid)
        latencies.append((time.perf_counter() - t0) * 1000)
    return latencies


def run_traversal(db, node_ids: list[int]) -> dict:
    queries = {
        "1_hop": "MATCH (:User {id: $id})-[:FOLLOWS]->(n:User) RETURN n.id LIMIT 1000",
        "2_hop": "MATCH (:User {id: $id})-[:FOLLOWS*1..2]->(n:User) RETURN n.id LIMIT 1000",
        "3_hop": "MATCH (:User {id: $id})-[:FOLLOWS*1..3]->(n:User) RETURN n.id LIMIT 1000",
    }

    results = {}
    for label, q in queries.items():
        print(f"  [kuzu] traversal {label} ...")
        conn = get_conn(db)

        def fn(nid, query=q, c=conn):
            c.execute(query, {"id": nid}).get_as_df()

        results[label] = _percentiles(_run_latency(fn, node_ids))
    return results


def run_lookup(db, node_ids: list[int]) -> dict:
    results = {}
    conn = get_conn(db)

    def point_lookup(nid):
        conn.execute("MATCH (n:User {id: $id}) RETURN n.id", {"id": nid}).get_as_df()

    def filtered_lookup(nid):
        conn.execute(
            "MATCH (:User {id: $id})-[:FOLLOWS]->(n:User) WHERE n.id > $id RETURN count(n)",
            {"id": nid},
        ).get_as_df()

    for label, fn in [("point_lookup", point_lookup), ("filtered_lookup", filtered_lookup)]:
        print(f"  [kuzu] lookup {label} ...")
        results[label] = _percentiles(_run_latency(fn, node_ids))
    return results


def run_aggregation(db, node_ids: list[int]) -> dict:
    results = {}
    conn = get_conn(db)

    def count_follows(nid):
        conn.execute(
            "MATCH (:User {id: $id})-[:FOLLOWS]->(n:User) RETURN count(n)",
            {"id": nid},
        ).get_as_df()

    def count_followers(nid):
        conn.execute(
            "MATCH (n:User)-[:FOLLOWS]->(:User {id: $id}) RETURN count(n)",
            {"id": nid},
        ).get_as_df()

    for label, fn in [("count_follows", count_follows), ("count_followers", count_followers)]:
        print(f"  [kuzu] aggregation {label} ...")
        results[label] = _percentiles(_run_latency(fn, node_ids))
    return results


def _worker(db, node_ids: list[int], duration_sec: int, results: list):
    conn = get_conn(db)
    count = 0
    deadline = time.perf_counter() + duration_sec
    while time.perf_counter() < deadline:
        nid = random.choice(node_ids)
        if random.random() < 0.8:
            conn.execute(
                "MATCH (:User {id: $id})-[:FOLLOWS]->(n:User) RETURN n.id LIMIT 100",
                {"id": nid},
            ).get_as_df()
        else:
            conn.execute(
                "MATCH (n:User {id: $id}) SET n.id = n.id",
                {"id": nid},
            )
        count += 1
    results.append(count)


def run_mixed(db, node_ids: list[int]) -> dict:
    sweep = []
    for c in [1, 10, 40]:
        print(f"  [kuzu] mixed concurrency={c} ...")
        res_list = []
        threads = [threading.Thread(target=_worker, args=(db, node_ids, 30, res_list)) for _ in range(c)]
        t0 = time.perf_counter()
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        elapsed = time.perf_counter() - t0
        sweep.append({
            "concurrency": c,
            "total_ops": sum(res_list),
            "duration_sec": round(elapsed, 2),
            "qps": round(sum(res_list) / elapsed, 2),
        })
    return {"concurrency_sweep": sweep}
