#!/usr/bin/env python3
"""Ensure the legacy AudioServices alert-sound surface required by Gravity Falls.

The MediaToolbox/audio-processing compatibility patch may already install the
symbol in LC32LegacyAlertSoundCompat.m.  Do not emit a second definition into
AudioToolbox.m when that standalone implementation is present.
"""
from pathlib import Path

framework = Path("build/LiveExec32/GuestFrameworks/AudioToolbox")
path = framework / "AudioToolbox.m"
compat_path = framework / "LC32LegacyAlertSoundCompat.m"
source = path.read_text()
compat_source = compat_path.read_text() if compat_path.exists() else ""

signature = "void AudioServicesPlayAlertSound(SystemSoundID"
if signature in source:
    print("AudioToolbox: AudioServicesPlayAlertSound already present in AudioToolbox.m")
elif signature in compat_source:
    print("AudioToolbox: AudioServicesPlayAlertSound supplied by LC32LegacyAlertSoundCompat.m")
else:
    source += r'''

#pragma mark Legacy SystemSound compatibility
void AudioServicesPlayAlertSound(SystemSoundID inSystemSoundID) {
    AudioServicesPlaySystemSound(inSystemSoundID);
}
'''
    path.write_text(source)
    print("AudioToolbox: added AudioServicesPlayAlertSound compatibility alias")
