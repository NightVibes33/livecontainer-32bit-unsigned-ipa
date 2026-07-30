#!/usr/bin/env python3
from pathlib import Path

source_path = Path('runtime/LC32DarwinSyscalls.cpp')
test_path = Path('runtime/tests/LC32DarwinSyscallsTests.cpp')
source = source_path.read_text()
tests = test_path.read_text()

source = source.replace(
    '    constexpr uint32_t kBootstrapPort = 0x104u;\n',
    '    constexpr uint32_t kBootstrapPort = 0x104u;\n'
    '    constexpr uint32_t kSystemLoggerPort = 0x110u;\n'
    '    constexpr uint32_t kNotificationCenterPort = 0x111u;\n'
    '    constexpr uint32_t kCfprefsdPort = 0x112u;\n',
    1,
)
source = source.replace(
    '        addBuiltin(kBootstrapPort);\n',
    '        addBuiltin(kBootstrapPort);\n'
    '        addBuiltin(kSystemLoggerPort);\n'
    '        addBuiltin(kNotificationCenterPort);\n'
    '        addBuiltin(kCfprefsdPort);\n',
    1,
)

anchor = '    switch (number) {'
pos = source.rfind(anchor)
if pos < 0:
    raise SystemExit('Mach switch anchor missing')

helper = r'''    const auto queueBootstrapLookupReply = [&](const std::vector<uint8_t>& request,
                                                     uint32_t replyName) -> bool {
        if (replyName == 0 || request.size() < 160u) return false;
        auto replyPort = machPorts_.find(replyName);
        if (replyPort == machPorts_.end() || replyPort->second.receiveRefs == 0) {
            return false;
        }

        uint32_t requestId = 0;
        std::memcpy(&requestId, request.data() + 20u, sizeof(requestId));
        if (requestId != 404u) return false;

        const char* serviceBytes =
            reinterpret_cast<const char*>(request.data() + 32u);
        size_t serviceLength = 0;
        while (serviceLength < 128u && serviceBytes[serviceLength] != '\0') {
            ++serviceLength;
        }
        if (serviceLength == 128u) return false;
        const std::string serviceName(serviceBytes, serviceLength);

        uint32_t servicePort = 0;
        if (serviceName == "com.apple.system.logger") {
            servicePort = kSystemLoggerPort;
        } else if (serviceName == "com.apple.system.notification_center") {
            servicePort = kNotificationCenterPort;
        } else if (serviceName == "com.apple.cfprefsd.daemon") {
            servicePort = kCfprefsdPort;
        }

        constexpr uint8_t kNdr[8] = {0u, 0u, 0u, 0u, 1u, 0u, 0u, 0u};
        constexpr uint32_t kBootstrapUnknownService = 1102u;
        if (servicePort == 0) {
            std::vector<uint8_t> reply(36u, 0u);
            const uint32_t size = static_cast<uint32_t>(reply.size());
            const uint32_t local = replyName;
            const uint32_t replyId = 504u;
            std::memcpy(reply.data() + 4u, &size, 4u);
            std::memcpy(reply.data() + 12u, &local, 4u);
            std::memcpy(reply.data() + 20u, &replyId, 4u);
            std::memcpy(reply.data() + 24u, kNdr, sizeof(kNdr));
            std::memcpy(reply.data() + 32u, &kBootstrapUnknownService, 4u);
            replyPort->second.messages.push_back(std::move(reply));
            return true;
        }

        constexpr uint32_t kDescriptorCount = 1u;
        constexpr uint32_t kCopySendPortDescriptor =
            (kMachMsgTypeCopySend << 16u);
        std::vector<uint8_t> reply(52u, 0u);
        const uint32_t bits = kMachMessageComplex;
        const uint32_t size = static_cast<uint32_t>(reply.size());
        const uint32_t local = replyName;
        const uint32_t replyId = 504u;
        std::memcpy(reply.data(), &bits, 4u);
        std::memcpy(reply.data() + 4u, &size, 4u);
        std::memcpy(reply.data() + 12u, &local, 4u);
        std::memcpy(reply.data() + 20u, &replyId, 4u);
        std::memcpy(reply.data() + 24u, &kDescriptorCount, 4u);
        std::memcpy(reply.data() + 28u, &servicePort, 4u);
        std::memcpy(reply.data() + 36u, &kCopySendPortDescriptor, 4u);
        std::memcpy(reply.data() + 40u, kNdr, sizeof(kNdr));
        std::memcpy(reply.data() + 48u, &kKernSuccess, 4u);
        replyPort->second.messages.push_back(std::move(reply));
        return true;
    };

'''
source = source[:pos] + helper + source[pos:]

