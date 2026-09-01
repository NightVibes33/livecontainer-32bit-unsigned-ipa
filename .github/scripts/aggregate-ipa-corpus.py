#!/usr/bin/env python3
import collections, glob, json
from pathlib import Path
reports=[]
for path in glob.glob("corpus-results/**/*.json",recursive=True):
    data=json.load(open(path))
    if isinstance(data,list): reports.extend(data)
ok=[x for x in reports if x.get("status")=="ok"]
engines=collections.Counter(m for x in ok for m in x.get("markers",[]))
images=[image for app in ok for image in app.get("images", [{"libraries":app.get("libraries",[]),"imports":app.get("imports",[])}])]
libs=collections.Counter(y["name"] for image in images for y in image.get("libraries",[]))
imports=collections.Counter(y["name"] for image in images for y in image.get("imports",[]))
weak=collections.Counter(y["name"] for image in images for y in image.get("imports",[]) if y.get("weak"))
summary={
 "total":len(reports),"ok":len(ok),"failed":len(reports)-len(ok),"mach_images":len(images),
 "minimum_os":dict(collections.Counter(str(x.get("minimum_os")) for x in ok)),
 "markers":engines.most_common(),"libraries":libs.most_common(),
 "imports":imports.most_common(),"weak_imports":weak.most_common(),
 "failures":[x for x in reports if x.get("status")!="ok"],
}
Path("corpus-summary.json").write_text(json.dumps(summary,indent=2)+"\n")
lines=["# LiveExec32 37-app corpus audit","",f"- Audited: {len(reports)}",f"- Successful: {len(ok)}",f"- Failed: {len(reports)-len(ok)}",f"- Mach-O images: {len(images)}","","## Engine/API markers",""]
lines += [f"- `{k}`: {v}" for k,v in engines.most_common()]
lines += ["","## Most common libraries",""]
lines += [f"- `{k}`: {v}" for k,v in libs.most_common(60)]
lines += ["","## Most common weak imports",""]
lines += [f"- `{k}`: {v}" for k,v in weak.most_common(100)]
Path("corpus-summary.md").write_text("\n".join(lines)+"\n")
if len(reports)!=37 or len(ok)!=37: raise SystemExit("corpus audit incomplete")
