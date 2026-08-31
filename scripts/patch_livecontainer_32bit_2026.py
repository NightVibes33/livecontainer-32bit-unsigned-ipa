#!/usr/bin/env python3
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
BOOTSTRAP = ROOT / "LiveContainer/LCBootstrap.m"
WORKFLOW = ROOT / ".github/workflows/unsigned-ipa.yml"


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if old not in text:
        if new in text:
            return text
        raise SystemExit(f"{label}: expected source block was not found")
    return text.replace(old, new, 1)


def patch_bootstrap() -> None:
    text = BOOTSTRAP.read_text()

    text = replace_once(
        text,
        "static int (*appMain)(int, char**);",
        "extern char **environ;\nstatic int (*appMain)(int, char**, char**);",
        "appMain ABI",
    )

    text = text.replace('if (access("/var/mobile", R_OK) == 0) {', 'if (access("/usr/lib/systemhook.dylib", R_OK) == 0) {', 1)

    old_handler_re = re.compile(
        r"#if is32BitSupported\n"
        r"    bool metadataSays32Bit = \[guestAppInfo\[@\"is32bit\"\] boolValue\];.*?"
        r"#endif\n"
        r"    if\(!\[guestAppInfo\[@\"dontInjectTweakLoader\"\] boolValue\]\) \{",
        re.S,
    )
    new_handler = '''    bool metadataSays32Bit = [guestAppInfo[@"is32bit"] boolValue];
    bool is32bit = metadataSays32Bit;
    bool detectedRequires32BitLayer = false;
    if(LCDetectExecutableRequires32BitLayer(appExecPath, &detectedRequires32BitLayer)) {
        is32bit = detectedRequires32BitLayer;
        if(metadataSays32Bit != is32bit) {
            NSLog(@"[LCBootstrap] Correcting stale is32bit metadata (%d -> %d) for %s.", metadataSays32Bit, is32bit, appExecPath);
            NSMutableDictionary *repairedAppInfo = [guestAppInfo mutableCopy];
            repairedAppInfo[@"is32bit"] = @(is32bit);
            NSString *appInfoPath = [bundlePath stringByAppendingPathComponent:@"LCAppInfo.plist"];
            if([repairedAppInfo writeBinToFile:appInfoPath atomically:YES]) {
                guestAppInfo = repairedAppInfo;
            } else {
                NSLog(@"[LCBootstrap] Failed to persist repaired architecture metadata at %@.", appInfoPath);
            }
        }
    } else {
        NSLog(@"[LCBootstrap] Architecture inspection failed; retaining cached is32bit=%d.", metadataSays32Bit);
    }

    if(is32bit) {
        if (!isJitEnabled) {
            isJitEnabled = waitForJITEnabled(80, 1000 * 100);
            if(isJitEnabled) {
                init_bypassDyldLibValidation();
            }
        }
        if (!isJitEnabled) {
            return @"JIT is required to run 32-bit apps.";
        }

        NSString *selected32BitLayer = guestAppInfo[@"selected32BitEmulator"] ?: [lcSharedDefaults stringForKey:@"LCSelected32BitEmulator"];
        if(selected32BitLayer.length == 0) {
            selected32BitLayer = @"LiveExec32.app";
            NSLog(@"[LCBootstrap] No emulator selected; using bundled LiveExec32.app.");
        }

        NSBundle *selected32bitLayerBundle = [NSBundle bundleWithPath:[NSString stringWithFormat:@"%@/Applications/%@", docPath, selected32BitLayer]];
        if(!selected32bitLayerBundle) {
            selected32bitLayerBundle = [NSBundle bundleWithPath:[NSString stringWithFormat:@"%@/Applications/%@", appGroupFolder.path, selected32BitLayer]];
        }
        if(!selected32bitLayerBundle && [selected32BitLayer.lastPathComponent isEqualToString:@"LiveExec32.app"]) {
            NSString *bundledLiveExec32Path = [LCMainAppBundlePath() stringByAppendingPathComponent:@"LiveExec32.app"];
            selected32bitLayerBundle = [NSBundle bundleWithPath:bundledLiveExec32Path];
        }
        if(!selected32bitLayerBundle || !selected32bitLayerBundle.executablePath) {
            appError = @"The specified 32-bit emulator app is not found";
            NSLog(@"[LCBootstrap] %@", appError);
            *path = oldPath;
            return appError;
        }
        appExecPath = strdup(selected32bitLayerBundle.executablePath.UTF8String);
        overwriteExecPath(appExecPath);
    }

    if(![guestAppInfo[@"dontInjectTweakLoader"] boolValue]) {'''
    text, count = old_handler_re.subn(new_handler, text, count=1)
    if count != 1 and "LCSelected32BitEmulator" not in text:
        raise SystemExit("32-bit emulator handler: expected legacy handler was not found")

    reroute_re = re.compile(
        r"\n#if is32BitSupported\n"
        r"    LCClearDlopen32BitLayerReroute\(\);\n"
        r"#endif\n"
        r"    void \*appHandle = dlopen_nolock\(appExecPath, RTLD_LAZY\|RTLD_GLOBAL\|RTLD_FIRST\);\n"
        r"#if is32BitSupported\n"
        r"    if\(!is32bit && LCWasDlopenReroutedTo32BitLayer\(\)\) \{.*?"
        r"#endif\n",
        re.S,
    )
    replacement = "\n    void *appHandle = dlopen_nolock(appExecPath, RTLD_LAZY|RTLD_GLOBAL|RTLD_FIRST);\n"
    text, count = reroute_re.subn(replacement, text, count=1)
    if count != 1 and "LCClearDlopen32BitLayerReroute" in text:
        raise SystemExit("legacy dlopen reroute block: expected source block was not found")

    text = text.replace("ret = appMain(argc, argv);", "ret = appMain(argc, argv, environ);", 1)
    text = text.replace(
        "ret = appMain(sizeof(argv32)/sizeof(*argv32) - 1, argv32);",
        "ret = appMain(sizeof(argv32)/sizeof(*argv32) - 1, argv32, environ);",
        1,
    )

    required = [
        'LCSelected32BitEmulator',
        'selected32BitEmulator',
        'LiveExec32.app',
        'appMain(argc, argv, environ)',
    ]
    for marker in required:
        if marker not in text:
            raise SystemExit(f"bootstrap validation failed: {marker} missing")

    BOOTSTRAP.write_text(text)
    print(f"patched {BOOTSTRAP}")


