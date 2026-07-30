#!/usr/bin/env python3
from pathlib import Path

header_path = Path("runtime/LC32DarwinSyscalls.hpp")
header = header_path.read_text()
header_needle = """    bool resolveGuestPath(const std::string& guestPath,
                           std::string& hostPath,
                           int& errorNumber) const;
    int allocateGuestFd(int hostFd, uint32_t openFlags, uint32_t descriptorFlags);
"""
header_replacement = """    bool resolveGuestPath(const std::string& guestPath,
                           std::string& hostPath,
                           int& errorNumber) const;
    bool resolveGuestPathNoFollow(const std::string& guestPath,
                                   std::string& hostPath,
                                   int& errorNumber) const;
    int allocateGuestFd(int hostFd, uint32_t openFlags, uint32_t descriptorFlags);
"""
if header.count(header_needle) != 1:
    raise SystemExit("no-follow header insertion point not unique")
header_path.write_text(header.replace(header_needle, header_replacement, 1))

source_path = Path("runtime/LC32DarwinSyscalls.cpp")
source = source_path.read_text()
method_needle = "\nint DarwinSyscalls::allocateGuestFd"
method = r'''
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

'''
if source.count(method_needle) != 1:
    raise SystemExit("no-follow method insertion point not unique")
source = source.replace(method_needle, "\n" + method + "int DarwinSyscalls::allocateGuestFd", 1)

readlink_needle = """        case 47:
            return ok(number, static_cast<int32_t>(::getgid()), "getgid");
        case 65: {
"""
readlink_replacement = r'''        case 47:
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
'''
if source.count(readlink_needle) != 1:
    raise SystemExit("readlink syscall insertion point not unique")
source = source.replace(readlink_needle, readlink_replacement, 1)

lstat_needle = """        case 338: {
"""
lstat_replacement = r'''        case 340: {
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
'''
if source.count(lstat_needle) != 1:
    raise SystemExit("lstat64 syscall insertion point not unique")
source_path.write_text(source.replace(lstat_needle, lstat_replacement, 1))

test_path = Path("runtime/tests/LC32DarwinSyscallsTests.cpp")
test = test_path.read_text()
constant_needle = """    constexpr uint32_t kMincoreAddress = 0x1400u;
    constexpr uint32_t kSysctlNameAddress = 0x1600u;
"""
constant_replacement = """    constexpr uint32_t kMincoreAddress = 0x1400u;
    constexpr uint32_t kLinkReadAddress = 0x1800u;
    constexpr uint32_t kLinkStatAddress = 0x1c00u;
    constexpr uint32_t kSysctlNameAddress = 0x1600u;
"""
if test.count(constant_needle) != 1:
    raise SystemExit("readlink test constant insertion point not unique")
test = test.replace(constant_needle, constant_replacement, 1)

setup_needle = """    assert(::symlink("/etc/passwd", (root / "usr/lib/escape").c_str()) == 0);

    DarwinSyscalls rooted(syscallMemory, root.string());
"""
setup_replacement = """    assert(::symlink("/etc/passwd", (root / "usr/lib/escape").c_str()) == 0);
    assert(::symlink("libA.dylib", (root / "usr/lib/libAlias.dylib").c_str()) == 0);
    assert(::symlink("/etc", (root / "usr/outside").c_str()) == 0);

    DarwinSyscalls rooted(syscallMemory, root.string());
"""
if test.count(setup_needle) != 1:
    raise SystemExit("readlink test setup insertion point not unique")
test = test.replace(setup_needle, setup_replacement, 1)

