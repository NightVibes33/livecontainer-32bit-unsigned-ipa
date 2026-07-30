#pragma once

#include <array>
#include <string>
#include <vector>

namespace lc32 {

enum class VirtualRuntimeImageKind {
    Unsupported,
    LibSystem,
    LibObjC,
};

struct VirtualRuntimeImage {
    VirtualRuntimeImageKind kind = VirtualRuntimeImageKind::Unsupported;
    std::string canonicalPath;
    std::vector<std::string> capabilities;
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
             "virtual-memory", "process-environment"},
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

} // namespace lc32
