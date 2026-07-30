#!/usr/bin/env python3
from pathlib import Path

hpp_path = Path('runtime/LC32DarwinSyscalls.hpp')
cpp_path = Path('runtime/LC32DarwinSyscalls.cpp')
test_path = Path('runtime/tests/LC32DarwinSyscallsTests.cpp')
hpp = hpp_path.read_text()
cpp = cpp_path.read_text()
tests = test_path.read_text()

hpp_anchor = '''    struct MachPort {
        std::deque<std::vector<uint8_t>> messages;
        uint32_t receiveRefs = 0;
        uint32_t sendRefs = 0;
        uint32_t sendOnceRefs = 0;
        bool immortal = false;
    };
'''
notify_struct = hpp_anchor + '''
    struct NotifyRegistration {
        std::string name;
        uint64_t nameId = 0;
        uint64_t state = 0;
        bool pending = false;
        bool suspended = false;
    };
'''
if 'struct NotifyRegistration' not in hpp:
    if hpp_anchor not in hpp:
        raise SystemExit('header struct anchor missing')
    hpp = hpp.replace(hpp_anchor, notify_struct, 1)

member_anchor = '''    std::unordered_map<uint32_t, MachPort> machPorts_;
    uint32_t nextMachPort_ = 0x200u;
'''
member_replacement = '''    std::unordered_map<uint32_t, MachPort> machPorts_;
    std::unordered_map<int32_t, NotifyRegistration> notifyRegistrations_;
    std::unordered_map<std::string, uint64_t> notifyNameIds_;
    uint64_t nextNotifyNameId_ = 1u;
    uint32_t nextMachPort_ = 0x200u;
'''
if 'notifyRegistrations_' not in hpp:
    if member_anchor not in hpp:
        raise SystemExit('header member anchor missing')
    hpp = hpp.replace(member_anchor, member_replacement, 1)

start = cpp.find('    const auto queueServiceMigReply = ') 
end = cpp.find('\n    switch (number) {', start)
if start < 0 or end < 0:
    raise SystemExit('service helper bounds missing')
