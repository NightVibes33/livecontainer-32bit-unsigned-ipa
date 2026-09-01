#!/usr/bin/env python3
"""Compare a packaged LiveExec32 RootFS with the complete 40-app import contract."""
import argparse
import json
import re
import subprocess
from collections import defaultdict
from pathlib import Path


def command(*args):
    return subprocess.run(args, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)


def macho_exports(path):
    result = command("nm", "-gjU", str(path))
    if result.returncode:
        raise RuntimeError(f"nm failed for {path}: {result.stderr.strip()}")
    return {line.strip() for line in result.stdout.splitlines() if line.strip()}


def macho_reexports(path):
    result = command("otool", "-l", str(path))
    if result.returncode:
        raise RuntimeError(f"otool failed for {path}: {result.stderr.strip()}")
    output = result.stdout.splitlines()
    found = set()
    for index, line in enumerate(output):
        if line.strip() != "cmd LC_REEXPORT_DYLIB":
            continue
        for candidate in output[index + 1:index + 8]:
            match = re.match(r"\s*name\s+(\S+)\s+\(offset", candidate)
            if match:
                found.add(match.group(1)); break
    return found


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--contract", required=True)
    parser.add_argument("--rootfs", required=True)
    parser.add_argument("--json-output", required=True)
    parser.add_argument("--markdown-output", required=True)
    parser.add_argument("--allow-gaps", action="store_true")
    args = parser.parse_args()
    contract = json.loads(Path(args.contract).read_text())
    if contract.get("app_count") != 40 or len(contract.get("apps", {})) != 40:
        raise SystemExit("contract must contain exactly 40 unique apps")
    root = Path(args.rootfs)
    required_by_library = defaultdict(set)
    weak_by_library = defaultdict(set)
    apps_by_requirement = defaultdict(set)
    all_libraries = set()
    for app_id, app in contract["apps"].items():
        all_libraries.update(x for x in app["libraries"] if x.startswith("/"))
        for library, groups in app["imports"].items():
            if not library.startswith("/"):
                continue
            for symbol in groups["required"]:
                required_by_library[library].add(symbol)
                apps_by_requirement[(library, symbol)].add(app_id)
            weak_by_library[library].update(groups["weak"])
    exports = {}; reexports = {}; image_errors = {}
    # Inspect the contract images, then recursively inspect every LC_REEXPORT_DYLIB
    # target. Umbrellas such as libSystem.B contain almost no direct exports.
    pending = list(sorted(all_libraries))
    inspected = set()
    while pending:
        library = pending.pop(0)
        if library in inspected:
            continue
        inspected.add(library)
        image = root / library.lstrip("/")
        if not image.is_file():
            continue
        try:
            exports[library] = macho_exports(image)
            reexports[library] = macho_reexports(image)
            pending.extend(sorted(reexports[library] - inspected))
        except Exception as exc:
            image_errors[library] = str(exc)
    def surface(library, seen=None):
        seen = set() if seen is None else seen
        if library in seen: return set()
        seen.add(library)
        value = set(exports.get(library, ()))
        for target in reexports.get(library, ()):
            value.update(surface(target, seen))
        return value
    missing_libraries = sorted(x for x in all_libraries if x not in exports)
    missing_required = []
    missing_weak = []
    for library, symbols in sorted(required_by_library.items()):
        if library not in exports: continue
        available = surface(library)
        for symbol in sorted(symbols - available):
            missing_required.append({"library": library, "symbol": symbol, "apps": sorted(apps_by_requirement[(library, symbol)])})
    for library, symbols in sorted(weak_by_library.items()):
        if library not in exports: continue
        available = surface(library)
        for symbol in sorted(symbols - available):
            missing_weak.append({"library": library, "symbol": symbol})
    report = {
        "schema": 1, "app_count": 40,
        "absolute_library_count": len(all_libraries),
        "present_library_count": len(exports),
        "missing_libraries": missing_libraries,
        "missing_required": missing_required,
        "missing_weak": missing_weak,
        "image_errors": image_errors,
    }
    Path(args.json_output).write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    lines = ["# LiveExec32 40-app import coverage", "", f"- Apps: 40", f"- Absolute libraries: {len(all_libraries)}", f"- Missing libraries: {len(missing_libraries)}", f"- Missing required exports: {len(missing_required)}", f"- Missing weak exports (tracked, not startup-fatal): {len(missing_weak)}", f"- Image inspection errors: {len(image_errors)}", ""]
    if missing_libraries:
        lines += ["## Missing libraries", ""] + [f"- `{x}`" for x in missing_libraries] + [""]
    if missing_required:
        lines += ["## Missing required exports", ""] + [f"- `{x['symbol']}` from `{x['library']}` ({len(x['apps'])} app(s))" for x in missing_required] + [""]
    Path(args.markdown_output).write_text("\n".join(lines))
    print(f"libraries={len(all_libraries)} missing_libraries={len(missing_libraries)} missing_required={len(missing_required)} missing_weak={len(missing_weak)}")
    if not args.allow_gaps and (missing_libraries or missing_required or image_errors):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
