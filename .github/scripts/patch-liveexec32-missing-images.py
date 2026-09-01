#!/usr/bin/env python3
from pathlib import Path

root = Path("build/LiveExec32")
frameworks = {
    "Accelerate": "LC32AccelerateCompatibilityImage",
    "ImageIO": "LC32ImageIOCompatibilityImage",
    "MediaAccessibility": "LC32MediaAccessibilityCompatibilityImage",
    "VideoToolbox": "LC32VideoToolboxCompatibilityImage",
    "CoreSurface": "LC32CoreSurfaceCompatibilityImage",
    "GraphicsServices": "LC32GraphicsServicesCompatibilityImage",
    "PlugInKit": "LC32PlugInKitCompatibilityImage",
}
plist_template = (root / "GuestMakefile/FrameworkInfoPlists/CoreMedia.plist").read_text()
for framework, symbol in frameworks.items():
    source = root / "GuestFrameworks" / framework
    source.mkdir(parents=True, exist_ok=True)
    (source / f"{framework}.m").write_text(
        f"void {symbol}(void) {{}}\n")
    (root / "GuestMakefile/FrameworkInfoPlists" / f"{framework}.plist").write_text(
        plist_template.replace("CoreMedia", framework))
resolv = root / "GuestFrameworks/LC32/LC32Resolv.m"
resolv.write_text(r"""#include <stddef.h>
#include <stdint.h>

int res_9_b64_ntop(const unsigned char *source, size_t length,
                   char *target, size_t targetSize) {
    static const char alphabet[] =
        "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";
    if((!source && length) || !target) return -1;
    const size_t required = ((length + 2) / 3) * 4;
    if(targetSize <= required) return -1;
    size_t input = 0, output = 0;
    while(input + 3 <= length) {
        const uint32_t value = ((uint32_t)source[input] << 16) |
            ((uint32_t)source[input + 1] << 8) | source[input + 2];
        input += 3;
        target[output++] = alphabet[(value >> 18) & 63];
        target[output++] = alphabet[(value >> 12) & 63];
        target[output++] = alphabet[(value >> 6) & 63];
        target[output++] = alphabet[value & 63];
    }
    if(input < length) {
        uint32_t value = (uint32_t)source[input] << 16;
        const int hasSecond = input + 1 < length;
        if(hasSecond) value |= (uint32_t)source[input + 1] << 8;
        target[output++] = alphabet[(value >> 18) & 63];
        target[output++] = alphabet[(value >> 12) & 63];
        target[output++] = hasSecond ? alphabet[(value >> 6) & 63] : '=';
        target[output++] = '=';
    }
    target[output] = 0;
    return (int)output;
}
""")
print("created missing compatibility images and ARM32 resolver implementation")
