#!/usr/bin/env python3
from pathlib import Path

header_path = Path('runtime/LC32DarwinSyscalls.hpp')
source_path = Path('runtime/LC32DarwinSyscalls.cpp')
test_path = Path('runtime/tests/LC32DarwinSyscallsTests.cpp')

header = header_path.read_text()
old_port = '''    struct MachPort {
        std::deque<std::vector<uint8_t>> messages;
    };
'''
new_port = '''    struct MachPort {
        std::deque<std::vector<uint8_t>> messages;
        uint32_t receiveRefs = 0;
        uint32_t sendRefs = 0;
        uint32_t sendOnceRefs = 0;
        bool immortal = false;
    };
'''
if old_port not in header:
    raise SystemExit('MachPort header block not found')
header = header.replace(old_port, new_port, 1)
header_path.write_text(header)

source = source_path.read_text()
start = source.index('TrapResult DarwinSyscalls::dispatchMach(')
end = source.index('\n} // namespace lc32', start)
new_function = r'''TrapResult DarwinSyscalls::dispatchMach(CPUState& state, uint32_t number) {
    constexpr uint32_t kThreadPort = 0x101u;
    constexpr uint32_t kTaskPort = 0x102u;
    constexpr uint32_t kHostPort = 0x103u;

    constexpr uint32_t kMachPortRightSend = 0u;
    constexpr uint32_t kMachPortRightReceive = 1u;
    constexpr uint32_t kMachPortRightSendOnce = 2u;

    constexpr uint32_t kMachMsgTypeMoveSend = 17u;
    constexpr uint32_t kMachMsgTypeMoveSendOnce = 18u;
    constexpr uint32_t kMachMsgTypeCopySend = 19u;
    constexpr uint32_t kMachMsgTypeMakeSend = 20u;
    constexpr uint32_t kMachMsgTypeMakeSendOnce = 21u;

    constexpr uint32_t kMachSendMsg = 0x00000001u;
    constexpr uint32_t kMachReceiveMsg = 0x00000002u;
    constexpr uint32_t kMachMessageComplex = 0x80000000u;
    constexpr uint32_t kMachRemoteDispositionMask = 0xffu;

    constexpr uint32_t kKernSuccess = 0u;
    constexpr uint32_t kKernInvalidArgument = 4u;
    constexpr uint32_t kKernInvalidName = 15u;
    constexpr uint32_t kKernInvalidTask = 16u;
    constexpr uint32_t kKernInvalidRight = 17u;
    constexpr uint32_t kKernInvalidValue = 18u;
    constexpr uint32_t kKernUrefsOverflow = 19u;

    constexpr uint32_t kMachSendInvalidData = 0x10000002u;
    constexpr uint32_t kMachSendInvalidDestination = 0x10000003u;
    constexpr uint32_t kMachSendMessageTooSmall = 0x10000008u;
    constexpr uint32_t kMachSendInvalidRight = 0x1000000au;
    constexpr uint32_t kMachReceiveInvalidName = 0x10004002u;
    constexpr uint32_t kMachReceiveTimedOut = 0x10004003u;
    constexpr uint32_t kMachReceiveTooLarge = 0x10004004u;
    constexpr uint32_t kMachHeaderSize = 24u;
    constexpr uint32_t kMaximumMachMessage = 1024u * 1024u;

    const auto ensureBuiltinPorts = [&]() {
        const auto addBuiltin = [&](uint32_t name) {
            auto [it, inserted] = machPorts_.try_emplace(name);
            if (inserted) {
                it->second.receiveRefs = 1;
                it->second.sendRefs = 1;
                it->second.immortal = true;
            }
        };
        addBuiltin(kThreadPort);
        addBuiltin(kTaskPort);
        addBuiltin(kHostPort);
    };
    ensureBuiltinPorts();

    const auto validTask = [&](uint32_t task) {
        return task == kTaskPort;
    };
    const auto allocateReceivePort = [&]() -> uint32_t {
        uint32_t candidate = nextMachPort_;
        while (candidate == 0 || machPorts_.find(candidate) != machPorts_.end()) {
            ++candidate;
            if (candidate < 0x200u) candidate = 0x200u;
        }
        nextMachPort_ = candidate + 1u;
        MachPort port;
        port.receiveRefs = 1;
        machPorts_.emplace(candidate, std::move(port));
        return candidate;
    };
    const auto maybeErasePort = [&](uint32_t name) {
        const auto it = machPorts_.find(name);
        if (it == machPorts_.end() || it->second.immortal) return;
        if (it->second.receiveRefs == 0 && it->second.sendRefs == 0 &&
            it->second.sendOnceRefs == 0) {
            machPorts_.erase(it);
        }
    };
    const auto adjustRefs = [&](uint32_t name,
                                uint32_t right,
                                int32_t delta) -> uint32_t {
        auto it = machPorts_.find(name);
        if (it == machPorts_.end()) return kKernInvalidName;
        uint32_t* refs = nullptr;
        switch (right) {
            case kMachPortRightSend:
                refs = &it->second.sendRefs;
                break;
            case kMachPortRightReceive:
                refs = &it->second.receiveRefs;
                break;
            case kMachPortRightSendOnce:
                refs = &it->second.sendOnceRefs;
                break;
            default:
                return kKernInvalidRight;
        }
        if (right == kMachPortRightReceive) {
            const int64_t updated = static_cast<int64_t>(*refs) + delta;
            if (updated < 0 || updated > 1) return kKernInvalidValue;
            *refs = static_cast<uint32_t>(updated);
        } else if (delta < 0) {
            const uint32_t magnitude = static_cast<uint32_t>(-static_cast<int64_t>(delta));
            if (magnitude > *refs) return kKernInvalidRight;
            *refs -= magnitude;
        } else {
            const uint64_t updated = static_cast<uint64_t>(*refs) +
                                     static_cast<uint32_t>(delta);
            if (updated > UINT32_MAX) return kKernUrefsOverflow;
            *refs = static_cast<uint32_t>(updated);
        }
        maybeErasePort(name);
        return kKernSuccess;
    };

    switch (number) {
        case 16: {
            if (!validTask(state.r[0])) {
                return ok(number, static_cast<int32_t>(kKernInvalidTask),
                          "mach_port_allocate invalid task");
            }
            if (state.r[1] != kMachPortRightReceive) {
                return ok(number, static_cast<int32_t>(kKernInvalidRight),
                          "mach_port_allocate unsupported right");
            }
            if (!memory_.write) {
                return ok(number, static_cast<int32_t>(kKernInvalidArgument),
                          "mach_port_allocate memory callback");
            }
            const uint32_t name = allocateReceivePort();
            if (!memory_.write(state.r[2], &name, sizeof(name))) {
                machPorts_.erase(name);
                return ok(number, static_cast<int32_t>(kKernInvalidArgument),
                          "mach_port_allocate guest write");
            }
            return ok(number, static_cast<int32_t>(kKernSuccess),
                      "mach_port_allocate");
        }
        case 17: {
            if (!validTask(state.r[0])) {
                return ok(number, static_cast<int32_t>(kKernInvalidTask),
                          "mach_port_destroy invalid task");
            }
            const auto it = machPorts_.find(state.r[1]);
            if (it == machPorts_.end()) {
                return ok(number, static_cast<int32_t>(kKernInvalidName),
                          "mach_port_destroy invalid name");
            }
            if (it->second.immortal) {
                return ok(number, static_cast<int32_t>(kKernInvalidRight),
                          "mach_port_destroy immortal port");
            }
            machPorts_.erase(it);
            return ok(number, static_cast<int32_t>(kKernSuccess),
                      "mach_port_destroy");
        }
        case 18: {
            if (!validTask(state.r[0])) {
                return ok(number, static_cast<int32_t>(kKernInvalidTask),
                          "mach_port_deallocate invalid task");
            }
            auto it = machPorts_.find(state.r[1]);
            if (it == machPorts_.end()) {
                return ok(number, static_cast<int32_t>(kKernInvalidName),
                          "mach_port_deallocate invalid name");
            }
            uint32_t result = kKernInvalidRight;
            if (it->second.sendRefs != 0) {
                result = adjustRefs(state.r[1], kMachPortRightSend, -1);
            } else if (it->second.sendOnceRefs != 0) {
                result = adjustRefs(state.r[1], kMachPortRightSendOnce, -1);
            }
            return ok(number, static_cast<int32_t>(result),
                      "mach_port_deallocate");
        }
        case 19: {
            if (!validTask(state.r[0])) {
                return ok(number, static_cast<int32_t>(kKernInvalidTask),
                          "mach_port_mod_refs invalid task");
            }
            const uint32_t result = adjustRefs(state.r[1],
                                               state.r[2],
                                               static_cast<int32_t>(state.r[3]));
            return ok(number, static_cast<int32_t>(result), "mach_port_mod_refs");
        }
        case 21: {
            if (!validTask(state.r[0])) {
                return ok(number, static_cast<int32_t>(kKernInvalidTask),
                          "mach_port_insert_right invalid task");
            }
            const uint32_t name = state.r[1];
            const uint32_t poly = state.r[2];
            const uint32_t disposition = state.r[3];
            auto it = machPorts_.find(name);
            if (name == 0 || name != poly || it == machPorts_.end()) {
                return ok(number, static_cast<int32_t>(kKernInvalidName),
                          "mach_port_insert_right invalid name");
            }
            uint32_t result = kKernInvalidValue;
            if (disposition == kMachMsgTypeMakeSend) {
                result = it->second.receiveRefs != 0
                             ? adjustRefs(name, kMachPortRightSend, 1)
                             : kKernInvalidRight;
            } else if (disposition == kMachMsgTypeMakeSendOnce) {
                result = it->second.receiveRefs != 0
                             ? adjustRefs(name, kMachPortRightSendOnce, 1)
                             : kKernInvalidRight;
            } else if (disposition == kMachMsgTypeCopySend) {
                result = it->second.sendRefs != 0
                             ? adjustRefs(name, kMachPortRightSend, 1)
                             : kKernInvalidRight;
            } else if (disposition == kMachMsgTypeMoveSend) {
                result = it->second.sendRefs != 0 ? kKernSuccess : kKernInvalidRight;
            } else if (disposition == kMachMsgTypeMoveSendOnce) {
                result = it->second.sendOnceRefs != 0 ? kKernSuccess : kKernInvalidRight;
            }
            return ok(number, static_cast<int32_t>(result),
                      "mach_port_insert_right");
        }
        case 26: {
            const uint32_t name = allocateReceivePort();
            return ok(number, static_cast<int32_t>(name), "mach_reply_port");
        }
        case 27:
            return ok(number, static_cast<int32_t>(kThreadPort), "thread_self_trap");
        case 28:
            return ok(number, static_cast<int32_t>(kTaskPort), "task_self_trap");
        case 29:
            return ok(number, static_cast<int32_t>(kHostPort), "host_self_trap");
        case 31: {
            const uint32_t messageAddress = state.r[0];
            const uint32_t options = state.r[1];
            const uint32_t sendSize = state.r[2];
            const uint32_t receiveSize = state.r[3];
            const uint32_t receiveName = state.r[4];
            const bool send = (options & kMachSendMsg) != 0;
            const bool receive = (options & kMachReceiveMsg) != 0;
            if (!send && !receive) {
                return ok(number, static_cast<int32_t>(kKernSuccess), "mach_msg no-op");
            }

            if (send) {
                if (sendSize < kMachHeaderSize) {
                    return ok(number, static_cast<int32_t>(kMachSendMessageTooSmall),
                              "mach_msg send too small");
                }
                if (sendSize > kMaximumMachMessage || !memory_.read) {
                    return ok(number, static_cast<int32_t>(kMachSendInvalidData),
                              "mach_msg invalid send data");
                }
                std::vector<uint8_t> message(sendSize);
                if (!memory_.read(messageAddress, message.data(), message.size())) {
                    return ok(number, static_cast<int32_t>(kMachSendInvalidData),
                              "mach_msg send guest read");
                }
                uint32_t bits = 0;
                uint32_t headerSize = 0;
                uint32_t destination = 0;
                std::memcpy(&bits, message.data(), sizeof(bits));
                std::memcpy(&headerSize, message.data() + 4u, sizeof(headerSize));
                std::memcpy(&destination, message.data() + 8u, sizeof(destination));
                if (headerSize < kMachHeaderSize || headerSize > sendSize ||
                    (bits & kMachMessageComplex) != 0) {
                    return ok(number, static_cast<int32_t>(kMachSendInvalidData),
                              "mach_msg unsupported send header");
                }
                auto port = machPorts_.find(destination);
                if (destination == 0 || port == machPorts_.end()) {
                    return ok(number, static_cast<int32_t>(kMachSendInvalidDestination),
                              "mach_msg invalid destination");
                }
                const uint32_t disposition = bits & kMachRemoteDispositionMask;
                bool consumeSend = false;
                bool consumeSendOnce = false;
                bool hasRight = false;
                if (disposition == kMachMsgTypeCopySend) {
                    hasRight = port->second.sendRefs != 0;
                } else if (disposition == kMachMsgTypeMoveSend) {
                    hasRight = port->second.sendRefs != 0;
                    consumeSend = hasRight;
                } else if (disposition == kMachMsgTypeMoveSendOnce) {
                    hasRight = port->second.sendOnceRefs != 0;
                    consumeSendOnce = hasRight;
                } else if (disposition == kMachMsgTypeMakeSend) {
                    hasRight = port->second.receiveRefs != 0;
                } else if (disposition == kMachMsgTypeMakeSendOnce) {
                    hasRight = port->second.receiveRefs != 0;
                }
                if (!hasRight) {
                    return ok(number, static_cast<int32_t>(kMachSendInvalidRight),
                              "mach_msg missing send right");
                }
                message.resize(headerSize);
                port->second.messages.push_back(std::move(message));
                if (consumeSend) {
                    (void)adjustRefs(destination, kMachPortRightSend, -1);
                } else if (consumeSendOnce) {
                    (void)adjustRefs(destination, kMachPortRightSendOnce, -1);
                }
            }

            if (receive) {
                auto port = machPorts_.find(receiveName);
                if (receiveName == 0 || port == machPorts_.end() ||
                    port->second.receiveRefs == 0) {
                    return ok(number, static_cast<int32_t>(kMachReceiveInvalidName),
                              "mach_msg invalid receive name");
                }
                if (port->second.messages.empty()) {
                    return ok(number, static_cast<int32_t>(kMachReceiveTimedOut),
                              "mach_msg receive empty");
                }
                const std::vector<uint8_t>& message = port->second.messages.front();
                if (receiveSize < message.size()) {
                    return ok(number, static_cast<int32_t>(kMachReceiveTooLarge),
                              "mach_msg receive too large");
                }
                if (!memory_.write ||
                    !memory_.write(messageAddress, message.data(), message.size())) {
                    return ok(number, static_cast<int32_t>(kMachSendInvalidData),
                              "mach_msg receive guest write");
                }
                port->second.messages.pop_front();
            }
            return ok(number, static_cast<int32_t>(kKernSuccess), "mach_msg_trap");
        }
        default: {
            TrapResult result;
            result.number = number;
            result.detail = "unsupported Mach trap";
            return result;
        }
    }
}
'''
source = source[:start] + new_function + source[end:]
source_path.write_text(source)

