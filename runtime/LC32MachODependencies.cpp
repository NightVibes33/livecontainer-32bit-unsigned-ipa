#include "LC32MachODependencies.hpp"

#include <cstring>

namespace lc32 {
namespace {
constexpr uint32_t MH_MAGIC = 0xfeedfaceu;
constexpr uint32_t FAT_MAGIC = 0xcafebabeu;
constexpr uint32_t CPU_TYPE_ARM = 12u;
constexpr uint32_t LC_LOAD_DYLIB = 0xcu;
constexpr uint32_t LC_LOAD_WEAK_DYLIB = 0x80000018u;
constexpr uint32_t LC_REEXPORT_DYLIB = 0x8000001fu;
constexpr uint32_t LC_LOAD_UPWARD_DYLIB = 0x80000023u;
constexpr uint32_t LC_LOAD_DYLINKER = 0xeu;
constexpr uint32_t LC_RPATH = 0x8000001cu;

uint32_t read32le(const uint8_t* p) {
    return uint32_t(p[0]) | (uint32_t(p[1]) << 8) | (uint32_t(p[2]) << 16) | (uint32_t(p[3]) << 24);
}
uint32_t read32be(const uint8_t* p) {
    return uint32_t(p[3]) | (uint32_t(p[2]) << 8) | (uint32_t(p[1]) << 16) | (uint32_t(p[0]) << 24);
}
bool readCStringInCommand(const uint8_t* cmd, uint32_t cmdSize, uint32_t offset, std::string& out) {
    if (offset >= cmdSize) return false;
    const char* start = reinterpret_cast<const char*>(cmd + offset);
    const size_t max = cmdSize - offset;
    const void* end = std::memchr(start, '\0', max);
    if (!end) return false;
    out.assign(start, static_cast<const char*>(end));
    return true;
}
}

MachODependencyResult parseArmv7MachODependencies(const uint8_t* data, std::size_t size) {
    MachODependencyResult out;
    if (!data || size < 28) { out.error = "image too small"; return out; }

    const uint8_t* image = data;
    size_t imageSize = size;
    const uint32_t first = read32le(data);
    if (first == FAT_MAGIC) {
        if (size < 8) { out.error = "truncated fat header"; return out; }
        const uint32_t count = read32be(data + 4);
        if (count > 64 || size < 8ull + 20ull * count) { out.error = "invalid fat arch table"; return out; }
        bool found = false;
        for (uint32_t i = 0; i < count; ++i) {
            const uint8_t* arch = data + 8 + 20 * i;
            if (read32be(arch) != CPU_TYPE_ARM) continue;
            const uint32_t off = read32be(arch + 8);
            const uint32_t len = read32be(arch + 12);
            if (uint64_t(off) + len > size || len < 28) { out.error = "fat ARM slice out of bounds"; return out; }
            image = data + off;
            imageSize = len;
            found = true;
            break;
        }
        if (!found) { out.error = "no ARM slice"; return out; }
    }

    if (imageSize < 28 || read32le(image) != MH_MAGIC || read32le(image + 4) != CPU_TYPE_ARM) {
        out.error = "not a 32-bit ARM Mach-O";
        return out;
    }
    const uint32_t ncmds = read32le(image + 16);
    const uint32_t sizeofcmds = read32le(image + 20);
    if (ncmds > 4096 || uint64_t(28) + sizeofcmds > imageSize) { out.error = "invalid load commands"; return out; }

    size_t cursor = 28;
    for (uint32_t i = 0; i < ncmds; ++i) {
        if (cursor + 8 > imageSize) { out.error = "truncated load command"; return out; }
        const uint8_t* cmd = image + cursor;
        const uint32_t type = read32le(cmd);
        const uint32_t cmdSize = read32le(cmd + 4);
        if (cmdSize < 8 || cursor + cmdSize > imageSize) { out.error = "invalid load command size"; return out; }

        if (type == LC_LOAD_DYLIB || type == LC_LOAD_WEAK_DYLIB || type == LC_REEXPORT_DYLIB || type == LC_LOAD_UPWARD_DYLIB) {
            if (cmdSize < 24) { out.error = "short dylib command"; return out; }
            MachODependency dep;
            dep.kind = type == LC_LOAD_WEAK_DYLIB ? DependencyKind::Weak :
                       type == LC_REEXPORT_DYLIB ? DependencyKind::Reexport :
                       type == LC_LOAD_UPWARD_DYLIB ? DependencyKind::Upward : DependencyKind::Load;
            if (!readCStringInCommand(cmd, cmdSize, read32le(cmd + 8), dep.path)) { out.error = "invalid dylib path"; return out; }
            dep.currentVersion = read32le(cmd + 16);
            dep.compatibilityVersion = read32le(cmd + 20);
            out.dependencies.push_back(std::move(dep));
        } else if (type == LC_LOAD_DYLINKER || type == LC_RPATH) {
            if (cmdSize < 12) { out.error = "short string command"; return out; }
            std::string value;
            if (!readCStringInCommand(cmd, cmdSize, read32le(cmd + 8), value)) { out.error = "invalid command string"; return out; }
            if (type == LC_LOAD_DYLINKER) out.dyldPath = std::move(value);
            else out.rpaths.push_back(std::move(value));
        }
        cursor += cmdSize;
    }

    out.ok = true;
    return out;
}

} // namespace lc32
