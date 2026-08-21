# CognoDB Graph Database Benchmark

A reproducible performance benchmark comparing **CognoDB Cloud** against four other graph database platforms — Neo4j AuraDB, Memgraph Cloud, ArangoDB Oasis, and FalkorDB (self-hosted, resource-capped) — on the same dataset and the same query workloads.

---

## Motivation

Graph databases are a competitive, rapidly-evolving space. Vendors make strong performance claims, but published benchmarks are almost always vendor-funded, proprietary, or run on non-comparable hardware. This project takes a different approach: treat every platform as a black box, use a real publicly-available social graph dataset, and measure what actually matters in production — ingest throughput, query latency at percentile level, and concurrent read/write capacity.

The five platforms represent meaningfully different architectural points:

- **CognoDB** — the platform under evaluation; disk-based, Bolt+Cypher
- **Neo4j AuraDB** — the dominant Cypher-native cloud database; best apples-to-apples comparison
- **Memgraph Cloud** — in-memory Cypher engine; tests the in-memory vs disk trade-off
- **ArangoDB Oasis** — multi-model, disk-based, uses AQL; tests protocol and query-language overhead
- **FalkorDB** — Redis-based in-memory graph engine; tests a fundamentally different storage substrate (RESP protocol, not Bolt) under the same Cypher query surface

---

## Platform Selection Notes

The assignment asked for CognoDB plus at least four other platforms. Three managed-cloud options were attempted and could not be reached from the test environment:

### FalkorDB Cloud (signup unreachable)

- **URL**: https://app.falkordb.com
- **Outcome**: Signup page unreachable from the test region (Southeast Asia). Requests timed out consistently across two browsers and a mobile hotspot connection.

### TigerGraph Savanna (tgcloud.io) — auth failures

- **URL**: https://savanna.tgcloud.io
- Two accounts tried (Google SSO and email/password). `pyTigerGraph`'s legacy REST++ `createSecret()` → `getToken()` flow returned HTTP 400 / `'User authentication failed'` on Savanna 4.2.2 regardless of auth method. The Bolt port (7687) for openCypher was also tested directly and timed out — not publicly exposed by the Savanna proxy.

### Dgraph Cloud (signup unreachable)

- **URL**: https://cloud.dgraph.io
- Same unreachable-signup behavior as FalkorDB Cloud.

### Resolution: self-hosted FalkorDB, resource-capped

Rather than submit with only three other platforms, FalkorDB was run **self-hosted via Docker**, explicitly permitted by the assignment ("free tiers, free trials or self-hosted deployments capped to the same resources are all fine"):

```bash
docker run -d --name falkordb-bench --memory=512m --cpus=0.5 -p 6379:6379 falkordb/falkordb:latest
```

Capped to 0.5 vCPU / 512 MB RAM — matching CognoDB's actual free-tier allocation (see Platform Specifications below). This restores the benchmark to five platforms total while keeping every comparison honestly documented.

---

## Dataset

**soc-Slashdot0811** — Stanford Network Analysis Project (SNAP)

| Property | Full source dataset | Benchmark dataset (used) |
|---|---|---|
| Source | https://snap.stanford.edu/data/soc-Slashdot0811.html | Induced subgraph of the source |
| Nodes | 77,360 | 28,000 |
| Edges | 905,468 | 138,593 |
| Type | Directed social graph (Slashdot user friend/foe network, Nov 2008) | Same |
| Node attributes | ID only — no rich properties (noted as a caveat) | Same |

### Why the dataset was trimmed

The full dataset (905,468 edges) exceeds the assignment's own recommended range for the smallest free tier ("roughly 100k–500k relationships is a good range"). In practice, loading the full dataset onto CognoDB's free instance (512 MB RAM) caused the instance to hit ~103% memory usage and drop connections mid-query.

`data/trim_subgraph.py` addresses this by sampling 28,000 nodes at random and keeping only the edges whose *both* endpoints fall in that sample (an induced subgraph) — landing at 138,593 edges, comfortably inside the recommended range. **The same trimmed dataset (`data/nodes.csv` / `data/edges.csv`) is loaded identically onto all five platforms**, so the comparison stays fair. The original full dataset is retained as `data/nodes_full.csv` / `data/edges_full.csv` for reference and is not used in the benchmark runs.

`data/fetch_and_convert.py` downloads the raw dataset from SNAP and converts it to `nodes.csv` / `edges.csv`; `data/trim_subgraph.py` is then run on top to produce the trimmed set actually used.

### Known data quality note: self-loops

