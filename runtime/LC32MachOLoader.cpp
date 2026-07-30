#include "LC32MachOLoader.hpp"

#include <algorithm>
#include <cstring>

namespace lc32 {
namespace {
constexpr uint32_t MH_MAGIC = 0xfeedfaceu;
constexpr uint32_t FAT_CIGAM = 0xbebafecau;
constexpr int32_t CPU_TYPE_ARM = 12;
constexpr int32_t CPU_SUBTYPE_ARM_V7 = 9;
constexpr int32_t CPU_SUBTYPE_ARM_V7S = 11;
constexpr uint32_t MH_EXECUTE = 0x2u;
constexpr uint32_t MH_DYLINKER = 0x7u;
constexpr uint32_t LC_SEGMENT = 0x1u;
constexpr uint32_t LC_UNIXTHREAD = 0x5u;
constexpr uint32_t LC_MAIN = 0x80000028u;

uint32_t be32(uint32_t v) {
    return ((v & 0x000000ffu) << 24) |
           ((v & 0x0000ff00u) << 8) |
           ((v & 0x00ff0000u) >> 8) |
           ((v & 0xff000000u) >> 24);
}

template <typename T>
bool readObject(const uint8_t* data, std::size_t size, std::size_t off, T& out) {
    if (off > size || sizeof(T) > size - off) return false;
    std::memcpy(&out, data + off, sizeof(T));
    return true;
}

#pragma pack(push, 1)
struct FatHeader { uint32_t magic, nfatArch; };
struct FatArch { int32_t cpuType, cpuSubtype; uint32_t offset, size, align; };
struct MachHeader { uint32_t magic; int32_t cpuType, cpuSubtype; uint32_t filetype, ncmds, sizeofcmds, flags; };
struct LoadCommand { uint32_t cmd, cmdsize; };
struct SegmentCommand {
    uint32_t cmd, cmdsize;
    char segname[16];
    uint32_t vmaddr, vmsize, fileoff, filesize;
    int32_t maxprot, initprot;
    uint32_t nsects, flags;
};
struct EntryPointCommand { uint32_t cmd, cmdsize; uint64_t entryoff, stacksize; };
#pragma pack(pop)

bool selectSlice(const uint8_t* data, std::size_t size, uint32_t& off, uint32_t& len, std::string& error) {
    uint32_t magic = 0;
    if (!readObject(data, size, 0, magic)) { error = "file too small"; return false; }
    if (magic == MH_MAGIC) { off = 0; len = static_cast<uint32_t>(size); return true; }
    if (magic != FAT_CIGAM) { error = "not a 32-bit Mach-O or fat Mach-O"; return false; }

    FatHeader fh{};
    readObject(data, size, 0, fh);
    const uint32_t count = be32(fh.nfatArch);
    int bestRank = -1;
    for (uint32_t i = 0; i < count; ++i) {
        FatArch a{};
        const std::size_t archOff = sizeof(FatHeader) + std::size_t(i) * sizeof(FatArch);
        if (!readObject(data, size, archOff, a)) { error = "truncated fat architecture table"; return false; }
        const int32_t cpu = static_cast<int32_t>(be32(static_cast<uint32_t>(a.cpuType)));
        const int32_t sub = static_cast<int32_t>(be32(static_cast<uint32_t>(a.cpuSubtype))) & 0x00ffffff;
        if (cpu != CPU_TYPE_ARM) continue;
        const int rank = sub == CPU_SUBTYPE_ARM_V7S ? 2 : sub == CPU_SUBTYPE_ARM_V7 ? 1 : 0;
        const uint32_t candidateOff = be32(a.offset), candidateLen = be32(a.size);
        if (candidateOff > size || candidateLen > size - candidateOff) { error = "fat slice exceeds file"; return false; }
        if (rank > bestRank) { bestRank = rank; off = candidateOff; len = candidateLen; }
    }
    if (bestRank < 0) { error = "no ARM slice"; return false; }
    return true;
}
} // namespace

MachOLoadResult loadArmv7MachO(const uint8_t* data,
                               std::size_t size,
                               const MapCallback& map,
                               const WriteCallback& write,
                               uint32_t slide) {
    MachOLoadResult result;
    if (!data || !map || !write) { result.error = "missing loader input or callbacks"; return result; }

    uint32_t sliceOff = 0, sliceLen = 0;
    if (!selectSlice(data, size, sliceOff, sliceLen, result.error)) return result;
    result.sliceOffset = sliceOff;
    result.sliceSize = sliceLen;

    MachHeader mh{};
    if (!readObject(data, size, sliceOff, mh)) { result.error = "truncated Mach header"; return result; }
    if (mh.magic != MH_MAGIC || mh.cpuType != CPU_TYPE_ARM) { result.error = "selected slice is not ARM Mach-O"; return result; }
    if (sizeof(MachHeader) + mh.sizeofcmds > sliceLen) { result.error = "load commands exceed slice"; return result; }

    std::size_t commandOff = sliceOff + sizeof(MachHeader);
    uint32_t textVM = 0;
    bool haveThreadEntry = false;
    for (uint32_t i = 0; i < mh.ncmds; ++i) {
        LoadCommand lc{};
        if (!readObject(data, size, commandOff, lc) || lc.cmdsize < sizeof(LoadCommand) || lc.cmdsize > size - commandOff) {
            result.error = "invalid load command";
            return result;
        }
        if (lc.cmd == LC_SEGMENT) {
            SegmentCommand seg{};
            if (lc.cmdsize < sizeof(seg) || !readObject(data, size, commandOff, seg)) { result.error = "truncated segment"; return result; }
            if (seg.fileoff > sliceLen || seg.filesize > sliceLen - seg.fileoff || seg.filesize > seg.vmsize) {
                result.error = "invalid segment bounds";
                return result;
            }
            LoadedSegment out;
            out.name.assign(seg.segname, std::find(seg.segname, seg.segname + 16, '\0'));
            out.vmaddr = seg.vmaddr + slide;
            out.vmsize = seg.vmsize;
            out.fileoff = seg.fileoff;
            out.filesize = seg.filesize;
            out.initprot = static_cast<uint32_t>(seg.initprot);
            result.segments.push_back(out);
            if (out.name == "__TEXT") textVM = out.vmaddr;
            if (seg.vmsize != 0 && out.name != "__PAGEZERO") {
                if (!map(out.vmaddr, out.vmsize, out.initprot)) { result.error = "map callback rejected segment"; return result; }
                if (out.filesize != 0 && !write(out.vmaddr, data + sliceOff + out.fileoff, out.filesize)) {
                    result.error = "write callback rejected segment";
                    return result;
                }
            }
        } else if (lc.cmd == LC_MAIN) {
            EntryPointCommand ep{};
            if (lc.cmdsize < sizeof(ep) || !readObject(data, size, commandOff, ep)) { result.error = "truncated LC_MAIN"; return result; }
            result.entryPoint = textVM + static_cast<uint32_t>(ep.entryoff);
            if (ep.stacksize) result.stackPointer = 0x80000000u;
        } else if (lc.cmd == LC_UNIXTHREAD) {
            // ARM_THREAD_STATE32 commonly starts after cmd/cmdsize/flavor/count.
            if (lc.cmdsize >= 16 + 17 * sizeof(uint32_t)) {
                uint32_t regs[17]{};
                std::memcpy(regs, data + commandOff + 16, sizeof(regs));
                result.stackPointer = regs[13] + slide;
                result.entryPoint = regs[15] + slide;
                result.thumb = (regs[16] & (1u << 5)) != 0 || (result.entryPoint & 1u) != 0;
                result.entryPoint &= ~1u;
                haveThreadEntry = true;
            }
        }
        commandOff += lc.cmdsize;
    }

    const bool requiresEntryPoint = mh.filetype == MH_EXECUTE || mh.filetype == MH_DYLINKER;
    if (requiresEntryPoint && result.entryPoint == 0) {
        result.error = "no LC_MAIN or usable LC_UNIXTHREAD entry";
        return result;
    }
    if (result.entryPoint != 0) {
        if (!haveThreadEntry) result.thumb = (result.entryPoint & 1u) != 0;
        result.entryPoint &= ~1u;
    }
    result.ok = true;
    return result;
}

} // namespace lc32
