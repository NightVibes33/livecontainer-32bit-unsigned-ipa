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

int main() {
    constexpr uint32_t kGuestOpenCloseExec = 0x01000000u;
    constexpr uint32_t kFcntlGetFd = 1u;
    constexpr uint32_t kFcntlSetFd = 2u;
    constexpr uint32_t kFcntlGetFl = 3u;
    constexpr uint32_t kGuestStat64Size = 108u;
    constexpr uint32_t kGuestStat64ModeOffset = 4u;
    constexpr uint32_t kGuestStat64LinkCountOffset = 6u;
    constexpr uint32_t kGuestStat64SizeOffset = 60u;
    constexpr uint32_t kPathAddress = 512u;
    constexpr uint32_t kReadAddress = 1024u;
    constexpr uint32_t kStatAddress = 2048u;
    constexpr uint32_t kFstatAddress = 2304u;
    constexpr uint32_t kStackAddress = 3500u;

    std::vector<unsigned char> memory(4096);
    SyscallMemory syscallMemory;
    syscallMemory.read = [&](uint32_t address, void* output, size_t size) {
        if (static_cast<uint64_t>(address) + size > memory.size()) return false;
        std::memcpy(output, memory.data() + address, size);
        return true;
    };
    syscallMemory.write = [&](uint32_t address, const void* input, size_t size) {
        if (static_cast<uint64_t>(address) + size > memory.size()) return false;
        std::memcpy(memory.data() + address, input, size);
        return true;
    };

    DarwinSyscalls syscalls(syscallMemory);
    CPUState state{};

    state.r[12] = 0x80000000u | 20u;
    const auto getpid = syscalls.dispatch(state, 0, false);
    assert(getpid.handled);
    assert(getpid.trapClass == TrapClass::Unix);
    assert(getpid.number == 20);
    assert(state.r[0] != 0);

    state = {};
    state.r[12] = 0x80000000u | 116u;
    state.r[0] = 128;
    const auto gettimeofday = syscalls.dispatch(state, 0, false);
    assert(gettimeofday.handled && gettimeofday.errorNumber == 0);
    int32_t seconds = 0;
    std::memcpy(&seconds, memory.data() + 128, sizeof(seconds));
    assert(seconds > 0);

    const char hello[] = "hello";
    std::memcpy(memory.data() + 256, hello, sizeof(hello));
    std::string value;
    assert(syscalls.readCString(256, value));
    assert(value == "hello");

    state = {};
    state.r[12] = static_cast<uint32_t>(-28);
    const auto taskSelf = syscalls.dispatch(state, 0, false);
    assert(taskSelf.handled);
    assert(taskSelf.trapClass == TrapClass::Mach);
    assert(state.r[0] == 0x102u);

    state = {};
    state.r[12] = 0x80000000u | 9999u;
    const auto unknown = syscalls.dispatch(state, 0, false);
    assert(!unknown.handled);
    assert(unknown.number == 9999u);

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
        assert(static_cast<uint64_t>(address) + text.size() + 1u <= memory.size());
        std::memcpy(memory.data() + address, text.c_str(), text.size() + 1u);
    };
    const auto putWord = [&](uint32_t address, uint32_t word) {
        assert(static_cast<uint64_t>(address) + sizeof(word) <= memory.size());
        std::memcpy(memory.data() + address, &word, sizeof(word));
    };
    const auto readStatFields = [&](uint32_t address,
                                    uint16_t& mode,
                                    uint16_t& links,
                                    int64_t& size) {
        std::memcpy(&mode,
                    memory.data() + address + kGuestStat64ModeOffset,
                    sizeof(mode));
        std::memcpy(&links,
                    memory.data() + address + kGuestStat64LinkCountOffset,
                    sizeof(links));
        std::memcpy(&size,
                    memory.data() + address + kGuestStat64SizeOffset,
                    sizeof(size));
    };

    putCString(kPathAddress, "/usr/lib/libA.dylib");

    state = {};
    state.r[12] = 33;
    state.r[0] = kPathAddress;
    state.r[1] = F_OK;
    const auto exists = rooted.dispatch(state, 0x80u, false);
    assert(exists.handled && exists.errorNumber == 0);

    state = {};
    state.r[12] = 33;
    state.r[0] = kPathAddress;
    state.r[1] = R_OK;
    const auto readable = rooted.dispatch(state, 0x80u, false);
    assert(readable.handled && readable.errorNumber == 0);

    state = {};
    state.r[12] = 33;
    state.r[0] = kPathAddress;
    state.r[1] = W_OK;
    const auto writable = rooted.dispatch(state, 0x80u, false);
    assert(writable.handled && writable.errorNumber == EROFS);

    std::memset(memory.data() + kStatAddress, 0xa5, kGuestStat64Size + 1u);
    state = {};
    state.r[12] = 338;
    state.r[0] = kPathAddress;
    state.r[1] = kStatAddress;
    const auto stat64 = rooted.dispatch(state, 0x80u, false);
    assert(stat64.handled && stat64.errorNumber == 0);
    assert(state.r[0] == 0u);
    assert(memory[kStatAddress + kGuestStat64Size] == 0xa5u);

    uint16_t statMode = 0;
    uint16_t statLinks = 0;
    int64_t statSize = -1;
    readStatFields(kStatAddress, statMode, statLinks, statSize);
    assert((statMode & 0170000u) == 0100000u);
    assert(statLinks >= 1u);
    assert(statSize == static_cast<int64_t>(payload.size()));

    state = {};
    state.r[12] = 338;
    state.r[0] = kPathAddress;
    state.r[1] = static_cast<uint32_t>(memory.size() - 8u);
    const auto statBadPointer = rooted.dispatch(state, 0x80u, false);
    assert(statBadPointer.handled && statBadPointer.errorNumber == EFAULT);

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
    assert(getFd.handled && getFd.errorNumber == 0);
    assert(state.r[0] == 1u);

    state = {};
    state.r[12] = 92;
    state.r[0] = static_cast<uint32_t>(guestFd);
    state.r[1] = kFcntlGetFl;
    const auto getFl = rooted.dispatch(state, 0x80u, false);
    assert(getFl.handled && getFl.errorNumber == 0);
    assert(state.r[0] == kGuestOpenCloseExec);

    std::memset(memory.data() + kFstatAddress, 0x5a, kGuestStat64Size + 1u);
    state = {};
    state.r[12] = 339;
    state.r[0] = static_cast<uint32_t>(guestFd);
    state.r[1] = kFstatAddress;
    const auto fstat64 = rooted.dispatch(state, 0x80u, false);
    assert(fstat64.handled && fstat64.errorNumber == 0);
    assert(state.r[0] == 0u);
    assert(memory[kFstatAddress + kGuestStat64Size] == 0x5au);

    uint16_t fstatMode = 0;
    uint16_t fstatLinks = 0;
    int64_t fstatSize = -1;
    readStatFields(kFstatAddress, fstatMode, fstatLinks, fstatSize);
    assert((fstatMode & 0170000u) == 0100000u);
    assert(fstatLinks >= 1u);
    assert(fstatSize == static_cast<int64_t>(payload.size()));

    state = {};
    state.r[12] = 339;
    state.r[0] = 9999u;
    state.r[1] = kFstatAddress;
    const auto fstatBadFd = rooted.dispatch(state, 0x80u, false);
    assert(fstatBadFd.handled && fstatBadFd.errorNumber == EBADF);

    state = {};
    state.r[12] = 339;
    state.r[0] = static_cast<uint32_t>(guestFd);
    state.r[1] = static_cast<uint32_t>(memory.size() - 8u);
    const auto fstatBadPointer = rooted.dispatch(state, 0x80u, false);
    assert(fstatBadPointer.handled && fstatBadPointer.errorNumber == EFAULT);

    const auto seekGuest = [&](int64_t offset, int whence) {
        putWord(kStackAddress, static_cast<uint32_t>(whence));
        const uint64_t bits = static_cast<uint64_t>(offset);
        state = {};
        state.r[12] = 199;
        state.r[0] = static_cast<uint32_t>(guestFd);
        state.r[1] = 0xccccccccu; // AAPCS alignment hole before off_t.
        state.r[2] = static_cast<uint32_t>(bits);
        state.r[3] = static_cast<uint32_t>(bits >> 32u);
        state.r[13] = kStackAddress;
        return rooted.dispatch(state, 0x80u, false);
    };

    const auto seekSeven = seekGuest(7, SEEK_SET);
    assert(seekSeven.handled && seekSeven.errorNumber == 0);
    assert(state.r[0] == 7u);
    assert(state.r[1] == 0u);

    state = {};
    state.r[12] = 3;
    state.r[0] = static_cast<uint32_t>(guestFd);
    state.r[1] = kReadAddress;
    state.r[2] = 5;
    const auto readMiddle = rooted.dispatch(state, 0x80u, false);
    assert(readMiddle.handled && readMiddle.errorNumber == 0);
    assert(state.r[0] == 5u);
    assert(std::memcmp(memory.data() + kReadAddress, "dylib", 5) == 0);

    const auto seekEnd = seekGuest(-5, SEEK_END);
    assert(seekEnd.handled && seekEnd.errorNumber == 0);
    assert(state.r[0] == payload.size() - 5u);
    assert(state.r[1] == 0u);

    state = {};
    state.r[12] = 3;
    state.r[0] = static_cast<uint32_t>(guestFd);
    state.r[1] = kReadAddress;
    state.r[2] = 5;
    const auto readEnd = rooted.dispatch(state, 0x80u, false);
    assert(readEnd.handled && readEnd.errorNumber == 0);
    assert(std::memcmp(memory.data() + kReadAddress, "bytes", 5) == 0);

    const auto badWhence = seekGuest(0, 99);
    assert(badWhence.handled && badWhence.errorNumber == EINVAL);

    state = {};
    state.r[12] = 199;
    state.r[0] = 9999u;
    state.r[13] = kStackAddress;
    const auto seekBadFd = rooted.dispatch(state, 0x80u, false);
    assert(seekBadFd.handled && seekBadFd.errorNumber == EBADF);

    state = {};
    state.r[12] = 199;
    state.r[0] = static_cast<uint32_t>(guestFd);
    state.r[13] = static_cast<uint32_t>(memory.size() - 2u);
    const auto seekBadStack = rooted.dispatch(state, 0x80u, false);
    assert(seekBadStack.handled && seekBadStack.errorNumber == EFAULT);

    const auto seekStart = seekGuest(0, SEEK_SET);
    assert(seekStart.handled && seekStart.errorNumber == 0);

    state = {};
    state.r[12] = 92;
    state.r[0] = static_cast<uint32_t>(guestFd);
    state.r[1] = kFcntlSetFd;
    state.r[2] = 0;
    const auto setFd = rooted.dispatch(state, 0x80u, false);
    assert(setFd.handled && setFd.errorNumber == 0);

    state = {};
    state.r[12] = 92;
    state.r[0] = static_cast<uint32_t>(guestFd);
    state.r[1] = kFcntlGetFd;
    const auto getFdCleared = rooted.dispatch(state, 0x80u, false);
    assert(getFdCleared.handled && getFdCleared.errorNumber == 0);
    assert(state.r[0] == 0u);

    state = {};
    state.r[12] = 3;
    state.r[0] = static_cast<uint32_t>(guestFd);
    state.r[1] = kReadAddress;
    state.r[2] = static_cast<uint32_t>(payload.size());
    const auto read = rooted.dispatch(state, 0x80u, false);
    assert(read.handled && read.errorNumber == 0);
    assert(state.r[0] == payload.size());
    assert(std::memcmp(memory.data() + kReadAddress, payload.data(), payload.size()) == 0);

    state = {};
    state.r[12] = 6;
    state.r[0] = static_cast<uint32_t>(guestFd);
    const auto closed = rooted.dispatch(state, 0x80u, false);
    assert(closed.handled && closed.errorNumber == 0);

    state = {};
    state.r[12] = 3;
    state.r[0] = static_cast<uint32_t>(guestFd);
    state.r[1] = kReadAddress;
    state.r[2] = 1;
    const auto readClosed = rooted.dispatch(state, 0x80u, false);
    assert(readClosed.handled && readClosed.errorNumber == EBADF);

    state = {};
    state.r[12] = 5;
    state.r[0] = kPathAddress;
    state.r[1] = 1;
    const auto writeOpen = rooted.dispatch(state, 0x80u, false);
    assert(writeOpen.handled && writeOpen.errorNumber == EROFS);

    putCString(kPathAddress, "/missing.dylib");
    state = {};
    state.r[12] = 33;
    state.r[0] = kPathAddress;
    state.r[1] = F_OK;
    const auto missing = rooted.dispatch(state, 0x80u, false);
    assert(missing.handled && missing.errorNumber == ENOENT);

    state = {};
    state.r[12] = 338;
    state.r[0] = kPathAddress;
    state.r[1] = kStatAddress;
    const auto statMissing = rooted.dispatch(state, 0x80u, false);
    assert(statMissing.handled && statMissing.errorNumber == ENOENT);

    putCString(kPathAddress, "/../../etc/passwd");
    state = {};
    state.r[12] = 5;
    state.r[0] = kPathAddress;
    const auto traversal = rooted.dispatch(state, 0x80u, false);
    assert(traversal.handled && traversal.errorNumber == EACCES);

    putCString(kPathAddress, "/usr/lib/escape");
    state = {};
    state.r[12] = 5;
    state.r[0] = kPathAddress;
    const auto symlinkEscape = rooted.dispatch(state, 0x80u, false);
    assert(symlinkEscape.handled && symlinkEscape.errorNumber == EACCES);

    state = {};
    state.r[12] = 338;
    state.r[0] = kPathAddress;
    state.r[1] = kStatAddress;
    const auto statSymlinkEscape = rooted.dispatch(state, 0x80u, false);
    assert(statSymlinkEscape.handled && statSymlinkEscape.errorNumber == EACCES);

    std::filesystem::remove_all(root);
    std::cout << "LC32 Darwin syscall tests passed\n";
    return 0;
}
