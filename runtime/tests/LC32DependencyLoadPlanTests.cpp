#include "../LC32DependencyLoadPlan.hpp"

#include <cassert>
#include <cstring>
#include <iostream>
#include <unordered_map>

namespace {
void put32(std::vector<uint8_t>& v, size_t off, uint32_t x) {
    if (v.size() < off + 4) v.resize(off + 4);
    std::memcpy(v.data() + off, &x, 4);
}

std::vector<uint8_t> makeImage(const std::vector<std::pair<uint32_t, std::string>>& commands) {
    size_t sizeofcmds = 0;
    for (const auto& c : commands) sizeofcmds += (12 + c.second.size() + 1 + 3) & ~size_t(3);
    std::vector<uint8_t> v(28 + sizeofcmds, 0);
    put32(v, 0, 0xfeedfaceu);
    put32(v, 4, 12u);
    put32(v, 8, 9u);
    put32(v, 12, 6u);
    put32(v, 16, static_cast<uint32_t>(commands.size()));
    put32(v, 20, static_cast<uint32_t>(sizeofcmds));
    size_t off = 28;
    for (const auto& c : commands) {
        const uint32_t size = static_cast<uint32_t>((12 + c.second.size() + 1 + 3) & ~size_t(3));
        put32(v, off, c.first);
        put32(v, off + 4, size);
        put32(v, off + 8, 12u);
        std::memcpy(v.data() + off + 12, c.second.c_str(), c.second.size() + 1);
        off += size;
    }
    return v;
}
}

int main() {
    constexpr uint32_t LC_LOAD_DYLIB = 0x0cu;
    constexpr uint32_t LC_LOAD_WEAK_DYLIB = 0x80000018u;

    std::unordered_map<std::string, std::vector<uint8_t>> files;
    files["/guest/System/libA.dylib"] = makeImage({{LC_LOAD_DYLIB, "/System/libB.dylib"}});
    files["/guest/System/libB.dylib"] = makeImage({{LC_LOAD_DYLIB, "/System/libA.dylib"},
                                                   {LC_LOAD_WEAK_DYLIB, "/System/libMissingWeak.dylib"}});

    lc32::DependencyLoadPlanSpec spec;
    spec.rootGuestPath = "/Applications/Game.app/Game";
    spec.rootImage = makeImage({{LC_LOAD_DYLIB, "/System/libA.dylib"}});
    spec.context.guestRoot = "/guest";
    spec.context.executablePath = spec.rootGuestPath;
    spec.firstSlide = 0x30000000u;
    spec.slideStride = 0x01000000u;

    auto exists = [&](const std::string& host) { return files.count(host) != 0; };
    auto load = [&](const std::string& host, lc32::DependencyImage& image, std::string&) {
        auto it = files.find(host);
        if (it == files.end()) return false;
        image.bytes = it->second;
        return true;
    };

    auto plan = lc32::buildDependencyLoadPlan(spec, exists, load);
    assert(plan.ok);
    assert(plan.nodes.size() == 3);
    assert(plan.nodes[0].slide == 0x30000000u);
    assert(plan.nodes[1].slide == 0x31000000u);
    assert(plan.nodes[2].slide == 0x32000000u);
    assert(plan.missingRequired.empty());
    assert(plan.missingWeak.size() == 1);

    files.erase("/guest/System/libB.dylib");
    auto missing = lc32::buildDependencyLoadPlan(spec, exists, load);
    assert(!missing.ok);
    assert(missing.missingRequired.size() == 1);
    assert(missing.error == "required dependency chain is incomplete");

    std::cout << "LC32 dependency load-plan tests passed\n";
    return 0;
}
