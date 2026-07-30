# Fix It Felix ARMv7 Compatibility Status

## Target

Run the supplied decrypted ARMv7-only `Fix It Felix.ipa` through LiveExec32 on a 64-bit iOS device and prove real gameplay, not merely successful installation.

## Verified target identity

- Bundle identifier: `com.disney.FixItFelixJr`
- Executable: `FixItFelixJr`
- Architecture: ARMv7 only
- Minimum OS: iOS 4.3
- SDK: iPhoneOS 6.1
- IPA SHA-256: `7a5e925f98ca34939c74173b7819df602ed8ca3687918aa7951418ab3d4e1c67`
- Executable SHA-256: `23fe9e657c9d1c7364808c6f8f22e3af924f88e07fa52a6a7eecbcddbc222512`

## Implemented in this branch

- Strict ARMv7 IPA validation.
- Rejection of ARM64 or encrypted test executables.
- Deterministic staging of LiveExec32, rootfs, guest app, guest home and logs.
- Generated launch manifest with explicit environment and proof gates.
- Runtime-package verification for guest dyld, UIKit, Foundation, CoreFoundation, CoreGraphics, QuartzCore, OpenGLES and AudioToolbox.
- SHA-256 integrity validation of the staged executable.
- Guest data moved outside the application bundle.

## Repository boundary

This repository does not contain LiveExec32 source. It consumes a built `LiveExec32.app`. Therefore the following work cannot truthfully be completed only by editing this repository:

- Parse and execute the launch manifest inside LiveExec32.
- Add guest dyld boot-stage events.
- Implement missing syscalls.
- Implement Objective-C host/guest bridging.
- Implement UIKit, OpenGL ES, input and audio bridging.

Those changes require a source fork of `LiveContainer/LiveExec32`, followed by rebuilding `LiveExec32.app` and updating this repository to consume that build.

## Required runtime proof gates

A run is considered proven only when the device log records all of these in order:

1. `manifest_loaded`
2. `rootfs_validated`
3. `guest_dyld_started`
4. `guest_executable_mapped`
5. `dependent_images_loaded`
6. `initializers_completed`
7. `main_reached`
8. `uiapplicationmain_reached`
9. `first_frame_presented`
10. `touch_received`
11. `audio_started`
12. `save_written`

Passing CI or building an IPA is not proof that the ARMv7 game runs.
