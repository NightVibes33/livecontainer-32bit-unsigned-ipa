#!/usr/bin/env python3
from pathlib import Path

media = Path("build/LiveExec32/GuestFrameworks/MediaToolbox/LC32MTAudioProcessingTapCompat.m")
media.parent.mkdir(parents=True, exist_ok=True)
media.write_text(r'''
#include <stdint.h>
#include <stddef.h>
#include <MacTypes.h>

/*
 * Old Unity players use MediaToolbox's audio-processing tap as an optional
 * effect path. LiveExec32 does not yet expose a host MTAudioProcessingTap
 * bridge, so fail creation explicitly instead of reporting success with an
 * invalid tap. Callers can then retain their unprocessed audio path.
 */
typedef void *MTAudioProcessingTapRef;
typedef uint32_t MTAudioProcessingTapCreationFlags;
typedef uint32_t MTAudioProcessingTapFlags;
typedef int32_t CMItemCount;

OSStatus MTAudioProcessingTapCreate(
        const void *allocator,
        const void *callbacks,
        MTAudioProcessingTapCreationFlags flags,
        MTAudioProcessingTapRef *tapOut) {
    (void)allocator;
    (void)callbacks;
    (void)flags;
    if (tapOut) *tapOut = NULL;
    return -50; /* paramErr / unsupported compatibility path */
}

void *MTAudioProcessingTapGetStorage(MTAudioProcessingTapRef tap) {
    (void)tap;
    return NULL;
}

OSStatus MTAudioProcessingTapGetSourceAudio(
        MTAudioProcessingTapRef tap,
        CMItemCount numberFrames,
        void *bufferListInOut,
        MTAudioProcessingTapFlags *flagsOut,
        void *timeRangeOut,
        CMItemCount *numberFramesOut) {
    (void)tap;
    (void)numberFrames;
    (void)bufferListInOut;
    (void)timeRangeOut;
    if (flagsOut) *flagsOut = 0;
    if (numberFramesOut) *numberFramesOut = 0;
    return -50;
}
''')

audio = Path("build/LiveExec32/GuestFrameworks/AudioToolbox/LC32LegacyAlertSoundCompat.m")
audio.parent.mkdir(parents=True, exist_ok=True)
audio.write_text(r'''
#include <stdint.h>

typedef uint32_t SystemSoundID;

extern void AudioServicesPlaySystemSound(SystemSoundID inSystemSoundID);

/* Legacy alert sound uses the same guest system-sound transport. The host
 * runtime cannot reproduce the historical alert/vibrate policy exactly, but
 * routing the sound ID through the implemented system-sound path preserves
 * the app-visible audio behavior instead of silently dropping the call. */
void AudioServicesPlayAlertSound(SystemSoundID inSystemSoundID) {
    AudioServicesPlaySystemSound(inSystemSoundID);
}
''')

print("installed MediaToolbox tap and legacy AudioServices alert compatibility exports")
