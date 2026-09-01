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


# third typed geometry query batch
h=header.read_text()
if 'LC32CoreGraphicsOpContextConvertPointToDeviceSpace = 122' not in h:
 anchor='    LC32CoreGraphicsOpContextSetTextMatrix = 121,\n'
 if anchor not in h:raise SystemExit('third opcode anchor missing')
 h=h.replace(anchor,anchor+r'''    LC32CoreGraphicsOpContextConvertPointToDeviceSpace = 122,
    LC32CoreGraphicsOpContextConvertPointToUserSpace = 123,
    LC32CoreGraphicsOpContextConvertRectToDeviceSpace = 124,
    LC32CoreGraphicsOpContextConvertRectToUserSpace = 125,
    LC32CoreGraphicsOpContextGetCTM = 126,
    LC32CoreGraphicsOpContextGetPathBoundingBox = 127,
    LC32CoreGraphicsOpContextGetTextPosition = 128,
    LC32CoreGraphicsOpContextIsPathEmpty = 129,
    LC32CoreGraphicsOpContextReplacePathWithStrokedPath = 130,
    LC32CoreGraphicsOpPathGetBoundingBox = 131,
    LC32CoreGraphicsOpPathGetPathBoundingBox = 132,
    LC32CoreGraphicsOpPathIsEmpty = 133,
    LC32CoreGraphicsOpLayerGetSize = 134,
''')
 header.write_text(h)

g=guest.read_text()
if 'CGPoint CGContextConvertPointToDeviceSpace(' not in g:
 g += r'''
CGPoint CGContextConvertPointToDeviceSpace(CGContextRef c,CGPoint p) { CGPoint r=CGPointZero;if(c)(void)LC32_CG_CALL(LC32CoreGraphicsOpContextConvertPointToDeviceSpace,LC32_CG_HOST(c),LC32_CG_F32(p.x),LC32_CG_F32(p.y),LC32_CG_U32((uintptr_t)&r));return r; }
CGPoint CGContextConvertPointToUserSpace(CGContextRef c,CGPoint p) { CGPoint r=CGPointZero;if(c)(void)LC32_CG_CALL(LC32CoreGraphicsOpContextConvertPointToUserSpace,LC32_CG_HOST(c),LC32_CG_F32(p.x),LC32_CG_F32(p.y),LC32_CG_U32((uintptr_t)&r));return r; }
CGRect CGContextConvertRectToDeviceSpace(CGContextRef c,CGRect v) { CGRect r=CGRectZero;if(c)(void)LC32_CG_CALL(LC32CoreGraphicsOpContextConvertRectToDeviceSpace,LC32_CG_HOST(c),LC32_CG_F32(v.origin.x),LC32_CG_F32(v.origin.y),LC32_CG_F32(v.size.width),LC32_CG_F32(v.size.height),LC32_CG_U32((uintptr_t)&r));return r; }
CGRect CGContextConvertRectToUserSpace(CGContextRef c,CGRect v) { CGRect r=CGRectZero;if(c)(void)LC32_CG_CALL(LC32CoreGraphicsOpContextConvertRectToUserSpace,LC32_CG_HOST(c),LC32_CG_F32(v.origin.x),LC32_CG_F32(v.origin.y),LC32_CG_F32(v.size.width),LC32_CG_F32(v.size.height),LC32_CG_U32((uintptr_t)&r));return r; }
CGAffineTransform CGContextGetCTM(CGContextRef c) { CGAffineTransform r=CGAffineTransformIdentity;if(c)(void)LC32_CG_CALL(LC32CoreGraphicsOpContextGetCTM,LC32_CG_HOST(c),LC32_CG_U32((uintptr_t)&r));return r; }
CGRect CGContextGetPathBoundingBox(CGContextRef c) { CGRect r=CGRectNull;if(c)(void)LC32_CG_CALL(LC32CoreGraphicsOpContextGetPathBoundingBox,LC32_CG_HOST(c),LC32_CG_U32((uintptr_t)&r));return r; }
CGPoint CGContextGetTextPosition(CGContextRef c) { CGPoint r=CGPointZero;if(c)(void)LC32_CG_CALL(LC32CoreGraphicsOpContextGetTextPosition,LC32_CG_HOST(c),LC32_CG_U32((uintptr_t)&r));return r; }
bool CGContextIsPathEmpty(CGContextRef c) { return !c||LC32_CG_CALL(LC32CoreGraphicsOpContextIsPathEmpty,LC32_CG_HOST(c)); }
void CGContextReplacePathWithStrokedPath(CGContextRef c) { if(c)(void)LC32_CG_CALL(LC32CoreGraphicsOpContextReplacePathWithStrokedPath,LC32_CG_HOST(c)); }
CGRect CGPathGetBoundingBox(CGPathRef p) { CGRect r=CGRectNull;if(p)(void)LC32_CG_CALL(LC32CoreGraphicsOpPathGetBoundingBox,LC32_CG_HOST(p),LC32_CG_U32((uintptr_t)&r));return r; }
CGRect CGPathGetPathBoundingBox(CGPathRef p) { CGRect r=CGRectNull;if(p)(void)LC32_CG_CALL(LC32CoreGraphicsOpPathGetPathBoundingBox,LC32_CG_HOST(p),LC32_CG_U32((uintptr_t)&r));return r; }
bool CGPathIsEmpty(CGPathRef p) { return !p||LC32_CG_CALL(LC32CoreGraphicsOpPathIsEmpty,LC32_CG_HOST(p)); }
CGSize CGLayerGetSize(CGLayerRef l) { CGSize r=CGSizeZero;if(l)(void)LC32_CG_CALL(LC32CoreGraphicsOpLayerGetSize,LC32_CG_HOST(l),LC32_CG_U32((uintptr_t)&r));return r; }
'''
 guest.write_text(g)

x=host.read_text()
if 'bool WriteGuestCoreGraphicsFloats(' not in x:
 anchor='} // namespace\n\n__BEGIN_DECLS'
 helper=r'''bool WriteGuestCoreGraphicsFloats(u32 address,const CGFloat *values,size_t count) {
    if(!address||!values||count>16||static_cast<uint64_t>(address)+count*sizeof(float)>static_cast<uint64_t>(UINT32_MAX)+1)return false;
    float output[16];for(size_t i=0;i<count;++i)output[i]=static_cast<float>(values[i]);
    return Dynarmic_mem_1write(address,count*sizeof(float),reinterpret_cast<char *>(output))==0;
}

'''
 if anchor not in x:raise SystemExit('namespace anchor missing')
 x=x.replace(anchor,helper+anchor,1)
