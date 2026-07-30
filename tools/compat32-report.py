#!/usr/bin/env python3
"""Generate a deterministic compatibility report for a legacy 32-bit iOS IPA.

This is a static/runtime-package gate. It does not claim physical-device execution.
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
LC_LOAD_WEAK_DYLIB = 0x80000018
LC_REEXPORT_DYLIB = 0x8000001F
LC_LOAD_UPWARD_DYLIB = 0x80000023
LC_ENCRYPTION_INFO = 0x21
LC_VERSION_MIN_IPHONEOS = 0x25
LC_BUILD_VERSION = 0x32


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def cstr(blob: bytes, offset: int) -> str:
    if offset < 0 or offset >= len(blob):
        return ''
    return blob[offset:blob.find(b'\0', offset) if b'\0' in blob[offset:] else len(blob)].decode('utf-8', 'replace')


def parse_thin(data: bytes, base: int = 0) -> dict:
    if len(data) < base + 28:
        raise ValueError('truncated Mach-O header')
    raw = struct.unpack_from('<I', data, base)[0]
    if raw == MH_MAGIC:
        endian = '<'
    elif raw == MH_CIGAM:
        endian = '>'
    else:
        raise ValueError(f'unsupported thin Mach-O magic 0x{raw:08x}')
    magic, cputype, cpusubtype, filetype, ncmds, sizeofcmds, flags = struct.unpack_from(endian + '7I', data, base)
    off = base + 28
    deps: list[str] = []
    cryptid = None
    min_os = None
    sdk = None
    for _ in range(ncmds):
        if off + 8 > len(data):
            raise ValueError('truncated load command')
        cmd, cmdsize = struct.unpack_from(endian + '2I', data, off)
        if cmdsize < 8 or off + cmdsize > len(data):
            raise ValueError('invalid load command size')
        block = data[off:off + cmdsize]
        if cmd in (LC_LOAD_DYLIB, LC_LOAD_WEAK_DYLIB, LC_REEXPORT_DYLIB, LC_LOAD_UPWARD_DYLIB) and cmdsize >= 24:
            nameoff = struct.unpack_from(endian + 'I', block, 8)[0]
            deps.append(cstr(block, nameoff))
        elif cmd == LC_ENCRYPTION_INFO and cmdsize >= 20:
            cryptid = struct.unpack_from(endian + 'I', block, 16)[0]
        elif cmd == LC_VERSION_MIN_IPHONEOS and cmdsize >= 16:
            version, sdk_raw = struct.unpack_from(endian + '2I', block, 8)
            min_os = version
            sdk = sdk_raw
        elif cmd == LC_BUILD_VERSION and cmdsize >= 24:
            _platform, minos, sdk_raw, _ntools = struct.unpack_from(endian + '4I', block, 8)
            min_os = minos
            sdk = sdk_raw
        off += cmdsize
    return {
        'cputype': cputype,
        'cpusubtype': cpusubtype,
        'filetype': filetype,
        'dependencies': sorted(set(filter(None, deps))),
        'cryptid': cryptid,
        'minimumOSRaw': min_os,
        'sdkRaw': sdk,
    }


def parse_macho(path: Path) -> list[dict]:
    data = path.read_bytes()
    if len(data) < 4:
        raise ValueError('file too small')
    magic_be = struct.unpack_from('>I', data, 0)[0]
    magic_le = struct.unpack_from('<I', data, 0)[0]
    if magic_le in (MH_MAGIC, MH_CIGAM):
        return [parse_thin(data)]
    if magic_be not in (FAT_MAGIC, FAT_CIGAM):
        raise ValueError('not a supported Mach-O')
    endian = '>' if magic_be == FAT_MAGIC else '<'
    nfat = struct.unpack_from(endian + 'I', data, 4)[0]
    out = []
    for i in range(nfat):
        ent = 8 + i * 20
        if ent + 20 > len(data):
            raise ValueError('truncated fat header')
        cputype, cpusubtype, offset, size, _align = struct.unpack_from(endian + '5I', data, ent)
        if offset + size > len(data):
            raise ValueError('fat slice outside file')
        item = parse_thin(data, offset)
        item['fatHeaderCPUType'] = cputype
        item['fatHeaderCPUSubtype'] = cpusubtype
        out.append(item)
    return out


def version(raw: int | None) -> str | None:
    if raw is None:
        return None
    return f'{(raw >> 16) & 0xffff}.{(raw >> 8) & 0xff}.{raw & 0xff}'


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('ipa', type=Path)
    ap.add_argument('--livecontainer-ipa', type=Path)
    ap.add_argument('--expected-sha256')
    ap.add_argument('--output', type=Path, default=Path('compat32-report.json'))
    args = ap.parse_args()

    failures: list[str] = []
    warnings: list[str] = []
    if not args.ipa.is_file():
        raise SystemExit(f'IPA not found: {args.ipa}')
    actual_sha = sha256(args.ipa)
    if args.expected_sha256 and actual_sha.lower() != args.expected_sha256.lower():
        failures.append('IPA SHA-256 does not match expected value')

    with tempfile.TemporaryDirectory(prefix='compat32-') as td:
        root = Path(td)
        try:
            with zipfile.ZipFile(args.ipa) as zf:
                zf.extractall(root / 'guest')
        except zipfile.BadZipFile:
            raise SystemExit('input is not a valid ZIP/IPA')
        apps = list((root / 'guest' / 'Payload').glob('*.app'))
        if len(apps) != 1:
            raise SystemExit(f'expected exactly one Payload/*.app, found {len(apps)}')
        app = apps[0]
        info_path = app / 'Info.plist'
        if not info_path.is_file():
            raise SystemExit('missing guest Info.plist')
        info = plistlib.loads(info_path.read_bytes())
        executable_name = info.get('CFBundleExecutable')
        executable = app / str(executable_name)
        if not executable.is_file():
            raise SystemExit('guest executable missing')
        slices = parse_macho(executable)
        has_armv7 = any(s['cputype'] == CPU_TYPE_ARM for s in slices)
        has_arm64 = any(s['cputype'] == CPU_TYPE_ARM64 for s in slices)
        if not has_armv7:
            failures.append('no 32-bit ARM slice found')
        if has_arm64:
            warnings.append('IPA also contains ARM64; LiveContainer can prefer the native slice')
        encrypted = [s for s in slices if s.get('cryptid') not in (None, 0)]
        if encrypted:
            failures.append('one or more executable slices are FairPlay-encrypted (cryptid != 0)')

        all_deps = sorted({d for s in slices for d in s['dependencies']})
        forbidden_or_unhandled = [d for d in all_deps if d.startswith('/System/Library/PrivateFrameworks/')]
        if forbidden_or_unhandled:
            warnings.append('uses private frameworks; runtime availability must be verified in the staged guest rootfs')

        lc = {'provided': False}
        if args.livecontainer_ipa:
            lc['provided'] = True
            if not args.livecontainer_ipa.is_file():
                failures.append('LiveContainer IPA path does not exist')
            else:
                with zipfile.ZipFile(args.livecontainer_ipa) as zf:
                    names = set(zf.namelist())
                    required = {
                        'Payload/LiveContainer.app/LiveExec32.app/Info.plist',
                        'Payload/LiveContainer.app/LiveExec32.app/LiveExec32',
                    }
                    missing = sorted(required - names)
                    if missing:
                        failures.append('built LiveContainer IPA is missing bundled LiveExec32 files: ' + ', '.join(missing))
                    marker_found = False
                    for name in names:
                        if name.startswith('Payload/LiveContainer.app/') and not name.endswith('/'):
                            try:
                                if b'Rerouting 32-bit guest dlopen' in zf.read(name):
                                    marker_found = True
                                    break
                            except Exception:
                                pass
                    if not marker_found:
                        failures.append('built LiveContainer IPA lacks ARMv7 reroute marker')

        report = {
            'schemaVersion': 1,
            'result': 'pass' if not failures else 'fail',
            'scope': 'static IPA + packaged LiveContainer compatibility gate; physical-device execution is not emulated',
            'guest': {
                'ipaSHA256': actual_sha,
                'bundleIdentifier': info.get('CFBundleIdentifier'),
                'bundleVersion': info.get('CFBundleVersion'),
                'shortVersion': info.get('CFBundleShortVersionString'),
                'executable': executable_name,
                'executableSHA256': sha256(executable),
                'slices': [{**s, 'minimumOS': version(s.get('minimumOSRaw')), 'sdk': version(s.get('sdkRaw'))} for s in slices],
                'dependencies': all_deps,
                'armv7': has_armv7,
                'arm64': has_arm64,
                'decrypted': not encrypted,
            },
            'liveContainer': lc,
            'failures': failures,
            'warnings': warnings,
            'deviceProofStillRequired': [
                'guest dyld starts', 'dependent frameworks initialize', 'UIApplicationMain reached',
                'first frame rendered', 'touch input works', 'audio works', 'save data persists'
            ],
        }
        args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + '\n')
        print(json.dumps(report, indent=2, sort_keys=True))
    return 1 if failures else 0


if __name__ == '__main__':
    sys.exit(main())
