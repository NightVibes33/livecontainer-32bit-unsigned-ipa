#!/usr/bin/env python3
import argparse
import hashlib
import os
import plistlib
import stat
import sys
from pathlib import Path

REQUIRED_ROOTFS_PATHS = (
    "usr/lib/dyld",
    "usr/lib/libSystem.B.dylib",
    "usr/lib/libobjc.A.dylib",
    "System/Library/Frameworks/Foundation.framework/Foundation",
    "System/Library/Frameworks/UIKit.framework/UIKit",
    "System/Library/Frameworks/CoreFoundation.framework/CoreFoundation",
    "System/Library/Frameworks/CoreGraphics.framework/CoreGraphics",
    "System/Library/Frameworks/QuartzCore.framework/QuartzCore",
    "System/Library/Frameworks/OpenGLES.framework/OpenGLES",
    "System/Library/Frameworks/AudioToolbox.framework/AudioToolbox",
)


def fail(message: str) -> None:
    print(f"error: {message}", file=sys.stderr)
    raise SystemExit(1)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def require_inside(path: Path, root: Path, label: str) -> None:
    try:
        path.resolve().relative_to(root.resolve())
    except ValueError:
        fail(f"{label} escapes runtime directory: {path}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate a staged LiveExec32 full-app runtime")
    parser.add_argument("runtime", type=Path, help="LiveExec32Runtime directory")
    args = parser.parse_args()

    runtime = args.runtime.resolve()
    manifest_path = runtime / "launch.plist"
    if not manifest_path.is_file():
        fail(f"missing launch manifest: {manifest_path}")

    with manifest_path.open("rb") as handle:
        manifest = plistlib.load(handle)

    if manifest.get("schemaVersion") != 1:
        fail(f"unsupported schemaVersion: {manifest.get('schemaVersion')!r}")

    required_keys = (
        "guestRootFS", "guestBundle", "guestExecutable", "guestBundleIdentifier",
        "guestHome", "logDirectory", "ipaSHA256", "executableSHA256",
    )
    for key in required_keys:
        value = manifest.get(key)
        if not isinstance(value, str) or not value:
            fail(f"manifest key {key} is missing or invalid")

    rootfs = Path(manifest["guestRootFS"])
    bundle = Path(manifest["guestBundle"])
    executable = Path(manifest["guestExecutable"])
    guest_home = Path(manifest["guestHome"])
    logs = Path(manifest["logDirectory"])

    for path, label in ((rootfs, "guestRootFS"), (bundle, "guestBundle"),
                        (executable, "guestExecutable"), (guest_home, "guestHome"),
                        (logs, "logDirectory")):
        require_inside(path, runtime, label)

    if not rootfs.is_dir():
        fail(f"guestRootFS is not a directory: {rootfs}")
    if not bundle.is_dir():
        fail(f"guestBundle is not a directory: {bundle}")
    if not executable.is_file():
        fail(f"guestExecutable is not a file: {executable}")
    if not guest_home.is_dir():
        fail(f"guestHome is not a directory: {guest_home}")
    if not logs.is_dir():
        fail(f"logDirectory is not a directory: {logs}")

    mode = executable.stat().st_mode
    if not (mode & stat.S_IXUSR):
        print(f"warning: guest executable lacks owner execute bit: {executable}", file=sys.stderr)

    actual_exec_sha = sha256(executable)
    if actual_exec_sha.lower() != manifest["executableSHA256"].lower():
        fail("guest executable SHA-256 does not match launch manifest")

    missing = [relative for relative in REQUIRED_ROOTFS_PATHS if not (rootfs / relative).exists()]
    if missing:
        print("error: rootfs is missing required 32-bit runtime components:", file=sys.stderr)
        for relative in missing:
            print(f"  - {relative}", file=sys.stderr)
        return 1

    info_path = bundle / "Info.plist"
    if not info_path.is_file():
        fail(f"guest bundle has no Info.plist: {info_path}")
    with info_path.open("rb") as handle:
        info = plistlib.load(handle)
    if info.get("CFBundleIdentifier") != manifest["guestBundleIdentifier"]:
        fail("guest bundle identifier does not match launch manifest")
    if bundle / info.get("CFBundleExecutable", "") != executable:
        fail("guest executable path does not match Info.plist")

    print("LiveExec32 runtime verification passed")
    print(f"  bundle: {manifest['guestBundleIdentifier']}")
    print(f"  executable: {executable}")
    print(f"  rootfs: {rootfs}")
    print(f"  logs: {logs}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
