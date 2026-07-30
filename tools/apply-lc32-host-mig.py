#!/usr/bin/env python3
from pathlib import Path

source_path = Path('runtime/LC32DarwinSyscalls.cpp')
test_path = Path('runtime/tests/LC32DarwinSyscallsTests.cpp')
source = source_path.read_text()
tests = test_path.read_text()

anchor = '''    switch (number) {'''
if anchor not in source:
    raise SystemExit('Mach switch anchor missing')

mig_helper = '''    const auto queueHostMigReply = [&](const std::vector<uint8_t>& request,
                                       uint32_t replyName) -> bool {
        if (replyName == 0) return false;
        auto replyPort = machPorts_.find(replyName);
        if (replyPort == machPorts_.end() || replyPort->second.receiveRefs == 0 ||
            request.size() < kMachHeaderSize) {
            return false;
        }

        uint32_t requestId = 0;
        std::memcpy(&requestId, request.data() + 20u, sizeof(requestId));
        if (requestId != 200u && requestId != 202u) return false;

        constexpr uint8_t kNdr[8] = {0u, 0u, 0u, 0u, 1u, 0u, 0u, 0u};
        std::vector<uint8_t> reply;
        const auto appendWord = [&](uint32_t value) {
            const size_t base = reply.size();
            reply.resize(base + sizeof(value));
            std::memcpy(reply.data() + base, &value, sizeof(value));
        };
        const auto appendBytes = [&](const void* bytes, size_t size) {
            const size_t base = reply.size();
            reply.resize(base + size);
            std::memcpy(reply.data() + base, bytes, size);
        };

        reply.resize(kMachHeaderSize, 0u);
        appendBytes(kNdr, sizeof(kNdr));
        appendWord(kKernSuccess);

        if (requestId == 202u) {
            appendWord(4096u);
        } else {
            if (request.size() < 40u) return false;
            uint32_t flavor = 0;
            uint32_t requestedCount = 0;
            std::memcpy(&flavor, request.data() + 32u, sizeof(flavor));
            std::memcpy(&requestedCount, request.data() + 36u, sizeof(requestedCount));
            if (flavor != 1u || requestedCount < 12u) return false;

            appendWord(12u);
            const uint32_t hostBasicInfo[12] = {
                2u, 2u, 1024u * 1024u * 1024u,
                12u, 9u, 0u,
                2u, 2u, 2u, 2u,
                1024u * 1024u * 1024u, 0u,
            };
            appendBytes(hostBasicInfo, sizeof(hostBasicInfo));
        }

        const uint32_t bits = 0u;
        const uint32_t size = static_cast<uint32_t>(reply.size());
        const uint32_t remote = 0u;
        const uint32_t local = replyName;
        const uint32_t reserved = 0u;
        const uint32_t replyId = requestId + 100u;
        std::memcpy(reply.data(), &bits, 4u);
        std::memcpy(reply.data() + 4u, &size, 4u);
        std::memcpy(reply.data() + 8u, &remote, 4u);
        std::memcpy(reply.data() + 12u, &local, 4u);
        std::memcpy(reply.data() + 16u, &reserved, 4u);
        std::memcpy(reply.data() + 20u, &replyId, 4u);
        replyPort->second.messages.push_back(std::move(reply));
        return true;
    };

'''
# Insert into dispatchMach, using the last switch(number) in the file.
position = source.rfind(anchor)
if position < 0:
    raise SystemExit('Mach switch anchor missing')
source = source[:position] + mig_helper + source[position:]

old_send = '''                message.resize(headerSize);
                port->second.messages.push_back(std::move(message));
                if (consumeSend) {'''
new_send = '''                message.resize(headerSize);
                uint32_t replyName = 0;
                std::memcpy(&replyName, message.data() + 12u, sizeof(replyName));
                const bool handledHostMig =
                    destination == kHostPort && queueHostMigReply(message, replyName);
                if (!handledHostMig) {
                    port->second.messages.push_back(std::move(message));
                }
                if (consumeSend) {'''
