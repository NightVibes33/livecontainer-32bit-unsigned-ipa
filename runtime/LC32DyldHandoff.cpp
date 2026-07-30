#include "LC32DyldHandoff.hpp"

namespace lc32 {

DyldHandoffResult prepareDyldHandoff(const DyldHandoffSpec& spec,
                                     const MapCallback& map,
                                     const WriteCallback& write) {
    DyldHandoffResult out;
    if (!spec.appImage || !spec.appSize) { out.error = "missing app image"; return out; }
    if (!spec.dyldImage || !spec.dyldSize) { out.error = "missing dyld image"; return out; }
    if (!map || !write) { out.error = "missing memory callbacks"; return out; }
    if (!map(spec.stackBase, spec.stackSize, 3)) { out.error = "stack mapping failed"; return out; }

    out.app = loadArmv7MachO(spec.appImage, spec.appSize, map, write, spec.appSlide);
    if (!out.app.ok) { out.error = "app: " + out.app.error; return out; }
    out.dyld = loadArmv7MachO(spec.dyldImage, spec.dyldSize, map, write, spec.dyldSlide);
    if (!out.dyld.ok) { out.error = "dyld: " + out.dyld.error; return out; }

    uint32_t appHeader = spec.appSlide;
    for (const auto& segment : out.app.segments) {
        if (segment.fileoff == 0 && segment.filesize != 0) {
            appHeader = segment.vmaddr;
            break;
        }
    }

    ProcessStackSpec stack = spec.stack;
    if (stack.argv.empty()) stack.argv.push_back(spec.executablePath);
    if (stack.apple.empty()) {
        stack.apple.push_back({"executable_path", spec.executablePath});
        stack.apple.push_back({"main_mach_header", std::to_string(appHeader)});
    }
    out.processStack = buildDarwinProcessStack(spec.stackBase, spec.stackSize, stack, write);
    if (!out.processStack.ok) { out.error = "stack: " + out.processStack.error; return out; }

    out.pc = out.dyld.entryPoint & ~1u;
    out.sp = out.processStack.stackPointer;
    out.mainMachHeader = appHeader;
    out.thumb = out.dyld.thumb || (out.dyld.entryPoint & 1u);
    out.ok = true;
    return out;
}

} // namespace lc32
