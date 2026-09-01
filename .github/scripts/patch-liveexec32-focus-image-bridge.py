#!/usr/bin/env python3
from pathlib import Path
ROOT=Path("build/LiveExec32")

def insert(path, anchor, addition, marker):
    path=ROOT/path; text=path.read_text()
    if marker in text: return
    if anchor not in text: raise SystemExit(f"missing anchor in {path}: {anchor[:80]!r}")
    path.write_text(text.replace(anchor,addition+anchor,1))

# Stable opcodes extend the existing versioned guest/host packet protocol.
bridge=ROOT/"GuestFrameworks/CoreGraphics/LC32CoreGraphicsBridge.h"
text=bridge.read_text(); anchor="    LC32CoreGraphicsOpContextStrokeEllipseInRect = 85,\n"
if "LC32CoreGraphicsOpImageCreate = 88" not in text:
    if anchor not in text: raise SystemExit("CoreGraphics opcode anchor missing")
    text=text.replace(anchor,anchor+"    LC32CoreGraphicsOpPathAddEllipseInRect = 86,\n    LC32CoreGraphicsOpDataProviderCreateWithData = 87,\n    LC32CoreGraphicsOpImageCreate = 88,\n",1)
    bridge.write_text(text)

guest=ROOT/"GuestFrameworks/CoreGraphics/CoreGraphics.m"
text=guest.read_text()
anchor="CGDataProviderRef CGDataProviderCreateWithURL(CFURLRef url) {\n"
addition="""CGDataProviderRef CGDataProviderCreateWithData(
        void *info, const void *data, size_t size,
        CGDataProviderReleaseDataCallback releaseData) {
    if(!data && size) return NULL;
    CGDataProviderRef provider = (CGDataProviderRef)LC32_CG_CALL(
        LC32CoreGraphicsOpDataProviderCreateWithData,
        LC32_CG_U32((uintptr_t)data), LC32_CG_U32(size));
    /* Native CoreGraphics owns a copy, so no ARM32 callback or pointer
     * escapes into the host. The original allocation can be released now. */
    if(releaseData) releaseData(info, data, size);
    return provider;
}

"""
if "CGDataProviderRef CGDataProviderCreateWithData(" not in text:
    if anchor not in text: raise SystemExit("data provider anchor missing")
    text=text.replace(anchor,addition+anchor,1)
anchor="void CGImageRelease(CGImageRef image) {\n"
addition="""CGImageRef CGImageCreate(size_t width, size_t height,
        size_t bitsPerComponent, size_t bitsPerPixel, size_t bytesPerRow,
        CGColorSpaceRef space, CGBitmapInfo bitmapInfo,
        CGDataProviderRef provider, const CGFloat *decode,
        bool shouldInterpolate, CGColorRenderingIntent intent) {
    if(!provider || !space) return NULL;
    return (CGImageRef)LC32_CG_CALL(LC32CoreGraphicsOpImageCreate,
        LC32_CG_U32(width), LC32_CG_U32(height),
        LC32_CG_U32(bitsPerComponent), LC32_CG_U32(bitsPerPixel),
        LC32_CG_U32(bytesPerRow), LC32_CG_HOST(space),
        LC32_CG_U32(bitmapInfo), LC32_CG_HOST(provider),
        LC32_CG_U32((uintptr_t)decode),
        LC32_CG_U32(shouldInterpolate), LC32_CG_U32(intent));
}

"""
if "CGImageRef CGImageCreate(size_t width" not in text:
    if anchor not in text: raise SystemExit("CGImage anchor missing")
    text=text.replace(anchor,addition+anchor,1)
