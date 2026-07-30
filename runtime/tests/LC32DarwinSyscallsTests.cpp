#include "../LC32DarwinSyscalls.hpp"

#include <cassert>
#include <cerrno>
#include <cstdint>
#include <cstring>
#include <filesystem>
#include <fstream>
#include <iostream>
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
    constexpr uint32_t kStackAddress = 0x3000u;

    constexpr uint32_t kProtRead = 0x01u;
    constexpr uint32_t kProtWrite = 0x02u;
    constexpr uint32_t kProtExec = 0x04u;
    constexpr uint32_t kMapPrivate = 0x0002u;
    constexpr uint32_t kMapFixed = 0x0010u;
    constexpr uint32_t kMapJit = 0x0800u;
    constexpr uint32_t kMapAnonymous = 0x1000u;

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

    char rootTemplate[] = "/tmp/lc32-syscalls-XXXXXX";
    char* rootDirectory = ::mkdtemp(rootTemplate);
    assert(rootDirectory != nullptr);
    const std::filesystem::path root(rootDirectory);
    std::filesystem::create_directories(root / "usr/lib");

    const std::string payload = "legacy-dylib-bytes";
    {
        std::ofstream file(root / "usr/lib/libA.dylib", std::ios::binary);
        file.write(payload.data(), static_cast<std::streamsize>(payload.size()));
    }
    assert(::symlink("/etc/passwd", (root / "usr/lib/escape").c_str()) == 0);

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
