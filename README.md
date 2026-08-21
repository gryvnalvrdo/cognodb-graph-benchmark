# CognoDB Graph Database Benchmark

A reproducible performance benchmark comparing **CognoDB Cloud** against three other managed graph database platforms — Neo4j AuraDB, Memgraph Cloud, and ArangoDB Oasis — on the same dataset and the same query workloads.

---

## Motivation

Graph databases are a competitive, rapidly-evolving space. Vendors make strong performance claims, but published benchmarks are almost always vendor-funded, proprietary, or run on non-comparable hardware. This project takes a different approach: treat every platform as a black box, use a real publicly-available social graph dataset, and measure what actually matters in production — ingest throughput, query latency at percentile level, and concurrent read/write capacity.

The four platforms represent meaningfully different architectural points:

- **CognoDB** — the platform under evaluation; disk-based, Bolt+Cypher
- **Neo4j AuraDB** — the dominant Cypher-native cloud database; best apples-to-apples comparison
- **Memgraph Cloud** — in-memory Cypher engine; tests the in-memory vs disk trade-off
- **ArangoDB Oasis** — multi-model, disk-based, uses AQL; tests protocol and query-language overhead

---

## Platform 5 — Attempted, Not Included

The assignment specification requested a fifth platform from either **FalkorDB Cloud** or **TigerGraph Cloud Starter**. Both were attempted and both failed for documented, reproducible reasons:

### FalkorDB Cloud

- **URL**: https://app.falkordb.com
- **Outcome**: The signup page was unreachable from the test region (Southeast Asia / AWS ap-southeast-1). HTTP requests timed out consistently. Attempted from two different browsers (Chrome, incognito) and a mobile hotspot. No response within a 30-second window.
- **Evidence**: Connection timeout — `requests.get("https://app.falkordb.com", timeout=30)` never returned.

### TigerGraph Savanna (tgcloud.io)

- **URL**: https://savanna.tgcloud.io
- **Account 1**: Registered with Google SSO (`gryvnalvrdo@gmail.com`). TigerGraph Savanna 4.2.2 uses OIDC/OAuth2 when authenticated via Google. The pyTigerGraph 2.0.4 client uses the legacy REST++ `createSecret()` → `getToken()` flow, which calls `/restpp/requesttoken`. On Savanna 4.2.2, this endpoint returns HTTP 400 (Tomcat bad request) regardless of request format (GET query param, POST JSON, POST form). Confirmed by exhaustive testing of all documented pyTigerGraph auth methods.
- **Account 2**: Registered with email/password (`alverdogryven@gmail.com`, to avoid the Google SSO issue). `createSecret()` still returned `('User authentication failed', None)`. The Bolt port (7687) for openCypher connectivity was tested — connection timed out after 60 seconds, indicating port 7687 is not publicly exposed by the Savanna proxy.
- **Evidence**: 
  ```
  conn = tg.TigerGraphConnection(host=HOST, graphname="BenchmarkGraph",
                                  username=USER, password=PASSWORD, tgCloud=True)
  conn.createSecret()
  # → ('User authentication failed', None)
  ```
  ```
  # Bolt port test
  GraphDatabase.driver("bolt://HOST:7687", auth=(USER, PASSWORD))
  # → Connection timed out after 60s (port not exposed)
  ```

### Dgraph Cloud

- **URL**: https://cloud.dgraph.io
- **Outcome**: Signup page unreachable from the test region. Same timeout behavior as FalkorDB.

### Decision

Proceeding with four platforms. Four fully instrumented, reproducible data points is more honest and more useful than forcing a fifth platform with a broken or simulated connection. The benchmark remains a valid comparison of the four accessible managed graph databases.

---

## Dataset

**soc-Slashdot0811** — Stanford Network Analysis Project (SNAP)

| Property | Value |
|---|---|
| Source | https://snap.stanford.edu/data/soc-Slashdot0811.html |
| Nodes | 77,360 |
| Edges | 905,468 |
| Type | Directed social graph (Slashdot user friend/foe network, Nov 2008) |
| Node attributes | ID only — no rich properties (noted as a caveat) |

`data/fetch_and_convert.py` downloads directly from SNAP and converts to:
- `data/nodes.csv` — unique node IDs
- `data/edges.csv` — `source_id, target_id` pairs

---

## Platform Specifications

