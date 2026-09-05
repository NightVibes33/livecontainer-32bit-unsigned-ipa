#!/usr/bin/env python3
from pathlib import Path
ROOT = Path("build/LiveExec32")

def insert_once(path, anchor, addition, marker):
    path = ROOT / path
    text = path.read_text()
    if marker in text: return
    if anchor not in text: raise SystemExit(f"anchor missing in {path}: {anchor[:80]!r}")
    path.write_text(text.replace(anchor, addition + anchor, 1))

insert_once("GuestFrameworks/CoreGraphics/CoreGraphics.m",
"bool CGAffineTransformIsIdentity(CGAffineTransform transform) {\n",
"""CGAffineTransform CGAffineTransformInvert(CGAffineTransform t) {
    const CGFloat determinant = t.a * t.d - t.b * t.c;
    if(determinant == 0) return t;
    const CGFloat inverse = 1 / determinant;
    return (CGAffineTransform){
        t.d * inverse, -t.b * inverse, -t.c * inverse, t.a * inverse,
        (t.c * t.ty - t.d * t.tx) * inverse,
        (t.b * t.tx - t.a * t.ty) * inverse,
    };
}

""", "CGAffineTransform CGAffineTransformInvert(")

insert_once("GuestFrameworks/CoreGraphics/CoreGraphics.m",
"bool CGRectIsEmpty(CGRect rect) {\n",
"""CGRect CGRectStandardize(CGRect rect) {
    if(rect.size.width < 0) {
        rect.origin.x += rect.size.width;
        rect.size.width = -rect.size.width;
    }
    if(rect.size.height < 0) {
        rect.origin.y += rect.size.height;
        rect.size.height = -rect.size.height;
    }
    return rect;
}

""", "CGRect CGRectStandardize(")

insert_once("GuestFrameworks/CoreGraphics/CoreGraphics.m",
"void CGColorRelease(CGColorRef color) {\n",
"""CGColorRef CGColorRetain(CGColorRef color) {
    return color ? (CGColorRef)CFRetain(color) : NULL;
}

""", "CGColorRef CGColorRetain(")

uikit = ROOT / "GuestFrameworks/UIKit/UIKit.m"
if "CGPoint CGPointFromString(" not in uikit.read_text():
    with uikit.open("a") as f:
        f.write("""
CGPoint CGPointFromString(NSString *string) {
    if(!string) return CGPointZero;
    NSString *rectString = [NSString stringWithFormat:@"{%@,{0,0}}", string];
    return CGRectFromString(rectString).origin;
}
""")

