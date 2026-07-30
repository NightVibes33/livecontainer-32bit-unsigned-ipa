#!/usr/bin/env python3
from pathlib import Path

plugin_path = Path('runtime/LC32PluginMain.cpp')
bootstrap_path = Path('LiveContainer/LCBootstrap.m')
settings_path = Path('LiveContainerSwiftUI/Views/Settings/LCSettingsView.swift')
plugin = plugin_path.read_text()
bootstrap = bootstrap_path.read_text()
settings = settings_path.read_text()

# Export a stable detailed error string from the plugin.
log_anchor = '''    std::fclose(file);\n}\n\nbool readFile'''
log_replacement = '''    std::fclose(file);\n}\n\nstd::string gLastError;\n\nint failWith(int code, const std::string& stage, const std::string& detail) {\n    gLastError = stage + ": " + detail;\n    logEvent(stage, detail);\n    return code;\n}\n\nbool readFile'''
if 'std::string gLastError;' not in plugin:
    if log_anchor not in plugin:
        raise SystemExit('plugin log anchor missing')
    plugin = plugin.replace(log_anchor, log_replacement, 1)

entry_anchor = '''extern "C" __attribute__((visibility("default")))\nint LC32Main(int argc, char** argv) {\n'''
entry_replacement = '''extern "C" __attribute__((visibility("default")))\nconst char* LC32LastError(void) {\n    return gLastError.c_str();\n}\n\nextern "C" __attribute__((visibility("default")))\nint LC32Main(int argc, char** argv) {\n    gLastError.clear();\n'''
if 'const char* LC32LastError' not in plugin:
    if entry_anchor not in plugin:
        raise SystemExit('plugin entry anchor missing')
    plugin = plugin.replace(entry_anchor, entry_replacement, 1)

replacements = {
'''        logEvent("configuration-error", "LC32_GUEST_EXECUTABLE is missing");\n        return 64;''':
'''        return failWith(64, "configuration-error", "LC32_GUEST_EXECUTABLE is missing");''',
'''        logEvent("configuration-error", "LC32_GUEST_DYLD is missing");\n        return 64;''':
'''        return failWith(64, "configuration-error", "LC32_GUEST_DYLD is missing");''',
'''        logEvent("guest-executable-read-failed", error);\n        return 66;''':
'''        return failWith(66, "guest-executable-read-failed", std::string(executable) + ": " + error);''',
'''        logEvent("guest-dyld-read-failed", error);\n        return 66;''':
'''        return failWith(66, "guest-dyld-read-failed", std::string(dyld) + ": " + error);''',
'''        logEvent("boot-preparation-failed", detail, result.cpuResult.pc,\n                 result.cpuResult.instruction);\n        return 70;''':
'''        gLastError = "boot-preparation-failed: " + detail;\n        logEvent("boot-preparation-failed", detail, result.cpuResult.pc,\n                 result.cpuResult.instruction);\n        return 70;''',
'''    logEvent("guest-cpu-stop", stopDetail, result.cpuResult.pc,\n             result.cpuResult.instruction);\n    return 71;''':
'''    gLastError = "guest-cpu-stop: " + stopDetail;\n    logEvent("guest-cpu-stop", stopDetail, result.cpuResult.pc,\n             result.cpuResult.instruction);\n    return 71;'''
}
for old, new in replacements.items():
    if old in plugin:
        plugin = plugin.replace(old, new, 1)

# Fail before dlopen with an actionable rootfs error.
dyld_anchor = '''        NSString *runtimeDyld = [runtimeRoot stringByAppendingPathComponent:@"usr/lib/dyld"];\n        setenv("LC32_GUEST_EXECUTABLE", appBundle.executablePath.fileSystemRepresentation, 1);'''
dyld_replacement = '''        NSString *runtimeDyld = [runtimeRoot stringByAppendingPathComponent:@"usr/lib/dyld"];\n        if(![fm isReadableFileAtPath:runtimeDyld]) {\n            appError = [NSString stringWithFormat:\n                @"ARMv7 rootfs is missing or incomplete. Expected readable guest dyld at %@. Open Settings → 32-bit Runtime → Import ARMv7 RootFS Folder.",\n                runtimeDyld];\n            NSLog(@"[LCBootstrap] %@", appError);\n            *path = oldPath;\n            return appError;\n        }\n        setenv("LC32_GUEST_EXECUTABLE", appBundle.executablePath.fileSystemRepresentation, 1);'''
if 'Import ARMv7 RootFS Folder' not in bootstrap:
    if dyld_anchor not in bootstrap:
        raise SystemExit('bootstrap dyld anchor missing')
    bootstrap = bootstrap.replace(dyld_anchor, dyld_replacement, 1)