if 'case LC32CoreGraphicsOpContextConvertPointToDeviceSpace:' not in x:
 cases=r'''
        case LC32CoreGraphicsOpContextConvertPointToDeviceSpace:
        case LC32CoreGraphicsOpContextConvertPointToUserSpace: {
            if(!RequireCoreGraphicsSlots(call,4))return 0;CGContextRef c=SlotHostObject<CGContextRef>(call,0);if(!c)return 0;
            CGPoint p=CGPointMake(SlotCGFloat(call,1),SlotCGFloat(call,2));p=opcode==LC32CoreGraphicsOpContextConvertPointToDeviceSpace?CGContextConvertPointToDeviceSpace(c,p):CGContextConvertPointToUserSpace(c,p);
            CGFloat v[2]={p.x,p.y};return WriteGuestCoreGraphicsFloats(SlotU32(call,3),v,2);
        }
        case LC32CoreGraphicsOpContextConvertRectToDeviceSpace:
        case LC32CoreGraphicsOpContextConvertRectToUserSpace: {
            if(!RequireCoreGraphicsSlots(call,6))return 0;CGContextRef c=SlotHostObject<CGContextRef>(call,0);if(!c)return 0;
            CGRect r=SlotRect(call,1);r=opcode==LC32CoreGraphicsOpContextConvertRectToDeviceSpace?CGContextConvertRectToDeviceSpace(c,r):CGContextConvertRectToUserSpace(c,r);
            CGFloat v[4]={r.origin.x,r.origin.y,r.size.width,r.size.height};return WriteGuestCoreGraphicsFloats(SlotU32(call,5),v,4);
        }
        case LC32CoreGraphicsOpContextGetCTM: {
            if(!RequireCoreGraphicsSlots(call,2))return 0;CGContextRef c=SlotHostObject<CGContextRef>(call,0);if(!c)return 0;CGAffineTransform t=CGContextGetCTM(c);
            CGFloat v[6]={t.a,t.b,t.c,t.d,t.tx,t.ty};return WriteGuestCoreGraphicsFloats(SlotU32(call,1),v,6);
        }
        case LC32CoreGraphicsOpContextGetPathBoundingBox:
        case LC32CoreGraphicsOpPathGetBoundingBox:
        case LC32CoreGraphicsOpPathGetPathBoundingBox: {
            if(!RequireCoreGraphicsSlots(call,2))return 0;CGRect r;
            if(opcode==LC32CoreGraphicsOpContextGetPathBoundingBox){CGContextRef c=SlotHostObject<CGContextRef>(call,0);if(!c)return 0;r=CGContextGetPathBoundingBox(c);}else{CGPathRef p=SlotHostObject<CGPathRef>(call,0);if(!p)return 0;r=opcode==LC32CoreGraphicsOpPathGetBoundingBox?CGPathGetBoundingBox(p):CGPathGetPathBoundingBox(p);}
            CGFloat v[4]={r.origin.x,r.origin.y,r.size.width,r.size.height};return WriteGuestCoreGraphicsFloats(SlotU32(call,1),v,4);
        }
        case LC32CoreGraphicsOpContextGetTextPosition: {
            if(!RequireCoreGraphicsSlots(call,2))return 0;CGContextRef c=SlotHostObject<CGContextRef>(call,0);if(!c)return 0;CGPoint p=CGContextGetTextPosition(c);CGFloat v[2]={p.x,p.y};return WriteGuestCoreGraphicsFloats(SlotU32(call,1),v,2);
        }
        case LC32CoreGraphicsOpContextIsPathEmpty:
        case LC32CoreGraphicsOpPathIsEmpty: {
            if(!RequireCoreGraphicsSlots(call,1))return 0;if(opcode==LC32CoreGraphicsOpContextIsPathEmpty){CGContextRef c=SlotHostObject<CGContextRef>(call,0);return !c||CGContextIsPathEmpty(c);}CGPathRef p=SlotHostObject<CGPathRef>(call,0);return !p||CGPathIsEmpty(p);
        }
        case LC32CoreGraphicsOpContextReplacePathWithStrokedPath: {
            if(!RequireCoreGraphicsSlots(call,1))return 0;CGContextRef c=SlotHostObject<CGContextRef>(call,0);if(!c)return 0;CGContextReplacePathWithStrokedPath(c);return 1;
        }
        case LC32CoreGraphicsOpLayerGetSize: {
            if(!RequireCoreGraphicsSlots(call,2))return 0;CGLayerRef l=SlotHostObject<CGLayerRef>(call,0);if(!l)return 0;CGSize z=CGLayerGetSize(l);CGFloat v[2]={z.width,z.height};return WriteGuestCoreGraphicsFloats(SlotU32(call,1),v,2);
        }
'''
 anchor='    }\n    return 0;\n}\n\n__END_DECLS'
 if anchor not in x:raise SystemExit('third switch anchor missing')
 x=x.replace(anchor,cases+'    }\n    return 0;\n}\n\n__END_DECLS',1)
 host.write_text(x)
print('CoreGraphics: added 13 typed geometry query exports')


# fourth typed path geometry batch
h=header.read_text()
if 'LC32CoreGraphicsOpPathAddArc = 135' not in h:
 anchor='    LC32CoreGraphicsOpLayerGetSize = 134,\n'
 if anchor not in h:raise SystemExit('fourth opcode anchor missing')
 h=h.replace(anchor,anchor+r'''    LC32CoreGraphicsOpPathAddArc = 135,
    LC32CoreGraphicsOpPathAddRelativeArc = 136,
    LC32CoreGraphicsOpPathAddQuadCurveToPoint = 137,
    LC32CoreGraphicsOpPathAddPath = 138,
    LC32CoreGraphicsOpPathAddRoundedRect = 139,
    LC32CoreGraphicsOpPathCreateWithEllipseInRect = 140,
    LC32CoreGraphicsOpPathCreateWithRoundedRect = 141,
    LC32CoreGraphicsOpPathCreateCopyByTransformingPath = 142,
''')
 header.write_text(h)

def ts(t):
 return ','.join([f'LC32_CG_U32({t} != NULL)',*[f'{t} ? LC32_CG_F32({t}->{n}) : 0' for n in ('a','b','c','d','tx','ty')]])
g=guest.read_text()
if 'void CGPathAddArc(CGMutablePathRef' not in g:
 block=r'''
void CGPathAddArc(CGMutablePathRef p,const CGAffineTransform *t,CGFloat x,CGFloat y,CGFloat radius,CGFloat start,CGFloat end,bool clockwise) { if(p)(void)LC32_CG_CALL(LC32CoreGraphicsOpPathAddArc,LC32_CG_HOST(p),TRANSFORM,LC32_CG_F32(x),LC32_CG_F32(y),LC32_CG_F32(radius),LC32_CG_F32(start),LC32_CG_F32(end),LC32_CG_U32(clockwise)); }
void CGPathAddRelativeArc(CGMutablePathRef p,const CGAffineTransform *t,CGFloat x,CGFloat y,CGFloat radius,CGFloat start,CGFloat delta) { if(p)(void)LC32_CG_CALL(LC32CoreGraphicsOpPathAddRelativeArc,LC32_CG_HOST(p),TRANSFORM,LC32_CG_F32(x),LC32_CG_F32(y),LC32_CG_F32(radius),LC32_CG_F32(start),LC32_CG_F32(delta)); }
void CGPathAddQuadCurveToPoint(CGMutablePathRef p,const CGAffineTransform *t,CGFloat cx,CGFloat cy,CGFloat x,CGFloat y) { if(p)(void)LC32_CG_CALL(LC32CoreGraphicsOpPathAddQuadCurveToPoint,LC32_CG_HOST(p),TRANSFORM,LC32_CG_F32(cx),LC32_CG_F32(cy),LC32_CG_F32(x),LC32_CG_F32(y)); }
void CGPathAddPath(CGMutablePathRef p,const CGAffineTransform *t,CGPathRef other) { if(p&&other)(void)LC32_CG_CALL(LC32CoreGraphicsOpPathAddPath,LC32_CG_HOST(p),TRANSFORM,LC32_CG_HOST(other)); }
void CGPathAddRoundedRect(CGMutablePathRef p,const CGAffineTransform *t,CGRect r,CGFloat cw,CGFloat ch) { if(p)(void)LC32_CG_CALL(LC32CoreGraphicsOpPathAddRoundedRect,LC32_CG_HOST(p),TRANSFORM,LC32_CG_F32(r.origin.x),LC32_CG_F32(r.origin.y),LC32_CG_F32(r.size.width),LC32_CG_F32(r.size.height),LC32_CG_F32(cw),LC32_CG_F32(ch)); }
CGPathRef CGPathCreateWithEllipseInRect(CGRect r,const CGAffineTransform *t) { return (CGPathRef)LC32_CG_CALL(LC32CoreGraphicsOpPathCreateWithEllipseInRect,TRANSFORM,LC32_CG_F32(r.origin.x),LC32_CG_F32(r.origin.y),LC32_CG_F32(r.size.width),LC32_CG_F32(r.size.height)); }
CGPathRef CGPathCreateWithRoundedRect(CGRect r,CGFloat cw,CGFloat ch,const CGAffineTransform *t) { return (CGPathRef)LC32_CG_CALL(LC32CoreGraphicsOpPathCreateWithRoundedRect,TRANSFORM,LC32_CG_F32(r.origin.x),LC32_CG_F32(r.origin.y),LC32_CG_F32(r.size.width),LC32_CG_F32(r.size.height),LC32_CG_F32(cw),LC32_CG_F32(ch)); }
CGPathRef CGPathCreateCopyByTransformingPath(CGPathRef p,const CGAffineTransform *t) { return p?(CGPathRef)LC32_CG_CALL(LC32CoreGraphicsOpPathCreateCopyByTransformingPath,LC32_CG_HOST(p),TRANSFORM):NULL; }
'''.replace('TRANSFORM',ts('t'))
 g += block;guest.write_text(g)

