#!/usr/bin/env python3
from pathlib import Path

ROOT = Path("build/LiveExec32")
GUEST = ROOT / "GuestFrameworks"


def write(framework: str, name: str, source: str) -> None:
    directory = GUEST / framework
    directory.mkdir(parents=True, exist_ok=True)
    (directory / name).write_text(source)


# MediaToolbox is linked by one of the archive binaries but the pinned RootFS
# does not currently contain a guest image.  Create a real framework image so
# dyld can satisfy the load command.  API-level coverage is handled separately.
media = GUEST / "MediaToolbox"
media.mkdir(parents=True, exist_ok=True)
(media / "MediaToolbox.m").write_text("void LC32MediaToolboxCompatibilityImage(void) {}\n")
plist_template = (ROOT / "GuestMakefile/FrameworkInfoPlists/CoreMedia.plist").read_text()
(ROOT / "GuestMakefile/FrameworkInfoPlists/MediaToolbox.plist").write_text(
    plist_template.replace("CoreMedia", "MediaToolbox")
)

# Stage-1 compatibility surfaces: these exports are startup blockers in the
# exact 51-IPA Cartoon Network corpus.  Where a safe guest-side semantic is
# available we provide it.  Otherwise the symbol is deliberately exported as a
# conservative zero/NULL fallback so the guest reaches runtime code paths that
# can be instrumented and replaced with a full bridge based on observed use.
write("CFNetwork", "LC32CartoonNetworkCompat.m", r'''
#include <stdint.h>
uint32_t LC32CN_CFNetwork_ReturnZero(void) { return 0; }
#define LC32_CN_ALIAS(sym) __asm__(".globl " sym "\n" sym " = _LC32CN_CFNetwork_ReturnZero\n")
LC32_CN_ALIAS("_CFNetServiceBrowserCreate");
LC32_CN_ALIAS("_CFNetServiceBrowserInvalidate");
LC32_CN_ALIAS("_CFNetServiceBrowserScheduleWithRunLoop");
LC32_CN_ALIAS("_CFNetServiceBrowserSearchForServices");
LC32_CN_ALIAS("_CFNetServiceBrowserUnscheduleFromRunLoop");
LC32_CN_ALIAS("_CFNetServiceCancel");
LC32_CN_ALIAS("_CFNetServiceRegisterWithOptions");
LC32_CN_ALIAS("_CFNetServiceResolveWithTimeout");
LC32_CN_ALIAS("_CFNetServiceScheduleWithRunLoop");
LC32_CN_ALIAS("_CFNetServiceUnscheduleFromRunLoop");
LC32_CN_ALIAS("_CFStreamCreatePairWithSocketToNetService");
''')

write("CoreFoundation", "LC32CartoonNetworkCompat.m", r'''
#import <CoreFoundation/CoreFoundation.h>
#include <stdint.h>

uint32_t LC32CN_CoreFoundation_ReturnZero(void) { return 0; }
#define LC32_CN_ALIAS(sym) __asm__(".globl " sym "\n" sym " = _LC32CN_CoreFoundation_ReturnZero\n")
LC32_CN_ALIAS("_CFBinaryHeapAddValue");
LC32_CN_ALIAS("_CFBinaryHeapContainsValue");
LC32_CN_ALIAS("_CFBinaryHeapCreate");
LC32_CN_ALIAS("_CFBinaryHeapGetCount");
LC32_CN_ALIAS("_CFBinaryHeapGetMinimum");
LC32_CN_ALIAS("_CFBinaryHeapGetValues");
LC32_CN_ALIAS("_CFBinaryHeapRemoveMinimumValue");
LC32_CN_ALIAS("_CFNotificationCenterRemoveObserver");
LC32_CN_ALIAS("_CFRunLoopAddObserver");
LC32_CN_ALIAS("_CFRunLoopObserverCreate");
LC32_CN_ALIAS("_CFRunLoopObserverInvalidate");
LC32_CN_ALIAS("_CFStreamCreatePairWithPeerSocketSignature");

/* Unity uses this as a scheduling handoff.  Running an already-guest block
 * synchronously is safer than silently dropping it and avoids a deadlock while
 * preserving forward progress until the native run-loop bridge is extended. */
void CFRunLoopPerformBlock(CFRunLoopRef runLoop, CFTypeRef mode,
                           void (^block)(void)) {
    (void)runLoop;
    (void)mode;
    if(block) block();
}

/* Old Foundation binaries bind these singleton storage symbols through
 * CoreFoundation.  NULL is a safe startup value; actual collection creation
 * continues to use the normal Foundation/CF bridge. */
void *__NSArray0__ = 0;
void *__NSDictionary0__ = 0;
''')

