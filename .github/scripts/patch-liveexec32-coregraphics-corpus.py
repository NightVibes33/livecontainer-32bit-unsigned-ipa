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


# second typed context batch
h=header.read_text()
if 'LC32CoreGraphicsOpContextAddCurveToPoint = 105' not in h:
 anchor='    LC32CoreGraphicsOpContextFlush = 104,\n'
 if anchor not in h: raise SystemExit('second opcode anchor missing')
 h=h.replace(anchor,anchor+r'''    LC32CoreGraphicsOpContextAddCurveToPoint = 105,
    LC32CoreGraphicsOpContextAddQuadCurveToPoint = 106,
    LC32CoreGraphicsOpContextBeginTransparencyLayer = 107,
    LC32CoreGraphicsOpContextEndTransparencyLayer = 108,
    LC32CoreGraphicsOpContextEOClip = 109,
    LC32CoreGraphicsOpContextEOFillPath = 110,
    LC32CoreGraphicsOpContextEndPage = 111,
    LC32CoreGraphicsOpContextSetFillColorSpace = 112,
    LC32CoreGraphicsOpContextSetFont = 113,
    LC32CoreGraphicsOpContextSetFontSize = 114,
    LC32CoreGraphicsOpContextSetGrayStrokeColor = 115,
    LC32CoreGraphicsOpContextSetLineJoin = 116,
    LC32CoreGraphicsOpContextSetMiterLimit = 117,
    LC32CoreGraphicsOpContextSetRenderingIntent = 118,
    LC32CoreGraphicsOpContextSetShadow = 119,
    LC32CoreGraphicsOpContextSetTextDrawingMode = 120,
    LC32CoreGraphicsOpContextSetTextMatrix = 121,
''')
 header.write_text(h)

