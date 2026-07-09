"""Mining engine for Holo/Sim.

Splits large text or JSON files into hashed chunks and writes a manifest.
This does not append to HoloChain. Collector ingestion comes after mining.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from pathlib import Path
from typing import Any, Dict, List


DEFAULT_CHUNK_SIZE = 40000


def sha256_short(text: str, length: int = 12) -> str:
    """Return short SHA-256 hash for a text chunk."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:length]


def load_text(path: str | Path) -> str:
    """Load source file as text."""
    source = Path(path)
    return source.read_text(encoding="utf-8", errors="ignore")


def chunk_text(text: str, chunk_size: int = DEFAULT_CHUNK_SIZE) -> list[str]:
    """Split text into fixed-size chunks."""
    if chunk_size <= 0:
        raise ValueError("chunk_size must be greater than 0")

    return [text[i : i + chunk_size] for i in range(0, len(text), chunk_size)]


def mine_file(
    source_path: str | Path,
    output_dir: str | Path,
    *,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
) -> Dict[str, Any]:
    """Mine a large file into hashed chunk JSON files and a manifest."""
    source = Path(source_path).resolve()
    out_dir = Path(output_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    raw = load_text(source)
    parts = chunk_text(raw, chunk_size=chunk_size)

    manifest: List[Dict[str, Any]] = []

    for index, chunk in enumerate(parts, 1):
        chunk_hash = sha256_short(chunk)
        name = f"mine_{index:03}_{chunk_hash}.json"
        outpath = out_dir / name

        payload = {
            "index": index,
            "hash": chunk_hash,
            "source": str(source),
            "chars": len(chunk),
            "data": chunk,
        }

        outpath.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

        manifest.append(
            {
                "index": index,
                "hash": chunk_hash,
                "file": name,
                "chars": len(chunk),
            }
        )

    manifest_payload: Dict[str, Any] = {
        "source": str(source),
        "source_hash": hashlib.sha256(raw.encode("utf-8")).hexdigest(),
        "chunk_size": chunk_size,
        "total_chunks": len(parts),
        "created_at": int(time.time()),
        "chunks": manifest,
    }

    manifest_path = out_dir / f"manifest_{manifest_payload['created_at']}.json"
    manifest_path.write_text(
        json.dumps(manifest_payload, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    return {
        "status": "mined",
        "source": str(source),
        "output_dir": str(out_dir),
        "manifest": str(manifest_path),
        "total_chunks": len(parts),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Mine a large file into hashed Holo/Sim chunks.")
    parser.add_argument("source", help="Source file to mine")
    parser.add_argument("output", help="Output directory for mined chunks")
    parser.add_argument("--chunk-size", type=int, default=DEFAULT_CHUNK_SIZE)

    args = parser.parse_args()
    result = mine_file(args.source, args.output, chunk_size=args.chunk_size)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()