#include "LC32DarwinSyscalls.hpp"

#include <cerrno>
#include <chrono>
#include <cstring>
#include <unistd.h>

namespace lc32 {
namespace {
constexpr uint32_t CPSR_C = 1u << 29;
constexpr uint32_t kUnixTrapBase = 0x80000000u;
constexpr uint32_t kMachTrapBase = 0xffffffe0u;

TrapResult ok(uint32_t number, int32_t value, const char* detail) {
    TrapResult r;
    r.handled = true;
    r.returnValue = value;
    r.number = number;
    r.detail = detail;
    return r;
}

TrapResult fail(uint32_t number, int errorNumber, const char* detail) {
    TrapResult r;
    r.handled = true;
    r.returnValue = -1;
    r.errorNumber = errorNumber;
    r.number = number;
    r.detail = detail;
    return r;
}
}

DarwinSyscalls::DarwinSyscalls(SyscallMemory memory) : memory_(std::move(memory)) {}

bool DarwinSyscalls::readCString(uint32_t address, std::string& out, size_t limit) const {
    out.clear();
    if (!memory_.read || limit == 0) return false;
    for (size_t i = 0; i < limit; ++i) {
        char c = 0;
        if (!memory_.read(address + static_cast<uint32_t>(i), &c, 1)) return false;
        if (c == '\0') return true;
        out.push_back(c);
    }
    return false;
}

void DarwinSyscalls::writeReturn(CPUState& state, const TrapResult& result) const {
    if (result.errorNumber) {
        state.r[0] = static_cast<uint32_t>(result.errorNumber);
        state.cpsr |= CPSR_C;
    } else {
        state.r[0] = static_cast<uint32_t>(result.returnValue);
        state.cpsr &= ~CPSR_C;
    }
}

TrapResult DarwinSyscalls::dispatch(CPUState& state, uint32_t svcImmediate, bool) {
    uint32_t rawNumber = state.r[12];
    TrapResult result;

    if ((rawNumber & kUnixTrapBase) != 0) {
        result = dispatchUnix(state, rawNumber & ~kUnixTrapBase);
        result.trapClass = TrapClass::Unix;
    } else if (rawNumber >= kMachTrapBase) {
        result = dispatchMach(state, static_cast<uint32_t>(-static_cast<int32_t>(rawNumber)));
        result.trapClass = TrapClass::Mach;
    } else if (svcImmediate != 0) {
        result = dispatchUnix(state, svcImmediate);
        result.trapClass = TrapClass::Unix;
    } else {
        result.handled = false;
        result.number = rawNumber;
        result.detail = "unclassified SVC";
    }

    if (result.handled) writeReturn(state, result);
    return result;
}

TrapResult DarwinSyscalls::dispatchUnix(CPUState& state, uint32_t number) {
    switch (number) {
        case 1: { // exit
            TrapResult r = ok(number, static_cast<int32_t>(state.r[0]), "exit");
            r.shouldStop = true;
            return r;
        }
        case 20: // getpid
            return ok(number, static_cast<int32_t>(::getpid()), "getpid");
        case 24: // getuid
            return ok(number, static_cast<int32_t>(::getuid()), "getuid");
        case 25: // geteuid
            return ok(number, static_cast<int32_t>(::geteuid()), "geteuid");
        case 47: // getgid
            return ok(number, static_cast<int32_t>(::getgid()), "getgid");
        case 43: // getegid
            return ok(number, static_cast<int32_t>(::getegid()), "getegid");
        case 116: { // gettimeofday
            const uint32_t tvAddress = state.r[0];
            if (!tvAddress) return ok(number, 0, "gettimeofday(null)");
            struct GuestTimeval { int32_t sec; int32_t usec; } guest{};
            const auto now = std::chrono::system_clock::now().time_since_epoch();
            const auto micros = std::chrono::duration_cast<std::chrono::microseconds>(now).count();
            guest.sec = static_cast<int32_t>(micros / 1000000);
            guest.usec = static_cast<int32_t>(micros % 1000000);
            if (!memory_.write || !memory_.write(tvAddress, &guest, sizeof(guest))) {
                return fail(number, EFAULT, "gettimeofday guest write");
            }
            return ok(number, 0, "gettimeofday");
        }
        case 4: { // write
            const int fd = static_cast<int>(state.r[0]);
            const uint32_t bufferAddress = state.r[1];
            const size_t count = state.r[2];
            if (count > 16 * 1024 * 1024) return fail(number, EINVAL, "write length");
            std::string buffer(count, '\0');
            if (count && (!memory_.read || !memory_.read(bufferAddress, buffer.data(), count))) {
                return fail(number, EFAULT, "write guest read");
            }
            const ssize_t written = ::write(fd, buffer.data(), count);
            if (written < 0) return fail(number, errno, "write host call");
            return ok(number, static_cast<int32_t>(written), "write");
        }
        case 5: { // open
            std::string path;
            if (!readCString(state.r[0], path)) return fail(number, EFAULT, "open path");
            // Host filesystem access remains deliberately disabled until the guest-root path mapper exists.
            return fail(number, ENOENT, "open blocked pending guest-root mapper");
        }
        case 6: // close
            return ok(number, 0, "close virtualized");
        default: {
            TrapResult r;
            r.number = number;
            r.detail = "unsupported BSD syscall";
            return r;
        }
    }
}

TrapResult DarwinSyscalls::dispatchMach(CPUState&, uint32_t number) {
    switch (number) {
        case 26: // mach_reply_port
            return ok(number, 0x100, "mach_reply_port placeholder");
        case 27: // thread_self_trap
            return ok(number, 0x101, "thread_self_trap placeholder");
        case 28: // task_self_trap
            return ok(number, 0x102, "task_self_trap placeholder");
        case 29: // host_self_trap
            return ok(number, 0x103, "host_self_trap placeholder");
        default: {
            TrapResult r;
            r.number = number;
            r.detail = "unsupported Mach trap";
            return r;
        }
    }
}

} // namespace lc32
