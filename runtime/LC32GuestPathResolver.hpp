#pragma once

#include <functional>
#include <string>
#include <vector>

namespace lc32 {

struct GuestPathContext {
    std::string guestRoot;
    std::string executablePath;
    std::string loaderPath;
    std::vector<std::string> rpaths;
};

struct GuestPathResolution {
    bool ok = false;
    std::string requested;
    std::string resolvedGuestPath;
    std::string resolvedHostPath;
    std::vector<std::string> candidates;
    std::string error;
};

using GuestPathExists = std::function<bool(const std::string& hostPath)>;

GuestPathResolution resolveGuestLibraryPath(const std::string& requested,
                                            const GuestPathContext& context,
                                            const GuestPathExists& exists);

} // namespace lc32
