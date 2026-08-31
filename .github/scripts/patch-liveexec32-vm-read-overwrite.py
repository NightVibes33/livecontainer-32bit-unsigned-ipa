#!/usr/bin/env python3
from pathlib import Path

path = Path("build/LiveExec32/HostFrameworks/LC32/dynarmic_syscalls.cpp")
source = path.read_text()
anchor = '''        case 3213: {
'''
if source.count(anchor) != 1:
    raise SystemExit("expected exactly one mach_port_request_notification case")

handler = r'''        case 3809: { // vm_read_overwrite
            // The armv7 vm_map MIG ABI uses 32-bit addresses and sizes.
            struct __attribute__((packed, aligned(4))) VmReadOverwriteRequest32 {
                mach_msg_header_t Head;
                NDR_record_t NDR;
                u32 address;
                u32 size;
                u32 data;
            };
            struct __attribute__((packed, aligned(4))) VmReadOverwriteReply32 {
                mach_msg_header_t Head;
                NDR_record_t NDR;
                kern_return_t RetCode;
                u32 outsize;
            };
            static_assert(sizeof(VmReadOverwriteRequest32) == 44,
                "unexpected ARM32 vm_read_overwrite request layout");
            static_assert(sizeof(VmReadOverwriteReply32) == 40,
                "unexpected ARM32 vm_read_overwrite reply layout");

            if (send_size != sizeof(VmReadOverwriteRequest32)) {
                auto *error = reinterpret_cast<mig_reply_error_t *>(host_header);
                host_header->msgh_size = sizeof(*error);
                error->NDR = NDR_record;
                error->RetCode = MIG_BAD_ARGUMENTS;
                break;
            }
            if (rcv_size < sizeof(VmReadOverwriteReply32)) {
                host_header->msgh_size = sizeof(VmReadOverwriteReply32);
                result = MACH_RCV_TOO_LARGE;
                break;
            }

            const auto request =
                *reinterpret_cast<const VmReadOverwriteRequest32 *>(host_header);
            auto *reply =
                reinterpret_cast<VmReadOverwriteReply32 *>(host_header);
            const kern_return_t kr =
                request.Head.msgh_request_port == mach_task_self()
                    ? CopyGuestVmMemory(
                        request.address, request.data, request.size)
                    : KERN_INVALID_ARGUMENT;
            host_header->msgh_size = sizeof(*reply);
            reply->NDR = NDR_record;
            reply->RetCode = kr;
            reply->outsize = kr == KERN_SUCCESS ? request.size : 0;
            break;
        }
'''
path.write_text(source.replace(anchor, handler + anchor))
