#pragma once

#include "LC32DependencyLoadPlan.hpp"
#include "LC32MachOLoader.hpp"

#include <string>
#include <vector>

namespace lc32 {

struct DependencyMappedImage {
    std::string guestPath;
    std::string hostPath;
    uint32_t slide = 0;
    MachOLoadResult load;
};

struct DependencyMapResult {
    bool ok = false;
    std::string error;
    std::vector<DependencyMappedImage> images;
};

DependencyMapResult mapDependencyLoadPlan(const DependencyLoadPlanResult& plan,
                                          const DependencyImageLoader& loadImage,
                                          const MapCallback& map,
                                          const WriteCallback& write,
                                          bool skipRoot = true);

} // namespace lc32
