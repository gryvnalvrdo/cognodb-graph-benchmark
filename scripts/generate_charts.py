"""
Generate PNG charts from benchmark results (results/*.json) into results/charts/.

Run after all platforms have been benchmarked:
    python scripts/generate_charts.py
"""
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")  # headless — no display needed
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import seaborn as sns

RESULTS_DIR = Path(__file__).parent.parent / "results"
CHARTS_DIR = RESULTS_DIR / "charts"
PLATFORMS = ["cognodb", "neo4j", "memgraph", "arangodb", "falkordb"]

# Consistent color per platform across every chart, and a display label
PLATFORM_LABELS = {
    "cognodb": "CognoDB",
    "neo4j": "Neo4j AuraDB",
    "memgraph": "Memgraph Cloud",
    "arangodb": "ArangoDB Oasis",
    "falkordb": "FalkorDB",
}
PLATFORM_COLORS = {
    "cognodb": "#4C72B0",
    "neo4j": "#DD8452",
    "memgraph": "#55A868",
    "arangodb": "#C44E52",
    "falkordb": "#8172B2",
}

sns.set_theme(style="whitegrid")


def _load_results() -> dict:
    data = {}
    for p in PLATFORMS:
        path = RESULTS_DIR / f"{p}.json"
        if path.exists():
            data[p] = json.loads(path.read_text())
    return data


def _present_platforms(data: dict) -> list[str]:
    """Platforms with results, in the fixed PLATFORMS order."""
    return [p for p in PLATFORMS if p in data]


def _bar_colors(platforms: list[str]) -> list[str]:
    return [PLATFORM_COLORS[p] for p in platforms]


def _labels(platforms: list[str]) -> list[str]:
    return [PLATFORM_LABELS[p] for p in platforms]


def _save(fig, name: str) -> None:
    CHARTS_DIR.mkdir(parents=True, exist_ok=True)
    out_path = CHARTS_DIR / name
    fig.tight_layout()
    fig.savefig(out_path, dpi=150)
    plt.close(fig)
    print(f"  wrote {out_path}")


def chart_load_throughput(data: dict) -> None:
    platforms = [p for p in _present_platforms(data) if isinstance(data[p].get("load"), dict)]
    if not platforms:
        return
    nodes_per_sec = [data[p]["load"]["nodes_per_sec"] for p in platforms]
    edges_per_sec = [data[p]["load"]["edges_per_sec"] for p in platforms]

    fig, axes = plt.subplots(1, 2, figsize=(11, 4.5))
    for ax, values, title in [
        (axes[0], nodes_per_sec, "Nodes / sec"),
        (axes[1], edges_per_sec, "Edges / sec"),
    ]:
        ax.bar(_labels(platforms), values, color=_bar_colors(platforms))
        ax.set_title(title)
        ax.set_yscale("log")
        ax.yaxis.set_major_formatter(mticker.ScalarFormatter())
        ax.tick_params(axis="x", rotation=25)
        for i, v in enumerate(values):
            ax.text(i, v, f"{v:,.0f}", ha="center", va="bottom", fontsize=8)

    fig.suptitle("Data Loading Throughput (log scale)")
    _save(fig, "load_throughput.png")


def _hop_latency_chart(data: dict, category: str, hop_keys: list[str], hop_titles: list[str],
                        filename: str, suptitle: str) -> None:
    platforms = [p for p in _present_platforms(data) if category in data[p]]
    if not platforms:
        return

    fig, axes = plt.subplots(1, len(hop_keys), figsize=(4.2 * len(hop_keys), 4.5), sharey=False)
    if len(hop_keys) == 1:
        axes = [axes]

    for ax, hop_key, hop_title in zip(axes, hop_keys, hop_titles):
        p50s = [data[p][category].get(hop_key, {}).get("p50_ms") or 0 for p in platforms]
        p95s = [data[p][category].get(hop_key, {}).get("p95_ms") or 0 for p in platforms]

        x = range(len(platforms))
        width = 0.35
        ax.bar([i - width / 2 for i in x], p50s, width, label="p50", color=_bar_colors(platforms), alpha=0.9)
        ax.bar([i + width / 2 for i in x], p95s, width, label="p95", color=_bar_colors(platforms), alpha=0.5)
        ax.set_title(hop_title)
        ax.set_xticks(list(x))
        ax.set_xticklabels(_labels(platforms), rotation=25, ha="right")
        ax.set_yscale("log")
        ax.set_ylabel("ms")
        ax.legend(fontsize=8)

    fig.suptitle(suptitle)
    _save(fig, filename)


def chart_traversal(data: dict) -> None:
    _hop_latency_chart(
        data, "traversal",
        hop_keys=["1_hop", "2_hop", "3_hop"],
        hop_titles=["1-hop", "2-hop", "3-hop"],
        filename="traversal_latency.png",
        suptitle="Traversal Latency — p50 vs p95 (log scale, ms)",
    )


def chart_lookup(data: dict) -> None:
    _hop_latency_chart(
        data, "lookup",
        hop_keys=["point_lookup", "filtered_lookup"],
        hop_titles=["Point lookup", "Filtered lookup"],
        filename="lookup_latency.png",
        suptitle="Lookup Latency — p50 vs p95 (log scale, ms)",
    )


def chart_aggregation(data: dict) -> None:
    _hop_latency_chart(
        data, "aggregation",
        hop_keys=["count_follows", "count_followers"],
        hop_titles=["Count follows", "Count followers"],
        filename="aggregation_latency.png",
        suptitle="Aggregation Latency — p50 vs p95 (log scale, ms)",
    )


def chart_mixed_qps(data: dict) -> None:
    platforms = [p for p in _present_platforms(data) if "mixed" in data[p]]
    if not platforms:
        return

    fig, ax = plt.subplots(figsize=(7, 4.5))
    for p in platforms:
        sweep = data[p]["mixed"].get("concurrency_sweep", [])
        if not sweep:
            continue
        xs = [s["concurrency"] for s in sweep]
        ys = [s["qps"] for s in sweep]
        ax.plot(xs, ys, marker="o", label=PLATFORM_LABELS[p], color=PLATFORM_COLORS[p])

    ax.set_xlabel("Concurrent clients")
    ax.set_ylabel("Queries / sec")
    ax.set_yscale("log")
    ax.set_xscale("log")
    ax.set_xticks([1, 10, 40])
    ax.set_xticklabels(["1", "10", "40"])
    ax.set_title("Mixed Workload Throughput vs Concurrency (log-log)")
    ax.legend(fontsize=8)
    _save(fig, "mixed_qps.png")


def main() -> None:
    data = _load_results()
    if not data:
        print("No results found in results/*.json — run the benchmark harness first.")
        return

    print(f"Generating charts for: {', '.join(_present_platforms(data))}")
    chart_load_throughput(data)
    chart_traversal(data)
    chart_lookup(data)
    chart_aggregation(data)
    chart_mixed_qps(data)
    print(f"\nDone. Charts written to {CHARTS_DIR}/")


if __name__ == "__main__":
    main()