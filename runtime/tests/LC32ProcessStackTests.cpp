#include "../LC32ProcessStack.hpp"

#include <cassert>
#include <cstring>
#include <iostream>
#include <vector>

using namespace lc32;

int main() {
    constexpr uint32_t base = 0x70000000u;
    constexpr uint32_t size = 0x10000u;
    std::vector<unsigned char> memory(size);
    auto write = [&](uint32_t address, const void* data, size_t count) {
        if (address < base || static_cast<uint64_t>(address - base) + count > memory.size()) return false;
        std::memcpy(memory.data() + (address - base), data, count);
        return true;
    };
    auto read32 = [&](uint32_t address) {
        uint32_t value = 0;
        std::memcpy(&value, memory.data() + (address - base), sizeof(value));
        return value;
    };
    auto readString = [&](uint32_t address) {
        return std::string(reinterpret_cast<const char*>(memory.data() + (address - base)));
    };

    ProcessStackSpec spec;
    spec.argv = {"/Applications/Felix.app/Felix", "-AppleLanguages", "(en)"};
    spec.envp = {"HOME=/var/mobile/Containers/Data/Application/test", "TMPDIR=/tmp"};
    spec.apple = {{"executable_path", "/Applications/Felix.app/Felix"}, {"kern.osversion", "24A"}};

    const auto result = buildDarwinProcessStack(base, size, spec, write);
    assert(result.ok);
    assert((result.stackPointer & 15u) == 0);
    assert(read32(result.argcAddress) == 3);
    const uint32_t argv0 = read32(result.argvAddress);
    assert(readString(argv0) == spec.argv[0]);
    assert(read32(result.argvAddress + 3 * 4) == 0);
    const uint32_t env0 = read32(result.envpAddress);
    assert(readString(env0) == spec.envp[0]);
    const uint32_t apple0 = read32(result.appleAddress);
    assert(readString(apple0) == "executable_path=/Applications/Felix.app/Felix");

    ProcessStackSpec invalid;
    const auto bad = buildDarwinProcessStack(base, size, invalid, write);
    assert(!bad.ok);

    std::cout << "LC32 Darwin process stack tests passed\n";
    return 0;
}