| Platform | Engine | Query Language | Deployment | Free Tier Specs |
|---|---|---|---|---|
| **CognoDB Cloud** | Disk-based | Cypher (Bolt) | Managed cloud | 0.5 vCPU · 256 MB RAM · 1 GB disk |
| **Neo4j AuraDB** | Disk-based | Cypher (Bolt) | Managed cloud | 1 vCPU · 256 MB RAM |
| **Memgraph Cloud** | In-memory | Cypher (Bolt) | Managed cloud | Trial instance |
| **ArangoDB Oasis** | Disk-based (multi-model) | AQL (HTTP) | Managed cloud | 14-day trial |

> **Honest caveat on hardware heterogeneity:** Free-tier specs are not identical across vendors. Observed performance differences are partially attributable to infrastructure. Specs are documented as-advertised above.

---

## Architecture & Design Decisions

### Why one shared Bolt driver for three platforms?

CognoDB, Neo4j AuraDB, and Memgraph all implement the **Bolt binary protocol** with Cypher. A single `loaders/driver_bolt.py` module serves all three. Query equivalence is auditable at a glance and there is no copy-paste drift.

### Why AQL for ArangoDB instead of adapting Cypher?

ArangoDB does not natively speak Cypher. AQL expresses graph traversals differently (`FOR v IN 1..N OUTBOUND ...` vs `MATCH ()-[:REL*1..N]->()`). The AQL versions in `workloads/` are **logically equivalent** to the Cypher versions and placed side-by-side so the equivalence can be verified manually.

### Why `time.perf_counter()` instead of `datetime.now()`?

`perf_counter` uses the highest-resolution timer available on the OS. `datetime.now()` has platform-dependent resolution (typically 1ms on Windows) that would distort p50/p95 distributions at fast query latencies.

### Why UNWIND batching for loading?

Issuing one query per node or edge is network-bound for cloud platforms. UNWIND-based batching sends N operations per round-trip, dramatically reducing load time. Batch sizes are tuned per platform.

### Why p50 and p95 instead of averages?

Averages mask tail latency. A database that answers 99% of queries in 5ms but occasionally takes 5 seconds looks fine on average. p95 captures the worst-case experience for roughly 1 in 20 queries — a more operationally meaningful signal.

### Why 80/20 read/write split in the mixed workload?

Real-world social graph workloads are read-heavy. An 80% read / 20% write ratio approximates YCSB Workload B. It stresses lock management and connection pool behavior without being a pure read benchmark.

---

## Workloads

| Workload | Description | Metric |
|---|---|---|
| **Ingest** | Bulk load all nodes then all edges | nodes/sec, edges/sec, total wall-clock seconds |
| **Traversal** | 1-hop, 2-hop, 3-hop outbound neighbor expansion from 100 random start nodes | p50 & p95 latency (ms) |
| **Lookup** | Point lookup by ID + filtered neighbor count | p50 & p95 latency (ms) |
| **Aggregation** | Count outgoing and incoming edges per node | p50 & p95 latency (ms) |
| **Mixed** | Concurrent 80% reads / 20% writes at 1, 10, 40 clients | sustained QPS per concurrency level |

All read workloads run **10 warmup iterations** before **100 measured iterations**.

---

## Repository Structure

```
data/
  fetch_and_convert.py    Download SNAP dataset and convert to CSV
loaders/
  driver_bolt.py          Shared Bolt+Cypher driver (CognoDB / Neo4j / Memgraph)
  cognodb.py              CognoDB Cloud loader
  neo4j.py                Neo4j AuraDB loader
  memgraph.py             Memgraph Cloud loader
  arangodb.py             ArangoDB Oasis loader (AQL)
workloads/
  traversal.py            1/2/3-hop traversal — Cypher + AQL variants
  lookup.py               Point and filtered lookup
  aggregation.py          Count / group-by aggregations
  mixed.py                Concurrent mixed read/write
harness/
  run_benchmark.py        Orchestrator — load + workloads + emit results JSON
scripts/
  generate_charts.py      PNG charts from results JSON
  generate_tables.py      Markdown tables for README
results/                  Raw JSON outputs + charts (generated, not committed)
.env.example              Required environment variables (no secrets)
requirements.txt          Pinned Python dependencies
```

---

## Results

> **Results will be updated after all benchmark runs complete.**

### Data Loading Throughput

| Platform | Nodes/sec | Edges/sec | Total Load Time |
|---|---|---|---|
| CognoDB | — | — | — |
| Neo4j AuraDB | — | — | — |
| Memgraph Cloud | — | — | — |
| ArangoDB Oasis | — | — | — |

### Traversal Latency — p50 / p95 (ms)