write("CoreGraphics", "LC32CartoonNetworkCompat.m", r'''
#import <CoreGraphics/CoreGraphics.h>
#include <stdint.h>

uint32_t LC32CN_CoreGraphics_ReturnZero(void) { return 0; }
#define LC32_CN_ALIAS(sym) __asm__(".globl " sym "\n" sym " = _LC32CN_CoreGraphics_ReturnZero\n")
LC32_CN_ALIAS("_CGBitmapContextGetHeight");
LC32_CN_ALIAS("_CGBitmapContextGetWidth");
LC32_CN_ALIAS("_CGColorSpaceCreateWithName");
LC32_CN_ALIAS("_CGContextBeginTransparencyLayerWithRect");
LC32_CN_ALIAS("_CGContextDrawPDFPage");
LC32_CN_ALIAS("_CGContextDrawShading");
LC32_CN_ALIAS("_CGContextFlush");
LC32_CN_ALIAS("_CGContextSelectFont");
LC32_CN_ALIAS("_CGContextSetAlpha");
LC32_CN_ALIAS("_CGContextShowTextAtPoint");
LC32_CN_ALIAS("_CGDataProviderCopyData");
LC32_CN_ALIAS("_CGFontCreateWithFontName");
LC32_CN_ALIAS("_CGFunctionCreate");
LC32_CN_ALIAS("_CGFunctionRelease");
LC32_CN_ALIAS("_CGImageRetain");
LC32_CN_ALIAS("_CGPDFDocumentCreateWithURL");
LC32_CN_ALIAS("_CGPDFDocumentGetPage");
LC32_CN_ALIAS("_CGPDFDocumentRelease");
LC32_CN_ALIAS("_CGPathAddPath");
LC32_CN_ALIAS("_CGPathCreateWithEllipseInRect");
LC32_CN_ALIAS("_CGPathCreateWithRect");
LC32_CN_ALIAS("_CGShadingCreateRadial");
LC32_CN_ALIAS("_CGShadingRelease");

CGRect CGContextGetClipBoundingBox(CGContextRef context) {
    (void)context;
    return CGRectZero;
}

CGAffineTransform CGPDFPageGetDrawingTransform(CGPDFPageRef page,
        CGPDFBox box, CGRect rect, int rotate,
        bool preserveAspectRatio) {
    (void)page;
    (void)box;
    (void)rect;
    (void)rotate;
    (void)preserveAspectRatio;
    return CGAffineTransformIdentity;
}
''')

write("CoreMedia", "LC32CartoonNetworkCompat.m", r'''
#import <CoreMedia/CoreMedia.h>
#include <stdint.h>

uint32_t LC32CN_CoreMedia_ReturnZero(void) { return 0; }
#define LC32_CN_ALIAS(sym) __asm__(".globl " sym "\n" sym " = _LC32CN_CoreMedia_ReturnZero\n")
LC32_CN_ALIAS("_CMAudioFormatDescriptionGetRichestDecodableFormat");
LC32_CN_ALIAS("_CMFormatDescriptionGetExtension");
LC32_CN_ALIAS("_CMFormatDescriptionGetMediaSubType");

CGSize CMVideoFormatDescriptionGetPresentationDimensions(
        CMVideoFormatDescriptionRef videoDesc,
        Boolean usePixelAspectRatio, Boolean useCleanAperture) {
    (void)videoDesc;
    (void)usePixelAspectRatio;
    (void)useCleanAperture;
    return CGSizeZero;
}
''')

write("CoreText", "LC32CartoonNetworkCompat.m", r'''
#include <stdint.h>
uint32_t LC32CN_CoreText_ReturnZero(void) { return 0; }
#define LC32_CN_ALIAS(sym) __asm__(".globl " sym "\n" sym " = _LC32CN_CoreText_ReturnZero\n")
LC32_CN_ALIAS("_CTFontDescriptorCopyAttribute");
LC32_CN_ALIAS("_CTFontDescriptorCreateMatchingFontDescriptor");
LC32_CN_ALIAS("_CTFontDescriptorCreateWithNameAndSize");
LC32_CN_ALIAS("_CTFontManagerRegisterFontsForURL");
''')

