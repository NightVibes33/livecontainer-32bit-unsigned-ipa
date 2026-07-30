#pragma once

#include <cstddef>
#include <cstdint>
#include <string>
#include <vector>

namespace lc32 {

enum class DependencyKind : uint8_t {
    Load,
    Weak,
    Reexport,
    Upward,
};

struct MachODependency {
    DependencyKind kind = DependencyKind::Load;
    std::string path;
    uint32_t compatibilityVersion = 0;
    uint32_t currentVersion = 0;
};

struct MachODependencyResult {
    bool ok = false;
    std::string error;
    std::string dyldPath;
    std::vector<std::string> rpaths;
    std::vector<MachODependency> dependencies;
};

MachODependencyResult parseArmv7MachODependencies(const uint8_t* data, std::size_t size);

} // namespace lc32
