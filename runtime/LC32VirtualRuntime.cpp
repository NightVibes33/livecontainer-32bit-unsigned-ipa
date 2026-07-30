#include "LC32VirtualRuntime.hpp"

#include <array>

namespace lc32 {
namespace {

bool matches(const std::string& path, const std::array<const char*, 4>& aliases) {
    for (const char* alias : aliases) {
        if (path == alias) return true;
    }
    return false;
}

} // namespace

VirtualRuntimeImage resolveVirtualRuntimeImage(const std::string& guestPath) {
    static constexpr std::array<const char*, 4> kLibSystemAliases = {
        "/usr/lib/libSystem.B.dylib",
        "/usr/lib/libSystem.dylib",
        "@rpath/libSystem.B.dylib",
        "libSystem.B.dylib",
    };
    static constexpr std::array<const char*, 4> kLibObjCAliases = {
        "/usr/lib/libobjc.A.dylib",
        "/usr/lib/libobjc.dylib",
        "@rpath/libobjc.A.dylib",
        "libobjc.A.dylib",
    };

    if (matches(guestPath, kLibSystemAliases)) {
        return {
            VirtualRuntimeImageKind::LibSystem,
            "/usr/lib/libSystem.B.dylib",
            {
                "darwin-syscall-dispatch",
                "virtual-mach-ports",
                "confined-filesystem",
                "virtual-memory",
                "process-environment",
            },
        };
    }
    if (matches(guestPath, kLibObjCAliases)) {
        return {
            VirtualRuntimeImageKind::LibObjC,
            "/usr/lib/libobjc.A.dylib",
            {
                "selector-registry",
                "class-registry",
                "object-lifetime",
                "message-dispatch",
            },
        };
    }
    return {};
}

bool isVirtualRuntimeImage(const std::string& guestPath) {
    return resolveVirtualRuntimeImage(guestPath).kind != VirtualRuntimeImageKind::Unsupported;
}

const char* virtualRuntimeImageKindName(VirtualRuntimeImageKind kind) {
    switch (kind) {
        case VirtualRuntimeImageKind::LibSystem: return "libSystem";
        case VirtualRuntimeImageKind::LibObjC: return "libobjc";
        case VirtualRuntimeImageKind::Unsupported: return "unsupported";
    }
    return "unsupported";
}

} // namespace lc32
