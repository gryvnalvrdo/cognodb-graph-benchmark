# CognoDB Graph Database Benchmark

A reproducible performance benchmark comparing **CognoDB Cloud** against four other managed graph database platforms — Neo4j AuraDB, Memgraph Cloud, ArangoDB Oasis, and FalkorDB Cloud — on the same dataset, the same queries, and from the same client machine.

---

## Motivation

Graph databases are marketed on different strengths: in-memory speed, multi-model flexibility, Redis-native performance, or enterprise Cypher compatibility. Free-tier cloud offerings make it easy to spin up all of them within hours, yet published benchmarks almost never compare them head-to-head on identical workloads. This project closes that gap by treating each platform as a black box and measuring what actually matters in production: ingest throughput, query latency at percentile level, and concurrent read/write capacity.

---

## Dataset

**soc-Slashdot0811** — Stanford Network Analysis Project (SNAP)

| Property | Value |
|---|---|
| Source | https://snap.stanford.edu/data/soc-Slashdot0811.html |
| Nodes | 77,360 |
| Edges | 905,468 |
| Type | Directed social graph (Slashdot user friend/foe network, Nov 2008) |
| Node attributes | ID only (no rich properties — documented as a caveat) |

The dataset ships as a plain edge list. `data/fetch_and_convert.py` downloads it directly from SNAP and converts it to two CSVs used by all loaders:
- `data/nodes.csv` — unique node IDs
- `data/edges.csv` — `source_id, target_id` pairs

If a platform's free-tier storage cannot hold the full 905k edges, pass `--max-edges N` to trim deterministically. The **same N must be used on every platform** — the script enforces this with a warning.

---

## Platform Specifications

| Platform | Engine | Query Language | Free Tier |
|---|---|---|---|
| **CognoDB Cloud** | Disk-based | Cypher (Bolt) | 0.5 vCPU · 256 MB RAM · 1 GB disk |
| **Neo4j AuraDB** | Disk-based | Cypher (Bolt) | 1 vCPU · 256 MB RAM |
| **Memgraph Cloud** | In-memory | Cypher (Bolt) | Varies by trial |
| **ArangoDB Oasis** | Multi-model (disk) | AQL (HTTP) | 14-day trial |
| **FalkorDB Cloud** | Redis-based | Cypher (Redis) | Free, no trial limit |

> **Honest caveat:** Free-tier hardware is not identical across vendors. Observed performance differences are partially attributable to infrastructure, not solely engine design. This is documented — not hidden.

---

## Architecture & Design Decisions

### Why one shared Bolt driver for three platforms?

CognoDB, Neo4j AuraDB, and Memgraph all implement the **Bolt binary protocol** with Cypher as the query language. Rather than duplicating query logic three times, `loaders/driver_bolt.py` provides a single parameterized loader used by all three. This makes query equivalence auditable at a glance.

### Why AQL for ArangoDB instead of adapting Cypher?

ArangoDB does not natively speak Cypher. Its native query language, AQL, expresses graph traversals differently (`FOR v IN 1..N OUTBOUND ...` vs `MATCH ()-[:REL*1..N]->()`). The AQL versions in `workloads/` are written to be **logically equivalent** to the Cypher versions and are placed side-by-side so the equivalence can be verified manually.

### Why FalkorDB over TigerGraph?

FalkorDB (a successor to RedisGraph) uses a Redis-based storage model with a Cypher-compatible query interface — making it an interesting architectural contrast to disk-based databases while still being query-compatible. TigerGraph's free cloud tier is more restrictive in terms of trial duration and API surface, making FalkorDB the more reproducible choice.

### Why `time.perf_counter()` instead of `datetime.now()`?

`perf_counter` uses the highest-resolution timer available on the OS, suitable for sub-millisecond measurements. `datetime.now()` has platform-dependent resolution (typically 1ms on Windows) that would distort p50/p95 distributions at fast query latencies.

### Why UNWIND batching for loading?

Issuing one query per node or edge is network-bound. UNWIND-based batching sends N operations per round-trip, dramatically reducing load time. Batch sizes (1000 nodes, 500 edges) were tuned empirically to stay within Bolt message size limits while maximizing throughput.

### Why p50 and p95 instead of averages?

Averages mask tail latency. A database that answers 99% of queries in 5ms but occasionally takes 5 seconds looks fine on average. p95 (the 95th percentile) captures the worst-case experience for roughly 1 in 20 queries — a more operationally meaningful signal for production systems.

