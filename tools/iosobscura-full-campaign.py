#!/usr/bin/env python3
"""Run a resumable, single-runner compatibility campaign over iOSObscura.

Each IPA is streamed to temporary storage, validated against one built LiveContainer IPA,
then deleted. Results are append-only JSONL so an interrupted self-hosted runner can resume.
This is a static/package compatibility campaign; physical iOS execution remains a separate gate.
"""
from __future__ import annotations

import argparse
import concurrent.futures
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path

BASE = "https://archive.org/download/iOSObscura/"
FILES_XML = BASE + "iOSObscura_files.xml"
UA = "LiveContainer-iOSObscura-full-campaign/1.0"


def download(url: str, path: Path, retries: int = 4) -> None:
    last = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=180) as src, path.open("wb") as dst:
                while True:
                    chunk = src.read(1024 * 1024)
                    if not chunk:
                        break
                    dst.write(chunk)
            return
        except Exception as exc:
            last = exc
            path.unlink(missing_ok=True)
            time.sleep(min(30, 2 ** attempt))
    raise RuntimeError(f"download failed after {retries} attempts: {last!r}")


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def load_catalog(xml_path: Path, prefixes: list[str]) -> list[dict]:
    root = ET.parse(xml_path).getroot()
    entries = []
    for node in root.findall("file"):
        name = node.attrib.get("name", "")
        if not name.lower().endswith(".ipa"):
            continue
        if prefixes and not any(name.startswith(p) for p in prefixes):
            continue
        try:
            size = int(node.findtext("size") or "0")
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
    entries.sort(key=lambda x: x["name"].casefold())
    return entries


def completed_names(results_path: Path) -> set[str]:
    done: set[str] = set()
    if not results_path.exists():
        return done
    with results_path.open(errors="replace") as f:
        for line in f:
            try:
                row = json.loads(line)
                if row.get("name"):
                    done.add(row["name"])
            except json.JSONDecodeError:
                continue
    return done


def validate_one(entry: dict, index: int, livecontainer_ipa: Path, reports_dir: Path, temp_root: Path) -> dict:
    token = hashlib.sha256(entry["name"].encode()).hexdigest()[:16]
    ipa = temp_root / f"{index:05d}-{token}.ipa"
    report = reports_dir / f"{index:05d}-{token}.json"
    started = time.time()
    try:
        download(entry["url"], ipa)
        actual_size = ipa.stat().st_size
        cmd = [
            sys.executable, "tools/compat32-report.py", str(ipa),
            "--livecontainer-ipa", str(livecontainer_ipa),
            "--output", str(report),
        ]
        proc = subprocess.run(cmd, text=True, capture_output=True, timeout=600)
        parsed = {}
        if report.exists():
            try:
                parsed = json.loads(report.read_text())
            except Exception:
                parsed = {}
        return {
            "name": entry["name"], "url": entry["url"], "declaredSize": entry["size"],
            "actualSize": actual_size, "sha256": sha256(ipa), "exitCode": proc.returncode,
            "result": parsed.get("result", "error"), "failures": parsed.get("failures", []),
            "warnings": parsed.get("warnings", []), "bundleIdentifier": parsed.get("guest", {}).get("bundleIdentifier"),
            "armv7": parsed.get("guest", {}).get("armv7"), "arm64": parsed.get("guest", {}).get("arm64"),
            "decrypted": parsed.get("guest", {}).get("decrypted"), "report": str(report),
            "seconds": round(time.time() - started, 3), "stdoutTail": proc.stdout[-2000:],
            "stderrTail": proc.stderr[-2000:],
        }
    except subprocess.TimeoutExpired as exc:
        return {"name": entry["name"], "url": entry["url"], "result": "error", "error": "validator timeout", "seconds": round(time.time()-started, 3)}
    except Exception as exc:
        return {"name": entry["name"], "url": entry["url"], "result": "error", "error": repr(exc), "seconds": round(time.time()-started, 3)}
    finally:
        ipa.unlink(missing_ok=True)


def aggregate(results_path: Path, catalog_count: int, output: Path) -> dict:
    rows = []
    if results_path.exists():
        with results_path.open(errors="replace") as f:
            for line in f:
                try:
                    rows.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
    statuses = Counter(r.get("result", "error") for r in rows)
    failure_classes = Counter()
    warning_classes = Counter()
    for row in rows:
        for item in row.get("failures", []): failure_classes[item] += 1
        for item in row.get("warnings", []): warning_classes[item] += 1
        if row.get("error"): failure_classes[row["error"]] += 1
    summary = {
        "schemaVersion": 1, "catalogCount": catalog_count, "processed": len(rows),
        "remaining": max(0, catalog_count - len(rows)), "statusCounts": dict(statuses),
        "failureClasses": dict(failure_classes.most_common()),
        "warningClasses": dict(warning_classes.most_common()),
        "complete": len(rows) >= catalog_count,
        "scope": "static/package compatibility against one LiveContainer build; not physical-device runtime proof",
    }
    output.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    return summary


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--authorized", action="store_true")
    ap.add_argument("--livecontainer-ipa", type=Path, required=True)
    ap.add_argument("--output-dir", type=Path, default=Path("iosobscura-full-campaign"))
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--prefix", action="append", default=[])
    ap.add_argument("--stop-after", type=int, default=0, help="0 means process all remaining entries")
    args = ap.parse_args()
    if not args.authorized:
        raise SystemExit("--authorized is required")
    if not args.livecontainer_ipa.is_file():
        raise SystemExit(f"LiveContainer IPA not found: {args.livecontainer_ipa}")
    if not 1 <= args.workers <= 16:
        raise SystemExit("workers must be 1..16")

    out = args.output_dir
    out.mkdir(parents=True, exist_ok=True)
    reports_dir = out / "reports"
    reports_dir.mkdir(exist_ok=True)
    xml_path = out / "iOSObscura_files.xml"
    if not xml_path.exists():
        download(FILES_XML, xml_path)
    prefixes = args.prefix or ["Homebrew IPAs/", "PossiblyBroken/", "iOS 4/", "iOS 5/", "iOS 6/", "iOS 7/", "iOS 8/", "iPhoneOS 2/", "iPhoneOS 3/"]
    entries = load_catalog(xml_path, prefixes)
    (out / "catalog.json").write_text(json.dumps({"count": len(entries), "prefixes": prefixes, "entries": entries}, indent=2) + "\n")

    results_path = out / "results.jsonl"
    done = completed_names(results_path)
    pending = [(i, e) for i, e in enumerate(entries) if e["name"] not in done]
    if args.stop_after > 0:
        pending = pending[:args.stop_after]

    with tempfile.TemporaryDirectory(prefix="iosobscura-campaign-") as td, results_path.open("a", buffering=1) as sink:
        temp_root = Path(td)
        with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as pool:
            futures = {pool.submit(validate_one, e, i, args.livecontainer_ipa, reports_dir, temp_root): e for i, e in pending}
            for n, future in enumerate(concurrent.futures.as_completed(futures), 1):
                row = future.result()
                sink.write(json.dumps(row, sort_keys=True) + "\n")
                sink.flush()
                os.fsync(sink.fileno())
                if n % 25 == 0:
                    summary = aggregate(results_path, len(entries), out / "summary.json")
                    print(json.dumps(summary, sort_keys=True), flush=True)

    summary = aggregate(results_path, len(entries), out / "summary.json")
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0 if summary["complete"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
