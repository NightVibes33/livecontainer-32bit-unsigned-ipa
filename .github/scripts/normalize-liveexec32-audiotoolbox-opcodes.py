#!/usr/bin/env python3
"""Normalize the patched LiveExec32 AudioToolbox opcode enum.

The pinned LiveExec32 revision already owns opcodes 44-47 for AudioConverter
and ExtAudioFileWrapAudioFileID.  Older corpus patches also inserted operations
at those numeric slots and later re-added AudioConverter at 57-59.  Guest and
host compile the same bridge header, so keep the upstream ABI slots stable,
deduplicate names, and relocate only newly-added colliding operations above the
highest number present in the fully-patched table.
"""
from pathlib import Path
import re

path = Path("build/LiveExec32/GuestFrameworks/AudioToolbox/LC32AudioToolboxBridge.h")
text = path.read_text()

start_marker = "typedef enum : uint32_t {"
end_marker = "} LC32AudioToolboxOpcode;"
start = text.find(start_marker)
end = text.find(end_marker, start)
if start < 0 or end < 0:
    raise SystemExit("AudioToolbox opcode enum not found")

body_start = start + len(start_marker)
body = text[body_start:end]
lines = body.splitlines(keepends=True)
pattern = re.compile(r"^(\s*)(LC32AudioToolboxOp[A-Za-z0-9_]+)\s*=\s*(\d+),(\s*(?:/\*.*\*/)?\s*)$")

entries = []
for index, line in enumerate(lines):
    m = pattern.match(line.rstrip("\n"))
    if m:
        entries.append((index, m.group(1), m.group(2), int(m.group(3)), m.group(4), "\n" if line.endswith("\n") else ""))

if not entries:
    raise SystemExit("AudioToolbox opcode entries not found")

# These are part of the pinned upstream ABI and must not move.
canonical = {
    "LC32AudioToolboxOpAudioConverterNew": 44,
    "LC32AudioToolboxOpAudioConverterDispose": 45,
    "LC32AudioToolboxOpAudioConverterFillComplexBuffer": 46,
    "LC32AudioToolboxOpExtAudioFileWrapAudioFileID": 47,
}

all_values = [value for _, _, _, value, _, _ in entries]
next_value = max(all_values) + 1
reserved_values = set(canonical.values())
assigned_values = set()
seen_names = set()
rewrites = []
removed = []

for index, indent, name, original, suffix, newline in entries:
    if name in seen_names:
        lines[index] = ""
        removed.append((name, original))
        continue
    seen_names.add(name)

    if name in canonical:
        value = canonical[name]
    else:
        value = original
        # Preserve all non-conflicting existing/new values.  Relocate only a
        # collision with an upstream-reserved slot or another unique opcode.
        if value in reserved_values or value in assigned_values:
            while next_value in reserved_values or next_value in assigned_values:
                next_value += 1
            value = next_value
            next_value += 1

    if value in assigned_values:
        raise SystemExit(f"opcode collision remained for {name}={value}")
    assigned_values.add(value)
    if value != original:
        rewrites.append((name, original, value))
    lines[index] = f"{indent}{name} = {value},{suffix}{newline}"

new_body = "".join(lines)
new_text = text[:body_start] + new_body + text[end:]
path.write_text(new_text)

# Final strict validation: every opcode name and numeric value must be unique,
# and the pinned upstream ABI assignments must be intact.
check = path.read_text()[body_start:path.read_text().find(end_marker, body_start)]
parsed = re.findall(r"^\s*(LC32AudioToolboxOp[A-Za-z0-9_]+)\s*=\s*(\d+),", check, re.M)
names = [name for name, _ in parsed]
values = [int(value) for _, value in parsed]
if len(names) != len(set(names)):
    raise SystemExit("duplicate AudioToolbox opcode name remains")
if len(values) != len(set(values)):
    duplicates = sorted({v for v in values if values.count(v) > 1})
    raise SystemExit(f"duplicate AudioToolbox opcode values remain: {duplicates}")
resolved = dict((name, int(value)) for name, value in parsed)
for name, value in canonical.items():
    if resolved.get(name) != value:
        raise SystemExit(f"upstream opcode changed: {name}={resolved.get(name)} expected {value}")

print(f"AudioToolbox opcodes normalized: {len(parsed)} unique operations")
for name, old, new in rewrites:
    print(f"  remap {name}: {old} -> {new}")
for name, old in removed:
    print(f"  remove duplicate {name}={old}")
