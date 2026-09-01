#!/usr/bin/env python3
from pathlib import Path

path = Path("build/LiveExec32/GuestFrameworks/iAd/iAd.m")
source = path.read_text()
anchor = '''NSString *const ADBannerContentSizeIdentifierLandscape =
    @"ADBannerContentSizeLandscape";'''
if source.count(anchor) != 1:
    raise SystemExit("expected exactly one iAd landscape constant")
addition = r'''

NSString *const ADBannerContentSizeIdentifier320x50 =
    @"ADBannerContentSize320x50";
NSString *const ADBannerContentSizeIdentifier480x32 =
    @"ADBannerContentSize480x32";
'''
path.write_text(source.replace(anchor, anchor + addition))
