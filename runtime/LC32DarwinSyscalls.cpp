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

constexpr int32_t kCtlKern = 1;
constexpr int32_t kCtlHw = 6;
constexpr int32_t kKernOsType = 1;
constexpr int32_t kKernOsRelease = 2;
constexpr int32_t kKernOsRevision = 3;
constexpr int32_t kKernVersion = 4;
constexpr int32_t kKernOsVersion = 65;
constexpr int32_t kHwMachine = 1;
constexpr int32_t kHwModel = 2;
constexpr int32_t kHwCpuCount = 3;
constexpr int32_t kHwByteOrder = 4;
constexpr int32_t kHwPhysicalMemory = 5;
constexpr int32_t kHwUserMemory = 6;
constexpr int32_t kHwPageSize = 7;
constexpr int32_t kHwFloatingPoint = 11;
constexpr int32_t kHwMachineArch = 12;
constexpr int32_t kHwMemorySize = 24;
constexpr int32_t kHwAvailableCpu = 25;
constexpr uint32_t kCtlMaximumName = 12u;
constexpr uint32_t kRlimitPosixFlag = 0x1000u;
constexpr uint64_t kRlimitInfinity = (1ull << 63u) - 1u;
constexpr uint32_t kGuestDescriptorLimit = 10240u;

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


struct GuestRlimit {
    uint64_t current = 0;
    uint64_t maximum = 0;
};
#pragma pack(pop)

static_assert(sizeof(GuestTimespec32) == 8, "unexpected ARMv7 timespec layout");
static_assert(sizeof(GuestStat64) == 108, "unexpected iOS 6 user32_stat64 layout");
static_assert(sizeof(GuestRlimit) == 16, "unexpected ARMv7 rlimit layout");

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
        if (entry.second.directoryStream != nullptr) {
            ::closedir(entry.second.directoryStream);
        }
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


bool DarwinSyscalls::resolveGuestPathNoFollow(const std::string& guestPath,
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

    char resolvedRoot[PATH_MAX]{};
    if (!::realpath(guestRoot_.c_str(), resolvedRoot)) {
        errorNumber = errno ? errno : ENOENT;
        return false;
    }
    std::string root(resolvedRoot);
    while (root.size() > 1 && root.back() == '/') root.pop_back();
    if (components.empty()) {
        hostPath = root;
        return true;
    }

    std::string parentCandidate = guestRoot_;
    while (parentCandidate.size() > 1 && parentCandidate.back() == '/') {
        parentCandidate.pop_back();
    }
    for (std::size_t index = 0; index + 1u < components.size(); ++index) {
        parentCandidate.push_back('/');
        parentCandidate += components[index];
    }

    char resolvedParent[PATH_MAX]{};
    if (!::realpath(parentCandidate.c_str(), resolvedParent)) {
        errorNumber = errno ? errno : ENOENT;
        return false;
    }
    std::string parent(resolvedParent);
    while (parent.size() > 1 && parent.back() == '/') parent.pop_back();
    const bool withinRoot = parent == root ||
                            (parent.size() > root.size() &&
                             parent.compare(0, root.size(), root) == 0 &&
                             parent[root.size()] == '/');
    if (!withinRoot) {
        errorNumber = EACCES;
        return false;
    }

    hostPath = std::move(parent);
    if (hostPath.size() != 1 || hostPath.front() != '/') hostPath.push_back('/');
    hostPath += components.back();
    return true;
}

