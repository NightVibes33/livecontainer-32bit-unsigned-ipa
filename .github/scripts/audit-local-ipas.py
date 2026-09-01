#!/usr/bin/env python3
import argparse, importlib.util, json, plistlib, shutil, tempfile, zipfile
from pathlib import Path

spec=importlib.util.spec_from_file_location("corpus_audit", Path(__file__).with_name("audit-ipa-corpus.py"))
audit=importlib.util.module_from_spec(spec); spec.loader.exec_module(audit)

def scan(ipa, work):
    with zipfile.ZipFile(ipa) as archive:
        infos=archive.infolist()
        plists=[x for x in infos if x.filename.startswith("Payload/") and x.filename.count("/")==2 and x.filename.endswith(".app/Info.plist")]
        if not plists: raise ValueError("top-level app Info.plist missing")
        info=plistlib.loads(archive.read(plists[0]))
        app_root=plists[0].filename[:-len("Info.plist")]
        executable=app_root+info["CFBundleExecutable"]
        images=[]; primary_path=None
        for index,member in enumerate(x for x in infos if x.filename.startswith(app_root) and audit.is_macho_member(archive,x)):
            path=work/f"MachO-{index}"
            with archive.open(member) as source,path.open("wb") as target: shutil.copyfileobj(source,target)
            description=audit.describe_macho(path,member.filename[len(app_root):])
            if description is None: continue
            images.append(description)
            if member.filename==executable: primary_path=path
        primary=next((x for x in images if x["path"]==info["CFBundleExecutable"]),None)
        if primary is None or primary_path is None: raise ValueError("ARM32 main executable missing")
        names=[x.filename for x in infos]
    return {"status":"ok","archive_name":Path(ipa).name,"bundle_id":info.get("CFBundleIdentifier"),"bundle_version":info.get("CFBundleVersion"),"short_version":info.get("CFBundleShortVersionString"),"minimum_os":info.get("MinimumOSVersion"),"executable":info.get("CFBundleExecutable"),"cpu_type":primary["cpu_type"],"file_type":primary["file_type"],"pie":primary["pie"],"encrypted":primary["encrypted"],"libraries":primary["libraries"],"imports":primary["imports"],"images":images,"markers":audit.detect_markers(primary_path.read_bytes()),"has_managed":any("/Data/Managed/" in x for x in names),"has_unity_data":any(x.endswith("/Data/mainData") or x.endswith("/Data/globalgamemanagers") for x in names),"framework_count":sum(1 for x in names if ".app/Frameworks/" in x and x.endswith(".framework/Info.plist"))}

def main():
    parser=argparse.ArgumentParser();parser.add_argument("--ipa",action="append",required=True);parser.add_argument("--output",required=True);args=parser.parse_args();out=[]
    with tempfile.TemporaryDirectory() as temporary:
        for index,name in enumerate(args.ipa):
            work=Path(temporary)/str(index);work.mkdir();out.append(scan(name,work))
    Path(args.output).write_text(json.dumps(out,indent=2,sort_keys=True)+"\n")
    print(f"audited={len(out)} images={sum(len(x['images']) for x in out)}")
if __name__=="__main__":main()
