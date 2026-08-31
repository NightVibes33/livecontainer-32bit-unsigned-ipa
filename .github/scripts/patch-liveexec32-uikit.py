from pathlib import Path

path = Path("build/LiveExec32/GuestFrameworks/UIKit/UIKit.m")
source = path.read_text()
anchor = """NSString *const UIKeyboardBoundsUserInfoKey =
    @\"UIKeyboardBoundsUserInfoKey\";"""
if source.count(anchor) != 1:
    raise SystemExit("expected exactly one UIKit keyboard anchor")
addition = anchor + """
NSString *const UIKeyboardCenterBeginUserInfoKey =
    @\"UIKeyboardCenterBeginUserInfoKey\";
NSString *const UIKeyboardCenterEndUserInfoKey =
    @\"UIKeyboardCenterEndUserInfoKey\";"""
path.write_text(source.replace(anchor, addition))
