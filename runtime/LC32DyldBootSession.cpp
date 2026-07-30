#include "LC32DyldBootSession.hpp"

#include <cstring>
#include <sstream>
#include <utility>

namespace lc32 {

bool DyldBootSession::map(uint32_t address, uint32_t size, uint32_t protection) {
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

bool DyldBootSession::read(uint32_t address, void* data, std::size_t size) const {
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

bool DyldBootSession::write(uint32_t address, const void* data, std::size_t size) {
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

void DyldBootSession::event(DyldBootResult& out, std::string stage, std::string detail, uint32_t value) {
    out.events.push_back({std::move(stage), std::move(detail), state_.r[15], value});
}

bool DyldBootSession::dispatchSupervisorCall(DyldBootResult& out, const Result& stop, DarwinSyscalls& syscalls) {
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
    }
    return true;
}

DyldBootResult DyldBootSession::executePrepared(DyldBootResult out,
                                                 uint64_t maxSteps,
                                                 std::string syscallGuestRoot) {
    out.prepared = true;
    state_.r[15] = out.handoff.pc;
    state_.r[13] = out.handoff.sp;
    state_.r[0] = out.handoff.mainMachHeader;
    state_.setThumb(out.handoff.thumb);
    event(out, "dyld-handoff-ready", "entering guest dyld", out.handoff.mainMachHeader);

    Memory memory{
        [this](uint32_t address, void* data, size_t size) { return read(address, data, size); },
        [this](uint32_t address, const void* data, size_t size) { return write(address, data, size); }};
    DarwinSyscalls syscalls({memory.read, memory.write}, std::move(syscallGuestRoot));
    Interpreter interpreter(state_, memory);

    for (uint64_t i = 0; i < maxSteps; ++i) {
        Result step = interpreter.step();
        if (step.reason == StopReason::None) continue;
        if (step.reason == StopReason::UnsupportedInstruction && dispatchSupervisorCall(out, step, syscalls)) {
            if (out.exited || !out.cpuResult.detail.empty()) return out;
            continue;
        }
        out.cpuResult = step;
        event(out, "dyld-cpu-stop", step.detail, step.instruction);
        return out;
    }

    out.cpuResult = {StopReason::StepLimit, state_.r[15], 0, maxSteps, "dyld boot step limit"};
    event(out, "dyld-step-limit");
    return out;
}

DyldBootResult DyldBootSession::boot(const DyldHandoffSpec& spec, uint64_t maxSteps) {
    return bootImpl(spec, nullptr, nullptr, maxSteps);
}

DyldBootResult DyldBootSession::bootAudited(const DyldHandoffSpec& spec,
                                            GuestPathContext context,
                                            const GuestPathExists& exists,
                                            uint64_t maxSteps) {
    return bootImpl(spec, &context, &exists, maxSteps);
}

DyldBootResult DyldBootSession::bootImageSet(const DyldImageSetSpec& spec,
                                             uint64_t maxSteps) {
    DyldBootResult out;
    regions_.clear();
    state_ = {};
    event(out, "dyld-image-set-start", "planning and mapping guest dependency images");

    out.imageSet = prepareDyldImageSet(
        spec,
        [this](uint32_t address, uint32_t size, uint32_t protection) {
            return map(address, size, protection);
        },
        [this](uint32_t address, const void* data, std::size_t size) {
            return write(address, data, size);
        });
    if (!out.imageSet.ok) {
        out.cpuResult = {StopReason::Halt, 0, 0, 0, out.imageSet.error};
        event(out, "dyld-image-set-failed", out.imageSet.error);
        return out;
    }

    out.handoff = out.imageSet.handoff;
    if (!out.imageSet.plan.nodes.empty()) {
        out.dependencies = out.imageSet.plan.nodes.front().metadata;
    }
    for (const DependencyMappedImage& image : out.imageSet.mappedDependencies.images) {
        event(out, "dependency-image-mapped", image.guestPath, image.slide);
    }
    event(out,
          "dyld-image-set-ready",
          "mapped " + std::to_string(out.imageSet.mappedDependencies.images.size()) + " dependency images",
          static_cast<uint32_t>(out.imageSet.mappedDependencies.images.size()));
    return executePrepared(std::move(out), maxSteps, spec.pathContext.guestRoot);
}

DyldBootResult DyldBootSession::bootImpl(const DyldHandoffSpec& spec,
                                         const GuestPathContext* auditContext,
                                         const GuestPathExists* exists,
                                         uint64_t maxSteps) {
    DyldBootResult out;
    regions_.clear();
    state_ = {};
    event(out, "dyld-boot-start", "preparing app and dyld images");

    out.dependencies = parseArmv7MachODependencies(spec.appImage, spec.appSize);
    if (!out.dependencies.ok) {
        out.cpuResult = {StopReason::Halt, 0, 0, 0, out.dependencies.error};
        event(out, "dependency-parse-failed", out.dependencies.error);
        return out;
    }

    if (auditContext && exists) {
        GuestPathContext context = *auditContext;
        if (context.executablePath.empty()) context.executablePath = spec.executablePath;
        if (context.loaderPath.empty()) context.loaderPath = spec.executablePath;
        for (const std::string& rpath : out.dependencies.rpaths) context.rpaths.push_back(rpath);
        out.dependencyAudit = auditGuestDependencies(out.dependencies, context, *exists);
        event(out,
              out.dependencyAudit.ok ? "dependency-audit-passed" : "dependency-audit-failed",
              out.dependencyAudit.error,
              static_cast<uint32_t>(out.dependencyAudit.missingRequired.size()));
        if (!out.dependencyAudit.ok) {
            out.cpuResult = {StopReason::Halt, 0, 0, 0, out.dependencyAudit.error};
            return out;
        }
    }

    out.handoff = prepareDyldHandoff(
        spec,
        [this](uint32_t address, uint32_t size, uint32_t protection) { return map(address, size, protection); },
        [this](uint32_t address, const void* data, std::size_t size) { return write(address, data, size); });
    if (!out.handoff.ok) {
        out.cpuResult = {StopReason::Halt, 0, 0, 0, out.handoff.error};
        event(out, "dyld-handoff-failed", out.handoff.error);
        return out;
    }

    return executePrepared(std::move(out), maxSteps);
}

} // namespace lc32
