#include "LC32DyldBootSession.hpp"
#include "LC32MachODependencies.hpp"

#include <algorithm>
#include <cerrno>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <fstream>
#include <limits>
#include <string>
#include <vector>

namespace {

std::string jsonEscape(const std::string& value) {
    std::string out;
    out.reserve(value.size() + 16);
    for (unsigned char ch : value) {
        switch (ch) {
            case '\\': out += "\\\\"; break;
            case '"': out += "\\\""; break;
            case '\n': out += "\\n"; break;
            case '\r': out += "\\r"; break;
            case '\t': out += "\\t"; break;
            default:
                if (ch < 0x20) {
                    char escaped[7]{};
                    std::snprintf(escaped, sizeof(escaped), "\\u%04x", ch);
                    out += escaped;
                } else {
                    out.push_back(static_cast<char>(ch));
                }
                break;
        }
    }
    return out;
}

void logEvent(const std::string& stage,
              const std::string& detail = {},
              uint32_t pc = 0,
              uint32_t value = 0) {
    std::fprintf(stderr,
                 "[LC32Plugin] %s pc=0x%08x value=0x%08x %s\n",
                 stage.c_str(),
                 pc,
                 value,
                 detail.c_str());

    const char* path = std::getenv("LC32_LOG_PATH");
    if (!path || !*path) return;
    FILE* file = std::fopen(path, "a");
    if (!file) return;
    std::fprintf(file,
                 "{\"stage\":\"%s\",\"detail\":\"%s\",\"pc\":%u,\"value\":%u}\n",
                 jsonEscape(stage).c_str(),
                 jsonEscape(detail).c_str(),
                 pc,
                 value);
    std::fclose(file);
}

std::string gLastError;

int failWith(int code, const std::string& stage, const std::string& detail) {
    gLastError = stage + ": " + detail;
    logEvent(stage, detail);
    return code;
}

bool readFile(const char* path, std::vector<uint8_t>& bytes, std::string& error) {
    if (!path || !*path) {
        error = "path is empty";
        return false;
    }
    std::ifstream input(path, std::ios::binary | std::ios::ate);
    if (!input) {
        error = std::string("open failed: ") + std::strerror(errno);
        return false;
    }
    const std::streamoff length = input.tellg();
    if (length <= 0 || static_cast<uint64_t>(length) > std::numeric_limits<uint32_t>::max()) {
        error = "file size is invalid or exceeds the 32-bit runtime limit";
        return false;
    }
    bytes.resize(static_cast<size_t>(length));
    input.seekg(0, std::ios::beg);
    if (!input.read(reinterpret_cast<char*>(bytes.data()), length)) {
        error = "read failed";
        bytes.clear();
        return false;
    }
    return true;
}

uint64_t stepLimit() {
    constexpr uint64_t kDefault = 2'000'000;
    constexpr uint64_t kMaximum = 50'000'000;
    const char* text = std::getenv("LC32_MAX_STEPS");
    if (!text || !*text) return kDefault;
    char* end = nullptr;
    const unsigned long long parsed = std::strtoull(text, &end, 10);
    if (!end || *end != '\0' || parsed == 0) return kDefault;
    return parsed > kMaximum ? kMaximum : static_cast<uint64_t>(parsed);
}

std::string envValue(const char* key, const char* fallback = "") {
    const char* value = std::getenv(key);
    return value && *value ? value : fallback;
}

} // namespace

extern "C" __attribute__((visibility("default")))
const char* LC32LastError(void) {
    return gLastError.c_str();
}

