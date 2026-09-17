#!/usr/bin/env python3
from pathlib import Path

path = Path("build/LiveExec32/GuestFrameworks/MediaToolbox/LC32MTAudioProcessingTapCompat.m")
path.parent.mkdir(parents=True, exist_ok=True)
path.write_text(r'''
#include <stdint.h>
#include <stddef.h>

/*
 * Old Unity players use MediaToolbox's audio-processing tap as an optional
 * effect path. LiveExec32 does not yet expose a host MTAudioProcessingTap
 * bridge, so fail creation explicitly instead of reporting success with an
 * invalid tap. Callers can then retain their unprocessed audio path.
 */
typedef void *MTAudioProcessingTapRef;
typedef int32_t OSStatus;
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

print("installed MediaToolbox MTAudioProcessingTap compatibility exports")
