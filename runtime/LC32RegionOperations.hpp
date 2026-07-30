#pragma once

// Byte-preserving region split operations shared by both no-JIT boot paths.
// Callers validate page alignment and protection policy before invoking them.

#include <algorithm>
#include <cstddef>
#include <cstdint>
#include <utility>
#include <vector>

namespace lc32 {

namespace detail {

template <typename Region>
Region sliceRegion(const Region& source,
                   uint32_t base,
                   uint32_t size,
                   uint32_t protection) {
    Region out;
    out.base = base;
    out.size = size;
    out.protection = protection;
    const std::size_t offset = static_cast<std::size_t>(base - source.base);
    out.bytes.assign(source.bytes.begin() + offset,
                     source.bytes.begin() + offset + size);
    return out;
}

template <typename Region>
bool validRegionRange(uint32_t address, uint32_t size, uint64_t& end) {
    (void)sizeof(Region);
    if (size == 0) return false;
    end = static_cast<uint64_t>(address) + size;
    return end <= 0x100000000ull;
}

} // namespace detail

template <typename Region>
bool unmapRegionRange(std::vector<Region>& regions,
                      uint32_t address,
                      uint32_t size) {
    uint64_t end = 0;
    if (!detail::validRegionRange<Region>(address, size, end)) return false;

    std::vector<Region> updated;
    updated.reserve(regions.size() + 1u);
    for (const Region& region : regions) {
        const uint64_t regionEnd = static_cast<uint64_t>(region.base) + region.size;
        if (end <= region.base || address >= regionEnd) {
            updated.push_back(region);
            continue;
        }

        if (address > region.base) {
            const uint32_t leftSize = address - region.base;
            updated.push_back(detail::sliceRegion(
                region, region.base, leftSize, region.protection));
        }
        if (end < regionEnd) {
            const uint32_t rightBase = static_cast<uint32_t>(end);
            const uint32_t rightSize = static_cast<uint32_t>(regionEnd - end);
            updated.push_back(detail::sliceRegion(
                region, rightBase, rightSize, region.protection));
        }
    }
    regions = std::move(updated);
    return true;
}

template <typename Region>
bool protectRegionRange(std::vector<Region>& regions,
                        uint32_t address,
                        uint32_t size,
                        uint32_t protection) {
    uint64_t end = 0;
    if (!detail::validRegionRange<Region>(address, size, end)) return false;

    std::vector<std::pair<uint64_t, uint64_t>> coverage;
    for (const Region& region : regions) {
        const uint64_t regionEnd = static_cast<uint64_t>(region.base) + region.size;
        if (end <= region.base || address >= regionEnd) continue;
        coverage.push_back({std::max<uint64_t>(address, region.base),
                            std::min<uint64_t>(end, regionEnd)});
    }
    std::sort(coverage.begin(), coverage.end());
    uint64_t cursor = address;
    for (const auto& span : coverage) {
        if (span.first > cursor) return false;
        cursor = std::max(cursor, span.second);
        if (cursor >= end) break;
    }
    if (cursor < end) return false;

    std::vector<Region> updated;
    updated.reserve(regions.size() + 2u);
    for (const Region& region : regions) {
        const uint64_t regionEnd = static_cast<uint64_t>(region.base) + region.size;
        if (end <= region.base || address >= regionEnd) {
            updated.push_back(region);
            continue;
        }

        const uint32_t middleBase =
            static_cast<uint32_t>(std::max<uint64_t>(address, region.base));
        const uint32_t middleEnd =
            static_cast<uint32_t>(std::min<uint64_t>(end, regionEnd));

        if (middleBase > region.base) {
            updated.push_back(detail::sliceRegion(
                region,
                region.base,
                middleBase - region.base,
                region.protection));
        }
        updated.push_back(detail::sliceRegion(
            region, middleBase, middleEnd - middleBase, protection));
        if (middleEnd < regionEnd) {
            updated.push_back(detail::sliceRegion(
                region,
                middleEnd,
                static_cast<uint32_t>(regionEnd - middleEnd),
                region.protection));
        }
    }
    regions = std::move(updated);
    return true;
}

} // namespace lc32
