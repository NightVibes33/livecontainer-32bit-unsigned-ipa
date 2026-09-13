from pathlib import Path
root = Path('build/LiveExec32')
hp = root / 'GuestFrameworks/CoreGraphics/LC32CoreGraphicsBridge.h'
gp = root / 'GuestFrameworks/CoreGraphics/CoreGraphics.m'
sp = root / 'HostFrameworks/CoreGraphics/CoreGraphics.mm'
h, g, s = hp.read_text(), gp.read_text(), sp.read_text()
a = '    LC32CoreGraphicsOpContextShowGlyphsAtPoint = 114,\n'
if 'LC32CoreGraphicsOpPathAddEllipseInRect' not in h:
    if h.count(a) != 1: raise SystemExit('unexpected opcode anchor')
    h = h.replace(a, a + '    LC32CoreGraphicsOpPathAddEllipseInRect = 115,\n', 1)
a = 'void CGColorRelease(CGColorRef color) {\n    if(color) CFRelease(color);\n}\n'
if 'CGColorRef CGColorRetain' not in g:
    if g.count(a) != 1: raise SystemExit('unexpected color anchor')
    g = g.replace(a, 'CGColorRef CGColorRetain(CGColorRef color) {\n    return color ? (CGColorRef)CFRetain(color) : NULL;\n}\n\n' + a, 1)
a = 'CGPathRef CGPathCreateCopy(CGPathRef path) {\n'
if 'void CGPathAddEllipseInRect' not in g:
    if g.count(a) != 1: raise SystemExit('unexpected path anchor')
    body = '''void CGPathAddEllipseInRect(CGMutablePathRef path,
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

'''
    g = g.replace(a, body + a, 1)
a = '        case LC32CoreGraphicsOpContextSetStrokeColorSpace: {\n'
if 'case LC32CoreGraphicsOpPathAddEllipseInRect:' not in s:
    if s.count(a) != 1: raise SystemExit('unexpected host anchor')
    body = '''        case LC32CoreGraphicsOpPathAddEllipseInRect: {
            if(!RequireCoreGraphicsSlots(call, 12)) return 0;
            CGMutablePathRef path = SlotHostObject<CGMutablePathRef>(call, 0);
            if(!path) return 0;
            CGAffineTransform transformStorage;
            const CGAffineTransform *transform;
            if(!SlotOptionalTransform(call, 1, 2, transformStorage, transform)) return 0;
            CGPathAddEllipseInRect(path, transform, SlotRect(call, 8));
            return 1;
        }
'''
    s = s.replace(a, body + a, 1)
hp.write_text(h); gp.write_text(g); sp.write_text(s)