x=host.read_text()
if 'case LC32CoreGraphicsOpPathAddArc:' not in x:
 cases=r'''
        case LC32CoreGraphicsOpPathAddArc:
        case LC32CoreGraphicsOpPathAddRelativeArc: {
            const bool relative=opcode==LC32CoreGraphicsOpPathAddRelativeArc; if(!RequireCoreGraphicsSlots(call,relative?13:14))return 0;
            CGMutablePathRef p=SlotHostObject<CGMutablePathRef>(call,0);if(!p)return 0;CGAffineTransform storage;const CGAffineTransform *t;if(!SlotOptionalTransform(call,1,2,storage,t))return 0;
            if(relative)CGPathAddRelativeArc(p,t,SlotCGFloat(call,8),SlotCGFloat(call,9),SlotCGFloat(call,10),SlotCGFloat(call,11),SlotCGFloat(call,12));
            else{u32 clockwise=SlotU32(call,13);if(clockwise>1)return 0;CGPathAddArc(p,t,SlotCGFloat(call,8),SlotCGFloat(call,9),SlotCGFloat(call,10),SlotCGFloat(call,11),SlotCGFloat(call,12),clockwise!=0);}return 1;
        }
        case LC32CoreGraphicsOpPathAddQuadCurveToPoint: {
            if(!RequireCoreGraphicsSlots(call,12))return 0;CGMutablePathRef p=SlotHostObject<CGMutablePathRef>(call,0);if(!p)return 0;CGAffineTransform storage;const CGAffineTransform *t;if(!SlotOptionalTransform(call,1,2,storage,t))return 0;
            CGPathAddQuadCurveToPoint(p,t,SlotCGFloat(call,8),SlotCGFloat(call,9),SlotCGFloat(call,10),SlotCGFloat(call,11));return 1;
        }
        case LC32CoreGraphicsOpPathAddPath: {
            if(!RequireCoreGraphicsSlots(call,9))return 0;CGMutablePathRef p=SlotHostObject<CGMutablePathRef>(call,0);CGPathRef other=SlotHostObject<CGPathRef>(call,8);if(!p||!other)return 0;CGAffineTransform storage;const CGAffineTransform *t;if(!SlotOptionalTransform(call,1,2,storage,t))return 0;CGPathAddPath(p,t,other);return 1;
        }
        case LC32CoreGraphicsOpPathAddRoundedRect: {
            if(!RequireCoreGraphicsSlots(call,14))return 0;CGMutablePathRef p=SlotHostObject<CGMutablePathRef>(call,0);if(!p)return 0;CGAffineTransform storage;const CGAffineTransform *t;if(!SlotOptionalTransform(call,1,2,storage,t))return 0;CGPathAddRoundedRect(p,t,SlotRect(call,8),SlotCGFloat(call,12),SlotCGFloat(call,13));return 1;
        }
        case LC32CoreGraphicsOpPathCreateWithEllipseInRect:
        case LC32CoreGraphicsOpPathCreateWithRoundedRect: {
            const bool rounded=opcode==LC32CoreGraphicsOpPathCreateWithRoundedRect;if(!RequireCoreGraphicsSlots(call,rounded?13:11))return 0;CGAffineTransform storage;const CGAffineTransform *t;if(!SlotOptionalTransform(call,0,1,storage,t))return 0;
            CGRect r=SlotRect(call,7);CGPathRef result=rounded?CGPathCreateWithRoundedRect(r,SlotCGFloat(call,11),SlotCGFloat(call,12),t):CGPathCreateWithEllipseInRect(r,t);return result?LC32GuestObjectForOwnedHostObject(result):0;
        }
        case LC32CoreGraphicsOpPathCreateCopyByTransformingPath: {
            if(!RequireCoreGraphicsSlots(call,8))return 0;CGPathRef p=SlotHostObject<CGPathRef>(call,0);if(!p)return 0;CGAffineTransform storage;const CGAffineTransform *t;if(!SlotOptionalTransform(call,1,2,storage,t))return 0;CGPathRef result=CGPathCreateCopyByTransformingPath(p,t);return result?LC32GuestObjectForOwnedHostObject(result):0;
        }
'''
 anchor='    }\n    return 0;\n}\n\n__END_DECLS'
 if anchor not in x:raise SystemExit('fourth switch anchor missing')
 x=x.replace(anchor,cases+'    }\n    return 0;\n}\n\n__END_DECLS',1);host.write_text(x)
print('CoreGraphics: added 8 typed path geometry exports')


# fifth typed geometry array batch
h=header.read_text()
if 'LC32CoreGraphicsOpContextAddLines = 143' not in h:
 anchor='    LC32CoreGraphicsOpPathCreateCopyByTransformingPath = 142,\n'
 if anchor not in h:raise SystemExit('fifth opcode anchor missing')
 h=h.replace(anchor,anchor+r'''    LC32CoreGraphicsOpContextAddLines = 143,
    LC32CoreGraphicsOpContextAddRects = 144,
    LC32CoreGraphicsOpContextClipToRects = 145,
    LC32CoreGraphicsOpContextFillRects = 146,
    LC32CoreGraphicsOpPathAddLines = 147,
    LC32CoreGraphicsOpPathAddRects = 148,
    LC32CoreGraphicsOpContextSetLineDash = 149,
''');header.write_text(h)

g=guest.read_text()
if 'void CGContextAddLines(CGContextRef' not in g:
 g += r'''
void CGContextAddLines(CGContextRef c,const CGPoint *p,size_t n) { if(c&&p&&n)(void)LC32_CG_CALL(LC32CoreGraphicsOpContextAddLines,LC32_CG_HOST(c),LC32_CG_U32((uintptr_t)p),LC32_CG_U32(n)); }
void CGContextAddRects(CGContextRef c,const CGRect *r,size_t n) { if(c&&r&&n)(void)LC32_CG_CALL(LC32CoreGraphicsOpContextAddRects,LC32_CG_HOST(c),LC32_CG_U32((uintptr_t)r),LC32_CG_U32(n)); }
void CGContextClipToRects(CGContextRef c,const CGRect *r,size_t n) { if(c&&r&&n)(void)LC32_CG_CALL(LC32CoreGraphicsOpContextClipToRects,LC32_CG_HOST(c),LC32_CG_U32((uintptr_t)r),LC32_CG_U32(n)); }
void CGContextFillRects(CGContextRef c,const CGRect *r,size_t n) { if(c&&r&&n)(void)LC32_CG_CALL(LC32CoreGraphicsOpContextFillRects,LC32_CG_HOST(c),LC32_CG_U32((uintptr_t)r),LC32_CG_U32(n)); }
void CGPathAddLines(CGMutablePathRef p,const CGAffineTransform *t,const CGPoint *v,size_t n) { if(p&&v&&n)(void)LC32_CG_CALL(LC32CoreGraphicsOpPathAddLines,LC32_CG_HOST(p),LC32_CG_U32(t!=NULL),t?LC32_CG_F32(t->a):0,t?LC32_CG_F32(t->b):0,t?LC32_CG_F32(t->c):0,t?LC32_CG_F32(t->d):0,t?LC32_CG_F32(t->tx):0,t?LC32_CG_F32(t->ty):0,LC32_CG_U32((uintptr_t)v),LC32_CG_U32(n)); }
void CGPathAddRects(CGMutablePathRef p,const CGAffineTransform *t,const CGRect *v,size_t n) { if(p&&v&&n)(void)LC32_CG_CALL(LC32CoreGraphicsOpPathAddRects,LC32_CG_HOST(p),LC32_CG_U32(t!=NULL),t?LC32_CG_F32(t->a):0,t?LC32_CG_F32(t->b):0,t?LC32_CG_F32(t->c):0,t?LC32_CG_F32(t->d):0,t?LC32_CG_F32(t->tx):0,t?LC32_CG_F32(t->ty):0,LC32_CG_U32((uintptr_t)v),LC32_CG_U32(n)); }
void CGContextSetLineDash(CGContextRef c,CGFloat phase,const CGFloat *lengths,size_t n) { if(c&&(lengths||!n))(void)LC32_CG_CALL(LC32CoreGraphicsOpContextSetLineDash,LC32_CG_HOST(c),LC32_CG_F32(phase),LC32_CG_U32((uintptr_t)lengths),LC32_CG_U32(n)); }
''';guest.write_text(g)

