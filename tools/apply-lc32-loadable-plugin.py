#!/usr/bin/env python3
from pathlib import Path

path = Path('LiveContainer/LCBootstrap.m')
text = path.read_text()

old_bundle = '''static NSBundle *LCBundleFor32BitLayer(NSString *layerPath, NSString **executablePath) {
    NSBundle *bundle = [NSBundle bundleWithPath:layerPath];
    if(!bundle) {
        return nil;
    }
    NSString *execPath = bundle.executablePath;
    if(!execPath || ![NSFileManager.defaultManager fileExistsAtPath:execPath]) {
        return nil;
    }
    if(executablePath) {
        *executablePath = execPath;
    }
    return bundle;
}
'''
new_bundle = '''static NSBundle *LCBundleFor32BitLayer(NSString *layerPath, NSString **executablePath) {
    NSBundle *bundle = [NSBundle bundleWithPath:layerPath];
    if(!bundle) {
        return nil;
    }
    // LiveExec32.app remains the signed resource container, but the host must
    // dlopen a MH_DYLIB image rather than the app's MH_EXECUTE entry point.
    NSString *pluginPath = [layerPath stringByAppendingPathComponent:@"LiveExec32Plugin.dylib"];
    if(![NSFileManager.defaultManager fileExistsAtPath:pluginPath]) {
        return nil;
    }
    if(executablePath) {
        *executablePath = pluginPath;
    }
    return bundle;
}
'''
if old_bundle not in text:
    raise SystemExit('LCBundleFor32BitLayer anchor missing')
text = text.replace(old_bundle, new_bundle, 1)

old_copy = '''    NSError *copyError = nil;
    NSString *destinationParent = selected32BitLayerPath.stringByDeletingLastPathComponent;
    [NSFileManager.defaultManager createDirectoryAtPath:destinationParent withIntermediateDirectories:YES attributes:nil error:nil];
    if(![NSFileManager.defaultManager fileExistsAtPath:selected32BitLayerPath] &&
       [NSFileManager.defaultManager copyItemAtPath:bundled32BitLayerPath toPath:selected32BitLayerPath error:&copyError] &&
       LCBundleFor32BitLayer(selected32BitLayerPath, executablePath)) {
        return selected32BitLayerPath;
    }

    if(copyError) {
        NSLog(@"[LCBootstrap] Failed to copy bundled LiveExec32.app to Documents: %@", copyError);
    }
    return bundled32BitLayerPath;
'''
new_copy = '''    NSError *copyError = nil;
    NSString *destinationParent = selected32BitLayerPath.stringByDeletingLastPathComponent;
    [NSFileManager.defaultManager createDirectoryAtPath:destinationParent withIntermediateDirectories:YES attributes:nil error:nil];
    // A previous build may have copied the old MH_EXECUTE-only layer. Remove it
    // so the new loadable plugin is not shadowed by stale Documents content.
    if([NSFileManager.defaultManager fileExistsAtPath:selected32BitLayerPath]) {
        [NSFileManager.defaultManager removeItemAtPath:selected32BitLayerPath error:&copyError];
        if(copyError) {
            NSLog(@"[LCBootstrap] Failed to remove stale LiveExec32.app: %@", copyError);
            copyError = nil;
        }
    }
    if([NSFileManager.defaultManager copyItemAtPath:bundled32BitLayerPath toPath:selected32BitLayerPath error:&copyError] &&
       LCBundleFor32BitLayer(selected32BitLayerPath, executablePath)) {
        return selected32BitLayerPath;
    }

    if(copyError) {
        NSLog(@"[LCBootstrap] Failed to copy bundled LiveExec32.app to Documents: %@", copyError);
    }
    return bundled32BitLayerPath;
'''
if old_copy not in text:
    raise SystemExit('LiveExec32 copy anchor missing')
text = text.replace(old_copy, new_copy, 1)

old_contract = '''        NSLog(@"[LCBootstrap] Using 32-bit translation layer at %@", selected32BitLayerPath);
        appExecPath = strdup(selected32BitLayerExecPath.UTF8String);
'''
new_contract = '''        NSLog(@"[LCBootstrap] Using 32-bit translation layer at %@", selected32BitLayerPath);

        NSString *runtimeRoot = [docPath stringByAppendingPathComponent:@"LiveExec32Runtime/rootfs"];
        NSString *runtimeLogs = [docPath stringByAppendingPathComponent:@"LiveExec32Runtime/Logs"];
        [fm createDirectoryAtPath:runtimeLogs withIntermediateDirectories:YES attributes:nil error:nil];
        NSString *runtimeLog = [runtimeLogs stringByAppendingPathComponent:
            [NSString stringWithFormat:@"%@-boot.jsonl", appBundle.bundleIdentifier ?: @"unknown"]];
        NSString *runtimeDyld = [runtimeRoot stringByAppendingPathComponent:@"usr/lib/dyld"];
        setenv("LC32_GUEST_EXECUTABLE", appBundle.executablePath.fileSystemRepresentation, 1);
        setenv("LC32_GUEST_BUNDLE", appBundle.bundlePath.fileSystemRepresentation, 1);
        setenv("LC32_GUEST_HOME", newHomePath.fileSystemRepresentation, 1);
        setenv("LC32_GUEST_ROOTFS", runtimeRoot.fileSystemRepresentation, 1);
        setenv("LC32_GUEST_DYLD", runtimeDyld.fileSystemRepresentation, 1);
        setenv("LC32_LOG_PATH", runtimeLog.fileSystemRepresentation, 1);
        setenv("LC32_GUEST_BUNDLE_ID", (appBundle.bundleIdentifier ?: @"unknown").UTF8String, 1);
        setenv("LC32_LAUNCH_SCHEMA", "2", 1);
        appExecPath = strdup(selected32BitLayerExecPath.UTF8String);
'''
if old_contract not in text:
    raise SystemExit('32-bit launch contract anchor missing')
text = text.replace(old_contract, new_contract, 1)

old_entry = '''    // Find main()
    appMain = getAppEntryPoint(appHandle);
    if (!appMain) {
        appError = @"Could not find the main entry point";
'''
new_entry = '''    // Native guests use LC_MAIN. The interpreted 32-bit layer is a dylib with
    // one explicit C entry point so dyld never attempts to load a main executable.
#if is32BitSupported
    if(is32bit) {
        dlerror();
        appMain = (int (*)(int, char**))dlsym(appHandle, "LC32Main");
        const char *entryError = dlerror();
        if(entryError) {
            NSLog(@"[LCBootstrap] LC32Main lookup failed: %s", entryError);
        }
    } else {
        appMain = getAppEntryPoint(appHandle);
    }
#else
    appMain = getAppEntryPoint(appHandle);
#endif
    if (!appMain) {
        appError = is32bit ? @"LiveExec32Plugin.dylib does not export LC32Main" : @"Could not find the main entry point";
'''
if old_entry not in text:
    raise SystemExit('app entry point anchor missing')
text = text.replace(old_entry, new_entry, 1)

path.write_text(text)
print('patched LCBootstrap for loadable LC32 plugin')