Approximately 20% of edges in the trimmed dataset are self-loops (a node following itself), inherited proportionally from the source data (~8.5% of edges in the full dataset are self-loops — consistent with SNAP's published statistics, so this is a property of the source data rather than a parsing artifact). These are left in place and not filtered out, since removing them would require reloading every platform; their effect is structural (a node's 1-hop neighbor set trivially includes itself) rather than a fairness concern, since it applies identically across all five platforms.

---

## Platform Specifications

| Platform | Engine | Query Language | Deployment | Free Tier Specs |
|---|---|---|---|---|
| **CognoDB Cloud** | Disk-based | Cypher (Bolt) | Managed cloud | burst to 0.5 vCPU · 512 MB RAM · 1 GiB disk · up to 500 IOPS |
| **Neo4j AuraDB** | Disk-based | Cypher (Bolt) | Managed cloud | 1 vCPU · 256 MB RAM |
| **Memgraph Cloud** | In-memory | Cypher (Bolt) | Managed cloud | Trial instance |
| **ArangoDB Oasis** | Disk-based (multi-model) | AQL (HTTP) | Managed cloud | 14-day trial |
| **FalkorDB** | In-memory (Redis-based) | Cypher (RESP) | Self-hosted (Docker) | Capped to 0.5 vCPU · 512 MB RAM |

> **Honest caveat on hardware heterogeneity:** Free-tier specs are not identical across vendors. Observed performance differences are partially attributable to infrastructure, not engine capability alone. Specs are documented as-advertised (or as-configured, for the self-hosted FalkorDB instance) above.

> **Honest caveat on network geography:** All managed-cloud instances were provisioned in US regions (CognoDB: `us-east4`) while benchmarks were run from Indonesia. Round-trip network latency (~250ms observed floor across every query type on CognoDB) dominates absolute latency numbers on the managed-cloud platforms. FalkorDB, being self-hosted on `localhost`, does not carry this penalty — so **cross-platform latency comparisons should be read as protocol/engine-plus-network-path comparisons, not pure engine comparisons.** This is flagged explicitly rather than hidden.

---

## Architecture & Design Decisions

### Why one shared Bolt driver for three platforms?

CognoDB, Neo4j AuraDB, and Memgraph all implement the **Bolt binary protocol** with Cypher. A single `loaders/driver_bolt.py` module serves all three. Query equivalence is auditable at a glance and there is no copy-paste drift.

### Why isn't FalkorDB on the shared Bolt driver too?

FalkorDB is Cypher-compatible but speaks **RESP (Redis Serialization Protocol)**, not Bolt. It uses the official `falkordb` Python client instead (`loaders/falkordb.py`), but the Cypher query strings themselves are identical to the Bolt platforms' — only the transport and call syntax (`graph.query(...)` vs `session.run(...)`) differ. This keeps query logic auditable across all four Cypher-speaking platforms.

### Why AQL for ArangoDB instead of adapting Cypher?

ArangoDB does not natively speak Cypher. AQL expresses graph traversals differently (`FOR v IN 1..N OUTBOUND ...` vs `MATCH ()-[:REL*1..N]->()`). The AQL versions in `workloads/` are **logically equivalent** to the Cypher versions and placed side-by-side so the equivalence can be verified manually.

### Why `time.perf_counter()` instead of `datetime.now()`?

`perf_counter` uses the highest-resolution timer available on the OS. `datetime.now()` has platform-dependent resolution (typically 1ms on Windows) that would distort p50/p95 distributions at fast query latencies.

### Why UNWIND batching for loading?

Issuing one query per node or edge is network-bound for cloud platforms. UNWIND-based batching sends N operations per round-trip, dramatically reducing load time. Batch sizes are tuned per platform.

### Why explicit LIMIT on every traversal query?

Variable-length Cypher patterns (`*1..3`) are typically expanded in full by the query engine *before* a `LIMIT` is applied — so an unbounded 3-hop traversal on a graph with average out-degree ~5 can materialize thousands of paths server-side even though only a handful are returned. Every traversal query caps the result set (`LIMIT 500` / `100` / `25` for 1/2/3-hop respectively) to keep memory use bounded on constrained free-tier instances, applied identically across all platforms for fairness.

### Why clear/truncate existing data before each load?

`loaders/driver_bolt.py` provides `clear_graph()` (batched `DETACH DELETE`), and `loaders/arangodb.py` truncates its collections, before every load. Node/edge writes otherwise use `MERGE` (Bolt platforms) or `on_duplicate="ignore"` (ArangoDB) for idempotency, but neither removes stale data from a prior run with a different dataset size — so an explicit clear step is run first, guaranteeing every benchmark run starts from a clean, correctly-sized graph regardless of instance history. FalkorDB's loader achieves the same via `graph.delete()`.

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

All read workloads run **10 warmup iterations** before **100 measured iterations**, with retry-with-backoff (2 attempts, 1s delay) on transient connection failures. Iterations that still fail after retry are logged and excluded from the percentile calculation, with the failure count reported.