if old_send not in source:
    raise SystemExit('send queue anchor missing')
source = source.replace(old_send, new_send, 1)

insert_before = '''    char rootTemplate[] = "/tmp/lc32-syscalls-XXXXXX";'''
if insert_before not in tests:
    raise SystemExit('Mach test insertion anchor missing')

mig_tests = r'''
    state = {};
    state.r[12] = static_cast<uint32_t>(-29);
    const auto hostSelf = syscalls.dispatch(state, 0, false);
    assert(hostSelf.handled && state.r[0] == 0x103u);
    const uint32_t hostName = state.r[0];

    const auto sendHostRequest = [&](uint32_t requestId,
                                     const std::vector<uint32_t>& body) {
        const uint32_t requestSize =
            static_cast<uint32_t>(24u + body.size() * sizeof(uint32_t));
        uint32_t header[6] = {19u, requestSize, hostName, replyName, 0u, requestId};
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
    const auto receiveHostReply = [&](uint32_t capacity) {
        std::memset(lowMemory.data() + kMachMessageAddress, 0, capacity);
        state = {};
        state.r[12] = static_cast<uint32_t>(-31);
        state.r[0] = kMachMessageAddress;
        state.r[1] = kMachReceiveMsg;
        state.r[3] = capacity;
        state.r[4] = replyName;
        return syscalls.dispatch(state, 0, false);
    };

    sendHostRequest(202u, {});
    const auto pageReply = receiveHostReply(64u);
    assert(pageReply.handled && state.r[0] == 0u);
    uint32_t migReplySize = 0;
    uint32_t migReplyId = 0;
    uint32_t migReturn = 1;
    uint32_t migPageSize = 0;
    std::memcpy(&migReplySize, lowMemory.data() + kMachMessageAddress + 4u, 4u);
    std::memcpy(&migReplyId, lowMemory.data() + kMachMessageAddress + 20u, 4u);
    std::memcpy(&migReturn, lowMemory.data() + kMachMessageAddress + 32u, 4u);
    std::memcpy(&migPageSize, lowMemory.data() + kMachMessageAddress + 36u, 4u);
    assert(migReplySize == 40u && migReplyId == 302u);
    assert(migReturn == 0u && migPageSize == 4096u);

    sendHostRequest(200u, {0u, 1u, 1u, 12u});
    const auto infoReply = receiveHostReply(128u);
    assert(infoReply.handled && state.r[0] == 0u);
    uint32_t hostInfoCount = 0;
    uint32_t maxCpus = 0;
    uint32_t availableCpus = 0;
    uint32_t memorySize = 0;
    uint32_t cpuType = 0;
    uint32_t cpuSubtype = 0;
    std::memcpy(&migReplyId, lowMemory.data() + kMachMessageAddress + 20u, 4u);
    std::memcpy(&migReturn, lowMemory.data() + kMachMessageAddress + 32u, 4u);
    std::memcpy(&hostInfoCount, lowMemory.data() + kMachMessageAddress + 36u, 4u);
    std::memcpy(&maxCpus, lowMemory.data() + kMachMessageAddress + 40u, 4u);
    std::memcpy(&availableCpus, lowMemory.data() + kMachMessageAddress + 44u, 4u);
    std::memcpy(&memorySize, lowMemory.data() + kMachMessageAddress + 48u, 4u);
    std::memcpy(&cpuType, lowMemory.data() + kMachMessageAddress + 52u, 4u);
    std::memcpy(&cpuSubtype, lowMemory.data() + kMachMessageAddress + 56u, 4u);
    assert(migReplyId == 300u && migReturn == 0u && hostInfoCount == 12u);
    assert(maxCpus == 2u && availableCpus == 2u);
    assert(memorySize == 1024u * 1024u * 1024u);
    assert(cpuType == 12u && cpuSubtype == 9u);

'''
tests = tests.replace(insert_before, mig_tests + insert_before, 1)

source_path.write_text(source)
test_path.write_text(tests)
