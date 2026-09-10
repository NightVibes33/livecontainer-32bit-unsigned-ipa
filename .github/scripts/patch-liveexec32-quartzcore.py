from pathlib import Path

path = Path("build/LiveExec32/GuestFrameworks/QuartzCore/QuartzCore.m")
source = path.read_text()

# Nightly LiveExec32 now provides kCATransition, the linear/nearest/trilinear
# filters, and the CATransform3D affine helpers itself. Keep this migrated
# overlay strictly additive so QuartzCore does not link duplicate symbols.
declaration_anchor = "LC32_CONST_STR_DECL(NSString * const kCATransactionDisableActions)"
initializer_anchor = "    LC32_CONST_STR_INIT(kCATransactionDisableActions);"
for anchor in (declaration_anchor, initializer_anchor):
    if source.count(anchor) != 1:
        raise SystemExit(f"expected exactly one QuartzCore anchor: {anchor}")

# kCAFilterLanczos is still absent from the pinned nightly runtime and is
# required by the compatibility corpus.
if "LC32_CONST_STR_DECL(NSString * const kCAFilterLanczos)" not in source:
    source = source.replace(
        declaration_anchor,
        declaration_anchor + "\n\nLC32_CONST_STR_DECL(NSString * const kCAFilterLanczos)",
        1,
    )

if "LC32_CONST_STR_INIT(kCAFilterLanczos);" not in source:
    source = source.replace(
        initializer_anchor,
        initializer_anchor + "\n\n    LC32_CONST_STR_INIT(kCAFilterLanczos);",
        1,
    )

path.write_text(source)
