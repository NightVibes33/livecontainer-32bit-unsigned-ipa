#include "LC32DependencyLoadPlan.hpp"

#include <deque>
#include <unordered_map>

namespace lc32 {

DependencyLoadPlanResult buildDependencyLoadPlan(const DependencyLoadPlanSpec& spec,
                                                 const GuestPathExists& exists,
                                                 const DependencyImageLoader& loadImage) {
    DependencyLoadPlanResult out;
    if (spec.rootGuestPath.empty() || spec.rootImage.empty()) {
        out.error = "missing root dependency image";
        return out;
    }
    if (!exists || !loadImage || spec.slideStride == 0 || spec.maxImages == 0) {
        out.error = "invalid dependency load-plan callbacks or limits";
        return out;
    }

    struct Pending {
        std::string guestPath;
        std::string hostPath;
        std::string requestedBy;
        std::vector<uint8_t> bytes;
    };

    std::deque<Pending> queue;
    queue.push_back({spec.rootGuestPath, {}, {}, spec.rootImage});
    std::unordered_map<std::string, std::size_t> seen;

    while (!queue.empty()) {
        Pending current = std::move(queue.front());
        queue.pop_front();
        if (seen.find(current.guestPath) != seen.end()) continue;
        if (out.nodes.size() >= spec.maxImages) {
            out.error = "dependency image limit exceeded";
            return out;
        }

        MachODependencyResult metadata =
            parseArmv7MachODependencies(current.bytes.data(), current.bytes.size());
        if (!metadata.ok) {
            out.error = current.guestPath + ": " + metadata.error;
            return out;
        }

        const uint64_t slide64 = uint64_t(spec.firstSlide) +
                                 uint64_t(out.nodes.size()) * spec.slideStride;
        if (slide64 > 0xffffffffull) {
            out.error = "dependency slide address overflow";
            return out;
        }

        seen.emplace(current.guestPath, out.nodes.size());
        out.nodes.push_back({current.guestPath,
                             current.hostPath,
                             current.requestedBy,
                             static_cast<uint32_t>(slide64),
                             metadata});

        GuestPathContext context = spec.context;
        context.loaderPath = current.guestPath;
        context.rpaths.insert(context.rpaths.end(), metadata.rpaths.begin(), metadata.rpaths.end());

        for (const MachODependency& dependency : metadata.dependencies) {
            GuestPathResolution resolution =
                resolveGuestLibraryPath(dependency.path, context, exists);
            const bool weak = dependency.kind == DependencyKind::Weak;
            if (!resolution.ok) {
                (weak ? out.missingWeak : out.missingRequired).push_back(
                    current.guestPath + " -> " + dependency.path);
                continue;
            }
            if (seen.find(resolution.resolvedGuestPath) != seen.end()) continue;

            DependencyImage image;
            std::string loadError;
            if (!loadImage(resolution.resolvedHostPath, image, loadError)) {
                (weak ? out.missingWeak : out.missingRequired).push_back(
                    current.guestPath + " -> " + dependency.path +
                    (loadError.empty() ? "" : " (" + loadError + ")"));
                continue;
            }
            if (image.guestPath.empty()) image.guestPath = resolution.resolvedGuestPath;
            queue.push_back({image.guestPath,
                             resolution.resolvedHostPath,
                             current.guestPath,
                             std::move(image.bytes)});
        }
    }

    if (!out.missingRequired.empty()) {
        out.error = "required dependency chain is incomplete";
        return out;
    }
    out.ok = true;
    return out;
}

} // namespace lc32
