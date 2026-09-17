#!/usr/bin/env python3
"""Add the legacy AudioServices alert-sound surface required by Gravity Falls."""
from pathlib import Path

path = Path("build/LiveExec32/GuestFrameworks/AudioToolbox/AudioToolbox.m")
source = path.read_text()

signature = "void AudioServicesPlayAlertSound(SystemSoundID"
if signature not in source:
    source += r'''

#pragma mark Legacy SystemSound compatibility
void AudioServicesPlayAlertSound(SystemSoundID inSystemSoundID) {
    AudioServicesPlaySystemSound(inSystemSoundID);
}
'''
    path.write_text(source)
    print("AudioToolbox: added AudioServicesPlayAlertSound compatibility alias")
else:
    print("AudioToolbox: AudioServicesPlayAlertSound already present")
