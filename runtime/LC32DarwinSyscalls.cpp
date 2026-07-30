#include "LC32DarwinSyscalls.hpp"

#include <cerrno>
#include <chrono>
#include <climits>
#include <cstdlib>
#include <cstring>
#include <fcntl.h>
#include <string>
#include <sys/stat.h>
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
constexpr uint32_t kGuestOpenCloseExec = 0x01000000u;

constexpr uint32_t kGuestFdCloseExec = 1u;
constexpr uint32_t kFcntlGetFd = 1u;
constexpr uint32_t kFcntlSetFd = 2u;
constexpr uint32_t kFcntlGetFl = 3u;

constexpr uint32_t kProtRead = 0x01u;
constexpr uint32_t kProtWrite = 0x02u;
constexpr uint32_t kProtExec = 0x04u;
constexpr uint32_t kMapShared = 0x0001u;
constexpr uint32_t kMapPrivate = 0x0002u;
constexpr uint32_t kMapFixed = 0x0010u;
constexpr uint32_t kMapJit = 0x0800u;
constexpr uint32_t kMapAnonymous = 0x1000u;
constexpr uint32_t kPageSize = 4096u;
constexpr uint32_t kMaximumMapping = 64u * 1024u * 1024u;
constexpr size_t kMaximumTransfer = 16u * 1024u * 1024u;
constexpr uint32_t kMsAsync = 0x0001u;
constexpr uint32_t kMsInvalidate = 0x0002u;
constexpr uint32_t kMsKillPages = 0x0004u;
constexpr uint32_t kMsDeactivate = 0x0008u;
constexpr uint32_t kMsSync = 0x0010u;
constexpr int kMaximumAdvice = 9;

#pragma pack(push, 4)
struct GuestTimespec32 {
    int32_t seconds = 0;
    int32_t nanoseconds = 0;
};

// XNU 2050 (iOS 6-era) user32_stat64. The kernel declaration is explicitly
// packed and aligned to four bytes for 32-bit clients.
struct GuestStat64 {
    int32_t device = 0;
    uint16_t mode = 0;
    uint16_t linkCount = 0;
    uint64_t inode = 0;
    uint32_t userId = 0;
    uint32_t groupId = 0;
    int32_t specialDevice = 0;
    GuestTimespec32 accessTime;
    GuestTimespec32 modificationTime;
    GuestTimespec32 statusChangeTime;
    GuestTimespec32 birthTime;
    int64_t size = 0;
    int64_t blocks = 0;
    int32_t blockSize = 0;
    uint32_t flags = 0;
    uint32_t generation = 0;
    uint32_t longSpare = 0;
    int64_t quadSpare[2]{};
};
#pragma pack(pop)

static_assert(sizeof(GuestTimespec32) == 8, "unexpected ARMv7 timespec layout");
static_assert(sizeof(GuestStat64) == 108, "unexpected iOS 6 user32_stat64 layout");

int32_t clampSigned32(int64_t value) {
    if (value > INT32_MAX) return INT32_MAX;
    if (value < INT32_MIN) return INT32_MIN;
    return static_cast<int32_t>(value);
}

GuestTimespec32 guestTimespec(int64_t seconds, int64_t nanoseconds) {
    GuestTimespec32 out;
    out.seconds = clampSigned32(seconds);
    out.nanoseconds = clampSigned32(nanoseconds);
    return out;
}