test_needle = """    assert((mode & 0170000u) == 0100000u);
    assert(size == static_cast<int64_t>(payload.size()));

    state = {};
    state.r[12] = 5;
"""
test_replacement = r'''    assert((mode & 0170000u) == 0100000u);
    assert(size == static_cast<int64_t>(payload.size()));

    const std::string aliasTarget = "libA.dylib";
    putCString(kPathAddress, "/usr/lib/libAlias.dylib");
    std::memset(lowMemory.data() + kLinkReadAddress, 0x5a, 32u);
    state = {};
    state.r[12] = 58;
    state.r[0] = kPathAddress;
    state.r[1] = kLinkReadAddress;
    state.r[2] = 32u;
    const auto aliasReadlink = rooted.dispatch(state, 0x80u, false);
    assert(aliasReadlink.handled && aliasReadlink.errorNumber == 0);
    assert(aliasReadlink.returnValue == static_cast<int32_t>(aliasTarget.size()));
    assert(std::memcmp(lowMemory.data() + kLinkReadAddress,
                       aliasTarget.data(),
                       aliasTarget.size()) == 0);
    assert(lowMemory[kLinkReadAddress + aliasTarget.size()] == 0x5au);

    std::memset(lowMemory.data() + kLinkReadAddress, 0x5a, 8u);
    state = {};
    state.r[12] = 58;
    state.r[0] = kPathAddress;
    state.r[1] = kLinkReadAddress;
    state.r[2] = 4u;
    const auto shortReadlink = rooted.dispatch(state, 0x80u, false);
    assert(shortReadlink.handled && shortReadlink.errorNumber == 0);
    assert(shortReadlink.returnValue == 4);
    assert(std::memcmp(lowMemory.data() + kLinkReadAddress, "libA", 4u) == 0);
    assert(lowMemory[kLinkReadAddress + 4u] == 0x5au);

    std::memset(lowMemory.data() + kLinkStatAddress,
                0x5a,
                kGuestStat64Size + 1u);
    state = {};
    state.r[12] = 340;
    state.r[0] = kPathAddress;
    state.r[1] = kLinkStatAddress;
    const auto aliasLstat = rooted.dispatch(state, 0x80u, false);
    assert(aliasLstat.handled && aliasLstat.errorNumber == 0);
    std::memcpy(&mode,
                lowMemory.data() + kLinkStatAddress + kGuestStat64ModeOffset,
                sizeof(mode));
    std::memcpy(&size,
                lowMemory.data() + kLinkStatAddress + kGuestStat64SizeOffset,
                sizeof(size));
    assert((mode & 0170000u) == 0120000u);
    assert(size == static_cast<int64_t>(aliasTarget.size()));
    assert(lowMemory[kLinkStatAddress + kGuestStat64Size] == 0x5au);

    putCString(kPathAddress, "/usr/lib/libA.dylib");
    state = {};
    state.r[12] = 58;
    state.r[0] = kPathAddress;
    state.r[1] = kLinkReadAddress;
    state.r[2] = 32u;
    const auto regularReadlink = rooted.dispatch(state, 0x80u, false);
    assert(regularReadlink.handled && regularReadlink.errorNumber == EINVAL);

    putCString(kPathAddress, "/usr/lib/escape");
    std::memset(lowMemory.data() + kLinkReadAddress, 0x5a, 32u);
    state = {};
    state.r[12] = 58;
    state.r[0] = kPathAddress;
    state.r[1] = kLinkReadAddress;
    state.r[2] = 32u;
    const auto finalEscapeReadlink = rooted.dispatch(state, 0x80u, false);
    assert(finalEscapeReadlink.handled && finalEscapeReadlink.errorNumber == 0);
    assert(std::string(reinterpret_cast<char*>(lowMemory.data() + kLinkReadAddress),
                       static_cast<size_t>(finalEscapeReadlink.returnValue)) ==
           "/etc/passwd");

    state = {};
    state.r[12] = 340;
    state.r[0] = kPathAddress;
    state.r[1] = kLinkStatAddress;
    const auto finalEscapeLstat = rooted.dispatch(state, 0x80u, false);
    assert(finalEscapeLstat.handled && finalEscapeLstat.errorNumber == 0);

    putCString(kPathAddress, "/usr/outside/passwd");
    state = {};
    state.r[12] = 58;
    state.r[0] = kPathAddress;
    state.r[1] = kLinkReadAddress;
    state.r[2] = 32u;
    const auto parentEscapeReadlink = rooted.dispatch(state, 0x80u, false);
    assert(parentEscapeReadlink.handled && parentEscapeReadlink.errorNumber == EACCES);

    putCString(kPathAddress, "/usr/lib/libAlias.dylib");
    state = {};
    state.r[12] = 58;
    state.r[0] = kPathAddress;
    state.r[1] = kLinkReadAddress;
    state.r[2] = 0u;
    const auto zeroReadlink = rooted.dispatch(state, 0x80u, false);
    assert(zeroReadlink.handled && zeroReadlink.errorNumber == EINVAL);

    putCString(kPathAddress, "/usr/lib/libA.dylib");
    state = {};
    state.r[12] = 5;
'''
if test.count(test_needle) != 1:
    raise SystemExit("readlink test insertion point not unique")
test_path.write_text(test.replace(test_needle, test_replacement, 1))
