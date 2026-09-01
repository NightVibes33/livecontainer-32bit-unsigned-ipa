#!/usr/bin/env python3
# Add typed CoreGraphics bridges required by the exhaustive 40-app corpus.
from pathlib import Path
ROOT = Path('build/LiveExec32')
header = ROOT/'GuestFrameworks/CoreGraphics/LC32CoreGraphicsBridge.h'
guest = ROOT/'GuestFrameworks/CoreGraphics/CoreGraphics.m'
host = ROOT/'HostFrameworks/CoreGraphics/CoreGraphics.mm'

h=header.read_text()
if 'LC32CoreGraphicsOpBitmapContextGetHeight = 89' not in h:
 anchor='    LC32CoreGraphicsOpContextStrokeEllipseInRect = 85,\n'
 if anchor not in h: raise SystemExit('opcode anchor missing')
 h=h.replace(anchor,anchor+r'''    LC32CoreGraphicsOpBitmapContextGetHeight = 89,
    LC32CoreGraphicsOpBitmapContextGetWidth = 90,
    LC32CoreGraphicsOpColorCreateCopy = 91,
    LC32CoreGraphicsOpColorCreateCopyWithAlpha = 92,
    LC32CoreGraphicsOpColorEqualToColor = 93,
    LC32CoreGraphicsOpColorGetTypeID = 94,
    LC32CoreGraphicsOpColorSpaceCreateWithName = 95,
    LC32CoreGraphicsOpColorSpaceGetBaseColorSpace = 96,
    LC32CoreGraphicsOpColorSpaceGetNumberOfComponents = 97,
    LC32CoreGraphicsOpImageCreateCopy = 98,
    LC32CoreGraphicsOpImageGetDataProvider = 99,
    LC32CoreGraphicsOpImageGetRenderingIntent = 100,
    LC32CoreGraphicsOpImageGetShouldInterpolate = 101,
    LC32CoreGraphicsOpContextSetAllowsAntialiasing = 102,
    LC32CoreGraphicsOpContextSetAlpha = 103,
    LC32CoreGraphicsOpContextFlush = 104,
''')
 header.write_text(h)

