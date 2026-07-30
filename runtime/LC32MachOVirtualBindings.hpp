#pragma once

#include "LC32VirtualRuntime.hpp"

#include <algorithm>
#include <cstddef>
#include <cstdint>
#include <string>
#include <vector>

namespace lc32 {

struct MachOVirtualBinding {
    std::string symbol;
    uint32_t slotAddress = 0;
    VirtualRuntimeSymbol target;
};

struct MachOVirtualBindingResult {
    bool ok = false;
    std::string error;
    std::vector<MachOVirtualBinding> bindings;
    std::vector<std::string> unsupportedSymbols;
};

namespace macho_virtual_binding_detail {

constexpr uint32_t kMHMagic = 0xFEEDFACEu;
constexpr uint32_t kMHCigam = 0xCEFAEDFEu;
constexpr uint32_t kFatMagic = 0xCAFEBABEu;
constexpr uint32_t kFatCigam = 0xBEBAFECAu;
constexpr uint32_t kCPUTypeARM = 12u;
constexpr uint32_t kLCSegment = 0x1u;
constexpr uint32_t kLCSymtab = 0x2u;
constexpr uint32_t kLCDysymtab = 0xBu;
constexpr uint32_t kSNonLazySymbolPointers = 0x6u;
constexpr uint32_t kSLazySymbolPointers = 0x7u;
constexpr uint32_t kIndirectSymbolLocal = 0x80000000u;
constexpr uint32_t kIndirectSymbolAbsolute = 0x40000000u;
constexpr uint8_t kNStab = 0xE0u;
constexpr uint8_t kNType = 0x0Eu;
constexpr uint8_t kNUndefined = 0x00u;
constexpr uint8_t kNExternal = 0x01u;

inline bool rangeValid(std::size_t offset, std::size_t length, std::size_t limit) {
    return offset <= limit && length <= limit - offset;
}

inline uint16_t read16(const uint8_t* data, bool little) {
    if (little) return uint16_t(data[0]) | (uint16_t(data[1]) << 8);
    return (uint16_t(data[0]) << 8) | uint16_t(data[1]);
}

inline uint32_t read32(const uint8_t* data, bool little) {
    if (little) {
        return uint32_t(data[0]) | (uint32_t(data[1]) << 8) |
               (uint32_t(data[2]) << 16) | (uint32_t(data[3]) << 24);
    }
    return (uint32_t(data[0]) << 24) | (uint32_t(data[1]) << 16) |
           (uint32_t(data[2]) << 8) | uint32_t(data[3]);
}

inline std::string readCString(const uint8_t* data,
                               std::size_t size,
                               std::size_t offset,
                               std::size_t end) {
    if (offset >= size || offset >= end) return {};
    const std::size_t limit = std::min(size, end);
    std::size_t cursor = offset;
    while (cursor < limit && data[cursor] != 0) ++cursor;
    if (cursor == limit) return {};
    return std::string(reinterpret_cast<const char*>(data + offset), cursor - offset);
}

struct PointerSection {
    uint32_t address = 0;
    uint32_t size = 0;
    uint32_t indirectIndex = 0;
};

inline MachOVirtualBindingResult parseThin(const uint8_t* data,
                                           std::size_t size,
                                           std::size_t base,
                                           std::size_t sliceSize,
                                           uint32_t slide) {
    MachOVirtualBindingResult out;
    if (!rangeValid(base, 28, size) || sliceSize < 28 || !rangeValid(base, sliceSize, size)) {
        out.error = "truncated Mach-O header";
        return out;
    }

    const uint32_t rawMagic = read32(data + base, true);
    bool little = true;
    if (rawMagic == kMHMagic) little = true;
    else if (rawMagic == kMHCigam) little = false;
    else {
        out.error = "unsupported thin Mach-O magic";
        return out;
    }
    if (read32(data + base + 4, little) != kCPUTypeARM) {
        out.error = "Mach-O slice is not ARMv7";
        return out;
    }

    const uint32_t ncmds = read32(data + base + 16, little);
    const uint32_t sizeofcmds = read32(data + base + 20, little);
    const std::size_t commandsStart = base + 28;
    const std::size_t commandsEnd = commandsStart + sizeofcmds;
    const std::size_t sliceEnd = base + sliceSize;
    if (commandsEnd < commandsStart || commandsEnd > sliceEnd || commandsEnd > size) {
        out.error = "truncated Mach-O load commands";
        return out;
    }

    uint32_t symoff = 0;
    uint32_t nsyms = 0;
    uint32_t stroff = 0;
    uint32_t strsize = 0;
    uint32_t indirectsymoff = 0;
    uint32_t nindirectsyms = 0;
    bool foundSymtab = false;
    bool foundDysymtab = false;
    std::vector<PointerSection> pointerSections;

    std::size_t cursor = commandsStart;
    for (uint32_t commandIndex = 0; commandIndex < ncmds; ++commandIndex) {
        if (!rangeValid(cursor, 8, commandsEnd)) {
            out.error = "invalid Mach-O load-command table";
            return out;
        }
        const uint32_t cmd = read32(data + cursor, little);
        const uint32_t cmdsize = read32(data + cursor + 4, little);
        if (cmdsize < 8 || !rangeValid(cursor, cmdsize, commandsEnd)) {
            out.error = "invalid Mach-O load-command size";
            return out;
        }

        if (cmd == kLCSymtab) {
            if (cmdsize < 24) {
                out.error = "truncated LC_SYMTAB command";
                return out;
            }
            symoff = read32(data + cursor + 8, little);
            nsyms = read32(data + cursor + 12, little);
            stroff = read32(data + cursor + 16, little);
            strsize = read32(data + cursor + 20, little);
            foundSymtab = true;
        } else if (cmd == kLCDysymtab) {
            if (cmdsize < 64) {
                out.error = "truncated LC_DYSYMTAB command";
                return out;
            }
            indirectsymoff = read32(data + cursor + 56, little);
            nindirectsyms = read32(data + cursor + 60, little);
            foundDysymtab = true;
        } else if (cmd == kLCSegment) {
            if (cmdsize < 56) {
                out.error = "truncated LC_SEGMENT command";
                return out;
            }
            const uint32_t nsects = read32(data + cursor + 48, little);
            const std::size_t required = 56u + static_cast<std::size_t>(nsects) * 68u;
            if (required > cmdsize) {
                out.error = "truncated Mach-O section table";
                return out;
            }
            for (uint32_t sectionIndex = 0; sectionIndex < nsects; ++sectionIndex) {
                const std::size_t section = cursor + 56u + static_cast<std::size_t>(sectionIndex) * 68u;
                const uint32_t flags = read32(data + section + 56, little);
                const uint32_t type = flags & 0xFFu;
                if (type != kSNonLazySymbolPointers && type != kSLazySymbolPointers) continue;
                PointerSection pointerSection;
                pointerSection.address = read32(data + section + 32, little);
                pointerSection.size = read32(data + section + 36, little);
                pointerSection.indirectIndex = read32(data + section + 60, little);
                pointerSections.push_back(pointerSection);
            }
        }
        cursor += cmdsize;
    }

    if (pointerSections.empty()) {
        out.ok = true;
        return out;
    }
    if (!foundSymtab || !foundDysymtab) {
        out.error = "symbol-pointer sections require LC_SYMTAB and LC_DYSYMTAB";
        return out;
    }
    if (nsyms > 1000000u || nindirectsyms > 4000000u) {
        out.error = "Mach-O symbol table exceeds parser limits";
        return out;
    }

    const std::size_t symBase = base + symoff;
    const std::size_t strBase = base + stroff;
    const std::size_t indirectBase = base + indirectsymoff;
    const std::size_t symBytes = static_cast<std::size_t>(nsyms) * 12u;
    const std::size_t indirectBytes = static_cast<std::size_t>(nindirectsyms) * 4u;
    if (!rangeValid(symBase, symBytes, sliceEnd) || !rangeValid(strBase, strsize, sliceEnd) ||
        !rangeValid(indirectBase, indirectBytes, sliceEnd) ||
        !rangeValid(symBase, symBytes, size) || !rangeValid(strBase, strsize, size) ||
        !rangeValid(indirectBase, indirectBytes, size)) {
        out.error = "Mach-O symbol, string, or indirect-symbol table is truncated";
        return out;
    }

    for (const PointerSection& section : pointerSections) {
        if ((section.size & 3u) != 0) {
            out.error = "symbol-pointer section size is not pointer-aligned";
            return out;
        }
        const uint32_t pointerCount = section.size / 4u;
        if (section.indirectIndex > nindirectsyms ||
            pointerCount > nindirectsyms - section.indirectIndex) {
            out.error = "symbol-pointer section exceeds indirect-symbol table";
            return out;
        }
        for (uint32_t pointerIndex = 0; pointerIndex < pointerCount; ++pointerIndex) {
            const std::size_t indirectEntry = indirectBase +
                static_cast<std::size_t>(section.indirectIndex + pointerIndex) * 4u;
            const uint32_t symbolIndex = read32(data + indirectEntry, little);
            if ((symbolIndex & (kIndirectSymbolLocal | kIndirectSymbolAbsolute)) != 0) continue;
            if (symbolIndex >= nsyms) {
                out.error = "indirect symbol index exceeds symbol table";
                return out;
            }

            const std::size_t symbolEntry = symBase + static_cast<std::size_t>(symbolIndex) * 12u;
            const uint32_t stringOffset = read32(data + symbolEntry, little);
            const uint8_t type = data[symbolEntry + 4];
            const uint16_t description = read16(data + symbolEntry + 6, little);
            (void)description;
            if ((type & kNStab) != 0 || (type & kNType) != kNUndefined ||
                (type & kNExternal) == 0 || stringOffset == 0 || stringOffset >= strsize) {
                continue;
            }
            const std::string symbol = readCString(data, size, strBase + stringOffset, strBase + strsize);
            if (symbol.empty()) continue;
            const VirtualRuntimeSymbol target = resolveVirtualRuntimeSymbol(symbol);
            if (target.imageKind != VirtualRuntimeImageKind::Unsupported && target.executable) {
                out.bindings.push_back({
                    symbol,
                    static_cast<uint32_t>(section.address + slide + pointerIndex * 4u),
                    target,
                });
            } else {
                out.unsupportedSymbols.push_back(symbol);
            }
        }
    }

    std::sort(out.unsupportedSymbols.begin(), out.unsupportedSymbols.end());
    out.unsupportedSymbols.erase(
        std::unique(out.unsupportedSymbols.begin(), out.unsupportedSymbols.end()),
        out.unsupportedSymbols.end());
    out.ok = true;
    return out;
}

} // namespace macho_virtual_binding_detail

inline MachOVirtualBindingResult collectArmv7VirtualBindings(const uint8_t* data,
                                                             std::size_t size,
                                                             uint32_t slide = 0) {
    using namespace macho_virtual_binding_detail;
    MachOVirtualBindingResult out;
    if (!data || size < 4) {
        out.error = "empty Mach-O image";
        return out;
    }

    const uint32_t magicLE = read32(data, true);
    if (magicLE == kMHMagic || magicLE == kMHCigam) {
        return parseThin(data, size, 0, size, slide);
    }

    const uint32_t magicBE = read32(data, false);
    bool fatLittle = false;
    if (magicBE == kFatMagic) fatLittle = false;
    else if (magicBE == kFatCigam) fatLittle = true;
    else {
        out.error = "unsupported Mach-O magic";
        return out;
    }
    if (!rangeValid(0, 8, size)) {
        out.error = "truncated fat Mach-O header";
        return out;
    }
    const uint32_t count = read32(data + 4, fatLittle);
    if (count > 256u || !rangeValid(8, static_cast<std::size_t>(count) * 20u, size)) {
        out.error = "invalid fat Mach-O slice table";
        return out;
    }
    for (uint32_t index = 0; index < count; ++index) {
        const std::size_t entry = 8u + static_cast<std::size_t>(index) * 20u;
        const uint32_t cpuType = read32(data + entry, fatLittle);
        const uint32_t offset = read32(data + entry + 8, fatLittle);
        const uint32_t sliceSize = read32(data + entry + 12, fatLittle);
        if (cpuType != kCPUTypeARM) continue;
        return parseThin(data, size, offset, sliceSize, slide);
    }
    out.error = "fat Mach-O has no ARMv7 slice";
    return out;
}

} // namespace lc32
