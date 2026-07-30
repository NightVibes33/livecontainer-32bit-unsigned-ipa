#include "../LC32DarwinSyscalls.hpp"
#include "../LC32RegionOperations.hpp"

#include <cassert>
#include <cerrno>
#include <cstdint>
#include <cstring>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <set>
#include <string>
#include <unistd.h>
#include <vector>

using namespace lc32;

namespace {
struct Region {
    uint32_t base = 0;
    uint32_t size = 0;
    uint32_t protection = 0;
    std::vector<uint8_t> bytes;
};

bool contains(const Region& region, uint32_t address, size_t size) {
    const uint64_t end = static_cast<uint64_t>(address) + size;
    const uint64_t regionEnd = static_cast<uint64_t>(region.base) + region.size;
    return address >= region.base && end <= regionEnd;
}
} // namespace

int main() {
    constexpr uint32_t kGuestOpenCloseExec = 0x01000000u;
    constexpr uint32_t kFcntlGetFd = 1u;
    constexpr uint32_t kFcntlSetFd = 2u;
    constexpr uint32_t kFcntlGetFl = 3u;
    constexpr uint32_t kGuestStat64Size = 108u;
    constexpr uint32_t kGuestStat64ModeOffset = 4u;
    constexpr uint32_t kGuestStat64SizeOffset = 60u;
    constexpr uint32_t kPathAddress = 0x0200u;
    constexpr uint32_t kReadAddress = 0x0800u;
    constexpr uint32_t kStatAddress = 0x1000u;
    constexpr uint32_t kFstatAddress = 0x1200u;
    constexpr uint32_t kMincoreAddress = 0x1400u;
    constexpr uint32_t kLinkReadAddress = 0x1800u;
    constexpr uint32_t kLinkStatAddress = 0x1c00u;
    constexpr uint32_t kSysctlNameAddress = 0x1600u;
    constexpr uint32_t kSysctlLengthAddress = 0x1640u;
    constexpr uint32_t kSysctlOutputAddress = 0x1680u;
    constexpr uint32_t kRlimitAddress = 0x1700u;
    constexpr uint32_t kDirectoryBufferAddress = 0x2000u;
    constexpr uint32_t kDirectoryPositionAddress = 0x2f00u;
    constexpr uint32_t kStackAddress = 0x3000u;

    constexpr uint32_t kProtRead = 0x01u;
    constexpr uint32_t kProtWrite = 0x02u;
    constexpr uint32_t kProtExec = 0x04u;
    constexpr uint32_t kMapPrivate = 0x0002u;
    constexpr uint32_t kMapFixed = 0x0010u;
    constexpr uint32_t kMapJit = 0x0800u;
    constexpr uint32_t kMapAnonymous = 0x1000u;
    constexpr uint32_t kMsAsync = 0x0001u;
    constexpr uint32_t kMsSync = 0x0010u;

    std::vector<uint8_t> lowMemory(0x4000u);
    std::vector<Region> regions;

    SyscallMemory syscallMemory;
    syscallMemory.read = [&](uint32_t address, void* output, size_t size) {
        const uint64_t end = static_cast<uint64_t>(address) + size;
        if (end <= lowMemory.size()) {
            std::memcpy(output, lowMemory.data() + address, size);
            return true;
        }
        for (const Region& region : regions) {
            if (contains(region, address, size)) {
                std::memcpy(output,
                            region.bytes.data() + (address - region.base),
                            size);
                return true;
            }
        }
        return false;
    };
    syscallMemory.write = [&](uint32_t address, const void* input, size_t size) {
        const uint64_t end = static_cast<uint64_t>(address) + size;
        if (end <= lowMemory.size()) {
            std::memcpy(lowMemory.data() + address, input, size);
            return true;
        }
        for (Region& region : regions) {
            if (contains(region, address, size)) {
                std::memcpy(region.bytes.data() + (address - region.base),
                            input,
                            size);
                return true;
            }
        }
        return false;
    };
    syscallMemory.map = [&](uint32_t address,
                            uint32_t size,
                            uint32_t protection) {
        if (size == 0 || (address & 0xfffu) != 0 || (size & 0xfffu) != 0) {
            return false;
        }
        const uint64_t end = static_cast<uint64_t>(address) + size;
        if (end > 0x100000000ull) return false;
        for (const Region& region : regions) {
            const uint64_t regionEnd =
                static_cast<uint64_t>(region.base) + region.size;
            if (!(end <= region.base || address >= regionEnd)) return false;
        }
        regions.push_back(
            {address, size, protection, std::vector<uint8_t>(size)});
        return true;
    };
    syscallMemory.unmap = [&](uint32_t address, uint32_t size) {
        return unmapRegionRange(regions, address, size);
    };
    syscallMemory.protect = [&](uint32_t address,
                                    uint32_t size,
                                    uint32_t protection) {
        return protectRegionRange(regions, address, size, protection);
    };

    DarwinSyscalls syscalls(syscallMemory);
    CPUState state{};

    state.r[12] = 0x80000000u | 20u;
    const auto getpid = syscalls.dispatch(state, 0, false);
    assert(getpid.handled && getpid.trapClass == TrapClass::Unix);
    assert(state.r[0] != 0);

    state = {};
    state.r[12] = 116;
    state.r[0] = 0x80u;
    const auto gettimeofday = syscalls.dispatch(state, 0x80u, false);
    assert(gettimeofday.handled && gettimeofday.errorNumber == 0);

    state = {};
    state.r[12] = static_cast<uint32_t>(-28);
    const auto taskSelf = syscalls.dispatch(state, 0, false);
    assert(taskSelf.handled && taskSelf.trapClass == TrapClass::Mach);
    assert(state.r[0] == 0x102u);


    constexpr uint32_t kMachNameAddress = 0x0080u;
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
    uint32_t hostMemorySize = 0;
    uint32_t cpuType = 0;
    uint32_t cpuSubtype = 0;
    std::memcpy(&migReplyId, lowMemory.data() + kMachMessageAddress + 20u, 4u);
    std::memcpy(&migReturn, lowMemory.data() + kMachMessageAddress + 32u, 4u);
    std::memcpy(&hostInfoCount, lowMemory.data() + kMachMessageAddress + 36u, 4u);
    std::memcpy(&maxCpus, lowMemory.data() + kMachMessageAddress + 40u, 4u);
    std::memcpy(&availableCpus, lowMemory.data() + kMachMessageAddress + 44u, 4u);
    std::memcpy(&hostMemorySize, lowMemory.data() + kMachMessageAddress + 48u, 4u);
    std::memcpy(&cpuType, lowMemory.data() + kMachMessageAddress + 52u, 4u);
    std::memcpy(&cpuSubtype, lowMemory.data() + kMachMessageAddress + 56u, 4u);
    assert(migReplyId == 300u && migReturn == 0u && hostInfoCount == 12u);
    assert(maxCpus == 2u && availableCpus == 2u);
    assert(hostMemorySize == 1024u * 1024u * 1024u);
    assert(cpuType == 12u && cpuSubtype == 9u);

    char rootTemplate[] = "/tmp/lc32-syscalls-XXXXXX";
    char* rootDirectory = ::mkdtemp(rootTemplate);
    assert(rootDirectory != nullptr);
    const std::filesystem::path root(rootDirectory);
    std::filesystem::create_directories(root / "usr/lib/Frameworks");

    const std::string payload = "legacy-dylib-bytes";
    {
        std::ofstream file(root / "usr/lib/libA.dylib", std::ios::binary);
        file.write(payload.data(), static_cast<std::streamsize>(payload.size()));
    }
    assert(::symlink("/etc/passwd", (root / "usr/lib/escape").c_str()) == 0);
    assert(::symlink("libA.dylib", (root / "usr/lib/libAlias.dylib").c_str()) == 0);
    assert(::symlink("/etc", (root / "usr/outside").c_str()) == 0);

    DarwinSyscalls rooted(syscallMemory, root.string());

    const auto putCString = [&](uint32_t address, const std::string& text) {
        assert(static_cast<uint64_t>(address) + text.size() + 1u <=
               lowMemory.size());
        std::memcpy(lowMemory.data() + address, text.c_str(), text.size() + 1u);
    };
    const auto putWord = [&](uint32_t address, uint32_t word) {
        assert(static_cast<uint64_t>(address) + sizeof(word) <= lowMemory.size());
        std::memcpy(lowMemory.data() + address, &word, sizeof(word));
    };
    const auto readMapped = [&](uint32_t address, void* output, size_t size) {
        assert(syscallMemory.read(address, output, size));
    };

    putCString(kPathAddress, "/usr/lib");
    state = {};
    state.r[12] = 5;
    state.r[0] = kPathAddress;
    state.r[1] = 0u;
    const auto directoryOpened = rooted.dispatch(state, 0x80u, false);
    assert(directoryOpened.handled && directoryOpened.errorNumber == 0);
    const int directoryFd = static_cast<int>(state.r[0]);

    state = {};
    state.r[12] = 344;
    state.r[0] = static_cast<uint32_t>(directoryFd);
    state.r[1] = kDirectoryBufferAddress;
    state.r[2] = 8u;
    state.r[3] = kDirectoryPositionAddress;
    const auto tinyDirectoryRead = rooted.dispatch(state, 0x80u, false);
    assert(tinyDirectoryRead.handled && tinyDirectoryRead.errorNumber == EINVAL);

    std::memset(lowMemory.data() + kDirectoryBufferAddress, 0, 1024u);
    uint64_t directoryPosition = 0;
    std::memcpy(lowMemory.data() + kDirectoryPositionAddress,
                &directoryPosition,
                sizeof(directoryPosition));
    state = {};
    state.r[12] = 344;
    state.r[0] = static_cast<uint32_t>(directoryFd);
    state.r[1] = kDirectoryBufferAddress;
    state.r[2] = 1024u;
    state.r[3] = kDirectoryPositionAddress;
    const auto directoryRead = rooted.dispatch(state, 0x80u, false);
    assert(directoryRead.handled && directoryRead.errorNumber == 0);
    assert(directoryRead.returnValue > 0);

    std::set<std::string> directoryNames;
    size_t directoryOffset = 0;
    while (directoryOffset < static_cast<size_t>(directoryRead.returnValue)) {
        uint16_t recordLength = 0;
        uint16_t nameLength = 0;
        std::memcpy(&recordLength,
                    lowMemory.data() + kDirectoryBufferAddress + directoryOffset + 16u,
                    sizeof(recordLength));
        std::memcpy(&nameLength,
                    lowMemory.data() + kDirectoryBufferAddress + directoryOffset + 18u,
                    sizeof(nameLength));
        assert(recordLength >= 24u && (recordLength & 3u) == 0u);
        assert(directoryOffset + recordLength <=
               static_cast<size_t>(directoryRead.returnValue));
        directoryNames.emplace(reinterpret_cast<char*>(
                                   lowMemory.data() + kDirectoryBufferAddress +
                                   directoryOffset + 21u),
                               nameLength);
        directoryOffset += recordLength;
    }
    assert(directoryNames.count(".") == 1u);
    assert(directoryNames.count("..") == 1u);
    assert(directoryNames.count("libA.dylib") == 1u);
    assert(directoryNames.count("libAlias.dylib") == 1u);
    assert(directoryNames.count("Frameworks") == 1u);

    state = {};
    state.r[12] = 344;
    state.r[0] = static_cast<uint32_t>(directoryFd);
    state.r[1] = kDirectoryBufferAddress;
    state.r[2] = 1024u;
    state.r[3] = kDirectoryPositionAddress;
    const auto directoryEnd = rooted.dispatch(state, 0x80u, false);
    assert(directoryEnd.handled && directoryEnd.errorNumber == 0);
    assert(directoryEnd.returnValue == 0);

    state = {};
    state.r[12] = 6;
    state.r[0] = static_cast<uint32_t>(directoryFd);
    const auto directoryClosed = rooted.dispatch(state, 0x80u, false);
    assert(directoryClosed.handled && directoryClosed.errorNumber == 0);

    putCString(kPathAddress, "/usr/lib/libA.dylib");

    state = {};
    state.r[12] = 33;
    state.r[0] = kPathAddress;
    state.r[1] = R_OK;
    const auto access = rooted.dispatch(state, 0x80u, false);
    assert(access.handled && access.errorNumber == 0);

    state = {};
    state.r[12] = 338;
    state.r[0] = kPathAddress;
    state.r[1] = kStatAddress;
    const auto stat64 = rooted.dispatch(state, 0x80u, false);
    assert(stat64.handled && stat64.errorNumber == 0);
    uint16_t mode = 0;
    int64_t size = -1;
    std::memcpy(&mode,
                lowMemory.data() + kStatAddress + kGuestStat64ModeOffset,
                sizeof(mode));
    std::memcpy(&size,
                lowMemory.data() + kStatAddress + kGuestStat64SizeOffset,
                sizeof(size));
    assert((mode & 0170000u) == 0100000u);
    assert(size == static_cast<int64_t>(payload.size()));

    const std::string aliasTarget = "libA.dylib";
    putCString(kPathAddress, "/usr/lib/libAlias.dylib");
    std::memset(lowMemory.data() + kLinkReadAddress, 0x5a, 32u);
    state = {};
    state.r[12] = 58;
    state.r[0] = kPathAddress;
    state.r[1] = kLinkReadAddress;
    state.r[2] = 32u;
    const auto aliasReadlink = rooted.dispatch(state, 0x80u, false);
    assert(aliasReadlink.handled && aliasReadlink.errorNumber == 0);
    assert(aliasReadlink.returnValue == static_cast<int32_t>(aliasTarget.size()));
    assert(std::memcmp(lowMemory.data() + kLinkReadAddress,
                       aliasTarget.data(),
                       aliasTarget.size()) == 0);
    assert(lowMemory[kLinkReadAddress + aliasTarget.size()] == 0x5au);

    std::memset(lowMemory.data() + kLinkReadAddress, 0x5a, 8u);
    state = {};
    state.r[12] = 58;
    state.r[0] = kPathAddress;
    state.r[1] = kLinkReadAddress;
    state.r[2] = 4u;
    const auto shortReadlink = rooted.dispatch(state, 0x80u, false);
    assert(shortReadlink.handled && shortReadlink.errorNumber == 0);
    assert(shortReadlink.returnValue == 4);
    assert(std::memcmp(lowMemory.data() + kLinkReadAddress, "libA", 4u) == 0);
    assert(lowMemory[kLinkReadAddress + 4u] == 0x5au);

    std::memset(lowMemory.data() + kLinkStatAddress,
                0x5a,
                kGuestStat64Size + 1u);
    state = {};
    state.r[12] = 340;
    state.r[0] = kPathAddress;
    state.r[1] = kLinkStatAddress;
    const auto aliasLstat = rooted.dispatch(state, 0x80u, false);
    assert(aliasLstat.handled && aliasLstat.errorNumber == 0);
    std::memcpy(&mode,
                lowMemory.data() + kLinkStatAddress + kGuestStat64ModeOffset,
                sizeof(mode));
    std::memcpy(&size,
                lowMemory.data() + kLinkStatAddress + kGuestStat64SizeOffset,
                sizeof(size));
    assert((mode & 0170000u) == 0120000u);
    assert(size == static_cast<int64_t>(aliasTarget.size()));
    assert(lowMemory[kLinkStatAddress + kGuestStat64Size] == 0x5au);

    putCString(kPathAddress, "/usr/lib/libA.dylib");
    state = {};
    state.r[12] = 58;
    state.r[0] = kPathAddress;
    state.r[1] = kLinkReadAddress;
    state.r[2] = 32u;
    const auto regularReadlink = rooted.dispatch(state, 0x80u, false);
    assert(regularReadlink.handled && regularReadlink.errorNumber == EINVAL);

    putCString(kPathAddress, "/usr/lib/escape");
    std::memset(lowMemory.data() + kLinkReadAddress, 0x5a, 32u);
    state = {};
    state.r[12] = 58;
    state.r[0] = kPathAddress;
    state.r[1] = kLinkReadAddress;
    state.r[2] = 32u;
    const auto finalEscapeReadlink = rooted.dispatch(state, 0x80u, false);
    assert(finalEscapeReadlink.handled && finalEscapeReadlink.errorNumber == 0);
    assert(std::string(reinterpret_cast<char*>(lowMemory.data() + kLinkReadAddress),
                       static_cast<size_t>(finalEscapeReadlink.returnValue)) ==
           "/etc/passwd");

    state = {};
    state.r[12] = 340;
    state.r[0] = kPathAddress;
    state.r[1] = kLinkStatAddress;
    const auto finalEscapeLstat = rooted.dispatch(state, 0x80u, false);
    assert(finalEscapeLstat.handled && finalEscapeLstat.errorNumber == 0);

    putCString(kPathAddress, "/usr/outside/passwd");
    state = {};
    state.r[12] = 58;
    state.r[0] = kPathAddress;
    state.r[1] = kLinkReadAddress;
    state.r[2] = 32u;
    const auto parentEscapeReadlink = rooted.dispatch(state, 0x80u, false);
    assert(parentEscapeReadlink.handled && parentEscapeReadlink.errorNumber == EACCES);

    putCString(kPathAddress, "/usr/lib/libAlias.dylib");
    state = {};
    state.r[12] = 58;
    state.r[0] = kPathAddress;
    state.r[1] = kLinkReadAddress;
    state.r[2] = 0u;
    const auto zeroReadlink = rooted.dispatch(state, 0x80u, false);
    assert(zeroReadlink.handled && zeroReadlink.errorNumber == EINVAL);

    putCString(kPathAddress, "/usr/lib/libA.dylib");
    state = {};
    state.r[12] = 5;
    state.r[0] = kPathAddress;
    state.r[1] = kGuestOpenCloseExec;
    const auto opened = rooted.dispatch(state, 0x80u, false);
    assert(opened.handled && opened.errorNumber == 0);
    const int guestFd = static_cast<int>(state.r[0]);
    assert(guestFd >= 3);

    state = {};
    state.r[12] = 92;
    state.r[0] = static_cast<uint32_t>(guestFd);
    state.r[1] = kFcntlGetFd;
    const auto getFd = rooted.dispatch(state, 0x80u, false);
    assert(getFd.handled && getFd.errorNumber == 0 && state.r[0] == 1u);

    state = {};
    state.r[12] = 92;
    state.r[0] = static_cast<uint32_t>(guestFd);
    state.r[1] = kFcntlGetFl;
    const auto getFl = rooted.dispatch(state, 0x80u, false);
    assert(getFl.handled && getFl.errorNumber == 0);
    assert(state.r[0] == kGuestOpenCloseExec);

    std::memset(lowMemory.data() + kFstatAddress,
                0x5a,
                kGuestStat64Size + 1u);
    state = {};
    state.r[12] = 339;
    state.r[0] = static_cast<uint32_t>(guestFd);
    state.r[1] = kFstatAddress;
    const auto fstat64 = rooted.dispatch(state, 0x80u, false);
    assert(fstat64.handled && fstat64.errorNumber == 0);
    assert(lowMemory[kFstatAddress + kGuestStat64Size] == 0x5au);

    const auto seekGuest = [&](int64_t offset, int whence) {
        putWord(kStackAddress, static_cast<uint32_t>(whence));
        const uint64_t bits = static_cast<uint64_t>(offset);
        state = {};
        state.r[12] = 199;
        state.r[0] = static_cast<uint32_t>(guestFd);
        state.r[1] = 0xccccccccu;
        state.r[2] = static_cast<uint32_t>(bits);
        state.r[3] = static_cast<uint32_t>(bits >> 32u);
        state.r[13] = kStackAddress;
        return rooted.dispatch(state, 0x80u, false);
    };

    const auto seekSeven = seekGuest(7, SEEK_SET);
    assert(seekSeven.handled && seekSeven.errorNumber == 0);
    assert(state.r[0] == 7u && state.r[1] == 0u);

    state = {};
    state.r[12] = 3;
    state.r[0] = static_cast<uint32_t>(guestFd);
    state.r[1] = kReadAddress;
    state.r[2] = 5;
    const auto readMiddle = rooted.dispatch(state, 0x80u, false);
    assert(readMiddle.handled && readMiddle.errorNumber == 0);
    assert(std::memcmp(lowMemory.data() + kReadAddress, "dylib", 5) == 0);

    const auto mmapGuest = [&](uint32_t hint,
                               uint32_t length,
                               uint32_t protection,
                               uint32_t flags,
                               int fd,
                               int64_t offset) {
        putWord(kStackAddress, static_cast<uint32_t>(fd));
        putWord(kStackAddress + 4u, 0xddddddddu);
        const uint64_t bits = static_cast<uint64_t>(offset);
        putWord(kStackAddress + 8u, static_cast<uint32_t>(bits));
        putWord(kStackAddress + 12u, static_cast<uint32_t>(bits >> 32u));
        state = {};
        state.r[12] = 197;
        state.r[0] = hint;
        state.r[1] = length;
        state.r[2] = protection;
        state.r[3] = flags;
        state.r[13] = kStackAddress;
        return rooted.dispatch(state, 0x80u, false);
    };

    const auto anonymous = mmapGuest(0,
                                     5000u,
                                     kProtRead | kProtWrite,
                                     kMapPrivate | kMapAnonymous,
                                     -1,
                                     0);
    assert(anonymous.handled && anonymous.errorNumber == 0);
    const uint32_t anonymousAddress = state.r[0];
    assert(anonymousAddress == 0x50000000u);
    assert(regions.back().base == anonymousAddress);
    assert(regions.back().size == 0x2000u);
    for (uint8_t byte : regions.back().bytes) assert(byte == 0);

    const auto secondAnonymous = mmapGuest(0,
                                           4096u,
                                           kProtRead | kProtWrite,
                                           kMapPrivate | kMapAnonymous,
                                           -1,
                                           0);
    assert(secondAnonymous.handled && secondAnonymous.errorNumber == 0);
    assert(state.r[0] == 0x50003000u);

    const auto hinted = mmapGuest(0x60000000u,
                                  4096u,
                                  kProtRead | kProtWrite,
                                  kMapPrivate | kMapAnonymous,
                                  -1,
                                  0);
    assert(hinted.handled && hinted.errorNumber == 0);
    assert(state.r[0] == 0x60000000u);

    const auto overlappingHint = mmapGuest(anonymousAddress,
                                           4096u,
                                           kProtRead | kProtWrite,
                                           kMapPrivate | kMapAnonymous,
                                           -1,
                                           0);
    assert(overlappingHint.handled && overlappingHint.errorNumber == 0);
    assert(state.r[0] != anonymousAddress);

    const auto fileMapping = mmapGuest(
        0,
        static_cast<uint32_t>(payload.size() + 8u),
        kProtRead | kProtExec,
        kMapPrivate,
        guestFd,
        0);
    assert(fileMapping.handled && fileMapping.errorNumber == 0);
    const uint32_t fileAddress = state.r[0];
    std::vector<uint8_t> fileBytes(payload.size() + 8u, 0xff);
    readMapped(fileAddress, fileBytes.data(), fileBytes.size());
    assert(std::memcmp(fileBytes.data(), payload.data(), payload.size()) == 0);
    for (size_t i = payload.size(); i < fileBytes.size(); ++i) {
        assert(fileBytes[i] == 0);
    }

    const auto writableFile = mmapGuest(
        0, 4096u, kProtRead | kProtWrite, kMapPrivate, guestFd, 0);
    assert(writableFile.handled && writableFile.errorNumber == EROFS);

    const auto fixed = mmapGuest(0x61000000u,
                                 4096u,
                                 kProtRead,
                                 kMapPrivate | kMapAnonymous | kMapFixed,
                                 -1,
                                 0);
    assert(fixed.handled && fixed.errorNumber == EINVAL);

    const auto jit = mmapGuest(0,
                               4096u,
                               kProtRead | kProtExec,
                               kMapPrivate | kMapAnonymous | kMapJit,
                               -1,
                               0);
    assert(jit.handled && jit.errorNumber == EPERM);

    const auto unalignedOffset =
        mmapGuest(0, 4096u, kProtRead, kMapPrivate, guestFd, 1);
    assert(unalignedOffset.handled && unalignedOffset.errorNumber == EINVAL);

    const auto badFd =
        mmapGuest(0, 4096u, kProtRead, kMapPrivate, 9999, 0);
    assert(badFd.handled && badFd.errorNumber == EBADF);

    state = {};
    state.r[12] = 197;
    state.r[1] = 4096u;
    state.r[2] = kProtRead;
    state.r[3] = kMapPrivate | kMapAnonymous;
    state.r[13] = static_cast<uint32_t>(lowMemory.size() - 4u);
    const auto badStack = rooted.dispatch(state, 0x80u, false);
    assert(badStack.handled && badStack.errorNumber == EFAULT);

    state = {};
    state.r[12] = 74;
    state.r[0] = anonymousAddress + 0x1000u;
    state.r[1] = 1u;
    state.r[2] = kProtRead | kProtExec;
    const auto protectedPage = rooted.dispatch(state, 0x80u, false);
    assert(protectedPage.handled && protectedPage.errorNumber == 0);
    bool sawWritableFirstPage = false;
    bool sawExecutableSecondPage = false;
    for (const Region& region : regions) {
        if (region.base == anonymousAddress && region.size == 0x1000u) {
            sawWritableFirstPage = region.protection == (kProtRead | kProtWrite);
        }
        if (region.base == anonymousAddress + 0x1000u && region.size == 0x1000u) {
            sawExecutableSecondPage = region.protection == (kProtRead | kProtExec);
        }
    }
    assert(sawWritableFirstPage && sawExecutableSecondPage);

    state = {};
    state.r[12] = 74;
    state.r[0] = anonymousAddress;
    state.r[1] = 0x1000u;
    state.r[2] = kProtRead | kProtWrite | kProtExec;
    const auto writableExecutable = rooted.dispatch(state, 0x80u, false);
    assert(writableExecutable.handled && writableExecutable.errorNumber == EPERM);

    state = {};
    state.r[12] = 74;
    state.r[0] = anonymousAddress + 1u;
    state.r[1] = 0x1000u;
    state.r[2] = kProtRead;
    const auto unalignedProtect = rooted.dispatch(state, 0x80u, false);
    assert(unalignedProtect.handled && unalignedProtect.errorNumber == EINVAL);

    state = {};
    state.r[12] = 74;
    state.r[0] = 0x68000000u;
    state.r[1] = 0x1000u;
    state.r[2] = kProtRead;
    const auto missingProtect = rooted.dispatch(state, 0x80u, false);
    assert(missingProtect.handled && missingProtect.errorNumber == ENOMEM);

    state = {};
    state.r[12] = 73;
    state.r[0] = anonymousAddress + 0x1000u;
    state.r[1] = 1u;
    const auto unmappedPage = rooted.dispatch(state, 0x80u, false);
    assert(unmappedPage.handled && unmappedPage.errorNumber == 0);
    uint8_t removedByte = 0;
    assert(!syscallMemory.read(anonymousAddress + 0x1000u, &removedByte, 1));
    assert(syscallMemory.read(anonymousAddress, &removedByte, 1));

    const auto remappedPage = mmapGuest(anonymousAddress + 0x1000u,
                                        4096u,
                                        kProtRead | kProtWrite,
                                        kMapPrivate | kMapAnonymous,
                                        -1,
                                        0);
    assert(remappedPage.handled && remappedPage.errorNumber == 0);
    assert(state.r[0] == anonymousAddress + 0x1000u);

    state = {};
    state.r[12] = 73;
    state.r[0] = anonymousAddress + 1u;
    state.r[1] = 0x1000u;
    const auto unalignedUnmap = rooted.dispatch(state, 0x80u, false);
    assert(unalignedUnmap.handled && unalignedUnmap.errorNumber == EINVAL);

    state = {};
    state.r[12] = 73;
    state.r[0] = 0x69000000u;
    state.r[1] = 0x1000u;
    const auto emptyUnmap = rooted.dispatch(state, 0x80u, false);
    assert(emptyUnmap.handled && emptyUnmap.errorNumber == 0);

    state = {};
    state.r[12] = 65;
    state.r[0] = anonymousAddress;
    state.r[1] = 0x1000u;
    state.r[2] = kMsSync;
    const auto synchronized = rooted.dispatch(state, 0x80u, false);
    assert(synchronized.handled && synchronized.errorNumber == 0);

    state = {};
    state.r[12] = 65;
    state.r[0] = anonymousAddress;
    state.r[1] = 0x1000u;
    state.r[2] = kMsAsync | kMsSync;
    const auto conflictingSync = rooted.dispatch(state, 0x80u, false);
    assert(conflictingSync.handled && conflictingSync.errorNumber == EINVAL);

    state = {};
    state.r[12] = 65;
    state.r[0] = anonymousAddress + 1u;
    state.r[1] = 0x1000u;
    state.r[2] = kMsSync;
    const auto unalignedSync = rooted.dispatch(state, 0x80u, false);
    assert(unalignedSync.handled && unalignedSync.errorNumber == EINVAL);

    state = {};
    state.r[12] = 65;
    state.r[0] = 0x6a000000u;
    state.r[1] = 0x1000u;
    state.r[2] = kMsSync;
    const auto missingSync = rooted.dispatch(state, 0x80u, false);
    assert(missingSync.handled && missingSync.errorNumber == ENOMEM);

    state = {};
    state.r[12] = 75;
    state.r[0] = anonymousAddress + 0x1000u;
    state.r[1] = 1u;
    state.r[2] = 3u;
    const auto willNeed = rooted.dispatch(state, 0x80u, false);
    assert(willNeed.handled && willNeed.errorNumber == 0);

    state = {};
    state.r[12] = 75;
    state.r[0] = anonymousAddress + 0x1000u;
    state.r[1] = 0x1000u;
    state.r[2] = 99u;
    const auto invalidAdvice = rooted.dispatch(state, 0x80u, false);
    assert(invalidAdvice.handled && invalidAdvice.errorNumber == EINVAL);

    state = {};
    state.r[12] = 75;
    state.r[0] = anonymousAddress + 1u;
    state.r[1] = 0x1000u;
    state.r[2] = 0u;
    const auto unalignedAdvice = rooted.dispatch(state, 0x80u, false);
    assert(unalignedAdvice.handled && unalignedAdvice.errorNumber == EINVAL);

    state = {};
    state.r[12] = 75;
    state.r[0] = 0x6b000000u;
    state.r[1] = 0x1000u;
    state.r[2] = 0u;
    const auto missingAdvice = rooted.dispatch(state, 0x80u, false);
    assert(missingAdvice.handled && missingAdvice.errorNumber == ENOMEM);

    std::memset(lowMemory.data() + kMincoreAddress, 0, 2u);
    state = {};
    state.r[12] = 78;
    state.r[0] = anonymousAddress;
    state.r[1] = 0x2000u;
    state.r[2] = kMincoreAddress;
    const auto resident = rooted.dispatch(state, 0x80u, false);
    assert(resident.handled && resident.errorNumber == 0);
    assert(lowMemory[kMincoreAddress] == 0x01u);
    assert(lowMemory[kMincoreAddress + 1u] == 0x01u);

    state = {};
    state.r[12] = 78;
    state.r[0] = anonymousAddress + 1u;
    state.r[1] = 0x1000u;
    state.r[2] = kMincoreAddress;
    const auto unalignedMincore = rooted.dispatch(state, 0x80u, false);
    assert(unalignedMincore.handled && unalignedMincore.errorNumber == EINVAL);

    state = {};
    state.r[12] = 78;
    state.r[0] = 0x6c000000u;
    state.r[1] = 0x1000u;
    state.r[2] = kMincoreAddress;
    const auto missingMincore = rooted.dispatch(state, 0x80u, false);
    assert(missingMincore.handled && missingMincore.errorNumber == ENOMEM);

    state = {};
    state.r[12] = 78;
    state.r[0] = anonymousAddress;
    state.r[1] = 0x2000u;
    state.r[2] = static_cast<uint32_t>(lowMemory.size() - 1u);
    const auto badMincoreVector = rooted.dispatch(state, 0x80u, false);
    assert(badMincoreVector.handled && badMincoreVector.errorNumber == EFAULT);

    const auto sysctlGuest = [&](int32_t rootMib,
                                 int32_t leafMib,
                                 uint32_t outputAddress,
                                 uint32_t outputLength,
                                 uint32_t newAddress = 0,
                                 uint32_t newLength = 0) {
        const int32_t mib[2] = {rootMib, leafMib};
        std::memcpy(lowMemory.data() + kSysctlNameAddress, mib, sizeof(mib));
        std::memcpy(lowMemory.data() + kSysctlLengthAddress,
                    &outputLength,
                    sizeof(outputLength));
        std::memcpy(lowMemory.data() + kStackAddress,
                    &newAddress,
                    sizeof(newAddress));
        std::memcpy(lowMemory.data() + kStackAddress + sizeof(uint32_t),
                    &newLength,
                    sizeof(newLength));
        state = {};
        state.r[12] = 202;
        state.r[0] = kSysctlNameAddress;
        state.r[1] = 2u;
        state.r[2] = outputAddress;
        state.r[3] = kSysctlLengthAddress;
        state.r[13] = kStackAddress;
        return rooted.dispatch(state, 0x80u, false);
    };

    const auto pageSizeQuery = sysctlGuest(6, 7, 0, 0);
    assert(pageSizeQuery.handled && pageSizeQuery.errorNumber == 0);
    uint32_t sysctlLength = 0;
    std::memcpy(&sysctlLength,
                lowMemory.data() + kSysctlLengthAddress,
                sizeof(sysctlLength));
    assert(sysctlLength == sizeof(int32_t));

    const auto pageSizeRead =
        sysctlGuest(6, 7, kSysctlOutputAddress, sizeof(int32_t));
    assert(pageSizeRead.handled && pageSizeRead.errorNumber == 0);
    int32_t guestPageSize = 0;
    std::memcpy(&guestPageSize,
                lowMemory.data() + kSysctlOutputAddress,
                sizeof(guestPageSize));
    assert(guestPageSize == 4096);

    std::memset(lowMemory.data() + kSysctlOutputAddress, 0, 32u);
    const auto osType = sysctlGuest(1, 1, kSysctlOutputAddress, 32u);
    assert(osType.handled && osType.errorNumber == 0);
    assert(std::string(reinterpret_cast<char*>(
               lowMemory.data() + kSysctlOutputAddress)) == "Darwin");

    const auto memorySize = sysctlGuest(6, 24, kSysctlOutputAddress, 8u);
    assert(memorySize.handled && memorySize.errorNumber == 0);
    uint64_t guestMemorySize = 0;
    std::memcpy(&guestMemorySize,
                lowMemory.data() + kSysctlOutputAddress,
                sizeof(guestMemorySize));
    assert(guestMemorySize == 1024ull * 1024ull * 1024ull);

    lowMemory[kSysctlOutputAddress] = 0x5au;
    const auto shortOutput = sysctlGuest(1, 1, kSysctlOutputAddress, 2u);
    assert(shortOutput.handled && shortOutput.errorNumber == ENOMEM);
    std::memcpy(&sysctlLength,
                lowMemory.data() + kSysctlLengthAddress,
                sizeof(sysctlLength));
    assert(sysctlLength == 7u);
    assert(lowMemory[kSysctlOutputAddress] == 0x5au);

    const auto writeAttempt =
        sysctlGuest(6, 7, kSysctlOutputAddress, 4u, kReadAddress, 4u);
    assert(writeAttempt.handled && writeAttempt.errorNumber == EPERM);

    const auto missingSysctl = sysctlGuest(6, 99, kSysctlOutputAddress, 4u);
    assert(missingSysctl.handled && missingSysctl.errorNumber == ENOENT);

    state = {};
    state.r[12] = 202;
    state.r[0] = static_cast<uint32_t>(lowMemory.size() - 4u);
    state.r[1] = 2u;
    state.r[2] = kSysctlOutputAddress;
    state.r[3] = kSysctlLengthAddress;
    state.r[13] = kStackAddress;
    const auto badSysctlName = rooted.dispatch(state, 0x80u, false);
    assert(badSysctlName.handled && badSysctlName.errorNumber == EFAULT);

    const int32_t validMib[2] = {6, 7};
    std::memcpy(lowMemory.data() + kSysctlNameAddress,
                validMib,
                sizeof(validMib));
    state = {};
    state.r[12] = 202;
    state.r[0] = kSysctlNameAddress;
    state.r[1] = 2u;
    state.r[2] = kSysctlOutputAddress;
    state.r[3] = kSysctlLengthAddress;
    state.r[13] = static_cast<uint32_t>(lowMemory.size() - 4u);
    const auto badSysctlStack = rooted.dispatch(state, 0x80u, false);
    assert(badSysctlStack.handled && badSysctlStack.errorNumber == EFAULT);

    uint32_t seekWhence = SEEK_SET;
    std::memcpy(lowMemory.data() + kStackAddress,
                &seekWhence,
                sizeof(seekWhence));
    state = {};
    state.r[12] = 199;
    state.r[0] = static_cast<uint32_t>(guestFd);
    state.r[2] = 3u;
    state.r[3] = 0u;
    state.r[13] = kStackAddress;
    const auto positioned = rooted.dispatch(state, 0x80u, false);
    assert(positioned.handled && positioned.errorNumber == 0);
    assert(state.r[0] == 3u && state.r[1] == 0u);

    uint32_t preadOffsetLow = 7u;
    uint32_t preadOffsetHigh = 0u;
    std::memcpy(lowMemory.data() + kStackAddress,
                &preadOffsetLow,
                sizeof(preadOffsetLow));
    std::memcpy(lowMemory.data() + kStackAddress + sizeof(uint32_t),
                &preadOffsetHigh,
                sizeof(preadOffsetHigh));
    state = {};
    state.r[12] = 153;
    state.r[0] = static_cast<uint32_t>(guestFd);
    state.r[1] = kReadAddress;
    state.r[2] = 5u;
    state.r[13] = kStackAddress;
    const auto positionedRead = rooted.dispatch(state, 0x80u, false);
    assert(positionedRead.handled && positionedRead.errorNumber == 0);
    assert(state.r[0] == 5u);
    assert(std::string(reinterpret_cast<char*>(lowMemory.data() + kReadAddress),
                       5u) == "dylib");

    seekWhence = SEEK_CUR;
    std::memcpy(lowMemory.data() + kStackAddress,
                &seekWhence,
                sizeof(seekWhence));
    state = {};
    state.r[12] = 199;
    state.r[0] = static_cast<uint32_t>(guestFd);
    state.r[2] = 0u;
    state.r[3] = 0u;
    state.r[13] = kStackAddress;
    const auto unchangedPosition = rooted.dispatch(state, 0x80u, false);
    assert(unchangedPosition.handled && unchangedPosition.errorNumber == 0);
    assert(state.r[0] == 3u && state.r[1] == 0u);

    preadOffsetLow = 0u;
    preadOffsetHigh = 0u;
    std::memcpy(lowMemory.data() + kStackAddress,
                &preadOffsetLow,
                sizeof(preadOffsetLow));
    std::memcpy(lowMemory.data() + kStackAddress + sizeof(uint32_t),
                &preadOffsetHigh,
                sizeof(preadOffsetHigh));
    state = {};
    state.r[12] = 414;
    state.r[0] = static_cast<uint32_t>(guestFd);
    state.r[1] = kReadAddress;
    state.r[2] = 6u;
    state.r[13] = kStackAddress;
    const auto noCancelRead = rooted.dispatch(state, 0x80u, false);
    assert(noCancelRead.handled && noCancelRead.errorNumber == 0);
    assert(std::string(reinterpret_cast<char*>(lowMemory.data() + kReadAddress),
                       6u) == "legacy");

    preadOffsetHigh = 0xffffffffu;
    std::memcpy(lowMemory.data() + kStackAddress + sizeof(uint32_t),
                &preadOffsetHigh,
                sizeof(preadOffsetHigh));
    state = {};
    state.r[12] = 153;
    state.r[0] = static_cast<uint32_t>(guestFd);
    state.r[1] = kReadAddress;
    state.r[2] = 1u;
    state.r[13] = kStackAddress;
    const auto negativePread = rooted.dispatch(state, 0x80u, false);
    assert(negativePread.handled && negativePread.errorNumber == EINVAL);

    state = {};
    state.r[12] = 153;
    state.r[0] = static_cast<uint32_t>(guestFd);
    state.r[1] = kReadAddress;
    state.r[2] = 1u;
    state.r[13] = static_cast<uint32_t>(lowMemory.size() - 4u);
    const auto badPreadStack = rooted.dispatch(state, 0x80u, false);
    assert(badPreadStack.handled && badPreadStack.errorNumber == EFAULT);

    state = {};
    state.r[12] = 89;
    const auto descriptorLimit = rooted.dispatch(state, 0x80u, false);
    assert(descriptorLimit.handled && descriptorLimit.errorNumber == 0);
    assert(state.r[0] == 10240u);

    state = {};
    state.r[12] = 194;
    state.r[0] = 3u;
    state.r[1] = kRlimitAddress;
    const auto stackLimit = rooted.dispatch(state, 0x80u, false);
    assert(stackLimit.handled && stackLimit.errorNumber == 0);
    uint64_t stackCurrent = 0;
    uint64_t stackMaximum = 0;
    std::memcpy(&stackCurrent,
                lowMemory.data() + kRlimitAddress,
                sizeof(stackCurrent));
    std::memcpy(&stackMaximum,
                lowMemory.data() + kRlimitAddress + sizeof(uint64_t),
                sizeof(stackMaximum));
    assert(stackCurrent == 8ull * 1024ull * 1024ull);
    assert(stackMaximum == 64ull * 1024ull * 1024ull);

    state = {};
    state.r[12] = 194;
    state.r[0] = 0x1000u | 8u;
    state.r[1] = kRlimitAddress;
    const auto fileLimit = rooted.dispatch(state, 0x80u, false);
    assert(fileLimit.handled && fileLimit.errorNumber == 0);
    uint64_t fileCurrent = 0;
    uint64_t fileMaximum = 0;
    std::memcpy(&fileCurrent,
                lowMemory.data() + kRlimitAddress,
                sizeof(fileCurrent));
    std::memcpy(&fileMaximum,
                lowMemory.data() + kRlimitAddress + sizeof(uint64_t),
                sizeof(fileMaximum));
    assert(fileCurrent == 256u && fileMaximum == 10240u);

    state = {};
    state.r[12] = 194;
    state.r[0] = 99u;
    state.r[1] = kRlimitAddress;
    const auto badLimitResource = rooted.dispatch(state, 0x80u, false);
    assert(badLimitResource.handled && badLimitResource.errorNumber == EINVAL);

    state = {};
    state.r[12] = 194;
    state.r[0] = 3u;
    state.r[1] = static_cast<uint32_t>(lowMemory.size() - 8u);
    const auto badLimitPointer = rooted.dispatch(state, 0x80u, false);
    assert(badLimitPointer.handled && badLimitPointer.errorNumber == EFAULT);

    state = {};
    state.r[12] = 92;
    state.r[0] = static_cast<uint32_t>(guestFd);
    state.r[1] = kFcntlSetFd;
    state.r[2] = 0;
    const auto setFd = rooted.dispatch(state, 0x80u, false);
    assert(setFd.handled && setFd.errorNumber == 0);

    state = {};
    state.r[12] = 6;
    state.r[0] = static_cast<uint32_t>(guestFd);
    const auto closed = rooted.dispatch(state, 0x80u, false);
    assert(closed.handled && closed.errorNumber == 0);

    putCString(kPathAddress, "/../../etc/passwd");
    state = {};
    state.r[12] = 5;
    state.r[0] = kPathAddress;
    const auto traversal = rooted.dispatch(state, 0x80u, false);
    assert(traversal.handled && traversal.errorNumber == EACCES);

    putCString(kPathAddress, "/usr/lib/escape");
    state = {};
    state.r[12] = 338;
    state.r[0] = kPathAddress;
    state.r[1] = kStatAddress;
    const auto statEscape = rooted.dispatch(state, 0x80u, false);
    assert(statEscape.handled && statEscape.errorNumber == EACCES);

    std::filesystem::remove_all(root);
    std::cout << "LC32 Darwin syscall tests passed\n";
    return 0;
}
