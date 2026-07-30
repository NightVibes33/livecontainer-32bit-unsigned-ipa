#include "LC32BootSession.hpp"

#include <algorithm>
#include <cstring>
#include <sstream>

namespace lc32 {

BootSession::BootSession() = default;

bool BootSession::map(uint32_t address, uint32_t size, uint32_t protection) {
    if (size == 0) return true;
    const uint64_t end = uint64_t(address) + size;
    if (end > 0x100000000ull) return false;
    for (const Region& r : regions_) {
        const uint64_t rEnd = uint64_t(r.base) + r.size;
        if (!(end <= r.base || address >= rEnd)) return false;
    }
    Region r;
    r.base = address;
    r.size = size;
    r.protection = protection;
    r.bytes.resize(size);
    regions_.push_back(std::move(r));
    return true;
}

bool BootSession::read(uint32_t address, void* data, std::size_t size) const {
    const uint64_t end = uint64_t(address) + size;
    for (const Region& r : regions_) {
        const uint64_t rEnd = uint64_t(r.base) + r.size;
        if (address >= r.base && end <= rEnd) {
            std::memcpy(data, r.bytes.data() + (address - r.base), size);
            return true;
        }
    }
    return false;
}

bool BootSession::write(uint32_t address, const void* data, std::size_t size) {
    const uint64_t end = uint64_t(address) + size;
    for (Region& r : regions_) {
        const uint64_t rEnd = uint64_t(r.base) + r.size;
        if (address >= r.base && end <= rEnd) {
            std::memcpy(r.bytes.data() + (address - r.base), data, size);
            return true;
        }
    }
    return false;
}

void BootSession::event(BootResult& out, std::string stage, std::string detail, uint32_t value) {
    out.events.push_back({std::move(stage), std::move(detail), state_.r[15], value});
}

bool BootSession::dispatchSupervisorCall(BootResult& out, const Result& stop, DarwinSyscalls& syscalls) {
    uint32_t immediate = 0;
    uint32_t width = 0;
    if (!state_.thumb() && (stop.instruction & 0x0f000000u) == 0x0f000000u) {
        immediate = stop.instruction & 0x00ffffffu;
        width = 4;
    } else if (state_.thumb() && (stop.instruction & 0xff00u) == 0xdf00u) {
        immediate = stop.instruction & 0xffu;
        width = 2;
    } else {
        return false;
    }

    TrapResult trap = syscalls.dispatch(state_, immediate, state_.thumb());
    std::ostringstream detail;
    detail << (trap.trapClass == TrapClass::Mach ? "mach" : trap.trapClass == TrapClass::Unix ? "unix" : "unknown")
           << ':' << trap.number << ':' << trap.detail;
    event(out, trap.handled ? "syscall-handled" : "syscall-unsupported", detail.str(), trap.number);
    if (!trap.handled) {
        out.cpuResult = stop;
        out.cpuResult.detail = detail.str();
        return true;
    }
    state_.r[15] += width;
    if (trap.shouldStop) {
        out.exited = true;
        out.exitCode = trap.returnValue;
        out.cpuResult = {StopReason::Halt, state_.r[15], stop.instruction, stop.steps, detail.str()};
        return true;
    }
    return true;
}

BootResult BootSession::boot(const uint8_t* image, std::size_t size, uint64_t maxSteps) {
    BootResult out;
    regions_.clear();
    state_ = {};
    event(out, "boot-start", "loading ARMv7 Mach-O");

    out.image = loadArmv7MachO(
        image,
        size,
        [this](uint32_t address, uint32_t bytes, uint32_t protection) { return map(address, bytes, protection); },
        [this](uint32_t address, const void* data, std::size_t bytes) { return write(address, data, bytes); });
    if (!out.image.ok) {
        event(out, "macho-load-failed", out.image.error);
        out.cpuResult = {StopReason::Halt, 0, 0, 0, out.image.error};
        return out;
    }

    out.loaded = true;
    state_.r[15] = out.image.entryPoint & ~1u;
    state_.setThumb(out.image.thumb || (out.image.entryPoint & 1u));
    if (out.image.stackPointer) {
        state_.r[13] = out.image.stackPointer;
    } else {
        constexpr uint32_t stackBase = 0x70000000u;
        constexpr uint32_t stackSize = 1024u * 1024u;
        if (!map(stackBase, stackSize, 3)) {
            out.cpuResult = {StopReason::MemoryFault, state_.r[15], 0, 0, "stack mapping failed"};
            event(out, "stack-map-failed");
            return out;
        }
        state_.r[13] = stackBase + stackSize - 16;
    }
    event(out, "macho-loaded", "entry point ready", state_.r[15]);

    Memory memory{
        [this](uint32_t address, void* data, size_t bytes) { return read(address, data, bytes); },
        [this](uint32_t address, const void* data, size_t bytes) { return write(address, data, bytes); }};
    SyscallMemory syscallMemory{memory.read, memory.write};
    Interpreter interpreter(state_, memory);
    DarwinSyscalls syscalls(syscallMemory);

    for (uint64_t i = 0; i < maxSteps; ++i) {
        Result step = interpreter.step();
        if (step.reason == StopReason::None) continue;
        if (step.reason == StopReason::UnsupportedInstruction && dispatchSupervisorCall(out, step, syscalls)) {
            if (out.exited || !out.cpuResult.detail.empty()) return out;
            continue;
        }
        out.cpuResult = step;
        event(out, "cpu-stop", step.detail, step.instruction);
        return out;
    }

    out.cpuResult = {StopReason::StepLimit, state_.r[15], 0, maxSteps, "boot step limit"};
    event(out, "step-limit");
    return out;
}

} // namespace lc32
