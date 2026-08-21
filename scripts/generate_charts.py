import json
from pathlib import Path

RESULTS_DIR = Path(__file__).parent.parent / "results"
PLATFORMS = ["cognodb", "neo4j", "memgraph", "arangodb", "falkordb"]


def _load_results() -> dict:
    return {
        p: json.loads((RESULTS_DIR / f"{p}.json").read_text())
        for p in PLATFORMS
        if (RESULTS_DIR / f"{p}.json").exists()
    }


def _fmt(val, unit="") -> str:
    if not val:
        return "N/A"
    return f"{val:,.1f}{unit}" if isinstance(val, float) else f"{val:,}{unit}"


def table_load(data: dict) -> str:
    rows = ["## Data Loading Throughput", "", "| Platform | Nodes/sec | Edges/sec | Total Load Time |", "|---|---|---|---|"]
    for p in PLATFORMS:
        if p not in data or not isinstance(data[p].get("load"), dict):
            continue
        l = data[p]["load"]
        rows.append(f"| {p.capitalize()} | {_fmt(l.get('nodes_per_sec'))} | {_fmt(l.get('edges_per_sec'))} | {_fmt(l.get('total_load_sec'), 's')} |")
    return "\n".join(rows)


def table_traversal(data: dict) -> str:
    rows = ["## Traversal Latency (p50 / p95 ms)", "", "| Platform | 1-hop p50 | 1-hop p95 | 2-hop p50 | 2-hop p95 | 3-hop p50 | 3-hop p95 |", "|---|---|---|---|---|---|---|"]
    for p in PLATFORMS:
        if p not in data or "traversal" not in data[p]:
            continue
        t = data[p]["traversal"]
        row = f"| {p.capitalize()} "
        for hop in ["1_hop", "2_hop", "3_hop"]:
            h = t.get(hop, {})
            row += f"| {_fmt(h.get('p50_ms'), 'ms')} | {_fmt(h.get('p95_ms'), 'ms')} "
        rows.append(row + "|")
    return "\n".join(rows)


def table_lookup(data: dict) -> str:
    rows = ["## Lookup Latency (p50 / p95 ms)", "", "| Platform | Point p50 | Point p95 | Filtered p50 | Filtered p95 |", "|---|---|---|---|---|"]
    for p in PLATFORMS:
        if p not in data or "lookup" not in data[p]:
            continue
        l = data[p]["lookup"]
        point = l.get("point_lookup", {})
        filt = l.get("filtered_lookup", {})
        rows.append(
            f"| {p.capitalize()} | {_fmt(point.get('p50_ms'), 'ms')} | {_fmt(point.get('p95_ms'), 'ms')} "
            f"| {_fmt(filt.get('p50_ms'), 'ms')} | {_fmt(filt.get('p95_ms'), 'ms')} |"
        )
    return "\n".join(rows)


def table_aggregation(data: dict) -> str:
    rows = ["## Aggregation Latency (p50 / p95 ms)", "", "| Platform | Count Follows p50 | Count Follows p95 | Count Followers p50 | Count Followers p95 |", "|---|---|---|---|---|"]
    for p in PLATFORMS:
        if p not in data or "aggregation" not in data[p]:
            continue
        a = data[p]["aggregation"]
        cf = a.get("count_follows", {})
        cr = a.get("count_followers", {})
        rows.append(
            f"| {p.capitalize()} | {_fmt(cf.get('p50_ms'), 'ms')} | {_fmt(cf.get('p95_ms'), 'ms')} "
            f"| {_fmt(cr.get('p50_ms'), 'ms')} | {_fmt(cr.get('p95_ms'), 'ms')} |"
        )
    return "\n".join(rows)


def table_mixed_qps(data: dict) -> str:
    rows = ["## Mixed Workload Throughput (QPS)", "", "| Platform | 1 client | 10 clients | 40 clients |", "|---|---|---|---|"]
    for p in PLATFORMS:
        if p not in data or "mixed" not in data[p]:
            continue
        sweep = data[p]["mixed"].get("concurrency_sweep", [])
        qps = [_fmt(s.get("qps"), " qps") for s in sweep] + ["N/A"] * 3
        rows.append(f"| {p.capitalize()} | {qps[0]} | {qps[1]} | {qps[2]} |")
    return "\n".join(rows)


def main():
    data = _load_results()
    if not data:
        print("No results found.")
        return
    output = "\n\n".join([
        table_load(data),
        table_traversal(data),
        table_lookup(data),
        table_aggregation(data),
        table_mixed_qps(data),
    ])
    out_path = RESULTS_DIR / "tables.md"
    out_path.write_text(output)
    print(f"Tables written to {out_path}")


if __name__ == "__main__":
    main()