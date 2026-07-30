#!/usr/bin/env python3
"""Aggregate compat32 campaign JSON reports into actionable compatibility buckets.

Inputs may be report JSON files or directories. Output contains coverage by archive/iOS
family, engine hints, linked framework, failure reason, and runtime stage. This does not
claim physical-device success; it converts large campaigns into implementation priorities.
"""
from __future__ import annotations

import argparse
import collections
import json
import re
from pathlib import Path
from typing import Any, Iterable

ENGINE_HINTS = {
    "Unity": ("UnityFramework", "libmono", "mono", "Unity"),
    "Cocos2d": ("cocos2d",),
    "Unreal": ("Unreal", "UE3", "UE4"),
    "SDL": ("SDL",),
    "Adobe AIR": ("Adobe AIR", "libCore", "ANE"),
    "GameSalad": ("GameSalad",),
}

STAGE_ORDER = [
    "ipa-parse", "macho-parse", "launch-contract", "dynarmic-initialized",
    "guest-executable-mapping", "guest-executable-mapped", "guest-dyld-mapping",
    "guest-dyld-mapped", "dependencies", "initializers", "objc-runtime",
    "main", "uiapplicationmain", "window", "first-frame", "touch", "audio", "save-write",
]


def iter_json(paths: Iterable[Path]) -> Iterable[tuple[Path, dict[str, Any]]]:
    for path in paths:
        if path.is_dir():
            yield from iter_json(sorted(path.rglob("*.json")))
            continue
        try:
            data = json.loads(path.read_text(errors="replace"))
        except Exception:
            continue
        if isinstance(data, dict) and ("guest" in data or "failures" in data or "stage" in data):
            yield path, data


def archive_family(path: Path, data: dict[str, Any]) -> str:
    hay = " ".join([
        str(path),
        str(data.get("archivePath", "")),
        str(data.get("name", "")),
        str(data.get("source", "")),
    ])
    for name in ("iPhoneOS 2", "iPhoneOS 3", "iOS 4", "iOS 5", "iOS 6", "iOS 7", "iOS 8", "Homebrew IPAs", "PossiblyBroken"):
        if name.lower() in hay.lower():
            return name
    guest = data.get("guest") or {}
    min_os = str(guest.get("slices", [{}])[0].get("minimumOS", "")) if guest.get("slices") else ""
    major = re.match(r"(\d+)", min_os)
    return f"minimum iOS {major.group(1)}" if major else "unknown"


def detect_engine(data: dict[str, Any]) -> str:
    guest = data.get("guest") or {}
    text = json.dumps({
        "dependencies": guest.get("dependencies", []),
        "bundle": guest.get("bundleIdentifier"),
        "warnings": data.get("warnings", []),
    }, sort_keys=True)
    for engine, needles in ENGINE_HINTS.items():
        if any(n.lower() in text.lower() for n in needles):
            return engine
    return "Unknown"


def terminal_stage(data: dict[str, Any]) -> str:
    stage = data.get("stage") or data.get("lastStage") or data.get("runtimeStage")
    if stage:
        return str(stage)
    proof = data.get("runtimeProof") or data.get("bootStages") or []
    if isinstance(proof, list) and proof:
        for candidate in reversed(STAGE_ORDER):
            if candidate in proof:
                return candidate
    failures = " ".join(map(str, data.get("failures", []))).lower()
    if "fairplay" in failures or "cryptid" in failures:
        return "macho-parse"
    if "mach-o" in failures or "arm slice" in failures:
        return "macho-parse"
    return "static-eligible" if not data.get("failures") else "ipa-parse"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("inputs", nargs="+", type=Path)
    ap.add_argument("--output", type=Path, default=Path("compat32-aggregate.json"))
    ap.add_argument("--markdown", type=Path, default=Path("compat32-aggregate.md"))
    args = ap.parse_args()

    by_family = collections.Counter()
    by_engine = collections.Counter()
    by_failure = collections.Counter()
    by_warning = collections.Counter()
    by_framework = collections.Counter()
    by_stage = collections.Counter()
    combinations = collections.Counter()
    total = passed = 0

    for path, report in iter_json(args.inputs):
        total += 1
        family = archive_family(path, report)
        engine = detect_engine(report)
        stage = terminal_stage(report)
        failures = [str(x) for x in report.get("failures", [])]
        warnings = [str(x) for x in report.get("warnings", [])]
        guest = report.get("guest") or {}
        deps = guest.get("dependencies", []) or []

        by_family[family] += 1
        by_engine[engine] += 1
        by_stage[stage] += 1
        combinations[(family, engine, stage)] += 1
        if not failures:
            passed += 1
        for failure in failures or ["none"]:
            by_failure[failure] += 1
        for warning in warnings:
            by_warning[warning] += 1
        for dep in deps:
            if "/Frameworks/" in dep or "/PrivateFrameworks/" in dep or dep.endswith(".dylib"):
                by_framework[str(dep)] += 1

    def top(counter: collections.Counter, n: int = 100):
        return [{"name": str(k), "count": v} for k, v in counter.most_common(n)]

    output = {
        "schemaVersion": 1,
        "scope": "static reports plus any imported device runtime stages",
        "totalReports": total,
        "staticEligible": passed,
        "staticFailed": total - passed,
        "byIOSFamily": top(by_family),
        "byEngineHint": top(by_engine),
        "byTerminalStage": top(by_stage),
        "topFailures": top(by_failure, 250),
        "topWarnings": top(by_warning, 250),
        "topDependencies": top(by_framework, 500),
        "topFamilyEngineStage": [
            {"iosFamily": k[0], "engine": k[1], "stage": k[2], "count": v}
            for k, v in combinations.most_common(500)
        ],
        "implementationPriority": [
            "Fix launch-contract/rootfs/dyld blockers first",
            "Then implement the most common missing syscall families",
            "Then Objective-C runtime and UIKit bridge coverage",
            "Then OpenGL ES/EAGL rendering",
            "Then touch, audio, and persistence",
        ],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, indent=2, sort_keys=True) + "\n")

    md = [
        "# 32-bit IPA compatibility campaign",
        "",
        f"- Reports: **{total}**",
        f"- Static eligible: **{passed}**",
        f"- Static failed: **{total - passed}**",
        "",
        "## Top terminal stages",
    ]
    md += [f"- `{x['name']}`: {x['count']}" for x in output["byTerminalStage"][:20]]
    md += ["", "## Top failures"]
    md += [f"- {x['name']}: {x['count']}" for x in output["topFailures"][:30]]
    md += ["", "## Top dependencies"]
    md += [f"- `{x['name']}`: {x['count']}" for x in output["topDependencies"][:30]]
    args.markdown.write_text("\n".join(md) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