tests = test_path.read_text()
block_start = tests.index('    state = {};\n    state.r[12] = static_cast<uint32_t>(-26);')
block_end = tests.index('    char rootTemplate[]', block_start)
new_tests = r'''    constexpr uint32_t kMachNameAddress = 0x0080u;
    constexpr uint32_t kMachMessageAddress = 0x0100u;
    constexpr uint32_t kMachSendMsg = 0x00000001u;
    constexpr uint32_t kMachReceiveMsg = 0x00000002u;
    constexpr uint32_t kMachMsgTypeMakeSend = 20u;
    constexpr uint32_t kMachPortRightSend = 0u;
    constexpr uint32_t kMachPortRightReceive = 1u;
    constexpr uint32_t kKernInvalidName = 15u;
    constexpr uint32_t kKernInvalidRight = 17u;
    constexpr uint32_t kMachSendInvalidRight = 0x1000000au;
    constexpr uint32_t kMachReceiveInvalidName = 0x10004002u;
    constexpr uint32_t kMachReceiveTimedOut = 0x10004003u;
    constexpr uint32_t kMachReceiveTooLarge = 0x10004004u;

    state = {};
    state.r[12] = static_cast<uint32_t>(-26);
    const auto replyPort = syscalls.dispatch(state, 0, false);
    assert(replyPort.handled && replyPort.errorNumber == 0);
    const uint32_t replyName = state.r[0];
    assert(replyName >= 0x200u);

    uint32_t messageHeader[6] = {19u, 28u, replyName, 0u, 0u, 0x1234u};
    uint32_t payloadWord = 0xfeedfaceu;
    std::memcpy(lowMemory.data() + kMachMessageAddress,
                messageHeader,
                sizeof(messageHeader));
    std::memcpy(lowMemory.data() + kMachMessageAddress + sizeof(messageHeader),
                &payloadWord,
                sizeof(payloadWord));

    state = {};
    state.r[12] = static_cast<uint32_t>(-31);
    state.r[0] = kMachMessageAddress;
    state.r[1] = kMachSendMsg;
    state.r[2] = 28u;
    const auto sendWithoutRight = syscalls.dispatch(state, 0, false);
    assert(sendWithoutRight.handled && state.r[0] == kMachSendInvalidRight);

    state = {};
    state.r[12] = static_cast<uint32_t>(-21);
    state.r[0] = 0x102u;
    state.r[1] = replyName;
    state.r[2] = replyName;
    state.r[3] = kMachMsgTypeMakeSend;
    const auto makeSend = syscalls.dispatch(state, 0, false);
    assert(makeSend.handled && state.r[0] == 0u);

    state = {};
    state.r[12] = static_cast<uint32_t>(-31);
    state.r[0] = kMachMessageAddress;
    state.r[1] = kMachSendMsg;
    state.r[2] = 28u;
    const auto machSend = syscalls.dispatch(state, 0, false);
    assert(machSend.handled && state.r[0] == 0u);

    std::memset(lowMemory.data() + kMachMessageAddress, 0, 32u);
    state = {};
    state.r[12] = static_cast<uint32_t>(-31);
    state.r[0] = kMachMessageAddress;
    state.r[1] = kMachReceiveMsg;
    state.r[3] = 24u;
    state.r[4] = replyName;
    const auto machSmallReceive = syscalls.dispatch(state, 0, false);
    assert(machSmallReceive.handled && state.r[0] == kMachReceiveTooLarge);

    state = {};
    state.r[12] = static_cast<uint32_t>(-31);
    state.r[0] = kMachMessageAddress;
    state.r[1] = kMachReceiveMsg;
    state.r[3] = 32u;
    state.r[4] = replyName;
    const auto machReceive = syscalls.dispatch(state, 0, false);
    assert(machReceive.handled && state.r[0] == 0u);
    uint32_t receivedId = 0;
    uint32_t receivedPayload = 0;
    std::memcpy(&receivedId, lowMemory.data() + kMachMessageAddress + 20u, 4u);
    std::memcpy(&receivedPayload, lowMemory.data() + kMachMessageAddress + 24u, 4u);
    assert(receivedId == 0x1234u && receivedPayload == payloadWord);

    state = {};
    state.r[12] = static_cast<uint32_t>(-31);
    state.r[0] = kMachMessageAddress;
    state.r[1] = kMachReceiveMsg;
    state.r[3] = 32u;
    state.r[4] = replyName;
    const auto machEmptyReceive = syscalls.dispatch(state, 0, false);
    assert(machEmptyReceive.handled && state.r[0] == kMachReceiveTimedOut);

    std::memset(lowMemory.data() + kMachNameAddress, 0, sizeof(uint32_t));
    state = {};
    state.r[12] = static_cast<uint32_t>(-16);
    state.r[0] = 0x102u;
    state.r[1] = kMachPortRightReceive;
    state.r[2] = kMachNameAddress;
    const auto allocatedPort = syscalls.dispatch(state, 0, false);
    assert(allocatedPort.handled && state.r[0] == 0u);
    uint32_t allocatedName = 0;
    std::memcpy(&allocatedName,
                lowMemory.data() + kMachNameAddress,
                sizeof(allocatedName));
    assert(allocatedName >= 0x200u && allocatedName != replyName);

    state = {};
    state.r[12] = static_cast<uint32_t>(-21);
    state.r[0] = 0x102u;
    state.r[1] = allocatedName;
    state.r[2] = allocatedName;
    state.r[3] = kMachMsgTypeMakeSend;
    const auto allocatedMakeSend = syscalls.dispatch(state, 0, false);
    assert(allocatedMakeSend.handled && state.r[0] == 0u);

    state = {};
    state.r[12] = static_cast<uint32_t>(-19);
    state.r[0] = 0x102u;
    state.r[1] = allocatedName;
    state.r[2] = kMachPortRightSend;
    state.r[3] = 1u;
    const auto addSendRef = syscalls.dispatch(state, 0, false);
    assert(addSendRef.handled && state.r[0] == 0u);

    for (int index = 0; index < 2; ++index) {
        state = {};
        state.r[12] = static_cast<uint32_t>(-18);
        state.r[0] = 0x102u;
        state.r[1] = allocatedName;
        const auto deallocated = syscalls.dispatch(state, 0, false);
        assert(deallocated.handled && state.r[0] == 0u);
    }
    state = {};
    state.r[12] = static_cast<uint32_t>(-18);
    state.r[0] = 0x102u;
    state.r[1] = allocatedName;
    const auto missingSendRef = syscalls.dispatch(state, 0, false);
    assert(missingSendRef.handled && state.r[0] == kKernInvalidRight);

    state = {};
    state.r[12] = static_cast<uint32_t>(-17);
    state.r[0] = 0x102u;
    state.r[1] = allocatedName;
    const auto destroyedPort = syscalls.dispatch(state, 0, false);
    assert(destroyedPort.handled && state.r[0] == 0u);

    state = {};
    state.r[12] = static_cast<uint32_t>(-17);
    state.r[0] = 0x102u;
    state.r[1] = allocatedName;
    const auto destroyMissing = syscalls.dispatch(state, 0, false);
    assert(destroyMissing.handled && state.r[0] == kKernInvalidName);

    state = {};
    state.r[12] = static_cast<uint32_t>(-31);
    state.r[0] = kMachMessageAddress;
    state.r[1] = kMachReceiveMsg;
    state.r[3] = 32u;
    state.r[4] = allocatedName;
    const auto receiveDestroyed = syscalls.dispatch(state, 0, false);
    assert(receiveDestroyed.handled && state.r[0] == kMachReceiveInvalidName);

'''
tests = tests[:block_start] + new_tests + tests[block_end:]
test_path.write_text(tests)
