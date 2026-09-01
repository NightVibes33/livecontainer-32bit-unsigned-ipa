from pathlib import Path

path = Path("build/LiveExec32/GuestFrameworks/QuartzCore/QuartzCore.m")
source = path.read_text()
declaration_anchor = "LC32_CONST_STR_DECL(NSString * const kCATransactionDisableActions)"
initializer_anchor = "    LC32_CONST_STR_INIT(kCATransactionDisableActions);"
for anchor in (declaration_anchor, initializer_anchor):
    if source.count(anchor) != 1:
        raise SystemExit(f"expected exactly one QuartzCore anchor: {anchor}")
source = source.replace(
    declaration_anchor,
    declaration_anchor + """\n\nLC32_CONST_STR_DECL(NSString * const kCATransition)\nLC32_CONST_STR_DECL(NSString * const kCAFilterLinear)\nLC32_CONST_STR_DECL(NSString * const kCAFilterNearest)\nLC32_CONST_STR_DECL(NSString * const kCAFilterTrilinear)\nLC32_CONST_STR_DECL(NSString * const kCAFilterLanczos)""",
)
source = source.replace(
    initializer_anchor,
    initializer_anchor + """\n\n    LC32_CONST_STR_INIT(kCATransition);\n    LC32_CONST_STR_INIT(kCAFilterLinear);\n    LC32_CONST_STR_INIT(kCAFilterNearest);\n    LC32_CONST_STR_INIT(kCAFilterTrilinear);\n    LC32_CONST_STR_INIT(kCAFilterLanczos);""",
)
transform_marker = "bool CATransform3DIsAffine(CATransform3D transform)"
if transform_marker not in source:
    source += r"""

bool CATransform3DIsAffine(CATransform3D transform) {
    return transform.m13 == 0 && transform.m14 == 0 &&
        transform.m23 == 0 && transform.m24 == 0 &&
        transform.m31 == 0 && transform.m32 == 0 &&
        transform.m33 == 1 && transform.m34 == 0 &&
        transform.m43 == 0 && transform.m44 == 1;
}

CATransform3D CATransform3DMakeAffineTransform(CGAffineTransform affine) {
    CATransform3D transform = CATransform3DIdentity;
    transform.m11 = affine.a;
    transform.m12 = affine.b;
    transform.m21 = affine.c;
    transform.m22 = affine.d;
    transform.m41 = affine.tx;
    transform.m42 = affine.ty;
    return transform;
}

CGAffineTransform CATransform3DGetAffineTransform(CATransform3D transform) {
    return CGAffineTransformMake(transform.m11, transform.m12,
        transform.m21, transform.m22, transform.m41, transform.m42);
}
"""

path.write_text(source)
