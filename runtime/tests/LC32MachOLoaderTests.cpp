#include "../LC32MachOLoader.hpp"

#include <cassert>
#include <cstdint>
#include <cstring>
#include <map>
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
#pragma pack(pop)

std::vector<uint8_t> makeThinMachO() {
    MachHeader mh{0xfeedfaceu, 12, 9, 2, 2,
                  static_cast<uint32_t>(sizeof(SegmentCommand) + sizeof(EntryPointCommand)), 0};
    SegmentCommand seg{};
    seg.cmd = 1;
    seg.cmdsize = sizeof(seg);
    std::memcpy(seg.segname, "__TEXT", 6);
    seg.vmaddr = 0x1000;
    seg.vmsize = 0x1000;
    seg.fileoff = 0;
    seg.filesize = 0x100;
    seg.initprot = 5;
    EntryPointCommand ep{0x80000028u, sizeof(EntryPointCommand), 0x40, 0};

    std::vector<uint8_t> file(0x100, 0);
    std::memcpy(file.data(), &mh, sizeof(mh));
    std::memcpy(file.data() + sizeof(mh), &seg, sizeof(seg));
    std::memcpy(file.data() + sizeof(mh) + sizeof(seg), &ep, sizeof(ep));
    return file;
}
}

int main() {
    auto file = makeThinMachO();
    std::map<uint32_t, std::vector<uint8_t>> mapped;
    auto result = lc32::loadArmv7MachO(
        file.data(), file.size(),
        [&](uint32_t address, uint32_t size, uint32_t) {
            mapped[address] = std::vector<uint8_t>(size);
            return true;
        },
        [&](uint32_t address, const void* data, std::size_t size) {
            auto it = mapped.find(address);
            if (it == mapped.end() || size > it->second.size()) return false;
            std::memcpy(it->second.data(), data, size);
            return true;
        });

    assert(result.ok);
    assert(result.entryPoint == 0x1040);
    assert(result.segments.size() == 1);
    assert(result.segments[0].name == "__TEXT");
    assert(mapped.count(0x1000) == 1);

    file[0] = 0;
    auto bad = lc32::loadArmv7MachO(file.data(), file.size(),
                                    [](uint32_t, uint32_t, uint32_t) { return true; },
                                    [](uint32_t, const void*, std::size_t) { return true; });
    assert(!bad.ok);
    return 0;
}
