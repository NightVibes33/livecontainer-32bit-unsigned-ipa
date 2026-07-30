#!/usr/bin/env python3
from pathlib import Path

source_path = Path('runtime/LC32DarwinSyscalls.cpp')
test_path = Path('runtime/tests/LC32DarwinSyscallsTests.cpp')
source = source_path.read_text()
tests = test_path.read_text()

source = source.replace(
    '    constexpr uint32_t kHostPort = 0x103u;\n',
    '    constexpr uint32_t kHostPort = 0x103u;\n'
    '    constexpr uint32_t kBootstrapPort = 0x104u;\n',
    1,
)
source = source.replace(
    '        addBuiltin(kHostPort);\n',
    '        addBuiltin(kHostPort);\n'
    '        addBuiltin(kBootstrapPort);\n',
    1,
)

anchor = '    const auto queueHostMigReply = [&]('
pos = source.find(anchor)
if pos < 0:
    raise SystemExit('host MIG helper anchor missing')

switch_pos = source.find('    switch (number) {', pos)
if switch_pos < 0:
    raise SystemExit('Mach switch missing')

helper = r'''    const auto queueTaskSpecialPortReply = [&](const std::vector<uint8_t>& request,
                                                    uint32_t replyName) -> bool {
        if (replyName == 0 || request.size() < 36u) return false;
        auto replyPort = machPorts_.find(replyName);
        if (replyPort == machPorts_.end() || replyPort->second.receiveRefs == 0) {
            return false;
        }

        uint32_t requestId = 0;
        uint32_t whichPort = 0;
        std::memcpy(&requestId, request.data() + 20u, sizeof(requestId));
        std::memcpy(&whichPort, request.data() + 32u, sizeof(whichPort));
        if (requestId != 3409u || whichPort != 4u) return false;

        constexpr uint32_t kDescriptorCount = 1u;
        constexpr uint32_t kCopySendPortDescriptor =
            (kMachMsgTypeCopySend << 16u); // disposition byte, type=port descriptor
        constexpr uint8_t kNdr[8] = {0u, 0u, 0u, 0u, 1u, 0u, 0u, 0u};

        std::vector<uint8_t> reply(52u, 0u);
        const uint32_t bits = kMachMessageComplex;
        const uint32_t size = static_cast<uint32_t>(reply.size());
        const uint32_t remote = 0u;
        const uint32_t local = replyName;
        const uint32_t reserved = 0u;
        const uint32_t replyId = 3509u;
        std::memcpy(reply.data(), &bits, 4u);
        std::memcpy(reply.data() + 4u, &size, 4u);
        std::memcpy(reply.data() + 8u, &remote, 4u);
        std::memcpy(reply.data() + 12u, &local, 4u);
        std::memcpy(reply.data() + 16u, &reserved, 4u);
        std::memcpy(reply.data() + 20u, &replyId, 4u);
        std::memcpy(reply.data() + 24u, &kDescriptorCount, 4u);
        std::memcpy(reply.data() + 28u, &kBootstrapPort, 4u);
        std::memcpy(reply.data() + 36u, &kCopySendPortDescriptor, 4u);
        std::memcpy(reply.data() + 40u, kNdr, sizeof(kNdr));
        std::memcpy(reply.data() + 48u, &kKernSuccess, 4u);
        replyPort->second.messages.push_back(std::move(reply));
        return true;
    };

'''
source = source[:switch_pos] + helper + source[switch_pos:]

old_send = '''                const bool handledHostMig =
                    destination == kHostPort && queueHostMigReply(message, replyName);
                if (!handledHostMig) {
                    port->second.messages.push_back(std::move(message));
                }
'''
new_send = '''                const bool handledHostMig =
                    destination == kHostPort && queueHostMigReply(message, replyName);
                const bool handledTaskSpecialPort =
                    destination == kTaskPort &&
                    queueTaskSpecialPortReply(message, replyName);
                if (!handledHostMig && !handledTaskSpecialPort) {
                    port->second.messages.push_back(std::move(message));
                }
'''
if old_send not in source:
    raise SystemExit('MIG send interception anchor missing')
source = source.replace(old_send, new_send, 1)

insert_before = '    char rootTemplate[] = "/tmp/lc32-syscalls-XXXXXX";'
if insert_before not in tests:
    raise SystemExit('test insertion anchor missing')

bootstrap_tests = r'''
    // task_get_special_port(TASK_BOOTSTRAP_PORT) is MIG request 3409.
    const uint32_t bootstrapRequestBody[3] = {0u, 0u, 4u};
    const uint32_t bootstrapRequestSize = 36u;
    uint32_t bootstrapHeader[6] = {
        19u, bootstrapRequestSize, 0x102u, replyName, 0u, 3409u};
    std::memcpy(lowMemory.data() + kMachMessageAddress,
                bootstrapHeader,
                sizeof(bootstrapHeader));
    std::memcpy(lowMemory.data() + kMachMessageAddress + 24u,
                bootstrapRequestBody,
                sizeof(bootstrapRequestBody));
    state = {};
    state.r[12] = static_cast<uint32_t>(-31);
    state.r[0] = kMachMessageAddress;
    state.r[1] = kMachSendMsg;
    state.r[2] = bootstrapRequestSize;
    const auto bootstrapSend = syscalls.dispatch(state, 0, false);
    assert(bootstrapSend.handled && state.r[0] == 0u);

    std::memset(lowMemory.data() + kMachMessageAddress, 0, 64u);
    state = {};
    state.r[12] = static_cast<uint32_t>(-31);
    state.r[0] = kMachMessageAddress;
    state.r[1] = kMachReceiveMsg;
    state.r[3] = 64u;
    state.r[4] = replyName;
    const auto bootstrapReceive = syscalls.dispatch(state, 0, false);
    assert(bootstrapReceive.handled && state.r[0] == 0u);
    uint32_t bootstrapBits = 0;
    uint32_t bootstrapReplySize = 0;
    uint32_t bootstrapReplyId = 0;
    uint32_t bootstrapDescriptorCount = 0;
    uint32_t bootstrapPortName = 0;
    uint32_t bootstrapDescriptorWord = 0;
    uint32_t bootstrapReturn = 1;
    std::memcpy(&bootstrapBits, lowMemory.data() + kMachMessageAddress, 4u);
    std::memcpy(&bootstrapReplySize, lowMemory.data() + kMachMessageAddress + 4u, 4u);
    std::memcpy(&bootstrapReplyId, lowMemory.data() + kMachMessageAddress + 20u, 4u);
    std::memcpy(&bootstrapDescriptorCount, lowMemory.data() + kMachMessageAddress + 24u, 4u);
    std::memcpy(&bootstrapPortName, lowMemory.data() + kMachMessageAddress + 28u, 4u);
    std::memcpy(&bootstrapDescriptorWord, lowMemory.data() + kMachMessageAddress + 36u, 4u);
    std::memcpy(&bootstrapReturn, lowMemory.data() + kMachMessageAddress + 48u, 4u);
    assert((bootstrapBits & 0x80000000u) != 0u);
    assert(bootstrapReplySize == 52u && bootstrapReplyId == 3509u);
    assert(bootstrapDescriptorCount == 1u && bootstrapPortName == 0x104u);
    assert(((bootstrapDescriptorWord >> 16u) & 0xffu) == 19u);
    assert((bootstrapDescriptorWord >> 24u) == 0u);
    assert(bootstrapReturn == 0u);

'''
tests = tests.replace(insert_before, bootstrap_tests + insert_before, 1)

source_path.write_text(source)
test_path.write_text(tests)
