#!/usr/bin/env python3
from pathlib import Path

source_path = Path('runtime/LC32DarwinSyscalls.cpp')
test_path = Path('runtime/tests/LC32DarwinSyscallsTests.cpp')
source = source_path.read_text()
tests = test_path.read_text()

anchor = '    switch (number) {'
pos = source.rfind(anchor)
if pos < 0:
    raise SystemExit('Mach switch anchor missing')

helper = r'''    const auto queueServiceMigReply = [&](uint32_t destination,
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
            if (replyPort == machPorts_.end() || replyPort->second.receiveRefs == 0) {
                return;
            }

            constexpr uint8_t kNdr[8] = {0u, 0u, 0u, 0u, 1u, 0u, 0u, 0u};
            std::vector<uint8_t> reply(36u + words.size() * sizeof(uint32_t), 0u);
            const uint32_t size = static_cast<uint32_t>(reply.size());
            const uint32_t local = replyName;
            const uint32_t replyId = requestId + 100u;
            std::memcpy(reply.data() + 4u, &size, 4u);
            std::memcpy(reply.data() + 12u, &local, 4u);
            std::memcpy(reply.data() + 20u, &replyId, 4u);
            std::memcpy(reply.data() + 24u, kNdr, sizeof(kNdr));
            std::memcpy(reply.data() + 32u, &returnCode, 4u);
            if (!words.empty()) {
                std::memcpy(reply.data() + 36u,
                            words.data(),
                            words.size() * sizeof(uint32_t));
            }
            replyPort->second.messages.push_back(std::move(reply));
        };

        constexpr int32_t kMigBadId = -303;
        if (destination != kNotificationCenterPort) {
            queueInlineReply(kMigBadId, {});
            return true;
        }

        switch (requestId) {
            case 1002u: // _notify_server_check
                if (request.size() >= 36u) {
                    queueInlineReply(0, {0u, 0u}); // check=false, status=OK
                } else {
                    queueInlineReply(kMigBadId, {});
                }
                return true;
            case 1004u: // _notify_server_suspend
            case 1005u: // _notify_server_resume
                if (request.size() >= 36u) {
                    queueInlineReply(0, {0u}); // status=OK
                } else {
                    queueInlineReply(kMigBadId, {});
                }
                return true;
            case 1023u: // _notify_server_checkin
                queueInlineReply(0, {3u, 42u, 0u}); // version, server PID, status
                return true;
            default:
                queueInlineReply(kMigBadId, {});
                return true;
        }
    };

'''
source = source[:pos] + helper + source[pos:]

old_send = '''                const bool handledBootstrapLookup =
                    destination == kBootstrapPort &&
                    queueBootstrapLookupReply(message, replyName);
                if (!handledHostMig && !handledTaskSpecialPort &&
                    !handledBootstrapLookup) {
                    port->second.messages.push_back(std::move(message));
                }
'''
new_send = '''                const bool handledBootstrapLookup =
                    destination == kBootstrapPort &&
                    queueBootstrapLookupReply(message, replyName);
                const bool handledServiceMig =
                    queueServiceMigReply(destination, message, replyName);
                if (!handledHostMig && !handledTaskSpecialPort &&
                    !handledBootstrapLookup && !handledServiceMig) {
                    port->second.messages.push_back(std::move(message));
                }
'''
if old_send not in source:
    raise SystemExit('service MIG interception anchor missing')
source = source.replace(old_send, new_send, 1)

insert_before = '    char rootTemplate[] = "/tmp/lc32-syscalls-XXXXXX";'
if insert_before not in tests:
    raise SystemExit('test insertion anchor missing')