### Why 80/20 read/write split in the mixed workload?

Real-world social graph workloads are read-heavy. An 80% read (1-hop traversal) / 20% write (property update) ratio is a standard approximation used in benchmarks like YCSB Workload B. It stresses the database's lock management and connection pool behavior without being a pure read benchmark.

---

## Workloads

| Workload | Description | Metric |
|---|---|---|
| **Ingest** | Bulk load all nodes then all edges via UNWIND batching | nodes/sec, edges/sec, total wall-clock seconds |
| **Traversal** | 1-hop, 2-hop, 3-hop outbound neighbor expansion from 100 random start nodes | p50 & p95 latency (ms) |
| **Lookup** | Point lookup by ID + filtered neighbor count | p50 & p95 latency (ms) |
| **Aggregation** | Count outgoing and incoming edges per node | p50 & p95 latency (ms) |
| **Mixed** | Concurrent 80% reads / 20% writes at 1, 10, 40 clients | sustained QPS per concurrency level |

All read workloads run **10 warmup iterations** before **100 measured iterations** to eliminate cold-start effects.

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
  falkordb.py             FalkorDB Cloud loader
workloads/
  traversal.py            1/2/3-hop traversal — Cypher + AQL variants
  lookup.py               Point and filtered lookup
  aggregation.py          Count / group-by aggregations
  mixed.py                Concurrent mixed read/write (threaded)
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

> Results will be populated after running the benchmark against all five platforms.

### Data Loading Throughput

*Run `python scripts/generate_tables.py` after benchmarking.*

### Traversal Latency (p50 / p95)

*Run `python scripts/generate_tables.py` after benchmarking.*

### Mixed Workload Throughput

*Run `python scripts/generate_tables.py` after benchmarking.*

---

## Reproduction

### Requirements

- Python 3.11+
- Free-tier accounts on all five platforms
- All benchmarks run from the same client machine and network region

### Setup

```bash
git clone https://github.com/gryvnalvrdo/cognodb-graph-benchmark
cd cognodb-graph-benchmark

python -m venv venv
source venv/bin/activate      # Windows: venv\Scripts\Activate.ps1
pip install -r requirements.txt

cp .env.example .env
# Edit .env — fill in connection strings and credentials for all five platforms
```

### Download and Convert Dataset

```bash
python data/fetch_and_convert.py
```

For platforms with storage constraints:

```bash
python data/fetch_and_convert.py --max-edges 400000
```

> If trimming, use the **same `--max-edges` value on every platform**.

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

If data is already loaded from a previous run:

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

- **Hardware heterogeneity:** Free-tier specs differ across providers. Performance gaps may reflect infrastructure rather than engine capability alone. Advertised specs are documented in the platform table above.
- **Network variance:** All timings include the client-to-server round-trip. Cloud latency is non-deterministic; percentile reporting (p50/p95) mitigates, but does not eliminate, this noise.
- **No node attributes:** soc-Slashdot0811 contains no node properties beyond the ID. Filtered lookups test structural traversal, not property index performance.
- **Query language parity:** Cypher and AQL express equivalent graph traversals with different syntax. Logical equivalence was verified by comparing result sets on a sample, but language-level optimizer differences remain a confounding variable.
- **GIL contention:** Python's Global Interpreter Lock limits true CPU parallelism in the mixed workload threads. At high concurrency (40 clients), throughput may be bottlenecked by the client rather than the database. This is consistent across all platforms and is therefore a fair comparison.

---

## Dependencies

| Package | Version | Purpose |
|---|---|---|
| `neo4j` | 5.22.0 | Bolt driver for CognoDB, Neo4j, Memgraph |
| `python-arango` | 8.1.3 | ArangoDB HTTP/AQL driver |
| `falkordb` | 1.0.9 | FalkorDB Redis-based graph driver |
| `numpy` | 2.0.2 | Percentile computation |
| `pandas` | 2.2.3 | Result aggregation |
| `matplotlib` | 3.9.2 | Chart generation |
| `seaborn` | 0.13.2 | Chart styling |
| `python-dotenv` | 1.0.1 | Environment variable loading |
| `tqdm` | 4.66.5 | Progress reporting |
| `requests` | 2.32.3 | HTTP utilities |
