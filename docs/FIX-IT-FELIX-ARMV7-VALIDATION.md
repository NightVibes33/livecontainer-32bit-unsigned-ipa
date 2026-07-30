# Fix It Felix ARMv7 compatibility target

This branch uses the user-supplied `Fix It Felix.ipa` as the first full-app validation target. The IPA itself is not committed.

## Verified static identity

- IPA SHA-256: `7a5e925f98ca34939c74173b7819df602ed8ca3687918aa7951418ab3d4e1c67`
- Executable SHA-256: `23fe9e657c9d1c7364808c6f8f22e3af924f88e07fa52a6a7eecbcddbc222512`
- Bundle identifier: `com.disney.FixItFelixJr`
- Bundle version: `1.4`
- Executable: `FixItFelixJr`
- Architecture: ARMv7-only Mach-O
- Minimum iOS: 4.3
- SDK: iPhoneOS 6.1
- Device families: iPhone and iPad
- Encryption requirement: `cryptid == 0`

Run the validator before every device test:

```sh
python3 tools/validate-armv7-ipa.py \
  --expect-sha256 7a5e925f98ca34939c74173b7819df602ed8ca3687918aa7951418ab3d4e1c67 \
  "/path/to/Fix It Felix.ipa"
```

## Stage a reproducible runtime bundle

```sh
tools/stage-liveexec32-layer.sh \
  /path/to/LiveExec32.app \
  /path/to/LiveContainer/Documents \
  LiveExec32.app \
  --rootfs /path/to/armv7-rootfs \
  --ipa "/path/to/Fix It Felix.ipa"
```

This produces `Documents/LiveExec32Runtime/launch.plist` with explicit paths for the translation layer, root filesystem, guest bundle, guest executable, guest home, hashes, environment, and logs.

## Runtime proof gates

Do not describe the game as working until all gates below are captured on a physical ARM64 device:

1. `guest-dyld-entered`
2. `main-executable-mapped`
3. `dependent-images-loaded`
4. `initializers-complete`
5. `objc-images-registered`
6. `main-entered`
7. `uiapplicationmain-entered`
8. `window-created`
9. `first-frame-presented`
10. `touch-event-received`
11. `audio-callback-received`
12. `gameplay-stable-300s`
13. `save-write-confirmed`

Every failed gate must include the last guest PC, translated block address, loaded image list, missing symbol or syscall, and the generated crash log. Static validation proves only that the IPA is an appropriate ARMv7 test input.

## Next runtime change

LiveContainer must export the generated manifest path before opening LiveExec32:

```text
LC32_LAUNCH_MANIFEST=<LiveContainer Documents>/LiveExec32Runtime/launch.plist
```

LiveExec32 then needs to parse that manifest and emit the proof-gate events above. The existing path substitution alone cannot prove a UIKit application booted.