old = cpp[start:end]
new = r'''    const auto queueServiceMigReply = [&](uint32_t destination,
                                                   const std::vector<uint8_t>& request,
                                                   uint32_t replyName) -> bool {
        if (destination != kSystemLoggerPort &&
            destination != kNotificationCenterPort &&
            destination != kCfprefsdPort) {
            return false;
        }
        if (request.size() < kMachHeaderSize) return true;

        uint32_t requestId = 0;
        std::memcpy(&requestId, request.data() + 20u, sizeof(requestId));

        const auto queueInlineReply = [&](int32_t returnCode,
                                          const std::vector<uint32_t>& words) {
            if (replyName == 0) return;
            auto replyPort = machPorts_.find(replyName);
            if (replyPort == machPorts_.end() || replyPort->second.receiveRefs == 0) return;
            constexpr uint8_t kNdr[8] = {0u, 0u, 0u, 0u, 1u, 0u, 0u, 0u};
            std::vector<uint8_t> reply(36u + words.size() * 4u, 0u);
            const uint32_t size = static_cast<uint32_t>(reply.size());
            const uint32_t local = replyName;
            const uint32_t replyId = requestId + 100u;
            std::memcpy(reply.data() + 4u, &size, 4u);
            std::memcpy(reply.data() + 12u, &local, 4u);
            std::memcpy(reply.data() + 20u, &replyId, 4u);
            std::memcpy(reply.data() + 24u, kNdr, sizeof(kNdr));
            std::memcpy(reply.data() + 32u, &returnCode, 4u);
            if (!words.empty()) std::memcpy(reply.data() + 36u, words.data(), words.size() * 4u);
            replyPort->second.messages.push_back(std::move(reply));
        };
        const auto tokenAt32 = [&]() -> int32_t {
            int32_t token = 0;
            if (request.size() >= 36u) std::memcpy(&token, request.data() + 32u, 4u);
            return token;
        };
        constexpr int32_t kMigBadId = -303;
        constexpr uint32_t kNotifyOk = 0u;
        constexpr uint32_t kNotifyInvalidToken = 2u;

        if (destination != kNotificationCenterPort) {
            queueInlineReply(kMigBadId, {});
            return true;
        }

        switch (requestId) {
            case 1002u: { // check(token) -> check,status and clear pending
                const int32_t token = tokenAt32();
                auto it = notifyRegistrations_.find(token);
                if (it == notifyRegistrations_.end()) {
                    queueInlineReply(0, {0u, kNotifyInvalidToken});
                } else {
                    const uint32_t pending = (!it->second.suspended && it->second.pending) ? 1u : 0u;
                    if (pending != 0u) it->second.pending = false;
                    queueInlineReply(0, {pending, kNotifyOk});
                }
                return true;
            }
            case 1003u: { // get_state(token)
                const int32_t token = tokenAt32();
                auto it = notifyRegistrations_.find(token);
                if (it == notifyRegistrations_.end()) {
                    queueInlineReply(0, {0u, 0u, kNotifyInvalidToken});
                } else {
                    queueInlineReply(0, {static_cast<uint32_t>(it->second.state),
                                         static_cast<uint32_t>(it->second.state >> 32u),
                                         kNotifyOk});
                }
                return true;
            }
            case 1004u:
            case 1005u: {
                const int32_t token = tokenAt32();
                auto it = notifyRegistrations_.find(token);
                const uint32_t status = it == notifyRegistrations_.end() ? kNotifyInvalidToken : kNotifyOk;
                if (it != notifyRegistrations_.end()) it->second.suspended = requestId == 1004u;
                queueInlineReply(0, {status});
                return true;
            }
            case 1009u: { // post by stable name id, one-way
                if (request.size() >= 40u) {
                    uint64_t nameId = 0;
                    std::memcpy(&nameId, request.data() + 32u, 8u);
                    for (auto& entry : notifyRegistrations_) {
                        if (entry.second.nameId == nameId) entry.second.pending = true;
                    }
                }
                return true;
            }
            case 1011u: { // fixed-name compatibility form: name[128] at 32, token at 160
                if (request.size() < 164u) return true;
                const char* nameBytes = reinterpret_cast<const char*>(request.data() + 32u);
                size_t length = 0;
                while (length < 128u && nameBytes[length] != '\0') ++length;
                if (length == 0u || length == 128u) return true;
                int32_t token = 0;
                std::memcpy(&token, request.data() + 160u, 4u);
                const std::string name(nameBytes, length);
                uint64_t nameId = 0;
                auto nameIt = notifyNameIds_.find(name);
                if (nameIt == notifyNameIds_.end()) {
                    nameId = nextNotifyNameId_++;
                    notifyNameIds_.emplace(name, nameId);
                } else {
                    nameId = nameIt->second;
                }
                notifyRegistrations_[token] = NotifyRegistration{name, nameId, 0u, false, false};
                return true;
            }
            case 1016u:
                notifyRegistrations_.erase(tokenAt32());
                return true;
            case 1018u: { // get_state_3(token) -> state,nid,status
                const int32_t token = tokenAt32();
                auto it = notifyRegistrations_.find(token);
                if (it == notifyRegistrations_.end()) {
                    queueInlineReply(0, {0u, 0u, UINT32_MAX, UINT32_MAX, kNotifyInvalidToken});
                } else {
                    queueInlineReply(0, {static_cast<uint32_t>(it->second.state),
                                         static_cast<uint32_t>(it->second.state >> 32u),
                                         static_cast<uint32_t>(it->second.nameId),
                                         static_cast<uint32_t>(it->second.nameId >> 32u),
                                         kNotifyOk});
                }
                return true;
            }
            case 1020u: { // set_state_3(token,state) -> nid,status
                if (request.size() < 44u) { queueInlineReply(kMigBadId, {}); return true; }
                const int32_t token = tokenAt32();
                uint64_t value = 0;
                std::memcpy(&value, request.data() + 36u, 8u);
                auto it = notifyRegistrations_.find(token);
                if (it == notifyRegistrations_.end()) {
                    queueInlineReply(0, {UINT32_MAX, UINT32_MAX, kNotifyInvalidToken});
                } else {
                    it->second.state = value;
                    queueInlineReply(0, {static_cast<uint32_t>(it->second.nameId),
                                         static_cast<uint32_t>(it->second.nameId >> 32u),
                                         kNotifyOk});
                }
                return true;
            }
            case 1023u:
                queueInlineReply(0, {3u, 42u, kNotifyOk});
                return true;
            default:
                queueInlineReply(kMigBadId, {});
                return true;
        }
    };
'''
cpp = cpp[:start] + new + cpp[end:]

