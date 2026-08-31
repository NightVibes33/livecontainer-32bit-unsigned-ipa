#!/bin/bash
set -euxo pipefail

ROOTFS=${1:?guest RootFS path is required}
VERSION=1.17
ARCHIVE="$RUNNER_TEMP/libiconv-$VERSION.tar.gz"
SOURCE="$RUNNER_TEMP/libiconv-$VERSION"
URL="https://ftp.gnu.org/pub/gnu/libiconv/libiconv-$VERSION.tar.gz"
SHA256=8f74213b56238c85a50a5329f77e06198771e70dd9a739779f4c02f65d971313
SDKROOT=$(cd build/LiveExec32/tmp/iPhoneOS10.3.sdk && pwd)
CC=$(xcrun --sdk iphoneos --find clang)

curl --fail --location --retry 3 --output "$ARCHIVE" "$URL"
echo "$SHA256  $ARCHIVE" | shasum -a 256 -c -
rm -rf "$SOURCE"
tar -xzf "$ARCHIVE" -C "$RUNNER_TEMP"

(
  cd "$SOURCE"
  env \
    CC="$CC" \
    CFLAGS="-arch armv7s -isysroot $SDKROOT -miphoneos-version-min=10.3 -O2" \
    LDFLAGS="-arch armv7s -isysroot $SDKROOT -miphoneos-version-min=10.3 -Wl,-alias,_libiconv,_iconv,-alias,_libiconv_open,_iconv_open,-alias,_libiconv_close,_iconv_close" \
    ./configure \
      --host=arm-apple-darwin \
      --prefix=/usr \
      --disable-static \
      --enable-shared
)
gmake -C "$SOURCE/libcharset/lib" -j"$(sysctl -n hw.logicalcpu)"
install -m 0644 "$SOURCE/libcharset/include/localcharset.h" "$SOURCE/include/localcharset.h"
gmake -C "$SOURCE/lib" -j"$(sysctl -n hw.logicalcpu)"

install -d -m 0755 "$ROOTFS/usr/lib"
# ZIP-based IPA installation materializes guest symlinks as tiny text files.
# Felix links this compatibility name directly, so store a real Mach-O there.
install -m 0755 "$ROOTFS/usr/lib/libstdc++.6.0.9.dylib" "$RUNNER_TEMP/libstdc++.6.dylib"
rm -f "$ROOTFS/usr/lib/libstdc++.6.dylib"
install -m 0755 "$RUNNER_TEMP/libstdc++.6.dylib" "$ROOTFS/usr/lib/libstdc++.6.dylib"
file "$ROOTFS/usr/lib/libstdc++.6.dylib" | grep Mach-O
test "$(otool -D "$ROOTFS/usr/lib/libstdc++.6.dylib" | tail -n 1)" = /usr/lib/libstdc++.6.dylib
install -m 0755 "$SOURCE/lib/.libs/libiconv.2.dylib" \
  "$ROOTFS/usr/lib/libiconv.2.dylib"
install -m 0755 "$SOURCE/libcharset/lib/.libs/libcharset.1.dylib" \
  "$ROOTFS/usr/lib/libcharset.1.dylib"
ln -sfn libiconv.2.dylib "$ROOTFS/usr/lib/libiconv.dylib"
ln -sfn libcharset.1.dylib "$ROOTFS/usr/lib/libcharset.dylib"

file "$ROOTFS/usr/lib/libiconv.2.dylib" | grep arm_v7s
file "$ROOTFS/usr/lib/libcharset.1.dylib" | grep arm_v7s
test "$(otool -D "$ROOTFS/usr/lib/libiconv.2.dylib" | tail -n 1)" = /usr/lib/libiconv.2.dylib
test "$(otool -D "$ROOTFS/usr/lib/libcharset.1.dylib" | tail -n 1)" = /usr/lib/libcharset.1.dylib
ICONV_EXPORTS=$(nm -gU "$ROOTFS/usr/lib/libiconv.2.dylib")
for symbol in _iconv _iconv_open _iconv_close; do
  grep -F " $symbol" <<< "$ICONV_EXPORTS"
done
otool -L "$ROOTFS/usr/lib/libiconv.2.dylib"
