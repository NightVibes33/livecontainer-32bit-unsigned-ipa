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
(corevideo / "CoreVideo.m").write_text("""#import <CoreVideo/CoreVideo.h>
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
CVReturn CVPixelBufferLockBaseAddress(CVPixelBufferRef b, CVPixelBufferLockFlags f) { return b ? kCVReturnSuccess : kCVReturnInvalidArgument; }
CVReturn CVPixelBufferUnlockBaseAddress(CVPixelBufferRef b, CVPixelBufferLockFlags f) { return b ? kCVReturnSuccess : kCVReturnInvalidArgument; }
void *CVPixelBufferGetBaseAddress(CVPixelBufferRef b) { return NULL; }
void *CVPixelBufferGetBaseAddressOfPlane(CVPixelBufferRef b, size_t p) { return NULL; }
size_t CVPixelBufferGetBytesPerRow(CVPixelBufferRef b) { return 0; }
size_t CVPixelBufferGetBytesPerRowOfPlane(CVPixelBufferRef b, size_t p) { return 0; }
size_t CVPixelBufferGetDataSize(CVPixelBufferRef b) { return 0; }
size_t CVPixelBufferGetHeight(CVPixelBufferRef b) { return 0; }
size_t CVPixelBufferGetWidth(CVPixelBufferRef b) { return 0; }
size_t CVPixelBufferGetPlaneCount(CVPixelBufferRef b) { return 0; }
CFTypeRef CVBufferGetAttachment(CVBufferRef b, CFStringRef k, CVAttachmentMode *m) { return NULL; }
void CVBufferSetAttachment(CVBufferRef b, CFStringRef k, CFTypeRef v, CVAttachmentMode m) {}
CVReturn CVPixelBufferCreate(CFAllocatorRef a, size_t w, size_t h, OSType f, CFDictionaryRef d, CVPixelBufferRef *o) { if(o) *o = NULL; return kCVReturnUnsupported; }
CVReturn CVPixelBufferCreateWithBytes(CFAllocatorRef a, size_t w, size_t h, OSType f, void *base, size_t row, CVPixelBufferReleaseBytesCallback cb, void *ctx, CFDictionaryRef d, CVPixelBufferRef *o) { if(o) *o=NULL; if(cb) cb(ctx,base); return kCVReturnUnsupported; }
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

bool CGSizeEqualToSize(CGSize left, CGSize right) {
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
    "bool CGAffineTransformEqualToTransform(", "bool CGSizeEqualToSize(",
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
