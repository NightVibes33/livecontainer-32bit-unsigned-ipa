#!/usr/bin/env python3
"""Combine the 51-app CN import audit with exact regression gates for two user-supplied legacy IPAs."""
import argparse
import json
import subprocess
from pathlib import Path

EXPECTED = {
    "Kick_the_boss_v1.8_os40.ipa": {
        "sha256": "c59de9b5351e43e8561fc0f303429474014521c052857acc0c21ee1a2282f0ba",
        "bundle_id": "com.gamehivecorp.kickthebossfree",
        "minimum_os": "4.0",
        "arm32_images": 1,
    },
    "Gravity_Falls_v1.0_os42.ipa": {
        "sha256": "b3b1321c8c53ac4189ab78c5f71e4fa8f9f64fd429b7aea505306617b5a11a9c",
        "bundle_id": "com.disney.gravityfallsmysteryshackattack",
        "minimum_os": "4.2",
        "arm32_images": 1,
    },
}
EXPECTED_GRAVITY_GAP = {
    "library": "/System/Library/Frameworks/AudioToolbox.framework/AudioToolbox",
    "symbol": "_AudioServicesPlayAlertSound",
}


def exports(path: Path):
    result = subprocess.run(
        ["nm", "-gjU", str(path)], text=True, stdout=subprocess.PIPE,
        stderr=subprocess.PIPE, check=False
    )
    if result.returncode:
        raise SystemExit(f"nm failed for {path}: {result.stderr.strip()}")
    return {line.strip() for line in result.stdout.splitlines() if line.strip()}


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--metadata", required=True)
    p.add_argument("--cn-coverage", required=True)
    p.add_argument("--rootfs", required=True)
    p.add_argument("--json-output", required=True)
    p.add_argument("--markdown-output", required=True)
    args = p.parse_args()

    metadata = json.loads(Path(args.metadata).read_text())
    cn = json.loads(Path(args.cn_coverage).read_text())
    root = Path(args.rootfs)

    if metadata.get("schema") != 1:
        raise SystemExit("legacy-extra metadata must use schema 1")
    apps = metadata.get("apps", [])
    if len(apps) != 2:
        raise SystemExit(f"legacy-extra metadata must contain exactly 2 apps, got {len(apps)}")
    by_name = {app.get("archive_name"): app for app in apps}
    if set(by_name) != set(EXPECTED):
        raise SystemExit(f"unexpected legacy-extra archive set: {sorted(by_name)}")

    for name, expected in EXPECTED.items():
        app = by_name[name]
        for key, value in expected.items():
            if app.get(key) != value:
                raise SystemExit(f"{name}: expected {key}={value!r}, got {app.get(key)!r}")

    kick = by_name["Kick_the_boss_v1.8_os40.ipa"]
    gravity = by_name["Gravity_Falls_v1.0_os42.ipa"]
    if kick.get("missing_required_against_prepatch_rootfs") != []:
        raise SystemExit("Kick the Boss audit unexpectedly contains a pre-patch required-binding gap")
    if gravity.get("missing_required_against_prepatch_rootfs") != [EXPECTED_GRAVITY_GAP]:
        raise SystemExit("Gravity Falls audit no longer matches the exact known pre-patch gap")

    if cn.get("schema") != 2 or cn.get("app_count") != 51 or cn.get("arm32_image_count") != 51:
        raise SystemExit("Cartoon Network coverage is not the expected 51-app / 51-image strict report")
    if cn.get("missing_libraries") or cn.get("missing_required") or cn.get("image_errors"):
        raise SystemExit("Cartoon Network strict import coverage contains startup-fatal gaps")

    checked_bindings = []
    for app in apps:
        for gap in app.get("missing_required_against_prepatch_rootfs", []):
            image = root / gap["library"].lstrip("/")
            if not image.is_file():
                raise SystemExit(f"packaged RootFS is missing {gap['library']}")
            available = exports(image)
            if gap["symbol"] not in available:
                raise SystemExit(
                    f"{app['archive_name']}: packaged RootFS still misses "
                    f"{gap['symbol']} from {gap['library']}"
                )
            checked_bindings.append({
                "archive_name": app["archive_name"],
                "library": gap["library"],
                "symbol": gap["symbol"],
                "status": "present_in_packaged_rootfs",
            })

    extra_images = sum(int(app.get("arm32_images", 0)) for app in apps)
    combined_apps = cn["app_count"] + len(apps)
    combined_images = cn["arm32_image_count"] + extra_images
    if combined_apps != 53 or combined_images != 53:
        raise SystemExit(f"combined gate must be exactly 53 apps / 53 ARM32 images, got {combined_apps}/{combined_images}")

    report = {
        "schema": 1,
        "app_count": combined_apps,
        "arm32_image_count": combined_images,
        "cartoon_network": {
            "app_count": 51,
            "arm32_image_count": 51,
            "strict_schema3_import_audit": True,
            "missing_library_count": len(cn.get("missing_libraries", [])),
            "missing_required_count": len(cn.get("missing_required", [])),
            "image_error_count": len(cn.get("image_errors", {})),
        },
        "legacy_extra": {
            "app_count": 2,
            "arm32_image_count": extra_images,
            "exact_audit_metadata_verified": True,
            "archives": [
                {
                    "archive_name": app["archive_name"],
                    "sha256": app["sha256"],
                    "bundle_id": app["bundle_id"],
                    "minimum_os": app["minimum_os"],
                }
                for app in apps
            ],
            "packaged_rootfs_binding_regressions": checked_bindings,
        },
        "status": "pass",
    }
    Path(args.json_output).write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")

    lines = [
        "# LiveExec32 53-app legacy compatibility gate",
        "",
        "- Combined apps: 53",
        "- Combined ARM32 Mach-O images: 53",
        "- Cartoon Network apps: 51 (strict exhaustive schema-3 import audit)",
        "- Additional exact user-supplied apps: 2",
        "- Kick the Boss v1.8 / iOS 4.0 audit identity: verified",
        "- Gravity Falls v1.0 / iOS 4.2 audit identity: verified",
        "- Cartoon Network missing required exports: 0",
        "- Cartoon Network missing libraries: 0",
        "- Cartoon Network image inspection errors: 0",
        f"- Extra packaged-RootFS binding regressions checked: {len(checked_bindings)}",
        "",
    ]
    for item in checked_bindings:
        lines.append(
            f"- PASS `{item['archive_name']}`: `{item['symbol']}` is exported by `{item['library']}`"
        )
    lines += [
        "",
        "The 51 Cartoon Network entries are checked from their exhaustive schema-3 contract. "
        "The two additional apps are pinned by the exact recorded archive hashes/metadata and their "
        "known pre-patch required-binding regressions are rechecked against the packaged RootFS.",
        "",
    ]
    Path(args.markdown_output).write_text("\n".join(lines))
    print("53-app compatibility gate PASS: 51 strict CN + 2 exact legacy regressions")


if __name__ == "__main__":
    main()