corevideo = ROOT / "GuestFrameworks/CoreVideo"
corevideo.mkdir(parents=True, exist_ok=True)
(corevideo / "CoreVideo.m").write_text("""#import <CoreVideo/CoreVideo.h>\n#import <Foundation/Foundation.h>\n#include <stdint.h>\n#include <stdlib.h>
const CFStringRef kCVPixelBufferPixelFormatTypeKey = CFSTR("PixelFormatType");
const CFStringRef kCVPixelBufferBytesPerRowAlignmentKey = CFSTR("BytesPerRowAlignment");
const CFStringRef kCVPixelBufferHeightKey = CFSTR("Height");
const CFStringRef kCVPixelBufferIOSurfacePropertiesKey = CFSTR("IOSurfaceProperties");
const CFStringRef kCVPixelBufferWidthKey = CFSTR("Width");
const CFStringRef kCVImageBufferColorPrimariesKey = CFSTR("ColorPrimaries");
const CFStringRef kCVImageBufferColorPrimaries_ITU_R_709_2 = CFSTR("ITU_R_709_2");
const CFStringRef kCVImageBufferTransferFunctionKey = CFSTR("TransferFunction");
const CFStringRef kCVImageBufferTransferFunction_ITU_R_709_2 = CFSTR("ITU_R_709_2");
const CFStringRef kCVImageBufferYCbCrMatrixKey = CFSTR("YCbCrMatrix");
const CFStringRef kCVImageBufferYCbCrMatrix_ITU_R_601_4 = CFSTR("ITU_R_601_4");
@interface LC32PixelBuffer : NSObject { @public size_t w,h,row,size; OSType format; void *bytes; BOOL owns; NSUInteger locks; CVPixelBufferReleaseBytesCallback callback; void *context; NSMutableDictionary *attachments; NSMutableDictionary *modes; } @end
@implementation LC32PixelBuffer
- (id)init { if((self=[super init])) { attachments=[NSMutableDictionary new]; modes=[NSMutableDictionary new]; } return self; }
- (void)dealloc { if(callback) callback(context, bytes); else if(owns) free(bytes); [attachments release]; [modes release]; [super dealloc]; }
@end
static LC32PixelBuffer *LC32PB(CVPixelBufferRef b) { id o=(id)b; return [o isKindOfClass:[LC32PixelBuffer class]] ? (LC32PixelBuffer *)o : nil; }
CVReturn CVPixelBufferLockBaseAddress(CVPixelBufferRef b, CVPixelBufferLockFlags f) { LC32PixelBuffer *p=LC32PB(b); if(!p) return kCVReturnInvalidArgument; p->locks++; return kCVReturnSuccess; }
CVReturn CVPixelBufferUnlockBaseAddress(CVPixelBufferRef b, CVPixelBufferLockFlags f) { LC32PixelBuffer *p=LC32PB(b); if(!p || !p->locks) return kCVReturnInvalidArgument; p->locks--; return kCVReturnSuccess; }
void *CVPixelBufferGetBaseAddress(CVPixelBufferRef b) { LC32PixelBuffer *p=LC32PB(b); return p?p->bytes:NULL; }
void *CVPixelBufferGetBaseAddressOfPlane(CVPixelBufferRef b, size_t p) { return NULL; }
size_t CVPixelBufferGetBytesPerRow(CVPixelBufferRef b) { LC32PixelBuffer *p=LC32PB(b); return p?p->row:0; }
size_t CVPixelBufferGetBytesPerRowOfPlane(CVPixelBufferRef b, size_t p) { return 0; }
size_t CVPixelBufferGetDataSize(CVPixelBufferRef b) { LC32PixelBuffer *p=LC32PB(b); return p?p->size:0; }
size_t CVPixelBufferGetHeight(CVPixelBufferRef b) { LC32PixelBuffer *p=LC32PB(b); return p?p->h:0; }
size_t CVPixelBufferGetWidth(CVPixelBufferRef b) { LC32PixelBuffer *p=LC32PB(b); return p?p->w:0; }
size_t CVPixelBufferGetPlaneCount(CVPixelBufferRef b) { return 0; }
CFTypeRef CVBufferGetAttachment(CVBufferRef b, CFStringRef k, CVAttachmentMode *m) { LC32PixelBuffer *p=LC32PB((CVPixelBufferRef)b); if(!p || !k) return NULL; if(m) *m=(CVAttachmentMode)[[p->modes objectForKey:(id)k] unsignedIntegerValue]; return (CFTypeRef)[p->attachments objectForKey:(id)k]; }
void CVBufferSetAttachment(CVBufferRef b, CFStringRef k, CFTypeRef v, CVAttachmentMode m) { LC32PixelBuffer *p=LC32PB((CVPixelBufferRef)b); if(!p || !k) return; if(v) { [p->attachments setObject:(id)v forKey:(id)k]; [p->modes setObject:[NSNumber numberWithUnsignedInteger:m] forKey:(id)k]; } else { [p->attachments removeObjectForKey:(id)k]; [p->modes removeObjectForKey:(id)k]; } }
CVReturn CVPixelBufferCreate(CFAllocatorRef a, size_t w, size_t h, OSType f, CFDictionaryRef d, CVPixelBufferRef *o) { if(!o || !w || !h) return kCVReturnInvalidArgument; *o=NULL; size_t bpp=(f==0x42475241 || f==0x41524742)?4:(f==0x4c303038?1:0); if(!bpp || w>SIZE_MAX/bpp || h>SIZE_MAX/(w*bpp)) return kCVReturnInvalidPixelFormat; LC32PixelBuffer *p=[LC32PixelBuffer new]; p->w=w; p->h=h; p->format=f; p->row=w*bpp; p->size=p->row*h; p->bytes=calloc(1,p->size); if(!p->bytes){[p release];return kCVReturnAllocationFailed;} p->owns=YES; *o=(CVPixelBufferRef)p; return kCVReturnSuccess; }
CVReturn CVPixelBufferCreateWithBytes(CFAllocatorRef a, size_t w, size_t h, OSType f, void *base, size_t row, CVPixelBufferReleaseBytesCallback cb, void *ctx, CFDictionaryRef d, CVPixelBufferRef *o) { if(!o || !base || !w || !h || row>SIZE_MAX/h) return kCVReturnInvalidArgument; *o=NULL; LC32PixelBuffer *p=[LC32PixelBuffer new]; p->w=w; p->h=h; p->format=f; p->row=row; p->size=row*h; p->bytes=base; p->callback=cb; p->context=ctx; *o=(CVPixelBufferRef)p; return kCVReturnSuccess; }
CVReturn CVPixelBufferPoolCreatePixelBuffer(CFAllocatorRef a, CVPixelBufferPoolRef p, CVPixelBufferRef *o) { if(o) *o=NULL; return kCVReturnUnsupported; }
void CVPixelBufferRelease(CVPixelBufferRef b) { if(b) CFRelease(b); }
CVReturn CVOpenGLESTextureCacheCreate(CFAllocatorRef a, CFDictionaryRef ca, EAGLContext *c, CFDictionaryRef ta, CVOpenGLESTextureCacheRef *o) { if(o) *o=NULL; return kCVReturnUnsupported; }
CVReturn CVOpenGLESTextureCacheCreateTextureFromImage(CFAllocatorRef a, CVOpenGLESTextureCacheRef c, CVImageBufferRef i, CFDictionaryRef d, GLenum t, GLint in, GLsizei w, GLsizei h, GLenum f, GLenum ty, size_t p, CVOpenGLESTextureRef *o) { if(o) *o=NULL; return kCVReturnUnsupported; }
void CVOpenGLESTextureCacheFlush(CVOpenGLESTextureCacheRef c, CVOptionFlags o) {}
GLuint CVOpenGLESTextureGetName(CVOpenGLESTextureRef i) { return 0; }
GLenum CVOpenGLESTextureGetTarget(CVOpenGLESTextureRef i) { return 0; }
""")
plist_source = ROOT / "GuestMakefile/FrameworkInfoPlists/CoreMedia.plist"
(ROOT / "GuestMakefile/FrameworkInfoPlists/CoreVideo.plist").write_text(
    plist_source.read_text().replace("CoreMedia", "CoreVideo"))
