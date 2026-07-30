#pragma once

#include <array>
#include <cstddef>
#include <cstdint>
#include <functional>
#include <string>

namespace lc32 {

struct CPUState {
    std::array<uint32_t, 16> r{};
    uint32_t cpsr = 0x10;
    bool thumb() const { return (cpsr & (1u << 5)) != 0; }
    void setThumb(bool value) {
        if (value) cpsr |= (1u << 5); else cpsr &= ~(1u << 5);
    }
};

struct Memory {
    std::function<bool(uint32_t, void*, size_t)> read;
    std::function<bool(uint32_t, const void*, size_t)> write;
};

enum class StopReason {
    None,
    Halt,
    MemoryFault,
    UnsupportedInstruction,
    StepLimit,
};

struct Result {
    StopReason reason = StopReason::None;
    uint32_t pc = 0;
    uint32_t instruction = 0;
    uint64_t steps = 0;
    std::string detail;
};

class Interpreter {
public:
    Interpreter(CPUState& state, Memory memory);
    Result run(uint64_t maxSteps);
    Result step();

private:
    CPUState& s_;
    Memory m_;
    uint64_t steps_ = 0;

    bool conditionPassed(uint32_t cond) const;
    void setNZ(uint32_t value);
    void setNZCV(uint32_t value, bool carry, bool overflow);
    uint32_t readReg(unsigned index, uint32_t currentPC) const;
    bool read32(uint32_t address, uint32_t& value) const;
    bool read16(uint32_t address, uint16_t& value) const;
    bool write32(uint32_t address, uint32_t value) const;
    Result stepARM();
    Result stepThumb();
    Result unsupported(uint32_t pc, uint32_t instruction, const char* detail);
    Result fault(uint32_t pc, uint32_t instruction, const char* detail);
};

} // namespace lc32
