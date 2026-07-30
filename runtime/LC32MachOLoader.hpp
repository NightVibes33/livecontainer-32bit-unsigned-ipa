#pragma once

#include <cstddef>
#include <cstdint>
#include <functional>
#include <string>
#include <vector>

namespace lc32 {

struct LoadedSegment {
    std::string name;
    uint32_t vmaddr = 0;
    uint32_t vmsize = 0;
    uint32_t fileoff = 0;
    uint32_t filesize = 0;
    uint32_t initprot = 0;
};

struct MachOLoadResult {
    bool ok = false;
    std::string error;
    uint32_t sliceOffset = 0;
    uint32_t sliceSize = 0;
    uint32_t entryPoint = 0;
    uint32_t stackPointer = 0;
    bool thumb = false;
    std::vector<LoadedSegment> segments;
};

using MapCallback = std::function<bool(uint32_t address, uint32_t size, uint32_t protection)>;
using WriteCallback = std::function<bool(uint32_t address, const void* data, std::size_t size)>;

MachOLoadResult loadArmv7MachO(const uint8_t* data,
                               std::size_t size,
                               const MapCallback& map,
                               const WriteCallback& write,
                               uint32_t slide = 0);

} // namespace lc32
