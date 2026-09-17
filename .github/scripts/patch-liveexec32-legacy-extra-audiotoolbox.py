#!/usr/bin/env python3
"""Ensure the legacy AudioServices alert-sound surface required by Gravity Falls.

The MediaToolbox/audio-processing compatibility patch may already install the
symbol in LC32LegacyAlertSoundCompat.m. Do not emit a second definition into
AudioToolbox.m when that standalone implementation is present. In that case,
add only an extern declaration so source-level compatibility checks still see
the public surface without creating a duplicate linker symbol.
"""
from pathlib import Path
import re

framework = Path("build/LiveExec32/GuestFrameworks/AudioToolbox")
path = framework / "AudioToolbox.m"
compat_path = framework / "LC32LegacyAlertSoundCompat.m"
source = path.read_text()
compat_source = compat_path.read_text() if compat_path.exists() else ""

signature = "void AudioServicesPlayAlertSound(SystemSoundID"
definition_re = re.compile(r"(?m)^\s*void\s+AudioServicesPlayAlertSound\s*\(SystemSoundID[^;]*\)\s*\{")

source_has_definition = bool(definition_re.search(source))
compat_has_definition = bool(definition_re.search(compat_source))
if source_has_definition and compat_has_definition:
    raise SystemExit("AudioToolbox: duplicate AudioServicesPlayAlertSound implementations before patch")

if source_has_definition:
    print("AudioToolbox: AudioServicesPlayAlertSound implemented in AudioToolbox.m")
elif compat_has_definition:
    if signature not in source:
        source += r'''

#pragma mark Legacy SystemSound compatibility declaration
extern void AudioServicesPlayAlertSound(SystemSoundID inSystemSoundID);
'''
        path.write_text(source)
    print("AudioToolbox: AudioServicesPlayAlertSound implemented by LC32LegacyAlertSoundCompat.m")
else:
    source += r'''

#pragma mark Legacy SystemSound compatibility
void AudioServicesPlayAlertSound(SystemSoundID inSystemSoundID) {
    AudioServicesPlaySystemSound(inSystemSoundID);
}
'''
    path.write_text(source)
    print("AudioToolbox: added AudioServicesPlayAlertSound compatibility alias")

# Enforce exactly one implementation across the framework source set.
definitions = 0
for candidate in framework.glob("*.m"):
    definitions += len(definition_re.findall(candidate.read_text(errors="ignore")))
if definitions != 1:
    raise SystemExit(f"AudioToolbox: expected exactly one AudioServicesPlayAlertSound implementation, found {definitions}")
print("AudioToolbox: exactly one AudioServicesPlayAlertSound implementation verified")