x=host.read_text()
if 'bool ReadGuestCoreGraphicsPoints(' not in x:
 anchor='} // namespace\n\n__BEGIN_DECLS'
 helper=r'''bool ReadGuestCoreGraphicsPoints(u32 address,size_t count,std::vector<CGPoint>& out) {
    if(!address||!count||count>1024*1024||count>SIZE_MAX/(2*sizeof(float))||static_cast<uint64_t>(address)+count*2*sizeof(float)>static_cast<uint64_t>(UINT32_MAX)+1)return false;
    std::vector<float> in(count*2);if(Dynarmic_mem_1read(address,in.size()*sizeof(float),reinterpret_cast<char *>(in.data()))!=0)return false;
    out.resize(count);for(size_t i=0;i<count;++i)out[i]=CGPointMake(in[i*2],in[i*2+1]);return true;
}
bool ReadGuestCoreGraphicsRects(u32 address,size_t count,std::vector<CGRect>& out) {
    if(!address||!count||count>1024*1024||count>SIZE_MAX/(4*sizeof(float))||static_cast<uint64_t>(address)+count*4*sizeof(float)>static_cast<uint64_t>(UINT32_MAX)+1)return false;
    std::vector<float> in(count*4);if(Dynarmic_mem_1read(address,in.size()*sizeof(float),reinterpret_cast<char *>(in.data()))!=0)return false;
    out.resize(count);for(size_t i=0;i<count;++i)out[i]=CGRectMake(in[i*4],in[i*4+1],in[i*4+2],in[i*4+3]);return true;
}

'''
 if anchor not in x:raise SystemExit('fifth namespace anchor missing')
 x=x.replace(anchor,helper+anchor,1)
if 'case LC32CoreGraphicsOpContextAddLines:' not in x:
 cases=r'''
        case LC32CoreGraphicsOpContextAddLines: {
            if(!RequireCoreGraphicsSlots(call,3))return 0;CGContextRef c=SlotHostObject<CGContextRef>(call,0);std::vector<CGPoint> v;if(!c||!ReadGuestCoreGraphicsPoints(SlotU32(call,1),SlotU32(call,2),v))return 0;CGContextAddLines(c,v.data(),v.size());return 1;
        }
        case LC32CoreGraphicsOpContextAddRects:
        case LC32CoreGraphicsOpContextClipToRects:
        case LC32CoreGraphicsOpContextFillRects: {
            if(!RequireCoreGraphicsSlots(call,3))return 0;CGContextRef c=SlotHostObject<CGContextRef>(call,0);std::vector<CGRect> v;if(!c||!ReadGuestCoreGraphicsRects(SlotU32(call,1),SlotU32(call,2),v))return 0;
            if(opcode==LC32CoreGraphicsOpContextAddRects)CGContextAddRects(c,v.data(),v.size());else if(opcode==LC32CoreGraphicsOpContextClipToRects)CGContextClipToRects(c,v.data(),v.size());else{CGContextFillRects(c,v.data(),v.size());SyncBitmapBacking(c,FindBitmapBacking(c));}return 1;
        }
        case LC32CoreGraphicsOpPathAddLines:
        case LC32CoreGraphicsOpPathAddRects: {
            if(!RequireCoreGraphicsSlots(call,10))return 0;CGMutablePathRef p=SlotHostObject<CGMutablePathRef>(call,0);if(!p)return 0;CGAffineTransform storage;const CGAffineTransform *t;if(!SlotOptionalTransform(call,1,2,storage,t))return 0;
            if(opcode==LC32CoreGraphicsOpPathAddLines){std::vector<CGPoint> v;if(!ReadGuestCoreGraphicsPoints(SlotU32(call,8),SlotU32(call,9),v))return 0;CGPathAddLines(p,t,v.data(),v.size());}else{std::vector<CGRect> v;if(!ReadGuestCoreGraphicsRects(SlotU32(call,8),SlotU32(call,9),v))return 0;CGPathAddRects(p,t,v.data(),v.size());}return 1;
        }
        case LC32CoreGraphicsOpContextSetLineDash: {
            if(!RequireCoreGraphicsSlots(call,4))return 0;CGContextRef c=SlotHostObject<CGContextRef>(call,0);if(!c)return 0;size_t n=SlotU32(call,3);std::vector<CGFloat> values;const CGFloat *ptr=nullptr;if(n&&!ReadGuestCGFloatArray(SlotU32(call,2),n,false,values,ptr))return 0;CGContextSetLineDash(c,SlotCGFloat(call,1),ptr,n);return 1;
        }
'''
 anchor='    }\n    return 0;\n}\n\n__END_DECLS'
 if anchor not in x:raise SystemExit('fifth switch anchor missing')
 x=x.replace(anchor,cases+'    }\n    return 0;\n}\n\n__END_DECLS',1);host.write_text(x)
print('CoreGraphics: added 7 typed geometry array exports')


# sixth typed provider and font batch
h=header.read_text()
if 'LC32CoreGraphicsOpDataConsumerCreateWithCFData = 150' not in h:
 anchor='    LC32CoreGraphicsOpContextSetLineDash = 149,\n'
 if anchor not in h:raise SystemExit('sixth opcode anchor missing')
 h=h.replace(anchor,anchor+r'''    LC32CoreGraphicsOpDataConsumerCreateWithCFData = 150,
    LC32CoreGraphicsOpDataProviderCopyData = 151,
    LC32CoreGraphicsOpDataProviderCreateWithCFData = 152,
    LC32CoreGraphicsOpFontCopyPostScriptName = 153,
    LC32CoreGraphicsOpFontCopyTableForTag = 154,
    LC32CoreGraphicsOpFontCreateWithDataProvider = 155,
    LC32CoreGraphicsOpFontCreateWithFontName = 156,
    LC32CoreGraphicsOpFontGetAscent = 157,
    LC32CoreGraphicsOpFontGetCapHeight = 158,
    LC32CoreGraphicsOpFontGetDescent = 159,
    LC32CoreGraphicsOpFontGetUnitsPerEm = 160,
    LC32CoreGraphicsOpFontGetXHeight = 161,
    LC32CoreGraphicsOpLayerGetContext = 162,
''');header.write_text(h)

g=guest.read_text()
if 'CGDataConsumerRef CGDataConsumerCreateWithCFData(' not in g:
 g += r'''
CGDataConsumerRef CGDataConsumerCreateWithCFData(CFMutableDataRef d) { return d?(CGDataConsumerRef)LC32_CG_CALL(LC32CoreGraphicsOpDataConsumerCreateWithCFData,LC32_CG_HOST(d)):NULL; }
CFDataRef CGDataProviderCopyData(CGDataProviderRef p) { return p?(CFDataRef)LC32_CG_CALL(LC32CoreGraphicsOpDataProviderCopyData,LC32_CG_HOST(p)):NULL; }
CGDataProviderRef CGDataProviderCreateWithCFData(CFDataRef d) { return d?(CGDataProviderRef)LC32_CG_CALL(LC32CoreGraphicsOpDataProviderCreateWithCFData,LC32_CG_HOST(d)):NULL; }
CFStringRef CGFontCopyPostScriptName(CGFontRef f) { return f?(CFStringRef)LC32_CG_CALL(LC32CoreGraphicsOpFontCopyPostScriptName,LC32_CG_HOST(f)):NULL; }
CFDataRef CGFontCopyTableForTag(CGFontRef f,uint32_t tag) { return f?(CFDataRef)LC32_CG_CALL(LC32CoreGraphicsOpFontCopyTableForTag,LC32_CG_HOST(f),LC32_CG_U32(tag)):NULL; }
CGFontRef CGFontCreateWithDataProvider(CGDataProviderRef p) { return p?(CGFontRef)LC32_CG_CALL(LC32CoreGraphicsOpFontCreateWithDataProvider,LC32_CG_HOST(p)):NULL; }
CGFontRef CGFontCreateWithFontName(CFStringRef n) { return n?(CGFontRef)LC32_CG_CALL(LC32CoreGraphicsOpFontCreateWithFontName,LC32_CG_HOST(n)):NULL; }
int CGFontGetAscent(CGFontRef f) { return f?(int32_t)LC32_CG_CALL(LC32CoreGraphicsOpFontGetAscent,LC32_CG_HOST(f)):0; }
int CGFontGetCapHeight(CGFontRef f) { return f?(int32_t)LC32_CG_CALL(LC32CoreGraphicsOpFontGetCapHeight,LC32_CG_HOST(f)):0; }
int CGFontGetDescent(CGFontRef f) { return f?(int32_t)LC32_CG_CALL(LC32CoreGraphicsOpFontGetDescent,LC32_CG_HOST(f)):0; }
int CGFontGetUnitsPerEm(CGFontRef f) { return f?(int32_t)LC32_CG_CALL(LC32CoreGraphicsOpFontGetUnitsPerEm,LC32_CG_HOST(f)):0; }
int CGFontGetXHeight(CGFontRef f) { return f?(int32_t)LC32_CG_CALL(LC32CoreGraphicsOpFontGetXHeight,LC32_CG_HOST(f)):0; }
CGContextRef CGLayerGetContext(CGLayerRef l) { return l?(CGContextRef)LC32_CG_CALL(LC32CoreGraphicsOpLayerGetContext,LC32_CG_HOST(l)):NULL; }
''';guest.write_text(g)