print("patched focus value graphics and installed CoreVideo image")


# Exact ABI-local value operations and CF ownership operations required by the
# corpus. Host-backed opaque objects are Objective-C proxy objects in the guest,
# so CFRetain/CFRelease preserve the same ownership contract without allowing a
# native pointer to escape into ARM32 code.
core_graphics = ROOT / "GuestFrameworks/CoreGraphics/CoreGraphics.m"
text = core_graphics.read_text()
local_exports = r"""
bool CGAffineTransformEqualToTransform(CGAffineTransform left,
                                       CGAffineTransform right) {
    return left.a == right.a && left.b == right.b &&
        left.c == right.c && left.d == right.d &&
        left.tx == right.tx && left.ty == right.ty;
}

bool LC32CGSizeEqualToSizeExport(CGSize left, CGSize right)
    __asm__("_CGSizeEqualToSize");
bool LC32CGSizeEqualToSizeExport(CGSize left, CGSize right) {
    return left.width == right.width && left.height == right.height;
}

CGColorSpaceRef CGColorSpaceRetain(CGColorSpaceRef space) {
    return space ? (CGColorSpaceRef)CFRetain(space) : NULL;
}

CGFontRef CGFontRetain(CGFontRef font) {
    return font ? (CGFontRef)CFRetain(font) : NULL;
}
void CGFontRelease(CGFontRef font) { if(font) CFRelease(font); }

CGImageRef CGImageRetain(CGImageRef image) {
    return image ? (CGImageRef)CFRetain(image) : NULL;
}

CGLayerRef CGLayerRetain(CGLayerRef layer) {
    return layer ? (CGLayerRef)CFRetain(layer) : NULL;
}
void CGLayerRelease(CGLayerRef layer) { if(layer) CFRelease(layer); }

CGPDFContentStreamRef CGPDFContentStreamRetain(CGPDFContentStreamRef stream) {
    return stream ? (CGPDFContentStreamRef)CFRetain(stream) : NULL;
}
void CGPDFContentStreamRelease(CGPDFContentStreamRef stream) {
    if(stream) CFRelease(stream);
}

CGPDFDocumentRef CGPDFDocumentRetain(CGPDFDocumentRef document) {
    return document ? (CGPDFDocumentRef)CFRetain(document) : NULL;
}
void CGPDFDocumentRelease(CGPDFDocumentRef document) {
    if(document) CFRelease(document);
}

CGPDFPageRef CGPDFPageRetain(CGPDFPageRef page) {
    return page ? (CGPDFPageRef)CFRetain(page) : NULL;
}
void CGPDFPageRelease(CGPDFPageRef page) { if(page) CFRelease(page); }

CGPathRef CGPathRetain(CGPathRef path) {
    return path ? (CGPathRef)CFRetain(path) : NULL;
}

void CGDataConsumerRelease(CGDataConsumerRef consumer) {
    if(consumer) CFRelease(consumer);
}
void CGFunctionRelease(CGFunctionRef function) {
    if(function) CFRelease(function);
}
void CGPDFOperatorTableRelease(CGPDFOperatorTableRef table) {
    if(table) CFRelease(table);
}
void CGPDFScannerRelease(CGPDFScannerRef scanner) {
    if(scanner) CFRelease(scanner);
}
void CGShadingRelease(CGShadingRef shading) {
    if(shading) CFRelease(shading);
}
"""
for declaration in [
    "bool CGAffineTransformEqualToTransform(", "LC32CGSizeEqualToSizeExport(",
    "CGColorSpaceRef CGColorSpaceRetain(", "CGFontRef CGFontRetain(",
    "void CGFontRelease(", "CGImageRef CGImageRetain(",
    "CGLayerRef CGLayerRetain(", "void CGLayerRelease(",
    "CGPDFContentStreamRef CGPDFContentStreamRetain(",
    "void CGPDFContentStreamRelease(", "CGPDFDocumentRef CGPDFDocumentRetain(",
    "void CGPDFDocumentRelease(", "CGPDFPageRef CGPDFPageRetain(",
    "void CGPDFPageRelease(", "CGPathRef CGPathRetain(",
    "void CGDataConsumerRelease(", "void CGFunctionRelease(",
    "void CGPDFOperatorTableRelease(", "void CGPDFScannerRelease(",
    "void CGShadingRelease(",
]:
    if declaration in text:
        raise SystemExit(f"local corpus export already exists: {declaration}")
