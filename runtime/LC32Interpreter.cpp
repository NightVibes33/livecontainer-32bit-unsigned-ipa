#include "LC32Interpreter.hpp"

#include <cstring>
#include <sstream>

namespace lc32 {
namespace {
constexpr uint32_t N = 1u << 31;
constexpr uint32_t Z = 1u << 30;
constexpr uint32_t C = 1u << 29;
constexpr uint32_t V = 1u << 28;

static uint32_t ror(uint32_t value, unsigned amount) {
    amount &= 31;
    return amount ? (value >> amount) | (value << (32 - amount)) : value;
}
}

Interpreter::Interpreter(CPUState& state, Memory memory) : s_(state), m_(std::move(memory)) {}

bool Interpreter::read32(uint32_t a, uint32_t& v) const { return m_.read && m_.read(a, &v, sizeof(v)); }
bool Interpreter::read16(uint32_t a, uint16_t& v) const { return m_.read && m_.read(a, &v, sizeof(v)); }
bool Interpreter::write32(uint32_t a, uint32_t v) const { return m_.write && m_.write(a, &v, sizeof(v)); }

uint32_t Interpreter::readReg(unsigned i, uint32_t pc) const { return i == 15 ? pc + (s_.thumb() ? 4 : 8) : s_.r[i]; }

void Interpreter::setNZ(uint32_t value) {
    s_.cpsr = (s_.cpsr & ~(N | Z)) | (value & N) | (value == 0 ? Z : 0);
}

void Interpreter::setNZCV(uint32_t value, bool carry, bool overflow) {
    setNZ(value);
    s_.cpsr = (s_.cpsr & ~(C | V)) | (carry ? C : 0) | (overflow ? V : 0);
}

bool Interpreter::conditionPassed(uint32_t c) const {
    const bool n = s_.cpsr & N, z = s_.cpsr & Z, carry = s_.cpsr & C, v = s_.cpsr & V;
    switch (c) {
        case 0x0: return z; case 0x1: return !z; case 0x2: return carry; case 0x3: return !carry;
        case 0x4: return n; case 0x5: return !n; case 0x6: return v; case 0x7: return !v;
        case 0x8: return carry && !z; case 0x9: return !carry || z; case 0xA: return n == v;
        case 0xB: return n != v; case 0xC: return !z && n == v; case 0xD: return z || n != v;
        case 0xE: return true; default: return false;
    }
}

Result Interpreter::unsupported(uint32_t pc, uint32_t insn, const char* detail) {
    return {StopReason::UnsupportedInstruction, pc, insn, steps_, detail};
}
Result Interpreter::fault(uint32_t pc, uint32_t insn, const char* detail) {
    return {StopReason::MemoryFault, pc, insn, steps_, detail};
}

Result Interpreter::stepARM() {
    const uint32_t pc = s_.r[15];
    uint32_t insn = 0;
    if (!read32(pc, insn)) return fault(pc, 0, "ARM instruction fetch");
    ++steps_;
    if (!conditionPassed(insn >> 28)) { s_.r[15] = pc + 4; return {}; }

    // BX/BLX register.
    if ((insn & 0x0ffffff0u) == 0x012fff10u || (insn & 0x0ffffff0u) == 0x012fff30u) {
        const uint32_t target = readReg(insn & 0xf, pc);
        if ((insn & 0x20u) != 0) s_.r[14] = pc + 4;
        s_.setThumb(target & 1u);
        s_.r[15] = target & ~1u;
        return {};
    }
    // B/BL immediate.
    if ((insn & 0x0e000000u) == 0x0a000000u) {
        int32_t off = static_cast<int32_t>((insn & 0x00ffffffu) << 8) >> 6;
        if (insn & (1u << 24)) s_.r[14] = pc + 4;
        s_.r[15] = pc + 8 + off;
        return {};
    }
    // MOVW/MOVT.
    if ((insn & 0x0fb00000u) == 0x03000000u || (insn & 0x0fb00000u) == 0x03400000u) {
        const unsigned rd = (insn >> 12) & 0xf;
        const uint32_t imm = ((insn >> 4) & 0xf000u) | (insn & 0xfffu);
        if ((insn & 0x00400000u) != 0) s_.r[rd] = (s_.r[rd] & 0xffffu) | (imm << 16);
        else s_.r[rd] = imm;
        s_.r[15] = pc + 4;
        return {};
    }
    // LDR/STR immediate, word only.
    if ((insn & 0x0c000000u) == 0x04000000u && !(insn & (1u << 22))) {
        const bool pre = insn & (1u << 24), up = insn & (1u << 23), wb = insn & (1u << 21), load = insn & (1u << 20);
        const unsigned rn = (insn >> 16) & 0xf, rd = (insn >> 12) & 0xf;
        const uint32_t base = readReg(rn, pc), off = insn & 0xfffu;
        const uint32_t adjusted = up ? base + off : base - off;
        const uint32_t address = pre ? adjusted : base;
        if (load) {
            uint32_t value = 0; if (!read32(address, value)) return fault(pc, insn, "LDR");
            if (rd == 15) { s_.setThumb(value & 1u); s_.r[15] = value & ~1u; }
            else { s_.r[rd] = value; s_.r[15] = pc + 4; }
        } else {
            if (!write32(address, readReg(rd, pc))) return fault(pc, insn, "STR");
            s_.r[15] = pc + 4;
        }
        if (!pre || wb) s_.r[rn] = adjusted;
        return {};
    }
    // Data processing, immediate or register with immediate shift.
    if ((insn & 0x0c000000u) == 0) {
        const bool immediate = insn & (1u << 25), setFlags = insn & (1u << 20);
        const unsigned opcode = (insn >> 21) & 0xf, rn = (insn >> 16) & 0xf, rd = (insn >> 12) & 0xf;
        uint32_t op2 = 0;
        if (immediate) op2 = ror(insn & 0xffu, ((insn >> 8) & 0xf) * 2);
        else {
            if (insn & (1u << 4)) return unsupported(pc, insn, "register-controlled shift");
            op2 = readReg(insn & 0xf, pc);
            const unsigned type = (insn >> 5) & 3, amount = (insn >> 7) & 0x1f;
            if (amount) {
                if (type == 0) op2 <<= amount;
                else if (type == 1) op2 >>= amount;
                else if (type == 2) op2 = static_cast<uint32_t>(static_cast<int32_t>(op2) >> amount);
                else op2 = ror(op2, amount);
            }
        }
        const uint32_t a = readReg(rn, pc);
        uint32_t result = 0; bool write = true, carry = false, overflow = false;
        switch (opcode) {
            case 0x0: result = a & op2; break; case 0x1: result = a ^ op2; break;
            case 0x2: result = a - op2; carry = a >= op2; overflow = ((a ^ op2) & (a ^ result) & N); break;
            case 0x4: { uint64_t sum = uint64_t(a) + op2; result = uint32_t(sum); carry = sum >> 32; overflow = (~(a ^ op2) & (a ^ result) & N); break; }
            case 0x8: result = a & op2; write = false; break;
            case 0xA: result = a - op2; carry = a >= op2; overflow = ((a ^ op2) & (a ^ result) & N); write = false; break;
            case 0xC: result = a | op2; break; case 0xD: result = op2; break;
            case 0xE: result = a & ~op2; break; case 0xF: result = ~op2; break;
            default: return unsupported(pc, insn, "ARM data-processing opcode");
        }
        if (setFlags || !write) setNZCV(result, carry, overflow);
        if (write) {
            if (rd == 15) s_.r[15] = result & ~1u; else { s_.r[rd] = result; s_.r[15] = pc + 4; }
        } else s_.r[15] = pc + 4;
        return {};
    }
    return unsupported(pc, insn, "ARM opcode");
}

Result Interpreter::stepThumb() {
    const uint32_t pc = s_.r[15];
    uint16_t insn = 0;
    if (!read16(pc, insn)) return fault(pc, 0, "Thumb instruction fetch");
    ++steps_;
    // MOVS/CMP/ADDS/SUBS immediate.
    if ((insn & 0xe000u) == 0x2000u) {
        const unsigned op = (insn >> 11) & 3, rd = (insn >> 8) & 7; const uint32_t imm = insn & 0xff;
        uint32_t result = 0;
        if (op == 0) { result = imm; s_.r[rd] = result; setNZ(result); }
        else if (op == 1) { result = s_.r[rd] - imm; setNZCV(result, s_.r[rd] >= imm, false); }
        else if (op == 2) { uint64_t sum = uint64_t(s_.r[rd]) + imm; result = uint32_t(sum); s_.r[rd] = result; setNZCV(result, sum >> 32, false); }
        else { result = s_.r[rd] - imm; s_.r[rd] = result; setNZCV(result, true, false); }
        s_.r[15] = pc + 2; return {};
    }
    // Unconditional branch.
    if ((insn & 0xf800u) == 0xe000u) {
        int32_t off = static_cast<int32_t>((insn & 0x7ffu) << 21) >> 20;
        s_.r[15] = pc + 4 + off; return {};
    }
    // BX/BLX register.
    if ((insn & 0xff00u) == 0x4700u) {
        const unsigned rm = (insn >> 3) & 0xf; const uint32_t target = readReg(rm, pc);
        if (insn & 0x80) s_.r[14] = (pc + 2) | 1u;
        s_.setThumb(target & 1u); s_.r[15] = target & ~1u; return {};
    }
    // LDR literal.
    if ((insn & 0xf800u) == 0x4800u) {
        const unsigned rd = (insn >> 8) & 7; uint32_t value = 0;
        const uint32_t address = ((pc + 4) & ~3u) + ((insn & 0xffu) << 2);
        if (!read32(address, value)) return fault(pc, insn, "Thumb LDR literal");
        s_.r[rd] = value; s_.r[15] = pc + 2; return {};
    }
    return unsupported(pc, insn, "Thumb opcode");
}

Result Interpreter::step() { return s_.thumb() ? stepThumb() : stepARM(); }

Result Interpreter::run(uint64_t maxSteps) {
    for (uint64_t i = 0; i < maxSteps; ++i) {
        Result r = step();
        if (r.reason != StopReason::None) return r;
    }
    return {StopReason::StepLimit, s_.r[15], 0, steps_, "step limit"};
}

} // namespace lc32