| Platform | 1-hop p50 | 1-hop p95 | 2-hop p50 | 2-hop p95 | 3-hop p50 | 3-hop p95 |
|---|---|---|---|---|---|---|
| CognoDB | — | — | — | — | — | — |
| Neo4j AuraDB | — | — | — | — | — | — |
| Memgraph Cloud | — | — | — | — | — | — |
| ArangoDB Oasis | — | — | — | — | — | — |

### Lookup Latency — p50 / p95 (ms)

| Platform | Point Lookup p50 | Point Lookup p95 | Filtered p50 | Filtered p95 |
|---|---|---|---|---|
| CognoDB | — | — | — | — |
| Neo4j AuraDB | — | — | — | — |
| Memgraph Cloud | — | — | — | — |
| ArangoDB Oasis | — | — | — | — |

### Mixed Workload Throughput (QPS)

| Platform | 1 client | 10 clients | 40 clients |
|---|---|---|---|
| CognoDB | — | — | — |
| Neo4j AuraDB | — | — | — |
| Memgraph Cloud | — | — | — |
| ArangoDB Oasis | — | — | — |

---

## Reproduction

### Requirements

- Python 3.11+
- Free-tier accounts on: CognoDB, Neo4j AuraDB, Memgraph Cloud, ArangoDB Oasis

### Setup

```bash
git clone https://github.com/gryvnalvrdo/cognodb-graph-benchmark
cd cognodb-graph-benchmark

python -m venv venv
source venv/bin/activate      # Windows: venv\Scripts\Activate.ps1
pip install -r requirements.txt

cp .env.example .env
# Edit .env — fill in credentials for all four platforms
```

### Download Dataset

```bash
python data/fetch_and_convert.py
```

### Verify Connectivity

```bash
python harness/run_benchmark.py --platform cognodb --dry-run
python harness/run_benchmark.py --platform neo4j --dry-run
python harness/run_benchmark.py --platform memgraph --dry-run
python harness/run_benchmark.py --platform arangodb --dry-run
```

### Run Benchmark

```bash
python harness/run_benchmark.py --platform cognodb
python harness/run_benchmark.py --platform neo4j
python harness/run_benchmark.py --platform memgraph
python harness/run_benchmark.py --platform arangodb
```

Use `--skip-load` if data is already loaded:

```bash
python harness/run_benchmark.py --platform cognodb --skip-load
```

### Generate Output

```bash
python scripts/generate_charts.py   # → results/charts/*.png
python scripts/generate_tables.py   # → results/tables.md
```

---

## Caveats

- **Only four platforms benchmarked:** FalkorDB Cloud, TigerGraph Savanna, and Dgraph Cloud were all attempted and failed. Full documentation is in the "Platform 5 — Attempted, Not Included" section above.
- **Hardware heterogeneity:** Free-tier specs differ across vendors. Performance gaps reflect both engine capability and infrastructure.
- **Network variance:** All cloud timings include the client-to-server round-trip. Cloud latency is non-deterministic; percentile reporting mitigates but does not eliminate this noise.
- **No node attributes:** soc-Slashdot0811 contains no node properties beyond the ID. Filtered lookups test structural traversal, not property index performance.
- **Query language parity:** Cypher (Bolt platforms) and AQL (ArangoDB) express equivalent traversals with different syntax. Logical equivalence was verified by comparing result sets on a sample, but language-level optimizer differences remain a confounding variable.
- **GIL contention (mixed workload):** Python's Global Interpreter Lock limits true CPU parallelism in threaded workloads. At 40 clients, throughput may be bottlenecked by the Python client rather than the database. This is consistent across all platforms and therefore a fair relative comparison.
- **Memgraph self-signed certificate:** Memgraph Cloud uses a self-signed TLS certificate. The Bolt driver is configured with `bolt+ssc://` to accept it. This is a known Memgraph Cloud configuration requirement.

---

## Dependencies

| Package | Version | Purpose |
|---|---|---|
| `neo4j` | 5.22.0 | Bolt driver for CognoDB, Neo4j, Memgraph |
| `python-arango` | 8.1.3 | ArangoDB HTTP/AQL driver |
| `numpy` | 2.0.2 | Percentile computation |
| `pandas` | 2.2.3 | Result aggregation |
| `matplotlib` | 3.9.2 | Chart generation |
| `seaborn` | 0.13.2 | Chart styling |
| `python-dotenv` | 1.0.1 | Environment variable loading |
| `tqdm` | 4.66.5 | Progress reporting |
| `requests` | 2.32.3 | HTTP utilities |