x=host.read_text()
if 'case LC32CoreGraphicsOpDataConsumerCreateWithCFData:' not in x:
 cases=r'''
        case LC32CoreGraphicsOpDataConsumerCreateWithCFData: {
            if(!RequireCoreGraphicsSlots(call,1))return 0;CFMutableDataRef d=SlotHostObject<CFMutableDataRef>(call,0);CGDataConsumerRef r=d?CGDataConsumerCreateWithCFData(d):nullptr;return r?LC32GuestObjectForOwnedHostObject(r):0;
        }
        case LC32CoreGraphicsOpDataProviderCopyData: {
            if(!RequireCoreGraphicsSlots(call,1))return 0;CGDataProviderRef p=SlotHostObject<CGDataProviderRef>(call,0);CFDataRef r=p?CGDataProviderCopyData(p):nullptr;return r?LC32GuestObjectForOwnedHostObject(r):0;
        }
        case LC32CoreGraphicsOpDataProviderCreateWithCFData: {
            if(!RequireCoreGraphicsSlots(call,1))return 0;CFDataRef d=SlotHostObject<CFDataRef>(call,0);CGDataProviderRef r=d?CGDataProviderCreateWithCFData(d):nullptr;return r?LC32GuestObjectForOwnedHostObject(r):0;
        }
        case LC32CoreGraphicsOpFontCopyPostScriptName: {
            if(!RequireCoreGraphicsSlots(call,1))return 0;CGFontRef f=SlotHostObject<CGFontRef>(call,0);CFStringRef r=f?CGFontCopyPostScriptName(f):nullptr;return r?LC32GuestObjectForOwnedHostObject(r):0;
        }
        case LC32CoreGraphicsOpFontCopyTableForTag: {
            if(!RequireCoreGraphicsSlots(call,2))return 0;CGFontRef f=SlotHostObject<CGFontRef>(call,0);CFDataRef r=f?CGFontCopyTableForTag(f,SlotU32(call,1)):nullptr;return r?LC32GuestObjectForOwnedHostObject(r):0;
        }
        case LC32CoreGraphicsOpFontCreateWithDataProvider: {
            if(!RequireCoreGraphicsSlots(call,1))return 0;CGDataProviderRef p=SlotHostObject<CGDataProviderRef>(call,0);CGFontRef r=p?CGFontCreateWithDataProvider(p):nullptr;return r?LC32GuestObjectForOwnedHostObject(r):0;
        }
        case LC32CoreGraphicsOpFontCreateWithFontName: {
            if(!RequireCoreGraphicsSlots(call,1))return 0;CFStringRef n=SlotHostObject<CFStringRef>(call,0);CGFontRef r=n?CGFontCreateWithFontName(n):nullptr;return r?LC32GuestObjectForOwnedHostObject(r):0;
        }
        case LC32CoreGraphicsOpFontGetAscent:
        case LC32CoreGraphicsOpFontGetCapHeight:
        case LC32CoreGraphicsOpFontGetDescent:
        case LC32CoreGraphicsOpFontGetUnitsPerEm:
        case LC32CoreGraphicsOpFontGetXHeight: {
            if(!RequireCoreGraphicsSlots(call,1))return 0;CGFontRef f=SlotHostObject<CGFontRef>(call,0);if(!f)return 0;int v;
            if(opcode==LC32CoreGraphicsOpFontGetAscent)v=CGFontGetAscent(f);else if(opcode==LC32CoreGraphicsOpFontGetCapHeight)v=CGFontGetCapHeight(f);else if(opcode==LC32CoreGraphicsOpFontGetDescent)v=CGFontGetDescent(f);else if(opcode==LC32CoreGraphicsOpFontGetUnitsPerEm)v=CGFontGetUnitsPerEm(f);else v=CGFontGetXHeight(f);return static_cast<u32>(v);
        }
        case LC32CoreGraphicsOpLayerGetContext: {
            if(!RequireCoreGraphicsSlots(call,1))return 0;CGLayerRef l=SlotHostObject<CGLayerRef>(call,0);CGContextRef r=l?CGLayerGetContext(l):nullptr;return r?[(id)r guest_self]:0;
        }
'''
 anchor='    }\n    return 0;\n}\n\n__END_DECLS'
 if anchor not in x:raise SystemExit('sixth switch anchor missing')
 x=x.replace(anchor,cases+'    }\n    return 0;\n}\n\n__END_DECLS',1);host.write_text(x)
print('CoreGraphics: added 13 typed provider/font exports')


# seventh typed image layer shading batch
h=header.read_text()
if 'LC32CoreGraphicsOpContextBeginPage = 163' not in h:
 anchor='    LC32CoreGraphicsOpLayerGetContext = 162,\n'
 if anchor not in h:raise SystemExit('seventh opcode anchor missing')
 h=h.replace(anchor,anchor+r'''    LC32CoreGraphicsOpContextBeginPage = 163,
    LC32CoreGraphicsOpContextDrawLayerAtPoint = 164,
    LC32CoreGraphicsOpContextDrawLayerInRect = 165,
    LC32CoreGraphicsOpContextDrawPDFPage = 166,
    LC32CoreGraphicsOpContextDrawShading = 167,
    LC32CoreGraphicsOpContextDrawTiledImage = 168,
    LC32CoreGraphicsOpImageCreateWithMaskingColors = 169,
    LC32CoreGraphicsOpImageCopyDecode = 170,
    LC32CoreGraphicsOpImageMaskCreate = 171,
    LC32CoreGraphicsOpLayerCreateWithContext = 172,
    LC32CoreGraphicsOpShadingCreateAxial = 173,
    LC32CoreGraphicsOpShadingCreateRadial = 174,
''');header.write_text(h)