return_anchor = '''#endif\n    return [NSString stringWithFormat:@"App returned from its main function with code %d.", ret];\n}'''
return_replacement = '''#endif\n#if is32BitSupported\n    if(is32bit && ret != 0) {\n        const char* (*lastErrorFn)(void) = (const char* (*)(void))dlsym(appHandle, "LC32LastError");\n        const char* runtimeDetail = lastErrorFn ? lastErrorFn() : NULL;\n        if(runtimeDetail && runtimeDetail[0]) {\n            return [NSString stringWithFormat:@"LiveExec32 stopped with code %d: %s", ret, runtimeDetail];\n        }\n    }\n#endif\n    return [NSString stringWithFormat:@"App returned from its main function with code %d.", ret];\n}'''
if 'LiveExec32 stopped with code' not in bootstrap:
    if return_anchor not in bootstrap:
        raise SystemExit('bootstrap return anchor missing')
    bootstrap = bootstrap.replace(return_anchor, return_replacement, 1)

# Add the SwiftUI rootfs folder importer.
if 'import UniformTypeIdentifiers' not in settings:
    settings = settings.replace('import UserNotifications\n', 'import UserNotifications\nimport UniformTypeIdentifiers\n', 1)

state_anchor = '''    #if is32BitSupported\n    @AppStorage("selected32BitLayer") var liveExec32Path : String = ""\n    #endif'''
state_replacement = '''    #if is32BitSupported\n    @AppStorage("selected32BitLayer") var liveExec32Path : String = ""\n    @StateObject private var rootfsImportFileAlert = AlertHelper<URL>()\n    @State private var armv7RootfsStatus = "Not installed"\n    #endif'''
if 'rootfsImportFileAlert' not in settings:
    if state_anchor not in settings:
        raise SystemExit('settings state anchor missing')
    settings = settings.replace(state_anchor, state_replacement, 1)

jit_anchor = '''                } footer: {\n                    Text("lc.settings.JitDesc".loc)\n                }\n                \n                Section{'''
rootfs_section = '''                } footer: {\n                    Text("lc.settings.JitDesc".loc)\n                }\n\n                #if is32BitSupported\n                Section {\n                    Button {\n                        Task { await importArmv7Rootfs() }\n                    } label: {\n                        Text("Import ARMv7 RootFS Folder")\n                    }\n                    Button(role: .destructive) {\n                        removeArmv7Rootfs()\n                    } label: {\n                        Text("Remove ARMv7 RootFS")\n                    }\n                    HStack {\n                        Text("Status")\n                        Spacer()\n                        Text(armv7RootfsStatus).foregroundStyle(.secondary)\n                    }\n                } header: {\n                    Text("32-bit Runtime")\n                } footer: {\n                    Text("Choose an extracted ARMv7 iOS root filesystem you are authorized to use. It must contain usr/lib/dyld and the required iOS frameworks. Apple runtime files are not bundled with LiveContainer.")\n                }\n                #endif\n                \n                Section{'''
if 'Text("32-bit Runtime")' not in settings:
    if jit_anchor not in settings:
        raise SystemExit('settings JIT section anchor missing')
    settings = settings.replace(jit_anchor, rootfs_section, 1)

importer_anchor = '''            .betterFileImporter(isPresented: $certificateImportFileAlert.show, types: [.p12], multiple: false, callback: { fileUrls in\n                certificateImportFileAlert.close(result: fileUrls[0])\n            }, onDismiss: {\n                certificateImportFileAlert.close(result: nil)\n            })'''
importer_replacement = importer_anchor + '''\n            #if is32BitSupported\n            .betterFileImporter(isPresented: $rootfsImportFileAlert.show, types: [.folder], multiple: false, callback: { fileUrls in\n                rootfsImportFileAlert.close(result: fileUrls.first)\n            }, onDismiss: {\n                rootfsImportFileAlert.close(result: nil)\n            })\n            #endif'''
if 'types: [.folder]' not in settings:
    if importer_anchor not in settings:
        raise SystemExit('settings importer anchor missing')
    settings = settings.replace(importer_anchor, importer_replacement, 1)

