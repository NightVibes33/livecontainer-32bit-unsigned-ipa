#!/usr/bin/env python3
import argparse
import hashlib
import json
import plistlib
import re
import shutil
import tempfile
import urllib.parse
import urllib.request
import zipfile
from pathlib import Path

import lief

IDENTIFIER = "cartoon-network-ios-archive"
SOURCE = f"https://archive.org/download/{IDENTIFIER}"
UA = {"User-Agent": "LiveExec32-CartoonNetwork-audit/1"}
MACH_MAGICS = {
    b"\xce\xfa\xed\xfe", b"\xfe\xed\xfa\xce",
    b"\xcf\xfa\xed\xfe", b"\xfe\xed\xfa\xcf",
    b"\xca\xfe\xba\xbe", b"\xbe\xba\xfe\xca",
    b"\xca\xfe\xba\xbf", b"\xbf\xba\xfe\xca",
}


def metadata_apps():
    req = urllib.request.Request(
        f"https://archive.org/metadata/{IDENTIFIER}", headers=UA)
    with urllib.request.urlopen(req, timeout=120) as r:
        meta = json.load(r)
    apps = []
    for f in meta.get("files", []):
        name = f.get("name", "")
        if not name.lower().endswith(".ipa"):
            continue
        apps.append({
            "name": name,
            "size": int(f.get("size") or 0),
            "md5": f.get("md5"),
            "sha1": f.get("sha1"),
        })
    return sorted(apps, key=lambda x: x["name"].lower())


def balanced_shards(apps, count):
    bins = [[] for _ in range(count)]
    totals = [0] * count
    for app in sorted(apps, key=lambda x: x["size"], reverse=True):
        i = min(range(count), key=lambda n: totals[n])
        bins[i].append(app)
        totals[i] += app["size"]
    return bins, totals


def digest(path, algorithm):
    h = hashlib.new(algorithm)
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def download(entry, target):
    url = SOURCE.rstrip("/") + "/" + urllib.parse.quote(entry["name"], safe="/")
    last_error = None
    for attempt in range(3):
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=240) as src, target.open("wb") as dst:
                shutil.copyfileobj(src, dst, 1024 * 1024)
            if entry["size"] and target.stat().st_size != entry["size"]:
                raise ValueError(
                    f"size mismatch {target.stat().st_size} != {entry['size']}")
            for alg in ("md5", "sha1"):
                expected = entry.get(alg)
                if expected and digest(target, alg).lower() != expected.lower():
                    raise ValueError(f"{alg} mismatch")
            return url
        except Exception as e:
            last_error = e
            target.unlink(missing_ok=True)
    raise last_error


def is_macho(z, info):
    if info.is_dir() or info.file_size < 4:
        return False
    with z.open(info) as f:
        return f.read(4) in MACH_MAGICS


def binaries(parsed):
    if parsed is None:
        return []
    try:
        return list(parsed)
    except TypeError:
        return [parsed]


def is_arm32(binary):
    cpu = str(binary.header.cpu_type)
    return "ARM" in cpu and "ARM64" not in cpu


def is_arm64(binary):
    return "ARM64" in str(binary.header.cpu_type)


def describe_arm32(path, relative):
    parsed = lief.MachO.parse(str(path))
    choices = [b for b in binaries(parsed) if is_arm32(b)]
    if not choices:
        return None
    b = choices[0]
    imports = []
    for sym in b.imported_symbols:
        item = {"name": sym.name}
        try:
            item["ordinal"] = sym.library_ordinal
        except Exception:
            pass
        try:
            item["weak"] = bool(sym.has_binding_info and sym.binding_info.weak_import)
        except Exception:
            item["weak"] = False
        imports.append(item)
    libs = []
    for lib in b.libraries:
        command = str(lib.command)
        if "ID_DYLIB" not in command:
            libs.append(lib.name)
    return {
        "path": relative,
        "cpu": str(b.header.cpu_type),
        "pie": bool(b.is_pie),
        "encrypted": bool(b.has_encryption_info and b.encryption_info.crypt_id),
        "libraries": libs,
        "imports": imports,
    }


