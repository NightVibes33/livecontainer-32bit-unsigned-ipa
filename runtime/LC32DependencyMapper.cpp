#include "LC32DependencyMapper.hpp"

namespace lc32 {

DependencyMapResult mapDependencyLoadPlan(const DependencyLoadPlanResult& plan,
                                          const DependencyImageLoader& loadImage,
                                          const MapCallback& map,
                                          const WriteCallback& write,
                                          bool skipRoot) {
    DependencyMapResult out;
    if (!plan.ok) {
        out.error = plan.error.empty() ? "dependency load plan is not valid" : plan.error;
        return out;
    }
    if (!loadImage || !map || !write) {
        out.error = "missing dependency mapping callbacks";
        return out;
    }

    const std::size_t first = skipRoot && !plan.nodes.empty() ? 1u : 0u;
    for (std::size_t i = first; i < plan.nodes.size(); ++i) {
        const DependencyLoadNode& node = plan.nodes[i];
        if (node.hostPath.empty()) {
            out.error = node.guestPath + ": missing resolved host path";
            return out;
        }

        DependencyImage image;
        std::string loadError;
        if (!loadImage(node.hostPath, image, loadError)) {
            out.error = node.guestPath + ": " +
                        (loadError.empty() ? "dependency image reload failed" : loadError);
            return out;
        }
        if (image.bytes.empty()) {
            out.error = node.guestPath + ": dependency image is empty";
            return out;
        }
        if (!image.guestPath.empty() && image.guestPath != node.guestPath) {
            out.error = node.guestPath + ": dependency image guest-path mismatch";
            return out;
        }

        MachOLoadResult loaded =
            loadArmv7MachO(image.bytes.data(), image.bytes.size(), map, write, node.slide);
        out.images.push_back({node.guestPath, node.hostPath, node.slide, loaded});
        if (!loaded.ok) {
            out.error = node.guestPath + ": " + loaded.error;
            return out;
        }
    }

    out.ok = true;
    return out;
}

} // namespace lc32
