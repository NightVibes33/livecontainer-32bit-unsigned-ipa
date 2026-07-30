#include "LC32DarwinSyscalls.hpp"

#include <cerrno>
#include <chrono>
#include <climits>
#include <cstdlib>
#include <cstring>
#include <fcntl.h>
#include <string>
#include <unistd.h>
#include <utility>
#include <vector>

namespace lc32 {
namespace {
constexpr uint32_t CPSR_C = 1u << 29;
constexpr uint32_t kUnixTrapBase = 0x80000000u;
constexpr uint32_t kMachTrapBase = 0xffffffe0u;
constexpr uint32_t kGuestOpenAccessMode = 0x3u;
constexpr uint32_t kGuestOpenCreate = 0x0200u;
constexpr uint32_t kGuestOpenTruncate = 0x0400u;
constexpr size_t kMaximumTransfer = 16u * 1024u * 1024u;

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
} // namespace

DarwinSyscalls::DarwinSyscalls(SyscallMemory memory, std::string guestRoot)
    : memory_(std::move(memory)), guestRoot_(std::move(guestRoot)) {}

DarwinSyscalls::~DarwinSyscalls() {
    for (const auto& entry : guestFiles_) {
        ::close(entry.second);
    }
}

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

bool DarwinSyscalls::resolveGuestPath(const std::string& guestPath,
                                      std::string& hostPath,
                                      int& errorNumber) const {
    hostPath.clear();
    errorNumber = 0;
    if (guestRoot_.empty()) {
        errorNumber = ENOENT;
        return false;
    }
    if (guestPath.empty() || guestPath.front() != '/') {
        errorNumber = EINVAL;
        return false;
    }

    std::vector<std::string> components;
    std::size_t start = 1;
    while (start <= guestPath.size()) {
        const std::size_t end = guestPath.find('/', start);
        const std::string component = guestPath.substr(
            start, end == std::string::npos ? std::string::npos : end - start);
        if (component.empty() || component == ".") {
            // Ignore repeated separators and current-directory components.
        } else if (component == "..") {
            if (components.empty()) {
                errorNumber = EACCES;
                return false;
            }
            components.pop_back();
        } else {
            components.push_back(component);
        }
        if (end == std::string::npos) break;
        start = end + 1;
    }

    std::string candidate = guestRoot_;
    while (candidate.size() > 1 && candidate.back() == '/') candidate.pop_back();
    for (const std::string& component : components) {
        candidate.push_back('/');
        candidate += component;
    }

    char resolvedRoot[PATH_MAX]{};
    char resolvedTarget[PATH_MAX]{};
    if (!::realpath(guestRoot_.c_str(), resolvedRoot)) {
        errorNumber = errno ? errno : ENOENT;
        return false;
    }
    if (!::realpath(candidate.c_str(), resolvedTarget)) {
        errorNumber = errno ? errno : ENOENT;
        return false;
    }

    std::string root(resolvedRoot);
    std::string target(resolvedTarget);
    while (root.size() > 1 && root.back() == '/') root.pop_back();
    const bool withinRoot = target == root ||
                            (target.size() > root.size() &&
                             target.compare(0, root.size(), root) == 0 &&
                             target[root.size()] == '/');
    if (!withinRoot) {
        errorNumber = EACCES;
        return false;
    }

    hostPath = std::move(target);
    return true;
}

int DarwinSyscalls::allocateGuestFd(int hostFd) {
    for (int attempts = 0; attempts < INT_MAX - 3; ++attempts) {
        if (nextGuestFd_ < 3) nextGuestFd_ = 3;
        const int candidate = nextGuestFd_++;
        if (guestFiles_.find(candidate) == guestFiles_.end()) {
            guestFiles_.emplace(candidate, hostFd);
            return candidate;
        }
    }
    return -1;
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
    const uint32_t rawNumber = state.r[12];
    TrapResult result;

    // Negative ARM Mach trap numbers occupy 0xffffffe0..0xffffffff and must
    // be classified before the generic high-bit BSD form.
    if (rawNumber >= kMachTrapBase) {
        result = dispatchMach(state, static_cast<uint32_t>(-static_cast<int32_t>(rawNumber)));
        result.trapClass = TrapClass::Mach;
    } else if ((rawNumber & kUnixTrapBase) != 0) {
        result = dispatchUnix(state, rawNumber & ~kUnixTrapBase);
        result.trapClass = TrapClass::Unix;
    } else if (svcImmediate == 0x80u) {
        // Darwin ARM EABI: svc #0x80 selects a BSD syscall whose number is in r12.
        result = dispatchUnix(state, rawNumber);
        result.trapClass = TrapClass::Unix;
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
        case 1: {
            TrapResult r = ok(number, static_cast<int32_t>(state.r[0]), "exit");
            r.shouldStop = true;
            return r;
        }
        case 3: {
            const int guestFd = static_cast<int>(state.r[0]);
            const uint32_t bufferAddress = state.r[1];
            const size_t count = state.r[2];
            if (count > kMaximumTransfer) return fail(number, EINVAL, "read length");
            const auto file = guestFiles_.find(guestFd);
            if (file == guestFiles_.end()) return fail(number, EBADF, "read guest fd");
            std::vector<uint8_t> buffer(count);
            const ssize_t bytesRead = ::read(file->second, buffer.data(), count);
            if (bytesRead < 0) return fail(number, errno, "read host call");
            if (bytesRead != 0 &&
                (!memory_.write || !memory_.write(bufferAddress, buffer.data(), static_cast<size_t>(bytesRead)))) {
                return fail(number, EFAULT, "read guest write");
            }
            return ok(number, static_cast<int32_t>(bytesRead), "read");
        }
        case 4: {
            const int fd = static_cast<int>(state.r[0]);
            const uint32_t bufferAddress = state.r[1];
            const size_t count = state.r[2];
            if (count > kMaximumTransfer) return fail(number, EINVAL, "write length");
            std::string buffer(count, '\0');
            if (count && (!memory_.read || !memory_.read(bufferAddress, buffer.data(), count))) {
                return fail(number, EFAULT, "write guest read");
            }
            const ssize_t written = ::write(fd, buffer.data(), count);
            if (written < 0) return fail(number, errno, "write host call");
            return ok(number, static_cast<int32_t>(written), "write");
        }
        case 5: {
            std::string path;
            if (!readCString(state.r[0], path)) return fail(number, EFAULT, "open path");
            const uint32_t flags = state.r[1];
            if ((flags & kGuestOpenAccessMode) != 0 ||
                (flags & (kGuestOpenCreate | kGuestOpenTruncate)) != 0) {
                return fail(number, EROFS, "open read-only guest root");
            }
            std::string hostPath;
            int pathError = 0;
            if (!resolveGuestPath(path, hostPath, pathError)) {
                return fail(number, pathError ? pathError : ENOENT, "open guest path");
            }
            int hostFlags = O_RDONLY;
#ifdef O_CLOEXEC
            hostFlags |= O_CLOEXEC;
#endif
            const int hostFd = ::open(hostPath.c_str(), hostFlags);
            if (hostFd < 0) return fail(number, errno, "open host call");
            const int guestFd = allocateGuestFd(hostFd);
            if (guestFd < 0) {
                ::close(hostFd);
                return fail(number, EMFILE, "open guest fd table");
            }
            return ok(number, guestFd, "open");
        }
        case 6: {
            const int guestFd = static_cast<int>(state.r[0]);
            const auto file = guestFiles_.find(guestFd);
            if (file == guestFiles_.end()) {
                if (guestFd >= 0 && guestFd <= 2) return ok(number, 0, "close standard fd virtualized");
                return fail(number, EBADF, "close guest fd");
            }
            const int hostFd = file->second;
            guestFiles_.erase(file);
            if (::close(hostFd) != 0) return fail(number, errno, "close host call");
            return ok(number, 0, "close");
        }
        case 20: return ok(number, static_cast<int32_t>(::getpid()), "getpid");
        case 24: return ok(number, static_cast<int32_t>(::getuid()), "getuid");
        case 25: return ok(number, static_cast<int32_t>(::geteuid()), "geteuid");
        case 47: return ok(number, static_cast<int32_t>(::getgid()), "getgid");
        case 43: return ok(number, static_cast<int32_t>(::getegid()), "getegid");
        case 116: {
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
        case 26: return ok(number, 0x100, "mach_reply_port placeholder");
        case 27: return ok(number, 0x101, "thread_self_trap placeholder");
        case 28: return ok(number, 0x102, "task_self_trap placeholder");
        case 29: return ok(number, 0x103, "host_self_trap placeholder");
        default: {
            TrapResult r;
            r.number = number;
            r.detail = "unsupported Mach trap";
            return r;
        }
    }
}

} // namespace lc32
