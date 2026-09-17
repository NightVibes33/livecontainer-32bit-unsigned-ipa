#!/usr/bin/env python3
from pathlib import Path

ROOT = Path("build/LiveExec32")


def replace_once(path: Path, old: str, new: str, label: str):
    text = path.read_text()
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{path}: expected exactly one {label}, found {count}")
    path.write_text(text.replace(old, new, 1))


# Shared bundle metadata policy.
header = ROOT / "include/LC32LegacyCanvas.h"
text = header.read_text()
anchor = """static inline BOOL LC32BundleMayRetainLegacyLandscapePhoneCanvas(
        NSBundle *bundle, uint32_t sdkVersion) {"""
if text.count(anchor) != 1:
    raise SystemExit("legacy canvas header anchor missing")
addition = r'''
/* Generic pre-iOS-8 logical-canvas metadata. The host decides whether a
 * universal app should use its phone or iPad half from the current native
 * idiom; the guest uses the same device-family + launch-art contract when
 * virtualizing UIScreen. */
static inline BOOL LC32BundleSupportsLegacyPhoneCanvas(
        NSBundle *bundle, uint32_t sdkVersion) {
    const LC32SupportedDeviceFamilies families =
        LC32BundleSupportedDeviceFamilies(bundle);
    if(!families.supportsPhone || sdkVersion >= 0x00080000) return NO;
    return LC32BundleContainsPhoneLaunchArt(bundle, bundle.infoDictionary);
}

static inline BOOL LC32BundleSupportsLegacyIPadCanvas(
        NSBundle *bundle, uint32_t sdkVersion) {
    const LC32SupportedDeviceFamilies families =
        LC32BundleSupportedDeviceFamilies(bundle);
    return families.supportsPad && sdkVersion < 0x00080000;
}

static inline uint32_t LC32BundleLegacyPhoneCanvasHeight(
        NSBundle *bundle, uint32_t sdkVersion) {
    if(!LC32BundleSupportsLegacyPhoneCanvas(bundle, sdkVersion)) return 0;
    return LC32BundleContainsTallPhoneLaunchArt(
        bundle, bundle.infoDictionary) ? 568 : 480;
}

'''
header.write_text(text.replace(anchor, addition + anchor, 1))

