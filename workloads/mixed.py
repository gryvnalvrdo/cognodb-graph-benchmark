import random
import threading
import time
from typing import Callable

DURATION_SEC = 30


def _worker(fn: Callable, node_ids: list[int], duration_sec: int, results: list):
    count = 0
    deadline = time.perf_counter() + duration_sec
    while time.perf_counter() < deadline:
        fn(random.choice(node_ids))
        count += 1
    results.append(count)


def _run_concurrent(read_fn: Callable, write_fn: Callable, node_ids: list[int], concurrency: int, platform: str) -> dict:
    print(f"  [{platform}] mixed concurrency={concurrency} duration={DURATION_SEC}s ...")

    def mixed_fn(nid):
        if random.random() < 0.8:
            read_fn(nid)
        else:
            write_fn(nid)

    results = []
    threads = [
        threading.Thread(target=_worker, args=(mixed_fn, node_ids, DURATION_SEC, results))
        for _ in range(concurrency)
    ]
    t0 = time.perf_counter()
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    elapsed = time.perf_counter() - t0

    return {
        "concurrency": concurrency,
        "total_ops": sum(results),
        "duration_sec": round(elapsed, 2),
        "qps": round(sum(results) / elapsed, 2),
    }


def run_bolt(driver_or_graph, node_ids: list[int], platform: str) -> dict:
    is_falkor = hasattr(driver_or_graph, "query")

    def read_fn(nid):
        if is_falkor:
            driver_or_graph.query("MATCH (:User {id: $id})-[:FOLLOWS]->(n) RETURN n LIMIT 100", {"id": nid})
        else:
            with driver_or_graph.session() as s:
                s.run("MATCH (:User {id: $id})-[:FOLLOWS]->(n) RETURN n LIMIT 100", id=nid).consume()

    def write_fn(nid):
        if is_falkor:
            driver_or_graph.query("MATCH (u:User {id: $id}) SET u.ts = timestamp() RETURN u", {"id": nid})
        else:
            with driver_or_graph.session() as s:
                s.run("MATCH (u:User {id: $id}) SET u.ts = timestamp() RETURN u", id=nid).consume()

    return {"concurrency_sweep": [_run_concurrent(read_fn, write_fn, node_ids, c, platform) for c in [1, 10, 40]]}


def run_arangodb(db, node_ids: list[int]) -> dict:
    def read_fn(nid):
        list(db.aql.execute(
            "WITH users FOR v IN 1..1 OUTBOUND CONCAT('users/', @id) follows LIMIT 100 RETURN v",
            bind_vars={"id": str(nid)},
        ))

    def write_fn(nid):
        list(db.aql.execute(
            "UPDATE @id WITH {ts: DATE_NOW()} IN users RETURN NEW",
            bind_vars={"id": str(nid)},
        ))

    return {"concurrency_sweep": [_run_concurrent(read_fn, write_fn, node_ids, c, "arangodb") for c in [1, 10, 40]]}