#include "../LC32Interpreter.hpp"

#include <cassert>
#include <cstdint>
#include <cstring>
#include <vector>

using namespace lc32;

static void put32(std::vector<uint8_t>& m, uint32_t a, uint32_t v) { std::memcpy(m.data() + a, &v, 4); }
static void put16(std::vector<uint8_t>& m, uint32_t a, uint16_t v) { std::memcpy(m.data() + a, &v, 2); }

int main() {
    std::vector<uint8_t> bytes(0x1000);
    Memory memory{
        [&](uint32_t a, void* out, size_t n) { if (uint64_t(a) + n > bytes.size()) return false; std::memcpy(out, bytes.data() + a, n); return true; },
        [&](uint32_t a, const void* in, size_t n) { if (uint64_t(a) + n > bytes.size()) return false; std::memcpy(bytes.data() + a, in, n); return true; }
    };

    // ARM: mov r0,#1; add r1,r0,#2; str r1,[r2]; ldr r3,[r2]; b .
    put32(bytes, 0x100, 0xE3A00001);
    put32(bytes, 0x104, 0xE2801002);
    put32(bytes, 0x108, 0xE5821000);
    put32(bytes, 0x10C, 0xE5923000);
    put32(bytes, 0x110, 0xEAFFFFFE);
    CPUState arm{}; arm.r[15] = 0x100; arm.r[2] = 0x300;
    Interpreter armCpu(arm, memory);
    for (int i = 0; i < 4; ++i) assert(armCpu.step().reason == StopReason::None);
    assert(arm.r[0] == 1 && arm.r[1] == 3 && arm.r[3] == 3);

    // Thumb: movs r0,#5; adds r0,#2; bx r1.
    put16(bytes, 0x200, 0x2005);
    put16(bytes, 0x202, 0x3002);
    put16(bytes, 0x204, 0x4708);
    CPUState thumb{}; thumb.setThumb(true); thumb.r[15] = 0x200; thumb.r[1] = 0x101;
    Interpreter thumbCpu(thumb, memory);
    assert(thumbCpu.step().reason == StopReason::None);
    assert(thumbCpu.step().reason == StopReason::None);
    assert(thumb.r[0] == 7);
    assert(thumbCpu.step().reason == StopReason::None);
    assert(thumb.thumb() && thumb.r[15] == 0x100);

    // Unsupported opcode must be reported, never silently skipped.
    put32(bytes, 0x400, 0xEE000A10); // coprocessor/VFP class, not implemented yet.
    CPUState unsupported{}; unsupported.r[15] = 0x400;
    Interpreter unsupportedCpu(unsupported, memory);
    Result result = unsupportedCpu.step();
    assert(result.reason == StopReason::UnsupportedInstruction);
    assert(result.pc == 0x400);
    return 0;
}
