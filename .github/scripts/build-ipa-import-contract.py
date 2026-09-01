#!/usr/bin/env python3
"""Build a deterministic, library-aware import contract from IPA audit reports."""
import argparse
import json
from collections import defaultdict
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--reports", nargs="+", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    apps = []
    for report in args.reports:
        data = json.loads(Path(report).read_text())
        if isinstance(data, dict):
            data = data.get("apps", [])
        apps.extend(data)
    failed = [x for x in apps if x.get("status") != "ok"]
    if failed:
        raise SystemExit(f"refusing incomplete reports: {len(failed)} failures")
    unique = {}
    for app in apps:
        app_id = app.get("bundle_id") or app.get("archive_name")
        if app_id in unique:
            raise SystemExit(f"duplicate app id: {app_id}")
        images = app.get("images") or [{
            "path": app.get("executable"),
            "libraries": app["libraries"],
            "imports": app["imports"],
        }]
        imports = defaultdict(lambda: {"required": set(), "weak": set()})
        all_libraries = set()
        image_contract = {}
        unresolved_bindings = []
        for image in images:
            libs = image["libraries"]
            all_libraries.update(x["name"] for x in libs)
            image_imports = defaultdict(lambda: {"required": set(), "weak": set()})
            image_exports = set(image.get("exports", []))
            self_bindings = {"required": set(), "weak": set()}
            symbol_table_only = 0
            for symbol in image["imports"]:
                # LIEF's imported_symbols also includes undefined/symbol-table
                # records without a dyld bind operation. They are evidence,
                # but not runtime import bindings.
                bound = symbol.get("bound", "address" in symbol)
                if not bound:
                    symbol_table_only += 1
                    continue
                ordinal = symbol.get("ordinal")
                strength = "weak" if symbol.get("weak", False) else "required"
                if isinstance(ordinal, int) and 1 <= ordinal <= len(libs):
                    library = libs[ordinal - 1]["name"]
                    imports[library][strength].add(symbol["name"])
                    image_imports[library][strength].add(symbol["name"])
                elif ordinal == 0:
                    # BIND_SPECIAL_DYLIB_SELF is resolved within this bundled
                    # Mach-O image. Keep every operation in the contract, but
                    # do not misclassify it as a RootFS framework dependency.
                    self_bindings[strength].add(symbol["name"])
                else:
                    # Main-executable, flat/weak lookup, or malformed ordinals
                    # require a different resolution surface. Never discard them.
                    unresolved_bindings.append({
                        "image": image["path"], "symbol": symbol["name"],
                        "ordinal": ordinal, "strength": strength,
                        "reason": "unresolved special or invalid library ordinal",
                    })
            image_contract[image["path"]] = {
                "libraries": sorted({x["name"] for x in libs}),
                "imports": {
                    lib: {kind: sorted(names) for kind, names in groups.items()}
                    for lib, groups in sorted(image_imports.items())
                },
                "self_bindings": {
                    kind: sorted(names) for kind, names in self_bindings.items()
                },
                "symbol_table_only_count": symbol_table_only,
            }
        unique[app_id] = {
            "minimum_os": app.get("minimum_os"),
            "markers": sorted(app.get("markers", [])),
            "image_count": len(images),
            "images": image_contract,
            "libraries": sorted(all_libraries),
            "imports": {
                lib: {kind: sorted(names) for kind, names in groups.items()}
                for lib, groups in sorted(imports.items())
            },
            "unresolved_bindings": unresolved_bindings,
        }
    unresolved_count = sum(
        len(app["unresolved_bindings"]) for app in unique.values())
    output = {
        "schema": 3,
        "app_count": len(unique),
        "unresolved_binding_count": unresolved_count,
        "apps": {key: unique[key] for key in sorted(unique)},
    }
    Path(args.output).write_text(json.dumps(output, indent=2, sort_keys=True) + "\n")
    print(f"wrote {len(unique)} apps to {args.output}; "
          f"unresolved_bindings={unresolved_count}")
    if unresolved_count:
        raise SystemExit("contract contains unresolved Mach-O bindings")


if __name__ == "__main__":
    main()
