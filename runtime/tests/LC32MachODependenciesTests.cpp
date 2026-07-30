#include "../LC32MachODependencies.hpp"

#include <cassert>
#include <cstring>
#include <iostream>
#include <vector>

namespace {
void put32(std::vector<uint8_t>& v, size_t off, uint32_t x) {
    if (v.size() < off + 4) v.resize(off + 4);
    std::memcpy(v.data() + off, &x, 4);
}
uint32_t align4(uint32_t x) { return (x + 3u) & ~3u; }
uint32_t appendStringCommand(std::vector<uint8_t>& v, size_t off, uint32_t type, const char* text, bool dylib) {
    const uint32_t base = dylib ? 24u : 12u;
    const uint32_t size = align4(base + static_cast<uint32_t>(std::strlen(text)) + 1u);
    if (v.size() < off + size) v.resize(off + size);
    put32(v, off, type);
    put32(v, off + 4, size);
    put32(v, off + 8, base);
    if (dylib) { put32(v, off + 16, 0x10000u); put32(v, off + 20, 0x10000u); }
    std::memcpy(v.data() + off + base, text, std::strlen(text) + 1);
    return size;
}
}

int main() {
    std::vector<uint8_t> image(28, 0);
    put32(image, 0, 0xfeedfaceu);
    put32(image, 4, 12u);
    put32(image, 8, 9u);
    put32(image, 12, 2u);

    size_t cursor = 28;
    uint32_t total = 0;
    total += appendStringCommand(image, cursor + total, 0x0eu, "/usr/lib/dyld", false);
    total += appendStringCommand(image, cursor + total, 0x0cu, "/System/Library/Frameworks/UIKit.framework/UIKit", true);
    total += appendStringCommand(image, cursor + total, 0x80000018u, "/usr/lib/libSystem.B.dylib", true);
    total += appendStringCommand(image, cursor + total, 0x8000001fu, "@rpath/GameSupport.framework/GameSupport", true);
    total += appendStringCommand(image, cursor + total, 0x8000001cu, "@executable_path/Frameworks", false);
    put32(image, 16, 5u);
    put32(image, 20, total);

    auto result = lc32::parseArmv7MachODependencies(image.data(), image.size());
    assert(result.ok);
    assert(result.dyldPath == "/usr/lib/dyld");
    assert(result.rpaths.size() == 1);
    assert(result.rpaths[0] == "@executable_path/Frameworks");
    assert(result.dependencies.size() == 3);
    assert(result.dependencies[0].kind == lc32::DependencyKind::Load);
    assert(result.dependencies[1].kind == lc32::DependencyKind::Weak);
    assert(result.dependencies[2].kind == lc32::DependencyKind::Reexport);
    assert(result.dependencies[2].path == "@rpath/GameSupport.framework/GameSupport");

    std::cout << "LC32 Mach-O dependency tests passed\n";
    return 0;
}