int DarwinSyscalls::allocateGuestFd(int hostFd,
                                    uint32_t openFlags,
                                    uint32_t descriptorFlags,
                                    DIR* directoryStream) {
    for (int attempts = 0; attempts < INT_MAX - 3; ++attempts) {
        if (nextGuestFd_ < 3) nextGuestFd_ = 3;
        const int candidate = nextGuestFd_++;
        if (guestFiles_.find(candidate) == guestFiles_.end()) {
            guestFiles_.emplace(candidate,
                                GuestFile{hostFd,
                                          openFlags,
                                          descriptorFlags,
                                          directoryStream});
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
            DIR* directoryStream = nullptr;
            struct stat openedStat{};
            if (::fstat(hostFd, &openedStat) != 0) {
                const int savedError = errno;
                ::close(hostFd);
                return fail(number, savedError, "open fstat");
            }
            if (S_ISDIR(openedStat.st_mode)) {
                const int directoryFd = ::dup(hostFd);
                if (directoryFd < 0) {
                    const int savedError = errno;
                    ::close(hostFd);
                    return fail(number, savedError, "open directory dup");
                }
                directoryStream = ::fdopendir(directoryFd);
                if (directoryStream == nullptr) {
                    const int savedError = errno;
                    ::close(directoryFd);
                    ::close(hostFd);
                    return fail(number, savedError, "open directory stream");
                }
            }
            const uint32_t descriptorFlags =
                (flags & kGuestOpenCloseExec) != 0 ? kGuestFdCloseExec : 0u;
            const int guestFd = allocateGuestFd(hostFd,
                                                flags,
                                                descriptorFlags,
                                                directoryStream);
            if (guestFd < 0) {
                if (directoryStream != nullptr) ::closedir(directoryStream);
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
            DIR* directoryStream = file->second.directoryStream;
            guestFiles_.erase(file);
            if (directoryStream != nullptr && ::closedir(directoryStream) != 0) {
                const int savedError = errno;
                ::close(hostFd);
                return fail(number, savedError, "close directory stream");
            }
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
        case 58: {
            std::string path;
            if (!readCString(state.r[0], path)) {
                return fail(number, EFAULT, "readlink path");
            }
            const uint32_t bufferAddress = state.r[1];
            const size_t count = state.r[2];
            if (count == 0 || count > kMaximumTransfer) {
                return fail(number, EINVAL, "readlink length");
            }
            std::string hostPath;
            int pathError = 0;
            if (!resolveGuestPathNoFollow(path, hostPath, pathError)) {
                return fail(number,
                            pathError ? pathError : ENOENT,
                            "readlink guest path");
            }
            std::vector<char> target(count);
            ssize_t bytes = -1;
            do {
                bytes = ::readlink(hostPath.c_str(), target.data(), target.size());
            } while (bytes < 0 && errno == EINTR);
            if (bytes < 0) return fail(number, errno, "readlink host call");
            if (bytes > 0 &&
                (!memory_.write ||
                 !memory_.write(bufferAddress,
                                target.data(),
                                static_cast<size_t>(bytes)))) {
                return fail(number, EFAULT, "readlink guest write");
            }
            return ok(number, static_cast<int32_t>(bytes), "readlink");
        }
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
        case 78: {
            const uint32_t address = state.r[0];
            const uint32_t length = state.r[1];
            const uint32_t vectorAddress = state.r[2];
            if (length == 0 || length > kMaximumMapping ||
                (address & (kPageSize - 1u)) != 0) {
                return fail(number, EINVAL, "mincore range");
            }
            uint32_t mappedLength = 0;
            if (!alignPage(length, mappedLength) || mappedLength == 0 ||
                static_cast<uint64_t>(address) + mappedLength > 0x100000000ull) {
                return fail(number, EINVAL, "mincore aligned range");
            }
            if (!mappedPageRange(memory_, address, mappedLength)) {
                return fail(number, ENOMEM, "mincore unmapped range");
            }
            if (!memory_.write || vectorAddress == 0) {
                return fail(number, EFAULT, "mincore vector");
            }
            const size_t pageCount = mappedLength / kPageSize;
            std::vector<uint8_t> residency(pageCount, 0x01u);
            if (!memory_.write(vectorAddress, residency.data(), residency.size())) {
                return fail(number, EFAULT, "mincore guest write");
            }
            return ok(number, 0, "mincore");
        }
        case 89:
            return ok(number,
                      static_cast<int32_t>(kGuestDescriptorLimit),
                      "getdtablesize");
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
        case 153:
        case 414: {
            const int guestFd = static_cast<int>(state.r[0]);
            const uint32_t bufferAddress = state.r[1];
            const size_t count = state.r[2];
            if (count > kMaximumTransfer) {
                return fail(number, EINVAL, "pread length");
            }
            const auto file = guestFiles_.find(guestFd);
            if (file == guestFiles_.end()) {
                return fail(number, EBADF, "pread guest fd");
            }

            uint32_t offsetLowAddress = 0;
            uint32_t offsetHighAddress = 0;
            if (!addAddress(state.r[13], 0u, offsetLowAddress) ||
                !addAddress(state.r[13], 4u, offsetHighAddress)) {
                return fail(number, EFAULT, "pread stack address");
            }
            uint32_t offsetLow = 0;
            uint32_t offsetHigh = 0;
            if (!memory_.read ||
                !memory_.read(offsetLowAddress, &offsetLow, sizeof(offsetLow)) ||
                !memory_.read(offsetHighAddress, &offsetHigh, sizeof(offsetHigh))) {
                return fail(number, EFAULT, "pread stack read");
            }
            const uint64_t rawOffset = static_cast<uint64_t>(offsetLow) |
                                       (static_cast<uint64_t>(offsetHigh) << 32u);
            const int64_t offset = static_cast<int64_t>(rawOffset);
            if (offset < 0) return fail(number, EINVAL, "pread offset");

            std::vector<uint8_t> buffer(count);
            ssize_t bytesRead = -1;
            do {
                bytesRead = ::pread(file->second.hostFd,
                                    buffer.data(),
                                    buffer.size(),
                                    static_cast<off_t>(offset));
            } while (bytesRead < 0 && errno == EINTR);
            if (bytesRead < 0) return fail(number, errno, "pread host call");
            if (bytesRead > 0 &&
                (!memory_.write ||
                 !memory_.write(bufferAddress,
                                buffer.data(),
                                static_cast<size_t>(bytesRead)))) {
                return fail(number, EFAULT, "pread guest write");
            }
            return ok(number,
                      static_cast<int32_t>(bytesRead),
                      number == 414 ? "pread_nocancel" : "pread");
        }
        case 194: {
            const uint32_t rawResource = state.r[0];
            if ((rawResource & ~(kRlimitPosixFlag | 0x0fu)) != 0) {
                return fail(number, EINVAL, "getrlimit flags");
            }
            const uint32_t resource = rawResource & ~kRlimitPosixFlag;
            GuestRlimit limit;
            switch (resource) {
                case 0: // RLIMIT_CPU
                case 1: // RLIMIT_FSIZE
                    limit = {kRlimitInfinity, kRlimitInfinity};
                    break;
                case 2: // RLIMIT_DATA
                    limit = {512ull * 1024ull * 1024ull,
                             768ull * 1024ull * 1024ull};
                    break;
                case 3: // RLIMIT_STACK
                    limit = {8ull * 1024ull * 1024ull,
                             64ull * 1024ull * 1024ull};
                    break;
                case 4: // RLIMIT_CORE
                    limit = {0, 0};
                    break;
                case 5: // RLIMIT_AS
                    limit = {1024ull * 1024ull * 1024ull,
                             1024ull * 1024ull * 1024ull};
                    break;
                case 6: // RLIMIT_MEMLOCK
                    limit = {16ull * 1024ull * 1024ull,
                             64ull * 1024ull * 1024ull};
                    break;
                case 7: // RLIMIT_NPROC
                    limit = {256, 512};
                    break;
                case 8: // RLIMIT_NOFILE
                    limit = {256, kGuestDescriptorLimit};
                    break;
                default:
                    return fail(number, EINVAL, "getrlimit resource");
            }
            if (!memory_.write ||
                !memory_.write(state.r[1], &limit, sizeof(limit))) {
                return fail(number, EFAULT, "getrlimit guest write");
            }
            return ok(number, 0, "getrlimit");
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
        case 202: {
            const uint32_t nameAddress = state.r[0];
            const uint32_t nameLength = state.r[1];
            const uint32_t oldAddress = state.r[2];
            const uint32_t oldLengthAddress = state.r[3];
            if (nameLength == 0 || nameLength > kCtlMaximumName) {
                return fail(number, EINVAL, "sysctl name length");
            }
            if (!memory_.read || !memory_.write || oldLengthAddress == 0) {
                return fail(number, EFAULT, "sysctl memory callbacks");
            }

            uint32_t stackNewAddress = 0;
            uint32_t stackNewLength = 0;
            if (!addAddress(state.r[13], 0u, stackNewAddress) ||
                !addAddress(state.r[13], 4u, stackNewLength)) {
                return fail(number, EFAULT, "sysctl stack address");
            }
            uint32_t newAddress = 0;
            uint32_t newLength = 0;
            if (!memory_.read(stackNewAddress, &newAddress, sizeof(newAddress)) ||
                !memory_.read(stackNewLength, &newLength, sizeof(newLength))) {
                return fail(number, EFAULT, "sysctl stack read");
            }
            if (newAddress != 0 || newLength != 0) {
                return fail(number, EPERM, "sysctl read-only profile");
            }

            std::vector<int32_t> mib(nameLength);
            if (!memory_.read(nameAddress,
                              mib.data(),
                              mib.size() * sizeof(mib.front()))) {
                return fail(number, EFAULT, "sysctl name read");
            }
            if (mib.size() != 2u) {
                return fail(number, ENOENT, "sysctl unsupported MIB depth");
            }

            std::vector<uint8_t> payload;
            const auto setString = [&](const char* value) {
                const size_t length = std::strlen(value) + 1u;
                payload.assign(reinterpret_cast<const uint8_t*>(value),
                               reinterpret_cast<const uint8_t*>(value) + length);
            };
            const auto setInt32 = [&](int32_t value) {
                payload.resize(sizeof(value));
                std::memcpy(payload.data(), &value, sizeof(value));
            };
            const auto setUInt64 = [&](uint64_t value) {
                payload.resize(sizeof(value));
                std::memcpy(payload.data(), &value, sizeof(value));
            };

            if (mib[0] == kCtlKern) {
                switch (mib[1]) {
                    case kKernOsType:
                        setString("Darwin");
                        break;
                    case kKernOsRelease:
                        setString("12.5.0");
                        break;
                    case kKernOsRevision:
                        setInt32(199506);
                        break;
                    case kKernVersion:
                        setString("Darwin Kernel Version 12.5.0: LC32 deterministic ARMv7 profile");
                        break;
                    case kKernOsVersion:
                        setString("10B329");
                        break;
                    default:
                        return fail(number, ENOENT, "sysctl unsupported kern MIB");
                }
            } else if (mib[0] == kCtlHw) {
                switch (mib[1]) {
                    case kHwMachine:
                        setString("iPhone5,2");
                        break;
                    case kHwModel:
                        setString("N42AP");
                        break;
                    case kHwCpuCount:
                    case kHwAvailableCpu:
                        setInt32(2);
                        break;
                    case kHwByteOrder:
                        setInt32(1234);
                        break;
                    case kHwPhysicalMemory:
                        setInt32(1024 * 1024 * 1024);
                        break;
                    case kHwUserMemory:
                        setInt32(768 * 1024 * 1024);
                        break;
                    case kHwPageSize:
                        setInt32(static_cast<int32_t>(kPageSize));
                        break;
                    case kHwFloatingPoint:
                        setInt32(1);
                        break;
                    case kHwMachineArch:
                        setString("arm");
                        break;
                    case kHwMemorySize:
                        setUInt64(1024ull * 1024ull * 1024ull);
                        break;
                    default:
                        return fail(number, ENOENT, "sysctl unsupported hw MIB");
                }
            } else {
                return fail(number, ENOENT, "sysctl unsupported root MIB");
            }

            if (payload.size() > UINT32_MAX) {
                return fail(number, ENOMEM, "sysctl payload length");
            }
            uint32_t suppliedLength = 0;
            if (!memory_.read(oldLengthAddress,
                              &suppliedLength,
                              sizeof(suppliedLength))) {
                return fail(number, EFAULT, "sysctl old length read");
            }
            const uint32_t requiredLength = static_cast<uint32_t>(payload.size());
            if (!memory_.write(oldLengthAddress,
                               &requiredLength,
                               sizeof(requiredLength))) {
                return fail(number, EFAULT, "sysctl old length write");
            }
            if (oldAddress == 0) {
                return ok(number, 0, "sysctl size query");
            }
            if (suppliedLength < requiredLength) {
                return fail(number, ENOMEM, "sysctl output too small");
            }
            if (!payload.empty() &&
                !memory_.write(oldAddress, payload.data(), payload.size())) {
                return fail(number, EFAULT, "sysctl output write");
            }
            return ok(number, 0, "sysctl");
        }
        case 344: {
            const int guestFd = static_cast<int>(state.r[0]);
            const uint32_t bufferAddress = state.r[1];
            const size_t bufferSize = state.r[2];
            const uint32_t positionAddress = state.r[3];
            if (bufferSize == 0 || bufferSize > kMaximumTransfer) {
                return fail(number, EINVAL, "getdirentries64 buffer size");
            }
            if (!memory_.write || positionAddress == 0) {
                return fail(number, EFAULT, "getdirentries64 memory");
            }
            const auto file = guestFiles_.find(guestFd);
            if (file == guestFiles_.end()) {
                return fail(number, EBADF, "getdirentries64 guest fd");
            }
            DIR* stream = file->second.directoryStream;
            if (stream == nullptr) {
                return fail(number, ENOTDIR, "getdirentries64 not directory");
            }

            const long initialCookie = ::telldir(stream);
            std::vector<uint8_t> output;
            output.reserve(bufferSize);
            uint64_t finalPosition = initialCookie < 0 ? 0u : static_cast<uint64_t>(initialCookie);

            for (;;) {
                const long entryCookie = ::telldir(stream);
                errno = 0;
                struct dirent* entry = ::readdir(stream);
                if (entry == nullptr) {
                    if (errno != 0) {
                        if (initialCookie >= 0) ::seekdir(stream, initialCookie);
                        return fail(number, errno, "getdirentries64 readdir");
                    }
                    break;
                }

                const size_t nameLength = ::strnlen(entry->d_name, 1024u);
                if (nameLength > UINT16_MAX) {
                    if (initialCookie >= 0) ::seekdir(stream, initialCookie);
                    return fail(number, EOVERFLOW, "getdirentries64 name length");
                }
                const size_t recordSize = (21u + nameLength + 1u + 3u) & ~size_t(3u);
                if (recordSize > UINT16_MAX) {
                    if (initialCookie >= 0) ::seekdir(stream, initialCookie);
                    return fail(number, EOVERFLOW, "getdirentries64 record length");
                }
                if (recordSize > bufferSize - output.size()) {
                    if (entryCookie >= 0) ::seekdir(stream, entryCookie);
                    if (output.empty()) {
                        return fail(number, EINVAL, "getdirentries64 buffer too small");
                    }
                    break;
                }

                const long nextCookie = ::telldir(stream);
                const uint64_t inode = static_cast<uint64_t>(entry->d_ino);
                const uint64_t seekOffset =
                    nextCookie < 0 ? finalPosition : static_cast<uint64_t>(nextCookie);
                const uint16_t recordLength = static_cast<uint16_t>(recordSize);
                const uint16_t guestNameLength = static_cast<uint16_t>(nameLength);
                const uint8_t type = static_cast<uint8_t>(entry->d_type);
                const size_t base = output.size();
                output.resize(base + recordSize, 0);
                std::memcpy(output.data() + base + 0u, &inode, sizeof(inode));
                std::memcpy(output.data() + base + 8u, &seekOffset, sizeof(seekOffset));
                std::memcpy(output.data() + base + 16u,
                            &recordLength,
                            sizeof(recordLength));
                std::memcpy(output.data() + base + 18u,
                            &guestNameLength,
                            sizeof(guestNameLength));
                std::memcpy(output.data() + base + 20u, &type, sizeof(type));
                std::memcpy(output.data() + base + 21u,
                            entry->d_name,
                            nameLength + 1u);
                finalPosition = seekOffset;
            }

            if (!output.empty() &&
                !memory_.write(bufferAddress, output.data(), output.size())) {
                if (initialCookie >= 0) ::seekdir(stream, initialCookie);
                return fail(number, EFAULT, "getdirentries64 guest buffer write");
            }
            if (!memory_.write(positionAddress,
                               &finalPosition,
                               sizeof(finalPosition))) {
                if (initialCookie >= 0) ::seekdir(stream, initialCookie);
                return fail(number, EFAULT, "getdirentries64 position write");
            }
            return ok(number,
                      static_cast<int32_t>(output.size()),
                      "getdirentries64");
        }
        case 340: {
            std::string path;
            if (!readCString(state.r[0], path)) {
                return fail(number, EFAULT, "lstat64 path");
            }
            std::string hostPath;
            int pathError = 0;
            if (!resolveGuestPathNoFollow(path, hostPath, pathError)) {
                return fail(number,
                            pathError ? pathError : ENOENT,
                            "lstat64 guest path");
            }
            struct stat host{};
            if (::lstat(hostPath.c_str(), &host) != 0) {
                return fail(number, errno, "lstat64 host call");
            }
            const GuestStat64 guest = guestStat64(host);
            if (!memory_.write ||
                !memory_.write(state.r[1], &guest, sizeof(guest))) {
                return fail(number, EFAULT, "lstat64 guest write");
            }
            return ok(number, 0, "lstat64");
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

TrapResult DarwinSyscalls::dispatchMach(CPUState& state, uint32_t number) {
    constexpr uint32_t kThreadPort = 0x101u;
    constexpr uint32_t kTaskPort = 0x102u;
    constexpr uint32_t kHostPort = 0x103u;
    constexpr uint32_t kBootstrapPort = 0x104u;
    constexpr uint32_t kSystemLoggerPort = 0x110u;
    constexpr uint32_t kNotificationCenterPort = 0x111u;
    constexpr uint32_t kCfprefsdPort = 0x112u;

    constexpr uint32_t kMachPortRightSend = 0u;
    constexpr uint32_t kMachPortRightReceive = 1u;
    constexpr uint32_t kMachPortRightSendOnce = 2u;

    constexpr uint32_t kMachMsgTypeMoveSend = 17u;
    constexpr uint32_t kMachMsgTypeMoveSendOnce = 18u;
    constexpr uint32_t kMachMsgTypeCopySend = 19u;
    constexpr uint32_t kMachMsgTypeMakeSend = 20u;
    constexpr uint32_t kMachMsgTypeMakeSendOnce = 21u;

    constexpr uint32_t kMachSendMsg = 0x00000001u;
    constexpr uint32_t kMachReceiveMsg = 0x00000002u;
    constexpr uint32_t kMachMessageComplex = 0x80000000u;
    constexpr uint32_t kMachRemoteDispositionMask = 0xffu;

    constexpr uint32_t kKernSuccess = 0u;
    constexpr uint32_t kKernInvalidArgument = 4u;
    constexpr uint32_t kKernInvalidName = 15u;
    constexpr uint32_t kKernInvalidTask = 16u;
    constexpr uint32_t kKernInvalidRight = 17u;
    constexpr uint32_t kKernInvalidValue = 18u;
    constexpr uint32_t kKernUrefsOverflow = 19u;

    constexpr uint32_t kMachSendInvalidData = 0x10000002u;
    constexpr uint32_t kMachSendInvalidDestination = 0x10000003u;
    constexpr uint32_t kMachSendMessageTooSmall = 0x10000008u;
    constexpr uint32_t kMachSendInvalidRight = 0x1000000au;
    constexpr uint32_t kMachReceiveInvalidName = 0x10004002u;
    constexpr uint32_t kMachReceiveTimedOut = 0x10004003u;
    constexpr uint32_t kMachReceiveTooLarge = 0x10004004u;
    constexpr uint32_t kMachHeaderSize = 24u;
    constexpr uint32_t kMaximumMachMessage = 1024u * 1024u;

    const auto ensureBuiltinPorts = [&]() {
        const auto addBuiltin = [&](uint32_t name) {
            auto [it, inserted] = machPorts_.try_emplace(name);
            if (inserted) {
                it->second.receiveRefs = 1;
                it->second.sendRefs = 1;
                it->second.immortal = true;
            }
        };
        addBuiltin(kThreadPort);
        addBuiltin(kTaskPort);
        addBuiltin(kHostPort);
        addBuiltin(kBootstrapPort);
        addBuiltin(kSystemLoggerPort);
        addBuiltin(kNotificationCenterPort);
        addBuiltin(kCfprefsdPort);
    };
    ensureBuiltinPorts();

    const auto validTask = [&](uint32_t task) {
        return task == kTaskPort;
    };
    const auto allocateReceivePort = [&]() -> uint32_t {
        uint32_t candidate = nextMachPort_;
        while (candidate == 0 || machPorts_.find(candidate) != machPorts_.end()) {
            ++candidate;
            if (candidate < 0x200u) candidate = 0x200u;
        }
        nextMachPort_ = candidate + 1u;
        MachPort port;
        port.receiveRefs = 1;
        machPorts_.emplace(candidate, std::move(port));
        return candidate;
    };
    const auto maybeErasePort = [&](uint32_t name) {
        const auto it = machPorts_.find(name);
        if (it == machPorts_.end() || it->second.immortal) return;
        if (it->second.receiveRefs == 0 && it->second.sendRefs == 0 &&
            it->second.sendOnceRefs == 0) {
            machPorts_.erase(it);
        }
    };
    const auto adjustRefs = [&](uint32_t name,
                                uint32_t right,
                                int32_t delta) -> uint32_t {
        auto it = machPorts_.find(name);
        if (it == machPorts_.end()) return kKernInvalidName;
        uint32_t* refs = nullptr;
        switch (right) {
            case kMachPortRightSend:
                refs = &it->second.sendRefs;
                break;
            case kMachPortRightReceive:
                refs = &it->second.receiveRefs;
                break;
            case kMachPortRightSendOnce:
                refs = &it->second.sendOnceRefs;
                break;
            default:
                return kKernInvalidRight;
        }
        if (right == kMachPortRightReceive) {
            const int64_t updated = static_cast<int64_t>(*refs) + delta;
            if (updated < 0 || updated > 1) return kKernInvalidValue;
            *refs = static_cast<uint32_t>(updated);
        } else if (delta < 0) {
            const uint32_t magnitude = static_cast<uint32_t>(-static_cast<int64_t>(delta));
            if (magnitude > *refs) return kKernInvalidRight;
            *refs -= magnitude;
        } else {
            const uint64_t updated = static_cast<uint64_t>(*refs) +
                                     static_cast<uint32_t>(delta);
            if (updated > UINT32_MAX) return kKernUrefsOverflow;
            *refs = static_cast<uint32_t>(updated);
        }
        maybeErasePort(name);
        return kKernSuccess;
    };

    const auto queueHostMigReply = [&](const std::vector<uint8_t>& request,
                                       uint32_t replyName) -> bool {
        if (replyName == 0) return false;
        auto replyPort = machPorts_.find(replyName);
        if (replyPort == machPorts_.end() || replyPort->second.receiveRefs == 0 ||
            request.size() < kMachHeaderSize) {
            return false;
        }

        uint32_t requestId = 0;
        std::memcpy(&requestId, request.data() + 20u, sizeof(requestId));
        if (requestId != 200u && requestId != 202u) return false;

        constexpr uint8_t kNdr[8] = {0u, 0u, 0u, 0u, 1u, 0u, 0u, 0u};
        std::vector<uint8_t> reply;
        const auto appendWord = [&](uint32_t value) {
            const size_t base = reply.size();
            reply.resize(base + sizeof(value));
            std::memcpy(reply.data() + base, &value, sizeof(value));
        };
        const auto appendBytes = [&](const void* bytes, size_t size) {
            const size_t base = reply.size();
            reply.resize(base + size);
            std::memcpy(reply.data() + base, bytes, size);
        };

        reply.resize(kMachHeaderSize, 0u);
        appendBytes(kNdr, sizeof(kNdr));
        appendWord(kKernSuccess);

        if (requestId == 202u) {
            appendWord(4096u);
        } else {
            if (request.size() < 40u) return false;
            uint32_t flavor = 0;
            uint32_t requestedCount = 0;
            std::memcpy(&flavor, request.data() + 32u, sizeof(flavor));
            std::memcpy(&requestedCount, request.data() + 36u, sizeof(requestedCount));
            if (flavor != 1u || requestedCount < 12u) return false;

            appendWord(12u);
            const uint32_t hostBasicInfo[12] = {
                2u, 2u, 1024u * 1024u * 1024u,
                12u, 9u, 0u,
                2u, 2u, 2u, 2u,
                1024u * 1024u * 1024u, 0u,
            };
            appendBytes(hostBasicInfo, sizeof(hostBasicInfo));
        }

        const uint32_t bits = 0u;
        const uint32_t size = static_cast<uint32_t>(reply.size());
        const uint32_t remote = 0u;
        const uint32_t local = replyName;
        const uint32_t reserved = 0u;
        const uint32_t replyId = requestId + 100u;
        std::memcpy(reply.data(), &bits, 4u);
        std::memcpy(reply.data() + 4u, &size, 4u);
        std::memcpy(reply.data() + 8u, &remote, 4u);
        std::memcpy(reply.data() + 12u, &local, 4u);
        std::memcpy(reply.data() + 16u, &reserved, 4u);
        std::memcpy(reply.data() + 20u, &replyId, 4u);
        replyPort->second.messages.push_back(std::move(reply));
        return true;
    };

    const auto queueTaskSpecialPortReply = [&](const std::vector<uint8_t>& request,
                                                    uint32_t replyName) -> bool {
        if (replyName == 0 || request.size() < 36u) return false;
        auto replyPort = machPorts_.find(replyName);
        if (replyPort == machPorts_.end() || replyPort->second.receiveRefs == 0) {
            return false;
        }

        uint32_t requestId = 0;
        uint32_t whichPort = 0;
        std::memcpy(&requestId, request.data() + 20u, sizeof(requestId));
        std::memcpy(&whichPort, request.data() + 32u, sizeof(whichPort));
        if (requestId != 3409u || whichPort != 4u) return false;

        constexpr uint32_t kDescriptorCount = 1u;
        constexpr uint32_t kCopySendPortDescriptor =
            (kMachMsgTypeCopySend << 16u); // disposition byte, type=port descriptor
        constexpr uint8_t kNdr[8] = {0u, 0u, 0u, 0u, 1u, 0u, 0u, 0u};

        std::vector<uint8_t> reply(52u, 0u);
        const uint32_t bits = kMachMessageComplex;
        const uint32_t size = static_cast<uint32_t>(reply.size());
        const uint32_t remote = 0u;
        const uint32_t local = replyName;
        const uint32_t reserved = 0u;
        const uint32_t replyId = 3509u;
        std::memcpy(reply.data(), &bits, 4u);
        std::memcpy(reply.data() + 4u, &size, 4u);
        std::memcpy(reply.data() + 8u, &remote, 4u);
        std::memcpy(reply.data() + 12u, &local, 4u);
        std::memcpy(reply.data() + 16u, &reserved, 4u);
        std::memcpy(reply.data() + 20u, &replyId, 4u);
        std::memcpy(reply.data() + 24u, &kDescriptorCount, 4u);
        std::memcpy(reply.data() + 28u, &kBootstrapPort, 4u);
        std::memcpy(reply.data() + 36u, &kCopySendPortDescriptor, 4u);
        std::memcpy(reply.data() + 40u, kNdr, sizeof(kNdr));
        std::memcpy(reply.data() + 48u, &kKernSuccess, 4u);
        replyPort->second.messages.push_back(std::move(reply));
        return true;
    };

    const auto queueBootstrapLookupReply = [&](const std::vector<uint8_t>& request,
                                                     uint32_t replyName) -> bool {
        if (replyName == 0 || request.size() < 160u) return false;
        auto replyPort = machPorts_.find(replyName);
        if (replyPort == machPorts_.end() || replyPort->second.receiveRefs == 0) {
            return false;
        }

        uint32_t requestId = 0;
        std::memcpy(&requestId, request.data() + 20u, sizeof(requestId));
        if (requestId != 404u) return false;

        const char* serviceBytes =
            reinterpret_cast<const char*>(request.data() + 32u);
        size_t serviceLength = 0;
        while (serviceLength < 128u && serviceBytes[serviceLength] != '\0') {
            ++serviceLength;
        }
        if (serviceLength == 128u) return false;
        const std::string serviceName(serviceBytes, serviceLength);

        uint32_t servicePort = 0;
        if (serviceName == "com.apple.system.logger") {
            servicePort = kSystemLoggerPort;
        } else if (serviceName == "com.apple.system.notification_center") {
            servicePort = kNotificationCenterPort;
        } else if (serviceName == "com.apple.cfprefsd.daemon") {
            servicePort = kCfprefsdPort;
        }

        constexpr uint8_t kNdr[8] = {0u, 0u, 0u, 0u, 1u, 0u, 0u, 0u};
        constexpr uint32_t kBootstrapUnknownService = 1102u;
        if (servicePort == 0) {
            std::vector<uint8_t> reply(36u, 0u);
            const uint32_t size = static_cast<uint32_t>(reply.size());
            const uint32_t local = replyName;
            const uint32_t replyId = 504u;
            std::memcpy(reply.data() + 4u, &size, 4u);
            std::memcpy(reply.data() + 12u, &local, 4u);
            std::memcpy(reply.data() + 20u, &replyId, 4u);
            std::memcpy(reply.data() + 24u, kNdr, sizeof(kNdr));
            std::memcpy(reply.data() + 32u, &kBootstrapUnknownService, 4u);
            replyPort->second.messages.push_back(std::move(reply));
            return true;
        }

        constexpr uint32_t kDescriptorCount = 1u;
        constexpr uint32_t kCopySendPortDescriptor =
            (kMachMsgTypeCopySend << 16u);
        std::vector<uint8_t> reply(52u, 0u);
        const uint32_t bits = kMachMessageComplex;
        const uint32_t size = static_cast<uint32_t>(reply.size());
        const uint32_t local = replyName;
        const uint32_t replyId = 504u;
        std::memcpy(reply.data(), &bits, 4u);
        std::memcpy(reply.data() + 4u, &size, 4u);
        std::memcpy(reply.data() + 12u, &local, 4u);
        std::memcpy(reply.data() + 20u, &replyId, 4u);
        std::memcpy(reply.data() + 24u, &kDescriptorCount, 4u);
        std::memcpy(reply.data() + 28u, &servicePort, 4u);
        std::memcpy(reply.data() + 36u, &kCopySendPortDescriptor, 4u);
        std::memcpy(reply.data() + 40u, kNdr, sizeof(kNdr));
        std::memcpy(reply.data() + 48u, &kKernSuccess, 4u);
        replyPort->second.messages.push_back(std::move(reply));
        return true;
    };

    const auto queueServiceMigReply = [&](uint32_t destination,
                                                   const std::vector<uint8_t>& request,
                                                   uint32_t replyName) -> bool {
        if (destination != kSystemLoggerPort &&
            destination != kNotificationCenterPort &&
            destination != kCfprefsdPort) {
            return false;
        }
        if (request.size() < kMachHeaderSize) return true;

        uint32_t requestId = 0;
        std::memcpy(&requestId, request.data() + 20u, sizeof(requestId));

        const auto queueInlineReply = [&](int32_t returnCode,
                                          const std::vector<uint32_t>& words) {
            if (replyName == 0) return;
            auto replyPort = machPorts_.find(replyName);
            if (replyPort == machPorts_.end() || replyPort->second.receiveRefs == 0) return;
            constexpr uint8_t kNdr[8] = {0u, 0u, 0u, 0u, 1u, 0u, 0u, 0u};
            std::vector<uint8_t> reply(36u + words.size() * 4u, 0u);
            const uint32_t size = static_cast<uint32_t>(reply.size());
            const uint32_t local = replyName;
            const uint32_t replyId = requestId + 100u;
            std::memcpy(reply.data() + 4u, &size, 4u);
            std::memcpy(reply.data() + 12u, &local, 4u);
            std::memcpy(reply.data() + 20u, &replyId, 4u);
            std::memcpy(reply.data() + 24u, kNdr, sizeof(kNdr));
            std::memcpy(reply.data() + 32u, &returnCode, 4u);
            if (!words.empty()) std::memcpy(reply.data() + 36u, words.data(), words.size() * 4u);
            replyPort->second.messages.push_back(std::move(reply));
        };
        const auto tokenAt32 = [&]() -> int32_t {
            int32_t token = 0;
            if (request.size() >= 36u) std::memcpy(&token, request.data() + 32u, 4u);
            return token;
        };
        constexpr int32_t kMigBadId = -303;
        constexpr uint32_t kNotifyOk = 0u;
        constexpr uint32_t kNotifyInvalidToken = 2u;

        if (destination != kNotificationCenterPort) {
            queueInlineReply(kMigBadId, {});
            return true;
        }

        switch (requestId) {
            case 1002u: { // check(token) -> check,status and clear pending
                const int32_t token = tokenAt32();
                auto it = notifyRegistrations_.find(token);
                if (it == notifyRegistrations_.end()) {
                    const uint32_t status = canceledNotifyTokens_.count(token) != 0u
                                                ? kNotifyInvalidToken
                                                : kNotifyOk;
                    queueInlineReply(0, {0u, status});
                } else {
                    const uint32_t pending = (!it->second.suspended && it->second.pending) ? 1u : 0u;
                    if (pending != 0u) it->second.pending = false;
                    queueInlineReply(0, {pending, kNotifyOk});
                }
                return true;
            }
            case 1003u: { // get_state(token)
                const int32_t token = tokenAt32();
                auto it = notifyRegistrations_.find(token);
                if (it == notifyRegistrations_.end()) {
                    queueInlineReply(0, {0u, 0u, kNotifyInvalidToken});
                } else {
                    queueInlineReply(0, {static_cast<uint32_t>(it->second.state),
                                         static_cast<uint32_t>(it->second.state >> 32u),
                                         kNotifyOk});
                }
                return true;
            }
            case 1004u:
            case 1005u: {
                const int32_t token = tokenAt32();
                auto it = notifyRegistrations_.find(token);
                const uint32_t status = it == notifyRegistrations_.end() ? kNotifyInvalidToken : kNotifyOk;
                if (it != notifyRegistrations_.end()) it->second.suspended = requestId == 1004u;
                queueInlineReply(0, {status});
                return true;
            }
            case 1009u: { // post by stable name id, one-way
                if (request.size() >= 40u) {
                    uint64_t nameId = 0;
                    std::memcpy(&nameId, request.data() + 32u, 8u);
                    for (auto& entry : notifyRegistrations_) {
                        if (entry.second.nameId == nameId) entry.second.pending = true;
                    }
                }
                return true;
            }
            case 1011u: { // fixed-name compatibility form: name[128] at 32, token at 160
                if (request.size() < 164u) return true;
                const char* nameBytes = reinterpret_cast<const char*>(request.data() + 32u);
                size_t length = 0;
                while (length < 128u && nameBytes[length] != '\0') ++length;
                if (length == 0u || length == 128u) return true;
                int32_t token = 0;
                std::memcpy(&token, request.data() + 160u, 4u);
                const std::string name(nameBytes, length);
                uint64_t nameId = 0;
                auto nameIt = notifyNameIds_.find(name);
                if (nameIt == notifyNameIds_.end()) {
                    nameId = nextNotifyNameId_++;
                    notifyNameIds_.emplace(name, nameId);
                } else {
                    nameId = nameIt->second;
                }
                canceledNotifyTokens_.erase(token);
                notifyRegistrations_[token] = NotifyRegistration{name, nameId, 0u, false, false};
                return true;
            }
            case 1016u: {
                const int32_t token = tokenAt32();
                notifyRegistrations_.erase(token);
                canceledNotifyTokens_.insert(token);
                return true;
            }
            case 1018u: { // get_state_3(token) -> state,nid,status
                const int32_t token = tokenAt32();
                auto it = notifyRegistrations_.find(token);
                if (it == notifyRegistrations_.end()) {
                    queueInlineReply(0, {0u, 0u, UINT32_MAX, UINT32_MAX, kNotifyInvalidToken});
                } else {
                    queueInlineReply(0, {static_cast<uint32_t>(it->second.state),
                                         static_cast<uint32_t>(it->second.state >> 32u),
                                         static_cast<uint32_t>(it->second.nameId),
                                         static_cast<uint32_t>(it->second.nameId >> 32u),
                                         kNotifyOk});
                }
                return true;
            }
            case 1020u: { // set_state_3(token,state) -> nid,status
                if (request.size() < 44u) { queueInlineReply(kMigBadId, {}); return true; }
                const int32_t token = tokenAt32();
                uint64_t value = 0;
                std::memcpy(&value, request.data() + 36u, 8u);
                auto it = notifyRegistrations_.find(token);
                if (it == notifyRegistrations_.end()) {
                    queueInlineReply(0, {UINT32_MAX, UINT32_MAX, kNotifyInvalidToken});
                } else {
                    it->second.state = value;
                    queueInlineReply(0, {static_cast<uint32_t>(it->second.nameId),
                                         static_cast<uint32_t>(it->second.nameId >> 32u),
                                         kNotifyOk});
                }
                return true;
            }
            case 1023u:
                queueInlineReply(0, {3u, 42u, kNotifyOk});
                return true;
            default:
                queueInlineReply(kMigBadId, {});
                return true;
        }
    };

    switch (number) {
        case 16: {
            if (!validTask(state.r[0])) {
                return ok(number, static_cast<int32_t>(kKernInvalidTask),
                          "mach_port_allocate invalid task");
            }
            if (state.r[1] != kMachPortRightReceive) {
                return ok(number, static_cast<int32_t>(kKernInvalidRight),
                          "mach_port_allocate unsupported right");
            }
            if (!memory_.write) {
                return ok(number, static_cast<int32_t>(kKernInvalidArgument),
                          "mach_port_allocate memory callback");
            }
            const uint32_t name = allocateReceivePort();
            if (!memory_.write(state.r[2], &name, sizeof(name))) {
                machPorts_.erase(name);
                return ok(number, static_cast<int32_t>(kKernInvalidArgument),
                          "mach_port_allocate guest write");
            }
            return ok(number, static_cast<int32_t>(kKernSuccess),
                      "mach_port_allocate");
        }
        case 17: {
            if (!validTask(state.r[0])) {
                return ok(number, static_cast<int32_t>(kKernInvalidTask),
                          "mach_port_destroy invalid task");
            }
            const auto it = machPorts_.find(state.r[1]);
            if (it == machPorts_.end()) {
                return ok(number, static_cast<int32_t>(kKernInvalidName),
                          "mach_port_destroy invalid name");
            }
            if (it->second.immortal) {
                return ok(number, static_cast<int32_t>(kKernInvalidRight),
                          "mach_port_destroy immortal port");
            }
            machPorts_.erase(it);
            return ok(number, static_cast<int32_t>(kKernSuccess),
                      "mach_port_destroy");
        }
        case 18: {
            if (!validTask(state.r[0])) {
                return ok(number, static_cast<int32_t>(kKernInvalidTask),
                          "mach_port_deallocate invalid task");
            }
            auto it = machPorts_.find(state.r[1]);
            if (it == machPorts_.end()) {
                return ok(number, static_cast<int32_t>(kKernInvalidName),
                          "mach_port_deallocate invalid name");
            }
            uint32_t result = kKernInvalidRight;
            if (it->second.sendRefs != 0) {
                result = adjustRefs(state.r[1], kMachPortRightSend, -1);
            } else if (it->second.sendOnceRefs != 0) {
                result = adjustRefs(state.r[1], kMachPortRightSendOnce, -1);
            }
            return ok(number, static_cast<int32_t>(result),
                      "mach_port_deallocate");
        }
        case 19: {
            if (!validTask(state.r[0])) {
                return ok(number, static_cast<int32_t>(kKernInvalidTask),
                          "mach_port_mod_refs invalid task");
            }
            const uint32_t result = adjustRefs(state.r[1],
                                               state.r[2],
                                               static_cast<int32_t>(state.r[3]));
            return ok(number, static_cast<int32_t>(result), "mach_port_mod_refs");
        }
        case 21: {
            if (!validTask(state.r[0])) {
                return ok(number, static_cast<int32_t>(kKernInvalidTask),
                          "mach_port_insert_right invalid task");
            }
            const uint32_t name = state.r[1];
            const uint32_t poly = state.r[2];
            const uint32_t disposition = state.r[3];
            auto it = machPorts_.find(name);
            if (name == 0 || name != poly || it == machPorts_.end()) {
                return ok(number, static_cast<int32_t>(kKernInvalidName),
                          "mach_port_insert_right invalid name");
            }
            uint32_t result = kKernInvalidValue;
            if (disposition == kMachMsgTypeMakeSend) {
                result = it->second.receiveRefs != 0
                             ? adjustRefs(name, kMachPortRightSend, 1)
                             : kKernInvalidRight;
            } else if (disposition == kMachMsgTypeMakeSendOnce) {
                result = it->second.receiveRefs != 0
                             ? adjustRefs(name, kMachPortRightSendOnce, 1)
                             : kKernInvalidRight;
            } else if (disposition == kMachMsgTypeCopySend) {
                result = it->second.sendRefs != 0
                             ? adjustRefs(name, kMachPortRightSend, 1)
                             : kKernInvalidRight;
            } else if (disposition == kMachMsgTypeMoveSend) {
                result = it->second.sendRefs != 0 ? kKernSuccess : kKernInvalidRight;
            } else if (disposition == kMachMsgTypeMoveSendOnce) {
                result = it->second.sendOnceRefs != 0 ? kKernSuccess : kKernInvalidRight;
            }
            return ok(number, static_cast<int32_t>(result),
                      "mach_port_insert_right");
        }
        case 26: {
            const uint32_t name = allocateReceivePort();
            return ok(number, static_cast<int32_t>(name), "mach_reply_port");
        }
        case 27:
            return ok(number, static_cast<int32_t>(kThreadPort), "thread_self_trap");
        case 28:
            return ok(number, static_cast<int32_t>(kTaskPort), "task_self_trap");
        case 29:
            return ok(number, static_cast<int32_t>(kHostPort), "host_self_trap");
        case 31: {
            const uint32_t messageAddress = state.r[0];
            const uint32_t options = state.r[1];
            const uint32_t sendSize = state.r[2];
            const uint32_t receiveSize = state.r[3];
            const uint32_t receiveName = state.r[4];
            const bool send = (options & kMachSendMsg) != 0;
            const bool receive = (options & kMachReceiveMsg) != 0;
            if (!send && !receive) {
                return ok(number, static_cast<int32_t>(kKernSuccess), "mach_msg no-op");
            }

            if (send) {
                if (sendSize < kMachHeaderSize) {
                    return ok(number, static_cast<int32_t>(kMachSendMessageTooSmall),
                              "mach_msg send too small");
                }
                if (sendSize > kMaximumMachMessage || !memory_.read) {
                    return ok(number, static_cast<int32_t>(kMachSendInvalidData),
                              "mach_msg invalid send data");
                }
                std::vector<uint8_t> message(sendSize);
                if (!memory_.read(messageAddress, message.data(), message.size())) {
                    return ok(number, static_cast<int32_t>(kMachSendInvalidData),
                              "mach_msg send guest read");
                }
                uint32_t bits = 0;
                uint32_t headerSize = 0;
                uint32_t destination = 0;
                std::memcpy(&bits, message.data(), sizeof(bits));
                std::memcpy(&headerSize, message.data() + 4u, sizeof(headerSize));
                std::memcpy(&destination, message.data() + 8u, sizeof(destination));
                if (headerSize < kMachHeaderSize || headerSize > sendSize ||
                    (bits & kMachMessageComplex) != 0) {
                    return ok(number, static_cast<int32_t>(kMachSendInvalidData),
                              "mach_msg unsupported send header");
                }
                auto port = machPorts_.find(destination);
                if (destination == 0 || port == machPorts_.end()) {
                    return ok(number, static_cast<int32_t>(kMachSendInvalidDestination),
                              "mach_msg invalid destination");
                }
                const uint32_t disposition = bits & kMachRemoteDispositionMask;
                bool consumeSend = false;
                bool consumeSendOnce = false;
                bool hasRight = false;
                if (disposition == kMachMsgTypeCopySend) {
                    hasRight = port->second.sendRefs != 0;
                } else if (disposition == kMachMsgTypeMoveSend) {
                    hasRight = port->second.sendRefs != 0;
                    consumeSend = hasRight;
                } else if (disposition == kMachMsgTypeMoveSendOnce) {
                    hasRight = port->second.sendOnceRefs != 0;
                    consumeSendOnce = hasRight;
                } else if (disposition == kMachMsgTypeMakeSend) {
                    hasRight = port->second.receiveRefs != 0;
                } else if (disposition == kMachMsgTypeMakeSendOnce) {
                    hasRight = port->second.receiveRefs != 0;
                }
                if (!hasRight) {
                    return ok(number, static_cast<int32_t>(kMachSendInvalidRight),
                              "mach_msg missing send right");
                }
                message.resize(headerSize);
                uint32_t replyName = 0;
                std::memcpy(&replyName, message.data() + 12u, sizeof(replyName));
                const bool handledHostMig =
                    destination == kHostPort && queueHostMigReply(message, replyName);
                const bool handledTaskSpecialPort =
                    destination == kTaskPort &&
                    queueTaskSpecialPortReply(message, replyName);
                const bool handledBootstrapLookup =
                    destination == kBootstrapPort &&
                    queueBootstrapLookupReply(message, replyName);
                const bool handledServiceMig =
                    queueServiceMigReply(destination, message, replyName);
                if (!handledHostMig && !handledTaskSpecialPort &&
                    !handledBootstrapLookup && !handledServiceMig) {
                    port->second.messages.push_back(std::move(message));
                }
                if (consumeSend) {
                    (void)adjustRefs(destination, kMachPortRightSend, -1);
                } else if (consumeSendOnce) {
                    (void)adjustRefs(destination, kMachPortRightSendOnce, -1);
                }
            }

            if (receive) {
                auto port = machPorts_.find(receiveName);
                if (receiveName == 0 || port == machPorts_.end() ||
                    port->second.receiveRefs == 0) {
                    return ok(number, static_cast<int32_t>(kMachReceiveInvalidName),
                              "mach_msg invalid receive name");
                }
                if (port->second.messages.empty()) {
                    return ok(number, static_cast<int32_t>(kMachReceiveTimedOut),
                              "mach_msg receive empty");
                }
                const std::vector<uint8_t>& message = port->second.messages.front();
                if (receiveSize < message.size()) {
                    return ok(number, static_cast<int32_t>(kMachReceiveTooLarge),
                              "mach_msg receive too large");
                }
                if (!memory_.write ||
                    !memory_.write(messageAddress, message.data(), message.size())) {
                    return ok(number, static_cast<int32_t>(kMachSendInvalidData),
                              "mach_msg receive guest write");
                }
                port->second.messages.pop_front();
            }
            return ok(number, static_cast<int32_t>(kKernSuccess), "mach_msg_trap");
        }
        default: {
            TrapResult result;
            result.number = number;
            result.detail = "unsupported Mach trap";
            return result;
        }
    }
}

} // namespace lc32
