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
LC_SYMTAB = 0x2
LC_LOAD_DYLIB = 0xC
LC_LOAD_WEAK_DYLIB = 0x80000018
LC_REEXPORT_DYLIB = 0x8000001F
LC_LOAD_UPWARD_DYLIB = 0x80000023
LC_ENCRYPTION_INFO = 0x21
LC_VERSION_MIN_IPHONEOS = 0x25
LC_BUILD_VERSION = 0x32
N_STAB = 0xE0
N_TYPE = 0x0E
N_UNDF = 0x00
N_EXT = 0x01

VIRTUAL_READY_SYMBOLS = {
    "memcpy", "memmove", "memset", "memcmp", "strlen", "strcmp", "strncmp", "strchr", "strrchr",
}
VIRTUAL_PLANNED_SYMBOLS = {
    "exit", "abort", "malloc", "calloc", "realloc", "free", "open", "close", "read", "write",
    "lseek", "access", "gettimeofday", "time", "arc4random", "arc4random_uniform", "objc_msgSend",
    "objc_msgSendSuper", "objc_msgSendSuper2", "objc_getClass", "objc_lookUpClass", "objc_getMetaClass",
    "sel_registerName", "sel_getUid", "objc_retain", "objc_release", "objc_autorelease", "objc_storeStrong",
    "objc_storeWeak", "objc_loadWeakRetained", "objc_destroyWeak", "objc_initWeak", "objc_copyWeak", "objc_moveWeak",
}


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def cstr(blob: bytes, offset: int, end: int | None = None) -> str:
    limit = len(blob) if end is None else min(len(blob), end)
    if offset < 0 or offset >= limit:
        return ''
    nul = blob.find(b'\0', offset, limit)
    if nul < 0:
        return ''
    return blob[offset:nul].decode('utf-8', 'replace')


def normalize_symbol(name: str) -> str:
    return name.lstrip('_')


