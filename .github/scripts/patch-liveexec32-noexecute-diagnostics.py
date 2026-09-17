#!/usr/bin/env python3
from pathlib import Path
import runpy

p = Path("build/LiveExec32/HostFrameworks/LC32/dynarmic_callbacks.cpp")
s = p.read_text()
old = r'''        } else {
            SetPendingGuestCrashMessageIfEmpty(
                "Guest exception at pc=0x%08x, exception=%d, instruction=0x%08x",
                pc, static_cast<int>(exception), code);
            printf("ExceptionRaised[%s->%s:%d]: pc=0x%x, exception=%d, code=0x%08X\n", __FILE__, __func__, __LINE__, pc, exception, code);
            DumpCrashReport(signal);
        }
'''
new = r'''        } else {
            if (exception == Dynarmic::A32::Exception::NoExecuteFault) {
                const auto registers = cpu->Regs();
                u32 objectWords[8] = {};
                u32 vtableWords[12] = {};
                const bool haveObject = read_guest_memory_with_permissions(
                    registers[Reg::R0], objectWords, sizeof(objectWords), PROT_READ);
                const u32 vtable = haveObject ? objectWords[0] : 0;
                const bool haveVtable = vtable && read_guest_memory_with_permissions(
                    vtable, vtableWords, sizeof(vtableWords), PROT_READ);
                SetPendingGuestCrashMessageIfEmpty(
                    "Guest no-execute fault pc=0x%08x instruction=0x%08x; "
                    "r0-object=0x%08x readable=%d words="
                    "[%08x %08x %08x %08x %08x %08x %08x %08x]; "
                    "vtable=0x%08x readable=%d words="
                    "[%08x %08x %08x %08x %08x %08x %08x %08x %08x %08x %08x %08x]",
                    pc, code, registers[Reg::R0], haveObject,
                    objectWords[0], objectWords[1], objectWords[2], objectWords[3],
                    objectWords[4], objectWords[5], objectWords[6], objectWords[7],
                    vtable, haveVtable,
                    vtableWords[0], vtableWords[1], vtableWords[2], vtableWords[3],
                    vtableWords[4], vtableWords[5], vtableWords[6], vtableWords[7],
                    vtableWords[8], vtableWords[9], vtableWords[10], vtableWords[11]);
            } else {
                SetPendingGuestCrashMessageIfEmpty(
                    "Guest exception at pc=0x%08x, exception=%d, instruction=0x%08x",
                    pc, static_cast<int>(exception), code);
            }
            printf("ExceptionRaised[%s->%s:%d]: pc=0x%x, exception=%d, code=0x%08X\n", __FILE__, __func__, __LINE__, pc, exception, code);
            DumpCrashReport(signal);
        }
'''
if old not in s:
    raise SystemExit("no-execute diagnostic anchor missing")
p.write_text(s.replace(old, new, 1))
print("LC32: installed no-execute object/vtable crash diagnostics")

# Temp-branch-only Yu-Gi-Oh gameplay hang instrumentation. The normal
# unsigned workflow already calls this script, so chaining here keeps the
# production workflow unchanged while making workflow_dispatch at this ref
# build the instrumented runtime.
runpy.run_path(
    ".github/scripts/patch-liveexec32-yugioh-hang.py",
    run_name="__main__",
)
