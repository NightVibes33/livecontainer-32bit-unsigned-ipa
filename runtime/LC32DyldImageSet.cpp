#include "LC32DyldImageSet.hpp"

namespace lc32 {

DyldImageSetResult prepareDyldImageSet(const DyldImageSetSpec& spec,
                                       const MapCallback& map,
                                       const WriteCallback& write) {
    DyldImageSetResult out;
    if (!spec.handoff.appImage || !spec.handoff.appSize) {
        out.error = "missing app image";
        return out;
    }
    if (!spec.handoff.dyldImage || !spec.handoff.dyldSize) {
        out.error = "missing dyld image";
        return out;
    }
    if (!spec.loadImage || !spec.exists || !map || !write) {
        out.error = "missing dyld image-set callbacks";
        return out;
    }

    DependencyLoadPlanSpec planSpec;
    planSpec.rootGuestPath = spec.handoff.executablePath;
    planSpec.rootImage.assign(spec.handoff.appImage,
                              spec.handoff.appImage + spec.handoff.appSize);
    planSpec.context = spec.pathContext;
    if (planSpec.context.executablePath.empty()) {
        planSpec.context.executablePath = spec.handoff.executablePath;
    }
    if (planSpec.context.loaderPath.empty()) {
        planSpec.context.loaderPath = spec.handoff.executablePath;
    }
    planSpec.firstSlide = spec.firstDependencySlide;
    planSpec.slideStride = spec.dependencySlideStride;
    planSpec.maxImages = spec.maxDependencyImages;

    out.plan = buildDependencyLoadPlan(planSpec, spec.exists, spec.loadImage);
    if (!out.plan.ok) {
        out.error = out.plan.error;
        return out;
    }

    out.handoff = prepareDyldHandoff(spec.handoff, map, write);
    if (!out.handoff.ok) {
        out.error = out.handoff.error;
        return out;
    }

    out.mappedDependencies =
        mapDependencyLoadPlan(out.plan, spec.loadImage, map, write, true);
    if (!out.mappedDependencies.ok) {
        out.error = out.mappedDependencies.error;
        return out;
    }

    out.ok = true;
    return out;
}

} // namespace lc32