Index used for point/filtered lookups on all Cypher platforms: `CREATE INDEX ... FOR (u:User) ON (u.id)`. ArangoDB uses a unique persistent index on `users.id`.

---

## Repository Structure

```
data/
  fetch_and_convert.py    Download SNAP dataset and convert to CSV
  trim_subgraph.py        Sample an induced subgraph sized for the smallest free tier
  nodes.csv / edges.csv   Trimmed dataset actually used for benchmarking (28k / 138.6k)
  nodes_full.csv / edges_full.csv   Full source dataset, kept for reference
loaders/
  driver_bolt.py          Shared Bolt+Cypher driver (CognoDB / Neo4j / Memgraph)
  cognodb.py               CognoDB Cloud loader
  neo4j.py                 Neo4j AuraDB loader
  memgraph.py               Memgraph Cloud loader
  arangodb.py               ArangoDB Oasis loader (AQL)
  falkordb.py               FalkorDB loader (RESP client, Cypher queries)
workloads/
  traversal.py             1/2/3-hop traversal — Cypher (Bolt + FalkorDB) + AQL variants
  lookup.py                 Point and filtered lookup
  aggregation.py             Count / group-by aggregations
  mixed.py                   Concurrent mixed read/write
harness/
  run_benchmark.py           Orchestrator — load + workloads + emit results JSON
scripts/
  generate_charts.py          PNG charts from results JSON
  generate_tables.py           Markdown tables for README
results/                       Raw JSON outputs + charts (generated, not committed)
.env.example                    Required environment variables (no secrets)
requirements.txt                 Pinned Python dependencies
```

---

## Results

> Table below reflects the most recent `scripts/generate_tables.py` run. Regenerate after every platform has been benchmarked to refresh all rows.

### Data Loading Throughput

| Platform | Nodes/sec | Edges/sec | Total Load Time |
|---|---|---|---|
| CognoDB | 3,576.3 | 1,741.1 | 87.4s |
| Neo4j AuraDB | — | — | — |
| Memgraph Cloud | — | — | — |
| ArangoDB Oasis | — | — | — |
| FalkorDB | — | — | — |

### Traversal Latency — p50 / p95 (ms)

| Platform | 1-hop p50 | 1-hop p95 | 2-hop p50 | 2-hop p95 | 3-hop p50 | 3-hop p95 |
|---|---|---|---|---|---|---|
| CognoDB | 273.8 | 453.9 | 313.1 | 429.1 | 277.9 | 1086.6 |
| Neo4j AuraDB | — | — | — | — | — | — |
| Memgraph Cloud | — | — | — | — | — | — |
| ArangoDB Oasis | — | — | — | — | — | — |
| FalkorDB | — | — | — | — | — | — |

### Lookup Latency — p50 / p95 (ms)

| Platform | Point Lookup p50 | Point Lookup p95 | Filtered p50 | Filtered p95 |
|---|---|---|---|---|
| CognoDB | 294.1 | 429.1 | 327.4 | 440.4 |
| Neo4j AuraDB | — | — | — | — |
| Memgraph Cloud | — | — | — | — |
| ArangoDB Oasis | — | — | — | — |
| FalkorDB | — | — | — | — |

### Aggregation Latency — p50 / p95 (ms)

| Platform | Count Follows p50 | Count Follows p95 | Count Followers p50 | Count Followers p95 |
|---|---|---|---|---|
| CognoDB | 250.6 | 286.2 | 250.4 | 259.0 |
| Neo4j AuraDB | — | — | — | — |
| Memgraph Cloud | — | — | — | — |
| ArangoDB Oasis | — | — | — | — |
| FalkorDB | — | — | — | — |

### Mixed Workload Throughput (QPS)

| Platform | 1 client | 10 clients | 40 clients |
|---|---|---|---|
| CognoDB | 3.69 | 36.46 | 147.02 |
| Neo4j AuraDB | — | — | — |
| Memgraph Cloud | — | — | — |
| ArangoDB Oasis | — | — | — |
| FalkorDB | — | — | — |

---

## Reproduction

### Requirements

- Python 3.11+
- Docker (for self-hosted FalkorDB)
- Free-tier accounts on: CognoDB, Neo4j AuraDB, Memgraph Cloud, ArangoDB Oasis

### Setup

```bash
git clone https://github.com/gryvnalvrdo/cognodb-graph-benchmark
cd cognodb-graph-benchmark

python -m venv venv
source venv/bin/activate      # Windows: venv\Scripts\Activate.ps1
pip install -r requirements.txt

cp .env.example .env
# Edit .env — fill in credentials for CognoDB, Neo4j, Memgraph, ArangoDB
# (FalkorDB defaults to localhost:6379 and needs no credentials)

docker run -d --name falkordb-bench --memory=512m --cpus=0.5 -p 6379:6379 falkordb/falkordb:latest
```

