#!/usr/bin/env python3
from pathlib import Path
p = Path('runtime/tests/LC32DarwinSyscallsTests.cpp')
s = p.read_text()
s = s.replace('    uint32_t memorySize = 0;\n', '    uint32_t hostMemorySize = 0;\n', 1)
s = s.replace('    std::memcpy(&memorySize, lowMemory.data() + kMachMessageAddress + 48u, 4u);\n', '    std::memcpy(&hostMemorySize, lowMemory.data() + kMachMessageAddress + 48u, 4u);\n', 1)
s = s.replace('    assert(memorySize == 1024u * 1024u * 1024u);\n', '    assert(hostMemorySize == 1024u * 1024u * 1024u);\n', 1)
p.write_text(s)
