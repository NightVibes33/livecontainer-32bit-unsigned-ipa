from pathlib import Path

path = Path("build/LiveExec32/GuestFrameworks/Security/Security.m")
source = path.read_text()

# The pinned nightly runtime already exports the accessibility variants plus
# description/comment/label/synchronizable. Keep this migration overlay
# additive and supply only the corpus constants that nightly still lacks.
service_anchor = 'const CFStringRef kSecAttrService = CFSTR("svce");'
if source.count(service_anchor) != 1:
    raise SystemExit("expected exactly one Security service anchor")

missing = service_anchor + """
const CFStringRef kSecAttrCreator = CFSTR("crtr");
const CFStringRef kSecAttrType = CFSTR("type");
const CFStringRef kSecAttrIsInvisible = CFSTR("invi");
const CFStringRef kSecAttrIsNegative = CFSTR("nega");"""

path.write_text(source.replace(service_anchor, missing, 1))