def parse_thin(data: bytes, base: int = 0, slice_size: int | None = None) -> dict:
    if len(data) < base + 28:
        raise ValueError('truncated Mach-O header')
    raw = struct.unpack_from('<I', data, base)[0]
    if raw == MH_MAGIC:
        endian = '<'
    elif raw == MH_CIGAM:
        endian = '>'
    else:
        raise ValueError(f'unsupported thin Mach-O magic 0x{raw:08x}')
    _magic, cputype, cpusubtype, filetype, ncmds, sizeofcmds, flags = struct.unpack_from(endian + '7I', data, base)
    slice_end = len(data) if slice_size is None else min(len(data), base + slice_size)
    off = base + 28
    commands_end = off + sizeofcmds
    if commands_end > slice_end:
        raise ValueError('truncated Mach-O load commands')
    deps: list[str] = []
    cryptid = None
    min_os = None
    sdk = None
    symtab: tuple[int, int, int, int] | None = None
    for _ in range(ncmds):
        if off + 8 > commands_end:
            raise ValueError('truncated load command')
        cmd, cmdsize = struct.unpack_from(endian + '2I', data, off)
        if cmdsize < 8 or off + cmdsize > commands_end:
            raise ValueError('invalid load command size')
        block = data[off:off + cmdsize]
        if cmd == LC_SYMTAB and cmdsize >= 24:
            symtab = struct.unpack_from(endian + '4I', block, 8)
        elif cmd in (LC_LOAD_DYLIB, LC_LOAD_WEAK_DYLIB, LC_REEXPORT_DYLIB, LC_LOAD_UPWARD_DYLIB) and cmdsize >= 24:
            nameoff = struct.unpack_from(endian + 'I', block, 8)[0]
            deps.append(cstr(block, nameoff, len(block)))
        elif cmd == LC_ENCRYPTION_INFO and cmdsize >= 20:
            cryptid = struct.unpack_from(endian + 'I', block, 16)[0]
        elif cmd == LC_VERSION_MIN_IPHONEOS and cmdsize >= 16:
            version_raw, sdk_raw = struct.unpack_from(endian + '2I', block, 8)
            min_os = version_raw
            sdk = sdk_raw
        elif cmd == LC_BUILD_VERSION and cmdsize >= 24:
            _platform, minos, sdk_raw, _ntools = struct.unpack_from(endian + '4I', block, 8)
            min_os = minos
            sdk = sdk_raw
        off += cmdsize

    imports: list[str] = []
    if symtab is not None:
        symoff, nsyms, stroff, strsize = symtab
        if nsyms > 1_000_000:
            raise ValueError('Mach-O symbol count exceeds parser limit')
        sym_base = base + symoff
        str_base = base + stroff
        if sym_base + nsyms * 12 > slice_end or str_base + strsize > slice_end:
            raise ValueError('Mach-O symbol or string table is truncated')
        for index in range(nsyms):
            entry = sym_base + index * 12
            string_offset = struct.unpack_from(endian + 'I', data, entry)[0]
            n_type = data[entry + 4]
            if n_type & N_STAB or (n_type & N_TYPE) != N_UNDF or not n_type & N_EXT:
                continue
            if not 0 < string_offset < strsize:
                continue
            symbol = cstr(data, str_base + string_offset, str_base + strsize)
            if symbol:
                imports.append(symbol)

    return {
        'cputype': cputype,
        'cpusubtype': cpusubtype,
        'filetype': filetype,
        'flags': flags,
        'dependencies': sorted(set(filter(None, deps))),
        'imports': sorted(set(imports)),
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
        item = parse_thin(data, offset, size)
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

        arm_slices = [s for s in slices if s['cputype'] == CPU_TYPE_ARM]
        all_deps = sorted({d for s in arm_slices for d in s['dependencies']})
        all_imports = sorted({name for s in arm_slices for name in s.get('imports', [])})
        normalized_imports = [(name, normalize_symbol(name)) for name in all_imports]
        ready_symbols = [name for name, normalized in normalized_imports if normalized in VIRTUAL_READY_SYMBOLS]
        planned_symbols = [name for name, normalized in normalized_imports if normalized in VIRTUAL_PLANNED_SYMBOLS]
        unknown_symbols = [
            name for name, normalized in normalized_imports
            if normalized not in VIRTUAL_READY_SYMBOLS and normalized not in VIRTUAL_PLANNED_SYMBOLS
        ]
        first_runtime_blocker = planned_symbols[0] if planned_symbols else (unknown_symbols[0] if unknown_symbols else None)

        private_frameworks = [d for d in all_deps if d.startswith('/System/Library/PrivateFrameworks/')]
        if private_frameworks:
            warnings.append('uses private frameworks; a clean-room bridge is required')

        lc = {'provided': False}
        if args.livecontainer_ipa:
            lc['provided'] = True
            if not args.livecontainer_ipa.is_file():
                failures.append('LiveContainer IPA path does not exist')
            else:
                lc['ipaSHA256'] = sha256(args.livecontainer_ipa)
                with zipfile.ZipFile(args.livecontainer_ipa) as zf:
                    names = set(zf.namelist())
                    required = {
                        'Payload/LiveContainer.app/LiveExec32.app/Info.plist',
                        'Payload/LiveContainer.app/LiveExec32.app/LiveExec32',
                        'Payload/LiveContainer.app/LiveExec32.app/LiveExec32Plugin.dylib',
                    }
                    missing = sorted(required - names)
                    if missing:
                        failures.append('built LiveContainer IPA is missing bundled LC32 files: ' + ', '.join(missing))
                    searchable = b''
                    for name in names:
                        if name.startswith('Payload/LiveContainer.app/') and not name.endswith('/'):
                            try:
                                searchable += zf.read(name)
                            except Exception:
                                pass
                    required_markers = [b'LC32Main', b'cleanroom-virtual-symbol-ready', b'cleanroom-symbol-implementation-required']
                    absent = [marker.decode() for marker in required_markers if marker not in searchable]
                    if absent:
                        failures.append('built LiveContainer IPA lacks current virtual-runtime markers: ' + ', '.join(absent))

        report = {
            'schemaVersion': 2,
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
                'importedSymbols': all_imports,
                'baseRuntime': {
                    'readySymbols': ready_symbols,
                    'plannedSymbols': planned_symbols,
                    'unknownSymbols': unknown_symbols,
                    'firstRuntimeBlocker': first_runtime_blocker,
                },
                'armv7': has_armv7,
                'arm64': has_arm64,
                'decrypted': not encrypted,
            },
            'liveContainer': lc,
            'failures': failures,
            'warnings': warnings,
            'deviceProofStillRequired': [
                'indirect symbols bound', 'ARMv7 entry starts', 'Objective-C runtime initializes',
                'UIApplicationMain reached', 'first frame rendered', 'touch input works',
                'audio works', 'save data persists'
            ],
        }
        args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + '\n')
        print(json.dumps(report, indent=2, sort_keys=True))
    return 1 if failures else 0


if __name__ == '__main__':
    sys.exit(main())
