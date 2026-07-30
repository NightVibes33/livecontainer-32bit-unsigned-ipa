#!/usr/bin/env python3
from pathlib import Path

source_path = Path("runtime/LC32DarwinSyscalls.cpp")
source = source_path.read_text()
constant_needle = """constexpr uint32_t kCtlMaximumName = 12u;
"""
constant_replacement = """constexpr uint32_t kCtlMaximumName = 12u;
constexpr uint32_t kRlimitPosixFlag = 0x1000u;
constexpr uint64_t kRlimitInfinity = (1ull << 63u) - 1u;
constexpr uint32_t kGuestDescriptorLimit = 10240u;
"""
if source.count(constant_needle) != 1:
    raise SystemExit("rlimit constant insertion point not unique")
source = source.replace(constant_needle, constant_replacement, 1)

struct_needle = """struct GuestStat64 {
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
"""
struct_replacement = struct_needle + """

struct GuestRlimit {
    uint64_t current = 0;
    uint64_t maximum = 0;
};
"""
if source.count(struct_needle) != 1:
    raise SystemExit("rlimit struct insertion point not unique")
source = source.replace(struct_needle, struct_replacement, 1)

assert_needle = """static_assert(sizeof(GuestStat64) == 108, "unexpected iOS 6 user32_stat64 layout");
"""
assert_replacement = assert_needle + """static_assert(sizeof(GuestRlimit) == 16, "unexpected ARMv7 rlimit layout");
"""
if source.count(assert_needle) != 1:
    raise SystemExit("rlimit assertion insertion point not unique")
source = source.replace(assert_needle, assert_replacement, 1)

getdtablesize_needle = """        case 92: {
"""
getdtablesize_replacement = """        case 89:
            return ok(number,
                      static_cast<int32_t>(kGuestDescriptorLimit),
                      "getdtablesize");
        case 92: {
"""
if source.count(getdtablesize_needle) != 1:
    raise SystemExit("getdtablesize insertion point not unique")
source = source.replace(getdtablesize_needle, getdtablesize_replacement, 1)

pread_needle = """        case 197: {
"""
pread_replacement = """        case 153:
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
"""
if source.count(pread_needle) != 1:
    raise SystemExit("pread insertion point not unique")
source_path.write_text(source.replace(pread_needle, pread_replacement, 1))

test_path = Path("runtime/tests/LC32DarwinSyscallsTests.cpp")
test = test_path.read_text()
constant_test_needle = """    constexpr uint32_t kSysctlOutputAddress = 0x1680u;
    constexpr uint32_t kStackAddress = 0x3000u;
"""
constant_test_replacement = """    constexpr uint32_t kSysctlOutputAddress = 0x1680u;
    constexpr uint32_t kRlimitAddress = 0x1700u;
    constexpr uint32_t kStackAddress = 0x3000u;
"""
if test.count(constant_test_needle) != 1:
    raise SystemExit("pread test constant insertion point not unique")
test = test.replace(constant_test_needle, constant_test_replacement, 1)

