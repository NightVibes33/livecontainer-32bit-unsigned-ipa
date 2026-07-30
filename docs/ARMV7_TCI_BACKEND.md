# No-JIT ARMv7 runtime

## Goal

Run decrypted ARMv7 iOS binaries without an externally enabled JIT session and without creating writable+executable native code pages.

## Why the current backend cannot satisfy this

The bundled LiveExec32 backend uses Dynarmic, which dynamically recompiles ARMv7 instructions into ARM64 host code. Bypassing LiveContainer's launch check does not remove Dynarmic's executable-memory requirement.

## Selected backend direction

Use QEMU TCG with the TCI (Tiny Code Interpreter) host backend. TCI executes TCG bytecode in an interpreter rather than emitting native host instructions.

The runtime must be built as an embedded library rather than a standalone QEMU process.

## Runtime boundary

`LCARMv7Runtime` owns:

- ARMv7/Thumb CPU state and execution.
- Guest virtual memory and Mach-O mappings.
- Darwin syscall dispatch into controlled host wrappers.
- Guest dyld and library loading.
- Objective-C message and object proxying.
- UIKit/Foundation/OpenGL ES compatibility calls.

LiveContainer owns:

- IPA import and architecture detection.
- Per-app data containers.
- App selection, lifecycle, input and display surfaces.
- Crash-report collection and compatibility metadata.

## Milestones

1. Build an arm-softmmu/user-mode TCI library for arm64 iOS with no generated executable pages.
2. Execute ARM and Thumb arithmetic/branch smoke-test binaries inside the host app.
3. Load a decrypted 32-bit Mach-O and reach its entry point.
4. Add Darwin syscall, pthread and dyld compatibility required by a command-line iOS binary.
5. Proxy Objective-C runtime calls between 32-bit guest objects and 64-bit host objects.
6. Add UIKit, Foundation, CoreGraphics, OpenGL ES and audio shims incrementally against validated IPAs.

## Acceptance checks

A build is not described as supporting no-JIT 32-bit apps until all of these pass on a real non-jailbroken device:

- `CS_DEBUGGED` is not set.
- No JIT provider is attached.
- No memory mapping is simultaneously writable and executable.
- ARM and Thumb smoke tests pass.
- A decrypted 32-bit Mach-O reaches its entry point.
- At least one UIKit IPA renders and accepts touch input.

## Current status

Architecture selected. No-JIT 32-bit runtime is not yet implemented. Main-branch 64-bit JIT-less behavior remains separate from this work.
