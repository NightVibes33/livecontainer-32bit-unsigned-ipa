#pragma once

#include <algorithm>
#include <array>
#include <cstdint>
#include <functional>
#include <string>
#include <vector>

namespace lc32 {

enum class VirtualRuntimeImageKind {
    Unsupported,
    LibSystem,
    LibObjC,
};

enum class VirtualRuntimeBindingKind {
    Unsupported,
    MemoryIntrinsic,
    StringIntrinsic,
    ProcessShim,
    FileShim,
    ObjectiveCRuntime,
};

struct VirtualRuntimeImage {
    VirtualRuntimeImageKind kind = VirtualRuntimeImageKind::Unsupported;
    std::string canonicalPath;
    std::vector<std::string> capabilities;
};

struct VirtualRuntimeSymbol {
    VirtualRuntimeImageKind imageKind = VirtualRuntimeImageKind::Unsupported;
    VirtualRuntimeBindingKind bindingKind = VirtualRuntimeBindingKind::Unsupported;
    std::string canonicalName;
    uint32_t guestAddress = 0;
    bool executable = false;
};

struct VirtualRuntimeMemory {
    std::function<bool(uint32_t, void*, std::size_t)> read;
    std::function<bool(uint32_t, const void*, std::size_t)> write;
};

struct VirtualRuntimeCallResult {
    bool handled = false;
    bool ok = false;
    uint32_t returnValue = 0;
    std::string error;
};

inline bool virtualRuntimeMatches(const std::string& path,
                                  const std::array<const char*, 4>& aliases) {
    for (const char* alias : aliases) {
        if (path == alias) return true;
    }
    return false;
}

inline VirtualRuntimeImage resolveVirtualRuntimeImage(const std::string& guestPath) {
    static constexpr std::array<const char*, 4> kLibSystemAliases = {
        "/usr/lib/libSystem.B.dylib", "/usr/lib/libSystem.dylib",
        "@rpath/libSystem.B.dylib", "libSystem.B.dylib",
    };
    static constexpr std::array<const char*, 4> kLibObjCAliases = {
        "/usr/lib/libobjc.A.dylib", "/usr/lib/libobjc.dylib",
        "@rpath/libobjc.A.dylib", "libobjc.A.dylib",
    };

    if (virtualRuntimeMatches(guestPath, kLibSystemAliases)) {
        return {
            VirtualRuntimeImageKind::LibSystem,
            "/usr/lib/libSystem.B.dylib",
            {"darwin-syscall-dispatch", "virtual-mach-ports", "confined-filesystem",
             "virtual-memory", "process-environment", "memory-intrinsics", "string-intrinsics"},
        };
    }
    if (virtualRuntimeMatches(guestPath, kLibObjCAliases)) {
        return {
            VirtualRuntimeImageKind::LibObjC,
            "/usr/lib/libobjc.A.dylib",
            {"selector-registry", "class-registry", "object-lifetime", "message-dispatch"},
        };
    }
    return {};
}

inline std::string normalizeVirtualRuntimeSymbolName(std::string name) {
    while (!name.empty() && name.front() == '_') name.erase(name.begin());
    return name;
}

struct VirtualRuntimeSymbolSpec {
    const char* name;
    VirtualRuntimeImageKind imageKind;
    VirtualRuntimeBindingKind bindingKind;
    bool executable;
};

inline const std::array<VirtualRuntimeSymbolSpec, 43>& virtualRuntimeSymbolSpecs() {
    static constexpr std::array<VirtualRuntimeSymbolSpec, 43> kSpecs = {{
        {"memcpy", VirtualRuntimeImageKind::LibSystem, VirtualRuntimeBindingKind::MemoryIntrinsic, true},
        {"memmove", VirtualRuntimeImageKind::LibSystem, VirtualRuntimeBindingKind::MemoryIntrinsic, true},
        {"memset", VirtualRuntimeImageKind::LibSystem, VirtualRuntimeBindingKind::MemoryIntrinsic, true},
        {"memcmp", VirtualRuntimeImageKind::LibSystem, VirtualRuntimeBindingKind::MemoryIntrinsic, true},
        {"strlen", VirtualRuntimeImageKind::LibSystem, VirtualRuntimeBindingKind::StringIntrinsic, true},
        {"strcmp", VirtualRuntimeImageKind::LibSystem, VirtualRuntimeBindingKind::StringIntrinsic, true},
        {"strncmp", VirtualRuntimeImageKind::LibSystem, VirtualRuntimeBindingKind::StringIntrinsic, true},
        {"strchr", VirtualRuntimeImageKind::LibSystem, VirtualRuntimeBindingKind::StringIntrinsic, true},
        {"strrchr", VirtualRuntimeImageKind::LibSystem, VirtualRuntimeBindingKind::StringIntrinsic, true},
        {"exit", VirtualRuntimeImageKind::LibSystem, VirtualRuntimeBindingKind::ProcessShim, false},
        {"abort", VirtualRuntimeImageKind::LibSystem, VirtualRuntimeBindingKind::ProcessShim, false},
        {"malloc", VirtualRuntimeImageKind::LibSystem, VirtualRuntimeBindingKind::MemoryIntrinsic, false},
        {"calloc", VirtualRuntimeImageKind::LibSystem, VirtualRuntimeBindingKind::MemoryIntrinsic, false},
        {"realloc", VirtualRuntimeImageKind::LibSystem, VirtualRuntimeBindingKind::MemoryIntrinsic, false},
        {"free", VirtualRuntimeImageKind::LibSystem, VirtualRuntimeBindingKind::MemoryIntrinsic, false},
        {"open", VirtualRuntimeImageKind::LibSystem, VirtualRuntimeBindingKind::FileShim, false},
        {"close", VirtualRuntimeImageKind::LibSystem, VirtualRuntimeBindingKind::FileShim, false},
        {"read", VirtualRuntimeImageKind::LibSystem, VirtualRuntimeBindingKind::FileShim, false},
        {"write", VirtualRuntimeImageKind::LibSystem, VirtualRuntimeBindingKind::FileShim, false},
        {"lseek", VirtualRuntimeImageKind::LibSystem, VirtualRuntimeBindingKind::FileShim, false},
        {"access", VirtualRuntimeImageKind::LibSystem, VirtualRuntimeBindingKind::FileShim, false},
        {"gettimeofday", VirtualRuntimeImageKind::LibSystem, VirtualRuntimeBindingKind::ProcessShim, false},
        {"time", VirtualRuntimeImageKind::LibSystem, VirtualRuntimeBindingKind::ProcessShim, false},
        {"arc4random", VirtualRuntimeImageKind::LibSystem, VirtualRuntimeBindingKind::ProcessShim, false},
        {"arc4random_uniform", VirtualRuntimeImageKind::LibSystem, VirtualRuntimeBindingKind::ProcessShim, false},
        {"objc_msgSend", VirtualRuntimeImageKind::LibObjC, VirtualRuntimeBindingKind::ObjectiveCRuntime, false},
        {"objc_msgSendSuper", VirtualRuntimeImageKind::LibObjC, VirtualRuntimeBindingKind::ObjectiveCRuntime, false},
        {"objc_msgSendSuper2", VirtualRuntimeImageKind::LibObjC, VirtualRuntimeBindingKind::ObjectiveCRuntime, false},
        {"objc_getClass", VirtualRuntimeImageKind::LibObjC, VirtualRuntimeBindingKind::ObjectiveCRuntime, false},
        {"objc_lookUpClass", VirtualRuntimeImageKind::LibObjC, VirtualRuntimeBindingKind::ObjectiveCRuntime, false},
        {"objc_getMetaClass", VirtualRuntimeImageKind::LibObjC, VirtualRuntimeBindingKind::ObjectiveCRuntime, false},
        {"sel_registerName", VirtualRuntimeImageKind::LibObjC, VirtualRuntimeBindingKind::ObjectiveCRuntime, false},
        {"sel_getUid", VirtualRuntimeImageKind::LibObjC, VirtualRuntimeBindingKind::ObjectiveCRuntime, false},
        {"objc_retain", VirtualRuntimeImageKind::LibObjC, VirtualRuntimeBindingKind::ObjectiveCRuntime, false},
        {"objc_release", VirtualRuntimeImageKind::LibObjC, VirtualRuntimeBindingKind::ObjectiveCRuntime, false},
        {"objc_autorelease", VirtualRuntimeImageKind::LibObjC, VirtualRuntimeBindingKind::ObjectiveCRuntime, false},
        {"objc_storeStrong", VirtualRuntimeImageKind::LibObjC, VirtualRuntimeBindingKind::ObjectiveCRuntime, false},
        {"objc_storeWeak", VirtualRuntimeImageKind::LibObjC, VirtualRuntimeBindingKind::ObjectiveCRuntime, false},
        {"objc_loadWeakRetained", VirtualRuntimeImageKind::LibObjC, VirtualRuntimeBindingKind::ObjectiveCRuntime, false},
        {"objc_destroyWeak", VirtualRuntimeImageKind::LibObjC, VirtualRuntimeBindingKind::ObjectiveCRuntime, false},
        {"objc_initWeak", VirtualRuntimeImageKind::LibObjC, VirtualRuntimeBindingKind::ObjectiveCRuntime, false},
        {"objc_copyWeak", VirtualRuntimeImageKind::LibObjC, VirtualRuntimeBindingKind::ObjectiveCRuntime, false},
        {"objc_moveWeak", VirtualRuntimeImageKind::LibObjC, VirtualRuntimeBindingKind::ObjectiveCRuntime, false},
    }};
    return kSpecs;
}

inline VirtualRuntimeSymbol resolveVirtualRuntimeSymbol(const std::string& importedName) {
    const std::string normalized = normalizeVirtualRuntimeSymbolName(importedName);
    const auto& specs = virtualRuntimeSymbolSpecs();
    for (std::size_t index = 0; index < specs.size(); ++index) {
        const auto& spec = specs[index];
        if (normalized != spec.name) continue;
        return {
            spec.imageKind,
            spec.bindingKind,
            spec.name,
            static_cast<uint32_t>(0xF1000000u + index * 4u),
            spec.executable,
        };
    }
    return {};
}

inline bool isVirtualRuntimeImage(const std::string& guestPath) {
    return resolveVirtualRuntimeImage(guestPath).kind != VirtualRuntimeImageKind::Unsupported;
}

inline const char* virtualRuntimeImageKindName(VirtualRuntimeImageKind kind) {
    switch (kind) {
        case VirtualRuntimeImageKind::LibSystem: return "libSystem";
        case VirtualRuntimeImageKind::LibObjC: return "libobjc";
        case VirtualRuntimeImageKind::Unsupported: return "unsupported";
    }
    return "unsupported";
}

inline bool readVirtualCString(const VirtualRuntimeMemory& memory,
                               uint32_t address,
                               std::vector<uint8_t>& out,
                               std::size_t limit = 1024 * 1024) {
    if (!memory.read) return false;
    out.clear();
    for (std::size_t index = 0; index < limit; ++index) {
        uint8_t ch = 0;
        if (!memory.read(address + static_cast<uint32_t>(index), &ch, 1)) return false;
        out.push_back(ch);
        if (ch == 0) return true;
    }
    return false;
}

inline VirtualRuntimeCallResult dispatchVirtualRuntimeSymbol(
    const VirtualRuntimeSymbol& symbol,
    const std::array<uint32_t, 4>& args,
    const VirtualRuntimeMemory& memory) {
    VirtualRuntimeCallResult result;
    if (symbol.imageKind == VirtualRuntimeImageKind::Unsupported || !symbol.executable) return result;
    result.handled = true;
    constexpr uint32_t kMaxCopy = 16u * 1024u * 1024u;

    if (symbol.canonicalName == "memcpy" || symbol.canonicalName == "memmove") {
        const uint32_t count = args[2];
        if (count > kMaxCopy) { result.error = "copy exceeds virtual runtime limit"; return result; }
        std::vector<uint8_t> buffer(count);
        if (count && (!memory.read || !memory.read(args[1], buffer.data(), count))) {
            result.error = "source memory is unreadable"; return result;
        }
        if (count && (!memory.write || !memory.write(args[0], buffer.data(), count))) {
            result.error = "destination memory is unwritable"; return result;
        }
        result.ok = true; result.returnValue = args[0]; return result;
    }
    if (symbol.canonicalName == "memset") {
        const uint32_t count = args[2];
        if (count > kMaxCopy) { result.error = "fill exceeds virtual runtime limit"; return result; }
        std::vector<uint8_t> buffer(count, static_cast<uint8_t>(args[1]));
        if (count && (!memory.write || !memory.write(args[0], buffer.data(), count))) {
            result.error = "destination memory is unwritable"; return result;
        }
        result.ok = true; result.returnValue = args[0]; return result;
    }
    if (symbol.canonicalName == "memcmp") {
        const uint32_t count = args[2];
        if (count > kMaxCopy) { result.error = "comparison exceeds virtual runtime limit"; return result; }
        std::vector<uint8_t> left(count), right(count);
        if (count && (!memory.read || !memory.read(args[0], left.data(), count) ||
                      !memory.read(args[1], right.data(), count))) {
            result.error = "comparison memory is unreadable"; return result;
        }
        int comparison = 0;
        for (uint32_t index = 0; index < count; ++index) {
            if (left[index] == right[index]) continue;
            comparison = left[index] < right[index] ? -1 : 1;
            break;
        }
        result.ok = true; result.returnValue = static_cast<uint32_t>(comparison); return result;
    }

    std::vector<uint8_t> left;
    if (!readVirtualCString(memory, args[0], left)) {
        result.error = "string memory is unreadable"; return result;
    }
    if (symbol.canonicalName == "strlen") {
        result.ok = true; result.returnValue = static_cast<uint32_t>(left.size() - 1); return result;
    }
    if (symbol.canonicalName == "strchr" || symbol.canonicalName == "strrchr") {
        const uint8_t needle = static_cast<uint8_t>(args[1]);
        uint32_t found = 0;
        for (std::size_t index = 0; index < left.size(); ++index) {
            if (left[index] == needle) {
                found = args[0] + static_cast<uint32_t>(index);
                if (symbol.canonicalName == "strchr") break;
            }
            if (left[index] == 0) break;
        }
        result.ok = true; result.returnValue = found; return result;
    }

    std::vector<uint8_t> right;
    if (!readVirtualCString(memory, args[1], right)) {
        result.error = "string memory is unreadable"; return result;
    }
    std::size_t limit = std::min(left.size(), right.size());
    if (symbol.canonicalName == "strncmp") limit = std::min<std::size_t>(limit, args[2]);
    int comparison = 0;
    for (std::size_t index = 0; index < limit; ++index) {
        if (left[index] == right[index]) {
            if (left[index] == 0) break;
            continue;
        }
        comparison = left[index] < right[index] ? -1 : 1;
        break;
    }
    result.ok = true; result.returnValue = static_cast<uint32_t>(comparison); return result;
}

} // namespace lc32