GuestStat64 guestStat64(const struct stat& host) {
    GuestStat64 out;
    out.device = static_cast<int32_t>(host.st_dev);
    out.mode = static_cast<uint16_t>(host.st_mode);
    const uint64_t links = static_cast<uint64_t>(host.st_nlink);
    out.linkCount = static_cast<uint16_t>(links > UINT16_MAX ? UINT16_MAX : links);
    out.inode = static_cast<uint64_t>(host.st_ino);
    out.userId = static_cast<uint32_t>(host.st_uid);
    out.groupId = static_cast<uint32_t>(host.st_gid);
    out.specialDevice = static_cast<int32_t>(host.st_rdev);
#if defined(__APPLE__)
    out.accessTime = guestTimespec(host.st_atimespec.tv_sec, host.st_atimespec.tv_nsec);
    out.modificationTime = guestTimespec(host.st_mtimespec.tv_sec, host.st_mtimespec.tv_nsec);
    out.statusChangeTime = guestTimespec(host.st_ctimespec.tv_sec, host.st_ctimespec.tv_nsec);
    out.birthTime = guestTimespec(host.st_birthtimespec.tv_sec, host.st_birthtimespec.tv_nsec);
    out.flags = static_cast<uint32_t>(host.st_flags);
    out.generation = static_cast<uint32_t>(host.st_gen);
#else
    out.accessTime = guestTimespec(host.st_atim.tv_sec, host.st_atim.tv_nsec);
    out.modificationTime = guestTimespec(host.st_mtim.tv_sec, host.st_mtim.tv_nsec);
    out.statusChangeTime = guestTimespec(host.st_ctim.tv_sec, host.st_ctim.tv_nsec);
    out.birthTime = {};
#endif
    out.size = static_cast<int64_t>(host.st_size);
    out.blocks = static_cast<int64_t>(host.st_blocks);
    out.blockSize = clampSigned32(static_cast<int64_t>(host.st_blksize));
    return out;
}

TrapResult ok(uint32_t number, int32_t value, const char* detail) {
    TrapResult result;
    result.handled = true;
    result.returnValue = value;
    result.number = number;
    result.detail = detail;
    return result;
}

TrapResult ok64(CPUState& state, uint32_t number, int64_t value, const char* detail) {
    const uint64_t bits = static_cast<uint64_t>(value);
    state.r[1] = static_cast<uint32_t>(bits >> 32u);
    return ok(number, static_cast<int32_t>(static_cast<uint32_t>(bits)), detail);
}

TrapResult fail(uint32_t number, int errorNumber, const char* detail) {
    TrapResult result;
    result.handled = true;
    result.returnValue = -1;
    result.errorNumber = errorNumber;
    result.number = number;
    result.detail = detail;
    return result;
}

bool addAddress(uint32_t base, uint32_t offset, uint32_t& out) {
    if (offset > UINT32_MAX - base) return false;
    out = base + offset;
    return true;
}

bool alignPage(uint32_t value, uint32_t& out) {
    const uint64_t aligned = (static_cast<uint64_t>(value) + kPageSize - 1u) &
                             ~(static_cast<uint64_t>(kPageSize) - 1u);
    if (aligned > UINT32_MAX) return false;
    out = static_cast<uint32_t>(aligned);
    return true;
}


bool mappedPageRange(const SyscallMemory& memory,
                     uint32_t address,
                     uint32_t length) {
    if (!memory.read || length == 0 ||
        (address & (kPageSize - 1u)) != 0) {
        return false;
    }
    uint32_t mappedLength = 0;
    if (!alignPage(length, mappedLength) || mappedLength == 0) return false;
    const uint64_t end = static_cast<uint64_t>(address) + mappedLength;
    if (end > 0x100000000ull) return false;

    uint8_t probe = 0;
    for (uint64_t page = address; page < end; page += kPageSize) {
        if (!memory.read(static_cast<uint32_t>(page), &probe, 1)) return false;
    }
    return memory.read(static_cast<uint32_t>(end - 1u), &probe, 1);
}
} // namespace

DarwinSyscalls::DarwinSyscalls(SyscallMemory memory, std::string guestRoot)
    : memory_(std::move(memory)), guestRoot_(std::move(guestRoot)) {}

DarwinSyscalls::~DarwinSyscalls() {
    for (const auto& entry : guestFiles_) {
        ::close(entry.second.hostFd);
    }
}

