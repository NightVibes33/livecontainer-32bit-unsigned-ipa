#!/usr/bin/env python3
from pathlib import Path

path = Path("build/LiveExec32/HostFrameworks/LC32/dynarmic_syscalls.cpp")
source = path.read_text()
anchor = '''        case 3213: {
'''
if source.count(anchor) != 1:
    raise SystemExit("expected exactly one mach_port_request_notification case")

handler = r'''        case 3825: { // mach_make_memory_entry_64
            // vm_map.defs packs this request on 4-byte boundaries for armv7.
            struct __attribute__((packed, aligned(4))) MakeMemoryEntryRequest32 {
                mach_msg_header_t Head;
                mach_msg_body_t msgh_body;
                mach_msg_port_descriptor_t parent_entry;
                NDR_record_t NDR;
                memory_object_size_t size;
                memory_object_offset_t offset;
                vm_prot_t permission;
            };
            struct __attribute__((packed, aligned(4))) MakeMemoryEntryReply32 {
                mach_msg_header_t Head;
                mach_msg_body_t msgh_body;
                mach_msg_port_descriptor_t object_handle;
                NDR_record_t NDR;
                memory_object_size_t size;
            };
            static_assert(sizeof(MakeMemoryEntryRequest32) == 68,
                "unexpected ARM32 mach_make_memory_entry_64 request layout");
            static_assert(sizeof(MakeMemoryEntryReply32) == 56,
                "unexpected ARM32 mach_make_memory_entry_64 reply layout");

            if (send_size != sizeof(MakeMemoryEntryRequest32)) {
                auto *error = reinterpret_cast<mig_reply_error_t *>(host_header);
                host_header->msgh_size = sizeof(*error);
                error->NDR = NDR_record;
                error->RetCode = MIG_BAD_ARGUMENTS;
                break;
            }
            if (rcv_size < sizeof(MakeMemoryEntryReply32)) {
                host_header->msgh_size = sizeof(MakeMemoryEntryReply32);
                result = MACH_RCV_TOO_LARGE;
                break;
            }

            const auto request =
                *reinterpret_cast<const MakeMemoryEntryRequest32 *>(host_header);
            memory_object_size_t size = request.size;
            memory_object_offset_t hostOffset = request.offset;
            const bool createsNamedEntry =
                (request.permission & MAP_MEM_NAMED_CREATE) != 0;
            if (!createsNamedEntry && request.offset != 0) {
                void *mapped = get_memory(static_cast<u32>(request.offset));
                if (mapped == nullptr) {
                    auto *error =
                        reinterpret_cast<mig_reply_error_t *>(host_header);
                    host_header->msgh_size = sizeof(*error);
                    error->NDR = NDR_record;
                    error->RetCode = KERN_INVALID_ADDRESS;
                    break;
                }
                hostOffset =
                    reinterpret_cast<memory_object_offset_t>(mapped);
            }

            mach_port_t objectHandle = MACH_PORT_NULL;
            const kern_return_t kr =
                request.Head.msgh_request_port == mach_task_self()
                    ? mach_make_memory_entry_64(
                        mach_task_self(), &size, hostOffset,
                        request.permission, &objectHandle,
                        request.parent_entry.name)
                    : KERN_INVALID_ARGUMENT;
            if (kr != KERN_SUCCESS) {
                auto *error = reinterpret_cast<mig_reply_error_t *>(host_header);
                host_header->msgh_size = sizeof(*error);
                error->NDR = NDR_record;
                error->RetCode = kr;
                break;
            }

            auto *reply =
                reinterpret_cast<MakeMemoryEntryReply32 *>(host_header);
            host_header->msgh_bits |= MACH_MSGH_BITS_COMPLEX;
            host_header->msgh_size = sizeof(*reply);
            reply->msgh_body.msgh_descriptor_count = 1;
            reply->object_handle.name = objectHandle;
            reply->object_handle.disposition = MACH_MSG_TYPE_MOVE_SEND;
            reply->object_handle.type = MACH_MSG_PORT_DESCRIPTOR;
            reply->NDR = NDR_record;
            reply->size = size;
            break;
        }
'''
path.write_text(source.replace(anchor, handler + anchor))