extern "C" __attribute__((visibility("default")))
int LC32Main(int argc, char** argv) {
    gLastError.clear();
    const char* executable = std::getenv("LC32_GUEST_EXECUTABLE");
    if ((!executable || !*executable) && argc > 1) executable = argv[1];
    const char* dyld = std::getenv("LC32_GUEST_DYLD");
    const std::string guestRoot = envValue("LC32_GUEST_ROOTFS");

    if (!executable || !*executable) {
        return failWith(64, "configuration-error", "LC32_GUEST_EXECUTABLE is missing");
    }
    logEvent("plugin-start", executable);

    std::vector<uint8_t> appImage;
    std::vector<uint8_t> dyldImage;
    std::string error;
    if (!readFile(executable, appImage, error)) {
        return failWith(66, "guest-executable-read-failed", std::string(executable) + ": " + error);
    }
    const bool hasGuestDyld = dyld && *dyld && readFile(dyld, dyldImage, error);
    if (!hasGuestDyld) {
        logEvent("cleanroom-loader-start", "guest dyld unavailable; inspecting app dependencies");
        lc32::MachODependencyResult metadata =
            lc32::parseArmv7MachODependencies(appImage.data(), appImage.size());
        if (!metadata.ok) {
            return failWith(70, "cleanroom-loader-parse-failed", metadata.error);
        }
        if (metadata.dependencies.empty()) {
            return failWith(72, "cleanroom-loader-blocked",
                            "application has no declared dependencies but direct entry startup is not implemented");
        }
        for (const auto& dependency : metadata.dependencies) {
            const std::string& path = dependency.path;
            const bool isWeak = dependency.kind == lc32::DependencyKind::Weak;
            logEvent(isWeak ? "cleanroom-weak-dependency" : "cleanroom-dependency", path);
        }
        const auto required = std::find_if(metadata.dependencies.begin(), metadata.dependencies.end(),
            [](const lc32::MachODependency& dependency) {
                return dependency.kind != lc32::DependencyKind::Weak;
            });
        if (required != metadata.dependencies.end()) {
            return failWith(72, "cleanroom-bridge-required", required->path);
        }
        return failWith(72, "cleanroom-loader-blocked", "only weak dependencies were declared");
    }

    lc32::DyldHandoffSpec spec;
    spec.appImage = appImage.data();
    spec.appSize = appImage.size();
    spec.dyldImage = dyldImage.data();
    spec.dyldSize = dyldImage.size();
    spec.executablePath = executable;
    spec.stack.argv.push_back(executable);
    for (int index = 2; index < argc; ++index) {
        if (argv[index]) spec.stack.argv.emplace_back(argv[index]);
    }

    const std::string home = envValue("LC32_GUEST_HOME", envValue("HOME").c_str());
    const std::string tmp = envValue("TMPDIR", "/tmp");
    if (!home.empty()) spec.stack.envp.push_back("HOME=" + home);
    if (!tmp.empty()) spec.stack.envp.push_back("TMPDIR=" + tmp);
    spec.stack.envp.push_back("DYLD_SHARED_REGION=private");
    if (!guestRoot.empty()) spec.stack.envp.push_back("LC32_GUEST_ROOTFS=" + guestRoot);
    spec.stack.apple.emplace_back("executable_path", executable);

    lc32::DyldBootSession session;
    const uint64_t maxSteps = stepLimit();
    logEvent("dyld-boot-dispatch", dyld, 0, static_cast<uint32_t>(maxSteps));
    lc32::DyldBootResult result = session.boot(spec, maxSteps);

    for (const lc32::DyldBootEvent& event : result.events) {
        logEvent(event.stage, event.detail, event.pc, event.value);
    }

    if (!result.prepared || !result.handoff.ok) {
        const std::string detail = !result.handoff.error.empty()
                                       ? result.handoff.error
                                       : result.cpuResult.detail;
        gLastError = "boot-preparation-failed: " + detail;
        logEvent("boot-preparation-failed", detail, result.cpuResult.pc,
                 result.cpuResult.instruction);
        return 70;
    }
    if (result.exited) {
        logEvent("guest-exited", std::to_string(result.exitCode), result.cpuResult.pc,
                 static_cast<uint32_t>(result.cpuResult.steps));
        return result.exitCode;
    }

    std::string stopDetail = result.cpuResult.detail;
    if (stopDetail.empty()) stopDetail = "guest stopped without exiting";
    gLastError = "guest-cpu-stop: " + stopDetail;
    logEvent("guest-cpu-stop", stopDetail, result.cpuResult.pc,
             result.cpuResult.instruction);
    return 71;
}
