#pragma once

#include "LC32DarwinSyscalls.hpp"
#include "LC32Interpreter.hpp"
#include "LC32MachOLoader.hpp"

#include <cstddef>
#include <cstdint>
#include <string>
#include <vector>

namespace lc32 {

struct BootEvent {
    std::string stage;
    std::string detail;
    uint32_t pc = 0;
    uint32_t value = 0;
};

struct BootResult {
    bool loaded = false;
    bool exited = false;
    int exitCode = 0;
    Result cpuResult;
    MachOLoadResult image;
    std::vector<BootEvent> events;
};

class BootSession {
public:
    BootSession();

    BootResult boot(const uint8_t* image, std::size_t size, uint64_t maxSteps = 100000);
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
    void event(BootResult& out, std::string stage, std::string detail = {}, uint32_t value = 0);
    bool dispatchSupervisorCall(BootResult& out, const Result& cpuStop, DarwinSyscalls& syscalls);
};

} // namespace lc32
