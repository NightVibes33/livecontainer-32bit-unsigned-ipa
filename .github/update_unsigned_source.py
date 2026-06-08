#!/usr/bin/env python3
import json
import os
import plistlib
from datetime import datetime, timezone
from pathlib import Path

REPO = os.environ.get("GITHUB_REPOSITORY", "NightVibes33/livecontainer-32bit-unsigned-ipa")
SOURCE_PATH = Path(os.environ.get("SOURCE_JSON", "apps.json"))
INFO_PLIST = Path(os.environ.get("INFO_PLIST", "Resources/Info.plist"))
IPA_PATH = Path(os.environ.get("IPA_PATH", os.environ.get("OUTPUT_IPA", "LiveContainer-unsigned.ipa")))
RELEASE_TAG = os.environ.get("RELEASE_TAG", "unsigned-latest")
IPA_ASSET_NAME = os.environ.get("IPA_ASSET_NAME", "LiveContainer-unsigned.ipa")
DOWNLOAD_URL = os.environ.get("IPA_DOWNLOAD_URL", f"https://github.com/{REPO}/releases/download/{RELEASE_TAG}/{IPA_ASSET_NAME}")
RELEASE_URL = os.environ.get("RELEASE_URL", f"https://github.com/{REPO}/releases/tag/{RELEASE_TAG}")
ICON_URL = f"https://raw.githubusercontent.com/{REPO}/main/screenshots/AppIcon1024.png"
HEADER_URL = f"https://raw.githubusercontent.com/{REPO}/main/screenshots/header.png"
SCREENSHOT_URL = f"https://raw.githubusercontent.com/{REPO}/main/screenshots/1.png"
RELEASE_IMAGE_URL = f"https://raw.githubusercontent.com/{REPO}/main/screenshots/release.png"


def read_info_plist():
    with INFO_PLIST.open("rb") as infile:
        return plistlib.load(infile)


def iso_now():
    override = os.environ.get("SOURCE_DATE")
    if override:
        return override
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def ipa_size():
    override = os.environ.get("IPA_SIZE")
    if override:
        return int(override)
    if IPA_PATH.exists():
        return IPA_PATH.stat().st_size
    return 0


def commit_description():
    sha = os.environ.get("GITHUB_SHA", "")[:7]
    run_id = os.environ.get("GITHUB_RUN_ID", "")
    run_url = f"https://github.com/{REPO}/actions/runs/{run_id}" if run_id else RELEASE_URL
    bits = [
        "Automated unsigned real-device build for SideStore and AltStore.",
        "Includes bundled LiveExec32.app for the experimental 32-bit IPA translation path.",
        "Requires a configured JIT provider such as StikDebug for 32-bit launches.",
    ]
    if sha:
        bits.append(f"Build commit: {sha} ({run_url}).")
    return "\n".join(bits)


