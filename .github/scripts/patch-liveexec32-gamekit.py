from pathlib import Path

path = Path("build/LiveExec32/GuestFrameworks/GameKit/GKLocalPlayer+LC32.m")
source = path.read_text()
anchor = '#import <GameKit/GameKit.h>'
if source.count(anchor) != 1:
    raise SystemExit("expected exactly one GameKit import anchor")
constants = """

NSString * const GKErrorDomain = @"GKErrorDomain";
NSString * const GKPlayerAuthenticationDidChangeNotificationName =
    @"GKPlayerAuthenticationDidChangeNotificationName";
"""
path.write_text(source.replace(anchor, anchor + constants))