write("CoreVideo", "LC32CartoonNetworkCompat.m", r'''
#include <stdint.h>
uint32_t LC32CN_CoreVideo_ReturnZero(void) { return 0; }
#define LC32_CN_ALIAS(sym) __asm__(".globl " sym "\n" sym " = _LC32CN_CoreVideo_ReturnZero\n")
/* Returning NULL/unsupported from the Metal texture-cache path intentionally
 * allows old Unity players to fall back to their OpenGL ES renderer. */
LC32_CN_ALIAS("_CVMetalTextureCacheCreate");
LC32_CN_ALIAS("_CVMetalTextureCacheCreateTextureFromImage");
LC32_CN_ALIAS("_CVMetalTextureCacheFlush");
LC32_CN_ALIAS("_CVMetalTextureGetTexture");
''')

write("Foundation", "LC32CartoonNetworkCompat.m", r'''
#include <stdint.h>
uint32_t LC32CN_Foundation_ReturnZero(void) { return 0; }
__asm__(".globl __NSDictionaryOfVariableBindings\n"
        "__NSDictionaryOfVariableBindings = _LC32CN_Foundation_ReturnZero\n");
''')

write("SystemConfiguration", "LC32CartoonNetworkCompat.m", r'''
#include <stdint.h>
uint32_t LC32CN_SystemConfiguration_ReturnZero(void) { return 0; }
__asm__(".globl _SCNetworkReachabilitySetDispatchQueue\n"
        "_SCNetworkReachabilitySetDispatchQueue = _LC32CN_SystemConfiguration_ReturnZero\n");
''')

write("UIKit", "LC32CartoonNetworkCompat.m", r'''
#import <UIKit/UIKit.h>

void UIAccessibilityRequestGuidedAccessSession(
        BOOL enable, void (^completionHandler)(BOOL didSucceed)) {
    (void)enable;
    if(completionHandler) completionHandler(NO);
}
''')

# Some SDK-era binaries bind NSLayoutConstraint through Foundation's two-level
# namespace.  Re-export the existing UIKit guest shim instead of defining a
# second Objective-C class with the same runtime name.
makefile = ROOT / "GuestMakefile/Makefile"
text = makefile.read_text()
old = """Foundation_LDFLAGS = \\
  -compatibility_version 678.24.0 \\
  -current_version 678.24.0 \\
  -Wl,-reexport_library,$(THEOS_OBJ_DIR)/CoreFoundation.framework/CoreFoundation \\
  -Wl,-reexport_library,$(THEOS_OBJ_DIR)/CFNetwork.framework/CFNetwork
"""
new = """Foundation_LDFLAGS = \\
  -compatibility_version 678.24.0 \\
  -current_version 678.24.0 \\
  -Wl,-reexport_library,$(THEOS_OBJ_DIR)/CoreFoundation.framework/CoreFoundation \\
  -Wl,-reexport_library,$(THEOS_OBJ_DIR)/CFNetwork.framework/CFNetwork \\
  -Wl,-reexport_library,$(THEOS_OBJ_DIR)/UIKit.framework/UIKit
"""
if "-reexport_library,$(THEOS_OBJ_DIR)/UIKit.framework/UIKit" not in text:
    if text.count(old) != 1:
        raise SystemExit("Foundation re-export anchor missing")
    text = text.replace(old, new, 1)

old_dep = """Foundation: | CoreFoundation CFNetwork
Foundation.all.framework.variables: | \\
  CoreFoundation.all.framework.variables CFNetwork.all.framework.variables
"""
new_dep = """Foundation: | CoreFoundation CFNetwork UIKit
Foundation.all.framework.variables: | \\
  CoreFoundation.all.framework.variables CFNetwork.all.framework.variables \\
  UIKit.all.framework.variables
"""
if "Foundation: | CoreFoundation CFNetwork UIKit" not in text:
    if text.count(old_dep) != 1:
        raise SystemExit("Foundation dependency anchor missing")
    text = text.replace(old_dep, new_dep, 1)
makefile.write_text(text)

print("installed Cartoon Network 51-IPA startup compatibility exports")
