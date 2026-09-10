from pathlib import Path

path = Path("build/LiveExec32/GuestFrameworks/Security/Security.m")
if not path.is_file():
    raise SystemExit("nightly Security source is missing")

# Pinned nightly LiveExec32 now supplies the legacy Security constants from
# Security.m and its generated constant sources. This migration hook remains
# intentionally validation-only so it cannot introduce duplicate exports.
source = path.read_text()
for symbol in (
    "kSecAttrAccessible",
    "kSecAttrService",
):
    if symbol not in source:
        raise SystemExit(f"expected nightly Security baseline symbol: {symbol}")
