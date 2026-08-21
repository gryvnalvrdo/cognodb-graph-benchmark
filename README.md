# CognoDB Graph Database Benchmark

A reproducible performance benchmark comparing **CognoDB Cloud** against four other graph database platforms — Neo4j AuraDB, Memgraph Cloud, ArangoDB Oasis, and **Kùzu** — on the same dataset, the same queries, and from the same client machine.

---

## Motivation

Graph databases are a competitive, rapidly-evolving space. Vendors make strong performance claims, but published benchmarks are almost always vendor-funded, proprietary, or run on non-comparable hardware. This project takes a different approach: treat every platform as a black box, use a real publicly-available social graph dataset, and measure what actually matters in production — ingest throughput, query latency at percentile level, and concurrent read/write capacity.

The five platforms represent meaningfully different architectural points:

- **CognoDB** — the platform under evaluation; disk-based, Bolt+Cypher
- **Neo4j AuraDB** — the dominant Cypher-native cloud database; best apples-to-apples comparison
- **Memgraph Cloud** — in-memory Cypher engine; tests the in-memory vs disk trade-off
- **ArangoDB Oasis** — multi-model, disk-based, uses AQL; tests protocol/language overhead
- **Kùzu** — embedded columnar graph database, Cypher-native; tests embedded vs managed-cloud trade-off

---

## Dataset

**soc-Slashdot0811** — Stanford Network Analysis Project (SNAP)

| Property | Value |
|---|---|
| Source | https://snap.stanford.edu/data/soc-Slashdot0811.html |
| Nodes | 77,360 |
| Edges | 905,468 |
| Type | Directed social graph (Slashdot user friend/foe network, Nov 2008) |
| Node attributes | ID only — no rich properties (documented as a caveat) |

`data/fetch_and_convert.py` downloads it directly from SNAP and converts to:
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
| **Kùzu** | Columnar (embedded) | Cypher (in-process) | Local / embedded | Unbounded (local machine) |