def architectures(path):
    parsed = lief.MachO.parse(str(path))
    return sorted({str(b.header.cpu_type) for b in binaries(parsed)})


def parse_sdk_major(info):
    for key in ("DTSDKName", "DTPlatformVersion"):
        value = str(info.get(key) or "")
        m = re.search(r"(?:iphoneos)?(\d+)(?:\.|$)", value.lower())
        if m:
            return int(m.group(1))
    return None


def launch_policy(info, names, sdk_major):
    families = info.get("UIDeviceFamily")
    if not isinstance(families, list):
        families = [1] if info.get("LSRequiresIPhoneOS") else []
    families = sorted({int(x) for x in families if str(x).isdigit()})
    supports_phone = 1 in families
    supports_ipad = 2 in families
    lower = [n.lower() for n in names]
    phone_art = any(
        ("default" in n or "launchimage" in n)
        and ("iphone" in n or "568h" in n)
        for n in lower
    )
    tall_phone = any("568h" in n for n in lower)
    launch_images = info.get("UILaunchImages")
    if isinstance(launch_images, list):
        for x in launch_images:
            if not isinstance(x, dict):
                continue
            name = str(x.get("UILaunchImageName") or "").lower()
            size = str(x.get("UILaunchImageSize") or "").lower()
            if "568" in name or "568" in size:
                tall_phone = True
            if name or size:
                phone_art = phone_art or ("768" not in size and "1024" not in size)
    ipad_art = any(
        ("default" in n or "launchimage" in n)
        and ("ipad" in n or "portrait" in n or "landscape" in n)
        for n in lower
    )
    legacy = sdk_major is not None and sdk_major < 8
    phone_height = 568 if tall_phone else 480
    phone_canvas = f"320x{phone_height}" if legacy and supports_phone else None
    ipad_canvas = "768x1024" if legacy and supports_ipad else None
    if legacy:
        host_phone = phone_canvas or ipad_canvas
        host_ipad = ipad_canvas or phone_canvas
    else:
        host_phone = "modern-dynamic"
        host_ipad = "modern-dynamic"
    return {
        "device_families": families,
        "supports_phone": supports_phone,
        "supports_ipad": supports_ipad,
        "phone_launch_art": phone_art,
        "tall_phone_launch_art": tall_phone,
        "ipad_launch_art": ipad_art,
        "legacy_sdk": legacy,
        "legacy_phone_canvas": phone_canvas,
        "legacy_ipad_canvas": ipad_canvas,
        "host_phone_canvas": host_phone,
        "host_ipad_canvas": host_ipad,
    }


def detect_markers(blob):
    checks = {
        "unity": [b"UnityEngine", b"UnityAppController"],
        "cordovaphonegap": [b"Cordova", b"PhoneGap", b"CDVViewController"],
        "cocos2d": [b"cocos2d", b"CCDirector"],
        "fmod": [b"FMOD", b"fmod_event"],
        "openal": [b"alcOpenDevice", b"alSourcePlay"],
        "opengles": [b"EAGLContext", b"glDrawElements"],
        "metal": [b"MTLCreateSystemDefaultDevice", b"CAMetalLayer"],
        "uiwebview": [b"UIWebView"],
        "webkit": [b"WKWebView"],
        "gamekit": [b"GKLocalPlayer"],
        "avfoundation": [b"AVAudioPlayer", b"AVPlayer", b"AVCaptureSession"],
    }
    return sorted(k for k, needles in checks.items() if any(n in blob for n in needles))


INTERESTING_IMPORTS = {
    "pthread_join", "pthread_cond_wait", "pthread_mutex_lock",
    "dispatch_group_wait", "dispatch_semaphore_wait", "dispatch_sync",
    "curl_easy_perform", "socket", "connect", "poll", "select",
    "MTLCreateSystemDefaultDevice", "alcOpenDevice", "AudioQueueNewOutput",
}


