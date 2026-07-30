#!/usr/bin/env python3
"""Download and structurally validate a bounded batch of iOSObscura IPAs.

This intentionally performs static package inspection only. It never executes IPA code.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import plistlib
import struct
import sys
import tempfile
import urllib.parse
import urllib.request
import zipfile
from pathlib import Path
from typing import Any

ARCHIVE_ID = "iOSObscura"
METADATA_URL = f"https://archive.org/metadata/{ARCHIVE_ID}"
DOWNLOAD_ROOT = f"https://archive.org/download/{ARCHIVE_ID}/"
CPU_NAMES = {
    7: "arm",
    12: "arm",
    0x0100000C: "arm64",
    0x01000007: "x86_64",
}


def fetch_json(url: str) -> dict[str, Any]:
    req = urllib.request.Request(url, headers={"User-Agent": "LiveContainer-IPA-Validator/1.0"})
    with urllib.request.urlopen(req, timeout=60) as response:
        return json.load(response)


def download(url: str, destination: Path, max_bytes: int) -> tuple[int, str]:
    req = urllib.request.Request(url, headers={"User-Agent": "LiveContainer-IPA-Validator/1.0"})
    digest = hashlib.sha256()
    total = 0
    with urllib.request.urlopen(req, timeout=120) as response, destination.open("wb") as out:
        while True:
            chunk = response.read(1024 * 1024)
            if not chunk:
                break
            total += len(chunk)
            if total > max_bytes:
                raise ValueError(f"download exceeds configured limit ({max_bytes} bytes)")
            digest.update(chunk)
            out.write(chunk)
    return total, digest.hexdigest()


def macho_arches(data: bytes) -> list[str]:
    if len(data) < 8:
        return []
    magic_be = struct.unpack(">I", data[:4])[0]
    magic_le = struct.unpack("<I", data[:4])[0]
    arches: list[str] = []

    if magic_be in (0xCAFEBABE, 0xCAFEBABF):
        is_64 = magic_be == 0xCAFEBABF
        count = struct.unpack(">I", data[4:8])[0]
        entry_size = 32 if is_64 else 20
        for index in range(min(count, 32)):
            offset = 8 + index * entry_size
            if offset + 4 > len(data):
                break
            cpu = struct.unpack(">I", data[offset : offset + 4])[0]
            arches.append(CPU_NAMES.get(cpu, f"cpu-{cpu:#x}"))
        return sorted(set(arches))

    if magic_be in (0xFEEDFACE, 0xFEEDFACF):
        cpu = struct.unpack(">I", data[4:8])[0]
        return [CPU_NAMES.get(cpu, f"cpu-{cpu:#x}")]
    if magic_le in (0xFEEDFACE, 0xFEEDFACF):
        cpu = struct.unpack("<I", data[4:8])[0]
        return [CPU_NAMES.get(cpu, f"cpu-{cpu:#x}")]
    return []


def inspect_ipa(path: Path) -> dict[str, Any]:
    result: dict[str, Any] = {"valid_zip": False, "loadable_candidate": False}
    with zipfile.ZipFile(path) as archive:
        bad_member = archive.testzip()
        if bad_member:
            raise ValueError(f"CRC failure in {bad_member}")
        result["valid_zip"] = True
        names = archive.namelist()
        plist_names = [n for n in names if n.startswith("Payload/") and n.count("/") == 2 and n.endswith(".app/Info.plist")]
        if not plist_names:
            raise ValueError("missing top-level Payload/*.app/Info.plist")
        plist_name = sorted(plist_names)[0]
        info = plistlib.loads(archive.read(plist_name))
        executable = info.get("CFBundleExecutable")
        app_prefix = plist_name[: -len("Info.plist")]
        executable_name = app_prefix + str(executable) if executable else ""
        if not executable or executable_name not in names:
            raise ValueError("missing declared app executable")
        binary = archive.read(executable_name)
        arches = macho_arches(binary)
        result.update(
            {
                "bundle_id": info.get("CFBundleIdentifier"),
                "display_name": info.get("CFBundleDisplayName") or info.get("CFBundleName"),
                "version": info.get("CFBundleShortVersionString"),
                "minimum_os": info.get("MinimumOSVersion"),
                "executable": executable,
                "architectures": arches,
                "armv7_candidate": "arm" in arches,
                "arm64_native": "arm64" in arches,
                "encrypted": None,
                "loadable_candidate": bool(arches and ("arm" in arches or "arm64" in arches)),
            }
        )
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--offset", type=int, default=0)
    parser.add_argument("--limit", type=int, default=25)
    parser.add_argument("--max-file-mib", type=int, default=750)
    parser.add_argument("--output", default="validation-results.json")
    args = parser.parse_args()
    if args.offset < 0 or args.limit < 1 or args.limit > 250:
        parser.error("offset must be >= 0 and limit must be between 1 and 250")

    metadata = fetch_json(METADATA_URL)
    files = []
    for item in metadata.get("files", []):
        name = item.get("name", "")
        if name.lower().endswith(".ipa"):
            files.append(item)
    files.sort(key=lambda item: item.get("name", "").casefold())
    selected = files[args.offset : args.offset + args.limit]
    results: list[dict[str, Any]] = []

    with tempfile.TemporaryDirectory(prefix="iosobscura-") as temp_dir:
        root = Path(temp_dir)
        for index, item in enumerate(selected, start=args.offset):
            name = item["name"]
            record: dict[str, Any] = {
                "archive_index": index,
                "archive_name": name,
                "archive_size": int(item.get("size", 0) or 0),
                "archive_md5": item.get("md5"),
                "status": "failed",
            }
            try:
                encoded_name = urllib.parse.quote(name, safe="/")
                local_path = root / f"{index}.ipa"
                size, sha256 = download(DOWNLOAD_ROOT + encoded_name, local_path, args.max_file_mib * 1024 * 1024)
                record.update({"downloaded_size": size, "sha256": sha256})
                record.update(inspect_ipa(local_path))
                record["status"] = "validated"
            except Exception as exc:  # keep the batch progressing
                record["error"] = f"{type(exc).__name__}: {exc}"
            results.append(record)
            print(f"[{index + 1}/{len(files)}] {record['status']}: {name}", flush=True)

    summary = {
        "archive_id": ARCHIVE_ID,
        "total_ipa_files": len(files),
        "offset": args.offset,
        "requested_limit": args.limit,
        "processed": len(results),
        "validated": sum(r["status"] == "validated" for r in results),
        "failed": sum(r["status"] != "validated" for r in results),
        "armv7_candidates": sum(bool(r.get("armv7_candidate")) for r in results),
        "arm64_native": sum(bool(r.get("arm64_native")) for r in results),
        "results": results,
    }
    Path(args.output).write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    print(json.dumps({key: value for key, value in summary.items() if key != "results"}, indent=2))
    return 0 if results else 2


if __name__ == "__main__":
    sys.exit(main())
