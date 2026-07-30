#include "LC32ProcessStack.hpp"

#include <algorithm>
#include <cstring>

namespace lc32 {
namespace {
uint32_t alignDown(uint32_t value, uint32_t alignment) { return value & ~(alignment - 1u); }
}

ProcessStackResult buildDarwinProcessStack(uint32_t stackBase,
                                           uint32_t stackSize,
                                           const ProcessStackSpec& spec,
                                           const StackWrite& write) {
    ProcessStackResult out;
    if (!write || stackSize < 4096 || spec.argv.empty()) {
        out.error = "invalid process stack input";
        return out;
    }
    const uint64_t top64 = static_cast<uint64_t>(stackBase) + stackSize;
    if (top64 > 0xffffffffu) {
        out.error = "stack range overflow";
        return out;
    }
    const uint32_t bottom = stackBase;
    uint32_t cursor = static_cast<uint32_t>(top64);

    auto pushBytes = [&](const void* data, size_t size, uint32_t alignment, uint32_t& address) -> bool {
        if (size > cursor - bottom) return false;
        cursor -= static_cast<uint32_t>(size);
        cursor = alignDown(cursor, alignment);
        if (cursor < bottom) return false;
        address = cursor;
        return write(cursor, data, size);
    };
    auto pushString = [&](const std::string& value, uint32_t& address) -> bool {
        return pushBytes(value.c_str(), value.size() + 1, 1, address);
    };

    std::vector<uint32_t> argvPtrs(spec.argv.size());
    std::vector<uint32_t> envPtrs(spec.envp.size());
    std::vector<uint32_t> applePtrs(spec.apple.size());

    for (size_t i = spec.apple.size(); i-- > 0;) {
        const std::string combined = spec.apple[i].first + "=" + spec.apple[i].second;
        if (!pushString(combined, applePtrs[i])) { out.error = "apple strings exceed stack"; return out; }
    }
    for (size_t i = spec.envp.size(); i-- > 0;) {
        if (!pushString(spec.envp[i], envPtrs[i])) { out.error = "environment exceeds stack"; return out; }
    }
    for (size_t i = spec.argv.size(); i-- > 0;) {
        if (!pushString(spec.argv[i], argvPtrs[i])) { out.error = "arguments exceed stack"; return out; }
    }

    cursor = alignDown(cursor, 16);
    std::vector<uint32_t> words;
    words.reserve(1 + argvPtrs.size() + 1 + envPtrs.size() + 1 + applePtrs.size() + 1);
    words.push_back(static_cast<uint32_t>(argvPtrs.size()));
    words.insert(words.end(), argvPtrs.begin(), argvPtrs.end());
    words.push_back(0);
    words.insert(words.end(), envPtrs.begin(), envPtrs.end());
    words.push_back(0);
    words.insert(words.end(), applePtrs.begin(), applePtrs.end());
    words.push_back(0);

    const uint32_t tableBytes = static_cast<uint32_t>(words.size() * sizeof(uint32_t));
    if (tableBytes > cursor - bottom) { out.error = "pointer table exceeds stack"; return out; }
    cursor = alignDown(cursor - tableBytes, 16);
    if (cursor < bottom || !write(cursor, words.data(), tableBytes)) {
        out.error = "failed writing process stack";
        return out;
    }

    out.ok = true;
    out.stackPointer = cursor;
    out.argcAddress = cursor;
    out.argvAddress = cursor + 4;
    out.envpAddress = out.argvAddress + static_cast<uint32_t>((argvPtrs.size() + 1) * 4);
    out.appleAddress = out.envpAddress + static_cast<uint32_t>((envPtrs.size() + 1) * 4);
    return out;
}

} // namespace lc32