def patch_workflow() -> None:
    text = WORKFLOW.read_text()

    old_step = '''      - name: Patch integrated 32-bit runtime
        run: |
          set -euxo pipefail
          python3 scripts/patch_livecontainer_32bit_host.py LiveContainer/LCBootstrap.m
          python3 scripts/patch_liveexec32.py build/LiveExec32
          grep -q 'Starting LiveExec32 without the legacy host JIT gate' LiveContainer/LCBootstrap.m
          grep -q 'LC32_RUNTIME_ROOT_MISSING' build/LiveExec32/main.cpp
          ! grep -q 'JIT is required to run 32-bit apps through LiveExec32' LiveContainer/LCBootstrap.m
'''
    new_step = '''      - name: Prepare current 32-bit emulator integration
        run: |
          set -euxo pipefail
          python3 scripts/patch_liveexec32.py build/LiveExec32
          grep -q 'LCSelected32BitEmulator' LiveContainer/LCBootstrap.m
          grep -q 'selected32BitEmulator' LiveContainerSwiftUI/Models/LCAppInfo.h
          grep -q 'LC32BitTranslationLayer' LiveContainerSwiftUI/Models/LCAppInfo.m
          grep -q 'LC32_RUNTIME_ROOT_MISSING' build/LiveExec32/main.cpp
'''
    text = replace_once(text, old_step, new_step, "workflow integration step")

    old_build_tail = '''          test -f "$LIVEEXEC_APP/Info.plist"
          test -f "$LIVEEXEC_APP/LiveExec32"
          echo "LIVEEXEC_APP=$LIVEEXEC_APP" >> "$GITHUB_ENV"
'''
    new_build_tail = '''          test -f "$LIVEEXEC_APP/Info.plist"
          test -f "$LIVEEXEC_APP/LiveExec32"
          /usr/libexec/PlistBuddy -c 'Add :LC32BitTranslationLayer bool true' "$LIVEEXEC_APP/Info.plist" 2>/dev/null || \
            /usr/libexec/PlistBuddy -c 'Set :LC32BitTranslationLayer true' "$LIVEEXEC_APP/Info.plist"
          /usr/libexec/PlistBuddy -c 'Print :LC32BitTranslationLayer' "$LIVEEXEC_APP/Info.plist"
          echo "LIVEEXEC_APP=$LIVEEXEC_APP" >> "$GITHUB_ENV"
'''
    text = replace_once(text, old_build_tail, new_build_tail, "LiveExec32 Info.plist marker")

    old_verify = '''          if ! grep -R -a -q 'Rerouting 32-bit guest dlopen' ipa-check/Payload/LiveContainer.app; then
            echo "missing ARMv7 dlopen reroute marker in packaged IPA" >&2
            exit 1
          fi
          if ! grep -R -a -q 'Starting LiveExec32 without the legacy host JIT gate' ipa-check/Payload/LiveContainer.app; then
            echo "missing direct LiveExec32 launch marker in packaged IPA" >&2
            exit 1
          fi
          if ! grep -R -a -q 'LC32_RUNTIME_ROOT_MISSING' ipa-check/Payload/LiveContainer.app/LiveExec32.app; then
            echo "missing patched LiveExec32 runtime diagnostics" >&2
            exit 1
          fi
'''
    new_verify = '''          if ! grep -R -a -q 'LCSelected32BitEmulator' ipa-check/Payload/LiveContainer.app; then
            echo "missing current 32-bit emulator selection handler in packaged IPA" >&2
            exit 1
          fi
          if [ "$(/usr/libexec/PlistBuddy -c 'Print :LC32BitTranslationLayer' ipa-check/Payload/LiveContainer.app/LiveExec32.app/Info.plist)" != "true" ]; then
            echo "bundled LiveExec32 is not marked as an LC32BitTranslationLayer" >&2
            exit 1
          fi
          if ! grep -R -a -q 'LC32_RUNTIME_ROOT_MISSING' ipa-check/Payload/LiveContainer.app/LiveExec32.app; then
            echo "missing patched LiveExec32 runtime diagnostics" >&2
            exit 1
          fi
'''
    text = replace_once(text, old_verify, new_verify, "workflow verification block")

    text = text.replace(
        "Includes the patched integrated LiveExec32 runtime.",
        "Includes bundled LiveExec32 integrated with the current LiveContainer 32-bit emulator handlers.",
    )

    WORKFLOW.write_text(text)
    print(f"patched {WORKFLOW}")


if __name__ == "__main__":
    patch_bootstrap()
    patch_workflow()
