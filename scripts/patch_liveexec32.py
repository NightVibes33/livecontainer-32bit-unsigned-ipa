#!/usr/bin/env python3
from pathlib import Path
import sys


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if old not in text:
        raise SystemExit(f"{label}: expected source block was not found")
    return text.replace(old, new, 1)


def main() -> None:
    root = Path(sys.argv[1] if len(sys.argv) > 1 else "build/LiveExec32")
    path = root / "main.cpp"
    source = path.read_text()

    source = replace_once(
        source,
        "#include <string.h>\n",
        "#include <string.h>\n#include <limits.h>\n#include <string>\n",
        "includes",
    )

    source = replace_once(
        source,
        '// /var/mobile/Documents/TrollExperiments/CProjects/dynarmic\n#define DEFAULT_ROOT_PATH "/private/var/mobile/Documents/TrollExperiments/CProjects/dynarmic/iOS10RAMDisk"\n#define DEFAULT_DYLD_PATH DEFAULT_ROOT_PATH "/usr/lib/dyld"\n',
        '''static std::string LC32RuntimeRoot(const char *argv0) {
  const char *configured = getenv("ROOT_PATH");
  if(configured && configured[0]) {
    return configured;
  }

  const char *lcHome = getenv("LC_HOME_PATH");
  if(lcHome && lcHome[0]) {
    return std::string(lcHome) + "/Documents/LiveExec32Runtime";
  }

  char resolved[PATH_MAX] = {0};
  if(argv0 && realpath(argv0, resolved)) {
    char *dir = dirname(resolved);
    return std::string(dir) + "/RuntimeRoot";
  }
  return "RuntimeRoot";
}
''',
        "runtime root constants",
    )

    source = replace_once(
        source,
        '''  Dynarmic_nativeInitialize();
  u32 execAddr = Dynarmic_map_file(false, 0x11000000, execPath);

  setenv("DYLD_PATH", DEFAULT_DYLD_PATH, 0);
  const char *dyldPath = getenv("DYLD_PATH");
  printf("Loading dyld at DYLD_PATH %s\\n", dyldPath);
  Dynarmic_map_file(true, 0x10000000, dyldPath);
  printf("entry point: 0x%x\\n", threadHandle.jit->Regs()[15]);

  setenv("ROOT_PATH", DEFAULT_ROOT_PATH, 0);
  const char *rootPath = getenv("ROOT_PATH");
''',
        '''  std::string runtimeRoot = LC32RuntimeRoot(argv[0]);
  std::string runtimeDyld = runtimeRoot + "/usr/lib/dyld";
  setenv("ROOT_PATH", runtimeRoot.c_str(), 1);
  setenv("DYLD_PATH", runtimeDyld.c_str(), 1);

  if(access(runtimeDyld.c_str(), R_OK) != 0) {
    fprintf(stderr, "LC32_RUNTIME_ROOT_MISSING: expected readable dyld at %s\\n", runtimeDyld.c_str());
    fprintf(stderr, "Install the extracted 32-bit runtime at Documents/LiveExec32Runtime.\\n");
    return 78;
  }

  if(!Dynarmic_nativeInitialize()) {
    fprintf(stderr, "LC32_BACKEND_INIT_FAILED: the ARMv7 execution backend could not initialize.\\n");
    return 70;
  }
  u32 execAddr = Dynarmic_map_file(false, 0x11000000, execPath);

  const char *dyldPath = getenv("DYLD_PATH");
  printf("Loading dyld at DYLD_PATH %s\\n", dyldPath);
  Dynarmic_map_file(true, 0x10000000, dyldPath);
  printf("entry point: 0x%x\\n", threadHandle.jit->Regs()[15]);

  const char *rootPath = getenv("ROOT_PATH");
''',
        "runtime initialization",
    )

    path.write_text(source)
    print(f"patched {path}")


if __name__ == "__main__":
    main()
