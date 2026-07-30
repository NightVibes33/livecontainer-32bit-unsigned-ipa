#!/usr/bin/env python3
"""Validate an IPA before using it as a LiveExec32 compatibility target.

This intentionally performs static validation only. A passing result means the
IPA is a usable ARMv7 test input; it does not claim UIKit or gameplay works.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import plistlib
import struct
import sys
import tempfile
import zipfile
from pathlib import Path

MH_MAGIC = 0xFEEDFACE
MH_CIGAM = 0xCEFAEDFE
FAT_MAGIC = 0xCAFEBABE
FAT_CIGAM = 0xBEBAFECA
CPU_TYPE_ARM = 12
CPU_TYPE_ARM64 = 0x0100000C
LC_LOAD_DYLIB = 0xC
LC_LOAD_WEAK_DYLIB = 0x18 | 0x80000000
LC_REEXPORT_DYLIB = 0x1F | 0x80000000
LC_LOAD_UPWARD_DYLIB = 0x23 | 0x80000000
LC_ENCRYPTION_INFO = 0x21


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def c_string(blob: bytes, start: int, end: int) -> str:
    raw = blob[start:end].split(b"\0", 1)[0]
    return raw.decode("utf-8", "replace")


def parse_thin(blob: bytes, offset: int = 0) -> dict:
    if len(blob) < offset + 28:
        raise ValueError("Mach-O header is truncated")
    magic_le = struct.unpack_from("<I", blob, offset)[0]
    if magic_le == MH_MAGIC:
        endian = "<"
    elif magic_le == MH_CIGAM:
        endian = ">"
    else:
        raise ValueError(f"unsupported thin Mach-O magic 0x{magic_le:08x}")

    _, cputype, cpusubtype, _, ncmds, sizeofcmds, flags = struct.unpack_from(
        endian + "IiiIIII", blob, offset
    )
    cursor = offset + 28
    commands_end = cursor + sizeofcmds
    if commands_end > len(blob):
        raise ValueError("Mach-O load commands are truncated")

    dylibs: list[str] = []
    cryptid = None
    for _ in range(ncmds):
        if cursor + 8 > commands_end:
            raise ValueError("invalid Mach-O load-command table")
        cmd, cmdsize = struct.unpack_from(endian + "II", blob, cursor)
        if cmdsize < 8 or cursor + cmdsize > commands_end:
            raise ValueError("invalid Mach-O load-command size")
        if cmd in {LC_LOAD_DYLIB, LC_LOAD_WEAK_DYLIB, LC_REEXPORT_DYLIB, LC_LOAD_UPWARD_DYLIB}:
            name_offset = struct.unpack_from(endian + "I", blob, cursor + 8)[0]
            if 0 < name_offset < cmdsize:
                dylibs.append(c_string(blob, cursor + name_offset, cursor + cmdsize))
        elif cmd == LC_ENCRYPTION_INFO and cmdsize >= 20:
            _, _, cryptid = struct.unpack_from(endian + "III", blob, cursor + 8)
        cursor += cmdsize

    return {
        "cputype": cputype,
        "cpusubtype": cpusubtype,
        "ncmds": ncmds,
        "flags": flags,
        "cryptid": cryptid,
        "dylibs": dylibs,
    }


def parse_macho(blob: bytes) -> list[dict]:
    if len(blob) < 4:
        raise ValueError("empty executable")
    magic_be = struct.unpack_from(">I", blob, 0)[0]
    if magic_be in {FAT_MAGIC, FAT_CIGAM}:
        endian = ">" if magic_be == FAT_MAGIC else "<"
        nfat = struct.unpack_from(endian + "I", blob, 4)[0]
        slices = []
        cursor = 8
        for _ in range(nfat):
            if cursor + 20 > len(blob):
                raise ValueError("fat header is truncated")
            cputype, cpusubtype, offset, size, _ = struct.unpack_from(endian + "iiIII", blob, cursor)
            if offset + size > len(blob):
                raise ValueError("fat slice exceeds file size")
            parsed = parse_thin(blob, offset)
            parsed["fat_cputype"] = cputype
            parsed["fat_cpusubtype"] = cpusubtype
            parsed["offset"] = offset
            parsed["size"] = size
            slices.append(parsed)
            cursor += 20
        return slices
    return [parse_thin(blob)]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("ipa", type=Path)
    parser.add_argument("--expect-sha256")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    result: dict = {
        "ipa": str(args.ipa),
        "ipaSha256": sha256(args.ipa),
        "checks": {},
        "errors": [],
    }
    if args.expect_sha256 and result["ipaSha256"].lower() != args.expect_sha256.lower():
        result["errors"].append("IPA SHA-256 does not match expected value")

    try:
        with zipfile.ZipFile(args.ipa) as zf:
            app_roots = sorted({name.split("/", 2)[1] for name in zf.namelist() if name.startswith("Payload/") and ".app/" in name})
            if len(app_roots) != 1:
                raise ValueError(f"expected exactly one Payload app, found {len(app_roots)}")
            app_root = f"Payload/{app_roots[0]}"
            info = plistlib.loads(zf.read(f"{app_root}/Info.plist"))
            executable_name = info.get("CFBundleExecutable")
            if not isinstance(executable_name, str) or not executable_name:
                raise ValueError("CFBundleExecutable is missing")
            executable_path = f"{app_root}/{executable_name}"
            executable = zf.read(executable_path)
            slices = parse_macho(executable)

            has_armv7 = any(s["cputype"] == CPU_TYPE_ARM for s in slices)
            has_arm64 = any(s["cputype"] == CPU_TYPE_ARM64 for s in slices)
            encrypted = any((s["cryptid"] or 0) != 0 for s in slices)
            result.update({
                "bundleIdentifier": info.get("CFBundleIdentifier"),
                "bundleVersion": info.get("CFBundleVersion"),
                "minimumOSVersion": info.get("MinimumOSVersion"),
                "sdkName": info.get("DTSDKName"),
                "deviceFamily": info.get("UIDeviceFamily"),
                "executable": executable_name,
                "executablePath": executable_path,
                "executableSha256": hashlib.sha256(executable).hexdigest(),
                "slices": slices,
            })
            result["checks"] = {
                "validZip": True,
                "singleAppBundle": True,
                "hasArmv7": has_armv7,
                "hasArm64": has_arm64,
                "armv7Only": has_armv7 and not has_arm64,
                "decrypted": not encrypted,
            }
            if not has_armv7:
                result["errors"].append("executable has no ARMv7 slice")
            if has_arm64:
                result["errors"].append("executable also contains ARM64; this is not an ARMv7-only proof target")
            if encrypted:
                result["errors"].append("executable has cryptid != 0 and must be decrypted before testing")
    except (OSError, KeyError, ValueError, zipfile.BadZipFile, plistlib.InvalidFileException) as exc:
        result["errors"].append(str(exc))

    result["passed"] = not result["errors"]
    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        status = "PASS" if result["passed"] else "FAIL"
        print(f"[{status}] {args.ipa}")
        for name, value in result.get("checks", {}).items():
            print(f"  {'PASS' if value else 'FAIL'} {name}")
        if result.get("bundleIdentifier"):
            print(f"  bundle: {result['bundleIdentifier']}")
            print(f"  executable: {result['executable']}")
            print(f"  minimum iOS: {result.get('minimumOSVersion')}")
            print(f"  SDK: {result.get('sdkName')}")
        for error in result["errors"]:
            print(f"  ERROR: {error}", file=sys.stderr)
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
