#pragma once

#include "LC32DependencyLoadPlan.hpp"
#include "LC32DependencyMapper.hpp"
#include "LC32DyldHandoff.hpp"

namespace lc32 {

struct DyldImageSetSpec {
    DyldHandoffSpec handoff;
    GuestPathContext pathContext;
    DependencyImageLoader loadImage;
    GuestPathExists exists;
    uint32_t firstDependencySlide = 0x30000000u;
    uint32_t dependencySlideStride = 0x01000000u;
    std::size_t maxDependencyImages = 256;
};

struct DyldImageSetResult {
    bool ok = false;
    std::string error;
    DependencyLoadPlanResult plan;
    DyldHandoffResult handoff;
    DependencyMapResult mappedDependencies;
};

DyldImageSetResult prepareDyldImageSet(const DyldImageSetSpec& spec,
                                       const MapCallback& map,
                                       const WriteCallback& write);

} // namespace lc32
