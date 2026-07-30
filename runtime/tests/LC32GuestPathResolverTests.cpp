#include "../LC32GuestPathResolver.hpp"

#include <cassert>
#include <iostream>
#include <set>

using namespace lc32;

int main() {
    GuestPathContext context;
    context.guestRoot = "/guest-root";
    context.executablePath = "/Applications/Felix.app/Felix";
    context.loaderPath = "/usr/lib/dyld";
    context.rpaths = {"@executable_path/Frameworks", "/System/Library/Frameworks"};

    const std::set<std::string> present = {
        "/guest-root/Applications/Felix.app/Frameworks/GameKit.dylib",
        "/guest-root/usr/lib/libSystem.B.dylib"
    };
    auto exists = [&](const std::string& path) { return present.count(path) != 0; };

    auto exec = resolveGuestLibraryPath("@executable_path/Frameworks/GameKit.dylib", context, exists);
    assert(exec.ok);
    assert(exec.resolvedGuestPath == "/Applications/Felix.app/Frameworks/GameKit.dylib");

    auto loader = resolveGuestLibraryPath("@loader_path/libSystem.B.dylib", context, exists);
    assert(loader.ok);
    assert(loader.resolvedGuestPath == "/usr/lib/libSystem.B.dylib");

    auto rpath = resolveGuestLibraryPath("@rpath/GameKit.dylib", context, exists);
    assert(rpath.ok);
    assert(rpath.candidates.size() == 1);

    auto missing = resolveGuestLibraryPath("/System/Library/Frameworks/UIKit.framework/UIKit", context, exists);
    assert(!missing.ok);
    assert(missing.error == "library not found in guest root");

    auto escape = resolveGuestLibraryPath("@executable_path/../../../../etc/passwd", context, exists);
    assert(!escape.ok);
    assert(escape.error == "no safe candidate paths");

    std::cout << "LC32 guest path resolver tests passed\n";
    return 0;
}
