#pragma once

#include <cstdint>
#include <functional>
#include <string>
#include <utility>
#include <vector>

namespace lc32 {

struct ProcessStackSpec {
    std::vector<std::string> argv;
    std::vector<std::string> envp;
    std::vector<std::pair<std::string, std::string>> apple;
};

struct ProcessStackResult {
    bool ok = false;
    std::string error;
    uint32_t stackPointer = 0;
    uint32_t argcAddress = 0;
    uint32_t argvAddress = 0;
    uint32_t envpAddress = 0;
    uint32_t appleAddress = 0;
};

using StackWrite = std::function<bool(uint32_t address, const void* data, size_t size)>;

ProcessStackResult buildDarwinProcessStack(uint32_t stackBase,
                                           uint32_t stackSize,
                                           const ProcessStackSpec& spec,
                                           const StackWrite& write);

} // namespace lc32
