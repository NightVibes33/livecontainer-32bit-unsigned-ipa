#!/usr/bin/env python3
from pathlib import Path
import sys

path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("build/LiveExec32/dynarmic.cpp")
source = path.read_text()

marker = "#define MACH_MSG_UNION(function, name) \\\n"
if source.count(marker) != 1:
    raise SystemExit("expected exactly one MACH_MSG_UNION marker")

types = r'''
typedef struct {
    mach_msg_header_t Head;
    NDR_record_t NDR;
    thread_flavor_t flavor;
} LC32RequestThreadInfo;

typedef struct {
    mach_msg_header_t Head;
    NDR_record_t NDR;
    kern_return_t RetCode;
    mach_msg_type_number_t thread_info_outCnt;
    integer_t thread_info_out[THREAD_INFO_MAX];
} LC32ReplyThreadInfo;

typedef union {
    LC32RequestThreadInfo In;
    LC32ReplyThreadInfo Out;
} LC32MachMessageThreadInfo;

'''
source = source.replace(marker, types + marker)

anchor = '''        case 3409: {
'''
if source.count(anchor) != 1:
    raise SystemExit("expected exactly one task_get_special_port case")

handler = r'''        case 3612: {
            // thread_info MIG request. Older 32-bit runtimes (including FMOD)
            // use this to query scheduling and CPU-usage information.
            LC32MachMessageThreadInfo *Mess =
                (LC32MachMessageThreadInfo *)host_header;
            mach_msg_type_number_t count = THREAD_INFO_MAX;
            kern_return_t kr = thread_info(
                Mess->In.Head.msgh_request_port,
                Mess->In.flavor,
                (thread_info_t)Mess->Out.thread_info_out,
                &count);
            host_header->msgh_size =
                sizeof(LC32ReplyThreadInfo) -
                sizeof(Mess->Out.thread_info_out) +
                count * sizeof(integer_t);
            Mess->Out.NDR = NDR_record;
            Mess->Out.RetCode = kr;
            Mess->Out.thread_info_outCnt = (kr == KERN_SUCCESS) ? count : 0;
            result = MACH_MSG_SUCCESS;
            break;
        }
'''
source = source.replace(anchor, handler + anchor)
path.write_text(source)