def app_permissions():
    return {
        "entitlements": [
            "application-identifier",
            "com.apple.security.application-groups",
            "get-task-allow",
            "keychain-access-groups",
            "com.apple.developer.kernel.extended-virtual-addressing",
            "com.apple.developer.kernel.increased-memory-limit",
            "com.apple.developer.healthkit.background-delivery",
            "com.apple.developer.healthkit",
            "com.apple.developer.healthkit.access",
        ],
        "privacy": {
            "LSRequiresIPhoneOS": "The guest app is requesting for this permission.",
            "NFCReaderUsageDescription": "The guest app is requesting for this permission.",
            "NSAppleMusicUsageDescription": "The guest app is requesting for this permission.",
            "NSBluetoothAlwaysUsageDescription": "The guest app is requesting for this permission.",
            "NSBluetoothPeripheralUsageDescription": "The guest app is requesting for this permission.",
            "NSCalendarsFullAccessUsageDescription": "The guest app is requesting for this permission.",
            "NSCalendarsWriteOnlyAccessUsageDescription": "The guest app is requesting for this permission.",
            "NSCameraUsageDescription": "The guest app is requesting for this permission.",
            "NSContactsUsageDescription": "The guest app is requesting for this permission.",
            "NSFaceIDUsageDescription": "The guest app is requesting for this permission.",
            "NSFallDetectionUsageDescription": "The guest app is requesting for this permission.",
            "NSGKFriendListUsageDescription": "The guest app is requesting for this permission.",
            "NSHealthClinicalHealthRecordsShareUsageDescription": "The guest app is requesting for this permission.",
            "NSHealthShareUsageDescription": "The guest app is requesting for this permission.",
            "NSHealthUpdateUsageDescription": "The guest app is requesting for this permission.",
            "NSHomeKitUsageDescription": "The guest app is requesting for this permission.",
            "NSIdentityUsageDescription": "The guest app is requesting for this permission.",
            "NSLocalNetworkUsageDescription": "The guest app is requesting for this permission.",
            "NSLocationAlwaysAndWhenInUseUsageDescription": "The guest app is requesting for this permission.",
            "NSLocationDefaultAccuracyReduced": "The guest app is requesting for this permission.",
            "NSLocationTemporaryUsageDescriptionDictionary": "The guest app is requesting for this permission.",
            "NSLocationUsageDescription": "The guest app is requesting for this permission.",
            "NSLocationWhenInUseUsageDescription": "The guest app is requesting for this permission.",
            "NSMicrophoneUsageDescription": "The guest app is requesting for this permission.",
            "NSMotionUsageDescription": "The guest app is requesting for this permission.",
            "NSNearbyInteractionAllowOnceUsageDescription": "The guest app is requesting for this permission.",
            "NSNearbyInteractionUsageDescription": "The guest app is requesting for this permission.",
            "NSPhotoLibraryAddUsageDescription": "The guest app is requesting for this permission.",
            "NSPhotoLibraryUsageDescription": "The guest app is requesting for this permission.",
            "NSRemindersFullAccessUsageDescription": "The guest app is requesting for this permission.",
            "NSSensorKitUsageDescription": "The guest app is requesting for this permission.",
            "NSSiriUsageDescription": "The guest app is requesting for this permission.",
            "NSSpeechRecognitionUsageDescription": "The guest app is requesting for this permission.",
            "NSUserTrackingUsageDescription": "The guest app is requesting for this permission.",
            "SBAppUsesLocalNotifications": "The guest app is requesting for this permission.",
            "UIApplicationSceneManifest": "The guest app is requesting for this permission.",
        },
    }


def build_source():
    info = read_info_plist()
    version = str(info.get("CFBundleShortVersionString", "0"))
    build_version = str(info.get("CFBundleVersion", version))
    date = iso_now()
    description = commit_description()
    size = ipa_size()
    version_entry = {
        "version": version,
        "buildVersion": build_version,
        "date": date,
        "localizedDescription": description,
        "downloadURL": DOWNLOAD_URL,
        "size": size,
        "minOSVersion": "15.0",
    }
    app = {
        "name": "LiveContainer 32-bit Unsigned",
        "bundleIdentifier": "com.nightvibes33.livecontainer32",
        "developerName": "NightVibes33 / LiveContainer Team",
        "subtitle": "LiveContainer with bundled LiveExec32 for experimental 32-bit IPA launches.",
        "localizedDescription": "Run iOS apps through LiveContainer. This fork bundles LiveExec32 for experimental 32-bit IPA translation and ships as an unsigned IPA for SideStore and AltStore.",
        "iconURL": ICON_URL,
        "tintColor": "#0784FC",
        "category": "utilities",
        "version": version,
        "buildVersion": build_version,
        "versionDate": date[:10],
        "versionDescription": description,
        "downloadURL": DOWNLOAD_URL,
        "size": size,
        "screenshotURLs": [SCREENSHOT_URL],
        "appPermissions": app_permissions(),
        "versions": [version_entry],
    }
    return {
        "name": "LiveContainer 32-bit Unsigned",
        "identifier": "com.nightvibes33.livecontainer32.source",
        "subtitle": "Unsigned LiveContainer builds with bundled LiveExec32.",
        "description": "AltStore and SideStore source for unsigned real-device LiveContainer builds with bundled LiveExec32. 32-bit IPA support is experimental and still requires JIT.",
        "iconURL": ICON_URL,
        "headerURL": HEADER_URL,
        "website": f"https://github.com/{REPO}",
        "tintColor": "#0784FC",
        "apps": [app],
        "news": [
            {
                "appID": "com.nightvibes33.livecontainer32",
                "caption": "Unsigned IPA auto-release updated.",
                "date": date,
                "identifier": f"unsigned-{build_version}",
                "imageURL": RELEASE_IMAGE_URL,
                "notify": False,
                "tintColor": "#0784FC",
                "title": f"LiveContainer {version} build {build_version}",
                "url": RELEASE_URL,
            }
        ],
    }


def main():
    source = build_source()
    SOURCE_PATH.write_text(json.dumps(source, indent=2) + "\n")
    print(f"updated {SOURCE_PATH} for {source['apps'][0]['version']} ({source['apps'][0]['buildVersion']})")


if __name__ == "__main__":
    main()