bool DarwinSyscalls::readCString(uint32_t address, std::string& out, size_t limit) const {
    out.clear();
    if (!memory_.read || limit == 0) return false;
    for (size_t i = 0; i < limit; ++i) {
        if (i > UINT32_MAX - address) return false;
        char character = 0;
        if (!memory_.read(address + static_cast<uint32_t>(i), &character, 1)) return false;
        if (character == '\0') return true;
        out.push_back(character);
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

int DarwinSyscalls::allocateGuestFd(int hostFd,
                                    uint32_t openFlags,
                                    uint32_t descriptorFlags) {
    for (int attempts = 0; attempts < INT_MAX - 3; ++attempts) {
        if (nextGuestFd_ < 3) nextGuestFd_ = 3;
        const int candidate = nextGuestFd_++;
        if (guestFiles_.find(candidate) == guestFiles_.end()) {
            guestFiles_.emplace(candidate, GuestFile{hostFd, openFlags, descriptorFlags});
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
            TrapResult result = ok(number, static_cast<int32_t>(state.r[0]), "exit");
            result.shouldStop = true;
            return result;
        }
        case 3: {
            const int guestFd = static_cast<int>(state.r[0]);
            const uint32_t bufferAddress = state.r[1];
            const size_t count = state.r[2];
            if (count > kMaximumTransfer) return fail(number, EINVAL, "read length");
            const auto file = guestFiles_.find(guestFd);
            if (file == guestFiles_.end()) return fail(number, EBADF, "read guest fd");
            std::vector<uint8_t> buffer(count);
            const ssize_t bytesRead = ::read(file->second.hostFd, buffer.data(), count);
            if (bytesRead < 0) return fail(number, errno, "read host call");
            if (bytesRead != 0 &&
                (!memory_.write ||
                 !memory_.write(bufferAddress, buffer.data(), static_cast<size_t>(bytesRead)))) {
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
            const uint32_t descriptorFlags =
                (flags & kGuestOpenCloseExec) != 0 ? kGuestFdCloseExec : 0u;
            const int guestFd = allocateGuestFd(hostFd, flags, descriptorFlags);
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
                if (guestFd >= 0 && guestFd <= 2) {
                    return ok(number, 0, "close standard fd virtualized");
                }
                return fail(number, EBADF, "close guest fd");
            }
            const int hostFd = file->second.hostFd;
            guestFiles_.erase(file);
            if (::close(hostFd) != 0) return fail(number, errno, "close host call");
            return ok(number, 0, "close");
        }
        case 20:
            return ok(number, static_cast<int32_t>(::getpid()), "getpid");
        case 24:
            return ok(number, static_cast<int32_t>(::getuid()), "getuid");
        case 25:
            return ok(number, static_cast<int32_t>(::geteuid()), "geteuid");
        case 33: {
            std::string path;
            if (!readCString(state.r[0], path)) return fail(number, EFAULT, "access path");
            const int mode = static_cast<int>(state.r[1]);
            if ((mode & ~7) != 0) return fail(number, EINVAL, "access mode");
            if ((mode & W_OK) != 0) return fail(number, EROFS, "access read-only guest root");
            std::string hostPath;
            int pathError = 0;
            if (!resolveGuestPath(path, hostPath, pathError)) {
                return fail(number, pathError ? pathError : ENOENT, "access guest path");
            }
            if (::access(hostPath.c_str(), mode & (R_OK | X_OK)) != 0) {
                return fail(number, errno, "access host call");
            }
            return ok(number, 0, "access");
        }
        case 43:
            return ok(number, static_cast<int32_t>(::getegid()), "getegid");
        case 47:
            return ok(number, static_cast<int32_t>(::getgid()), "getgid");
        case 65: {
            const uint32_t address = state.r[0];
            const uint32_t length = state.r[1];
            const uint32_t flags = state.r[2];
            const uint32_t supported = kMsAsync | kMsInvalidate |
                                       kMsKillPages | kMsDeactivate | kMsSync;
            if ((flags & ~supported) != 0 ||
                ((flags & kMsAsync) != 0 && (flags & kMsSync) != 0)) {
                return fail(number, EINVAL, "msync flags");
            }
            if (length == 0 || length > kMaximumMapping ||
                (address & (kPageSize - 1u)) != 0) {
                return fail(number, EINVAL, "msync range");
            }
            if (!mappedPageRange(memory_, address, length)) {
                return fail(number, ENOMEM, "msync unmapped range");
            }
            // Guest mappings are private memory or read-only file snapshots;
            // there is no writable host backing store to flush.
            return ok(number, 0, "msync virtual no-op");
        }
        case 73: {
            const uint32_t address = state.r[0];
            const uint32_t length = state.r[1];
            if (length == 0 || length > kMaximumMapping ||
                (address & (kPageSize - 1u)) != 0) {
                return fail(number, EINVAL, "munmap range");
            }
            uint32_t mappedLength = 0;
            if (!alignPage(length, mappedLength) || mappedLength == 0 ||
                static_cast<uint64_t>(address) + mappedLength > 0x100000000ull) {
                return fail(number, EINVAL, "munmap aligned range");
            }
            if (!memory_.unmap) return fail(number, ENOSYS, "munmap callback");
            if (!memory_.unmap(address, mappedLength)) {
                return fail(number, EINVAL, "munmap guest range");
            }
            return ok(number, 0, "munmap");
        }
        case 74: {
            const uint32_t address = state.r[0];
            const uint32_t length = state.r[1];
            const uint32_t protection = state.r[2];
            if (length == 0 || length > kMaximumMapping ||
                (address & (kPageSize - 1u)) != 0) {
                return fail(number, EINVAL, "mprotect range");
            }
            if ((protection & ~(kProtRead | kProtWrite | kProtExec)) != 0) {
                return fail(number, EINVAL, "mprotect protection");
            }
            if ((protection & (kProtWrite | kProtExec)) ==
                (kProtWrite | kProtExec)) {
                return fail(number, EPERM, "mprotect W+X blocked");
            }
            uint32_t mappedLength = 0;
            if (!alignPage(length, mappedLength) || mappedLength == 0 ||
                static_cast<uint64_t>(address) + mappedLength > 0x100000000ull) {
                return fail(number, EINVAL, "mprotect aligned range");
            }
            if (!memory_.protect) return fail(number, ENOSYS, "mprotect callback");
            if (!memory_.protect(address, mappedLength, protection)) {
                return fail(number, ENOMEM, "mprotect guest range");
            }
            return ok(number, 0, "mprotect");
        }
        case 75: {
            const uint32_t address = state.r[0];
            const uint32_t length = state.r[1];
            const int advice = static_cast<int>(state.r[2]);
            if (advice < 0 || advice > kMaximumAdvice) {
                return fail(number, EINVAL, "madvise behavior");
            }
            if (length == 0 || length > kMaximumMapping ||
                (address & (kPageSize - 1u)) != 0) {
                return fail(number, EINVAL, "madvise range");
            }
            if (!mappedPageRange(memory_, address, length)) {
                return fail(number, ENOMEM, "madvise unmapped range");
            }
            // Advice changes host paging policy only. The interpreter keeps
            // deterministic guest bytes and treats valid hints as successful.
            return ok(number, 0, "madvise virtual no-op");
        }
        case 92: {
            const int guestFd = static_cast<int>(state.r[0]);
            const uint32_t command = state.r[1];
            const uint32_t argument = state.r[2];
            const auto file = guestFiles_.find(guestFd);
            if (file == guestFiles_.end()) return fail(number, EBADF, "fcntl guest fd");
            switch (command) {
                case kFcntlGetFd:
                    return ok(number,
                              static_cast<int32_t>(file->second.descriptorFlags),
                              "fcntl F_GETFD");
                case kFcntlSetFd:
                    file->second.descriptorFlags = argument & kGuestFdCloseExec;
                    return ok(number, 0, "fcntl F_SETFD");
                case kFcntlGetFl:
                    return ok(number,
                              static_cast<int32_t>(file->second.openFlags),
                              "fcntl F_GETFL");
                default:
                    return fail(number, EINVAL, "fcntl unsupported command");
            }
        }
        case 116: {
            const uint32_t timevalAddress = state.r[0];
            if (!timevalAddress) return ok(number, 0, "gettimeofday(null)");
            struct GuestTimeval {
                int32_t seconds;
                int32_t microseconds;
            } guest{};
            const auto now = std::chrono::system_clock::now().time_since_epoch();
            const auto microseconds =
                std::chrono::duration_cast<std::chrono::microseconds>(now).count();
            guest.seconds = static_cast<int32_t>(microseconds / 1000000);
            guest.microseconds = static_cast<int32_t>(microseconds % 1000000);
            if (!memory_.write ||
                !memory_.write(timevalAddress, &guest, sizeof(guest))) {
                return fail(number, EFAULT, "gettimeofday guest write");
            }
            return ok(number, 0, "gettimeofday");
        }
        case 197: {
            const uint32_t requestedAddress = state.r[0];
            const uint32_t length = state.r[1];
            const uint32_t protection = state.r[2];
            const uint32_t flags = state.r[3];

            if (length == 0 || length > kMaximumMapping) {
                return fail(number, EINVAL, "mmap length");
            }
            if ((protection & ~(kProtRead | kProtWrite | kProtExec)) != 0) {
                return fail(number, EINVAL, "mmap protection");
            }
            if ((flags & kMapFixed) != 0) {
                return fail(number, EINVAL, "mmap MAP_FIXED blocked");
            }
            if ((flags & kMapJit) != 0) {
                return fail(number, EPERM, "mmap MAP_JIT blocked");
            }
            const uint32_t sharing = flags & (kMapShared | kMapPrivate);
            if (sharing != kMapShared && sharing != kMapPrivate) {
                return fail(number, EINVAL, "mmap sharing mode");
            }
            const uint32_t supportedFlags =
                kMapShared | kMapPrivate | kMapAnonymous;
            if ((flags & ~supportedFlags) != 0) {
                return fail(number, EINVAL, "mmap flags");
            }
            if (!memory_.map || !memory_.write || !memory_.read) {
                return fail(number, ENOMEM, "mmap memory callbacks");
            }

            uint32_t stackFdAddress = 0;
            uint32_t stackOffsetLowAddress = 0;
            uint32_t stackOffsetHighAddress = 0;
            if (!addAddress(state.r[13], 0u, stackFdAddress) ||
                !addAddress(state.r[13], 8u, stackOffsetLowAddress) ||
                !addAddress(state.r[13], 12u, stackOffsetHighAddress)) {
                return fail(number, EFAULT, "mmap stack address");
            }

            uint32_t fdWord = 0;
            uint32_t offsetLow = 0;
            uint32_t offsetHigh = 0;
            if (!memory_.read(stackFdAddress, &fdWord, sizeof(fdWord)) ||
                !memory_.read(stackOffsetLowAddress, &offsetLow, sizeof(offsetLow)) ||
                !memory_.read(stackOffsetHighAddress, &offsetHigh, sizeof(offsetHigh))) {
                return fail(number, EFAULT, "mmap stack read");
            }

            const int guestFd = static_cast<int32_t>(fdWord);
            const uint64_t rawOffset = static_cast<uint64_t>(offsetLow) |
                                       (static_cast<uint64_t>(offsetHigh) << 32u);
            const int64_t offset = static_cast<int64_t>(rawOffset);
            if (offset < 0 || (rawOffset & (kPageSize - 1u)) != 0) {
                return fail(number, EINVAL, "mmap offset");
            }

            const bool anonymous = (flags & kMapAnonymous) != 0;
            const GuestFile* file = nullptr;
            if (anonymous) {
                if (guestFd != -1) return fail(number, EINVAL, "mmap anonymous fd");
            } else {
                if ((protection & kProtWrite) != 0) {
                    return fail(number, EROFS, "mmap writable file blocked");
                }
                const auto found = guestFiles_.find(guestFd);
                if (found == guestFiles_.end()) return fail(number, EBADF, "mmap guest fd");
                file = &found->second;
            }

            uint32_t mappedLength = 0;
            if (!alignPage(length, mappedLength) || mappedLength == 0) {
                return fail(number, EINVAL, "mmap aligned length");
            }

            std::vector<uint8_t> contents(length, 0);
            if (file != nullptr) {
                size_t completed = 0;
                while (completed < contents.size()) {
                    const ssize_t bytes = ::pread(
                        file->hostFd,
                        contents.data() + completed,
                        contents.size() - completed,
                        static_cast<off_t>(offset + static_cast<int64_t>(completed)));
                    if (bytes < 0) {
                        if (errno == EINTR) continue;
                        return fail(number, errno, "mmap pread");
                    }
                    if (bytes == 0) break;
                    completed += static_cast<size_t>(bytes);
                }
            }

            uint32_t mappingAddress = 0;
            bool mapped = false;
            if (requestedAddress != 0) {
                if ((requestedAddress & (kPageSize - 1u)) != 0) {
                    return fail(number, EINVAL, "mmap address alignment");
                }
                mapped = memory_.map(requestedAddress, mappedLength, protection);
                if (mapped) mappingAddress = requestedAddress;
            }

            if (!mapped) {
                uint32_t candidate = nextMmapAddress_;
                if ((candidate & (kPageSize - 1u)) != 0 &&
                    !alignPage(candidate, candidate)) {
                    return fail(number, ENOMEM, "mmap address overflow");
                }
                for (uint32_t attempt = 0; attempt < 4096u; ++attempt) {
                    const uint64_t end = static_cast<uint64_t>(candidate) + mappedLength;
                    if (end > 0x100000000ull) break;
                    if (memory_.map(candidate, mappedLength, protection)) {
                        mappingAddress = candidate;
                        mapped = true;
                        break;
                    }
                    if (end + kPageSize > 0x100000000ull) break;
                    candidate = static_cast<uint32_t>(end + kPageSize);
                }
            }

            if (!mapped) return fail(number, ENOMEM, "mmap guest allocation");
            if (!contents.empty() &&
                !memory_.write(mappingAddress, contents.data(), contents.size())) {
                return fail(number, EFAULT, "mmap guest write");
            }

            const uint64_t next = static_cast<uint64_t>(mappingAddress) +
                                  mappedLength + kPageSize;
            nextMmapAddress_ = next < 0x100000000ull
                                   ? static_cast<uint32_t>(next)
                                   : 0x50000000u;
            return ok(number, static_cast<int32_t>(mappingAddress), "mmap");
        }
        case 199: {
            const int guestFd = static_cast<int>(state.r[0]);
            const auto file = guestFiles_.find(guestFd);
            if (file == guestFiles_.end()) return fail(number, EBADF, "lseek guest fd");

            // ARM AAPCS aligns the off_t argument to r2:r3 after the fd in r0.
            // The following int argument is therefore passed at the current SP.
            uint32_t whenceWord = 0;
            if (!memory_.read ||
                !memory_.read(state.r[13], &whenceWord, sizeof(whenceWord))) {
                return fail(number, EFAULT, "lseek whence stack read");
            }
            const int whence = static_cast<int>(whenceWord);
            if (whence != SEEK_SET && whence != SEEK_CUR && whence != SEEK_END) {
                return fail(number, EINVAL, "lseek whence");
            }

            const uint64_t rawOffset = static_cast<uint64_t>(state.r[2]) |
                                       (static_cast<uint64_t>(state.r[3]) << 32u);
            const int64_t offset = static_cast<int64_t>(rawOffset);
            const off_t position = ::lseek(file->second.hostFd,
                                           static_cast<off_t>(offset),
                                           whence);
            if (position == static_cast<off_t>(-1)) {
                return fail(number, errno, "lseek host call");
            }
            return ok64(state, number, static_cast<int64_t>(position), "lseek");
        }
        case 338: {
            std::string path;
            if (!readCString(state.r[0], path)) return fail(number, EFAULT, "stat64 path");
            std::string hostPath;
            int pathError = 0;
            if (!resolveGuestPath(path, hostPath, pathError)) {
                return fail(number, pathError ? pathError : ENOENT, "stat64 guest path");
            }
            struct stat host{};
            if (::stat(hostPath.c_str(), &host) != 0) {
                return fail(number, errno, "stat64 host call");
            }
            const GuestStat64 guest = guestStat64(host);
            if (!memory_.write || !memory_.write(state.r[1], &guest, sizeof(guest))) {
                return fail(number, EFAULT, "stat64 guest write");
            }
            return ok(number, 0, "stat64");
        }
        case 339: {
            const int guestFd = static_cast<int>(state.r[0]);
            const uint32_t statAddress = state.r[1];
            const auto file = guestFiles_.find(guestFd);
            if (file == guestFiles_.end()) return fail(number, EBADF, "fstat64 guest fd");
            struct stat host{};
            if (::fstat(file->second.hostFd, &host) != 0) {
                return fail(number, errno, "fstat64 host call");
            }
            const GuestStat64 guest = guestStat64(host);
            if (!memory_.write || !memory_.write(statAddress, &guest, sizeof(guest))) {
                return fail(number, EFAULT, "fstat64 guest write");
            }
            return ok(number, 0, "fstat64");
        }
        default: {
            TrapResult result;
            result.number = number;
            result.detail = "unsupported BSD syscall";
            return result;
        }
    }
}

TrapResult DarwinSyscalls::dispatchMach(CPUState&, uint32_t number) {
    switch (number) {
        case 26:
            return ok(number, 0x100, "mach_reply_port placeholder");
        case 27:
            return ok(number, 0x101, "thread_self_trap placeholder");
        case 28:
            return ok(number, 0x102, "task_self_trap placeholder");
        case 29:
            return ok(number, 0x103, "host_self_trap placeholder");
        default: {
            TrapResult result;
            result.number = number;
            result.detail = "unsupported Mach trap";
            return result;
        }
    }
}

} // namespace lc32
