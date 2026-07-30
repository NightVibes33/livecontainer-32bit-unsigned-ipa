#pragma once

#include "LC32Interpreter.hpp"

#include <cstddef>
#include <cstdint>
#include <dirent.h>
#include <deque>
#include <functional>
#include <string>
#include <unordered_map>
#include <vector>

namespace lc32 {

struct SyscallMemory {
    std::function<bool(uint32_t, void*, size_t)> read;
    std::function<bool(uint32_t, const void*, size_t)> write;
    std::function<bool(uint32_t, uint32_t, uint32_t)> map;
    std::function<bool(uint32_t, uint32_t)> unmap;
    std::function<bool(uint32_t, uint32_t, uint32_t)> protect;
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
    explicit DarwinSyscalls(SyscallMemory memory, std::string guestRoot = {});
    ~DarwinSyscalls();

    DarwinSyscalls(const DarwinSyscalls&) = delete;
    DarwinSyscalls& operator=(const DarwinSyscalls&) = delete;

    TrapResult dispatch(CPUState& state, uint32_t svcImmediate, bool thumbMode);
    bool readCString(uint32_t address, std::string& out, size_t limit = 4096) const;

private:
    struct GuestFile {
        int hostFd = -1;
        uint32_t openFlags = 0;
        uint32_t descriptorFlags = 0;
        DIR* directoryStream = nullptr;
    };

    struct MachPort {
        std::deque<std::vector<uint8_t>> messages;
        uint32_t receiveRefs = 0;
        uint32_t sendRefs = 0;
        uint32_t sendOnceRefs = 0;
        bool immortal = false;
    };

    struct NotifyRegistration {
        std::string name;
        uint64_t nameId = 0;
        uint64_t state = 0;
        bool pending = false;
        bool suspended = false;
    };

    TrapResult dispatchUnix(CPUState& state, uint32_t number);
    TrapResult dispatchMach(CPUState& state, uint32_t number);
    void writeReturn(CPUState& state, const TrapResult& result) const;
    bool resolveGuestPath(const std::string& guestPath,
                          std::string& hostPath,
                          int& errorNumber) const;
    bool resolveGuestPathNoFollow(const std::string& guestPath,
                                   std::string& hostPath,
                                   int& errorNumber) const;
    int allocateGuestFd(int hostFd,
                        uint32_t openFlags,
                        uint32_t descriptorFlags,
                        DIR* directoryStream = nullptr);

    SyscallMemory memory_;
    std::string guestRoot_;
    std::unordered_map<int, GuestFile> guestFiles_;
    std::unordered_map<uint32_t, MachPort> machPorts_;
    std::unordered_map<int32_t, NotifyRegistration> notifyRegistrations_;
    std::unordered_map<std::string, uint64_t> notifyNameIds_;
    uint64_t nextNotifyNameId_ = 1u;
    uint32_t nextMachPort_ = 0x200u;
    int nextGuestFd_ = 3;
    uint32_t nextMmapAddress_ = 0x50000000u;
};

} // namespace lc32
