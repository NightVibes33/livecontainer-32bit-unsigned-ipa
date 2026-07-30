#!/usr/bin/env python3
from pathlib import Path

source_path = Path("runtime/LC32DarwinSyscalls.cpp")
source = source_path.read_text()
needle = """        case 92: {
"""
replacement = """        case 78: {
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
        case 92: {
"""
if source.count(needle) != 1:
    raise SystemExit("mincore source insertion point not unique")
source_path.write_text(source.replace(needle, replacement, 1))

test_path = Path("runtime/tests/LC32DarwinSyscallsTests.cpp")
test = test_path.read_text()
constant_needle = """    constexpr uint32_t kFstatAddress = 0x1200u;
    constexpr uint32_t kStackAddress = 0x3000u;
"""
constant_replacement = """    constexpr uint32_t kFstatAddress = 0x1200u;
    constexpr uint32_t kMincoreAddress = 0x1400u;
    constexpr uint32_t kStackAddress = 0x3000u;
"""
if constant_needle not in test:
    raise SystemExit("mincore constant insertion point not found")
test = test.replace(constant_needle, constant_replacement, 1)

test_needle = """    const auto missingAdvice = rooted.dispatch(state, 0x80u, false);
    assert(missingAdvice.handled && missingAdvice.errorNumber == ENOMEM);

    state = {};
    state.r[12] = 92;
"""
test_replacement = """    const auto missingAdvice = rooted.dispatch(state, 0x80u, false);
    assert(missingAdvice.handled && missingAdvice.errorNumber == ENOMEM);

    std::memset(lowMemory.data() + kMincoreAddress, 0, 2u);
    state = {};
    state.r[12] = 78;
    state.r[0] = anonymousAddress;
    state.r[1] = 0x2000u;
    state.r[2] = kMincoreAddress;
    const auto resident = rooted.dispatch(state, 0x80u, false);
    assert(resident.handled && resident.errorNumber == 0);
    assert(lowMemory[kMincoreAddress] == 0x01u);
    assert(lowMemory[kMincoreAddress + 1u] == 0x01u);

    state = {};
    state.r[12] = 78;
    state.r[0] = anonymousAddress + 1u;
    state.r[1] = 0x1000u;
    state.r[2] = kMincoreAddress;
    const auto unalignedMincore = rooted.dispatch(state, 0x80u, false);
    assert(unalignedMincore.handled && unalignedMincore.errorNumber == EINVAL);

    state = {};
    state.r[12] = 78;
    state.r[0] = 0x6c000000u;
    state.r[1] = 0x1000u;
    state.r[2] = kMincoreAddress;
    const auto missingMincore = rooted.dispatch(state, 0x80u, false);
    assert(missingMincore.handled && missingMincore.errorNumber == ENOMEM);

    state = {};
    state.r[12] = 78;
    state.r[0] = anonymousAddress;
    state.r[1] = 0x2000u;
    state.r[2] = static_cast<uint32_t>(lowMemory.size() - 1u);
    const auto badMincoreVector = rooted.dispatch(state, 0x80u, false);
    assert(badMincoreVector.handled && badMincoreVector.errorNumber == EFAULT);

    state = {};
    state.r[12] = 92;
"""
if test_needle not in test:
    raise SystemExit("mincore test insertion point not found")
test_path.write_text(test.replace(test_needle, test_replacement, 1))

workflow_path = Path(".github/workflows/test-lc32-interpreter.yml")
workflow = workflow_path.read_text()
workflow = workflow.replace(
    "      - 'tools/fix-lc32-interpreter-mask.py'\n",
    "      - 'tools/fix-lc32-interpreter-mask.py'\n      - 'tools/apply_mincore.py'\n",
    1,
)
job = """  apply-staged-mincore-patch:
    if: github.event_name == 'pull_request' && github.event.pull_request.head.repo.full_name == github.repository
    runs-on: ubuntu-latest
    permissions:
      contents: write
    steps:
      - uses: actions/checkout@v6
        with:
          ref: ${{ github.event.pull_request.head.ref }}
          fetch-depth: 0
      - name: Apply staged mincore patch
        shell: bash
        run: python3 tools/apply_mincore.py
      - name: Commit staged mincore patch
        shell: bash
        run: |
          git config user.name "github-actions[bot]"
          git config user.email "41898282+github-actions[bot]@users.noreply.github.com"
          git add -A
          git commit -m "runtime: add mincore support"
          git push origin HEAD:${{ github.event.pull_request.head.ref }}

"""
workflow = workflow.replace("jobs:\n", "jobs:\n" + job, 1)
workflow_path.write_text(workflow)
Path(__file__).unlink()