old_send = '''                const bool handledTaskSpecialPort =
                    destination == kTaskPort &&
                    queueTaskSpecialPortReply(message, replyName);
                if (!handledHostMig && !handledTaskSpecialPort) {
                    port->second.messages.push_back(std::move(message));
                }
'''
new_send = '''                const bool handledTaskSpecialPort =
                    destination == kTaskPort &&
                    queueTaskSpecialPortReply(message, replyName);
                const bool handledBootstrapLookup =
                    destination == kBootstrapPort &&
                    queueBootstrapLookupReply(message, replyName);
                if (!handledHostMig && !handledTaskSpecialPort &&
                    !handledBootstrapLookup) {
                    port->second.messages.push_back(std::move(message));
                }
'''
if old_send not in source:
    raise SystemExit('MIG interception anchor missing')
source = source.replace(old_send, new_send, 1)

insert_before = '    char rootTemplate[] = "/tmp/lc32-syscalls-XXXXXX";'
if insert_before not in tests:
    raise SystemExit('test insertion anchor missing')

lookup_tests = r'''
    const auto sendBootstrapLookup = [&](const std::string& serviceName) {
        constexpr uint32_t kBootstrapRequestSize = 160u;
        std::memset(lowMemory.data() + kMachMessageAddress, 0,
                    kBootstrapRequestSize);
        uint32_t header[6] = {
            19u, kBootstrapRequestSize, 0x104u, replyName, 0u, 404u};
        std::memcpy(lowMemory.data() + kMachMessageAddress,
                    header,
                    sizeof(header));
        assert(serviceName.size() < 128u);
        std::memcpy(lowMemory.data() + kMachMessageAddress + 32u,
                    serviceName.c_str(),
                    serviceName.size() + 1u);
        state = {};
        state.r[12] = static_cast<uint32_t>(-31);
        state.r[0] = kMachMessageAddress;
        state.r[1] = kMachSendMsg;
        state.r[2] = kBootstrapRequestSize;
        const auto sent = syscalls.dispatch(state, 0, false);
        assert(sent.handled && state.r[0] == 0u);
    };
    const auto receiveBootstrapReply = [&](uint32_t capacity) {
        std::memset(lowMemory.data() + kMachMessageAddress, 0, capacity);
        state = {};
        state.r[12] = static_cast<uint32_t>(-31);
        state.r[0] = kMachMessageAddress;
        state.r[1] = kMachReceiveMsg;
        state.r[3] = capacity;
        state.r[4] = replyName;
        return syscalls.dispatch(state, 0, false);
    };

    sendBootstrapLookup("com.apple.system.notification_center");
    const auto lookupSuccess = receiveBootstrapReply(64u);
    assert(lookupSuccess.handled && state.r[0] == 0u);
    uint32_t lookupBits = 0;
    uint32_t lookupSize = 0;
    uint32_t lookupReplyId = 0;
    uint32_t lookupDescriptorCount = 0;
    uint32_t lookupPort = 0;
    uint32_t lookupDisposition = 0;
    uint32_t lookupReturn = 1;
    std::memcpy(&lookupBits, lowMemory.data() + kMachMessageAddress, 4u);
    std::memcpy(&lookupSize, lowMemory.data() + kMachMessageAddress + 4u, 4u);
    std::memcpy(&lookupReplyId, lowMemory.data() + kMachMessageAddress + 20u, 4u);
    std::memcpy(&lookupDescriptorCount, lowMemory.data() + kMachMessageAddress + 24u, 4u);
    std::memcpy(&lookupPort, lowMemory.data() + kMachMessageAddress + 28u, 4u);
    std::memcpy(&lookupDisposition, lowMemory.data() + kMachMessageAddress + 36u, 4u);
    std::memcpy(&lookupReturn, lowMemory.data() + kMachMessageAddress + 48u, 4u);
    assert((lookupBits & 0x80000000u) != 0u);
    assert(lookupSize == 52u && lookupReplyId == 504u);
    assert(lookupDescriptorCount == 1u && lookupPort == 0x111u);
    assert(((lookupDisposition >> 16u) & 0xffu) == 19u);
    assert(lookupReturn == 0u);

    sendBootstrapLookup("com.example.unsupported");
    const auto lookupMissing = receiveBootstrapReply(64u);
    assert(lookupMissing.handled && state.r[0] == 0u);
    uint32_t missingBits = 1;
    uint32_t missingSize = 0;
    uint32_t missingReplyId = 0;
    uint32_t missingReturn = 0;
    std::memcpy(&missingBits, lowMemory.data() + kMachMessageAddress, 4u);
    std::memcpy(&missingSize, lowMemory.data() + kMachMessageAddress + 4u, 4u);
    std::memcpy(&missingReplyId, lowMemory.data() + kMachMessageAddress + 20u, 4u);
    std::memcpy(&missingReturn, lowMemory.data() + kMachMessageAddress + 32u, 4u);
    assert((missingBits & 0x80000000u) == 0u);
    assert(missingSize == 36u && missingReplyId == 504u);
    assert(missingReturn == 1102u);

'''
tests = tests.replace(insert_before, lookup_tests + insert_before, 1)

source_path.write_text(source)
test_path.write_text(tests)
