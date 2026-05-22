"""Extract response bodies (HTML) from a HAR file to separate files.

Usage:
  uv run python tools/extract_har_html.py storage/recon/hike_taiwan_gov_tw.har \\
      --out-dir storage/recon/extracted --path-contains apply_1
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from urllib.parse import urlparse


def slugify_path(url: str) -> str:
    p = urlparse(url)
    raw = (p.path + "_" + p.query).strip("_/")
    return re.sub(r"[^A-Za-z0-9_\-=&.?]+", "_", raw)[:120] or "index"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("har", type=Path)
    ap.add_argument("--out-dir", type=Path, default=Path("storage/recon/extracted"))
    ap.add_argument("--path-contains", default="", help="only extract entries whose URL path contains this")
    ap.add_argument("--only-html", action="store_true", default=True)
    args = ap.parse_args()

    args.out_dir.mkdir(parents=True, exist_ok=True)
    data = json.loads(args.har.read_text(encoding="utf-8"))
    entries = data["log"]["entries"]

    extracted = 0
    for i, e in enumerate(entries):
        url = e["request"]["url"]
        if args.path_contains and args.path_contains not in url:
            continue
        method = e["request"]["method"]
        content = e["response"].get("content", {})
        mime = content.get("mimeType", "")
        if args.only_html and "text/html" not in mime:
            continue
        text = content.get("text")
        if not text:
            continue
        slug = f"{i:03d}_{method}_{slugify_path(url)}.html"
        out = args.out_dir / slug
        out.write_text(text, encoding="utf-8")
        print(f"[{i}] {method} {urlparse(url).path}  ({len(text)} chars) → {out.name}")
        extracted += 1

    print(f"\nextracted {extracted} files to {args.out_dir}")


if __name__ == "__main__":
    main()
