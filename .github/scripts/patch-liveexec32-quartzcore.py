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
path.write_text(source)