appear_anchor = '''        .onAppear() {\n            if !isViewAppeared {'''
appear_replacement = '''        .onAppear() {\n            #if is32BitSupported\n            refreshArmv7RootfsStatus()\n            #endif\n            if !isViewAppeared {'''
if 'refreshArmv7RootfsStatus()' not in settings:
    if appear_anchor not in settings:
        raise SystemExit('settings onAppear anchor missing')
    settings = settings.replace(appear_anchor, appear_replacement, 1)

functions_anchor = '''    func openGitHub() {'''
functions = r'''    #if is32BitSupported
    private var armv7RootfsURL: URL {
        FileManager.default.urls(for: .documentDirectory, in: .userDomainMask)[0]
            .appendingPathComponent("LiveExec32Runtime/rootfs", isDirectory: true)
    }

    private let armv7RequiredPaths = [
        "usr/lib/dyld",
        "System/Library/Frameworks/UIKit.framework/UIKit",
        "System/Library/Frameworks/Foundation.framework/Foundation",
        "System/Library/Frameworks/CoreFoundation.framework/CoreFoundation",
        "System/Library/Frameworks/CoreGraphics.framework/CoreGraphics",
        "System/Library/Frameworks/QuartzCore.framework/QuartzCore",
        "System/Library/Frameworks/OpenGLES.framework/OpenGLES",
        "System/Library/Frameworks/AudioToolbox.framework/AudioToolbox"
    ]

    func refreshArmv7RootfsStatus() {
        let fm = FileManager.default
        let missing = armv7RequiredPaths.filter {
            !fm.isReadableFile(atPath: armv7RootfsURL.appendingPathComponent($0).path)
        }
        armv7RootfsStatus = missing.isEmpty ? "Ready" : "Missing \(missing.count) required files"
    }

    func importArmv7Rootfs() async {
        guard let selectedURL = await rootfsImportFileAlert.open() else { return }
        let fm = FileManager.default
        let didAccess = selectedURL.startAccessingSecurityScopedResource()
        defer { if didAccess { selectedURL.stopAccessingSecurityScopedResource() } }

        let candidates = [selectedURL, selectedURL.appendingPathComponent("rootfs", isDirectory: true)]
        guard let sourceRoot = candidates.first(where: {
            fm.isReadableFile(atPath: $0.appendingPathComponent("usr/lib/dyld").path)
        }) else {
            errorInfo = "The selected folder does not contain a readable usr/lib/dyld. Select the root of an extracted ARMv7 iOS filesystem."
            errorShow = true
            return
        }

        let missing = armv7RequiredPaths.filter {
            !fm.isReadableFile(atPath: sourceRoot.appendingPathComponent($0).path)
        }
        guard missing.isEmpty else {
            errorInfo = "RootFS is incomplete. Missing:\n" + missing.joined(separator: "\n")
            errorShow = true
            return
        }

        let runtimeDirectory = armv7RootfsURL.deletingLastPathComponent()
        let stagingURL = runtimeDirectory.appendingPathComponent("rootfs-importing", isDirectory: true)
        do {
            try fm.createDirectory(at: runtimeDirectory, withIntermediateDirectories: true)
            if fm.fileExists(atPath: stagingURL.path) { try fm.removeItem(at: stagingURL) }
            try fm.copyItem(at: sourceRoot, to: stagingURL)
            if fm.fileExists(atPath: armv7RootfsURL.path) { try fm.removeItem(at: armv7RootfsURL) }
            try fm.moveItem(at: stagingURL, to: armv7RootfsURL)
            refreshArmv7RootfsStatus()
            successInfo = "ARMv7 rootfs installed and validated."
            successShow = true
        } catch {
            try? fm.removeItem(at: stagingURL)
            errorInfo = "RootFS import failed: \(error.localizedDescription)"
            errorShow = true
        }
    }

    func removeArmv7Rootfs() {
        do {
            if FileManager.default.fileExists(atPath: armv7RootfsURL.path) {
                try FileManager.default.removeItem(at: armv7RootfsURL)
            }
            refreshArmv7RootfsStatus()
        } catch {
            errorInfo = "Could not remove RootFS: \(error.localizedDescription)"
            errorShow = true
        }
    }
    #endif

    func openGitHub() {'''
if 'func importArmv7Rootfs() async' not in settings:
    if functions_anchor not in settings:
        raise SystemExit('settings functions anchor missing')
    settings = settings.replace(functions_anchor, functions, 1)

plugin_path.write_text(plugin)
bootstrap_path.write_text(bootstrap)
settings_path.write_text(settings)
print('applied LC32 rootfs import and detailed runtime error support')
