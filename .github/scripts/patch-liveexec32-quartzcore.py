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
    declaration_anchor + "\n\nLC32_CONST_STR_DECL(NSString * const kCATransition)",
)
source = source.replace(
    initializer_anchor,
    initializer_anchor + "\n\n    LC32_CONST_STR_INIT(kCATransition);",
)
path.write_text(source)
