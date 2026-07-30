#!/usr/bin/env python3
from pathlib import Path

source_path = Path("runtime/LC32DarwinSyscalls.cpp")
source = source_path.read_text()
constant_needle = """constexpr int kMaximumAdvice = 9;
"""
constant_replacement = """constexpr int kMaximumAdvice = 9;

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
"""
if source.count(constant_needle) != 1:
    raise SystemExit("sysctl constant insertion point not unique")
source = source.replace(constant_needle, constant_replacement, 1)

case_needle = """        case 338: {
"""
case_replacement = """        case 202: {
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
        case 338: {
"""
if source.count(case_needle) != 1:
    raise SystemExit("sysctl case insertion point not unique")
source_path.write_text(source.replace(case_needle, case_replacement, 1))

test_path = Path("runtime/tests/LC32DarwinSyscallsTests.cpp")
test = test_path.read_text()
constant_test_needle = """    constexpr uint32_t kMincoreAddress = 0x1400u;
    constexpr uint32_t kStackAddress = 0x3000u;
"""
constant_test_replacement = """    constexpr uint32_t kMincoreAddress = 0x1400u;
    constexpr uint32_t kSysctlNameAddress = 0x1600u;
    constexpr uint32_t kSysctlLengthAddress = 0x1640u;
    constexpr uint32_t kSysctlOutputAddress = 0x1680u;
    constexpr uint32_t kStackAddress = 0x3000u;
"""
if test.count(constant_test_needle) != 1:
    raise SystemExit("sysctl test constant insertion point not unique")
test = test.replace(constant_test_needle, constant_test_replacement, 1)

test_needle = """    const auto badMincoreVector = rooted.dispatch(state, 0x80u, false);
    assert(badMincoreVector.handled && badMincoreVector.errorNumber == EFAULT);

    state = {};
    state.r[12] = 92;
"""
test_replacement = """    const auto badMincoreVector = rooted.dispatch(state, 0x80u, false);
    assert(badMincoreVector.handled && badMincoreVector.errorNumber == EFAULT);

    const auto sysctlGuest = [&](int32_t rootMib,
                                 int32_t leafMib,
                                 uint32_t outputAddress,
                                 uint32_t outputLength,
                                 uint32_t newAddress = 0,
                                 uint32_t newLength = 0) {
        const int32_t mib[2] = {rootMib, leafMib};
        std::memcpy(lowMemory.data() + kSysctlNameAddress, mib, sizeof(mib));
        std::memcpy(lowMemory.data() + kSysctlLengthAddress,
                    &outputLength,
                    sizeof(outputLength));
        std::memcpy(lowMemory.data() + kStackAddress,
                    &newAddress,
                    sizeof(newAddress));
        std::memcpy(lowMemory.data() + kStackAddress + sizeof(uint32_t),
                    &newLength,
                    sizeof(newLength));
        state = {};
        state.r[12] = 202;
        state.r[0] = kSysctlNameAddress;
        state.r[1] = 2u;
        state.r[2] = outputAddress;
        state.r[3] = kSysctlLengthAddress;
        state.r[13] = kStackAddress;
        return rooted.dispatch(state, 0x80u, false);
    };

    const auto pageSizeQuery = sysctlGuest(6, 7, 0, 0);
    assert(pageSizeQuery.handled && pageSizeQuery.errorNumber == 0);
    uint32_t sysctlLength = 0;
    std::memcpy(&sysctlLength,
                lowMemory.data() + kSysctlLengthAddress,
                sizeof(sysctlLength));
    assert(sysctlLength == sizeof(int32_t));

    const auto pageSizeRead =
        sysctlGuest(6, 7, kSysctlOutputAddress, sizeof(int32_t));
    assert(pageSizeRead.handled && pageSizeRead.errorNumber == 0);
    int32_t guestPageSize = 0;
    std::memcpy(&guestPageSize,
                lowMemory.data() + kSysctlOutputAddress,
                sizeof(guestPageSize));
    assert(guestPageSize == 4096);

    std::memset(lowMemory.data() + kSysctlOutputAddress, 0, 32u);
    const auto osType = sysctlGuest(1, 1, kSysctlOutputAddress, 32u);
    assert(osType.handled && osType.errorNumber == 0);
    assert(std::string(reinterpret_cast<char*>(
               lowMemory.data() + kSysctlOutputAddress)) == "Darwin");

    const auto memorySize = sysctlGuest(6, 24, kSysctlOutputAddress, 8u);
    assert(memorySize.handled && memorySize.errorNumber == 0);
    uint64_t guestMemorySize = 0;
    std::memcpy(&guestMemorySize,
                lowMemory.data() + kSysctlOutputAddress,
                sizeof(guestMemorySize));
    assert(guestMemorySize == 1024ull * 1024ull * 1024ull);

    lowMemory[kSysctlOutputAddress] = 0x5au;
    const auto shortOutput = sysctlGuest(1, 1, kSysctlOutputAddress, 2u);
    assert(shortOutput.handled && shortOutput.errorNumber == ENOMEM);
    std::memcpy(&sysctlLength,
                lowMemory.data() + kSysctlLengthAddress,
                sizeof(sysctlLength));
    assert(sysctlLength == 7u);
    assert(lowMemory[kSysctlOutputAddress] == 0x5au);

    const auto writeAttempt =
        sysctlGuest(6, 7, kSysctlOutputAddress, 4u, kReadAddress, 4u);
    assert(writeAttempt.handled && writeAttempt.errorNumber == EPERM);

    const auto missingSysctl = sysctlGuest(6, 99, kSysctlOutputAddress, 4u);
    assert(missingSysctl.handled && missingSysctl.errorNumber == ENOENT);

    state = {};
    state.r[12] = 202;
    state.r[0] = static_cast<uint32_t>(lowMemory.size() - 4u);
    state.r[1] = 2u;
    state.r[2] = kSysctlOutputAddress;
    state.r[3] = kSysctlLengthAddress;
    state.r[13] = kStackAddress;
    const auto badSysctlName = rooted.dispatch(state, 0x80u, false);
    assert(badSysctlName.handled && badSysctlName.errorNumber == EFAULT);

    const int32_t validMib[2] = {6, 7};
    std::memcpy(lowMemory.data() + kSysctlNameAddress,
                validMib,
                sizeof(validMib));
    state = {};
    state.r[12] = 202;
    state.r[0] = kSysctlNameAddress;
    state.r[1] = 2u;
    state.r[2] = kSysctlOutputAddress;
    state.r[3] = kSysctlLengthAddress;
    state.r[13] = static_cast<uint32_t>(lowMemory.size() - 4u);
    const auto badSysctlStack = rooted.dispatch(state, 0x80u, false);
    assert(badSysctlStack.handled && badSysctlStack.errorNumber == EFAULT);

    state = {};
    state.r[12] = 92;
"""
if test.count(test_needle) != 1:
    raise SystemExit("sysctl test insertion point not unique")
test_path.write_text(test.replace(test_needle, test_replacement, 1))
