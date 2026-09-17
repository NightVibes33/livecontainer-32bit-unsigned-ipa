#!/usr/bin/env python3
from pathlib import Path
import runpy

p=Path('build/LiveExec32/HostFrameworks/LC32/bridge.mm')
s=p.read_text()
old='''        case 'B': // bool
        case 'I':
        case 'Q':
        case 'c':
        case 'i':
        case 'q':
            return (u32)value;'''
new='''        case 'B': // bool
        case 'C':
        case 'S':
        case 'I':
        case 'L':
        case 'Q':
        case 'c':
        case 's':
        case 'i':
        case 'l':
        case 'q':
            return (u32)value;'''
if old not in s: raise SystemExit('host argument scalar anchor missing')
s=s.replace(old,new,1)
old='''        default:
            printf("LC32HostToGuestArgument: unhandled type %s\\n", type);
            abort();'''
new='''        default:
            /* Modern UIKit can deliver private notification callbacks whose
             * argument encoding is unknown to the legacy guest. Do not abort
             * the host before LiveExec32 can report the guest state. */
            fprintf(stderr,
                "LC32: substituting zero for unsupported host argument type %s "
                "(value=0x%llx)\\n", type, (unsigned long long)value);
            fflush(stderr);
            return 0;'''
if old not in s: raise SystemExit('host argument fallback anchor missing')
s=s.replace(old,new,1)
p.write_text(s)
print('LC32: expanded scalar arguments and installed safe notification fallback')

# This script is already part of the unsigned-IPA compatibility stage. Keep
# the universal legacy-canvas patch in the same stage so every produced
# LiveExec32 package gets coherent phone/iPad geometry while this branch is
# being validated. The canvas script has strict one-shot anchors and therefore
# fails closed if upstream geometry changes underneath us.
runpy.run_path(str(Path(__file__).with_name('patch-liveexec32-universal-canvas.py')), run_name='__main__')
