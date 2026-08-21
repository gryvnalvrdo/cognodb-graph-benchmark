## Data Loading Throughput

| Platform | Nodes/sec | Edges/sec | Total Load Time |
|---|---|---|---|
| Cognodb | 3,576.3 | 1,741.1 | 87.4s |
| Neo4j | 7,286.2 | 4,114.6 | 37.5s |
| Memgraph | 3,826.7 | 1,944.0 | 78.6s |
| Arangodb | 1,817.4 | 2,689.2 | 66.9s |
| Falkordb | 36,457.5 | 14,442.5 | 10.4s |

## Traversal Latency (p50 / p95 ms)

| Platform | 1-hop p50 | 1-hop p95 | 2-hop p50 | 2-hop p95 | 3-hop p50 | 3-hop p95 |
|---|---|---|---|---|---|---|
| Cognodb | 273.8ms | 453.9ms | 313.1ms | 429.1ms | 277.9ms | 1,086.6ms |
| Neo4j | 75.3ms | 84.8ms | 79.8ms | 100.0ms | 75.8ms | 95.6ms |
| Memgraph | 235.4ms | 244.2ms | 237.7ms | 251.2ms | 236.8ms | 242.7ms |
| Arangodb | 245.9ms | 318.7ms | 269.7ms | 400.1ms | 250.3ms | 334.5ms |
| Falkordb | 0.6ms | 0.8ms | 0.9ms | 1.8ms | 0.7ms | 1.0ms |

## Lookup Latency (p50 / p95 ms)

| Platform | Point p50 | Point p95 | Filtered p50 | Filtered p95 |
|---|---|---|---|---|
| Cognodb | 294.1ms | 429.1ms | 327.4ms | 440.4ms |
| Neo4j | 74.5ms | 108.1ms | 73.5ms | 85.7ms |
| Memgraph | 234.9ms | 242.7ms | 234.9ms | 241.5ms |
| Arangodb | 243.9ms | 299.1ms | 245.5ms | 299.7ms |
| Falkordb | 0.5ms | 0.6ms | 0.5ms | 0.7ms |

## Aggregation Latency (p50 / p95 ms)

| Platform | Count Follows p50 | Count Follows p95 | Count Followers p50 | Count Followers p95 |
|---|---|---|---|---|
| Cognodb | 250.6ms | 286.2ms | 250.4ms | 259.0ms |
| Neo4j | 74.8ms | 109.6ms | 77.3ms | 205.1ms |
| Memgraph | 235.4ms | 246.0ms | 235.4ms | 250.9ms |
| Arangodb | 244.3ms | 299.7ms | 244.6ms | 289.3ms |
| Falkordb | 0.5ms | 0.6ms | 0.5ms | 0.7ms |

## Mixed Workload Throughput (QPS)

| Platform | 1 client | 10 clients | 40 clients |
|---|---|---|---|
| Cognodb | 3.7 qps | 36.5 qps | 147.0 qps |
| Neo4j | 11.6 qps | 15.5 qps | 13.1 qps |
| Memgraph | 4.2 qps | 40.5 qps | 162.0 qps |
| Arangodb | 3.9 qps | 37.1 qps | 116.4 qps |
| Falkordb | 1,668.6 qps | 1,722.0 qps | 1,121.9 qps |