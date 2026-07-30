#!/usr/bin/env python3
from pathlib import Path

path = Path('LiveContainer/LCBootstrap.m')
text = path.read_text()
old = '''    if(is32bit) {
        if (!isJitEnabled) {
            isJitEnabled = waitForJITEnabled(80, 1000 * 100);
            if(isJitEnabled) {
                init_bypassDyldLibValidation();
            }
        }
        if (!isJitEnabled) {
            return @"JIT is required to run 32-bit apps through LiveExec32.";
        }
        
        NSString *selected32BitLayerExecPath = nil;
'''
new = '''    if(is32bit) {
        // LiveExec32 now executes ARMv7 through the bundled no-JIT interpreter.
        // Do not block 32-bit guests on host JIT availability.
        NSLog(@"[LCBootstrap] Launching 32-bit guest through no-JIT LiveExec32 runtime.");

        NSString *selected32BitLayerExecPath = nil;
'''
if old not in text:
    raise SystemExit('obsolete 32-bit JIT gate not found')
text = text.replace(old, new, 1)
path.write_text(text)
