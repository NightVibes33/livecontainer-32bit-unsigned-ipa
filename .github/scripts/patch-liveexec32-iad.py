#!/usr/bin/env python3
from pathlib import Path

path = Path("build/LiveExec32/GuestFrameworks/iAd/iAd.m")
source = path.read_text()

# These legacy banner constants are native to the pinned nightly runtime now.
# Keep this migration hook as an assertion instead of re-defining them.
required = (
    "ADBannerContentSizeIdentifier320x50",
    "ADBannerContentSizeIdentifier480x32",
)
for symbol in required:
    if source.count(symbol) != 1:
        raise SystemExit(f"expected nightly iAd export exactly once: {symbol}")
