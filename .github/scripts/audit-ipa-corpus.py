#!/usr/bin/env python3
import argparse, hashlib, json, plistlib, shutil, tempfile, urllib.parse, urllib.request, zipfile
from pathlib import Path
import lief

def digest(path, algorithm):
    h=hashlib.new(algorithm)
    with path.open("rb") as f:
        for block in iter(lambda:f.read(1024*1024),b""): h.update(block)
    return h.hexdigest()

def choose_arm(binary):
    bins=list(binary) if hasattr(binary,"__iter__") else [binary]
    for b in bins:
        if "ARM" in str(b.header.cpu_type) and "ARM64" not in str(b.header.cpu_type):
            return b
    return None

MACH_MAGICS = {
    b"\xce\xfa\xed\xfe", b"\xfe\xed\xfa\xce",
    b"\xcf\xfa\xed\xfe", b"\xfe\xed\xfa\xcf",
    b"\xca\xfe\xba\xbe", b"\xbe\xba\xfe\xca",
    b"\xca\xfe\xba\xbf", b"\xbf\xba\xfe\xca",
}

def is_macho_member(archive, member):
    if member.is_dir() or member.file_size < 4:
        return False
    with archive.open(member) as stream:
        return stream.read(4) in MACH_MAGICS

def describe_macho(path, relative_name):
    parsed=lief.MachO.parse(str(path))
    binary=choose_arm(parsed)
    if binary is None: return None
    imported=[]
    for sym in binary.imported_symbols:
        item={"name":sym.name,"ordinal":sym.library_ordinal}
        if sym.has_binding_info:
            item["weak"]=bool(sym.binding_info.weak_import)
            item["address"]=int(sym.binding_info.address)
        imported.append(item)
    commands=[{"name":x.name,"command":str(x.command)} for x in binary.libraries]
    install_names=[x["name"] for x in commands if "ID_DYLIB" in x["command"]]
    # Mach binding ordinals count dependency load commands, never LC_ID_DYLIB.
    # LIEF exposes both through binary.libraries, so retaining the ID here
    # would shift every embedded-dylib import by one framework.
    libraries=[x for x in commands if "ID_DYLIB" not in x["command"]]
    return {
      "path":relative_name,"cpu_type":str(binary.header.cpu_type),
      "file_type":str(binary.header.file_type),"pie":bool(binary.is_pie),
      "encrypted":bool(binary.has_encryption_info and binary.encryption_info.crypt_id),
      "install_name":install_names[0] if install_names else None,
      "libraries":libraries,"imports":imported,
    }

def detect_markers(blob):
    checks={
      "unity": [b"UnityEngine",b"globalgamemanagers",b"mainData"],
      "fmod": [b"FMOD",b"fmod_event"],
      "cocos2d": [b"cocos2d",b"CCDirector"],
      "unreal": [b"UnrealEngine",b"UE3"],
      "openal": [b"alcOpenDevice",b"alSourcePlay"],
      "opengles": [b"EAGLContext",b"glDrawArrays",b"glDrawElements"],
      "avfoundation": [b"AVAudioPlayer",b"AVPlayer",b"AVCaptureSession"],
      "audiotoolbox": [b"AudioQueue",b"AudioUnit",b"AudioSession"],
      "gamecontroller": [b"GCController"],
      "gamekit": [b"GKLocalPlayer"],
      "webkit": [b"UIWebView",b"WKWebView"],
      "corevideo": [b"CVPixelBuffer"],
    }
    return sorted(k for k,needles in checks.items() if any(x in blob for x in needles))

def audit(entry, base, work):
    name=entry["name"]; target=work/"app.ipa"
    url=base.rstrip("/")+"/"+urllib.parse.quote(name,safe="/")
    req=urllib.request.Request(url,headers={"User-Agent":"LiveExec32-corpus-audit/1"})
    with urllib.request.urlopen(req,timeout=120) as src,target.open("wb") as dst:
        shutil.copyfileobj(src,dst,1024*1024)
    actual_size=target.stat().st_size
    if entry.get("size") and actual_size != entry["size"]:
        raise ValueError(f"size mismatch {actual_size} != {entry['size']}")
    for alg in ("md5","sha1"):
        if entry.get(alg) and digest(target,alg).lower()!=entry[alg].lower():
            raise ValueError(f"{alg} mismatch")
    with zipfile.ZipFile(target) as z:
        infos=z.infolist()
        plists=[i for i in infos if i.filename.startswith("Payload/") and i.filename.count("/")==2 and i.filename.endswith(".app/Info.plist")]
        if not plists: raise ValueError("top-level app Info.plist missing")
        info=plistlib.loads(z.read(plists[0]))
        app_root=plists[0].filename[:-len("Info.plist")]
        executable=app_root+info["CFBundleExecutable"]
        resource_names=[i.filename for i in infos]
        macho_infos=[i for i in infos if i.filename.startswith(app_root) and is_macho_member(z,i)]
        images=[]
        primary=None
        for index,macho_info in enumerate(macho_infos):
            image_path=work/f"MachO-{index}"
            with z.open(macho_info) as src,image_path.open("wb") as dst:
                shutil.copyfileobj(src,dst)
            relative=macho_info.filename[len(app_root):]
            description=describe_macho(image_path,relative)
            if description is None:
                continue
            images.append(description)
            if macho_info.filename==executable:
                primary=description
                exe_path=image_path
        if primary is None: raise ValueError("main executable Mach-O missing")
    raw=exe_path.read_bytes()
    return {
      "status":"ok","archive_name":name,"archive_url":url,"archive_size":actual_size,
      "bundle_id":info.get("CFBundleIdentifier"),"bundle_version":info.get("CFBundleVersion"),
      "short_version":info.get("CFBundleShortVersionString"),"minimum_os":info.get("MinimumOSVersion"),
      "executable":info.get("CFBundleExecutable"),"cpu_type":primary["cpu_type"],
      "file_type":primary["file_type"],"pie":primary["pie"],"encrypted":primary["encrypted"],
      "libraries":primary["libraries"],"imports":primary["imports"],"images":images,
      "markers":detect_markers(raw),
      "has_managed":any("/Data/Managed/" in x for x in resource_names),
      "has_unity_data":any(x.endswith("/Data/mainData") or x.endswith("/Data/globalgamemanagers") for x in resource_names),
      "framework_count":sum(1 for x in resource_names if ".app/Frameworks/" in x and x.endswith(".framework/Info.plist")),
    }

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--manifest",required=True); ap.add_argument("--output",required=True)
    ap.add_argument("--shard-index",type=int,default=0); ap.add_argument("--shard-count",type=int,default=1)
    args=ap.parse_args()
    manifest=json.load(open(args.manifest)); apps=manifest["apps"]; base=manifest["source"]
    selected=[x for i,x in enumerate(apps) if i%args.shard_count==args.shard_index]
    out=[]
    with tempfile.TemporaryDirectory() as td:
        work=Path(td)
        for entry in selected:
            appwork=work/"one"; shutil.rmtree(appwork,ignore_errors=True); appwork.mkdir()
            print(f"AUDIT {entry['name']}",flush=True)
            try: out.append(audit(entry,base,appwork))
            except Exception as e:
                out.append({"status":"error","archive_name":entry["name"],"error":repr(e)})
    Path(args.output).write_text(json.dumps(out,indent=2,sort_keys=True)+"\n")
    failures=sum(x["status"]!="ok" for x in out)
    print(f"audited={len(out)} failures={failures}")
    if failures: raise SystemExit(1)
if __name__=="__main__": main()