g=guest.read_text()
if 'void CGContextAddCurveToPoint(' not in g:
 g += r'''
void CGContextAddCurveToPoint(CGContextRef c,CGFloat x1,CGFloat y1,CGFloat x2,CGFloat y2,CGFloat x,CGFloat y) { if(c)(void)LC32_CG_CALL(LC32CoreGraphicsOpContextAddCurveToPoint,LC32_CG_HOST(c),LC32_CG_F32(x1),LC32_CG_F32(y1),LC32_CG_F32(x2),LC32_CG_F32(y2),LC32_CG_F32(x),LC32_CG_F32(y)); }
void CGContextAddQuadCurveToPoint(CGContextRef c,CGFloat cx,CGFloat cy,CGFloat x,CGFloat y) { if(c)(void)LC32_CG_CALL(LC32CoreGraphicsOpContextAddQuadCurveToPoint,LC32_CG_HOST(c),LC32_CG_F32(cx),LC32_CG_F32(cy),LC32_CG_F32(x),LC32_CG_F32(y)); }
void CGContextBeginTransparencyLayer(CGContextRef c,CFDictionaryRef options) { if(c)(void)LC32_CG_CALL(LC32CoreGraphicsOpContextBeginTransparencyLayer,LC32_CG_HOST(c),LC32_CG_HOST(options)); }
void CGContextEndTransparencyLayer(CGContextRef c) { if(c)(void)LC32_CG_CALL(LC32CoreGraphicsOpContextEndTransparencyLayer,LC32_CG_HOST(c)); }
void CGContextEOClip(CGContextRef c) { if(c)(void)LC32_CG_CALL(LC32CoreGraphicsOpContextEOClip,LC32_CG_HOST(c)); }
void CGContextEOFillPath(CGContextRef c) { if(c)(void)LC32_CG_CALL(LC32CoreGraphicsOpContextEOFillPath,LC32_CG_HOST(c)); }
void CGContextEndPage(CGContextRef c) { if(c)(void)LC32_CG_CALL(LC32CoreGraphicsOpContextEndPage,LC32_CG_HOST(c)); }
void CGContextSetFillColorSpace(CGContextRef c,CGColorSpaceRef v) { if(c&&v)(void)LC32_CG_CALL(LC32CoreGraphicsOpContextSetFillColorSpace,LC32_CG_HOST(c),LC32_CG_HOST(v)); }
void CGContextSetFont(CGContextRef c,CGFontRef v) { if(c&&v)(void)LC32_CG_CALL(LC32CoreGraphicsOpContextSetFont,LC32_CG_HOST(c),LC32_CG_HOST(v)); }
void CGContextSetFontSize(CGContextRef c,CGFloat v) { if(c)(void)LC32_CG_CALL(LC32CoreGraphicsOpContextSetFontSize,LC32_CG_HOST(c),LC32_CG_F32(v)); }
void CGContextSetGrayStrokeColor(CGContextRef c,CGFloat gray,CGFloat alpha) { if(c)(void)LC32_CG_CALL(LC32CoreGraphicsOpContextSetGrayStrokeColor,LC32_CG_HOST(c),LC32_CG_F32(gray),LC32_CG_F32(alpha)); }
void CGContextSetLineJoin(CGContextRef c,CGLineJoin v) { if(c)(void)LC32_CG_CALL(LC32CoreGraphicsOpContextSetLineJoin,LC32_CG_HOST(c),LC32_CG_U32(v)); }
void CGContextSetMiterLimit(CGContextRef c,CGFloat v) { if(c)(void)LC32_CG_CALL(LC32CoreGraphicsOpContextSetMiterLimit,LC32_CG_HOST(c),LC32_CG_F32(v)); }
void CGContextSetRenderingIntent(CGContextRef c,CGColorRenderingIntent v) { if(c)(void)LC32_CG_CALL(LC32CoreGraphicsOpContextSetRenderingIntent,LC32_CG_HOST(c),LC32_CG_U32(v)); }
void CGContextSetShadow(CGContextRef c,CGSize o,CGFloat blur) { if(c)(void)LC32_CG_CALL(LC32CoreGraphicsOpContextSetShadow,LC32_CG_HOST(c),LC32_CG_F32(o.width),LC32_CG_F32(o.height),LC32_CG_F32(blur)); }
void CGContextSetTextDrawingMode(CGContextRef c,CGTextDrawingMode v) { if(c)(void)LC32_CG_CALL(LC32CoreGraphicsOpContextSetTextDrawingMode,LC32_CG_HOST(c),LC32_CG_U32(v)); }
void CGContextSetTextMatrix(CGContextRef c,CGAffineTransform t) { if(c)(void)LC32_CG_CALL(LC32CoreGraphicsOpContextSetTextMatrix,LC32_CG_HOST(c),LC32_CG_F32(t.a),LC32_CG_F32(t.b),LC32_CG_F32(t.c),LC32_CG_F32(t.d),LC32_CG_F32(t.tx),LC32_CG_F32(t.ty)); }
'''
 guest.write_text(g)

