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
}
plist_template = (root / "GuestMakefile/FrameworkInfoPlists/CoreMedia.plist").read_text()
for framework, symbol in frameworks.items():
    source = root / "GuestFrameworks" / framework
    source.mkdir(parents=True, exist_ok=True)
    (source / f"{framework}.m").write_text(
        f"void {symbol}(void) {{}}\n")
    (root / "GuestMakefile/FrameworkInfoPlists" / f"{framework}.plist").write_text(
        plist_template.replace("CoreMedia", framework))
print("created six missing compatibility images; private copies are installed after packing")
