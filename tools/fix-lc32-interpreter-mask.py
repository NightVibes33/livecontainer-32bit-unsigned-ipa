#!/usr/bin/env python3
from pathlib import Path

path = Path('runtime/LC32Interpreter.cpp')
text = path.read_text()
old = '(insn & 0x0fb00000u) == 0x03000000u || (insn & 0x0fb00000u) == 0x03400000u'
new = '(insn & 0x0ff00000u) == 0x03000000u || (insn & 0x0ff00000u) == 0x03400000u'
if old not in text:
    raise SystemExit('MOVW/MOVT mask anchor not found')
path.write_text(text.replace(old, new, 1))
print('fixed MOVW/MOVT decode mask')