# Guest UIScreen: report the historical logical canvas rather than modern
# host dimensions. Universal apps choose phone on a phone and iPad on an iPad.
guest = ROOT / "GuestFrameworks/UIKit/UIKit.m"
replace_once(
    guest,
    '''static BOOL LC32LegacyIPadCanvasRequired;
static BOOL LC32LegacyIPadStatusBarHidden;
static BOOL LC32LegacyPhoneCanvasRequired;''',
    '''static BOOL LC32LegacyIPadCanvasRequired;
static BOOL LC32LegacyIPadStatusBarHidden;
static BOOL LC32LegacyPhoneCanvasRequired;
static BOOL LC32LegacySupportsPhoneCanvas;
static BOOL LC32LegacySupportsIPadCanvas;
static uint32_t LC32LegacyPhoneCanvasHeight;''',
    "guest legacy canvas globals",
)
replace_once(
    guest,
    '''    LC32LegacyPhoneCanvasRequired = getter &&
        LC32BundleUsesFixedLandscapePhoneCanvas(bundle, sdkVersion);
    LC32LegacyIPadStatusBarHidden = [[info objectForKey:
        @"UIStatusBarHidden"] boolValue];''',
    '''    LC32LegacyPhoneCanvasRequired = getter &&
        LC32BundleUsesFixedLandscapePhoneCanvas(bundle, sdkVersion);
    LC32LegacySupportsPhoneCanvas = getter &&
        LC32BundleSupportsLegacyPhoneCanvas(bundle, sdkVersion);
    LC32LegacySupportsIPadCanvas = getter &&
        LC32BundleSupportsLegacyIPadCanvas(bundle, sdkVersion);
    LC32LegacyPhoneCanvasHeight = getter
        ? LC32BundleLegacyPhoneCanvasHeight(bundle, sdkVersion) : 0;
    LC32LegacyIPadStatusBarHidden = [[info objectForKey:
        @"UIStatusBarHidden"] boolValue];''',
    "guest legacy canvas resolution",
)
replace_once(
    guest,
    '''static BOOL LC32ScreenNeedsLegacyIPadCanvas(CGRect hostBounds) {
    if(!LC32RequiresLegacyIPadCanvas()) return NO;
    const CGFloat shortEdge = MIN(hostBounds.size.width,
                                  hostBounds.size.height);
    /* A full-size iPad canvas has never had a short edge below 600 points.
     * A smaller value means that an iPad-only guest is running inside a
     * phone/classic host scene and needs a coherent virtual canvas. */
    return shortEdge > 0 && shortEdge < 600;
}''',
    '''static BOOL LC32ScreenNeedsLegacyIPadCanvas(CGRect hostBounds) {
    pthread_once(&LC32LegacyCanvasOnce, LC32ResolveLegacyCanvas);
    if(!LC32LegacySupportsIPadCanvas) {
        if(!LC32RequiresLegacyIPadCanvas()) return NO;
    }
    const CGFloat shortEdge = MIN(hostBounds.size.width,
                                  hostBounds.size.height);
    if(!(shortEdge > 0)) return NO;
    /* Universal apps use iPad geometry on an iPad-sized host and phone
     * geometry on a phone. iPad-only apps keep 768x1024 everywhere. */
    return shortEdge >= 600 || !LC32LegacySupportsPhoneCanvas;
}

static BOOL LC32ScreenNeedsLegacyPhoneCanvas(CGRect hostBounds) {
    pthread_once(&LC32LegacyCanvasOnce, LC32ResolveLegacyCanvas);
    if(!LC32LegacySupportsPhoneCanvas || !LC32LegacyPhoneCanvasHeight)
        return NO;
    const CGFloat shortEdge = MIN(hostBounds.size.width,
                                  hostBounds.size.height);
    if(!(shortEdge > 0)) return NO;
    /* Phone-only apps retain phone compatibility mode on iPad. Universal
     * apps use phone geometry only on a phone-sized host. */
    return shortEdge < 600 || !LC32LegacySupportsIPadCanvas;
}

static CGFloat LC32LegacyPhoneHeight(void) {
    pthread_once(&LC32LegacyCanvasOnce, LC32ResolveLegacyCanvas);
    return LC32LegacyPhoneCanvasHeight
        ? (CGFloat)LC32LegacyPhoneCanvasHeight : 480.0f;
}''',
    "guest legacy iPad canvas selector",
)
replace_once(
    guest,
    '''    } else if(LC32RequiresFixedLandscapePhoneCanvas()) {
        /* Pre-iOS-8 UIScreen coordinates stay portrait-oriented. Legacy GL
         * engines rotate within this surface while the host wrapper presents
         * it as a 480x320 landscape canvas. */
        bounds = CGRectMake(0, 0, 320, 480);
    }''',
    '''    } else if(LC32ScreenNeedsLegacyPhoneCanvas(bounds)) {
        /* Pre-iOS-8 UIScreen coordinates stay portrait-oriented. The native
         * wrapper performs presentation scaling/rotation while guest layout,
         * WebKit and renderers keep their original 320-point logical width. */
        bounds = CGRectMake(0, 0, 320, LC32LegacyPhoneHeight());
    }''',
    "guest UIScreen bounds phone branch",
)
replace_once(
    guest,
    '''    } else if(LC32RequiresFixedLandscapePhoneCanvas()) {
        frame = LC32LegacyIPadStatusBarHidden
            ? CGRectMake(0, 0, 320, 480)
            : CGRectMake(0, 20, 320, 460);
    }''',
    '''    } else if(LC32ScreenNeedsLegacyPhoneCanvas(frame)) {
        const CGFloat height = LC32LegacyPhoneHeight();
        frame = LC32LegacyIPadStatusBarHidden
            ? CGRectMake(0, 0, 320, height)
            : CGRectMake(0, 20, 320, height - 20);
    }''',
    "guest UIScreen applicationFrame phone branch",
)
replace_once(
    guest,
    '''    if(LC32RequiresFixedLandscapePhoneCanvas() && scale > 2.0f) {
        scale = 2.0f;
    }''',
    '''    const CGRect hostBounds = LC32HostScreenRect(self, @selector(bounds));
    if((LC32ScreenNeedsLegacyPhoneCanvas(hostBounds) ||
            LC32ScreenNeedsLegacyIPadCanvas(hostBounds)) && scale > 2.0f) {
        scale = 2.0f;
    }''',
    "guest UIScreen scale cap",
)

