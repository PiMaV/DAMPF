#!/usr/bin/env python3
# benchmark.py - Compare sequential vs parallel indexer performance.
# Usage: python scripts/benchmark.py [path]  (path = root dir to index; default: temp dir with synthetic files)

from __future__ import annotations

import argparse
import os
import sys
import tempfile
import time
from pathlib import Path

# Add project root for imports
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from indexer import run_indexer


def _log(msg: str) -> None:
    print(msg)


def run_benchmark(root: Path, output: Path, config: dict) -> tuple[float, int]:
    """Run indexer with timing. Returns (total_seconds, file_count)."""
    logs: list[str] = []

    def log_cb(msg: str) -> None:
        logs.append(msg)
        _log(msg)

    cfg = dict(config)
    cfg["log_callback"] = log_cb
    t0 = time.perf_counter()
    rows, groups = run_indexer(root, output, cfg)
    dt = time.perf_counter() - t0
    return dt, len(rows)


def main() -> None:
    ap = argparse.ArgumentParser(description="Benchmark DAMPF indexer: sequential vs parallel")
    ap.add_argument("path", nargs="?", help="Root dir to index (default: temp dir with synthetic files)")
    ap.add_argument("-n", "--files", type=int, default=500, help="Synthetic file count if no path (default: 500)")
    ap.add_argument("-w", "--workers", type=int, default=None, help="parallel_max_workers (default: cpu_count-1)")
    args = ap.parse_args()

    if args.path:
        root = Path(args.path).resolve()
        if not root.is_dir():
            print(f"Error: not a directory: {root}")
            sys.exit(1)
        output = root / "_benchmark_out"
        output.mkdir(parents=True, exist_ok=True)
        print(f"Indexing from {root}")
    else:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            n = args.files
            for i in range(n):
                (root / f"2024-01-15_run1_rep{i}_500us.tif").touch()
            output = root / "_benchmark_out"
            output.mkdir(parents=True, exist_ok=True)
            print(f"Created {n} synthetic files in temp dir")
            _run_comparison(root, output, args.workers)
        return

    _run_comparison(root, output, args.workers)


def _run_comparison(root: Path, output: Path, max_workers: int | None) -> None:
    workers = max_workers if max_workers is not None else max(1, (os.cpu_count() or 1) - 1)

    # Sequential (force threshold high so we never use parallel)
    cfg_seq = {"parallel_threshold": 999999, "parallel_max_workers": 1}
    print("\n--- Sequential ---")
    dt_seq, n_seq = run_benchmark(root, output, cfg_seq)
    print(f"  Total: {dt_seq:.3f}s, {n_seq} files, {n_seq / max(0.001, dt_seq):.0f} files/s")

    # Parallel
    cfg_par = {"parallel_threshold": 2, "parallel_max_workers": workers}
    print("\n--- Parallel (workers=%d) ---" % workers)
    dt_par, n_par = run_benchmark(root, output, cfg_par)
    print(f"  Total: {dt_par:.3f}s, {n_par} files, {n_par / max(0.001, dt_par):.0f} files/s")

    print("\n--- Summary ---")
    if dt_seq > 0:
        speedup = dt_seq / dt_par
        print(f"  Speedup: {speedup:.2f}x")
        print(f"  Sequential: {dt_seq:.3f}s | Parallel: {dt_par:.3f}s")


if __name__ == "__main__":
    main()
