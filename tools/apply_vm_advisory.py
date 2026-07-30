from pathlib import Path


def replace_once(path: str, old: str, new: str) -> None:
    file = Path(path)
    text = file.read_text()
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{path}: expected one replacement, found {count}")
    file.write_text(text.replace(old, new, 1))


replace_once(
    "runtime/LC32DarwinSyscalls.cpp",
    "constexpr size_t kMaximumTransfer = 16u * 1024u * 1024u;\n",
    "constexpr size_t kMaximumTransfer = 16u * 1024u * 1024u;\n"
    "constexpr uint32_t kMsAsync = 0x0001u;\n"
    "constexpr uint32_t kMsInvalidate = 0x0002u;\n"
    "constexpr uint32_t kMsKillPages = 0x0004u;\n"
    "constexpr uint32_t kMsDeactivate = 0x0008u;\n"
    "constexpr uint32_t kMsSync = 0x0010u;\n"
    "constexpr int kMaximumAdvice = 9;\n")

mapped_helper = r'''

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
'''
replace_once(
    "runtime/LC32DarwinSyscalls.cpp",
    "bool alignPage(uint32_t value, uint32_t& out) {\n"
    "    const uint64_t aligned = (static_cast<uint64_t>(value) + kPageSize - 1u) &\n"
    "                             ~(static_cast<uint64_t>(kPageSize) - 1u);\n"
    "    if (aligned > UINT32_MAX) return false;\n"
    "    out = static_cast<uint32_t>(aligned);\n"
    "    return true;\n"
    "}\n"
    "} // namespace\n",
    "bool alignPage(uint32_t value, uint32_t& out) {\n"
    "    const uint64_t aligned = (static_cast<uint64_t>(value) + kPageSize - 1u) &\n"
    "                             ~(static_cast<uint64_t>(kPageSize) - 1u);\n"
    "    if (aligned > UINT32_MAX) return false;\n"
    "    out = static_cast<uint32_t>(aligned);\n"
    "    return true;\n"
    "}\n" + mapped_helper +
    "} // namespace\n")

msync_case = r'''        case 65: {
            const uint32_t address = state.r[0];
            const uint32_t length = state.r[1];
            const uint32_t flags = state.r[2];
            const uint32_t supported = kMsAsync | kMsInvalidate |
                                       kMsKillPages | kMsDeactivate | kMsSync;
            if ((flags & ~supported) != 0 ||
                (flags & kMsAsync) != 0 && (flags & kMsSync) != 0) {
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
'''
replace_once(
    "runtime/LC32DarwinSyscalls.cpp",
    "        case 47:\n"
    "            return ok(number, static_cast<int32_t>(::getgid()), \"getgid\");\n"
    "        case 73: {\n",
    "        case 47:\n"
    "            return ok(number, static_cast<int32_t>(::getgid()), \"getgid\");\n" +
    msync_case +
    "        case 73: {\n")

madvise_case = r'''        case 75: {
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
'''
replace_once(
    "runtime/LC32DarwinSyscalls.cpp",
    "            return ok(number, 0, \"mprotect\");\n"
    "        }\n"
    "        case 92: {\n",
    "            return ok(number, 0, \"mprotect\");\n"
    "        }\n" +
    madvise_case +
    "        case 92: {\n")

replace_once(
    "runtime/tests/LC32DarwinSyscallsTests.cpp",
    "    constexpr uint32_t kMapAnonymous = 0x1000u;\n",
    "    constexpr uint32_t kMapAnonymous = 0x1000u;\n"
    "    constexpr uint32_t kMsAsync = 0x0001u;\n"
    "    constexpr uint32_t kMsSync = 0x0010u;\n")

advisory_tests = r'''
    state = {};
    state.r[12] = 65;
    state.r[0] = anonymousAddress;
    state.r[1] = 0x1000u;
    state.r[2] = kMsSync;
    const auto synchronized = rooted.dispatch(state, 0x80u, false);
    assert(synchronized.handled && synchronized.errorNumber == 0);

    state = {};
    state.r[12] = 65;
    state.r[0] = anonymousAddress;
    state.r[1] = 0x1000u;
    state.r[2] = kMsAsync | kMsSync;
    const auto conflictingSync = rooted.dispatch(state, 0x80u, false);
    assert(conflictingSync.handled && conflictingSync.errorNumber == EINVAL);

    state = {};
    state.r[12] = 65;
    state.r[0] = anonymousAddress + 1u;
    state.r[1] = 0x1000u;
    state.r[2] = kMsSync;
    const auto unalignedSync = rooted.dispatch(state, 0x80u, false);
    assert(unalignedSync.handled && unalignedSync.errorNumber == EINVAL);

    state = {};
    state.r[12] = 65;
    state.r[0] = 0x6a000000u;
    state.r[1] = 0x1000u;
    state.r[2] = kMsSync;
    const auto missingSync = rooted.dispatch(state, 0x80u, false);
    assert(missingSync.handled && missingSync.errorNumber == ENOMEM);

    state = {};
    state.r[12] = 75;
    state.r[0] = anonymousAddress + 0x1000u;
    state.r[1] = 1u;
    state.r[2] = 3u;
    const auto willNeed = rooted.dispatch(state, 0x80u, false);
    assert(willNeed.handled && willNeed.errorNumber == 0);

    state = {};
    state.r[12] = 75;
    state.r[0] = anonymousAddress + 0x1000u;
    state.r[1] = 0x1000u;
    state.r[2] = 99u;
    const auto invalidAdvice = rooted.dispatch(state, 0x80u, false);
    assert(invalidAdvice.handled && invalidAdvice.errorNumber == EINVAL);

    state = {};
    state.r[12] = 75;
    state.r[0] = anonymousAddress + 1u;
    state.r[1] = 0x1000u;
    state.r[2] = 0u;
    const auto unalignedAdvice = rooted.dispatch(state, 0x80u, false);
    assert(unalignedAdvice.handled && unalignedAdvice.errorNumber == EINVAL);

    state = {};
    state.r[12] = 75;
    state.r[0] = 0x6b000000u;
    state.r[1] = 0x1000u;
    state.r[2] = 0u;
    const auto missingAdvice = rooted.dispatch(state, 0x80u, false);
    assert(missingAdvice.handled && missingAdvice.errorNumber == ENOMEM);
'''
replace_once(
    "runtime/tests/LC32DarwinSyscallsTests.cpp",
    "    const auto emptyUnmap = rooted.dispatch(state, 0x80u, false);\n"
    "    assert(emptyUnmap.handled && emptyUnmap.errorNumber == 0);\n\n"
    "    state = {};\n"
    "    state.r[12] = 92;\n",
    "    const auto emptyUnmap = rooted.dispatch(state, 0x80u, false);\n"
    "    assert(emptyUnmap.handled && emptyUnmap.errorNumber == 0);\n" +
    advisory_tests +
    "\n    state = {};\n"
    "    state.r[12] = 92;\n")

Path(".github/workflows/apply-vm-advisory.yml").unlink()
Path("tools/apply_vm_advisory.py").unlink()
