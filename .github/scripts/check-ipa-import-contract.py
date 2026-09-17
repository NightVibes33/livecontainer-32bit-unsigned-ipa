#!/usr/bin/env python3
"""Compare a packaged LiveExec32 RootFS with an exhaustive IPA import contract."""
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
                found.add(match.group(1))
                break
    return found


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--contract", required=True)
    parser.add_argument("--rootfs", required=True)
    parser.add_argument("--json-output", required=True)
    parser.add_argument("--markdown-output", required=True)
    parser.add_argument("--expected-app-count", type=int, default=40)
    parser.add_argument("--expected-image-count", type=int, default=68)
    parser.add_argument("--title", default="LiveExec32 IPA import coverage")
    parser.add_argument("--allow-gaps", action="store_true")
    args = parser.parse_args()

    contract = json.loads(Path(args.contract).read_text())
    if contract.get("schema") != 3:
        raise SystemExit("contract must use exhaustive binding schema 3")

    apps = contract.get("apps", {})
    app_count = contract.get("app_count")
    if app_count != args.expected_app_count or len(apps) != args.expected_app_count:
        raise SystemExit(
            f"contract must contain exactly {args.expected_app_count} unique apps; "
            f"declared={app_count} actual={len(apps)}"
        )

    unresolved_bindings = [
        item for app in apps.values()
        for item in app.get("unresolved_bindings", [])
    ]
    if contract.get("unresolved_binding_count") != len(unresolved_bindings):
        raise SystemExit("contract unresolved-binding count is inconsistent")
    if unresolved_bindings:
        raise SystemExit(
            f"contract contains {len(unresolved_bindings)} unresolved bindings")

    image_count = sum(app.get("image_count", 0) for app in apps.values())
    if image_count != args.expected_image_count:
        raise SystemExit(
            f"contract must contain exactly {args.expected_image_count} ARM32 images, got {image_count}"
        )

    self_binding_count = sum(
        len(symbols)
        for app in apps.values()
        for image in app.get("images", {}).values()
        for symbols in image.get("self_bindings", {}).values()
    )
    symbol_table_only_count = sum(
        image.get("symbol_table_only_count", 0)
        for app in apps.values()
        for image in app.get("images", {}).values()
    )

    root = Path(args.rootfs)
    required_by_library = defaultdict(set)
    weak_by_library = defaultdict(set)
    apps_by_requirement = defaultdict(set)
    all_libraries = set()
    for app_id, app in apps.items():
        all_libraries.update(x for x in app["libraries"] if x.startswith("/"))
        for library, groups in app["imports"].items():
            if not library.startswith("/"):
                continue
            for symbol in groups["required"]:
                required_by_library[library].add(symbol)
                apps_by_requirement[(library, symbol)].add(app_id)
            weak_by_library[library].update(groups["weak"])

    exports = {}
    reexports = {}
    image_errors = {}
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
        if library in seen:
            return set()
        seen.add(library)
        value = set(exports.get(library, ()))
        for target in reexports.get(library, ()):
            value.update(surface(target, seen))
        return value

    missing_libraries = sorted(x for x in all_libraries if x not in exports)
    missing_required = []
    missing_weak = []
    for library, symbols in sorted(required_by_library.items()):
        if library not in exports:
            continue
        available = surface(library)
        for symbol in sorted(symbols - available):
            missing_required.append({
                "library": library,
                "symbol": symbol,
                "apps": sorted(apps_by_requirement[(library, symbol)]),
            })
    for library, symbols in sorted(weak_by_library.items()):
        if library not in exports:
            continue
        available = surface(library)
        for symbol in sorted(symbols - available):
            missing_weak.append({"library": library, "symbol": symbol})

    report = {
        "schema": 2,
        "contract_schema": contract["schema"],
        "contract_app_id_field": contract.get("app_id_field", "bundle_id"),
        "app_count": app_count,
        "arm32_image_count": image_count,
        "self_binding_count": self_binding_count,
        "symbol_table_only_count": symbol_table_only_count,
        "unresolved_binding_count": 0,
        "absolute_library_count": len(all_libraries),
        "present_library_count": len(exports),
        "missing_libraries": missing_libraries,
        "missing_required": missing_required,
        "missing_weak": missing_weak,
        "image_errors": image_errors,
    }
    Path(args.json_output).write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")

    lines = [
        f"# {args.title}", "",
        "- Contract schema: 3 (exhaustive binding accounting)",
        f"- Contract key: `{contract.get('app_id_field', 'bundle_id')}`",
        f"- Apps: {app_count}",
        f"- ARM32 Mach-O images: {image_count}",
        f"- App-contained self bindings tracked: {self_binding_count}",
        f"- Symbol-table-only records tracked: {symbol_table_only_count}",
        "- Unresolved special/invalid bindings: 0",
        f"- Absolute libraries: {len(all_libraries)}",
        f"- Missing libraries: {len(missing_libraries)}",
        f"- Missing required exports: {len(missing_required)}",
        f"- Missing weak exports (tracked, not startup-fatal): {len(missing_weak)}",
        f"- Image inspection errors: {len(image_errors)}", "",
    ]
    if missing_libraries:
        lines += ["## Missing libraries", ""] + [f"- `{x}`" for x in missing_libraries] + [""]
    if missing_required:
        lines += ["## Missing required exports", ""] + [
            f"- `{x['symbol']}` from `{x['library']}` ({len(x['apps'])} app(s))"
            for x in missing_required
        ] + [""]
    Path(args.markdown_output).write_text("\n".join(lines))
    print(
        f"apps={app_count} images={image_count} libraries={len(all_libraries)} "
        f"missing_libraries={len(missing_libraries)} "
        f"missing_required={len(missing_required)} missing_weak={len(missing_weak)}"
    )
    if not args.allow_gaps and (missing_libraries or missing_required or image_errors):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
