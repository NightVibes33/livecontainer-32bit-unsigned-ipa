#include "../LC32DyldHandoff.hpp"

#include <cassert>
#include <cstdint>
#include <cstring>
#include <iostream>
#include <vector>

namespace {
void put32(std::vector<uint8_t>& v, size_t off, uint32_t x) {
    if (v.size() < off + 4) v.resize(off + 4);
    std::memcpy(v.data() + off, &x, 4);
}

std::vector<uint8_t> makeMachO(uint32_t vmaddr, uint32_t entryoff) {
    std::vector<uint8_t> v(0x200, 0);
    put32(v, 0x00, 0xfeedfaceu);
    put32(v, 0x04, 12u);
    put32(v, 0x08, 9u);
    put32(v, 0x0c, 2u);
    put32(v, 0x10, 2u);
    put32(v, 0x14, 80u);
    size_t lc = 0x1c;
    put32(v, lc + 0x00, 1u);
    put32(v, lc + 0x04, 56u);
    std::memcpy(v.data() + lc + 8, "__TEXT", 6);
    put32(v, lc + 0x18, vmaddr);
    put32(v, lc + 0x1c, 0x1000u);
    put32(v, lc + 0x20, 0u);
    put32(v, lc + 0x24, 0x200u);
    put32(v, lc + 0x28, 7u);
    put32(v, lc + 0x2c, 5u);
    lc += 56;
    put32(v, lc + 0x00, 0x80000028u);
    put32(v, lc + 0x04, 24u);
    put32(v, lc + 0x08, entryoff);
    return v;
}
}

int main() {
    auto app = makeMachO(0x1000u, 0x100u);
    auto dyld = makeMachO(0x2000u, 0x120u);

    struct Region { uint32_t base; std::vector<uint8_t> bytes; };
    std::vector<Region> regions;
    auto map = [&](uint32_t address, uint32_t size, uint32_t) {
        for (const auto& r : regions) {
            uint64_t aEnd = uint64_t(address) + size;
            uint64_t rEnd = uint64_t(r.base) + r.bytes.size();
            if (!(aEnd <= r.base || address >= rEnd)) return false;
        }
        regions.push_back({address, std::vector<uint8_t>(size)});
        return true;
    };
    auto write = [&](uint32_t address, const void* data, size_t size) {
        for (auto& r : regions) {
            if (address >= r.base && uint64_t(address) + size <= uint64_t(r.base) + r.bytes.size()) {
                std::memcpy(r.bytes.data() + (address - r.base), data, size);
                return true;
            }
        }
        return false;
    };

    lc32::DyldHandoffSpec spec;
    spec.appImage = app.data(); spec.appSize = app.size();
    spec.dyldImage = dyld.data(); spec.dyldSize = dyld.size();
    spec.executablePath = "/Applications/FixItFelix.app/FixItFelix";
    spec.appSlide = 0x10000000u;
    spec.dyldSlide = 0x20000000u;
    auto result = lc32::prepareDyldHandoff(spec, map, write);

    assert(result.ok);
    assert(result.mainMachHeader == spec.appSlide + 0x1000u);
    assert(result.pc == spec.dyldSlide + 0x2000u + 0x120u);
    assert(result.sp != 0 && (result.sp & 0xfu) == 0);
    assert(!result.thumb);

    auto missing = spec;
    missing.dyldImage = nullptr;
    auto failure = lc32::prepareDyldHandoff(missing, map, write);
    assert(!failure.ok);
    assert(failure.error == "missing dyld image");

    std::cout << "LC32 dyld handoff tests passed\n";
    return 0;
}
