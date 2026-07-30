#!/usr/bin/env python3
from pathlib import Path

header_path = Path('runtime/LC32DarwinSyscalls.hpp')
header = header_path.read_text()
header = header.replace('#include <functional>\n', '#include <deque>\n#include <functional>\n', 1)
header = header.replace('#include <unordered_map>\n', '#include <unordered_map>\n#include <vector>\n', 1)
header = header.replace('    struct GuestFile {\n        int hostFd = -1;\n        uint32_t openFlags = 0;\n        uint32_t descriptorFlags = 0;\n        void* directory = nullptr;\n    };\n', '''    struct GuestFile {
        int hostFd = -1;
        uint32_t openFlags = 0;
        uint32_t descriptorFlags = 0;
        void* directory = nullptr;
    };

    struct MachPort {
        std::deque<std::vector<uint8_t>> messages;
    };
''', 1)
header = header.replace('    std::unordered_map<int, GuestFile> guestFiles_;\n', '''    std::unordered_map<int, GuestFile> guestFiles_;
    std::unordered_map<uint32_t, MachPort> machPorts_;
    uint32_t nextMachPort_ = 0x200u;
''', 1)
header_path.write_text(header)

source_path = Path('runtime/LC32DarwinSyscalls.cpp')
source = source_path.read_text()
old = '''TrapResult DarwinSyscalls::dispatchMach(CPUState&, uint32_t number) {
    switch (number) {
        case 26:
            return ok(number, 0x100, "mach_reply_port placeholder");
        case 27:
            return ok(number, 0x101, "thread_self_trap placeholder");
        case 28:
            return ok(number, 0x102, "task_self_trap placeholder");
        case 29:
            return ok(number, 0x103, "host_self_trap placeholder");
        default: {
            TrapResult result;
            result.number = number;
            result.detail = "unsupported Mach trap";
            return result;
        }
    }
}
'''
new = r'''TrapResult DarwinSyscalls::dispatchMach(CPUState& state, uint32_t number) {
    constexpr uint32_t kReplyPort = 0x100u;
    constexpr uint32_t kThreadPort = 0x101u;
    constexpr uint32_t kTaskPort = 0x102u;
    constexpr uint32_t kHostPort = 0x103u;
    constexpr uint32_t kMachSendMsg = 0x00000001u;
    constexpr uint32_t kMachReceiveMsg = 0x00000002u;
    constexpr uint32_t kMachMessageComplex = 0x80000000u;
    constexpr uint32_t kMachSuccess = 0u;
    constexpr uint32_t kMachSendInvalidData = 0x10000002u;
    constexpr uint32_t kMachSendInvalidDestination = 0x10000003u;
    constexpr uint32_t kMachSendMessageTooSmall = 0x10000008u;
    constexpr uint32_t kMachReceiveInvalidName = 0x10004002u;
    constexpr uint32_t kMachReceiveTimedOut = 0x10004003u;
    constexpr uint32_t kMachReceiveTooLarge = 0x10004004u;
    constexpr uint32_t kMachHeaderSize = 24u;
    constexpr uint32_t kMaximumMachMessage = 1024u * 1024u;

    const auto ensureBuiltinPorts = [&]() {
        machPorts_.try_emplace(kReplyPort);
        machPorts_.try_emplace(kThreadPort);
        machPorts_.try_emplace(kTaskPort);
        machPorts_.try_emplace(kHostPort);
    };
    ensureBuiltinPorts();

    switch (number) {
        case 26: {
            uint32_t candidate = nextMachPort_;
            while (candidate == 0 || machPorts_.find(candidate) != machPorts_.end()) {
                ++candidate;
                if (candidate < 0x200u) candidate = 0x200u;
            }
            nextMachPort_ = candidate + 1u;
            machPorts_.try_emplace(candidate);
            return ok(number, static_cast<int32_t>(candidate), "mach_reply_port");
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
                return ok(number, static_cast<int32_t>(kMachSuccess), "mach_msg no-op");
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
                message.resize(headerSize);
                port->second.messages.push_back(std::move(message));
            }

            if (receive) {
                auto port = machPorts_.find(receiveName);
                if (receiveName == 0 || port == machPorts_.end()) {
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
            return ok(number, static_cast<int32_t>(kMachSuccess), "mach_msg_trap");
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
if old not in source:
    raise SystemExit('Mach dispatch replacement point not found')
source_path.write_text(source.replace(old, new, 1))

test_path = Path('runtime/tests/LC32DarwinSyscallsTests.cpp')
test = test_path.read_text()
needle = '''    state = {};
    state.r[12] = static_cast<uint32_t>(-28);
    const auto taskSelf = syscalls.dispatch(state, 0, false);
    assert(taskSelf.handled && taskSelf.trapClass == TrapClass::Mach);
    assert(state.r[0] == 0x102u);
'''
replacement = needle + r'''

    state = {};
    state.r[12] = static_cast<uint32_t>(-26);
    const auto replyPort = syscalls.dispatch(state, 0, false);
    assert(replyPort.handled && replyPort.errorNumber == 0);
    const uint32_t replyName = state.r[0];
    assert(replyName >= 0x200u);

    constexpr uint32_t kMachMessageAddress = 0x0100u;
    constexpr uint32_t kMachSendMsg = 0x00000001u;
    constexpr uint32_t kMachReceiveMsg = 0x00000002u;
    constexpr uint32_t kMachReceiveTimedOut = 0x10004003u;
    constexpr uint32_t kMachReceiveTooLarge = 0x10004004u;
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
'''
if needle not in test:
    raise SystemExit('Mach test insertion point not found')
test_path.write_text(test.replace(needle, replacement, 1))
