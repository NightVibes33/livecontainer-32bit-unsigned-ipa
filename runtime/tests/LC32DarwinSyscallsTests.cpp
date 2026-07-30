#include "../LC32DarwinSyscalls.hpp"

#include <cassert>
#include <cerrno>
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

    std::vector<unsigned char> memory(4096);
    SyscallMemory sm;
    sm.read = [&](uint32_t address, void* out, size_t size) {
        if (address + size > memory.size()) return false;
        std::memcpy(out, memory.data() + address, size);
        return true;
    };
    sm.write = [&](uint32_t address, const void* in, size_t size) {
        if (address + size > memory.size()) return false;
        std::memcpy(memory.data() + address, in, size);
        return true;
    };

    DarwinSyscalls sys(sm);
    CPUState state{};

    state.r[12] = 0x80000000u | 20u;
    auto getpid = sys.dispatch(state, 0, false);
    assert(getpid.handled);
    assert(getpid.trapClass == TrapClass::Unix);
    assert(getpid.number == 20);
    assert(state.r[0] != 0);

    state = {};
    state.r[12] = 0x80000000u | 116u;
    state.r[0] = 128;
    auto gtod = sys.dispatch(state, 0, false);
    assert(gtod.handled && gtod.errorNumber == 0);
    int32_t sec = 0;
    std::memcpy(&sec, memory.data() + 128, sizeof(sec));
    assert(sec > 0);

    const char hello[] = "hello";
    std::memcpy(memory.data() + 256, hello, sizeof(hello));
    std::string value;
    assert(sys.readCString(256, value));
    assert(value == "hello");

    state = {};
    state.r[12] = static_cast<uint32_t>(-28);
    auto taskSelf = sys.dispatch(state, 0, false);
    assert(taskSelf.handled);
    assert(taskSelf.trapClass == TrapClass::Mach);
    assert(state.r[0] == 0x102u);

    state = {};
    state.r[12] = 0x80000000u | 9999u;
    auto unknown = sys.dispatch(state, 0, false);
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

    DarwinSyscalls rooted(sm, root.string());
    const auto putCString = [&](uint32_t address, const std::string& text) {
        assert(address + text.size() + 1u <= memory.size());
        std::memcpy(memory.data() + address, text.c_str(), text.size() + 1u);
    };

    putCString(512, "/usr/lib/libA.dylib");

    state = {};
    state.r[12] = 33;
    state.r[0] = 512;
    state.r[1] = F_OK;
    auto exists = rooted.dispatch(state, 0x80u, false);
    assert(exists.handled && exists.errorNumber == 0);

    state = {};
    state.r[12] = 33;
    state.r[0] = 512;
    state.r[1] = R_OK;
    auto readable = rooted.dispatch(state, 0x80u, false);
    assert(readable.handled && readable.errorNumber == 0);

    state = {};
    state.r[12] = 33;
    state.r[0] = 512;
    state.r[1] = W_OK;
    auto writable = rooted.dispatch(state, 0x80u, false);
    assert(writable.handled && writable.errorNumber == EROFS);

    state = {};
    state.r[12] = 5;
    state.r[0] = 512;
    state.r[1] = kGuestOpenCloseExec;
    auto opened = rooted.dispatch(state, 0x80u, false);
    assert(opened.handled && opened.errorNumber == 0);
    const int guestFd = static_cast<int>(state.r[0]);
    assert(guestFd >= 3);

    state = {};
    state.r[12] = 92;
    state.r[0] = static_cast<uint32_t>(guestFd);
    state.r[1] = kFcntlGetFd;
    auto getFd = rooted.dispatch(state, 0x80u, false);
    assert(getFd.handled && getFd.errorNumber == 0);
    assert(state.r[0] == 1u);

    state = {};
    state.r[12] = 92;
    state.r[0] = static_cast<uint32_t>(guestFd);
    state.r[1] = kFcntlGetFl;
    auto getFl = rooted.dispatch(state, 0x80u, false);
    assert(getFl.handled && getFl.errorNumber == 0);
    assert(state.r[0] == kGuestOpenCloseExec);

    state = {};
    state.r[12] = 92;
    state.r[0] = static_cast<uint32_t>(guestFd);
    state.r[1] = kFcntlSetFd;
    state.r[2] = 0;
    auto setFd = rooted.dispatch(state, 0x80u, false);
    assert(setFd.handled && setFd.errorNumber == 0);

    state = {};
    state.r[12] = 92;
    state.r[0] = static_cast<uint32_t>(guestFd);
    state.r[1] = kFcntlGetFd;
    auto getFdCleared = rooted.dispatch(state, 0x80u, false);
    assert(getFdCleared.handled && getFdCleared.errorNumber == 0);
    assert(state.r[0] == 0u);

    state = {};
    state.r[12] = 3;
    state.r[0] = static_cast<uint32_t>(guestFd);
    state.r[1] = 1024;
    state.r[2] = static_cast<uint32_t>(payload.size());
    auto read = rooted.dispatch(state, 0x80u, false);
    assert(read.handled && read.errorNumber == 0);
    assert(state.r[0] == payload.size());
    assert(std::memcmp(memory.data() + 1024, payload.data(), payload.size()) == 0);

    state = {};
    state.r[12] = 6;
    state.r[0] = static_cast<uint32_t>(guestFd);
    auto closed = rooted.dispatch(state, 0x80u, false);
    assert(closed.handled && closed.errorNumber == 0);

    state = {};
    state.r[12] = 3;
    state.r[0] = static_cast<uint32_t>(guestFd);
    state.r[1] = 1024;
    state.r[2] = 1;
    auto readClosed = rooted.dispatch(state, 0x80u, false);
    assert(readClosed.handled && readClosed.errorNumber == EBADF);

    state = {};
    state.r[12] = 5;
    state.r[0] = 512;
    state.r[1] = 1;
    auto writeOpen = rooted.dispatch(state, 0x80u, false);
    assert(writeOpen.handled && writeOpen.errorNumber == EROFS);

    putCString(512, "/missing.dylib");
    state = {};
    state.r[12] = 33;
    state.r[0] = 512;
    state.r[1] = F_OK;
    auto missing = rooted.dispatch(state, 0x80u, false);
    assert(missing.handled && missing.errorNumber == ENOENT);

    putCString(512, "/../../etc/passwd");
    state = {};
    state.r[12] = 5;
    state.r[0] = 512;
    auto traversal = rooted.dispatch(state, 0x80u, false);
    assert(traversal.handled && traversal.errorNumber == EACCES);

    putCString(512, "/usr/lib/escape");
    state = {};
    state.r[12] = 5;
    state.r[0] = 512;
    auto symlinkEscape = rooted.dispatch(state, 0x80u, false);
    assert(symlinkEscape.handled && symlinkEscape.errorNumber == EACCES);

    std::filesystem::remove_all(root);
    std::cout << "LC32 Darwin syscall tests passed\n";
    return 0;
}
