#!/bin/sh
set -eu

usage() {
  cat >&2 <<'EOF'
usage:
  stage-liveexec32-layer.sh LIVEEXEC32.app LIVE_CONTAINER_DOCUMENTS [relative-name]
  stage-liveexec32-layer.sh LIVEEXEC32.app LIVE_CONTAINER_DOCUMENTS [relative-name] \
      --rootfs /path/to/armv7-rootfs --ipa /path/to/test.ipa

The extended form stages one deterministic compatibility test bundle:
  Documents/<relative-name>
  Documents/LiveExec32Runtime/rootfs
  Documents/LiveExec32Runtime/TestApps/<bundle-id>.app
  Documents/LiveExec32Runtime/launch.plist
  Documents/LiveExec32Runtime/Logs
EOF
}

if [ "$#" -lt 2 ]; then
  usage
  exit 64
fi

source_app=$1
documents_dir=$2
shift 2
relative_name=LiveExec32.app
rootfs=
ipa=

if [ "$#" -gt 0 ] && [ "${1#--}" = "$1" ]; then
  relative_name=$1
  shift
fi

while [ "$#" -gt 0 ]; do
  case "$1" in
    --rootfs)
      [ "$#" -ge 2 ] || { usage; exit 64; }
      rootfs=$2
      shift 2
      ;;
    --ipa)
      [ "$#" -ge 2 ] || { usage; exit 64; }
      ipa=$2
      shift 2
      ;;
    *)
      echo "error: unknown argument: $1" >&2
      usage
      exit 64
      ;;
  esac
done

if [ -z "$documents_dir" ] || [ "$documents_dir" = "/" ]; then
  echo "error: documents directory must not be empty or /" >&2
  exit 65
fi

case "$source_app" in
  *.app) ;;
  *) echo "error: source must be a .app bundle: $source_app" >&2; exit 65 ;;
esac
case "$relative_name" in
  /*|..|../*|*/..|*/../*|*//*)
    echo "error: relative-name must stay inside LiveContainer Documents: $relative_name" >&2
    exit 65
    ;;
esac
[ -d "$source_app" ] || { echo "error: LiveExec32 app bundle not found: $source_app" >&2; exit 66; }

mkdir -p "$documents_dir"
target_app=$documents_dir/$relative_name
rm -rf "$target_app"
cp -R "$source_app" "$target_app"
echo "staged $target_app"

# The two-argument form remains backward compatible.
if [ -z "$rootfs" ] && [ -z "$ipa" ]; then
  echo "set Developer Settings > LiveExec32 .app path to: $relative_name"
  exit 0
fi
if [ -z "$rootfs" ] || [ -z "$ipa" ]; then
  echo "error: --rootfs and --ipa must be supplied together" >&2
  exit 65
fi
[ -d "$rootfs" ] || { echo "error: ARMv7 rootfs not found: $rootfs" >&2; exit 66; }
[ -f "$ipa" ] || { echo "error: IPA not found: $ipa" >&2; exit 66; }

script_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
python3 "$script_dir/validate-armv7-ipa.py" "$ipa"

runtime=$documents_dir/LiveExec32Runtime
staged_rootfs=$runtime/rootfs
test_apps=$runtime/TestApps
logs=$runtime/Logs
work=$(mktemp -d "${TMPDIR:-/tmp}/lc32-stage.XXXXXX")
trap 'rm -rf "$work"' EXIT HUP INT TERM

rm -rf "$runtime"
mkdir -p "$runtime" "$test_apps" "$logs"
cp -R "$rootfs" "$staged_rootfs"
unzip -q "$ipa" -d "$work"
app=$(find "$work/Payload" -maxdepth 1 -type d -name '*.app' | head -n 1)
[ -n "$app" ] || { echo "error: IPA has no Payload/*.app" >&2; exit 65; }

bundle_id=$(python3 - "$app/Info.plist" <<'PY'
import plistlib, sys
with open(sys.argv[1], 'rb') as f:
    info = plistlib.load(f)
print(info['CFBundleIdentifier'])
PY
)
executable=$(python3 - "$app/Info.plist" <<'PY'
import plistlib, sys
with open(sys.argv[1], 'rb') as f:
    info = plistlib.load(f)
print(info['CFBundleExecutable'])
PY
)
staged_app=$test_apps/$bundle_id.app
cp -R "$app" "$staged_app"
ipa_sha=$(shasum -a 256 "$ipa" | awk '{print $1}')
exec_sha=$(shasum -a 256 "$staged_app/$executable" | awk '{print $1}')

python3 - "$runtime/launch.plist" "$relative_name" "$staged_rootfs" "$staged_app" "$executable" "$bundle_id" "$ipa_sha" "$exec_sha" "$logs" <<'PY'
import plistlib, sys
(output, layer, rootfs, app, executable, bundle_id, ipa_sha, exec_sha, logs) = sys.argv[1:]
manifest = {
    'schemaVersion': 1,
    'translationLayerRelativePath': layer,
    'guestRootFS': rootfs,
    'guestBundle': app,
    'guestExecutable': app + '/' + executable,
    'guestBundleIdentifier': bundle_id,
    'guestHome': app + '/LiveExec32Data',
    'logDirectory': logs,
    'ipaSHA256': ipa_sha,
    'executableSHA256': exec_sha,
    'arguments': [],
    'environment': {
        'LC32_BOOT_TRACE': '1',
        'LC32_STRICT_MACHO': '1',
    },
}
with open(output, 'wb') as f:
    plistlib.dump(manifest, f, fmt=plistlib.FMT_XML, sort_keys=True)
PY

mkdir -p "$staged_app/LiveExec32Data/Documents" \
         "$staged_app/LiveExec32Data/Library/Preferences" \
         "$staged_app/LiveExec32Data/Library/Caches" \
         "$staged_app/LiveExec32Data/tmp"

echo "staged ARMv7 test app: $staged_app"
echo "staged ARMv7 rootfs: $staged_rootfs"
echo "launch manifest: $runtime/launch.plist"
echo "boot logs: $logs"
echo "set Developer Settings > LiveExec32 .app path to: $relative_name"
