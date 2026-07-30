#include "../LC32DyldImageSet.hpp"

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
struct EntryPointCommand { uint32_t cmd, cmdsize; uint64_t entryoff, stacksize; };
struct DylibCommand { uint32_t cmd, cmdsize, nameOffset, timestamp, currentVersion, compatibilityVersion; };
#pragma pack(pop)

std::vector<uint8_t> makeImage(uint32_t filetype,
                               uint32_t vmaddr,
                               const std::string& dependency,
                               bool withEntry) {
    const uint32_t dependencyCommandSize = dependency.empty()
        ? 0u
        : static_cast<uint32_t>((sizeof(DylibCommand) + dependency.size() + 1u + 3u) & ~3u);
    const uint32_t ncmds = 1u + (withEntry ? 1u : 0u) + (dependency.empty() ? 0u : 1u);
    const uint32_t sizeofcmds = static_cast<uint32_t>(sizeof(SegmentCommand)) +
                                (withEntry ? static_cast<uint32_t>(sizeof(EntryPointCommand)) : 0u) +
                                dependencyCommandSize;
    std::vector<uint8_t> file(0x300, 0);
    MachHeader header{0xfeedfaceu, 12, 9, filetype, ncmds, sizeofcmds, 0};
    std::memcpy(file.data(), &header, sizeof(header));

    size_t offset = sizeof(header);
    SegmentCommand segment{};
    segment.cmd = 1;
    segment.cmdsize = sizeof(segment);
    std::memcpy(segment.segname, "__TEXT", 6);
    segment.vmaddr = vmaddr;
    segment.vmsize = 0x1000;
    segment.fileoff = 0;
    segment.filesize = 0x300;
    segment.initprot = 5;
    std::memcpy(file.data() + offset, &segment, sizeof(segment));
    offset += sizeof(segment);

    if (withEntry) {
        EntryPointCommand entry{0x80000028u, sizeof(EntryPointCommand), 0x100u, 0};
        std::memcpy(file.data() + offset, &entry, sizeof(entry));
        offset += sizeof(entry);
    }

    if (!dependency.empty()) {
        DylibCommand command{0xcu, dependencyCommandSize, sizeof(DylibCommand), 0, 0, 0};
        std::memcpy(file.data() + offset, &command, sizeof(command));
        std::memcpy(file.data() + offset + sizeof(command), dependency.c_str(), dependency.size() + 1u);
    }
    return file;
}
}

int main() {
    auto app = makeImage(2u, 0x1000u, "/usr/lib/libA.dylib", true);
    auto dyld = makeImage(7u, 0x2000u, {}, true);
    auto dylib = makeImage(6u, 0x3000u, {}, false);

    lc32::DyldImageSetSpec spec;
    spec.handoff.appImage = app.data();
    spec.handoff.appSize = app.size();
    spec.handoff.dyldImage = dyld.data();
    spec.handoff.dyldSize = dyld.size();
    spec.handoff.executablePath = "/Applications/Game.app/Game";
    spec.handoff.appSlide = 0x10000000u;
    spec.handoff.dyldSlide = 0x20000000u;
    spec.pathContext.guestRoot = "/root";
    spec.exists = [](const std::string& hostPath) {
        return hostPath == "/root/usr/lib/libA.dylib";
    };
    spec.loadImage = [&](const std::string& hostPath, lc32::DependencyImage& image, std::string&) {
        if (hostPath != "/root/usr/lib/libA.dylib") return false;
        image.guestPath = "/usr/lib/libA.dylib";
        image.bytes = dylib;
        return true;
    };

    std::map<uint32_t, std::vector<uint8_t>> regions;
    auto result = lc32::prepareDyldImageSet(
        spec,
        [&](uint32_t address, uint32_t size, uint32_t) {
            if (regions.count(address)) return false;
            regions[address] = std::vector<uint8_t>(size);
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

    assert(result.ok);
    assert(result.plan.ok);
    assert(result.plan.nodes.size() == 2);
    assert(result.handoff.ok);
    assert(result.mappedDependencies.ok);
    assert(result.mappedDependencies.images.size() == 1);
    assert(result.mappedDependencies.images[0].guestPath == "/usr/lib/libA.dylib");
    assert(result.mappedDependencies.images[0].slide == 0x31000000u);
    assert(result.mappedDependencies.images[0].load.segments[0].vmaddr == 0x31003000u);
    assert(regions.count(0x10001000u) == 1);
    assert(regions.count(0x20002000u) == 1);
    assert(regions.count(0x31003000u) == 1);
    return 0;
}
