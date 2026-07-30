#pragma once

#include "LC32GuestPathResolver.hpp"
#include "LC32MachODependencies.hpp"

#include <cstddef>
#include <cstdint>
#include <functional>
#include <string>
#include <vector>

namespace lc32 {

struct DependencyImage {
    std::string guestPath;
    std::vector<uint8_t> bytes;
};

using DependencyImageLoader = std::function<bool(const std::string& hostPath,
                                                 DependencyImage& image,
                                                 std::string& error)>;

struct DependencyLoadNode {
    std::string guestPath;
    std::string hostPath;
    std::string requestedBy;
    uint32_t slide = 0;
    MachODependencyResult metadata;
};

struct DependencyLoadPlanSpec {
    std::string rootGuestPath;
    std::vector<uint8_t> rootImage;
    GuestPathContext context;
    uint32_t firstSlide = 0x30000000u;
    uint32_t slideStride = 0x01000000u;
    std::size_t maxImages = 256;
};

struct DependencyLoadPlanResult {
    bool ok = false;
    std::string error;
    std::vector<DependencyLoadNode> nodes;
    std::vector<std::string> missingRequired;
    std::vector<std::string> missingWeak;
};

DependencyLoadPlanResult buildDependencyLoadPlan(const DependencyLoadPlanSpec& spec,
                                                 const GuestPathExists& exists,
                                                 const DependencyImageLoader& loadImage);

} // namespace lc32
