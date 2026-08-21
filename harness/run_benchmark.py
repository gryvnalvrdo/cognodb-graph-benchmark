import argparse
import csv
import importlib
import json
import random
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

RESULTS_DIR = ROOT / "results"
RESULTS_DIR.mkdir(exist_ok=True)

DATA_DIR = ROOT / "data"
SAMPLE_SIZE = 100


def _load_node_ids() -> list[int]:
    with open(DATA_DIR / "nodes.csv") as f:
        return [int(row["id"]) for row in csv.DictReader(f)]


def _run_bolt(platform: str, dry_run: bool, skip_load: bool) -> dict:
    from loaders.driver_bolt import get_driver
    from workloads import traversal, lookup, aggregation, mixed

    result = {"platform": platform, "timestamp": datetime.now(timezone.utc).isoformat()}

    if dry_run:
        driver = get_driver(platform.upper())
        driver.close()
        print(f"[{platform}] dry-run: connectivity OK")
        return result

    loader = importlib.import_module(f"loaders.{platform}")
    result["load"] = loader.run().get("load", {}) if not skip_load else "skipped"

    driver = get_driver(platform.upper())
    node_ids = _load_node_ids()
    sample = random.sample(node_ids, min(SAMPLE_SIZE, len(node_ids)))

    result["traversal"] = traversal.run_bolt(driver, sample, platform)
    result["lookup"] = lookup.run_bolt(driver, sample, platform)
    result["aggregation"] = aggregation.run_bolt(driver, sample, platform)
    result["mixed"] = mixed.run_bolt(driver, node_ids, platform)

    driver.close()
    return result



def _run_arangodb(dry_run: bool, skip_load: bool) -> dict:
    from loaders import arangodb as arango_loader
    from loaders.arangodb import get_db
    from workloads import traversal, lookup, aggregation, mixed

    result = {"platform": "arangodb", "timestamp": datetime.now(timezone.utc).isoformat()}

    if dry_run:
        db = get_db()
        print("[arangodb] dry-run: connectivity OK")
        return result

    result["load"] = arango_loader.run().get("load", {}) if not skip_load else "skipped"
    db = get_db()
    node_ids = _load_node_ids()
    sample = random.sample(node_ids, min(SAMPLE_SIZE, len(node_ids)))

    result["traversal"] = traversal.run_arangodb(db, sample)
    result["lookup"] = lookup.run_arangodb(db, sample)
    result["aggregation"] = aggregation.run_arangodb(db, sample)
    result["mixed"] = mixed.run_arangodb(db, node_ids)

    return result


def main():
    parser = argparse.ArgumentParser(description="CognoDB Benchmark Harness")
    parser.add_argument("--platform", required=True, choices=["cognodb", "neo4j", "memgraph", "arangodb"])
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--skip-load", action="store_true")
    args = parser.parse_args()

    platform = args.platform
    print(f"\n{'='*60}")
    print(f"  Benchmark — {platform.upper()}")
    print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*60}\n")

    t_start = time.perf_counter()

    if platform in ("cognodb", "neo4j", "memgraph"):
        result = _run_bolt(platform, args.dry_run, args.skip_load)
    else:
        result = _run_arangodb(args.dry_run, args.skip_load)

    result["total_benchmark_sec"] = round(time.perf_counter() - t_start, 2)

    out_path = RESULTS_DIR / f"{platform}.json"
    with open(out_path, "w") as f:
        json.dump(result, f, indent=2)

    print(f"\nResults saved to {out_path} ({result['total_benchmark_sec']}s)")


if __name__ == "__main__":
    main()
