#include "../LC32DarwinSyscalls.hpp"

#include <cassert>
#include <cstring>
#include <iostream>
#include <vector>

using namespace lc32;

int main() {
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

    std::cout << "LC32 Darwin syscall tests passed\n";
    return 0;
}
