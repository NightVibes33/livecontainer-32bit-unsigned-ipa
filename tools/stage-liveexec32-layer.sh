#!/bin/sh
set -eu

usage() {
  echo "usage: $0 /path/to/LiveExec32.app /path/to/LiveContainer/Documents [relative-name]" >&2
  echo "example: $0 .theos/obj/debug/LiveExec32.app /var/mobile/Containers/Data/Application/<UUID>/Documents" >&2
}

if [ "$#" -lt 2 ] || [ "$#" -gt 3 ]; then
  usage
  exit 64
fi

source_app=$1
documents_dir=$2
relative_name=${3:-LiveExec32.app}

if [ -z "$documents_dir" ] || [ "$documents_dir" = "/" ]; then
  echo "error: documents directory must not be empty or /" >&2
  exit 65
fi

target_app=$documents_dir/$relative_name

case "$source_app" in
  *.app) ;;
  *)
    echo "error: source must be a .app bundle: $source_app" >&2
    exit 65
    ;;
esac

case "$relative_name" in
  /*|..|../*|*/..|*/../*|*//*)
    echo "error: relative-name must stay inside LiveContainer Documents: $relative_name" >&2
    exit 65
    ;;
esac

if [ ! -d "$source_app" ]; then
  echo "error: LiveExec32 app bundle not found: $source_app" >&2
  exit 66
fi

mkdir -p "$documents_dir"
rm -rf "$target_app"
cp -R "$source_app" "$target_app"

echo "staged $target_app"
echo "set Developer Settings > LiveExec32 .app path to: $relative_name"
