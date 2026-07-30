#!/usr/bin/env python3
from pathlib import Path
hpp_path = Path('runtime/LC32DarwinSyscalls.hpp')
cpp_path = Path('runtime/LC32DarwinSyscalls.cpp')
hpp = hpp_path.read_text()
cpp = cpp_path.read_text()
if '#include <unordered_set>' not in hpp:
    hpp = hpp.replace('#include <unordered_map>\n', '#include <unordered_map>\n#include <unordered_set>\n', 1)
old_member = '    std::unordered_map<std::string, uint64_t> notifyNameIds_;\n    uint64_t nextNotifyNameId_ = 1u;\n'
new_member = '    std::unordered_map<std::string, uint64_t> notifyNameIds_;\n    std::unordered_set<int32_t> canceledNotifyTokens_;\n    uint64_t nextNotifyNameId_ = 1u;\n'
if 'canceledNotifyTokens_' not in hpp:
    if old_member not in hpp: raise SystemExit('member anchor missing')
    hpp = hpp.replace(old_member, new_member, 1)
old_check = '''                if (it == notifyRegistrations_.end()) {
                    queueInlineReply(0, {0u, kNotifyInvalidToken});
                } else {
'''
new_check = '''                if (it == notifyRegistrations_.end()) {
                    const uint32_t status = canceledNotifyTokens_.count(token) != 0u
                                                ? kNotifyInvalidToken
                                                : kNotifyOk;
                    queueInlineReply(0, {0u, status});
                } else {
'''
if old_check not in cpp: raise SystemExit('check anchor missing')
cpp = cpp.replace(old_check, new_check, 1)
old_register = '                notifyRegistrations_[token] = NotifyRegistration{name, nameId, 0u, false, false};\n                return true;\n'
new_register = '                canceledNotifyTokens_.erase(token);\n                notifyRegistrations_[token] = NotifyRegistration{name, nameId, 0u, false, false};\n                return true;\n'
if old_register not in cpp: raise SystemExit('register anchor missing')
cpp = cpp.replace(old_register, new_register, 1)
old_cancel = '''            case 1016u:
                notifyRegistrations_.erase(tokenAt32());
                return true;
'''
new_cancel = '''            case 1016u: {
                const int32_t token = tokenAt32();
                notifyRegistrations_.erase(token);
                canceledNotifyTokens_.insert(token);
                return true;
            }
'''
if old_cancel not in cpp: raise SystemExit('cancel anchor missing')
cpp = cpp.replace(old_cancel, new_cancel, 1)
hpp_path.write_text(hpp)
cpp_path.write_text(cpp)