core_graphics.write_text(text + local_exports)
cl = ROOT / "GuestFrameworks/CoreLocation/CoreLocation+LC32Constants.m"
cl.write_text(cl.read_text() + "\n#include <math.h>\nconst CLLocationDistance kCLDistanceFilterNone = -1.0;\nconst CLLocationDegrees kCLHeadingFilterNone = -1.0;\nconst CLLocationAccuracy kCLLocationAccuracyHundredMeters = 100.0;\nconst CLLocationAccuracy kCLLocationAccuracyThreeKilometers = 3000.0;\nconst CLLocationCoordinate2D kCLLocationCoordinate2DInvalid = {INFINITY, INFINITY};\nCLLocationCoordinate2D CLLocationCoordinate2DMake(CLLocationDegrees latitude, CLLocationDegrees longitude) { return (CLLocationCoordinate2D){latitude, longitude}; }\nBOOL CLLocationCoordinate2DIsValid(CLLocationCoordinate2D c) { return isfinite(c.latitude) && isfinite(c.longitude) && fabs(c.latitude) <= 90.0 && fabs(c.longitude) <= 180.0; }\n")
av = ROOT / "GuestFrameworks/AVFoundation/AVFoundation.m"
av.write_text(av.read_text() + "\n#include <math.h>\nCGRect AVMakeRectWithAspectRatioInsideRect(CGSize aspect, CGRect bounds) { if(!(aspect.width > 0) || !(aspect.height > 0) || !(bounds.size.width > 0) || !(bounds.size.height > 0)) return CGRectZero; CGFloat scale = fmin(bounds.size.width / aspect.width, bounds.size.height / aspect.height); CGSize size = {aspect.width * scale, aspect.height * scale}; return (CGRect){{bounds.origin.x + (bounds.size.width - size.width) / 2, bounds.origin.y + (bounds.size.height - size.height) / 2}, size}; }\n")
cvtest = Path("build/corevideo-behavior.m")
cvtest.write_text("#import <CoreVideo/CoreVideo.h>\n#include <assert.h>\n#include <stdlib.h>\n#include <string.h>\nstatic int releases; static void released(void *ctx, const void *base){ assert(ctx==(void*)0x1234); releases++; free((void*)base); }\nint main(void){ CVPixelBufferRef p=0; assert(CVPixelBufferCreate(0,4,3,0x42475241,0,&p)==0); assert(p); assert(CVPixelBufferGetWidth(p)==4 && CVPixelBufferGetHeight(p)==3); assert(CVPixelBufferGetBytesPerRow(p)==16 && CVPixelBufferGetDataSize(p)==48); assert(CVPixelBufferLockBaseAddress(p,0)==0); void *b=CVPixelBufferGetBaseAddress(p); assert(b); memset(b,0xa5,48); assert(((unsigned char*)b)[47]==0xa5); assert(CVPixelBufferUnlockBaseAddress(p,0)==0); assert(CVPixelBufferUnlockBaseAddress(p,0)!=0); CFStringRef key=CFSTR(\"test\"); CFStringRef value=CFSTR(\"value\"); CVBufferSetAttachment(p,key,value,kCVAttachmentMode_ShouldPropagate); CVAttachmentMode mode=0; assert(CVBufferGetAttachment(p,key,&mode)==value && mode==kCVAttachmentMode_ShouldPropagate); CVBufferSetAttachment(p,key,NULL,0); assert(!CVBufferGetAttachment(p,key,NULL)); CVPixelBufferRelease(p); void *external=malloc(32); assert(CVPixelBufferCreateWithBytes(0,4,2,0x42475241,external,16,released,(void*)0x1234,0,&p)==0); CVPixelBufferRelease(p); assert(releases==1); return 0; }\n")