service_tests = r'''
    const auto sendServiceRequest = [&](uint32_t destination,
                                        uint32_t requestId,
                                        const std::vector<uint32_t>& body,
                                        bool expectsReply) {
        const uint32_t requestSize =
            static_cast<uint32_t>(24u + body.size() * sizeof(uint32_t));
        uint32_t header[6] = {
            19u, requestSize, destination, expectsReply ? replyName : 0u, 0u, requestId};
        std::memcpy(lowMemory.data() + kMachMessageAddress, header, sizeof(header));
        if (!body.empty()) {
            std::memcpy(lowMemory.data() + kMachMessageAddress + sizeof(header),
                        body.data(),
                        body.size() * sizeof(uint32_t));
        }
        state = {};
        state.r[12] = static_cast<uint32_t>(-31);
        state.r[0] = kMachMessageAddress;
        state.r[1] = kMachSendMsg;
        state.r[2] = requestSize;
        const auto sent = syscalls.dispatch(state, 0, false);
        assert(sent.handled && state.r[0] == 0u);
    };
    const auto receiveServiceReply = [&](uint32_t capacity) {
        std::memset(lowMemory.data() + kMachMessageAddress, 0, capacity);
        state = {};
        state.r[12] = static_cast<uint32_t>(-31);
        state.r[0] = kMachMessageAddress;
        state.r[1] = kMachReceiveMsg;
        state.r[3] = capacity;
        state.r[4] = replyName;
        return syscalls.dispatch(state, 0, false);
    };

    // notify_ipc subsystem 1000: _notify_server_check is request 1002.
    sendServiceRequest(0x111u, 1002u, {0u, 0u, 7u}, true);
    const auto notifyCheckReply = receiveServiceReply(64u);
    assert(notifyCheckReply.handled && state.r[0] == 0u);
    uint32_t serviceReplySize = 0;
    uint32_t serviceReplyId = 0;
    int32_t serviceReturnCode = 1;
    uint32_t notifyCheckValue = 1;
    uint32_t notifyStatus = 1;
    std::memcpy(&serviceReplySize, lowMemory.data() + kMachMessageAddress + 4u, 4u);
    std::memcpy(&serviceReplyId, lowMemory.data() + kMachMessageAddress + 20u, 4u);
    std::memcpy(&serviceReturnCode, lowMemory.data() + kMachMessageAddress + 32u, 4u);
    std::memcpy(&notifyCheckValue, lowMemory.data() + kMachMessageAddress + 36u, 4u);
    std::memcpy(&notifyStatus, lowMemory.data() + kMachMessageAddress + 40u, 4u);
    assert(serviceReplySize == 44u && serviceReplyId == 1102u);
    assert(serviceReturnCode == 0 && notifyCheckValue == 0u && notifyStatus == 0u);

    // notify check-in returns deterministic IPC version 3 and a stable virtual PID.
    sendServiceRequest(0x111u, 1023u, {}, true);
    const auto notifyCheckinReply = receiveServiceReply(64u);
    assert(notifyCheckinReply.handled && state.r[0] == 0u);
    uint32_t notifyVersion = 0;
    uint32_t notifyServerPid = 0;
    std::memcpy(&serviceReplySize, lowMemory.data() + kMachMessageAddress + 4u, 4u);
    std::memcpy(&serviceReplyId, lowMemory.data() + kMachMessageAddress + 20u, 4u);
    std::memcpy(&serviceReturnCode, lowMemory.data() + kMachMessageAddress + 32u, 4u);
    std::memcpy(&notifyVersion, lowMemory.data() + kMachMessageAddress + 36u, 4u);
    std::memcpy(&notifyServerPid, lowMemory.data() + kMachMessageAddress + 40u, 4u);
    std::memcpy(&notifyStatus, lowMemory.data() + kMachMessageAddress + 44u, 4u);
    assert(serviceReplySize == 48u && serviceReplyId == 1123u);
    assert(serviceReturnCode == 0 && notifyVersion == 3u);
    assert(notifyServerPid == 42u && notifyStatus == 0u);

    // Unknown notify and cfprefsd calls fail immediately with MIG_BAD_ID (-303).
    sendServiceRequest(0x111u, 1999u, {}, true);
    const auto notifyUnknownReply = receiveServiceReply(64u);
    assert(notifyUnknownReply.handled && state.r[0] == 0u);
    std::memcpy(&serviceReplyId, lowMemory.data() + kMachMessageAddress + 20u, 4u);
    std::memcpy(&serviceReturnCode, lowMemory.data() + kMachMessageAddress + 32u, 4u);
    assert(serviceReplyId == 2099u && serviceReturnCode == -303);

    sendServiceRequest(0x112u, 6000u, {}, true);
    const auto prefsUnknownReply = receiveServiceReply(64u);
    assert(prefsUnknownReply.handled && state.r[0] == 0u);
    std::memcpy(&serviceReplyId, lowMemory.data() + kMachMessageAddress + 20u, 4u);
    std::memcpy(&serviceReturnCode, lowMemory.data() + kMachMessageAddress + 32u, 4u);
    assert(serviceReplyId == 6100u && serviceReturnCode == -303);

    // One-way logger messages are consumed rather than accumulating forever.
    sendServiceRequest(0x110u, 5000u, {}, false);
    state = {};
    state.r[12] = static_cast<uint32_t>(-31);
    state.r[0] = kMachMessageAddress;
    state.r[1] = kMachReceiveMsg;
    state.r[3] = 64u;
    state.r[4] = 0x110u;
    const auto loggerQueueEmpty = syscalls.dispatch(state, 0, false);
    assert(loggerQueueEmpty.handled && state.r[0] == 0x10004003u);

'''
tests = tests.replace(insert_before, service_tests + insert_before, 1)

source_path.write_text(source)
test_path.write_text(tests)