# Host UIKit: use the existing native container so presentation and touch share
# the exact same transform.
host = ROOT / "HostFrameworks/UIKit/UIKit.mm"
replace_once(
    host,
    '''    LC32LegacyIPadGeometryModeReflowRootController,
    /* Some legacy landscape phone applications deliberately render through''',
    '''    LC32LegacyIPadGeometryModeReflowRootController,
    /* Resize-aware phone apps keep their historical 320x480/568 logical
     * canvas while a native wrapper aspect-fits it to the modern scene. */
    LC32LegacyIPadGeometryModeReflowPhoneController,
    /* Some legacy landscape phone applications deliberately render through''',
    "host geometry enum",
)
replace_once(
    host,
    '''bool LC32GeometryModePreservesPhoneCanvas(
        LC32LegacyIPadGeometryMode geometryMode) {
    return geometryMode ==
            LC32LegacyIPadGeometryModePreservePhonePortraitCanvas ||
        geometryMode ==
            LC32LegacyIPadGeometryModePreservePhoneLandscapeCanvas;
}''',
    '''bool LC32GeometryModePreservesPhoneCanvas(
        LC32LegacyIPadGeometryMode geometryMode) {
    return geometryMode ==
            LC32LegacyIPadGeometryModeReflowPhoneController ||
        geometryMode ==
            LC32LegacyIPadGeometryModePreservePhonePortraitCanvas ||
        geometryMode ==
            LC32LegacyIPadGeometryModePreservePhoneLandscapeCanvas;
}''',
    "host phone geometry predicate",
)
replace_once(
    host,
    '''struct LC32LegacyCanvasPolicy {
    LC32LegacyIPadCanvasKind kind;
    bool usesFixedLandscapeIPadCanvas;
    bool usesFixedLandscapePhoneCanvas;
    bool mayRetainLegacyLandscapePhoneCanvas;
};''',
    '''struct LC32LegacyCanvasPolicy {
    LC32LegacyIPadCanvasKind kind;
    bool usesFixedLandscapeIPadCanvas;
    bool usesFixedLandscapePhoneCanvas;
    bool mayRetainLegacyLandscapePhoneCanvas;
    bool supportsLegacyPhoneCanvas;
    bool supportsLegacyIPadCanvas;
    uint32_t legacyPhoneCanvasHeight;
};''',
    "host canvas policy struct",
)
replace_once(
    host,
    '''    static LC32LegacyCanvasPolicy result = {
        LC32LegacyIPadCanvasNone,
        false,
        false,
        false,
    };''',
    '''    static LC32LegacyCanvasPolicy result = {
        LC32LegacyIPadCanvasNone,
        false,
        false,
        false,
        false,
        false,
        0,
    };''',
    "host canvas policy initializer",
)
replace_once(
    host,
    '''        result.mayRetainLegacyLandscapePhoneCanvas =
            LC32BundleMayRetainLegacyLandscapePhoneCanvas(
                bundle, LC32GetGuestExecutableSDKVersion());''',
    '''        const uint32_t sdkVersion = LC32GetGuestExecutableSDKVersion();
        result.mayRetainLegacyLandscapePhoneCanvas =
            LC32BundleMayRetainLegacyLandscapePhoneCanvas(
                bundle, sdkVersion);
        result.supportsLegacyPhoneCanvas =
            LC32BundleSupportsLegacyPhoneCanvas(bundle, sdkVersion);
        result.supportsLegacyIPadCanvas =
            LC32BundleSupportsLegacyIPadCanvas(bundle, sdkVersion);
        result.legacyPhoneCanvasHeight =
            LC32BundleLegacyPhoneCanvasHeight(bundle, sdkVersion);''',
    "host canvas policy metadata",
)
old = '''bool LC32GuestMayRetainLegacyLandscapePhoneCanvas(void) {
    return LC32GuestLegacyCanvasPolicy()
        .mayRetainLegacyLandscapePhoneCanvas;
}
'''
new = old + r'''
bool LC32HostUsesPadIdiom(UIWindow *window) {
    UIUserInterfaceIdiom idiom = window
        ? window.traitCollection.userInterfaceIdiom
        : UIUserInterfaceIdiomUnspecified;
    if(idiom == UIUserInterfaceIdiomPad) return true;
    if(idiom == UIUserInterfaceIdiomPhone) return false;
    UIScreen *screen = window.screen ?: UIScreen.mainScreen;
    const CGRect bounds = screen.bounds;
    const CGFloat shortEdge = MIN(bounds.size.width, bounds.size.height);
    return shortEdge >= 600;
}

bool LC32HostWantsLegacyIPadCanvas(UIWindow *window) {
    const LC32LegacyCanvasPolicy &policy = LC32GuestLegacyCanvasPolicy();
    if(!policy.supportsLegacyIPadCanvas &&
            policy.kind == LC32LegacyIPadCanvasNone) return false;
    if(!policy.supportsLegacyPhoneCanvas) return true;
    return LC32HostUsesPadIdiom(window);
}

bool LC32HostWantsLegacyPhoneCanvas(UIWindow *window) {
    const LC32LegacyCanvasPolicy &policy = LC32GuestLegacyCanvasPolicy();
    if(!policy.supportsLegacyPhoneCanvas) return false;
    if(!policy.supportsLegacyIPadCanvas) return true;
    return !LC32HostUsesPadIdiom(window);
}
'''
replace_once(host, old, new, "host canvas selection helpers")
replace_once(
    host,
    '''bool LC32WindowNeedsLegacyIPadContainer(UIWindow *window) {
    if(!window || !LC32GuestNeedsLegacyIPadCanvas()) return false;
    const CGRect hostBounds = LC32WindowSceneBounds(window);
    const CGFloat shortEdge = MIN(hostBounds.size.width,
                                  hostBounds.size.height);
    return shortEdge > 0 && shortEdge < 600;
}''',
    '''bool LC32WindowNeedsLegacyIPadContainer(UIWindow *window) {
    return window && window.guest_selfOrNull &&
        LC32HostWantsLegacyIPadCanvas(window);
}''',
    "host iPad container eligibility",
)
replace_once(
    host,
    '''    if(!window || !window.guest_selfOrNull || !controller ||
            !LC32ObjectUsesGuestClass(controller) ||
            LC32GuestNeedsLegacyIPadCanvas()) {
        return false;
    }

    if(LC32GuestUsesFixedLandscapePhoneCanvas()) {''',
    '''    if(!window || !window.guest_selfOrNull || !controller ||
            !LC32ObjectUsesGuestClass(controller) ||
            !LC32HostWantsLegacyPhoneCanvas(window)) {
        return false;
    }

    if(LC32GuestUsesFixedLandscapePhoneCanvas()) {''',
    "host delayed phone canvas eligibility",
)
replace_once(
    host,
    '''bool LC32WindowNeedsImmediateLegacyPhoneCanvas(
        UIWindow *window, UIViewController *controller) {
    if(!window || !window.guest_selfOrNull || !controller ||
            !LC32ObjectUsesGuestClass(controller) ||
            LC32GuestNeedsLegacyIPadCanvas()) {
        return false;
    }

    if(!LC32GuestUsesFixedLandscapePhoneCanvas()) return false;''',
    '''bool LC32WindowNeedsImmediateLegacyPhoneCanvas(
        UIWindow *window, UIViewController *controller) {
    if(!window || !window.guest_selfOrNull || !controller ||
            !LC32ObjectUsesGuestClass(controller) ||
            !LC32HostWantsLegacyPhoneCanvas(window)) {
        return false;
    }

    /* Generic resize-aware phone apps can be isolated immediately. Preserve
     * the older hidden-root exception only for fixed landscape renderers. */
    if(!LC32GuestUsesFixedLandscapePhoneCanvas()) return true;''',
    "host immediate phone canvas eligibility",
)
replace_once(
    host,
    '''LC32LegacyIPadGeometryMode LC32LegacyPhoneCanvasGeometryMode(
        UIViewController *controller) {
    UIView *contentView = nil;''',
    '''LC32LegacyIPadGeometryMode LC32LegacyPhoneCanvasGeometryMode(
        UIViewController *controller) {
    if(!LC32GuestUsesFixedLandscapePhoneCanvas() &&
            !LC32GuestMayRetainLegacyLandscapePhoneCanvas()) {
        return LC32LegacyIPadGeometryModeReflowPhoneController;
    }
    UIView *contentView = nil;''',
    "host phone geometry classifier",
)
replace_once(
    host,
    '''    return LC32GuestUsesFixedLandscapePhoneCanvas()
        ? LC32LegacyIPadGeometryModePreservePhonePortraitCanvas
        : LC32LegacyIPadGeometryModePreservePhoneLandscapeCanvas;
}''',
    '''    if(LC32GuestUsesFixedLandscapePhoneCanvas()) {
        return LC32LegacyIPadGeometryModePreservePhonePortraitCanvas;
    }
    if(LC32GuestMayRetainLegacyLandscapePhoneCanvas()) {
        return LC32LegacyIPadGeometryModePreservePhoneLandscapeCanvas;
    }
    return LC32LegacyIPadGeometryModeReflowPhoneController;
}''',
    "host phone geometry fallback",
)
replace_once(
    host,
    '''bool LC32UsesClassicFullScreenViewport(UIWindow *window) {
    UIScreen *screen = window.screen ?: UIScreen.mainScreen;
    const CGRect screenBounds = screen.bounds;
    const CGFloat screenShortEdge = MIN(
        screenBounds.size.width, screenBounds.size.height);
    return (LC32GuestNeedsLegacyIPadCanvas() ||
            LC32GuestUsesFixedLandscapePhoneCanvas()) &&
           LC32GuestInterfacePolicy().statusBarHidden &&
           screenShortEdge > 0 && screenShortEdge < 600;
}''',
    '''bool LC32UsesClassicFullScreenViewport(UIWindow *window) {
    return window &&
        (LC32HostWantsLegacyIPadCanvas(window) ||
         LC32HostWantsLegacyPhoneCanvas(window)) &&
        LC32GuestInterfacePolicy().statusBarHidden;
}''',
    "host fullscreen viewport eligibility",
)
text = host.read_text()
anchor = '''    if(container && container.geometryMode ==
            LC32LegacyIPadGeometryModePreservePhonePortraitCanvas) {'''
