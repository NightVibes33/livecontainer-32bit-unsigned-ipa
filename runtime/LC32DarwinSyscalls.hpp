#pragma once

#include "LC32Interpreter.hpp"

#include <cstddef>
#include <cstdint>
#include <functional>
#include <string>

namespace lc32 {

struct SyscallMemory {
    std::function<bool(uint32_t, void*, size_t)> read;
    std::function<bool(uint32_t, const void*, size_t)> write;
};

enum class TrapClass : uint8_t {
    Unix,
    Mach,
    Unknown,
};

struct TrapResult {
    bool handled = false;
    bool shouldStop = false;
    int32_t returnValue = -1;
    int32_t errorNumber = 0;
    TrapClass trapClass = TrapClass::Unknown;
    uint32_t number = 0;
    std::string detail;
};

class DarwinSyscalls {
public:
    explicit DarwinSyscalls(SyscallMemory memory);

    TrapResult dispatch(CPUState& state, uint32_t svcImmediate, bool thumbMode);
    bool readCString(uint32_t address, std::string& out, size_t limit = 4096) const;

private:
    TrapResult dispatchUnix(CPUState& state, uint32_t number);
    TrapResult dispatchMach(CPUState& state, uint32_t number);
    void writeReturn(CPUState& state, const TrapResult& result) const;

    SyscallMemory memory_;
};

} // namespace lc32
