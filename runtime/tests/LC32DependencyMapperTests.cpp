#include "../LC32DependencyMapper.hpp"

#include <cassert>
#include <cstdint>
#include <cstring>
#include <map>
#include <string>
#include <vector>

namespace {
#pragma pack(push, 1)
struct MachHeader { uint32_t magic; int32_t cpuType, cpuSubtype; uint32_t filetype, ncmds, sizeofcmds, flags; };
struct SegmentCommand {
    uint32_t cmd, cmdsize; char segname[16];
    uint32_t vmaddr, vmsize, fileoff, filesize;
    int32_t maxprot, initprot; uint32_t nsects, flags;
};
#pragma pack(pop)

std::vector<uint8_t> makeMachO() {
    MachHeader mh{0xfeedfaceu, 12, 9, 6, 1, static_cast<uint32_t>(sizeof(SegmentCommand)), 0};
    SegmentCommand seg{};
    seg.cmd = 1;
    seg.cmdsize = sizeof(seg);
    std::memcpy(seg.segname, "__TEXT", 6);
    seg.vmaddr = 0x1000;
    seg.vmsize = 0x1000;
    seg.fileoff = 0;
    seg.filesize = 0x100;
    seg.initprot = 5;
    std::vector<uint8_t> file(0x100, 0);
    std::memcpy(file.data(), &mh, sizeof(mh));
    std::memcpy(file.data() + sizeof(mh), &seg, sizeof(seg));
    return file;
}
}

int main() {
    const auto image = makeMachO();
    lc32::DependencyLoadPlanResult plan;
    plan.ok = true;
    plan.nodes.push_back({"/Applications/Game.app/Game", "", "", 0x10000000u, {}});
    plan.nodes.push_back({"/usr/lib/libA.dylib", "/root/usr/lib/libA.dylib", "/Applications/Game.app/Game", 0x30000000u, {}});
    plan.nodes.push_back({"/usr/lib/libB.dylib", "/root/usr/lib/libB.dylib", "/usr/lib/libA.dylib", 0x31000000u, {}});

    std::map<uint32_t, std::vector<uint8_t>> regions;
    auto load = [&](const std::string& hostPath, lc32::DependencyImage& out, std::string&) {
        out.guestPath = hostPath.find("libA") != std::string::npos
                            ? "/usr/lib/libA.dylib"
                            : "/usr/lib/libB.dylib";
        out.bytes = image;
        return true;
    };
    auto mapped = lc32::mapDependencyLoadPlan(
        plan, load,
        [&](uint32_t address, uint32_t size, uint32_t) {
            regions.emplace(address, std::vector<uint8_t>(size));
            return true;
        },
        [&](uint32_t address, const void* data, std::size_t size) {
            for (auto& region : regions) {
                const uint64_t end = uint64_t(region.first) + region.second.size();
                if (address >= region.first && uint64_t(address) + size <= end) {
                    std::memcpy(region.second.data() + (address - region.first), data, size);
                    return true;
                }
            }
            return false;
        });
    assert(mapped.ok);
    assert(mapped.images.size() == 2);
    assert(mapped.images[0].load.ok);
    assert(mapped.images[0].load.segments[0].vmaddr == 0x30001000u);
    assert(mapped.images[1].load.segments[0].vmaddr == 0x31001000u);
    assert(regions.count(0x30001000u) == 1);
    assert(regions.count(0x31001000u) == 1);

    auto reloadFailure = lc32::mapDependencyLoadPlan(
        plan,
        [](const std::string&, lc32::DependencyImage&, std::string& error) {
            error = "read failed";
            return false;
        },
        [](uint32_t, uint32_t, uint32_t) { return true; },
        [](uint32_t, const void*, std::size_t) { return true; });
    assert(!reloadFailure.ok);
    assert(reloadFailure.error.find("read failed") != std::string::npos);

    auto mismatch = lc32::mapDependencyLoadPlan(
        plan,
        [&](const std::string&, lc32::DependencyImage& out, std::string&) {
            out.guestPath = "/wrong/path.dylib";
            out.bytes = image;
            return true;
        },
        [](uint32_t, uint32_t, uint32_t) { return true; },
        [](uint32_t, const void*, std::size_t) { return true; });
    assert(!mismatch.ok);
    assert(mismatch.error.find("guest-path mismatch") != std::string::npos);

    lc32::DependencyLoadPlanResult invalid;
    invalid.error = "plan failed";
    auto invalidResult = lc32::mapDependencyLoadPlan(
        invalid, load,
        [](uint32_t, uint32_t, uint32_t) { return true; },
        [](uint32_t, const void*, std::size_t) { return true; });
    assert(!invalidResult.ok);
    assert(invalidResult.error == "plan failed");
    return 0;
}
