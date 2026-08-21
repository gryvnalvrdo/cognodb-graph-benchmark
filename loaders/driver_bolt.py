import os
import time
from neo4j import GraphDatabase, Driver


def get_driver(platform: str, retries: int = 5, delay_sec: float = 10.0) -> Driver:
    prefix = platform.upper()
    uri = os.environ[f"{prefix}_URI"]
    user = os.environ[f"{prefix}_USER"]
    password = os.environ[f"{prefix}_PASSWORD"]

    for attempt in range(retries):
        try:
            driver = GraphDatabase.driver(uri, auth=(user, password))
            driver.verify_connectivity()
            return driver
        except Exception as e:
            if attempt < retries - 1:
                print(f"[{platform}] Connection attempt {attempt + 1} failed, retrying in {delay_sec}s ...")
                time.sleep(delay_sec)
            else:
                raise


def create_indexes(driver: Driver) -> None:
    with driver.session() as session:
        session.run("CREATE INDEX user_id IF NOT EXISTS FOR (u:User) ON (u.id)")


def load_nodes_batch(driver: Driver, node_ids: list[int], batch_size: int = 1000) -> float:
    start = time.perf_counter()
    for i in range(0, len(node_ids), batch_size):
        batch = [{"id": nid} for nid in node_ids[i : i + batch_size]]
        with driver.session() as session:
            session.run("UNWIND $rows AS row MERGE (u:User {id: row.id})", rows=batch)
    return time.perf_counter() - start


def load_edges_batch(driver: Driver, edges: list[tuple[int, int]], batch_size: int = 500) -> float:
    start = time.perf_counter()
    for i in range(0, len(edges), batch_size):
        batch = [{"src": s, "dst": d} for s, d in edges[i : i + batch_size]]
        with driver.session() as session:
            session.run(
                "UNWIND $rows AS row "
                "MATCH (a:User {id: row.src}), (b:User {id: row.dst}) "
                "MERGE (a)-[:FOLLOWS]->(b)",
                rows=batch,
            )
    return time.perf_counter() - start
