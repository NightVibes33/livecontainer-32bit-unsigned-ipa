#!/usr/bin/env python3
from pathlib import Path

path = Path('LiveContainer/LCBootstrap.m')
source = path.read_text()
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
        if (!isJitEnabled) {
            NSLog(@"[LCBootstrap] Launching 32-bit guest through the no-JIT LiveExec32 interpreter.");
        }

        NSString *selected32BitLayerExecPath = nil;
'''
if old not in source:
    raise SystemExit('32-bit JIT gate block not found')
source = source.replace(old, new, 1)
if 'JIT is required to run 32-bit apps through LiveExec32.' in source:
    raise SystemExit('JIT gate string still present')
path.write_text(source)
