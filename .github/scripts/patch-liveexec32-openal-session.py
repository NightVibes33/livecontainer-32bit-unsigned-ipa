#!/usr/bin/env python3
from pathlib import Path
p=Path('build/LiveExec32/HostFrameworks/OpenAL/OpenAL.mm')
s=p.read_text()
if '@import AVFAudio;' not in s:
    s=s.replace('@import Darwin;\n@import OpenAL;', '@import Darwin;\n@import OpenAL;\n@import AVFAudio;', 1)
old='''            ALCdevice *device = alcOpenDevice(hasName ? name.c_str() : nullptr);'''
new='''            /* Legacy ObjectAL expects alcOpenDevice to activate playback. */
            NSError *activationError = nil;
            AVAudioSession *audioSession = AVAudioSession.sharedInstance;
            if(![audioSession setActive:YES error:&activationError]) {
                NSLog(@\"LC32 OpenAL: audio-session activation failed: %@\",
                    activationError);
            }
            ALCdevice *device = alcOpenDevice(hasName ? name.c_str() : nullptr);'''
if old not in s: raise SystemExit('OpenAL device anchor missing')
s=s.replace(old,new,1)
p.write_text(s)
print('OpenAL: activates AVAudioSession before opening playback device')