g=guest.read_text()
if 'size_t CGBitmapContextGetHeight(' not in g:
 g += r'''
#pragma mark Exhaustive corpus CoreGraphics bridges
size_t CGBitmapContextGetHeight(CGContextRef c) { return c ? (size_t)LC32_CG_CALL(LC32CoreGraphicsOpBitmapContextGetHeight,LC32_CG_HOST(c)):0; }
size_t CGBitmapContextGetWidth(CGContextRef c) { return c ? (size_t)LC32_CG_CALL(LC32CoreGraphicsOpBitmapContextGetWidth,LC32_CG_HOST(c)):0; }
CGColorRef CGColorCreateCopy(CGColorRef c) { return c?(CGColorRef)LC32_CG_CALL(LC32CoreGraphicsOpColorCreateCopy,LC32_CG_HOST(c)):NULL; }
CGColorRef CGColorCreateCopyWithAlpha(CGColorRef c, CGFloat a) { return c?(CGColorRef)LC32_CG_CALL(LC32CoreGraphicsOpColorCreateCopyWithAlpha,LC32_CG_HOST(c),LC32_CG_F32(a)):NULL; }
bool CGColorEqualToColor(CGColorRef a, CGColorRef b) { if(a==b)return true; return a&&b&&LC32_CG_CALL(LC32CoreGraphicsOpColorEqualToColor,LC32_CG_HOST(a),LC32_CG_HOST(b)); }
CFTypeID CGColorGetTypeID(void) { return (CFTypeID)LC32_CG_CALL0(LC32CoreGraphicsOpColorGetTypeID); }
CGColorSpaceRef CGColorSpaceCreateWithName(CFStringRef n) { return n?(CGColorSpaceRef)LC32_CG_CALL(LC32CoreGraphicsOpColorSpaceCreateWithName,LC32_CG_HOST(n)):NULL; }
CGColorSpaceRef CGColorSpaceGetBaseColorSpace(CGColorSpaceRef s) { return s?(CGColorSpaceRef)LC32_CG_CALL(LC32CoreGraphicsOpColorSpaceGetBaseColorSpace,LC32_CG_HOST(s)):NULL; }
size_t CGColorSpaceGetNumberOfComponents(CGColorSpaceRef s) { return s?(size_t)LC32_CG_CALL(LC32CoreGraphicsOpColorSpaceGetNumberOfComponents,LC32_CG_HOST(s)):0; }
CGImageRef CGImageCreateCopy(CGImageRef i) { return i?(CGImageRef)LC32_CG_CALL(LC32CoreGraphicsOpImageCreateCopy,LC32_CG_HOST(i)):NULL; }
CGDataProviderRef CGImageGetDataProvider(CGImageRef i) { return i?(CGDataProviderRef)LC32_CG_CALL(LC32CoreGraphicsOpImageGetDataProvider,LC32_CG_HOST(i)):NULL; }
CGColorRenderingIntent CGImageGetRenderingIntent(CGImageRef i) { return i?(CGColorRenderingIntent)LC32_CG_CALL(LC32CoreGraphicsOpImageGetRenderingIntent,LC32_CG_HOST(i)):kCGRenderingIntentDefault; }
bool CGImageGetShouldInterpolate(CGImageRef i) { return i&&LC32_CG_CALL(LC32CoreGraphicsOpImageGetShouldInterpolate,LC32_CG_HOST(i)); }
void CGContextSetAllowsAntialiasing(CGContextRef c,bool v) { if(c)(void)LC32_CG_CALL(LC32CoreGraphicsOpContextSetAllowsAntialiasing,LC32_CG_HOST(c),LC32_CG_U32(v)); }
void CGContextSetAlpha(CGContextRef c,CGFloat a) { if(c)(void)LC32_CG_CALL(LC32CoreGraphicsOpContextSetAlpha,LC32_CG_HOST(c),LC32_CG_F32(a)); }
void CGContextFlush(CGContextRef c) { if(c)(void)LC32_CG_CALL(LC32CoreGraphicsOpContextFlush,LC32_CG_HOST(c)); }
'''
 guest.write_text(g)