g=guest.read_text()
if 'void CGContextBeginPage(CGContextRef' not in g:
 g += r'''
void CGContextBeginPage(CGContextRef c,const CGRect *r) { if(c)(void)LC32_CG_CALL(LC32CoreGraphicsOpContextBeginPage,LC32_CG_HOST(c),LC32_CG_U32(r!=NULL),r?LC32_CG_F32(r->origin.x):0,r?LC32_CG_F32(r->origin.y):0,r?LC32_CG_F32(r->size.width):0,r?LC32_CG_F32(r->size.height):0); }
void CGContextDrawLayerAtPoint(CGContextRef c,CGPoint p,CGLayerRef l) { if(c&&l)(void)LC32_CG_CALL(LC32CoreGraphicsOpContextDrawLayerAtPoint,LC32_CG_HOST(c),LC32_CG_F32(p.x),LC32_CG_F32(p.y),LC32_CG_HOST(l)); }
void CGContextDrawLayerInRect(CGContextRef c,CGRect r,CGLayerRef l) { if(c&&l)(void)LC32_CG_CALL(LC32CoreGraphicsOpContextDrawLayerInRect,LC32_CG_HOST(c),LC32_CG_F32(r.origin.x),LC32_CG_F32(r.origin.y),LC32_CG_F32(r.size.width),LC32_CG_F32(r.size.height),LC32_CG_HOST(l)); }
void CGContextDrawPDFPage(CGContextRef c,CGPDFPageRef p) { if(c&&p)(void)LC32_CG_CALL(LC32CoreGraphicsOpContextDrawPDFPage,LC32_CG_HOST(c),LC32_CG_HOST(p)); }
void CGContextDrawShading(CGContextRef c,CGShadingRef s) { if(c&&s)(void)LC32_CG_CALL(LC32CoreGraphicsOpContextDrawShading,LC32_CG_HOST(c),LC32_CG_HOST(s)); }
void CGContextDrawTiledImage(CGContextRef c,CGRect r,CGImageRef i) { if(c&&i)(void)LC32_CG_CALL(LC32CoreGraphicsOpContextDrawTiledImage,LC32_CG_HOST(c),LC32_CG_F32(r.origin.x),LC32_CG_F32(r.origin.y),LC32_CG_F32(r.size.width),LC32_CG_F32(r.size.height),LC32_CG_HOST(i)); }
CGImageRef CGImageCreateWithMaskingColors(CGImageRef i,const CGFloat *v) { return i&&v?(CGImageRef)LC32_CG_CALL(LC32CoreGraphicsOpImageCreateWithMaskingColors,LC32_CG_HOST(i),LC32_CG_U32((uintptr_t)v)):NULL; }
const CGFloat *CGImageGetDecode(CGImageRef i) { if(!i)return NULL;CGColorSpaceRef s=CGImageGetColorSpace(i);size_t n=s?CGColorSpaceGetNumberOfComponents(s):1;if(!n||n>1024)return NULL;CGFloat *v=LC32GetAssociatedGuestBuffer((id)i,(uint32_t)(n*2*sizeof(CGFloat)));return v&&LC32_CG_CALL(LC32CoreGraphicsOpImageCopyDecode,LC32_CG_HOST(i),LC32_CG_U32((uintptr_t)v),LC32_CG_U32(n*2))?v:NULL; }
CGImageRef CGImageMaskCreate(size_t w,size_t h,size_t bpc,size_t bpp,size_t row,CGDataProviderRef p,const CGFloat *decode,bool interpolate) { return p?(CGImageRef)LC32_CG_CALL(LC32CoreGraphicsOpImageMaskCreate,LC32_CG_U32(w),LC32_CG_U32(h),LC32_CG_U32(bpc),LC32_CG_U32(bpp),LC32_CG_U32(row),LC32_CG_HOST(p),LC32_CG_U32((uintptr_t)decode),LC32_CG_U32(interpolate)):NULL; }
CGLayerRef CGLayerCreateWithContext(CGContextRef c,CGSize s,CFDictionaryRef aux) { return c?(CGLayerRef)LC32_CG_CALL(LC32CoreGraphicsOpLayerCreateWithContext,LC32_CG_HOST(c),LC32_CG_F32(s.width),LC32_CG_F32(s.height),LC32_CG_HOST(aux)):NULL; }
CGShadingRef CGShadingCreateAxial(CGColorSpaceRef space,CGPoint start,CGPoint end,CGFunctionRef function,bool extendStart,bool extendEnd) { return space&&function?(CGShadingRef)LC32_CG_CALL(LC32CoreGraphicsOpShadingCreateAxial,LC32_CG_HOST(space),LC32_CG_F32(start.x),LC32_CG_F32(start.y),LC32_CG_F32(end.x),LC32_CG_F32(end.y),LC32_CG_HOST(function),LC32_CG_U32(extendStart),LC32_CG_U32(extendEnd)):NULL; }
CGShadingRef CGShadingCreateRadial(CGColorSpaceRef space,CGPoint start,CGFloat sr,CGPoint end,CGFloat er,CGFunctionRef function,bool extendStart,bool extendEnd) { return space&&function?(CGShadingRef)LC32_CG_CALL(LC32CoreGraphicsOpShadingCreateRadial,LC32_CG_HOST(space),LC32_CG_F32(start.x),LC32_CG_F32(start.y),LC32_CG_F32(sr),LC32_CG_F32(end.x),LC32_CG_F32(end.y),LC32_CG_F32(er),LC32_CG_HOST(function),LC32_CG_U32(extendStart),LC32_CG_U32(extendEnd)):NULL; }
''';guest.write_text(g)

x=host.read_text()
if 'case LC32CoreGraphicsOpContextBeginPage:' not in x:
 cases=r'''
        case LC32CoreGraphicsOpContextBeginPage: {
            if(!RequireCoreGraphicsSlots(call,6))return 0;CGContextRef c=SlotHostObject<CGContextRef>(call,0);u32 present=SlotU32(call,1);if(!c||present>1)return 0;CGRect r=SlotRect(call,2);CGContextBeginPage(c,present?&r:nullptr);return 1;
        }
        case LC32CoreGraphicsOpContextDrawLayerAtPoint: {
            if(!RequireCoreGraphicsSlots(call,4))return 0;CGContextRef c=SlotHostObject<CGContextRef>(call,0);CGLayerRef l=SlotHostObject<CGLayerRef>(call,3);if(!c||!l)return 0;CGContextDrawLayerAtPoint(c,CGPointMake(SlotCGFloat(call,1),SlotCGFloat(call,2)),l);SyncBitmapBacking(c,FindBitmapBacking(c));return 1;
        }
        case LC32CoreGraphicsOpContextDrawLayerInRect:
        case LC32CoreGraphicsOpContextDrawTiledImage: {
            if(!RequireCoreGraphicsSlots(call,6))return 0;CGContextRef c=SlotHostObject<CGContextRef>(call,0);if(!c)return 0;CGRect r=SlotRect(call,1);
            if(opcode==LC32CoreGraphicsOpContextDrawLayerInRect){CGLayerRef l=SlotHostObject<CGLayerRef>(call,5);if(!l)return 0;CGContextDrawLayerInRect(c,r,l);}else{CGImageRef i=SlotHostObject<CGImageRef>(call,5);if(!i)return 0;CGContextDrawTiledImage(c,r,i);}SyncBitmapBacking(c,FindBitmapBacking(c));return 1;
        }
        case LC32CoreGraphicsOpContextDrawPDFPage:
        case LC32CoreGraphicsOpContextDrawShading: {
            if(!RequireCoreGraphicsSlots(call,2))return 0;CGContextRef c=SlotHostObject<CGContextRef>(call,0);if(!c)return 0;
            if(opcode==LC32CoreGraphicsOpContextDrawPDFPage){CGPDFPageRef p=SlotHostObject<CGPDFPageRef>(call,1);if(!p)return 0;CGContextDrawPDFPage(c,p);}else{CGShadingRef s=SlotHostObject<CGShadingRef>(call,1);if(!s)return 0;CGContextDrawShading(c,s);}SyncBitmapBacking(c,FindBitmapBacking(c));return 1;
        }
        case LC32CoreGraphicsOpImageCreateWithMaskingColors: {
            if(!RequireCoreGraphicsSlots(call,2))return 0;CGImageRef i=SlotHostObject<CGImageRef>(call,0);if(!i)return 0;CGColorSpaceRef space=CGImageGetColorSpace(i);size_t n=space?CGColorSpaceGetNumberOfComponents(space):0;std::vector<CGFloat> values;const CGFloat *ptr=nullptr;if(!n||!ReadGuestCGFloatArray(SlotU32(call,1),n*2,false,values,ptr))return 0;CGImageRef r=CGImageCreateWithMaskingColors(i,ptr);return r?LC32GuestObjectForOwnedHostObject(r):0;
        }
        case LC32CoreGraphicsOpImageCopyDecode: {
            if(!RequireCoreGraphicsSlots(call,3))return 0;CGImageRef i=SlotHostObject<CGImageRef>(call,0);size_t n=SlotU32(call,2);const CGFloat *v=i?CGImageGetDecode(i):nullptr;return v&&n&&n<=2048?WriteGuestCoreGraphicsFloats(SlotU32(call,1),v,n):0;
        }
        case LC32CoreGraphicsOpImageMaskCreate: {
            if(!RequireCoreGraphicsSlots(call,8))return 0;CGDataProviderRef p=SlotHostObject<CGDataProviderRef>(call,5);u32 interpolate=SlotU32(call,7);if(!p||interpolate>1)return 0;std::vector<CGFloat> values;const CGFloat *decode=nullptr;if(SlotU32(call,6)&&!ReadGuestCGFloatArray(SlotU32(call,6),2,true,values,decode))return 0;CGImageRef r=CGImageMaskCreate(SlotU32(call,0),SlotU32(call,1),SlotU32(call,2),SlotU32(call,3),SlotU32(call,4),p,decode,interpolate!=0);return r?LC32GuestObjectForOwnedHostObject(r):0;
        }
        case LC32CoreGraphicsOpLayerCreateWithContext: {
            if(!RequireCoreGraphicsSlots(call,4))return 0;CGContextRef c=SlotHostObject<CGContextRef>(call,0);if(!c)return 0;CGLayerRef r=CGLayerCreateWithContext(c,CGSizeMake(SlotCGFloat(call,1),SlotCGFloat(call,2)),SlotHostObject<CFDictionaryRef>(call,3));return r?LC32GuestObjectForOwnedHostObject(r):0;
        }
        case LC32CoreGraphicsOpShadingCreateAxial:
        case LC32CoreGraphicsOpShadingCreateRadial: {
            const bool radial=opcode==LC32CoreGraphicsOpShadingCreateRadial;if(!RequireCoreGraphicsSlots(call,radial?10:8))return 0;CGColorSpaceRef s=SlotHostObject<CGColorSpaceRef>(call,0);CGFunctionRef f=SlotHostObject<CGFunctionRef>(call,radial?7:5);u32 a=SlotU32(call,radial?8:6),b=SlotU32(call,radial?9:7);if(!s||!f||a>1||b>1)return 0;CGShadingRef r=radial?CGShadingCreateRadial(s,CGPointMake(SlotCGFloat(call,1),SlotCGFloat(call,2)),SlotCGFloat(call,3),CGPointMake(SlotCGFloat(call,4),SlotCGFloat(call,5)),SlotCGFloat(call,6),f,a!=0,b!=0):CGShadingCreateAxial(s,CGPointMake(SlotCGFloat(call,1),SlotCGFloat(call,2)),CGPointMake(SlotCGFloat(call,3),SlotCGFloat(call,4)),f,a!=0,b!=0);return r?LC32GuestObjectForOwnedHostObject(r):0;
        }
'''
 anchor='    }\n    return 0;\n}\n\n__END_DECLS'
 if anchor not in x:raise SystemExit('seventh switch anchor missing')
 x=x.replace(anchor,cases+'    }\n    return 0;\n}\n\n__END_DECLS',1);host.write_text(x)
