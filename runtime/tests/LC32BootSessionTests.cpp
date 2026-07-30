#include "../LC32BootSession.hpp"

#include <cassert>
#include <cstdint>
#include <cstring>
#include <iostream>
#include <vector>

namespace {

void put32(std::vector<uint8_t>& v, size_t off, uint32_t x) {
    if (v.size() < off + 4) v.resize(off + 4);
    std::memcpy(v.data() + off, &x, 4);
}

std::vector<uint8_t> makeMachO() {
    std::vector<uint8_t> v(0x200, 0);
    put32(v, 0x00, 0xfeedfaceu); // MH_MAGIC
    put32(v, 0x04, 12u);         // CPU_TYPE_ARM
    put32(v, 0x08, 9u);          // ARM_V7
    put32(v, 0x0c, 2u);          // MH_EXECUTE
    put32(v, 0x10, 2u);          // ncmds
    put32(v, 0x14, 56u + 24u);   // sizeofcmds

    size_t lc = 0x1c;
    put32(v, lc + 0x00, 1u);     // LC_SEGMENT
    put32(v, lc + 0x04, 56u);
    std::memcpy(v.data() + lc + 8, "__TEXT", 6);
    put32(v, lc + 0x18, 0x1000u); // vmaddr
    put32(v, lc + 0x1c, 0x1000u); // vmsize
    put32(v, lc + 0x20, 0u);      // fileoff
    put32(v, lc + 0x24, 0x200u);  // filesize
    put32(v, lc + 0x28, 7u);
    put32(v, lc + 0x2c, 5u);

    lc += 56;
    put32(v, lc + 0x00, 0x80000028u); // LC_MAIN
    put32(v, lc + 0x04, 24u);
    put32(v, lc + 0x08, 0x100u);      // entryoff low
    put32(v, lc + 0x0c, 0u);

    // mov r12,#20 ; svc #0x80 ; mov r12,#1 ; mov r0,#7 ; svc #0x80
    put32(v, 0x100, 0xe3a0c014u);
    put32(v, 0x104, 0xef000080u);
    put32(v, 0x108, 0xe3a0c001u);
    put32(v, 0x10c, 0xe3a00007u);
    put32(v, 0x110, 0xef000080u);
    return v;
}

} // namespace

int main() {
    auto image = makeMachO();
    lc32::BootSession session;
    lc32::BootResult result = session.boot(image.data(), image.size(), 64);
    assert(result.loaded);
    assert(result.exited);
    assert(result.exitCode == 7);
    bool sawLoad = false, sawSyscall = false;
    for (const auto& event : result.events) {
        sawLoad |= event.stage == "macho-loaded";
        sawSyscall |= event.stage == "syscall-handled";
    }
    assert(sawLoad);
    assert(sawSyscall);
    std::cout << "LC32 boot session tests passed\n";
    return 0;
}
