#include "../LC32DyldBootSession.hpp"

#include <cassert>
#include <cstdint>
#include <cstring>
#include <string>
#include <vector>

namespace {
#pragma pack(push, 1)
struct MachHeader {
    uint32_t magic;
    int32_t cpuType, cpuSubtype;
    uint32_t filetype, ncmds, sizeofcmds, flags;
};
struct SegmentCommand {
    uint32_t cmd, cmdsize;
    char segname[16];
    uint32_t vmaddr, vmsize, fileoff, filesize;
    int32_t maxprot, initprot;
    uint32_t nsects, flags;
};
struct EntryPointCommand {
    uint32_t cmd, cmdsize;
    uint64_t entryoff, stacksize;
};
struct DylibCommand {
    uint32_t cmd, cmdsize, nameOffset, timestamp, currentVersion, compatibilityVersion;
};
#pragma pack(pop)

std::vector<uint8_t> makeImage(uint32_t filetype,
                               uint32_t vmaddr,
                               const std::string& dependency,
                               const std::vector<uint32_t>& code,
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

    std::size_t offset = sizeof(header);
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

    for (std::size_t i = 0; i < code.size(); ++i) {
        std::memcpy(file.data() + 0x100u + i * sizeof(uint32_t), &code[i], sizeof(uint32_t));
    }
    return file;
}
} // namespace

int main() {
    auto app = makeImage(2u, 0x1000u, "/usr/lib/libA.dylib", {0xe1a00000u}, true);
    auto dyld = makeImage(7u, 0x2000u, {}, {
        0xe3500000u, // cmp r0,#0
        0x0a000003u, // beq failure
        0xe3a0c014u, // mov r12,#20 getpid
        0xef000080u, // svc #0x80
        0xe3a0c001u, // mov r12,#1 exit
        0xe3a00000u, // mov r0,#0
        0xef000080u, // svc #0x80
        0xe3a0c001u, // failure: mov r12,#1
        0xe3a00009u, // mov r0,#9
        0xef000080u  // svc #0x80
    }, true);
    auto dylib = makeImage(6u, 0x3000u, {}, {}, false);

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
    spec.loadImage = [&](const std::string& hostPath,
                         lc32::DependencyImage& image,
                         std::string& error) {
        if (hostPath != "/root/usr/lib/libA.dylib") {
            error = "unexpected host dependency path";
            return false;
        }
        image.guestPath = "/usr/lib/libA.dylib";
        image.bytes = dylib;
        return true;
    };

    lc32::DyldBootSession session;
    auto result = session.bootImageSet(spec, 128);

    assert(result.prepared);
    assert(result.imageSet.ok);
    assert(result.imageSet.plan.nodes.size() == 2);
    assert(result.imageSet.mappedDependencies.images.size() == 1);
    assert(result.imageSet.mappedDependencies.images[0].guestPath == "/usr/lib/libA.dylib");
    assert(result.imageSet.mappedDependencies.images[0].slide == 0x31000000u);
    assert(result.imageSet.mappedDependencies.images[0].load.ok);
    assert(result.imageSet.mappedDependencies.images[0].load.segments[0].vmaddr == 0x31003000u);
    assert(result.handoff.mainMachHeader == 0x10001000u);
    assert(result.exited);
    assert(result.exitCode == 0);

    bool sawMapped = false;
    bool sawSetReady = false;
    bool sawHandoff = false;
    for (const lc32::DyldBootEvent& event : result.events) {
        sawMapped |= event.stage == "dependency-image-mapped" &&
                     event.detail == "/usr/lib/libA.dylib" &&
                     event.value == 0x31000000u;
        sawSetReady |= event.stage == "dyld-image-set-ready" && event.value == 1u;
        sawHandoff |= event.stage == "dyld-handoff-ready";
    }
    assert(sawMapped);
    assert(sawSetReady);
    assert(sawHandoff);
    return 0;
}
