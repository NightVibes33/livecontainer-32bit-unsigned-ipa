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
        libs = app["libraries"]
        imports = defaultdict(lambda: {"required": set(), "weak": set()})
        for symbol in app["imports"]:
            ordinal = symbol.get("ordinal")
            if not isinstance(ordinal, int) or not 1 <= ordinal <= len(libs):
                continue
            library = libs[ordinal - 1]["name"]
            strength = "weak" if symbol.get("weak", False) else "required"
            imports[library][strength].add(symbol["name"])
        unique[app_id] = {
            "minimum_os": app.get("minimum_os"),
            "markers": sorted(app.get("markers", [])),
            "libraries": sorted({x["name"] for x in libs}),
            "imports": {
                lib: {kind: sorted(names) for kind, names in groups.items()}
                for lib, groups in sorted(imports.items())
            },
        }
    output = {
        "schema": 1,
        "app_count": len(unique),
        "apps": {key: unique[key] for key in sorted(unique)},
    }
    Path(args.output).write_text(json.dumps(output, indent=2, sort_keys=True) + "\n")
    print(f"wrote {len(unique)} apps to {args.output}")


if __name__ == "__main__":
    main()
