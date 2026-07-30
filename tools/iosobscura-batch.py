#!/usr/bin/env python3
"""Catalog and optionally validate bounded batches from archive.org/download/iOSObscura.

The tool always catalogs metadata. Binary downloads require --authorized and are bounded
by --max-files/--max-bytes. It is designed for GitHub Actions sharding.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

BASE = "https://archive.org/download/iOSObscura/"
FILES_XML = BASE + "iOSObscura_files.xml"


def fetch(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "LiveContainer-compat32/1.0"})
    with urllib.request.urlopen(req, timeout=120) as r:
        return r.read()


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--prefix", default="Homebrew IPAs/", help="Archive path prefix")
    ap.add_argument("--shard-index", type=int, default=0)
    ap.add_argument("--shard-count", type=int, default=1)
    ap.add_argument("--max-files", type=int, default=25)
    ap.add_argument("--max-bytes", type=int, default=2 * 1024 * 1024 * 1024)
    ap.add_argument("--authorized", action="store_true", help="Attest authorization to download/test selected files")
    ap.add_argument("--download", action="store_true")
    ap.add_argument("--livecontainer-ipa", type=Path)
    ap.add_argument("--output-dir", type=Path, default=Path("compat32-batch"))
    args = ap.parse_args()

    if args.shard_count < 1 or not (0 <= args.shard_index < args.shard_count):
        raise SystemExit("invalid shard index/count")
    if args.download and not args.authorized:
        raise SystemExit("--download requires --authorized")

    args.output_dir.mkdir(parents=True, exist_ok=True)
    xml_path = args.output_dir / "iOSObscura_files.xml"
    if not xml_path.exists():
        xml_path.write_bytes(fetch(FILES_XML))

    root = ET.parse(xml_path).getroot()
    entries = []
    for node in root.findall("file"):
        name = node.attrib.get("name", "")
        if not name.lower().endswith(".ipa") or not name.startswith(args.prefix):
            continue
        size_text = node.findtext("size") or "0"
        try:
            size = int(size_text)
        except ValueError:
            size = 0
        entries.append({
            "name": name,
            "size": size,
            "md5": node.findtext("md5"),
            "sha1": node.findtext("sha1"),
            "source": node.findtext("source"),
            "url": BASE + urllib.parse.quote(name, safe="/"),
        })

    entries.sort(key=lambda x: x["name"].lower())
    sharded = [e for i, e in enumerate(entries) if i % args.shard_count == args.shard_index]
    selected = []
    total = 0
    for e in sharded:
        if len(selected) >= args.max_files:
            break
        if e["size"] and total + e["size"] > args.max_bytes:
            continue
        selected.append(e)
        total += e["size"]

    catalog = {
        "source": "iOSObscura",
        "prefix": args.prefix,
        "totalMatching": len(entries),
        "shardIndex": args.shard_index,
        "shardCount": args.shard_count,
        "selectedCount": len(selected),
        "selectedBytes": total,
        "downloadAuthorized": bool(args.authorized),
        "entries": selected,
    }
    (args.output_dir / "catalog.json").write_text(json.dumps(catalog, indent=2) + "\n")

    if not args.download:
        print(json.dumps(catalog, indent=2))
        return 0

    reports = []
    failures = 0
    downloads = args.output_dir / "downloads"
    reports_dir = args.output_dir / "reports"
    downloads.mkdir(exist_ok=True)
    reports_dir.mkdir(exist_ok=True)

    for idx, entry in enumerate(selected):
        safe_name = f"{idx:05d}-{Path(entry['name']).name}"
        ipa = downloads / safe_name
        try:
            ipa.write_bytes(fetch(entry["url"]))
            report = reports_dir / f"{idx:05d}.json"
            cmd = [sys.executable, "tools/compat32-report.py", str(ipa), "--output", str(report)]
            if args.livecontainer_ipa:
                cmd += ["--livecontainer-ipa", str(args.livecontainer_ipa)]
            proc = subprocess.run(cmd, text=True, capture_output=True)
            item = {
                "name": entry["name"],
                "url": entry["url"],
                "size": ipa.stat().st_size,
                "sha256": sha256(ipa),
                "exitCode": proc.returncode,
                "report": str(report),
                "stdoutTail": proc.stdout[-4000:],
                "stderrTail": proc.stderr[-4000:],
            }
            if proc.returncode != 0:
                failures += 1
            reports.append(item)
        except Exception as exc:
            failures += 1
            reports.append({"name": entry["name"], "error": repr(exc)})
        finally:
            if ipa.exists():
                ipa.unlink()

    summary = {
        "tested": len(reports),
        "passed": len(reports) - failures,
        "failed": failures,
        "items": reports,
    }
    (args.output_dir / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps(summary, indent=2))
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
