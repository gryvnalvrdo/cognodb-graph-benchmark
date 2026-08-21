import json
from pathlib import Path
import matplotlib.pyplot as plt
import numpy as np

RESULTS_DIR = Path(__file__).parent.parent / "results"
CHARTS_DIR = RESULTS_DIR / "charts"
CHARTS_DIR.mkdir(parents=True, exist_ok=True)

PLATFORMS = ["cognodb", "neo4j", "memgraph", "arangodb"]
PALETTE = {
    "cognodb": "#6C63FF",
    "neo4j": "#00BCD4",
    "memgraph": "#4CAF50",
    "arangodb": "#FF5722",
}


def _load_results() -> dict:
    return {
        p: json.loads((RESULTS_DIR / f"{p}.json").read_text())
        for p in PLATFORMS
        if (RESULTS_DIR / f"{p}.json").exists()
    }


def chart_load_throughput(data: dict):
    fig, axes = plt.subplots(1, 2, figsize=(12, 5))
    for ax, key, label in [
        (axes[0], "nodes_per_sec", "Nodes / sec"),
        (axes[1], "edges_per_sec", "Edges / sec"),
    ]:
        platforms = [p for p in data if isinstance(data[p].get("load"), dict)]
        vals = [data[p]["load"].get(key, 0) for p in platforms]
        bars = ax.bar([p.capitalize() for p in platforms], vals, color=[PALETTE.get(p, "#aaa") for p in platforms])
        ax.set_title(f"Ingest Throughput — {label}")
        ax.set_ylabel(label)
        ax.grid(axis="y", alpha=0.3)
        for bar, val in zip(bars, vals):
            ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height(), f"{val:,.0f}", ha="center", va="bottom", fontsize=9)
    plt.tight_layout()
    plt.savefig(CHARTS_DIR / "load_throughput.png", dpi=150)
    plt.close()


def chart_traversal_latency(data: dict):
    hops = ["1_hop", "2_hop", "3_hop"]
    for metric in ["p50_ms", "p95_ms"]:
        fig, ax = plt.subplots(figsize=(10, 5))
        x = np.arange(len(hops))
        width = 0.15
        for i, (platform, result) in enumerate(data.items()):
            if "traversal" not in result:
                continue
            vals = [result["traversal"].get(h, {}).get(metric, 0) for h in hops]
            ax.bar(x + i * width, vals, width, label=platform.capitalize(), color=PALETTE.get(platform, "#aaa"))
        ax.set_title(f"Traversal Latency — {metric.upper()}")
        ax.set_xlabel("Hop Depth")
        ax.set_ylabel(f"Latency ({metric})")
        ax.set_xticks(x + width * 2)
        ax.set_xticklabels(["1-hop", "2-hop", "3-hop"])
        ax.legend()
        ax.grid(axis="y", alpha=0.3)
        plt.tight_layout()
        plt.savefig(CHARTS_DIR / f"traversal_{metric}.png", dpi=150)
        plt.close()


def chart_mixed_qps(data: dict):
    fig, ax = plt.subplots(figsize=(10, 5))
    concurrency_levels = [1, 10, 40]
    for platform, result in data.items():
        sweep = result.get("mixed", {}).get("concurrency_sweep", [])
        qps_vals = [s.get("qps", 0) for s in sweep]
        if len(qps_vals) == 3:
            ax.plot(concurrency_levels, qps_vals, marker="o", label=platform.capitalize(), color=PALETTE.get(platform, "#aaa"))
    ax.set_title("Mixed Workload — QPS vs Concurrency")
    ax.set_xlabel("Concurrent Clients")
    ax.set_ylabel("Queries / sec")
    ax.set_xticks(concurrency_levels)
    ax.legend()
    ax.grid(alpha=0.3)
    plt.tight_layout()
    plt.savefig(CHARTS_DIR / "mixed_qps.png", dpi=150)
    plt.close()


def main():
    data = _load_results()
    if not data:
        print("No results found. Run the benchmark first.")
        return
    print(f"Generating charts for: {list(data.keys())}")
    chart_load_throughput(data)
    chart_traversal_latency(data)
    chart_mixed_qps(data)
    print(f"Charts saved to {CHARTS_DIR}")


if __name__ == "__main__":
    main()
