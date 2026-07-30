#!/usr/bin/env python3
"""Verify that a staged ARMv7 rootfs contains the absolute dylib/framework paths required by a compat report."""
from __future__ import annotations
import argparse, json, sys
from pathlib import Path


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('report', type=Path)
    ap.add_argument('rootfs', type=Path)
    ap.add_argument('--output', type=Path, default=Path('rootfs-compat.json'))
    args = ap.parse_args()
    data = json.loads(args.report.read_text())
    deps = data.get('guest', {}).get('dependencies', [])
    checked = []
    missing = []
    deferred = []
    for dep in deps:
        if dep.startswith('/'):
            candidate = args.rootfs / dep.lstrip('/')
            item = {'dependency': dep, 'path': str(candidate), 'present': candidate.exists()}
            checked.append(item)
            if not candidate.exists():
                missing.append(dep)
        else:
            deferred.append(dep)
    result = {
        'schemaVersion': 1,
        'result': 'pass' if not missing else 'fail',
        'rootfs': str(args.rootfs),
        'checkedAbsoluteDependencies': checked,
        'missingAbsoluteDependencies': missing,
        'deferredLoaderRelativeDependencies': deferred,
        'note': '@rpath, @loader_path, and @executable_path entries require dyld-resolution validation at runtime.'
    }
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + '\n')
    print(json.dumps(result, indent=2, sort_keys=True))
    return 1 if missing else 0

if __name__ == '__main__':
    sys.exit(main())
