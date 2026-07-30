#!/usr/bin/env python3
from pathlib import Path

plugin_path = Path('runtime/LC32PluginMain.cpp')
bootstrap_path = Path('LiveContainer/LCBootstrap.m')
plugin = plugin_path.read_text()
bootstrap = bootstrap_path.read_text()

plugin = plugin.replace('#include "LC32DyldBootSession.hpp"\n', '#include "LC32DyldBootSession.hpp"\n#include "LC32MachODependencies.hpp"\n')

anchor = '''    const char* dyld = std::getenv("LC32_GUEST_DYLD");
    const std::string guestRoot = envValue("LC32_GUEST_ROOTFS");
'''
replacement = '''    const char* dyld = std::getenv("LC32_GUEST_DYLD");
    const std::string guestRoot = envValue("LC32_GUEST_ROOTFS");
'''
if anchor not in plugin:
    raise SystemExit('plugin environment anchor missing')

old_missing = '''    if (!dyld || !*dyld) {
        return failWith(64, "configuration-error", "LC32_GUEST_DYLD is missing");
    }

    logEvent("plugin-start", executable);
'''
new_missing = '''    logEvent("plugin-start", executable);
'''
if old_missing in plugin:
    plugin = plugin.replace(old_missing, new_missing, 1)

old_read = '''    if (!readFile(dyld, dyldImage, error)) {
        return failWith(66, "guest-dyld-read-failed", std::string(dyld) + ": " + error);
    }

    lc32::DyldHandoffSpec spec;
'''
new_read = '''    const bool hasGuestDyld = dyld && *dyld && readFile(dyld, dyldImage, error);
    if (!hasGuestDyld) {
        logEvent("cleanroom-loader-start", "guest dyld unavailable; inspecting app dependencies");
        lc32::MachODependencyResult metadata =
            lc32::parseArmv7MachODependencies(appImage.data(), appImage.size());
        if (!metadata.ok) {
            return failWith(70, "cleanroom-loader-parse-failed", metadata.error);
        }
        if (metadata.dependencies.empty()) {
            return failWith(72, "cleanroom-loader-blocked",
                            "application has no declared dependencies but direct entry startup is not implemented");
        }
        for (const auto& dependency : metadata.dependencies) {
            const std::string& path = dependency.path;
            logEvent(dependency.weak ? "cleanroom-weak-dependency" : "cleanroom-dependency", path);
        }
        const auto required = std::find_if(metadata.dependencies.begin(), metadata.dependencies.end(),
            [](const lc32::MachODependency& dependency) { return !dependency.weak; });
        if (required != metadata.dependencies.end()) {
            return failWith(72, "cleanroom-bridge-required", required->path);
        }
        return failWith(72, "cleanroom-loader-blocked", "only weak dependencies were declared");
    }

    lc32::DyldHandoffSpec spec;
'''
if old_read not in plugin:
    raise SystemExit('plugin dyld read anchor missing')
plugin = plugin.replace(old_read, new_read, 1)

if '#include <algorithm>' not in plugin:
    plugin = plugin.replace('#include <cerrno>\n', '#include <algorithm>\n#include <cerrno>\n', 1)

old_bootstrap = '''        NSString *runtimeDyld = [runtimeRoot stringByAppendingPathComponent:@"usr/lib/dyld"];
        if(![fm isReadableFileAtPath:runtimeDyld]) {
            appError = [NSString stringWithFormat:
                @"ARMv7 rootfs is missing or incomplete. Expected readable guest dyld at %@. Open Settings → 32-bit Runtime → Import ARMv7 RootFS Folder.",
                runtimeDyld];
            NSLog(@"[LCBootstrap] %@", appError);
            *path = oldPath;
            return appError;
        }
        setenv("LC32_GUEST_EXECUTABLE", appBundle.executablePath.fileSystemRepresentation, 1);
'''
new_bootstrap = '''        NSString *runtimeDyld = [runtimeRoot stringByAppendingPathComponent:@"usr/lib/dyld"];
        setenv("LC32_GUEST_EXECUTABLE", appBundle.executablePath.fileSystemRepresentation, 1);
'''
if old_bootstrap not in bootstrap:
    raise SystemExit('bootstrap rootfs gate anchor missing')
bootstrap = bootstrap.replace(old_bootstrap, new_bootstrap, 1)

plugin_path.write_text(plugin)
bootstrap_path.write_text(bootstrap)
print('enabled rootfs-free clean-room loader discovery mode')
