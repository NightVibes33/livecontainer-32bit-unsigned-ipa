#include "../LC32DependencyAudit.hpp"

#include <cassert>
#include <iostream>
#include <set>

using namespace lc32;

int main() {
    MachODependencyResult deps;
    deps.ok = true;
    deps.rpaths = {"@executable_path/Frameworks"};
    deps.dependencies = {
        {DependencyKind::Load, "/usr/lib/libSystem.B.dylib", 0, 0},
        {DependencyKind::Load, "@rpath/GameKit.dylib", 0, 0},
        {DependencyKind::Weak, "/System/Library/Frameworks/StoreKit.framework/StoreKit", 0, 0}
    };

    GuestPathContext context;
    context.guestRoot = "/guest-root";
    context.executablePath = "/Applications/Felix.app/Felix";
    context.loaderPath = "/usr/lib/dyld";

    std::set<std::string> present = {
        "/guest-root/usr/lib/libSystem.B.dylib",
        "/guest-root/Applications/Felix.app/Frameworks/GameKit.dylib"
    };
    auto exists = [&](const std::string& path) { return present.count(path) != 0; };

    auto result = auditGuestDependencies(deps, context, exists);
    assert(result.ok);
    assert(result.missingRequired.empty());
    assert(result.missingWeak.size() == 1);
    assert(result.entries.size() == 3);

    present.erase("/guest-root/usr/lib/libSystem.B.dylib");
    result = auditGuestDependencies(deps, context, exists);
    assert(!result.ok);
    assert(result.missingRequired.size() == 1);
    assert(result.error == "missing required guest libraries");

    std::cout << "LC32 dependency audit tests passed\n";
    return 0;
}
