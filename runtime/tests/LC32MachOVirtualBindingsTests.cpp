#include "../LC32MachOVirtualBindings.hpp"

#include <array>
#include <cassert>
#include <cstdint>
#include <cstring>
#include <iostream>
#include <vector>

namespace {

void put16(std::vector<uint8_t>& bytes, std::size_t offset, uint16_t value) {
    bytes[offset] = static_cast<uint8_t>(value);
    bytes[offset + 1] = static_cast<uint8_t>(value >> 8);
}

void put32(std::vector<uint8_t>& bytes, std::size_t offset, uint32_t value) {
    bytes[offset] = static_cast<uint8_t>(value);
    bytes[offset + 1] = static_cast<uint8_t>(value >> 8);
    bytes[offset + 2] = static_cast<uint8_t>(value >> 16);
    bytes[offset + 3] = static_cast<uint8_t>(value >> 24);
}

std::vector<uint8_t> makeMachO() {
    std::vector<uint8_t> bytes(0x400, 0);
    constexpr uint32_t segmentSize = 56 + 68;
    constexpr uint32_t symtabSize = 24;
    constexpr uint32_t dysymtabSize = 80;

    put32(bytes, 0, 0xFEEDFACEu);
    put32(bytes, 4, 12u);
    put32(bytes, 8, 9u);
    put32(bytes, 12, 2u);
    put32(bytes, 16, 3u);
    put32(bytes, 20, segmentSize + symtabSize + dysymtabSize);

    std::size_t command = 28;
    put32(bytes, command, 1u);
    put32(bytes, command + 4, segmentSize);
    std::memcpy(bytes.data() + command + 8, "__DATA", 6);
    put32(bytes, command + 24, 0x1000u);
    put32(bytes, command + 28, 0x2000u);
    put32(bytes, command + 32, 0u);
    put32(bytes, command + 36, static_cast<uint32_t>(bytes.size()));
    put32(bytes, command + 40, 7u);
    put32(bytes, command + 44, 3u);
    put32(bytes, command + 48, 1u);

    const std::size_t section = command + 56;
    std::memcpy(bytes.data() + section, "__la_symbol_ptr", 15);
    std::memcpy(bytes.data() + section + 16, "__DATA", 6);
    put32(bytes, section + 32, 0x2000u);
    put32(bytes, section + 36, 8u);
    put32(bytes, section + 40, 0x300u);
    put32(bytes, section + 44, 2u);
    put32(bytes, section + 56, 7u);
    put32(bytes, section + 60, 0u);

    command += segmentSize;
    put32(bytes, command, 2u);
    put32(bytes, command + 4, symtabSize);
    put32(bytes, command + 8, 0x280u);
    put32(bytes, command + 12, 2u);
    put32(bytes, command + 16, 0x298u);
    put32(bytes, command + 20, 32u);

    command += symtabSize;
    put32(bytes, command, 0xBu);
    put32(bytes, command + 4, dysymtabSize);
    put32(bytes, command + 56, 0x2C0u);
    put32(bytes, command + 60, 2u);

    put32(bytes, 0x280, 1u);
    bytes[0x284] = 0x01u;
    put16(bytes, 0x286, 0u);
    put32(bytes, 0x28C, 9u);
    bytes[0x290] = 0x01u;
    put16(bytes, 0x292, 0u);

    bytes[0x298] = 0;
    std::memcpy(bytes.data() + 0x299, "_memcpy", 8);
    std::memcpy(bytes.data() + 0x2A1, "_malloc", 8);

    put32(bytes, 0x2C0, 0u);
    put32(bytes, 0x2C4, 1u);
    return bytes;
}

} // namespace

int main() {
    const std::vector<uint8_t> image = makeMachO();
    const lc32::MachOVirtualBindingResult bindings =
        lc32::collectArmv7VirtualBindings(image.data(), image.size());
    assert(bindings.ok);
    assert(bindings.error.empty());
    assert(bindings.bindings.size() == 1);
    assert(bindings.bindings[0].symbol == "_memcpy");
    assert(bindings.bindings[0].slotAddress == 0x2000u);
    assert(bindings.bindings[0].target.canonicalName == "memcpy");
    assert(bindings.bindings[0].target.guestAddress == 0xF1000000u);
    assert(bindings.unsupportedSymbols.size() == 1);
    assert(bindings.unsupportedSymbols[0] == "_malloc");

    std::vector<uint8_t> memory(256, 0);
    memory[0x10] = 1;
    memory[0x11] = 2;
    memory[0x12] = 3;
    memory[0x13] = 4;
    lc32::VirtualRuntimeMemory virtualMemory{
        [&memory](uint32_t address, void* output, std::size_t size) {
            if (address > memory.size() || size > memory.size() - address) return false;
            std::memcpy(output, memory.data() + address, size);
            return true;
        },
        [&memory](uint32_t address, const void* input, std::size_t size) {
            if (address > memory.size() || size > memory.size() - address) return false;
            std::memcpy(memory.data() + address, input, size);
            return true;
        }};
    const std::array<uint32_t, 4> args = {0x20u, 0x10u, 4u, 0u};
    const lc32::VirtualRuntimeCallResult call =
        lc32::dispatchVirtualRuntimeSymbol(bindings.bindings[0].target, args, virtualMemory);
    assert(call.handled);
    assert(call.ok);
    assert(call.returnValue == 0x20u);
    assert(memory[0x20] == 1 && memory[0x21] == 2 && memory[0x22] == 3 && memory[0x23] == 4);

    std::cout << "LC32 virtual Mach-O binding tests passed\n";
    return 0;
}