insert = r'''    if(container && container.geometryMode ==
            LC32LegacyIPadGeometryModeReflowPhoneController) {
        CGRect sceneBounds = LC32WindowSceneBounds(window);
        if(!(sceneBounds.size.width > 0) ||
                !(sceneBounds.size.height > 0)) {
            sceneBounds = (window.screen ?: UIScreen.mainScreen).bounds;
        }
        LC32NativeSetWindowFrame(window, sceneBounds);
        const UIInterfaceOrientation orientation =
            LC32WindowSceneOrientation(window, sceneBounds);
        const CGRect viewport = LC32LegacyViewportInView(
            window, container.view);
        [container fitGuestContentForViewport:viewport
            hostOrientation:orientation];
        return;
    }
'''
if text.count(anchor) != 1:
    raise SystemExit("host scale generic-phone insertion anchor missing")
host.write_text(text.replace(anchor, insert + anchor, 1))
replace_once(
    host,
    '''    if(!LC32GuestNeedsLegacyIPadCanvas()) return;
''',
    '''    if(!LC32HostWantsLegacyIPadCanvas(window)) return;
''',
    "host iPad scale fallback",
)
replace_once(
    host,
    '''    if(_geometryMode ==
            LC32LegacyIPadGeometryModePreservePhonePortraitCanvas) {''',
    '''    if(_geometryMode ==
            LC32LegacyIPadGeometryModeReflowPhoneController) {
        const uint32_t phoneHeight =
            LC32GuestLegacyCanvasPolicy().legacyPhoneCanvasHeight;
        canonicalBounds = CGRectMake(
            0, 0, 320, phoneHeight ? phoneHeight : 480);
    } else if(_geometryMode ==
            LC32LegacyIPadGeometryModePreservePhonePortraitCanvas) {''',
    "host canonical phone bounds",
)
replace_once(
    host,
    '''    } else if(_geometryMode ==
            LC32LegacyIPadGeometryModeReflowRootController) {''',
    '''    } else if(_geometryMode ==
            LC32LegacyIPadGeometryModeReflowRootController ||
            _geometryMode ==
                LC32LegacyIPadGeometryModeReflowPhoneController) {''',
    "host reflow logical orientation",
)
replace_once(
    host,
    '''    if(!view.guest_selfOrNull || !window.guest_selfOrNull ||
            LC32GuestUsesFixedLandscapePhoneCanvas() ||
            LC32GuestNeedsLegacyIPadCanvas()) return UIInterfaceOrientationUnknown;''',
    '''    if(!view.guest_selfOrNull || !window.guest_selfOrNull ||
            LC32HostWantsLegacyPhoneCanvas(window) ||
            LC32HostWantsLegacyIPadCanvas(window))
        return UIInterfaceOrientationUnknown;''',
    "host legacy root geometry ownership",
)
replace_once(
    host,
    '''        const bool usesIPadPolicy = LC32BundleNeedsLegacyIPadCanvas(
            bundle, LC32GetGuestExecutableSDKVersion());''',
    '''        const LC32SupportedDeviceFamilies families =
            LC32BundleSupportedDeviceFamilies(bundle);
        const bool usesIPadPolicy = families.supportsPad &&
            (!families.supportsPhone ||
             UIDevice.currentDevice.userInterfaceIdiom == UIUserInterfaceIdiomPad);''',
    "host universal orientation policy",
)

print("patched generic legacy phone/iPad canvas compatibility")
