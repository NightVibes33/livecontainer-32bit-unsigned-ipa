#pragma once

#include "LC32GuestPathResolver.hpp"
#include "LC32MachODependencies.hpp"

#include <string>
#include <vector>

namespace lc32 {

struct DependencyAuditEntry {
    std::string requested;
    std::string resolvedGuestPath;
    bool weak = false;
    bool found = false;
    std::vector<std::string> candidates;
    std::string error;
};

struct DependencyAuditResult {
    bool ok = false;
    std::string error;
    std::vector<DependencyAuditEntry> entries;
    std::vector<std::string> missingRequired;
    std::vector<std::string> missingWeak;
};

DependencyAuditResult auditGuestDependencies(const MachODependencyResult& dependencies,
                                             const GuestPathContext& context,
                                             const GuestPathExists& exists);

} // namespace lc32
