#!/usr/bin/env python3
from pathlib import Path
import sys


def main() -> None:
    path = Path(sys.argv[1] if len(sys.argv) > 1 else "LiveContainer/LCBootstrap.m")
    text = path.read_text()

    marker_text = "Starting LiveExec32 without the legacy host JIT gate"
    if marker_text in text:
        print(f"{path} already patched")
        return

    section = text.index("#if is32BitSupported", text.index("DyldHooksInit"))
    branch = text.index("    if(is32bit) {", section)
    gate = text.index("        if (!isJitEnabled) {", branch)
    marker = "        NSString *selected32BitLayerExecPath = nil;"
    marker_at = text.index(marker, gate)

    removed = text[gate:marker_at]
    expected_error = 'return @"JIT is required to run 32-bit apps through LiveExec32.";'
    if expected_error not in removed:
        raise SystemExit("The expected LiveExec32 host JIT rejection was not found")

    replacement = '''        // Start the integrated ARMv7 runtime directly. LiveExec32 owns
        // backend/executable-memory diagnostics instead of the host refusing launch.
        if(!isJitEnabled) {
            NSLog(@"[LCBootstrap] Starting LiveExec32 without the legacy host JIT gate.");
        }

'''
    path.write_text(text[:gate] + replacement + text[marker_at:])
    print(f"patched {path}")


if __name__ == "__main__":
    main()
