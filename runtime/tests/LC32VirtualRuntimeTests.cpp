#include "../LC32MachOImports.hpp"
#include "../LC32VirtualRuntime.hpp"

#include <array>
#include <cassert>
#include <cstdint>
#include <cstring>
#include <string>
#include <vector>

namespace {

void put32(std::vector<uint8_t>& data, std::size_t offset, uint32_t value) {
    data[offset] = static_cast<uint8_t>(value);
    data[offset + 1] = static_cast<uint8_t>(value >> 8);
    data[offset + 2] = static_cast<uint8_t>(value >> 16);
    data[offset + 3] = static_cast<uint8_t>(value >> 24);
}

std::vector<uint8_t> makeMachO() {
    const std::string strings("\0_memcpy\0_objc_msgSend\0_unknown_import\0", 39);
    std::vector<uint8_t> data(52 + 36 + strings.size());
    put32(data, 0, 0xFEEDFACEu);
    put32(data, 4, 12u);
    put32(data, 8, 9u);
    put32(data, 12, 2u);
    put32(data, 16, 1u);
    put32(data, 20, 24u);
    put32(data, 24, 0u);
    put32(data, 28, 2u);
    put32(data, 32, 24u);
    put32(data, 36, 52u);
    put32(data, 40, 3u);
    put32(data, 44, 88u);
    put32(data, 48, static_cast<uint32_t>(strings.size()));

    const uint32_t offsets[] = {1u, 9u, 23u};
    for (std::size_t index = 0; index < 3; ++index) {
        const std::size_t entry = 52 + index * 12;
        put32(data, entry, offsets[index]);
        data[entry + 4] = 1u;
    }
    std::memcpy(data.data() + 88, strings.data(), strings.size());
    return data;
}

} // namespace

int main() {
    const auto libSystem = lc32::resolveVirtualRuntimeImage("/usr/lib/libSystem.B.dylib");
    assert(libSystem.kind == lc32::VirtualRuntimeImageKind::LibSystem);
    const auto objc = lc32::resolveVirtualRuntimeImage("libobjc.A.dylib");
    assert(objc.kind == lc32::VirtualRuntimeImageKind::LibObjC);

    const auto memcpySymbol = lc32::resolveVirtualRuntimeSymbol("_memcpy");
    assert(memcpySymbol.executable);
    assert(memcpySymbol.guestAddress == 0xF1000000u);
    const auto objcSymbol = lc32::resolveVirtualRuntimeSymbol("_objc_msgSend");
    assert(objcSymbol.imageKind == lc32::VirtualRuntimeImageKind::LibObjC);
    assert(!objcSymbol.executable);

    std::vector<uint8_t> memory(256);
    const char* hello = "hello";
    std::memcpy(memory.data() + 32, hello, 6);
    lc32::VirtualRuntimeMemory callbacks{
        [&](uint32_t address, void* out, std::size_t size) {
            if (address > memory.size() || size > memory.size() - address) return false;
            std::memcpy(out, memory.data() + address, size);
            return true;
        },
        [&](uint32_t address, const void* in, std::size_t size) {
            if (address > memory.size() || size > memory.size() - address) return false;
            std::memcpy(memory.data() + address, in, size);
            return true;
        }};
    auto copied = lc32::dispatchVirtualRuntimeSymbol(memcpySymbol, {64u, 32u, 6u, 0u}, callbacks);
    assert(copied.handled && copied.ok && copied.returnValue == 64u);
    assert(std::memcmp(memory.data() + 64, hello, 6) == 0);
    auto length = lc32::dispatchVirtualRuntimeSymbol(
        lc32::resolveVirtualRuntimeSymbol("_strlen"), {64u, 0u, 0u, 0u}, callbacks);
    assert(length.handled && length.ok && length.returnValue == 5u);

    const auto image = makeMachO();
    const auto imports = lc32::parseArmv7MachOImports(image.data(), image.size());
    assert(imports.ok);
    assert(imports.symbols.size() == 3u);
    assert(imports.symbols[0] == "_memcpy");
    assert(imports.symbols[1] == "_objc_msgSend");
    assert(imports.symbols[2] == "_unknown_import");
    return 0;
}
