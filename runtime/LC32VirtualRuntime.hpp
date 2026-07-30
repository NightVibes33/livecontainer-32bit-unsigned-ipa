#pragma once

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

VirtualRuntimeImage resolveVirtualRuntimeImage(const std::string& guestPath);
bool isVirtualRuntimeImage(const std::string& guestPath);
const char* virtualRuntimeImageKindName(VirtualRuntimeImageKind kind);

} // namespace lc32