x=host.read_text()
if 'case LC32CoreGraphicsOpContextAddCurveToPoint:' not in x:
 cases=r'''
        case LC32CoreGraphicsOpContextAddCurveToPoint: {
            if(!RequireCoreGraphicsSlots(call,7))return 0; CGContextRef c=SlotHostObject<CGContextRef>(call,0);if(!c)return 0;
            CGContextAddCurveToPoint(c,SlotCGFloat(call,1),SlotCGFloat(call,2),SlotCGFloat(call,3),SlotCGFloat(call,4),SlotCGFloat(call,5),SlotCGFloat(call,6));return 1;
        }
        case LC32CoreGraphicsOpContextAddQuadCurveToPoint: {
            if(!RequireCoreGraphicsSlots(call,5))return 0; CGContextRef c=SlotHostObject<CGContextRef>(call,0);if(!c)return 0;
            CGContextAddQuadCurveToPoint(c,SlotCGFloat(call,1),SlotCGFloat(call,2),SlotCGFloat(call,3),SlotCGFloat(call,4));return 1;
        }
        case LC32CoreGraphicsOpContextBeginTransparencyLayer: {
            if(!RequireCoreGraphicsSlots(call,2))return 0; CGContextRef c=SlotHostObject<CGContextRef>(call,0);if(!c)return 0;
            CGContextBeginTransparencyLayer(c,SlotHostObject<CFDictionaryRef>(call,1));return 1;
        }
        case LC32CoreGraphicsOpContextEndTransparencyLayer:
        case LC32CoreGraphicsOpContextEOClip:
        case LC32CoreGraphicsOpContextEOFillPath:
        case LC32CoreGraphicsOpContextEndPage: {
            if(!RequireCoreGraphicsSlots(call,1))return 0; CGContextRef c=SlotHostObject<CGContextRef>(call,0);if(!c)return 0;
            if(opcode==LC32CoreGraphicsOpContextEndTransparencyLayer)CGContextEndTransparencyLayer(c);
            else if(opcode==LC32CoreGraphicsOpContextEOClip)CGContextEOClip(c);
            else if(opcode==LC32CoreGraphicsOpContextEOFillPath)CGContextEOFillPath(c);
            else CGContextEndPage(c); SyncBitmapBacking(c,FindBitmapBacking(c));return 1;
        }
        case LC32CoreGraphicsOpContextSetFillColorSpace:
        case LC32CoreGraphicsOpContextSetFont: {
            if(!RequireCoreGraphicsSlots(call,2))return 0; CGContextRef c=SlotHostObject<CGContextRef>(call,0);if(!c)return 0;
            if(opcode==LC32CoreGraphicsOpContextSetFillColorSpace){CGColorSpaceRef v=SlotHostObject<CGColorSpaceRef>(call,1);if(!v)return 0;CGContextSetFillColorSpace(c,v);}else{CGFontRef v=SlotHostObject<CGFontRef>(call,1);if(!v)return 0;CGContextSetFont(c,v);}return 1;
        }
        case LC32CoreGraphicsOpContextSetFontSize:
        case LC32CoreGraphicsOpContextSetMiterLimit: {
            if(!RequireCoreGraphicsSlots(call,2))return 0; CGContextRef c=SlotHostObject<CGContextRef>(call,0);if(!c)return 0;
            if(opcode==LC32CoreGraphicsOpContextSetFontSize)CGContextSetFontSize(c,SlotCGFloat(call,1));else CGContextSetMiterLimit(c,SlotCGFloat(call,1));return 1;
        }
        case LC32CoreGraphicsOpContextSetGrayStrokeColor: {
            if(!RequireCoreGraphicsSlots(call,3))return 0;CGContextRef c=SlotHostObject<CGContextRef>(call,0);if(!c)return 0;
            CGContextSetGrayStrokeColor(c,SlotCGFloat(call,1),SlotCGFloat(call,2));return 1;
        }
        case LC32CoreGraphicsOpContextSetLineJoin:
        case LC32CoreGraphicsOpContextSetRenderingIntent:
        case LC32CoreGraphicsOpContextSetTextDrawingMode: {
            if(!RequireCoreGraphicsSlots(call,2))return 0;CGContextRef c=SlotHostObject<CGContextRef>(call,0);if(!c)return 0;u32 v=SlotU32(call,1);
            if(opcode==LC32CoreGraphicsOpContextSetLineJoin)CGContextSetLineJoin(c,(CGLineJoin)v);
            else if(opcode==LC32CoreGraphicsOpContextSetRenderingIntent)CGContextSetRenderingIntent(c,(CGColorRenderingIntent)v);
            else CGContextSetTextDrawingMode(c,(CGTextDrawingMode)v);return 1;
        }
        case LC32CoreGraphicsOpContextSetShadow: {
            if(!RequireCoreGraphicsSlots(call,4))return 0;CGContextRef c=SlotHostObject<CGContextRef>(call,0);if(!c)return 0;
            CGContextSetShadow(c,CGSizeMake(SlotCGFloat(call,1),SlotCGFloat(call,2)),SlotCGFloat(call,3));return 1;
        }
        case LC32CoreGraphicsOpContextSetTextMatrix: {
            if(!RequireCoreGraphicsSlots(call,7))return 0;CGContextRef c=SlotHostObject<CGContextRef>(call,0);if(!c)return 0;
            CGContextSetTextMatrix(c,CGAffineTransformMake(SlotCGFloat(call,1),SlotCGFloat(call,2),SlotCGFloat(call,3),SlotCGFloat(call,4),SlotCGFloat(call,5),SlotCGFloat(call,6)));return 1;
        }
'''
 anchor='    }\n    return 0;\n}\n\n__END_DECLS'
 if anchor not in x:raise SystemExit('second host switch anchor missing')
 x=x.replace(anchor,cases+'    }\n    return 0;\n}\n\n__END_DECLS',1)
 host.write_text(x)
print('CoreGraphics: added 17 typed context state exports')