anchor="void CGPathAddRect(CGMutablePathRef path,\n"
addition="""void CGPathAddEllipseInRect(CGMutablePathRef path,
        const CGAffineTransform *transform, CGRect rect) {
    if(!path) return;
    LC32_CG_CALL(LC32CoreGraphicsOpPathAddEllipseInRect,
        LC32_CG_HOST(path), LC32_CG_U32(transform != NULL),
        transform ? LC32_CG_F32(transform->a) : 0,
        transform ? LC32_CG_F32(transform->b) : 0,
        transform ? LC32_CG_F32(transform->c) : 0,
        transform ? LC32_CG_F32(transform->d) : 0,
        transform ? LC32_CG_F32(transform->tx) : 0,
        transform ? LC32_CG_F32(transform->ty) : 0,
        LC32_CG_F32(rect.origin.x), LC32_CG_F32(rect.origin.y),
        LC32_CG_F32(rect.size.width), LC32_CG_F32(rect.size.height));
}

"""
if "void CGPathAddEllipseInRect(" not in text:
    if anchor not in text: raise SystemExit("CGPath anchor missing")
    text=text.replace(anchor,addition+anchor,1)
guest.write_text(text)

host=ROOT/"HostFrameworks/CoreGraphics/CoreGraphics.mm"
text=host.read_text(); anchor="        case LC32CoreGraphicsOpBitmapContextCreate: {\n"
addition="""        case LC32CoreGraphicsOpDataProviderCreateWithData: {
            if(!RequireCoreGraphicsSlots(call, 2)) return 0;
            const u32 guestData = SlotU32(call, 0);
            const size_t size = SlotU32(call, 1);
            if((!guestData && size) || size > kMaximumBitmapBytes ||
               static_cast<uint64_t>(guestData) + size >
                   static_cast<uint64_t>(UINT32_MAX) + 1) return 0;
            std::vector<uint8_t> bytes(size);
            if(size && Dynarmic_mem_1read(guestData, size,
                    reinterpret_cast<char *>(bytes.data())) != 0) return 0;
            CFDataRef data = CFDataCreate(kCFAllocatorDefault,
                bytes.data(), static_cast<CFIndex>(bytes.size()));
            if(!data) return 0;
            CGDataProviderRef provider = CGDataProviderCreateWithCFData(data);
            CFRelease(data);
            return provider ? LC32GuestObjectForOwnedHostObject(provider) : 0;
        }
        case LC32CoreGraphicsOpImageCreate: {
            if(!RequireCoreGraphicsSlots(call, 11)) return 0;
            CGColorSpaceRef colorSpace =
                SlotHostObject<CGColorSpaceRef>(call, 5);
            CGDataProviderRef provider =
                SlotHostObject<CGDataProviderRef>(call, 7);
            if(!colorSpace || !provider) return 0;
            std::vector<CGFloat> decodeValues;
            const CGFloat *decode = nullptr;
            const u32 guestDecode = SlotU32(call, 8);
            if(guestDecode) {
                const size_t components =
                    CGColorSpaceGetNumberOfComponents(colorSpace);
                if(!components || components > kMaximumColorComponents ||
                   !ReadGuestCGFloatArray(guestDecode, components * 2, false,
                       decodeValues, decode)) return 0;
            }
            CGImageRef image = CGImageCreate(SlotU32(call, 0),
                SlotU32(call, 1), SlotU32(call, 2), SlotU32(call, 3),
                SlotU32(call, 4), colorSpace, SlotU32(call, 6), provider,
                decode, SlotU32(call, 9),
                static_cast<CGColorRenderingIntent>(SlotU32(call, 10)));
            return image ? LC32GuestObjectForOwnedHostObject(image) : 0;
        }
        case LC32CoreGraphicsOpPathAddEllipseInRect: {
            if(!RequireCoreGraphicsSlots(call, 12)) return 0;
            CGMutablePathRef path =
                SlotHostObject<CGMutablePathRef>(call, 0);
            CGAffineTransform transformStorage;
            const CGAffineTransform *transform = nullptr;
            if(!path || !SlotOptionalTransform(call, 1, 2,
                    transformStorage, transform)) return 0;
            CGPathAddEllipseInRect(path, transform, SlotRect(call, 8));
            return 0;
        }
"""
if "case LC32CoreGraphicsOpImageCreate:" not in text:
    if anchor not in text: raise SystemExit("host dispatcher anchor missing")
    text=text.replace(anchor,addition+anchor,1)
host.write_text(text)
print("patched typed image/provider/path CoreGraphics bridge")
