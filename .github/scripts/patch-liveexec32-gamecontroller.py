#!/usr/bin/env python3
from pathlib import Path

path = Path("build/LiveExec32/GuestFrameworks/GameController/GCController+LC32.m")
path.parent.mkdir(parents=True, exist_ok=True)
path.write_text(r'''#import <GameController/GameController.h>

NSString *const GCControllerDidConnectNotification =
    @"GCControllerDidConnectNotification";
NSString *const GCControllerDidDisconnectNotification =
    @"GCControllerDidDisconnectNotification";
''')