x=host.read_text()
if 'case LC32CoreGraphicsOpBitmapContextGetHeight:' not in x:
 cases=r'''
        case LC32CoreGraphicsOpBitmapContextGetHeight:
        case LC32CoreGraphicsOpBitmapContextGetWidth: {
            if(!RequireCoreGraphicsSlots(call,1)) return 0;
            CGContextRef c=SlotHostObject<CGContextRef>(call,0); if(!c)return 0;
            return static_cast<u32>(opcode==LC32CoreGraphicsOpBitmapContextGetHeight?CGBitmapContextGetHeight(c):CGBitmapContextGetWidth(c));
        }
        case LC32CoreGraphicsOpColorCreateCopy:
        case LC32CoreGraphicsOpColorCreateCopyWithAlpha: {
            const bool alpha=opcode==LC32CoreGraphicsOpColorCreateCopyWithAlpha;
            if(!RequireCoreGraphicsSlots(call,alpha?2:1))return 0;
            CGColorRef c=SlotHostObject<CGColorRef>(call,0); if(!c)return 0;
            CGColorRef r=alpha?CGColorCreateCopyWithAlpha(c,SlotCGFloat(call,1)):CGColorCreateCopy(c);
            return r?LC32GuestObjectForOwnedHostObject(r):0;
        }
        case LC32CoreGraphicsOpColorEqualToColor: {
            if(!RequireCoreGraphicsSlots(call,2))return 0;
            CGColorRef a=SlotHostObject<CGColorRef>(call,0),b=SlotHostObject<CGColorRef>(call,1);
            return a&&b&&CGColorEqualToColor(a,b);
        }
        case LC32CoreGraphicsOpColorGetTypeID: return RequireCoreGraphicsSlots(call,0)?static_cast<u32>(CGColorGetTypeID()):0;
        case LC32CoreGraphicsOpColorSpaceCreateWithName: {
            if(!RequireCoreGraphicsSlots(call,1))return 0;
            CFStringRef n=SlotHostObject<CFStringRef>(call,0); CGColorSpaceRef r=n?CGColorSpaceCreateWithName(n):nullptr;
            return r?LC32GuestObjectForOwnedHostObject(r):0;
        }
        case LC32CoreGraphicsOpColorSpaceGetBaseColorSpace: {
            if(!RequireCoreGraphicsSlots(call,1))return 0;
            CGColorSpaceRef s=SlotHostObject<CGColorSpaceRef>(call,0); CGColorSpaceRef r=s?CGColorSpaceGetBaseColorSpace(s):nullptr;
            return r?[(id)r guest_self]:0;
        }
        case LC32CoreGraphicsOpColorSpaceGetNumberOfComponents: {
            if(!RequireCoreGraphicsSlots(call,1))return 0;
            CGColorSpaceRef s=SlotHostObject<CGColorSpaceRef>(call,0); return s?static_cast<u32>(CGColorSpaceGetNumberOfComponents(s)):0;
        }
        case LC32CoreGraphicsOpImageCreateCopy: {
            if(!RequireCoreGraphicsSlots(call,1))return 0;
            CGImageRef i=SlotHostObject<CGImageRef>(call,0); CGImageRef r=i?CGImageCreateCopy(i):nullptr;
            return r?LC32GuestObjectForOwnedHostObject(r):0;
        }
        case LC32CoreGraphicsOpImageGetDataProvider: {
            if(!RequireCoreGraphicsSlots(call,1))return 0;
            CGImageRef i=SlotHostObject<CGImageRef>(call,0); CGDataProviderRef r=i?CGImageGetDataProvider(i):nullptr;
            return r?[(id)r guest_self]:0;
        }
        case LC32CoreGraphicsOpImageGetRenderingIntent: {
            if(!RequireCoreGraphicsSlots(call,1))return 0; CGImageRef i=SlotHostObject<CGImageRef>(call,0);
            return i?static_cast<u32>(CGImageGetRenderingIntent(i)):0;
        }
        case LC32CoreGraphicsOpImageGetShouldInterpolate: {
            if(!RequireCoreGraphicsSlots(call,1))return 0; CGImageRef i=SlotHostObject<CGImageRef>(call,0);
            return i&&CGImageGetShouldInterpolate(i);
        }
        case LC32CoreGraphicsOpContextSetAllowsAntialiasing:
        case LC32CoreGraphicsOpContextSetAlpha: {
            if(!RequireCoreGraphicsSlots(call,2))return 0; CGContextRef c=SlotHostObject<CGContextRef>(call,0); if(!c)return 0;
            if(opcode==LC32CoreGraphicsOpContextSetAllowsAntialiasing){u32 v=SlotU32(call,1);if(v>1)return 0;CGContextSetAllowsAntialiasing(c,v!=0);}else CGContextSetAlpha(c,SlotCGFloat(call,1));
            SyncBitmapBacking(c,FindBitmapBacking(c)); return 1;
        }
        case LC32CoreGraphicsOpContextFlush: {
            if(!RequireCoreGraphicsSlots(call,1))return 0; CGContextRef c=SlotHostObject<CGContextRef>(call,0);if(!c)return 0;
            CGContextFlush(c);SyncBitmapBacking(c,FindBitmapBacking(c));return 1;
        }
'''
 anchor='    }\n    return 0;\n}\n\n__END_DECLS'
 if anchor not in x: raise SystemExit('host switch anchor missing')
 x=x.replace(anchor,cases+'    }\n    return 0;\n}\n\n__END_DECLS',1)
 host.write_text(x)
print('CoreGraphics: added 16 typed corpus dispatcher exports')
