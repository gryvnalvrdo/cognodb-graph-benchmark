import random
import time

import numpy as np
from neo4j.exceptions import ServiceUnavailable, SessionExpired
from typing import Callable

WARMUP_ITERATIONS = 10
BENCH_ITERATIONS = 100
MAX_RETRIES = 3
RETRY_DELAY_SEC = 2.0


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
        try:
            fn(random.choice(node_ids))
        except Exception:
            pass

    latencies = []
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
                    latencies.append(float("nan"))

    return [x for x in latencies if not (isinstance(x, float) and x != x)]


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
