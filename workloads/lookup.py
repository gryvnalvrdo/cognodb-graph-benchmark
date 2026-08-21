from workloads.traversal import WARMUP_ITERATIONS, BENCH_ITERATIONS, _percentiles, _run_latency


def run_bolt(driver, node_ids: list[int], platform: str) -> dict:
    def execute(q: str, nid: int):
        with driver.session() as s:
            s.run(q, id=nid).consume()

    queries = {
        "point_lookup": "MATCH (u:User {id: $id}) RETURN u",
        "filtered_lookup": "MATCH (u:User {id: $id})-[:FOLLOWS]->(n) WHERE n.id > $id RETURN count(n)",
    }

    results = {}
    for label, query in queries.items():
        print(f"  [{platform}] lookup {label} ...")
        results[label] = _percentiles(_run_latency(lambda nid, q=query: execute(q, nid), node_ids))

    return results


def run_arangodb(db, node_ids: list[int]) -> dict:
    queries = {
        "point_lookup": "RETURN DOCUMENT(CONCAT('users/', @id))",
        "filtered_lookup": "FOR v IN 1..1 OUTBOUND CONCAT('users/', @id) follows FILTER v.id > @id RETURN COUNT(v)",
    }

    results = {}
    for label, query in queries.items():
        print(f"  [arangodb] lookup {label} ...")
        results[label] = _percentiles(
            _run_latency(lambda nid, q=query: list(db.aql.execute(q, bind_vars={"id": str(nid)})), node_ids)
        )

    return results

def run_falkordb(graph, node_ids: list[int]) -> dict:
    def execute(q: str, nid: int):
        graph.query(q, {"id": nid})

    queries = {
        "point_lookup": "MATCH (u:User {id: $id}) RETURN u",
        "filtered_lookup": "MATCH (u:User {id: $id})-[:FOLLOWS]->(n) WHERE n.id > $id RETURN count(n)",
    }

    results = {}
    for label, query in queries.items():
        print(f"  [falkordb] lookup {label} ...")
        results[label] = _percentiles(_run_latency(lambda nid, q=query: execute(q, nid), node_ids))

    return results