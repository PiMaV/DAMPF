# filename_semantic_indexer.py
# VS Code friendly: edit variables below, run as a script. Uses indexer module.

from pathlib import Path

from dampf.indexer import (
    DEFAULT_ALLOWED_SUFFIXES,
    DEFAULT_MODALITY_MAP,
    DEFAULT_STOPWORDS,
    run_indexer,
    write_csv,
    write_jsonl,
)

# =========================
# USER SETTINGS (edit here)
# =========================
ROOT_DIR = r"C:\DATA\MEASUREMENTS"
OUTPUT_DIR = r"C:\DATA\MEASUREMENTS\_index"

RECURSIVE = True
INCLUDE_HIDDEN = False
FOLDER_TOKEN_DEPTH = 99
ALLOWED_SUFFIXES = DEFAULT_ALLOWED_SUFFIXES
STOPWORDS = DEFAULT_STOPWORDS
MODALITY_MAP = DEFAULT_MODALITY_MAP


def main() -> None:
    config = {
        "allowed_suffixes": ALLOWED_SUFFIXES,
        "folder_token_depth": FOLDER_TOKEN_DEPTH,
        "recursive": RECURSIVE,
        "include_hidden": INCLUDE_HIDDEN,
        "stopwords": STOPWORDS,
        "modality_map": MODALITY_MAP,
    }
    rows, _ = run_indexer(ROOT_DIR, OUTPUT_DIR, config)

    out_dir = Path(OUTPUT_DIR).expanduser().resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    jsonl_path = out_dir / "index.jsonl"
    csv_path = out_dir / "index.csv"

    write_jsonl(rows, jsonl_path)
    write_csv(rows, csv_path)

    if rows:
        confs = [r["confidence"] for r in rows]
        avg_conf = sum(confs) / len(confs)
        hi = sum(1 for c in confs if c >= 0.8)
        med = sum(1 for c in confs if 0.5 <= c < 0.8)
        lo = sum(1 for c in confs if c < 0.5)
        print(f"Indexed files: {len(rows)}")
        print(f"Avg confidence: {avg_conf:.3f} | >=0.8: {hi} | 0.5-0.8: {med} | <0.5: {lo}")
        print(f"Wrote: {jsonl_path}")
        print(f"Wrote: {csv_path}")
    else:
        print("No matching files found. Check ROOT_DIR and ALLOWED_SUFFIXES.")


if __name__ == "__main__":
    main()
