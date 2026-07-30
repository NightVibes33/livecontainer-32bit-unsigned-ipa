#pragma once
#include "LC32MachOLoader.hpp"
#include "LC32ProcessStack.hpp"
#include <cstddef>
#include <cstdint>
#include <string>

namespace lc32 {
struct DyldHandoffSpec {
    const uint8_t* appImage = nullptr; std::size_t appSize = 0;
    const uint8_t* dyldImage = nullptr; std::size_t dyldSize = 0;
    std::string executablePath;
    ProcessStackSpec stack;
    uint32_t appSlide = 0x10000000u;
    uint32_t dyldSlide = 0x20000000u;
    uint32_t stackBase = 0x70000000u;
    uint32_t stackSize = 1024u * 1024u;
};
struct DyldHandoffResult {
    bool ok = false; std::string error;
    MachOLoadResult app; MachOLoadResult dyld;
    ProcessStackResult processStack;
    uint32_t pc = 0, sp = 0, mainMachHeader = 0;
    bool thumb = false;
};
DyldHandoffResult prepareDyldHandoff(const DyldHandoffSpec& spec,
                                     const MapCallback& map,
                                     const WriteCallback& write);
} // namespace lc32
