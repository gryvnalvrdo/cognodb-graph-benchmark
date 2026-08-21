import random
import threading
import time
from typing import Callable

import numpy as np

WARMUP_ITERATIONS = 10
BENCH_ITERATIONS = 100
GRAPH_NAME = "BenchmarkGraph"


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


def _cypher(conn, query: str, params: dict):
    conn.runInterpretedQuery(f"USE GRAPH {GRAPH_NAME}\nINTERPRET QUERY () {{\n{query}\n}}", params)


def run_traversal(conn, node_ids: list[int]) -> dict:
    queries = {
        "1_hop": "MATCH (:User {id: @id})-[:FOLLOWS]->(n) RETURN n LIMIT 1000",
        "2_hop": "MATCH (:User {id: @id})-[:FOLLOWS*1..2]->(n) RETURN n LIMIT 1000",
        "3_hop": "MATCH (:User {id: @id})-[:FOLLOWS*1..3]->(n) RETURN n LIMIT 1000",
    }

    results = {}
    for label, q in queries.items():
        print(f"  [tigergraph] traversal {label} ...")
        results[label] = _percentiles(
            _run_latency(lambda nid, cyq=q: conn.runInstalledQuery(
                "runInterpretedQuery", {"query": cyq, "id": nid}
            ), node_ids)
        )
    return results


def run_lookup(conn, node_ids: list[int]) -> dict:
    def point_lookup(nid):
        conn.getVerticesById("User", [str(nid)])

    def filtered_lookup(nid):
        conn.runInterpretedQuery(
            f"USE GRAPH {GRAPH_NAME}\nINTERPRET QUERY () {{\n"
            f"  Seed = {{User.*}};\n"
            f"  Nbrs = SELECT t FROM Seed:s-(FOLLOWS:e)->User:t WHERE s.id == {nid} AND t.id > {nid} LIMIT 1000;\n"
            f"  PRINT Nbrs.size();\n}}"
        )

    results = {}
    for label, fn in [("point_lookup", point_lookup), ("filtered_lookup", filtered_lookup)]:
        print(f"  [tigergraph] lookup {label} ...")
        results[label] = _percentiles(_run_latency(fn, node_ids))

    return results


def run_aggregation(conn, node_ids: list[int]) -> dict:
    def count_follows(nid):
        conn.runInterpretedQuery(
            f"USE GRAPH {GRAPH_NAME}\nINTERPRET QUERY () {{\n"
            f"  Seed = {{User.*}};\n"
            f"  Nbrs = SELECT t FROM Seed:s-(FOLLOWS:e)->User:t WHERE s.id == {nid};\n"
            f"  PRINT Nbrs.size();\n}}"
        )

    def count_followers(nid):
        conn.runInterpretedQuery(
            f"USE GRAPH {GRAPH_NAME}\nINTERPRET QUERY () {{\n"
            f"  Seed = {{User.*}};\n"
            f"  Followers = SELECT s FROM Seed:s-(FOLLOWS:e)->User:t WHERE t.id == {nid};\n"
            f"  PRINT Followers.size();\n}}"
        )

    results = {}
    for label, fn in [("count_follows", count_follows), ("count_followers", count_followers)]:
        print(f"  [tigergraph] aggregation {label} ...")
        results[label] = _percentiles(_run_latency(fn, node_ids))

    return results


def _worker(fn: Callable, node_ids: list[int], duration_sec: int, results: list):
    count = 0
    deadline = time.perf_counter() + duration_sec
    while time.perf_counter() < deadline:
        fn(random.choice(node_ids))
        count += 1
    results.append(count)


def run_mixed(conn, node_ids: list[int]) -> dict:
    def read_fn(nid):
        conn.runInterpretedQuery(
            f"USE GRAPH {GRAPH_NAME}\nINTERPRET QUERY () {{\n"
            f"  Seed = {{User.*}};\n"
            f"  Hop1 = SELECT t FROM Seed:s-(FOLLOWS:e)->User:t WHERE s.id == {nid} LIMIT 100;\n"
            f"  PRINT Hop1;\n}}"
        )

    def write_fn(nid):
        conn.upsertVertex("User", str(nid), {"id": nid})

    def mixed_fn(nid):
        if random.random() < 0.8:
            read_fn(nid)
        else:
            write_fn(nid)

    sweep = []
    for c in [1, 10, 40]:
        print(f"  [tigergraph] mixed concurrency={c} ...")
        res_list = []
        threads = [threading.Thread(target=_worker, args=(mixed_fn, node_ids, 30, res_list)) for _ in range(c)]
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