def audit(entry, work):
    ipa = work / "app.ipa"
    url = download(entry, ipa)
    with zipfile.ZipFile(ipa) as z:
        infos = z.infolist()
        plists = [i for i in infos if i.filename.startswith("Payload/")
                  and i.filename.count("/") == 2
                  and i.filename.endswith(".app/Info.plist")]
        if not plists:
            raise ValueError("top-level Info.plist missing")
        plist_info = plists[0]
        info = plistlib.loads(z.read(plist_info))
        app_root = plist_info.filename[:-len("Info.plist")]
        exe_member = app_root + info["CFBundleExecutable"]
        member = next((i for i in infos if i.filename == exe_member), None)
        if member is None:
            raise ValueError("main executable missing")
        exe = work / "main"
        with z.open(member) as src, exe.open("wb") as dst:
            shutil.copyfileobj(src, dst)
        arches = architectures(exe)
        arm32 = describe_arm32(exe, info["CFBundleExecutable"])
        names = [i.filename[len(app_root):] for i in infos if i.filename.startswith(app_root)]
        sdk_major = parse_sdk_major(info)
        policy = launch_policy(info, names, sdk_major)
        embedded = []
        for idx, m in enumerate(i for i in infos if i.filename.startswith(app_root) and is_macho(z, i)):
            p = work / f"macho-{idx}"
            with z.open(m) as src, p.open("wb") as dst:
                shutil.copyfileobj(src, dst)
            d = describe_arm32(p, m.filename[len(app_root):])
            if d:
                embedded.append(d)
        raw = exe.read_bytes()
    all_imports = sorted({
        i["name"].lstrip("_")
        for image in embedded
        for i in image.get("imports", [])
        if i.get("name")
    })
    interesting = [x for x in all_imports if x in INTERESTING_IMPORTS]
    all_libs = sorted({lib for image in embedded for lib in image.get("libraries", [])})
    return {
        "status": "ok",
        "archive_name": entry["name"],
        "archive_url": url,
        "archive_size": entry["size"],
        "bundle_id": info.get("CFBundleIdentifier"),
        "short_version": info.get("CFBundleShortVersionString"),
        "bundle_version": info.get("CFBundleVersion"),
        "minimum_os": info.get("MinimumOSVersion"),
        "sdk_name": info.get("DTSDKName"),
        "sdk_major": sdk_major,
        "architectures": arches,
        "has_arm32": arm32 is not None,
        "main_arm32": arm32,
        "embedded_arm32_images": len(embedded),
        "markers": detect_markers(raw),
        "interesting_imports": interesting,
        "libraries": all_libs,
        "canvas": policy,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--shard-index", type=int, required=True)
    ap.add_argument("--shard-count", type=int, required=True)
    ap.add_argument("--output", required=True)
    args = ap.parse_args()
    apps = metadata_apps()
    shards, totals = balanced_shards(apps, args.shard_count)
    selected = shards[args.shard_index]
    print(
        f"all={len(apps)} shard={args.shard_index}/{args.shard_count} "
        f"apps={len(selected)} bytes={totals[args.shard_index]}", flush=True)
    results = []
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        for entry in selected:
            one = root / "one"
            shutil.rmtree(one, ignore_errors=True)
            one.mkdir()
            print("AUDIT", entry["name"], flush=True)
            try:
                results.append(audit(entry, one))
            except Exception as e:
                results.append({
                    "status": "error",
                    "archive_name": entry["name"],
                    "archive_size": entry["size"],
                    "error": repr(e),
                })
    Path(args.output).write_text(json.dumps(results, indent=2, sort_keys=True) + "\n")
    print("RESULTS", len(results), "OK", sum(x["status"] == "ok" for x in results))


if __name__ == "__main__":
    main()
