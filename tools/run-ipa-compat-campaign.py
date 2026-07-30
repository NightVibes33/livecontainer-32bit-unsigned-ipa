#!/usr/bin/env python3
"""Scan a large IPA library and rank clean-room compatibility bridge work.

The campaign is static and safe to shard. It never executes guest code. It reuses
validate-armv7-ipa.py so single-app and bulk results share the same parser.
"""
from __future__ import annotations

import argparse
import csv
import importlib.util
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


def load_validator(repo_root: Path):
    path = repo_root / "tools" / "validate-armv7-ipa.py"
    spec = importlib.util.spec_from_file_location("lc32_validator", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"could not load validator at {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def framework_key(path: str) -> str:
    if ".framework/" in path:
        return path.split(".framework/", 1)[0].rsplit("/", 1)[-1]
    leaf = path.rsplit("/", 1)[-1]
    if leaf.startswith("lib") and "." in leaf:
        return leaf.split(".", 1)[0]
    return leaf or path


def classify(result: dict[str, Any]) -> str:
    checks = result.get("checks", {})
    if not checks.get("validZip", False):
        return "invalid-ipa"
    if not checks.get("hasArmv7", False):
        return "no-armv7"
    if not checks.get("decrypted", False):
        return "encrypted"
    if checks.get("hasArm64", False):
        return "universal-armv7-arm64"
    return "armv7-cleanroom-candidate"


def scan_one(validator, ipa: Path) -> dict[str, Any]:
    result: dict[str, Any] = {
        "ipa": str(ipa),
        "checks": {},
        "errors": [],
    }
    try:
        import hashlib
        import plistlib
        import zipfile

        result["ipaSha256"] = validator.sha256(ipa)
        with zipfile.ZipFile(ipa) as zf:
            app_roots = sorted({
                name.split("/", 2)[1]
                for name in zf.namelist()
                if name.startswith("Payload/") and ".app/" in name
            })
            if len(app_roots) != 1:
                raise ValueError(f"expected exactly one Payload app, found {len(app_roots)}")
            app_root = f"Payload/{app_roots[0]}"
            info = plistlib.loads(zf.read(f"{app_root}/Info.plist"))
            executable_name = info.get("CFBundleExecutable")
            if not isinstance(executable_name, str) or not executable_name:
                raise ValueError("CFBundleExecutable is missing")
            executable_path = f"{app_root}/{executable_name}"
            executable = zf.read(executable_path)
            slices = validator.parse_macho(executable)
            has_armv7 = any(s["cputype"] == validator.CPU_TYPE_ARM for s in slices)
            has_arm64 = any(s["cputype"] == validator.CPU_TYPE_ARM64 for s in slices)
            encrypted = any((s["cryptid"] or 0) != 0 for s in slices)
            armv7_slices = [s for s in slices if s["cputype"] == validator.CPU_TYPE_ARM]
            dependencies: list[str] = []
            for slice_info in armv7_slices:
                dependencies.extend(slice_info.get("dylibs", []))
            dependencies = list(dict.fromkeys(dependencies))
            result.update({
                "bundleIdentifier": info.get("CFBundleIdentifier"),
                "bundleVersion": info.get("CFBundleVersion"),
                "displayName": info.get("CFBundleDisplayName") or info.get("CFBundleName"),
                "minimumOSVersion": info.get("MinimumOSVersion"),
                "sdkName": info.get("DTSDKName"),
                "deviceFamily": info.get("UIDeviceFamily"),
                "executable": executable_name,
                "executablePath": executable_path,
                "executableSha256": hashlib.sha256(executable).hexdigest(),
                "slices": slices,
                "dependencies": dependencies,
                "bridgeKeys": [framework_key(dep) for dep in dependencies],
            })
            result["checks"] = {
                "validZip": True,
                "singleAppBundle": True,
                "hasArmv7": has_armv7,
                "hasArm64": has_arm64,
                "armv7Only": has_armv7 and not has_arm64,
                "decrypted": not encrypted,
            }
    except Exception as exc:  # bulk campaigns must continue after malformed inputs
        result["errors"].append(str(exc))
    result["classification"] = classify(result)
    result["passedStaticGate"] = result["classification"] == "armv7-cleanroom-candidate"
    result["firstBridge"] = (result.get("bridgeKeys") or [None])[0]
    return result


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    fields = [
        "ipa", "bundleIdentifier", "displayName", "bundleVersion", "minimumOSVersion",
        "sdkName", "classification", "passedStaticGate", "firstBridge", "dependencyCount",
        "dependencies", "errors",
    ]
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({
                "ipa": row.get("ipa"),
                "bundleIdentifier": row.get("bundleIdentifier"),
                "displayName": row.get("displayName"),
                "bundleVersion": row.get("bundleVersion"),
                "minimumOSVersion": row.get("minimumOSVersion"),
                "sdkName": row.get("sdkName"),
                "classification": row.get("classification"),
                "passedStaticGate": row.get("passedStaticGate"),
                "firstBridge": row.get("firstBridge"),
                "dependencyCount": len(row.get("dependencies", [])),
                "dependencies": "|".join(row.get("dependencies", [])),
                "errors": "|".join(row.get("errors", [])),
            })


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("input", type=Path, help="Directory containing IPA files")
    parser.add_argument("--output", type=Path, default=Path("campaign-output"))
    parser.add_argument("--shard-index", type=int, default=0)
    parser.add_argument("--shard-count", type=int, default=1)
    parser.add_argument("--limit", type=int, default=0)
    args = parser.parse_args()

    if args.shard_count < 1 or not 0 <= args.shard_index < args.shard_count:
        parser.error("invalid shard configuration")

    repo_root = Path(__file__).resolve().parents[1]
    validator = load_validator(repo_root)
    all_ipas = sorted(p for p in args.input.rglob("*") if p.is_file() and p.suffix.lower() == ".ipa")
    selected = [p for i, p in enumerate(all_ipas) if i % args.shard_count == args.shard_index]
    if args.limit > 0:
        selected = selected[: args.limit]

    args.output.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, Any]] = []
    class_counts: Counter[str] = Counter()
    bridge_app_counts: Counter[str] = Counter()
    first_bridge_counts: Counter[str] = Counter()
    bridge_examples: dict[str, list[str]] = defaultdict(list)

    for index, ipa in enumerate(selected, 1):
        row = scan_one(validator, ipa)
        rows.append(row)
        class_counts[row["classification"]] += 1
        if row.get("firstBridge"):
            first_bridge_counts[row["firstBridge"]] += 1
        for bridge in set(row.get("bridgeKeys", [])):
            bridge_app_counts[bridge] += 1
            if len(bridge_examples[bridge]) < 10:
                bridge_examples[bridge].append(row.get("bundleIdentifier") or ipa.name)
        print(f"[{index}/{len(selected)}] {row['classification']} {ipa}", flush=True)

    ranking = [
        {
            "bridge": bridge,
            "appsDependingOnBridge": count,
            "appsBlockedFirst": first_bridge_counts.get(bridge, 0),
            "coveragePercent": round((count / len(rows) * 100.0), 3) if rows else 0.0,
            "examples": bridge_examples[bridge],
        }
        for bridge, count in bridge_app_counts.most_common()
    ]
    summary = {
        "schemaVersion": 1,
        "totalDiscovered": len(all_ipas),
        "totalScanned": len(rows),
        "shardIndex": args.shard_index,
        "shardCount": args.shard_count,
        "classifications": dict(class_counts),
        "bridgeRanking": ranking,
        "note": "Static coverage ranking only; it does not prove launch or gameplay.",
    }

    (args.output / "apps.json").write_text(json.dumps(rows, indent=2, sort_keys=True) + "\n")
    (args.output / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    write_csv(args.output / "apps.csv", rows)

    markdown = [
        "# LC32 IPA Compatibility Campaign",
        "",
        f"Scanned **{len(rows)}** of **{len(all_ipas)}** discovered IPA files.",
        "",
        "## Classification",
        "",
        "| Classification | Apps |",
        "|---|---:|",
    ]
    markdown.extend(f"| {name} | {count} |" for name, count in class_counts.most_common())
    markdown.extend(["", "## Bridge coverage ranking", "", "| Rank | Bridge | Apps | First blocker | Coverage |", "|---:|---|---:|---:|---:|"])
    for rank, item in enumerate(ranking[:100], 1):
        markdown.append(
            f"| {rank} | `{item['bridge']}` | {item['appsDependingOnBridge']} | "
            f"{item['appsBlockedFirst']} | {item['coveragePercent']}% |"
        )
    (args.output / "report.md").write_text("\n".join(markdown) + "\n")
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
