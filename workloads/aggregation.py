from workloads.traversal import _percentiles, _run_latency


def run_bolt(driver_or_graph, node_ids: list[int], platform: str) -> dict:
    is_falkor = hasattr(driver_or_graph, "query")

    def execute(q: str, nid: int):
        if is_falkor:
            driver_or_graph.query(q, {"id": nid})
        else:
            with driver_or_graph.session() as s:
                s.run(q, id=nid).consume()

    queries = {
        "count_follows": "MATCH (:User {id: $id})-[r:FOLLOWS]->() RETURN count(r) AS cnt",
        "count_followers": "MATCH ()-[r:FOLLOWS]->(:User {id: $id}) RETURN count(r) AS cnt",
    }

    results = {}
    for label, query in queries.items():
        print(f"  [{platform}] aggregation {label} ...")
        results[label] = _percentiles(_run_latency(lambda nid, q=query: execute(q, nid), node_ids))

    return results


def run_arangodb(db, node_ids: list[int]) -> dict:
    queries = {
        "count_follows": "RETURN LENGTH(FOR e IN follows FILTER e._from == CONCAT('users/', @id) RETURN 1)",
        "count_followers": "RETURN LENGTH(FOR e IN follows FILTER e._to == CONCAT('users/', @id) RETURN 1)",
    }

    results = {}
    for label, query in queries.items():
        print(f"  [arangodb] aggregation {label} ...")
        results[label] = _percentiles(
            _run_latency(lambda nid, q=query: list(db.aql.execute(q, bind_vars={"id": str(nid)})), node_ids)
        )

    return results
