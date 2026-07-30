#!/usr/bin/env python3
"""Download and statically validate one resumable iOSObscura campaign batch.

The script never executes guest code and never republishes IPA files. Each archive IPA is
streamed to temporary storage, checked against the exact LiveContainer IPA supplied by CI,
then deleted. Compact JSON/JSONL reports are retained for aggregation.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import tempfile
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
import zipfile
from collections import Counter
from pathlib import Path

BASE = "https://archive.org/download/iOSObscura/"
FILES_XML = BASE + "iOSObscura_files.xml"
DEFAULT_PREFIXES = [
    "Homebrew IPAs/",
    "PossiblyBroken/",
    "iOS 4/",
    "iOS 5/",
    "iOS 6/",
    "iOS 7/",
    "iOS 8/",
    "iPhoneOS 2/",
    "iPhoneOS 3/",
]
UA = "NightVibes33-LiveContainer-iOSObscura-Campaign/2.0"


def digest_file(path: Path, algorithm: str) -> str:
    h = hashlib.new(algorithm)
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def download(url: str, destination: Path, retries: int = 5) -> None:
    last_error: Exception | None = None
    for attempt in range(retries):
        try:
            request = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(request, timeout=240) as source, destination.open("wb") as sink:
                while True:
                    chunk = source.read(1024 * 1024)
                    if not chunk:
                        break
                    sink.write(chunk)
            return
        except Exception as exc:
            last_error = exc
            destination.unlink(missing_ok=True)
            if attempt + 1 < retries:
                time.sleep(min(45, 2 ** attempt))
    raise RuntimeError(f"download failed after {retries} attempts: {last_error!r}")


def load_catalog(xml_path: Path, prefixes: list[str]) -> list[dict]:
    root = ET.parse(xml_path).getroot()
    entries: list[dict] = []
    for node in root.findall("file"):
        name = node.attrib.get("name", "")
        if not name.lower().endswith(".ipa"):
            continue
        if prefixes and not any(name.startswith(prefix) for prefix in prefixes):
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
    entries.sort(key=lambda item: item["name"].casefold())
    return entries


def verify_livecontainer_ipa(path: Path) -> dict:
    required_files = {
        "Payload/LiveContainer.app/LiveExec32.app/Info.plist",
        "Payload/LiveContainer.app/LiveExec32.app/LiveExec32",
        "Payload/LiveContainer.app/LiveExec32.app/LiveExec32Plugin.dylib",
    }
    required_markers = [
        b"LC32Main",
        b"LC32_GUEST_EXECUTABLE",
        b"LC32_GUEST_DYLD",
        b"LC32_GUEST_ROOTFS",
    ]
    obsolete_marker = b"JIT is required to run 32-bit apps through LiveExec32"
    with zipfile.ZipFile(path) as archive:
        names = set(archive.namelist())
        missing = sorted(required_files - names)
        if missing:
            raise RuntimeError("current LiveContainer IPA is missing: " + ", ".join(missing))
        searchable = b""
        for name in names:
            if name.startswith("Payload/LiveContainer.app/") and not name.endswith("/"):
                try:
                    searchable += archive.read(name)
                except Exception:
                    pass
        missing_markers = [marker.decode() for marker in required_markers if marker not in searchable]
        if missing_markers:
            raise RuntimeError("current LiveContainer IPA lacks LC32 markers: " + ", ".join(missing_markers))
        if obsolete_marker in searchable:
            raise RuntimeError("current LiveContainer IPA still contains the obsolete JIT gate")
    return {
        "ipaSHA256": digest_file(path, "sha256"),
        "requiredFiles": sorted(required_files),
        "requiredMarkers": [marker.decode() for marker in required_markers],
        "obsoleteJITGateAbsent": True,
    }


def validate_one(entry: dict, global_index: int, livecontainer_ipa: Path, reports_dir: Path, temp_dir: Path) -> dict:
    token = hashlib.sha256(entry["name"].encode("utf-8")).hexdigest()[:16]
    ipa_path = temp_dir / f"{global_index:06d}-{token}.ipa"
    report_path = reports_dir / f"{global_index:06d}-{token}.json"
    started = time.time()
    base_row = {
        "globalIndex": global_index,
        "archiveName": entry["name"],
        "archiveUrl": entry["url"],
        "declaredSize": entry["size"],
        "archiveMD5": entry.get("md5"),
        "archiveSHA1": entry.get("sha1"),
    }
    try:
        download(entry["url"], ipa_path)
        actual_size = ipa_path.stat().st_size
        actual_md5 = digest_file(ipa_path, "md5")
        actual_sha1 = digest_file(ipa_path, "sha1")
        actual_sha256 = digest_file(ipa_path, "sha256")

        integrity_errors: list[str] = []
        if entry["size"] and actual_size != entry["size"]:
            integrity_errors.append(f"size mismatch: expected {entry['size']}, got {actual_size}")
        if entry.get("md5") and actual_md5.lower() != entry["md5"].lower():
            integrity_errors.append("MD5 mismatch against Internet Archive metadata")
        if entry.get("sha1") and actual_sha1.lower() != entry["sha1"].lower():
            integrity_errors.append("SHA-1 mismatch against Internet Archive metadata")

        command = [
            sys.executable,
            "tools/compat32-report.py",
            str(ipa_path),
            "--livecontainer-ipa",
            str(livecontainer_ipa),
            "--output",
            str(report_path),
        ]
        process = subprocess.run(command, text=True, capture_output=True, timeout=900)
        report: dict = {}
        if report_path.exists():
            try:
                report = json.loads(report_path.read_text())
            except Exception as exc:
                integrity_errors.append(f"report parse failed: {exc!r}")

        guest = report.get("guest", {})
        return {
            **base_row,
            "actualSize": actual_size,
            "ipaSHA256": actual_sha256,
            "integrityPassed": not integrity_errors,
            "integrityErrors": integrity_errors,
            "validatorExitCode": process.returncode,
            "result": report.get("result", "error"),
            "bundleIdentifier": guest.get("bundleIdentifier"),
            "bundleVersion": guest.get("bundleVersion"),
            "shortVersion": guest.get("shortVersion"),
            "armv7": guest.get("armv7"),
            "arm64": guest.get("arm64"),
            "decrypted": guest.get("decrypted"),
            "dependencies": guest.get("dependencies", []),
            "failures": report.get("failures", []),
            "warnings": report.get("warnings", []),
            "liveContainer": report.get("liveContainer", {}),
            "reportFile": report_path.name,
            "seconds": round(time.time() - started, 3),
            "stdoutTail": process.stdout[-2000:],
            "stderrTail": process.stderr[-2000:],
        }
    except subprocess.TimeoutExpired:
        return {**base_row, "result": "error", "error": "validator timeout", "seconds": round(time.time() - started, 3)}
    except Exception as exc:
        return {**base_row, "result": "error", "error": repr(exc), "seconds": round(time.time() - started, 3)}
    finally:
        ipa_path.unlink(missing_ok=True)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--authorized", action="store_true")
    parser.add_argument("--download", action="store_true")
    parser.add_argument("--prefix", action="append", default=[])
    parser.add_argument("--start-index", type=int, default=0)
    parser.add_argument("--batch-size", type=int, default=400, help="0 means all remaining entries")
    parser.add_argument("--shard-index", type=int, default=0)
    parser.add_argument("--shard-count", type=int, default=20)
    parser.add_argument("--max-bytes", type=int, default=4 * 1024 * 1024 * 1024)
    parser.add_argument("--livecontainer-ipa", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()

    if args.download and not args.authorized:
        parser.error("--download requires --authorized")
    if args.start_index < 0 or args.batch_size < 0:
        parser.error("start-index and batch-size must be non-negative")
    if args.shard_count < 1 or not 0 <= args.shard_index < args.shard_count:
        parser.error("invalid shard configuration")
    if args.max_bytes < 1:
        parser.error("max-bytes must be positive")
    if not args.livecontainer_ipa.is_file():
        parser.error(f"LiveContainer IPA not found: {args.livecontainer_ipa}")

    output = args.output_dir
    output.mkdir(parents=True, exist_ok=True)
    reports_dir = output / "reports"
    reports_dir.mkdir(exist_ok=True)
    metadata_path = output / "iOSObscura_files.xml"
    download(FILES_XML, metadata_path)

    prefixes = args.prefix or DEFAULT_PREFIXES
    catalog = load_catalog(metadata_path, prefixes)
    end = len(catalog) if args.batch_size == 0 else min(len(catalog), args.start_index + args.batch_size)
    batch = list(enumerate(catalog[args.start_index:end], start=args.start_index))
    shard = [(index, entry) for relative, (index, entry) in enumerate(batch) if relative % args.shard_count == args.shard_index]

    selected: list[tuple[int, dict]] = []
    skipped_for_budget: list[dict] = []
    declared_bytes = 0
    for index, entry in shard:
        size = max(0, int(entry.get("size") or 0))
        if size and declared_bytes + size > args.max_bytes:
            skipped_for_budget.append({"globalIndex": index, "name": entry["name"], "size": size})
            continue
        selected.append((index, entry))
        declared_bytes += size

    catalog_report = {
        "schemaVersion": 2,
        "source": "https://archive.org/download/iOSObscura",
        "prefixes": prefixes,
        "totalCatalogIPAs": len(catalog),
        "batchStart": args.start_index,
        "batchEndExclusive": end,
        "batchCount": len(batch),
        "shardIndex": args.shard_index,
        "shardCount": args.shard_count,
        "selectedCount": len(selected),
        "selectedDeclaredBytes": declared_bytes,
        "maxBytes": args.max_bytes,
        "skippedForByteBudget": skipped_for_budget,
        "entries": [{"globalIndex": index, **entry} for index, entry in selected],
    }
    (output / "catalog.json").write_text(json.dumps(catalog_report, indent=2, sort_keys=True) + "\n")

    if not args.download:
        print(json.dumps(catalog_report, indent=2, sort_keys=True))
        return 0

    livecontainer_profile = verify_livecontainer_ipa(args.livecontainer_ipa)
    app_sha256 = livecontainer_profile["ipaSHA256"]
    rows: list[dict] = []
    with tempfile.TemporaryDirectory(prefix="iosobscura-gh-") as temporary:
        temp_dir = Path(temporary)
        for position, (global_index, entry) in enumerate(selected, 1):
            row = validate_one(entry, global_index, args.livecontainer_ipa, reports_dir, temp_dir)
            rows.append(row)
            print(f"[{position}/{len(selected)}] index={global_index} result={row.get('result')} {entry['name']}", flush=True)

    results_path = output / "results.jsonl"
    with results_path.open("w", encoding="utf-8") as sink:
        for row in rows:
            sink.write(json.dumps(row, sort_keys=True) + "\n")

    result_counts = Counter(row.get("result", "error") for row in rows)
    classifications = Counter()
    for row in rows:
        if row.get("result") == "pass" and row.get("armv7") and not row.get("arm64") and row.get("decrypted"):
            classifications["armv7-current-app-static-pass"] += 1
        elif row.get("arm64"):
            classifications["contains-arm64"] += 1
        elif row.get("armv7") and not row.get("decrypted"):
            classifications["encrypted-armv7"] += 1
        elif row.get("armv7"):
            classifications["armv7-static-blocked"] += 1
        else:
            classifications["not-armv7-or-invalid"] += 1

    summary = {
        "schemaVersion": 2,
        "totalCatalogIPAs": len(catalog),
        "batchStart": args.start_index,
        "batchEndExclusive": end,
        "shardIndex": args.shard_index,
        "shardCount": args.shard_count,
        "selected": len(selected),
        "processed": len(rows),
        "skippedForByteBudget": len(skipped_for_budget),
        "resultCounts": dict(result_counts),
        "classifications": dict(classifications),
        "liveContainerIPASHA256": app_sha256,
        "liveContainerRuntimeProfile": livecontainer_profile,
        "scope": "static archive integrity + package/runtime compatibility; no guest code execution and no gameplay claim",
    }
    (output / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