anchor = '    char rootTemplate[] = "/tmp/lc32-syscalls-XXXXXX";'
if anchor not in tests:
    raise SystemExit('test anchor missing')
block = r'''
    // Stateful notify registration compatibility form.
    std::vector<uint8_t> registerRequest(164u, 0u);
    uint32_t registerHeader[6] = {19u, 164u, 0x111u, 0u, 0u, 1011u};
    std::memcpy(registerRequest.data(), registerHeader, sizeof(registerHeader));
    const char notifyName[] = "com.example.lc32.state";
    std::memcpy(registerRequest.data() + 32u, notifyName, sizeof(notifyName));
    const int32_t notifyToken = 77;
    std::memcpy(registerRequest.data() + 160u, &notifyToken, 4u);
    std::memcpy(lowMemory.data() + kMachMessageAddress, registerRequest.data(), registerRequest.size());
    state = {};
    state.r[12] = static_cast<uint32_t>(-31);
    state.r[0] = kMachMessageAddress;
    state.r[1] = kMachSendMsg;
    state.r[2] = 164u;
    assert(syscalls.dispatch(state, 0, false).handled && state.r[0] == 0u);

    // Set token state to a 64-bit value and recover its stable name ID.
    sendServiceRequest(0x111u, 1020u, {0u, 0u, 77u, 0x55667788u, 0x11223344u}, true);
    assert(receiveServiceReply(64u).handled && state.r[0] == 0u);
    uint32_t notifyNameIdLow = 0;
    uint32_t notifyNameIdHigh = 0;
    std::memcpy(&notifyNameIdLow, lowMemory.data() + kMachMessageAddress + 36u, 4u);
    std::memcpy(&notifyNameIdHigh, lowMemory.data() + kMachMessageAddress + 40u, 4u);
    assert(notifyNameIdLow != 0u && notifyNameIdHigh == 0u);

    sendServiceRequest(0x111u, 1003u, {0u, 0u, 77u}, true);
    assert(receiveServiceReply(64u).handled && state.r[0] == 0u);
    uint32_t stateLow = 0;
    uint32_t stateHigh = 0;
    std::memcpy(&stateLow, lowMemory.data() + kMachMessageAddress + 36u, 4u);
    std::memcpy(&stateHigh, lowMemory.data() + kMachMessageAddress + 40u, 4u);
    assert(stateLow == 0x55667788u && stateHigh == 0x11223344u);

    // Post by name ID, then check consumes the pending edge exactly once.
    sendServiceRequest(0x111u, 1009u, {0u, 0u, notifyNameIdLow, notifyNameIdHigh}, false);
    sendServiceRequest(0x111u, 1002u, {0u, 0u, 77u}, true);
    assert(receiveServiceReply(64u).handled && state.r[0] == 0u);
    uint32_t pendingOnce = 0;
    std::memcpy(&pendingOnce, lowMemory.data() + kMachMessageAddress + 36u, 4u);
    assert(pendingOnce == 1u);
    sendServiceRequest(0x111u, 1002u, {0u, 0u, 77u}, true);
    assert(receiveServiceReply(64u).handled && state.r[0] == 0u);
    std::memcpy(&pendingOnce, lowMemory.data() + kMachMessageAddress + 36u, 4u);
    assert(pendingOnce == 0u);

    // Cancellation is one-way; subsequent check reports invalid token.
    sendServiceRequest(0x111u, 1016u, {0u, 0u, 77u}, false);
    sendServiceRequest(0x111u, 1002u, {0u, 0u, 77u}, true);
    assert(receiveServiceReply(64u).handled && state.r[0] == 0u);
    uint32_t canceledStatus = 0;
    std::memcpy(&canceledStatus, lowMemory.data() + kMachMessageAddress + 40u, 4u);
    assert(canceledStatus == 2u);

'''
tests = tests.replace(anchor, block + anchor, 1)

hpp_path.write_text(hpp)
cpp_path.write_text(cpp)
test_path.write_text(tests)
