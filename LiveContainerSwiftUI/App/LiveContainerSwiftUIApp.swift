//
//  LiveContainerSwiftUIApp.swift
//  LiveContainer
//
//  Created by s s on 2025/5/16.
//
import SwiftUI

@main
struct LiveContainerSwiftUIApp : SwiftUI.App {
    @UIApplicationDelegateAdaptor(AppDelegate.self) var appDelegate

    private static let bundled32BitEmulatorName = "LiveExec32.app"
    private static let bundled32BitEmulatorCommit = "3d8760320d981f16aa4b00dd77917b447ac5b774"
    private static let bundled32BitEmulatorRevision = "57"

    private static func seedBundled32BitEmulator(using fm: FileManager) throws {
        let bundledURL = Bundle.main.bundleURL.appendingPathComponent(bundled32BitEmulatorName, isDirectory: true)
        guard fm.fileExists(atPath: bundledURL.path) else {
            return
        }

        let bundledInfoURL = bundledURL.appendingPathComponent("Info.plist")
        guard
            let bundledInfo = NSDictionary(contentsOf: bundledInfoURL),
            bundledInfo["LC32BitTranslationLayer"] as? Bool == true
        else {
            NSLog("[LC32] Ignoring bundled LiveExec32 because LC32BitTranslationLayer is missing")
            return
        }

        let bundledCommit = bundledInfo["LCBundledSourceCommit"] as? String
        let bundledRevision = bundledInfo["LCBundledBuildRevision"] as? String
        guard bundledCommit == bundled32BitEmulatorCommit,
              bundledRevision == bundled32BitEmulatorRevision else {
            NSLog("[LC32] Ignoring bundled LiveExec32 because its bundled metadata is stale")
            return
        }

        try fm.createDirectory(at: LCPath.bundlePath, withIntermediateDirectories: true)
        let installedURL = LCPath.bundlePath.appendingPathComponent(bundled32BitEmulatorName, isDirectory: true)
        let installedInfoURL = installedURL.appendingPathComponent("Info.plist")
        let installedInfo = NSDictionary(contentsOf: installedInfoURL)
        let installedCommit = installedInfo?["LCBundledSourceCommit"] as? String
        let installedRevision = installedInfo?["LCBundledBuildRevision"] as? String

        if installedCommit != bundled32BitEmulatorCommit || installedRevision != bundled32BitEmulatorRevision {
            if fm.fileExists(atPath: installedURL.path) {
                try fm.removeItem(at: installedURL)
            }
            try fm.copyItem(at: bundledURL, to: installedURL)
            NSLog("[LC32] Seeded bundled LiveExec32 emulator revision %@ at %@", bundled32BitEmulatorRevision, installedURL.path)
        }

        let sharedDefaults = LCUtils.appGroupUserDefault
        let selected = sharedDefaults.string(forKey: "LCSelected32BitEmulator") ?? ""
        if selected.isEmpty {
            sharedDefaults.set(bundled32BitEmulatorName, forKey: "LCSelected32BitEmulator")
            NSLog("[LC32] Selected bundled LiveExec32 as the default 32-bit emulator")
        }
    }
    
    init() {
        let fm = FileManager()
        var tempAppDataFolderNames : [String] = []
        var tempTweakFolderNames : [String] = []
        
        var tempApps: [LCAppModel] = []
        var tempArm32EmuApps: [LCAppModel] = []
        var tempHiddenApps: [LCAppModel] = []
        var tempURLSchemes: Set<String>? = DataManager.shared.model.multiLCStatus != 2 ? Set() : nil

        do {
            try Self.seedBundled32BitEmulator(using: fm)

            // load apps
            try fm.createDirectory(at: LCPath.bundlePath, withIntermediateDirectories: true)
            let appDirs = try fm.contentsOfDirectory(atPath: LCPath.bundlePath.path)
            for appDir in appDirs {
                if !appDir.hasSuffix(".app") {
                    continue
                }
                let newApp = LCAppInfo(bundlePath: "\(LCPath.bundlePath.path)/\(appDir)")!
                newApp.relativeBundlePath = appDir
                newApp.isShared = false
                let model = LCAppModel(appInfo: newApp)
                if newApp.isHidden {
                    tempHiddenApps.append(model)
                } else {
                    tempApps.append(model)
                    tempURLSchemes?.formUnion(newApp.urlSchemes() as! [String])
                }
                if newApp.is32bitEmulator {
                    tempArm32EmuApps.append(model)
                }
            }
            if LCPath.lcGroupDocPath != LCPath.docPath {
                try fm.createDirectory(at: LCPath.lcGroupBundlePath, withIntermediateDirectories: true)
                let appDirsShared = try fm.contentsOfDirectory(atPath: LCPath.lcGroupBundlePath.path)
                for appDir in appDirsShared {
                    if !appDir.hasSuffix(".app") {
                        continue
                    }
                    let newApp = LCAppInfo(bundlePath: "\(LCPath.lcGroupBundlePath.path)/\(appDir)")!
                    newApp.relativeBundlePath = appDir
                    newApp.isShared = true
                    let model = LCAppModel(appInfo: newApp)
                    if newApp.isHidden {
                        tempHiddenApps.append(model)
                    } else {
                        tempApps.append(model)
                        tempURLSchemes?.formUnion(newApp.urlSchemes() as! [String])
                    }
                    if newApp.is32bitEmulator {
                        tempArm32EmuApps.append(model)
                    }
                }
            }
            // load document folders
            try fm.createDirectory(at: LCPath.dataPath, withIntermediateDirectories: true)
            let dataDirs = try fm.contentsOfDirectory(atPath: LCPath.dataPath.path)
            for dataDir in dataDirs {
                let dataDirUrl = LCPath.dataPath.appendingPathComponent(dataDir)
                if !dataDirUrl.hasDirectoryPath {
                    continue
                }
                tempAppDataFolderNames.append(dataDir)
            }
            
            // load tweak folders
            try fm.createDirectory(at: LCPath.tweakPath, withIntermediateDirectories: true)
            let tweakDirs = try fm.contentsOfDirectory(atPath: LCPath.tweakPath.path)
            for tweakDir in tweakDirs {
                let tweakDirUrl = LCPath.tweakPath.appendingPathComponent(tweakDir)
                if !tweakDirUrl.hasDirectoryPath {
                    continue
                }
                let folderName = tweakDir.hasSuffix(".disabled") ? String(tweakDir.dropLast(".disabled".count)) : tweakDir
                tempTweakFolderNames.append(folderName)
            }
        } catch {
            NSLog("[LC] error:\(error)")
        }
        
        DataManager.shared.model.apps = tempApps
        DataManager.shared.model.arm32EmuApps = tempArm32EmuApps
        DataManager.shared.model.hiddenApps = tempHiddenApps
        DataManager.shared.model.appDataFolderNames = tempAppDataFolderNames
        DataManager.shared.model.tweakFolderNames = tempTweakFolderNames
        if let tempURLSchemes {
            UserDefaults.lcShared().set(Array(tempURLSchemes), forKey: "LCGuestURLSchemes")
        }
    }
    
    var body: some Scene {
        WindowGroup(id: "Main") {
            LCTabView()
                .handlesExternalEvents(preferring: ["*"], allowing: ["*"])
                .environmentObject(DataManager.shared.model)
                .environmentObject(LCAppSortManager.shared)
        }
        
        if UIApplication.shared.supportsMultipleScenes, #available(iOS 16.1, *) {
            WindowGroup(id: "appView", for: String.self) { $id in
                if let id {
                    MultitaskAppWindow(id: id)
                }
            }

        }
    }
    
}