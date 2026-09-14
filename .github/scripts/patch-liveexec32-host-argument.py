#!/usr/bin/env python3
from pathlib import Path
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
            printf(\"LC32HostToGuestArgument: unhandled type %s\\n\", type);
            abort();'''
new='''        default:
            /* Modern UIKit can deliver private notification callbacks whose
             * argument encoding is unknown to the legacy guest. Do not abort
             * the host before LiveExec32 can report the guest state. */
            fprintf(stderr,
                \"LC32: substituting zero for unsupported host argument type %s \"
                \"(value=0x%llx)\\n\", type, (unsigned long long)value);
            fflush(stderr);
            return 0;'''
if old not in s: raise SystemExit('host argument fallback anchor missing')
s=s.replace(old,new,1)
p.write_text(s)
print('LC32: expanded scalar arguments and installed safe notification fallback')
