from pathlib import Path

path = Path("build/LiveExec32/GuestFrameworks/Security/Security.m")
source = path.read_text()
anchor = 'const CFStringRef kSecAttrAccessible = CFSTR("pdmn");'
if source.count(anchor) != 1:
    raise SystemExit("expected exactly one Security accessibility anchor")
addition = anchor + """
const CFStringRef kSecAttrAccessibleWhenUnlocked = CFSTR("ak");
const CFStringRef kSecAttrAccessibleAfterFirstUnlock = CFSTR("ck");
const CFStringRef kSecAttrAccessibleAlways = CFSTR("dk");
const CFStringRef kSecAttrAccessibleWhenUnlockedThisDeviceOnly = CFSTR("aku");
const CFStringRef kSecAttrAccessibleAlwaysThisDeviceOnly = CFSTR("dku");
const CFStringRef kSecAttrAccessibleWhenPasscodeSetThisDeviceOnly = CFSTR("akpu");"""
source = source.replace(anchor, addition)
service_anchor = 'const CFStringRef kSecAttrService = CFSTR("svce");'
if source.count(service_anchor) != 1:
    raise SystemExit("expected exactly one Security service anchor")
more = service_anchor + """
const CFStringRef kSecAttrDescription = CFSTR("desc");
const CFStringRef kSecAttrComment = CFSTR("icmt");
const CFStringRef kSecAttrCreator = CFSTR("crtr");
const CFStringRef kSecAttrType = CFSTR("type");
const CFStringRef kSecAttrLabel = CFSTR("labl");
const CFStringRef kSecAttrIsInvisible = CFSTR("invi");
const CFStringRef kSecAttrIsNegative = CFSTR("nega");
const CFStringRef kSecAttrSynchronizable = CFSTR("sync");"""
path.write_text(source.replace(service_anchor, more))