print('CoreGraphics: added 12 typed image/layer/shading exports')


# eighth typed text path dictionary batch
h=header.read_text()
if 'LC32CoreGraphicsOpColorSpaceGetColorTableCount = 175' not in h:
 anchor='    LC32CoreGraphicsOpShadingCreateRadial = 174,\n'
 if anchor not in h:raise SystemExit('eighth opcode anchor missing')
 h=h.replace(anchor,anchor+r'''    LC32CoreGraphicsOpColorSpaceGetColorTableCount = 175,
    LC32CoreGraphicsOpColorSpaceCopyColorTable = 176,
    LC32CoreGraphicsOpFontGetGlyphAdvances = 177,
    LC32CoreGraphicsOpContextSelectFont = 178,
    LC32CoreGraphicsOpContextShowTextAtPoint = 179,
    LC32CoreGraphicsOpContextShowGlyphsAtPoint = 180,
    LC32CoreGraphicsOpContextShowGlyphsAtPositions = 181,
    LC32CoreGraphicsOpPathCreateCopyByDashingPath = 182,
    LC32CoreGraphicsOpPathCreateCopyByStrokingPath = 183,
    LC32CoreGraphicsOpPointMakeWithDictionaryRepresentation = 184,
    LC32CoreGraphicsOpRectMakeWithDictionaryRepresentation = 185,
    LC32CoreGraphicsOpSizeCreateDictionaryRepresentation = 186,
    LC32CoreGraphicsOpSizeMakeWithDictionaryRepresentation = 187,
''');header.write_text(h)

g=guest.read_text()
if 'size_t CGColorSpaceGetColorTableCount(' not in g:
 g += r'''
size_t CGColorSpaceGetColorTableCount(CGColorSpaceRef s) { return s?(size_t)LC32_CG_CALL(LC32CoreGraphicsOpColorSpaceGetColorTableCount,LC32_CG_HOST(s)):0; }
void CGColorSpaceGetColorTable(CGColorSpaceRef s,uint8_t *table) { if(s&&table)(void)LC32_CG_CALL(LC32CoreGraphicsOpColorSpaceCopyColorTable,LC32_CG_HOST(s),LC32_CG_U32((uintptr_t)table)); }
bool CGFontGetGlyphAdvances(CGFontRef f,const CGGlyph *glyphs,size_t n,int *advances) { return f&&glyphs&&advances&&n&&LC32_CG_CALL(LC32CoreGraphicsOpFontGetGlyphAdvances,LC32_CG_HOST(f),LC32_CG_U32((uintptr_t)glyphs),LC32_CG_U32(n),LC32_CG_U32((uintptr_t)advances)); }
void CGContextSelectFont(CGContextRef c,const char *name,CGFloat size,CGTextEncoding encoding) { if(!c||!name)return;size_t n=strnlen(name,LC32CoreGraphicsMaximumFilenameBytes+1);if(n<=LC32CoreGraphicsMaximumFilenameBytes)(void)LC32_CG_CALL(LC32CoreGraphicsOpContextSelectFont,LC32_CG_HOST(c),LC32_CG_U32((uintptr_t)name),LC32_CG_U32(n),LC32_CG_F32(size),LC32_CG_U32(encoding)); }
void CGContextShowTextAtPoint(CGContextRef c,CGFloat x,CGFloat y,const char *text,size_t n) { if(c&&text&&n)(void)LC32_CG_CALL(LC32CoreGraphicsOpContextShowTextAtPoint,LC32_CG_HOST(c),LC32_CG_F32(x),LC32_CG_F32(y),LC32_CG_U32((uintptr_t)text),LC32_CG_U32(n)); }
void CGContextShowGlyphsAtPoint(CGContextRef c,CGFloat x,CGFloat y,const CGGlyph *glyphs,size_t n) { if(c&&glyphs&&n)(void)LC32_CG_CALL(LC32CoreGraphicsOpContextShowGlyphsAtPoint,LC32_CG_HOST(c),LC32_CG_F32(x),LC32_CG_F32(y),LC32_CG_U32((uintptr_t)glyphs),LC32_CG_U32(n)); }
void CGContextShowGlyphsAtPositions(CGContextRef c,const CGGlyph *glyphs,const CGPoint *positions,size_t n) { if(c&&glyphs&&positions&&n)(void)LC32_CG_CALL(LC32CoreGraphicsOpContextShowGlyphsAtPositions,LC32_CG_HOST(c),LC32_CG_U32((uintptr_t)glyphs),LC32_CG_U32((uintptr_t)positions),LC32_CG_U32(n)); }
CGPathRef CGPathCreateCopyByDashingPath(CGPathRef p,const CGAffineTransform *t,CGFloat phase,const CGFloat *lengths,size_t n) { return p&&lengths&&n?(CGPathRef)LC32_CG_CALL(LC32CoreGraphicsOpPathCreateCopyByDashingPath,LC32_CG_HOST(p),LC32_CG_U32(t!=NULL),t?LC32_CG_F32(t->a):0,t?LC32_CG_F32(t->b):0,t?LC32_CG_F32(t->c):0,t?LC32_CG_F32(t->d):0,t?LC32_CG_F32(t->tx):0,t?LC32_CG_F32(t->ty):0,LC32_CG_F32(phase),LC32_CG_U32((uintptr_t)lengths),LC32_CG_U32(n)):NULL; }
CGPathRef CGPathCreateCopyByStrokingPath(CGPathRef p,const CGAffineTransform *t,CGFloat width,CGLineCap cap,CGLineJoin join,CGFloat miter) { return p?(CGPathRef)LC32_CG_CALL(LC32CoreGraphicsOpPathCreateCopyByStrokingPath,LC32_CG_HOST(p),LC32_CG_U32(t!=NULL),t?LC32_CG_F32(t->a):0,t?LC32_CG_F32(t->b):0,t?LC32_CG_F32(t->c):0,t?LC32_CG_F32(t->d):0,t?LC32_CG_F32(t->tx):0,t?LC32_CG_F32(t->ty):0,LC32_CG_F32(width),LC32_CG_U32(cap),LC32_CG_U32(join),LC32_CG_F32(miter)):NULL; }
bool CGPointMakeWithDictionaryRepresentation(CFDictionaryRef d,CGPoint *p) { return d&&p&&LC32_CG_CALL(LC32CoreGraphicsOpPointMakeWithDictionaryRepresentation,LC32_CG_HOST(d),LC32_CG_U32((uintptr_t)p)); }
bool CGRectMakeWithDictionaryRepresentation(CFDictionaryRef d,CGRect *r) { return d&&r&&LC32_CG_CALL(LC32CoreGraphicsOpRectMakeWithDictionaryRepresentation,LC32_CG_HOST(d),LC32_CG_U32((uintptr_t)r)); }
CFDictionaryRef CGSizeCreateDictionaryRepresentation(CGSize s) { return (CFDictionaryRef)LC32_CG_CALL(LC32CoreGraphicsOpSizeCreateDictionaryRepresentation,LC32_CG_F32(s.width),LC32_CG_F32(s.height)); }
bool CGSizeMakeWithDictionaryRepresentation(CFDictionaryRef d,CGSize *s) { return d&&s&&LC32_CG_CALL(LC32CoreGraphicsOpSizeMakeWithDictionaryRepresentation,LC32_CG_HOST(d),LC32_CG_U32((uintptr_t)s)); }
''';guest.write_text(g)

