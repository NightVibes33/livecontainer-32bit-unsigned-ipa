#!/usr/bin/env python3
import argparse, collections, glob, json
from pathlib import Path


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--manifest",required=True)
    ap.add_argument("--results-glob",default="cartoon-network-results/**/*.json")
    ap.add_argument("--json-output",default="cartoon-network-summary.json")
    ap.add_argument("--md-output",default="cartoon-network-summary.md")
    args=ap.parse_args()

    manifest=json.load(open(args.manifest))
    expected=manifest.get("apps",[])
    expected_names=[x["name"] for x in expected]
    expected_set=set(expected_names)

    reports=[]
    for path in glob.glob(args.results_glob,recursive=True):
        data=json.load(open(path))
        if isinstance(data,list): reports.extend(data)

    names=[x.get("archive_name") for x in reports]
    counts=collections.Counter(names)
    duplicates=sorted(k for k,v in counts.items() if k is not None and v>1)
    observed_set={x for x in names if x is not None}
    missing=sorted(expected_set-observed_set)
    unexpected=sorted(observed_set-expected_set)

    ok=[x for x in reports if x.get("status")=="ok"]
    failed=[x for x in reports if x.get("status")!="ok"]
    images=[image for app in ok for image in app.get("images",[])]
    libs=collections.Counter(y.get("name") for image in images for y in image.get("libraries",[]) if y.get("name"))
    imports=collections.Counter(y.get("name") for image in images for y in image.get("imports",[]) if y.get("name"))
    weak=collections.Counter(y.get("name") for image in images for y in image.get("imports",[]) if y.get("name") and y.get("weak"))
    markers=collections.Counter(m for app in ok for m in app.get("markers",[]))
    min_os=collections.Counter(str(app.get("minimum_os")) for app in ok)
    sdk=collections.Counter(str(app.get("sdk_name")) for app in ok)
    cpu=collections.Counter(f"{app.get('cpu_type')} / {app.get('cpu_subtype')}" for app in ok)
    device_family=collections.Counter(str(app.get("device_family")) for app in ok)

    uikit_imports=collections.Counter(
        name for name,count in imports.items()
        for _ in range(count)
        if name.startswith("_OBJC_CLASS_$_UI") or name.startswith("_OBJC_METACLASS_$_UI") or name.startswith("_UI")
    )

    summary={
        "archive_identifier":manifest.get("identifier"),
        "expected":len(expected_names),
        "reported":len(reports),
        "ok":len(ok),
        "failed":len(failed),
        "missing":missing,
        "duplicates":duplicates,
        "unexpected":unexpected,
        "mach_images":len(images),
        "minimum_os":dict(min_os),
        "sdk_names":dict(sdk),
        "cpu":dict(cpu),
        "device_family":dict(device_family),
        "markers":markers.most_common(),
        "libraries":libs.most_common(),
        "imports":imports.most_common(),
        "weak_imports":weak.most_common(),
        "uikit_imports":uikit_imports.most_common(),
        "failures":failed,
        "apps":reports,
    }
    Path(args.json_output).write_text(json.dumps(summary,indent=2,sort_keys=True)+"\n")

    lines=[
        "# Cartoon Network iOS full-corpus audit",
        "",
        f"- Archive IPAs discovered: **{len(expected_names)}**",
        f"- IPA reports emitted: **{len(reports)}**",
        f"- Successful audits: **{len(ok)}**",
        f"- Failed audits: **{len(failed)}**",
        f"- Mach-O images analyzed: **{len(images)}**",
        "",
        "## CPU slices",
        "",
    ]
    lines += [f"- `{k}`: {v}" for k,v in cpu.most_common()]
    lines += ["", "## Minimum iOS", ""]
    lines += [f"- `{k}`: {v}" for k,v in min_os.most_common()]
    lines += ["", "## SDK metadata", ""]
    lines += [f"- `{k}`: {v}" for k,v in sdk.most_common()]
    lines += ["", "## Runtime / engine markers", ""]
    lines += [f"- `{k}`: {v}" for k,v in markers.most_common()]
    lines += ["", "## Most common linked libraries", ""]
    lines += [f"- `{k}`: {v}" for k,v in libs.most_common(80)]
    lines += ["", "## Most common UIKit imports", ""]
    lines += [f"- `{k}`: {v}" for k,v in uikit_imports.most_common(120)]
    if failed:
        lines += ["", "## Audit failures", ""]
        lines += [f"- `{x.get('archive_name')}`: `{x.get('error')}`" for x in failed]
    if missing:
        lines += ["", "## Missing reports", ""]
        lines += [f"- `{x}`" for x in missing]
    if duplicates:
        lines += ["", "## Duplicate reports", ""]
        lines += [f"- `{x}`" for x in duplicates]
    if unexpected:
        lines += ["", "## Unexpected reports", ""]
        lines += [f"- `{x}`" for x in unexpected]
    Path(args.md_output).write_text("\n".join(lines)+"\n")

    complete=(
        len(reports)==len(expected_names)
        and not missing
        and not duplicates
        and not unexpected
    )
    if not complete:
        raise SystemExit("Cartoon Network corpus coverage incomplete")
    if failed:
        raise SystemExit(f"{len(failed)} Cartoon Network IPA audits failed")


if __name__=="__main__":
    main()