> **Platform 5 — Why Kùzu instead of FalkorDB or TigerGraph?**
>
> FalkorDB Cloud was inaccessible from the test region. TigerGraph Savanna 4.2.2 (the current cloud offering) has migrated to OIDC/OAuth2 authentication that is not supported by the current pyTigerGraph 2.0.4 REST++ client when the account uses Google SSO — a known compatibility gap documented in [pyTigerGraph issue tracker](https://github.com/tigergraph/pyTigerGraph).
>
> **Kùzu** was chosen as the replacement because:
> 1. It is Cypher-native, so the workload logic is identical to the Bolt-based platforms — no query-language confound.
> 2. It represents a genuinely different architectural point: columnar vectorized execution embedded in-process, rather than a managed remote server.
> 3. It is production-ready (Waterloo University, v0.11, 2024) and actively developed.
>
> The embedded/local nature of Kùzu is an explicit, documented caveat: its latency numbers reflect in-process function calls, not network round-trips. This makes it the upper-bound reference point — the best possible latency achievable on the test hardware — rather than a fair cloud comparison.

> **Honest caveat on hardware heterogeneity:** Free-tier cloud specs are not identical across vendors. Observed performance differences are partially attributable to infrastructure. Specs are documented as-advertised above.

---

## Architecture & Design Decisions

### Why one shared Bolt driver for three platforms?

CognoDB, Neo4j AuraDB, and Memgraph all implement the **Bolt binary protocol** with Cypher. A single `loaders/driver_bolt.py` module serves all three. This makes query equivalence auditable at a glance and eliminates copy-paste drift.

### Why AQL for ArangoDB instead of adapting Cypher?

ArangoDB does not natively speak Cypher. Its native query language AQL expresses graph traversals differently (`FOR v IN 1..N OUTBOUND ...` vs `MATCH ()-[:REL*1..N]->()`). The AQL versions in `workloads/` are **logically equivalent** to the Cypher versions and placed side-by-side so the equivalence can be verified manually.

### Why Kùzu uses a separate workload module?

Kùzu's Python API (`kuzu.Connection.execute()`) is not a Bolt driver — it is a direct in-process call. The queries are identical Cypher strings, but the transport layer is different. A separate `workloads/kuzu.py` wraps these calls with the same measurement harness (warmup, 100 iterations, `time.perf_counter()`).

### Why `time.perf_counter()` instead of `datetime.now()`?

`perf_counter` uses the highest-resolution timer available on the OS, suitable for sub-millisecond measurements. `datetime.now()` has platform-dependent resolution (typically 1ms on Windows) that would distort p50/p95 distributions at fast query latencies.

### Why UNWIND batching for loading?

Issuing one query per node or edge is network-bound for cloud platforms. UNWIND-based batching sends N operations per round-trip, dramatically reducing load time. Batch sizes are tuned per platform.

### Why p50 and p95 instead of averages?

Averages mask tail latency. A database that answers 99% of queries in 5ms but occasionally takes 5 seconds looks fine on average. p95 captures the worst-case experience for roughly 1 in 20 queries — a more operationally meaningful signal.

### Why 80/20 read/write split in the mixed workload?

Real-world social graph workloads are read-heavy. An 80% read (1-hop traversal) / 20% write (property update) ratio approximates YCSB Workload B. It stresses lock management and connection pool behavior without being a pure read benchmark.

---

## Workloads

| Workload | Description | Metric |
|---|---|---|
| **Ingest** | Bulk load all nodes then all edges | nodes/sec, edges/sec, total wall-clock seconds |
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
  kuzu.py                 Kùzu embedded loader
workloads/
  traversal.py            1/2/3-hop traversal — Cypher + AQL variants
  lookup.py               Point and filtered lookup
  aggregation.py          Count / group-by aggregations
  mixed.py                Concurrent mixed read/write (threaded, Bolt platforms)
  kuzu.py                 Kùzu-specific workloads (identical queries, in-process transport)
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

> **Benchmark results will be filled in after all runs complete.**

### Data Loading Throughput

| Platform | Nodes/sec | Edges/sec | Total Load Time |
|---|---|---|---|
| CognoDB | — | — | — |
| Neo4j AuraDB | — | — | — |
| Memgraph Cloud | — | — | — |
| ArangoDB Oasis | — | — | — |
| Kùzu (local) | — | — | — |

### Traversal Latency — p50 / p95 (ms)

| Platform | 1-hop p50 | 1-hop p95 | 2-hop p50 | 2-hop p95 | 3-hop p50 | 3-hop p95 |
|---|---|---|---|---|---|---|
| CognoDB | — | — | — | — | — | — |
| Neo4j AuraDB | — | — | — | — | — | — |
| Memgraph Cloud | — | — | — | — | — | — |
| ArangoDB Oasis | — | — | — | — | — | — |
| Kùzu (local) | — | — | — | — | — | — |

### Mixed Workload Throughput (QPS)

| Platform | 1 client | 10 clients | 40 clients |
|---|---|---|---|
| CognoDB | — | — | — |
| Neo4j AuraDB | — | — | — |
| Memgraph Cloud | — | — | — |
| ArangoDB Oasis | — | — | — |
| Kùzu (local) | — | — | — |

---

## Reproduction

### Requirements

- Python 3.11+
- Free-tier accounts on all cloud platforms (CognoDB, Neo4j AuraDB, Memgraph Cloud, ArangoDB Oasis)
- No account needed for Kùzu (embedded)
- All benchmarks run from the same client machine and network connection

### Setup

```bash
git clone https://github.com/gryvnalvrdo/cognodb-graph-benchmark
cd cognodb-graph-benchmark

python -m venv venv
source venv/bin/activate      # Windows: venv\Scripts\Activate.ps1
pip install -r requirements.txt

cp .env.example .env
# Edit .env — fill in connection strings and credentials for all cloud platforms
```

### Download and Convert Dataset

```bash
python data/fetch_and_convert.py
```

### Verify Connectivity

```bash
python harness/run_benchmark.py --platform cognodb --dry-run
python harness/run_benchmark.py --platform neo4j --dry-run
python harness/run_benchmark.py --platform memgraph --dry-run
python harness/run_benchmark.py --platform arangodb --dry-run
python harness/run_benchmark.py --platform kuzu --dry-run
```

### Run Benchmark

```bash
python harness/run_benchmark.py --platform cognodb
python harness/run_benchmark.py --platform neo4j
python harness/run_benchmark.py --platform memgraph
python harness/run_benchmark.py --platform arangodb
python harness/run_benchmark.py --platform kuzu
```

If data is already loaded:

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

- **Hardware heterogeneity (cloud platforms):** Free-tier specs differ across providers. Performance gaps reflect both engine capability and infrastructure. Advertised specs are documented in the platform table above.
- **Network variance (cloud platforms):** All cloud timings include the client-to-server round-trip from a single client machine. Cloud latency is non-deterministic; percentile reporting mitigates but does not eliminate this noise.
- **Kùzu is embedded (local), not cloud:** Kùzu's latency numbers reflect in-process function calls with no network hop. It is the theoretical lower-bound reference — the best latency achievable on this hardware — not a cloud-to-cloud comparison. This is an intentional architectural contrast, not a methodological flaw.
- **No node attributes:** soc-Slashdot0811 contains no node properties beyond the ID. Filtered lookups test structural traversal, not property index performance.
- **Query language parity:** Cypher (Bolt platforms + Kùzu) and AQL (ArangoDB) express equivalent traversals with different syntax. Logical equivalence was verified by comparing result sets on a sample, but language-level optimizer differences remain a confounding variable.
- **GIL contention (mixed workload):** Python's Global Interpreter Lock limits true CPU parallelism in threaded workloads. At 40 clients, throughput may be bottlenecked by the Python client rather than the database. This is consistent across all platforms and is therefore a fair relative comparison.
- **Memgraph self-signed certificate:** Memgraph Cloud uses a self-signed TLS certificate. The Bolt driver is configured with the `bolt+ssc://` scheme to accept it. This is a known Memgraph Cloud configuration requirement.

---

## Dependencies

| Package | Version | Purpose |
|---|---|---|
| `neo4j` | 5.22.0 | Bolt driver for CognoDB, Neo4j, Memgraph |
| `python-arango` | 8.1.3 | ArangoDB HTTP/AQL driver |
| `kuzu` | 0.11.3 | Kùzu embedded graph database |
| `numpy` | 2.0.2 | Percentile computation |
| `pandas` | 2.2.3 | Result aggregation |
| `matplotlib` | 3.9.2 | Chart generation |
| `seaborn` | 0.13.2 | Chart styling |
| `python-dotenv` | 1.0.1 | Environment variable loading |
| `tqdm` | 4.66.5 | Progress reporting |
| `requests` | 2.32.3 | HTTP utilities |