x=host.read_text()
if 'bool ReadGuestCoreGraphicsGlyphs(' not in x:
 anchor='} // namespace\n\n__BEGIN_DECLS'
 helper=r'''bool ReadGuestCoreGraphicsGlyphs(u32 address,size_t count,std::vector<CGGlyph>& out) {
    if(!address||!count||count>1024*1024||count>SIZE_MAX/sizeof(CGGlyph)||static_cast<uint64_t>(address)+count*sizeof(CGGlyph)>static_cast<uint64_t>(UINT32_MAX)+1)return false;
    out.resize(count);return Dynarmic_mem_1read(address,count*sizeof(CGGlyph),reinterpret_cast<char *>(out.data()))==0;
}
bool ReadGuestCoreGraphicsBytes(u32 address,size_t count,std::vector<char>& out) {
    if(!address||!count||count>LC32CoreGraphicsMaximumFilenameBytes||static_cast<uint64_t>(address)+count>static_cast<uint64_t>(UINT32_MAX)+1)return false;
    out.resize(count+1);if(Dynarmic_mem_1read(address,count,out.data())!=0)return false;out[count]=0;return true;
}

'''
 if anchor not in x:raise SystemExit('eighth namespace anchor missing')
 x=x.replace(anchor,helper+anchor,1)
if 'case LC32CoreGraphicsOpColorSpaceGetColorTableCount:' not in x:
 cases=r'''
        case LC32CoreGraphicsOpColorSpaceGetColorTableCount: {
            if(!RequireCoreGraphicsSlots(call,1))return 0;CGColorSpaceRef s=SlotHostObject<CGColorSpaceRef>(call,0);return s?static_cast<u32>(CGColorSpaceGetColorTableCount(s)):0;
        }
        case LC32CoreGraphicsOpColorSpaceCopyColorTable: {
            if(!RequireCoreGraphicsSlots(call,2))return 0;CGColorSpaceRef s=SlotHostObject<CGColorSpaceRef>(call,0);if(!s)return 0;size_t entries=CGColorSpaceGetColorTableCount(s),components=CGColorSpaceGetNumberOfComponents(s);if(!entries||!components||entries>SIZE_MAX/components)return 0;size_t bytes=entries*components;std::vector<uint8_t> table(bytes);CGColorSpaceGetColorTable(s,table.data());return Dynarmic_mem_1write(SlotU32(call,1),bytes,reinterpret_cast<char *>(table.data()))==0;
        }
        case LC32CoreGraphicsOpFontGetGlyphAdvances: {
            if(!RequireCoreGraphicsSlots(call,4))return 0;CGFontRef f=SlotHostObject<CGFontRef>(call,0);size_t n=SlotU32(call,2);std::vector<CGGlyph> glyphs;if(!f||!ReadGuestCoreGraphicsGlyphs(SlotU32(call,1),n,glyphs)||n>SIZE_MAX/sizeof(int))return 0;std::vector<int> advances(n);if(!CGFontGetGlyphAdvances(f,glyphs.data(),n,advances.data()))return 0;return Dynarmic_mem_1write(SlotU32(call,3),n*sizeof(int),reinterpret_cast<char *>(advances.data()))==0;
        }
        case LC32CoreGraphicsOpContextSelectFont: {
            if(!RequireCoreGraphicsSlots(call,5))return 0;CGContextRef c=SlotHostObject<CGContextRef>(call,0);std::vector<char> name;if(!c||!ReadGuestCoreGraphicsBytes(SlotU32(call,1),SlotU32(call,2),name))return 0;CGContextSelectFont(c,name.data(),SlotCGFloat(call,3),(CGTextEncoding)SlotU32(call,4));return 1;
        }
        case LC32CoreGraphicsOpContextShowTextAtPoint: {
            if(!RequireCoreGraphicsSlots(call,5))return 0;CGContextRef c=SlotHostObject<CGContextRef>(call,0);std::vector<char> text;if(!c||!ReadGuestCoreGraphicsBytes(SlotU32(call,3),SlotU32(call,4),text))return 0;CGContextShowTextAtPoint(c,SlotCGFloat(call,1),SlotCGFloat(call,2),text.data(),SlotU32(call,4));SyncBitmapBacking(c,FindBitmapBacking(c));return 1;
        }
        case LC32CoreGraphicsOpContextShowGlyphsAtPoint:
        case LC32CoreGraphicsOpContextShowGlyphsAtPositions: {
            const bool positions=opcode==LC32CoreGraphicsOpContextShowGlyphsAtPositions;if(!RequireCoreGraphicsSlots(call,positions?4:5))return 0;CGContextRef c=SlotHostObject<CGContextRef>(call,0);size_t n=SlotU32(call,positions?3:4);std::vector<CGGlyph> glyphs;if(!c||!ReadGuestCoreGraphicsGlyphs(SlotU32(call,positions?1:3),n,glyphs))return 0;if(positions){std::vector<CGPoint> p;if(!ReadGuestCoreGraphicsPoints(SlotU32(call,2),n,p))return 0;CGContextShowGlyphsAtPositions(c,glyphs.data(),p.data(),n);}else CGContextShowGlyphsAtPoint(c,SlotCGFloat(call,1),SlotCGFloat(call,2),glyphs.data(),n);SyncBitmapBacking(c,FindBitmapBacking(c));return 1;
        }
        case LC32CoreGraphicsOpPathCreateCopyByDashingPath: {
            if(!RequireCoreGraphicsSlots(call,11))return 0;CGPathRef p=SlotHostObject<CGPathRef>(call,0);if(!p)return 0;CGAffineTransform storage;const CGAffineTransform *t;if(!SlotOptionalTransform(call,1,2,storage,t))return 0;size_t n=SlotU32(call,10);std::vector<CGFloat> lengths;const CGFloat *v=nullptr;if(!ReadGuestCGFloatArray(SlotU32(call,9),n,false,lengths,v))return 0;CGPathRef r=CGPathCreateCopyByDashingPath(p,t,SlotCGFloat(call,8),v,n);return r?LC32GuestObjectForOwnedHostObject(r):0;
        }
        case LC32CoreGraphicsOpPathCreateCopyByStrokingPath: {
            if(!RequireCoreGraphicsSlots(call,12))return 0;CGPathRef p=SlotHostObject<CGPathRef>(call,0);if(!p)return 0;CGAffineTransform storage;const CGAffineTransform *t;if(!SlotOptionalTransform(call,1,2,storage,t))return 0;CGPathRef r=CGPathCreateCopyByStrokingPath(p,t,SlotCGFloat(call,8),(CGLineCap)SlotU32(call,9),(CGLineJoin)SlotU32(call,10),SlotCGFloat(call,11));return r?LC32GuestObjectForOwnedHostObject(r):0;
        }
        case LC32CoreGraphicsOpPointMakeWithDictionaryRepresentation:
        case LC32CoreGraphicsOpRectMakeWithDictionaryRepresentation:
        case LC32CoreGraphicsOpSizeMakeWithDictionaryRepresentation: {
            if(!RequireCoreGraphicsSlots(call,2))return 0;CFDictionaryRef d=SlotHostObject<CFDictionaryRef>(call,0);if(!d)return 0;if(opcode==LC32CoreGraphicsOpPointMakeWithDictionaryRepresentation){CGPoint v;if(!CGPointMakeWithDictionaryRepresentation(d,&v))return 0;CGFloat a[2]={v.x,v.y};return WriteGuestCoreGraphicsFloats(SlotU32(call,1),a,2);}if(opcode==LC32CoreGraphicsOpRectMakeWithDictionaryRepresentation){CGRect v;if(!CGRectMakeWithDictionaryRepresentation(d,&v))return 0;CGFloat a[4]={v.origin.x,v.origin.y,v.size.width,v.size.height};return WriteGuestCoreGraphicsFloats(SlotU32(call,1),a,4);}CGSize v;if(!CGSizeMakeWithDictionaryRepresentation(d,&v))return 0;CGFloat a[2]={v.width,v.height};return WriteGuestCoreGraphicsFloats(SlotU32(call,1),a,2);
        }
        case LC32CoreGraphicsOpSizeCreateDictionaryRepresentation: {
            if(!RequireCoreGraphicsSlots(call,2))return 0;CFDictionaryRef r=CGSizeCreateDictionaryRepresentation(CGSizeMake(SlotCGFloat(call,0),SlotCGFloat(call,1)));return r?LC32GuestObjectForOwnedHostObject(r):0;
        }
'''
 anchor='    }\n    return 0;\n}\n\n__END_DECLS'
 if anchor not in x:raise SystemExit('eighth switch anchor missing')
 x=x.replace(anchor,cases+'    }\n    return 0;\n}\n\n__END_DECLS',1);host.write_text(x)
print('CoreGraphics: added 13 typed text/path/dictionary exports')
