#!/usr/bin/env python3
from pathlib import Path

p = Path("build/LiveExec32/GuestFrameworks/AudioToolbox/AudioToolbox.m")
s = p.read_text()

marker = "parameters[64]"
if marker in s:
    print("AudioToolbox: parameter storage already present")
    raise SystemExit(0)

struct_anchor = "typedef struct LC32SilentAudioUnit"
render_anchor = "    AURenderCallbackStruct renderCallback;\n"

struct_pos = s.find(struct_anchor)
if struct_pos < 0:
    raise SystemExit("LC32SilentAudioUnit struct anchor missing")

render_pos = s.find(render_anchor, struct_pos)
if render_pos < 0:
    raise SystemExit("LC32SilentAudioUnit renderCallback anchor missing")

# Guard against accidentally patching another later structure if upstream changes.
struct_end = s.find("} LC32SilentAudioUnit;", struct_pos)
if struct_end < 0 or render_pos > struct_end:
    raise SystemExit("LC32SilentAudioUnit structure boundary missing")

parameter_storage = (
    render_anchor
    + "    struct { AudioUnitParameterID id; AudioUnitScope scope; AudioUnitElement element; "
      "AudioUnitParameterValue value; BOOL used; } parameters[64];\n"
)
s = s[:render_pos] + s[render_pos:].replace(render_anchor, parameter_storage, 1)
p.write_text(s)

# Verify we preserved upstream render-notify state and inserted storage in the intended struct.
patched = p.read_text()
if marker not in patched:
    raise SystemExit("AudioToolbox parameter storage insertion failed")
if "LC32SilentAudioRenderNotify *renderNotifies;" not in patched:
    raise SystemExit("AudioToolbox render-notify fields unexpectedly missing")

print("AudioToolbox: inserted parameter storage without disturbing render-notify layout")
