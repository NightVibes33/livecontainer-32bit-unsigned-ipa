from pathlib import Path

path = Path("runtime/LC32DarwinSyscalls.cpp")
text = path.read_text()
old = """            if ((flags & ~supported) != 0 ||
                (flags & kMsAsync) != 0 && (flags & kMsSync) != 0) {
"""
new = """            if ((flags & ~supported) != 0 ||
                ((flags & kMsAsync) != 0 && (flags & kMsSync) != 0)) {
"""
if text.count(old) != 1:
    raise SystemExit("expected one msync flag expression")
path.write_text(text.replace(old, new, 1))
Path("tools/apply_vm_advisory.py").unlink()
