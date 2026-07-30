#include "LC32DependencyAudit.hpp"

namespace lc32 {

DependencyAuditResult auditGuestDependencies(const MachODependencyResult& dependencies,
                                             const GuestPathContext& context,
                                             const GuestPathExists& exists) {
    DependencyAuditResult out;
    if (!dependencies.ok) {
        out.error = "dependency parse failed: " + dependencies.error;
        return out;
    }

    GuestPathContext effective = context;
    for (const auto& rpath : dependencies.rpaths) effective.rpaths.push_back(rpath);

    for (const auto& dependency : dependencies.dependencies) {
        const bool weak = dependency.kind == DependencyKind::Weak;
        GuestPathResolution resolved = resolveGuestLibraryPath(dependency.path, effective, exists);

        DependencyAuditEntry entry;
        entry.requested = dependency.path;
        entry.weak = weak;
        entry.found = resolved.ok;
        entry.resolvedGuestPath = resolved.resolvedGuestPath;
        entry.candidates = std::move(resolved.candidates);
        entry.error = std::move(resolved.error);
        out.entries.push_back(std::move(entry));

        if (!resolved.ok) {
            if (weak) out.missingWeak.push_back(dependency.path);
            else out.missingRequired.push_back(dependency.path);
        }
    }

    out.ok = out.missingRequired.empty();
    if (!out.ok) out.error = "missing required guest libraries";
    return out;
}

} // namespace lc32