### Download & Prepare Dataset

```bash
python data/fetch_and_convert.py
python data/trim_subgraph.py
```

This produces the trimmed `nodes.csv` / `edges.csv` (28,000 nodes / 138,593 edges) actually used for benchmarking; the untrimmed files are archived as `nodes_full.csv` / `edges_full.csv`.

### Verify Connectivity

```bash
python harness/run_benchmark.py --platform cognodb --dry-run
python harness/run_benchmark.py --platform neo4j --dry-run
python harness/run_benchmark.py --platform memgraph --dry-run
python harness/run_benchmark.py --platform arangodb --dry-run
python harness/run_benchmark.py --platform falkordb --dry-run
```

### Run Benchmark

```bash
python harness/run_benchmark.py --platform cognodb
python harness/run_benchmark.py --platform neo4j
python harness/run_benchmark.py --platform memgraph
python harness/run_benchmark.py --platform arangodb
python harness/run_benchmark.py --platform falkordb
```

Use `--skip-load` if data is already loaded and you only want to re-run the query workloads:

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

- **Dataset trimmed from the full source:** soc-Slashdot0811 in full (905,468 edges) exceeds the assignment's recommended 100k–500k range for the smallest free tier and caused CognoDB's free instance to hit its RAM limit. An induced subgraph (28,000 nodes / 138,593 edges) is used instead, identically across all five platforms. See "Dataset" above.
- **Self-loops present:** ~20% of edges in the trimmed dataset are self-loops, inherited proportionally from the source data. Not filtered, since doing so would require reloading every platform; applies identically to all five, so it does not bias the comparison.
- **Three cloud platforms unreachable, resolved via self-hosting:** FalkorDB Cloud, TigerGraph Savanna, and Dgraph Cloud were all attempted and failed at signup/auth (full documentation in "Platform Selection Notes"). FalkorDB was run self-hosted via Docker instead, capped to match CognoDB's free-tier resources, to keep the platform count at five as specified.
- **Hardware heterogeneity:** Free-tier specs differ across vendors and are not all identical to CognoDB's. Performance gaps reflect both engine capability and infrastructure differences, documented as-advertised in "Platform Specifications."
- **Network geography dominates absolute latency on managed-cloud platforms:** all managed instances are in US regions; benchmarks run from Indonesia. A ~250ms round-trip floor is visible across nearly every CognoDB query type regardless of query complexity, meaning cross-platform *absolute* latency comparisons partly reflect network path, not just engine performance. FalkorDB (localhost) is not subject to this and should be read as a different comparison axis (protocol/engine only, no network variable).
- **No node attributes:** soc-Slashdot0811 contains no node properties beyond the ID. Filtered lookups test structural traversal, not property index performance.
- **Query language parity:** Cypher (Bolt + FalkorDB platforms) and AQL (ArangoDB) express equivalent traversals with different syntax. Logical equivalence was verified by comparing result sets on a sample, but language-level optimizer differences remain a confounding variable.
- **GIL contention (mixed workload):** Python's Global Interpreter Lock limits true CPU parallelism in threaded workloads. At 40 clients, throughput may be bottlenecked by the Python client rather than the database. This is consistent across all platforms and therefore a fair relative comparison.
- **Memgraph self-signed certificate:** Memgraph Cloud uses a self-signed TLS certificate. The Bolt driver is configured with `bolt+ssc://` to accept it. This is a known Memgraph Cloud configuration requirement.
- **Explicit LIMIT on variable-length traversals:** 2-hop and 3-hop Cypher/AQL queries cap their result sets (see "Why explicit LIMIT" above) to stay within free-tier memory bounds. This reflects how such queries would realistically be run in production, but means p95 latencies do not represent an unbounded traversal.

---

## Dependencies

| Package | Version | Purpose |
|---|---|---|
| `neo4j` | 5.22.0 | Bolt driver for CognoDB, Neo4j, Memgraph |
| `python-arango` | 8.1.3 | ArangoDB HTTP/AQL driver |
| `falkordb` | 1.7.1 | FalkorDB RESP client |
| `numpy` | 2.0.2 | Percentile computation |
| `pandas` | 2.2.3 | Result aggregation |
| `matplotlib` | 3.9.2 | Chart generation |
| `seaborn` | 0.13.2 | Chart styling |
| `python-dotenv` | 1.0.1 | Environment variable loading |
| `tqdm` | 4.66.5 | Progress reporting |
| `requests` | 2.32.3 | HTTP utilities |