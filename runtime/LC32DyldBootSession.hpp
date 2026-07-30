#pragma once

#include "LC32DarwinSyscalls.hpp"
#include "LC32DependencyAudit.hpp"
#include "LC32DyldHandoff.hpp"
#include "LC32DyldImageSet.hpp"
#include "LC32Interpreter.hpp"
#include "LC32MachODependencies.hpp"

#include <cstddef>
#include <cstdint>
#include <string>
#include <vector>

namespace lc32 {

struct DyldBootEvent {
    std::string stage;
    std::string detail;
    uint32_t pc = 0;
    uint32_t value = 0;
};

struct DyldBootResult {
    bool prepared = false;
    bool exited = false;
    int exitCode = 0;
    DyldHandoffResult handoff;
    DyldImageSetResult imageSet;
    MachODependencyResult dependencies;
    DependencyAuditResult dependencyAudit;
    Result cpuResult;
    std::vector<DyldBootEvent> events;
};

class DyldBootSession {
public:
    DyldBootResult boot(const DyldHandoffSpec& spec, uint64_t maxSteps = 100000);
    DyldBootResult bootAudited(const DyldHandoffSpec& spec,
                               GuestPathContext context,
                               const GuestPathExists& exists,
                               uint64_t maxSteps = 100000);
    DyldBootResult bootImageSet(const DyldImageSetSpec& spec,
                                uint64_t maxSteps = 100000);
    CPUState& state() { return state_; }

private:
    struct Region {
        uint32_t base = 0;
        uint32_t size = 0;
        uint32_t protection = 0;
        std::vector<uint8_t> bytes;
    };

    CPUState state_{};
    std::vector<Region> regions_;

    bool map(uint32_t address, uint32_t size, uint32_t protection);
    bool unmap(uint32_t address, uint32_t size);
    bool protect(uint32_t address, uint32_t size, uint32_t protection);
    bool read(uint32_t address, void* data, std::size_t size) const;
    bool write(uint32_t address, const void* data, std::size_t size);
    void event(DyldBootResult& out, std::string stage, std::string detail = {}, uint32_t value = 0);
    bool dispatchSupervisorCall(DyldBootResult& out, const Result& stop, DarwinSyscalls& syscalls);
    DyldBootResult executePrepared(DyldBootResult out,
                                   uint64_t maxSteps,
                                   std::string syscallGuestRoot = {});
    DyldBootResult bootImpl(const DyldHandoffSpec& spec,
                            const GuestPathContext* auditContext,
                            const GuestPathExists* exists,
                            uint64_t maxSteps);
};

} // namespace lc32
