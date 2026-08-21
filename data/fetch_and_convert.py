import argparse
import csv
import gzip
import urllib.request
from pathlib import Path

SNAP_URL = "https://snap.stanford.edu/data/soc-Slashdot0811.txt.gz"
DATA_DIR = Path(__file__).parent
GZ_PATH = DATA_DIR / "soc-Slashdot0811.txt.gz"
NODES_CSV = DATA_DIR / "nodes.csv"
EDGES_CSV = DATA_DIR / "edges.csv"


def _progress(count, block_size, total_size):
    pct = count * block_size * 100 // total_size if total_size > 0 else 0
    print(f"\r  {min(pct, 100)}%", end="", flush=True)


def download(url: str, dest: Path) -> None:
    if dest.exists():
        print(f"[skip] {dest.name} already downloaded.")
        return
    print(f"Downloading {url} ...")
    urllib.request.urlretrieve(url, dest, reporthook=_progress)
    print()


def parse_edges(gz_path: Path, max_edges: int | None = None) -> list[tuple[int, int]]:
    edges = []
    print("Parsing edge list ...")
    with gzip.open(gz_path, "rt", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split()
            if len(parts) < 2:
                continue
            edges.append((int(parts[0]), int(parts[1])))
            if max_edges and len(edges) >= max_edges:
                print(f"  trimmed to {max_edges} edges")
                break
    return edges


def write_csvs(edges: list[tuple[int, int]]) -> None:
    node_ids = sorted({n for edge in edges for n in edge})
    print(f"Writing {NODES_CSV.name} ({len(node_ids):,} nodes) ...")
    with open(NODES_CSV, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["id"])
        for nid in node_ids:
            writer.writerow([nid])

    print(f"Writing {EDGES_CSV.name} ({len(edges):,} edges) ...")
    with open(EDGES_CSV, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["source_id", "target_id"])
        writer.writerows(edges)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--max-edges", type=int, default=None)
    args = parser.parse_args()

    download(SNAP_URL, GZ_PATH)
    edges = parse_edges(GZ_PATH, max_edges=args.max_edges)
    write_csvs(edges)

    node_count = len({n for edge in edges for n in edge})
    print(f"\nDone. Nodes: {node_count:,} | Edges: {len(edges):,}")
    if args.max_edges:
        print(f"WARNING: trimmed dataset — use --max-edges {args.max_edges} on ALL platforms.")


if __name__ == "__main__":
    main()
