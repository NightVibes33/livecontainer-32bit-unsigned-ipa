#!/bin/sh
set -eu

usage() {
  echo "usage: $0 /path/to/LiveContainer.app output.ipa" >&2
}

if [ "$#" -ne 2 ]; then
  usage
  exit 64
fi

app_path=$1
output_ipa=$2

case "$app_path" in
  *.app) ;;
  *)
    echo "error: first argument must be a .app bundle: $app_path" >&2
    exit 65
    ;;
esac

case "$output_ipa" in
  *.ipa) ;;
  *)
    echo "error: output must end with .ipa: $output_ipa" >&2
    exit 65
    ;;
esac

if [ ! -d "$app_path" ]; then
  echo "error: app bundle not found: $app_path" >&2
  exit 66
fi

if [ ! -f "$app_path/Info.plist" ]; then
  echo "error: missing Info.plist in app bundle: $app_path" >&2
  exit 67
fi

workdir=$(mktemp -d)
trap 'rm -rf "$workdir"' EXIT HUP INT TERM

mkdir -p "$workdir/Payload"
cp -R "$app_path" "$workdir/Payload/"

find "$workdir/Payload" -type f \( -name embedded.mobileprovision -o -name '*.xcent' \) -delete

rm -f "$output_ipa"
(
  cd "$workdir"
  zip -qry "$output_ipa" Payload -x '._*' -x '.DS_Store' -x '__MACOSX/*'
)

mv "$workdir/$output_ipa" "$output_ipa"
echo "created $output_ipa"
