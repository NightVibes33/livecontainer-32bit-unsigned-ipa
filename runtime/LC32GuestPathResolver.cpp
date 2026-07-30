#include "LC32GuestPathResolver.hpp"

#include <algorithm>
#include <sstream>

namespace lc32 {
namespace {

std::string dirname(std::string path) {
    while (path.size() > 1 && path.back() == '/') path.pop_back();
    const auto pos = path.find_last_of('/');
    if (pos == std::string::npos) return ".";
    if (pos == 0) return "/";
    return path.substr(0, pos);
}

bool normalizeGuestPath(const std::string& input, std::string& out) {
    if (input.empty() || input.front() != '/') return false;
    std::vector<std::string> parts;
    std::stringstream ss(input);
    std::string part;
    while (std::getline(ss, part, '/')) {
        if (part.empty() || part == ".") continue;
        if (part == "..") {
            if (parts.empty()) return false;
            parts.pop_back();
            continue;
        }
        parts.push_back(part);
    }
    out = "/";
    for (size_t i = 0; i < parts.size(); ++i) {
        if (i) out += '/';
        out += parts[i];
    }
    return true;
}

std::string joinGuest(const std::string& base, const std::string& suffix) {
    if (base.empty()) return suffix;
    if (suffix.empty()) return base;
    if (base.back() == '/' && suffix.front() == '/') return base + suffix.substr(1);
    if (base.back() != '/' && suffix.front() != '/') return base + '/' + suffix;
    return base + suffix;
}

std::string expandToken(const std::string& value,
                        const std::string& executableDir,
                        const std::string& loaderDir) {
    constexpr const char* exec = "@executable_path";
    constexpr const char* loader = "@loader_path";
    if (value.rfind(exec, 0) == 0) return joinGuest(executableDir, value.substr(16));
    if (value.rfind(loader, 0) == 0) return joinGuest(loaderDir, value.substr(12));
    return value;
}

} // namespace

GuestPathResolution resolveGuestLibraryPath(const std::string& requested,
                                            const GuestPathContext& context,
                                            const GuestPathExists& exists) {
    GuestPathResolution out;
    out.requested = requested;
    if (context.guestRoot.empty() || context.guestRoot.front() != '/') {
        out.error = "guest root must be absolute";
        return out;
    }
    if (!exists) {
        out.error = "missing existence callback";
        return out;
    }

    const std::string executableDir = dirname(context.executablePath);
    const std::string loaderDir = dirname(context.loaderPath);
    std::vector<std::string> rawCandidates;

    if (requested.rfind("@rpath/", 0) == 0) {
        const std::string suffix = requested.substr(7);
        for (const auto& rpath : context.rpaths) {
            rawCandidates.push_back(joinGuest(expandToken(rpath, executableDir, loaderDir), suffix));
        }
    } else {
        rawCandidates.push_back(expandToken(requested, executableDir, loaderDir));
    }

    for (const auto& raw : rawCandidates) {
        std::string guest;
        if (!normalizeGuestPath(raw, guest)) continue;
        out.candidates.push_back(guest);
        std::string hostRoot = context.guestRoot;
        while (hostRoot.size() > 1 && hostRoot.back() == '/') hostRoot.pop_back();
        const std::string host = hostRoot + guest;
        if (exists(host)) {
            out.ok = true;
            out.resolvedGuestPath = guest;
            out.resolvedHostPath = host;
            return out;
        }
    }

    out.error = out.candidates.empty() ? "no safe candidate paths" : "library not found in guest root";
    return out;
}

} // namespace lc32
