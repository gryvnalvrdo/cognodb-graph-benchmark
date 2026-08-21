import random
import time

import numpy as np
from neo4j.exceptions import ServiceUnavailable, SessionExpired
from typing import Callable

WARMUP_ITERATIONS = 10
BENCH_ITERATIONS = 100
MAX_RETRIES = 2
RETRY_DELAY_SEC = 1.0


def _percentiles(latencies_ms: list[float]) -> dict:
    if not latencies_ms:
        return {
            "p50_ms": None,
            "p95_ms": None,
            "mean_ms": None,
            "min_ms": None,
            "max_ms": None,
            "iterations": 0,
            "note": "all iterations failed (likely memory limit exceeded)",
        }
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
        try:
            fn(random.choice(node_ids))
        except Exception:
            pass

    latencies = []
    failed = 0
    for _ in range(BENCH_ITERATIONS):
        node_id = random.choice(node_ids)
        for attempt in range(MAX_RETRIES):
            try:
                t0 = time.perf_counter()
                fn(node_id)
                latencies.append((time.perf_counter() - t0) * 1000)
                break
            except Exception:
                if attempt < MAX_RETRIES - 1:
                    time.sleep(RETRY_DELAY_SEC)
                else:
                    failed += 1
    if failed > 0:
        print(f"    warning: {failed}/{BENCH_ITERATIONS} iterations failed (connection dropped)")
    return latencies


def run_bolt(driver, node_ids: list[int], platform: str) -> dict:
    def execute(q: str, node_id: int):
        with driver.session() as s:
            s.run(q, id=node_id).consume()

    queries = {
        "1_hop": "MATCH (:User {id: $id})-[:FOLLOWS]->(n) RETURN n LIMIT 500",
        "2_hop": "MATCH (:User {id: $id})-[:FOLLOWS*1..2]->(n) RETURN n LIMIT 100",
        "3_hop": "MATCH (:User {id: $id})-[:FOLLOWS*1..3]->(n) RETURN n LIMIT 25",
    }

    results = {}
    for hop_label, query in queries.items():
        print(f"  [{platform}] traversal {hop_label} ...")
        results[hop_label] = _percentiles(
            _run_latency(lambda nid, q=query: execute(q, nid), node_ids)
        )

    return results


def run_arangodb(db, node_ids: list[int]) -> dict:
    aql_queries = {
        "1_hop": "FOR v IN 1..1 OUTBOUND CONCAT('users/', @id) follows LIMIT 500 RETURN v",
        "2_hop": "FOR v IN 1..2 OUTBOUND CONCAT('users/', @id) follows LIMIT 500 RETURN v",
        "3_hop": "FOR v IN 1..3 OUTBOUND CONCAT('users/', @id) follows LIMIT 200 RETURN v",
    }

    results = {}
    for hop_label, query in aql_queries.items():
        print(f"  [arangodb] traversal {hop_label} ...")
        results[hop_label] = _percentiles(
            _run_latency(
                lambda nid, q=query: list(db.aql.execute(q, bind_vars={"id": str(nid)})),
                node_ids,
            )
        )

    return results
