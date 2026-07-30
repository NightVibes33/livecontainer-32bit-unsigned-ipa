#include "../LC32DyldBootSession.hpp"

#include <cassert>
#include <cstdint>
#include <cstring>
#include <iostream>
#include <vector>

namespace {

void put32(std::vector<uint8_t>& v, size_t off, uint32_t value) {
    if (v.size() < off + 4) v.resize(off + 4);
    std::memcpy(v.data() + off, &value, 4);
}

std::vector<uint8_t> makeMachO(uint32_t vmaddr, const std::vector<uint32_t>& code) {
    std::vector<uint8_t> v(0x300, 0);
    put32(v, 0x00, 0xfeedfaceu);
    put32(v, 0x04, 12u);
    put32(v, 0x08, 9u);
    put32(v, 0x0c, 2u);
    put32(v, 0x10, 2u);
    put32(v, 0x14, 80u);

    size_t lc = 0x1c;
    put32(v, lc + 0x00, 1u);
    put32(v, lc + 0x04, 56u);
    std::memcpy(v.data() + lc + 8, "__TEXT", 6);
    put32(v, lc + 0x18, vmaddr);
    put32(v, lc + 0x1c, 0x1000u);
    put32(v, lc + 0x20, 0u);
    put32(v, lc + 0x24, 0x300u);
    put32(v, lc + 0x28, 7u);
    put32(v, lc + 0x2c, 5u);

    lc += 56;
    put32(v, lc + 0x00, 0x80000028u);
    put32(v, lc + 0x04, 24u);
    put32(v, lc + 0x08, 0x100u);

    for (size_t i = 0; i < code.size(); ++i) put32(v, 0x100 + i * 4, code[i]);
    return v;
}

} // namespace

int main() {
    auto app = makeMachO(0x1000u, {0xe1a00000u});
    auto dyld = makeMachO(0x2000u, {
        0xe3500000u, // cmp r0,#0 -- main Mach header must be supplied
        0x0a000003u, // beq failure
        0xe3a0c014u, // mov r12,#20 getpid
        0xef000080u, // svc #0x80
        0xe3a0c001u, // mov r12,#1 exit
        0xe3a00000u, // mov r0,#0
        0xef000080u, // svc #0x80
        0xe3a0c001u, // failure: mov r12,#1
        0xe3a00009u, // mov r0,#9
        0xef000080u  // svc #0x80
    });

    lc32::DyldHandoffSpec spec;
    spec.appImage = app.data();
    spec.appSize = app.size();
    spec.dyldImage = dyld.data();
    spec.dyldSize = dyld.size();
    spec.executablePath = "/Applications/FixItFelix.app/FixItFelix";
    spec.appSlide = 0x10000000u;
    spec.dyldSlide = 0x20000000u;
    spec.stack.envp = {"HOME=/var/mobile", "TMPDIR=/tmp"};

    lc32::DyldBootSession session;
    auto result = session.boot(spec, 128);
    assert(result.prepared);
    assert(result.handoff.ok);
    assert(result.handoff.mainMachHeader == 0x10001000u);
    assert(result.exited);
    assert(result.exitCode == 0);
    assert(session.state().r[13] == result.handoff.sp);

    bool sawReady = false;
    bool sawSyscall = false;
    for (const auto& event : result.events) {
        sawReady |= event.stage == "dyld-handoff-ready";
        sawSyscall |= event.stage == "syscall-handled";
    }
    assert(sawReady);
    assert(sawSyscall);
    std::cout << "LC32 dyld boot session tests passed\n";
    return 0;
}