test_needle = """    const auto badSysctlStack = rooted.dispatch(state, 0x80u, false);
    assert(badSysctlStack.handled && badSysctlStack.errorNumber == EFAULT);

    state = {};
    state.r[12] = 92;
"""
test_replacement = """    const auto badSysctlStack = rooted.dispatch(state, 0x80u, false);
    assert(badSysctlStack.handled && badSysctlStack.errorNumber == EFAULT);

    uint32_t seekWhence = SEEK_SET;
    std::memcpy(lowMemory.data() + kStackAddress,
                &seekWhence,
                sizeof(seekWhence));
    state = {};
    state.r[12] = 199;
    state.r[0] = static_cast<uint32_t>(guestFd);
    state.r[2] = 3u;
    state.r[3] = 0u;
    state.r[13] = kStackAddress;
    const auto positioned = rooted.dispatch(state, 0x80u, false);
    assert(positioned.handled && positioned.errorNumber == 0);
    assert(state.r[0] == 3u && state.r[1] == 0u);

    uint32_t preadOffsetLow = 7u;
    uint32_t preadOffsetHigh = 0u;
    std::memcpy(lowMemory.data() + kStackAddress,
                &preadOffsetLow,
                sizeof(preadOffsetLow));
    std::memcpy(lowMemory.data() + kStackAddress + sizeof(uint32_t),
                &preadOffsetHigh,
                sizeof(preadOffsetHigh));
    state = {};
    state.r[12] = 153;
    state.r[0] = static_cast<uint32_t>(guestFd);
    state.r[1] = kReadAddress;
    state.r[2] = 5u;
    state.r[13] = kStackAddress;
    const auto positionedRead = rooted.dispatch(state, 0x80u, false);
    assert(positionedRead.handled && positionedRead.errorNumber == 0);
    assert(state.r[0] == 5u);
    assert(std::string(reinterpret_cast<char*>(lowMemory.data() + kReadAddress),
                       5u) == "dylib");

    seekWhence = SEEK_CUR;
    std::memcpy(lowMemory.data() + kStackAddress,
                &seekWhence,
                sizeof(seekWhence));
    state = {};
    state.r[12] = 199;
    state.r[0] = static_cast<uint32_t>(guestFd);
    state.r[2] = 0u;
    state.r[3] = 0u;
    state.r[13] = kStackAddress;
    const auto unchangedPosition = rooted.dispatch(state, 0x80u, false);
    assert(unchangedPosition.handled && unchangedPosition.errorNumber == 0);
    assert(state.r[0] == 3u && state.r[1] == 0u);

    preadOffsetLow = 0u;
    preadOffsetHigh = 0u;
    std::memcpy(lowMemory.data() + kStackAddress,
                &preadOffsetLow,
                sizeof(preadOffsetLow));
    std::memcpy(lowMemory.data() + kStackAddress + sizeof(uint32_t),
                &preadOffsetHigh,
                sizeof(preadOffsetHigh));
    state = {};
    state.r[12] = 414;
    state.r[0] = static_cast<uint32_t>(guestFd);
    state.r[1] = kReadAddress;
    state.r[2] = 6u;
    state.r[13] = kStackAddress;
    const auto noCancelRead = rooted.dispatch(state, 0x80u, false);
    assert(noCancelRead.handled && noCancelRead.errorNumber == 0);
    assert(std::string(reinterpret_cast<char*>(lowMemory.data() + kReadAddress),
                       6u) == "legacy");

    preadOffsetHigh = 0xffffffffu;
    std::memcpy(lowMemory.data() + kStackAddress + sizeof(uint32_t),
                &preadOffsetHigh,
                sizeof(preadOffsetHigh));
    state = {};
    state.r[12] = 153;
    state.r[0] = static_cast<uint32_t>(guestFd);
    state.r[1] = kReadAddress;
    state.r[2] = 1u;
    state.r[13] = kStackAddress;
    const auto negativePread = rooted.dispatch(state, 0x80u, false);
    assert(negativePread.handled && negativePread.errorNumber == EINVAL);

    state = {};
    state.r[12] = 153;
    state.r[0] = static_cast<uint32_t>(guestFd);
    state.r[1] = kReadAddress;
    state.r[2] = 1u;
    state.r[13] = static_cast<uint32_t>(lowMemory.size() - 4u);
    const auto badPreadStack = rooted.dispatch(state, 0x80u, false);
    assert(badPreadStack.handled && badPreadStack.errorNumber == EFAULT);

    state = {};
    state.r[12] = 89;
    const auto descriptorLimit = rooted.dispatch(state, 0x80u, false);
    assert(descriptorLimit.handled && descriptorLimit.errorNumber == 0);
    assert(state.r[0] == 10240u);

    state = {};
    state.r[12] = 194;
    state.r[0] = 3u;
    state.r[1] = kRlimitAddress;
    const auto stackLimit = rooted.dispatch(state, 0x80u, false);
    assert(stackLimit.handled && stackLimit.errorNumber == 0);
    uint64_t stackCurrent = 0;
    uint64_t stackMaximum = 0;
    std::memcpy(&stackCurrent,
                lowMemory.data() + kRlimitAddress,
                sizeof(stackCurrent));
    std::memcpy(&stackMaximum,
                lowMemory.data() + kRlimitAddress + sizeof(uint64_t),
                sizeof(stackMaximum));
    assert(stackCurrent == 8ull * 1024ull * 1024ull);
    assert(stackMaximum == 64ull * 1024ull * 1024ull);

    state = {};
    state.r[12] = 194;
    state.r[0] = 0x1000u | 8u;
    state.r[1] = kRlimitAddress;
    const auto fileLimit = rooted.dispatch(state, 0x80u, false);
    assert(fileLimit.handled && fileLimit.errorNumber == 0);
    uint64_t fileCurrent = 0;
    uint64_t fileMaximum = 0;
    std::memcpy(&fileCurrent,
                lowMemory.data() + kRlimitAddress,
                sizeof(fileCurrent));
    std::memcpy(&fileMaximum,
                lowMemory.data() + kRlimitAddress + sizeof(uint64_t),
                sizeof(fileMaximum));
    assert(fileCurrent == 256u && fileMaximum == 10240u);

    state = {};
    state.r[12] = 194;
    state.r[0] = 99u;
    state.r[1] = kRlimitAddress;
    const auto badLimitResource = rooted.dispatch(state, 0x80u, false);
    assert(badLimitResource.handled && badLimitResource.errorNumber == EINVAL);

    state = {};
    state.r[12] = 194;
    state.r[0] = 3u;
    state.r[1] = static_cast<uint32_t>(lowMemory.size() - 8u);
    const auto badLimitPointer = rooted.dispatch(state, 0x80u, false);
    assert(badLimitPointer.handled && badLimitPointer.errorNumber == EFAULT);

    state = {};
    state.r[12] = 92;
"""
if test.count(test_needle) != 1:
    raise SystemExit("pread test insertion point not unique")
test_path.write_text(test.replace(test_needle, test_replacement, 1))
