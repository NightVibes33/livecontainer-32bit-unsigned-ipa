#!/usr/bin/env python3
from pathlib import Path

path = Path("tools/apply_readlink_lstat.py")
text = path.read_text()
start = text.index('header_needle = """')
end = text.index('\nheader_path.write_text', start)
replacement = '''header_needle = "    int allocateGuestFd(int hostFd, uint32_t openFlags, uint32_t descriptorFlags);\\n"
header_replacement = """    bool resolveGuestPathNoFollow(const std::string& guestPath,
                                   std::string& hostPath,
                                   int& errorNumber) const;
    int allocateGuestFd(int hostFd, uint32_t openFlags, uint32_t descriptorFlags);
"""
if header.count(header_needle) != 1:
    raise SystemExit("no-follow header insertion point not unique")'''
path.write_text(text[:start] + replacement + text[end:])
