#!/usr/bin/env python3
from pathlib import Path

header_path = Path('runtime/LC32DarwinSyscalls.hpp')
header = header_path.read_text()
header = header.replace('#include <cstdint>\n', '#include <cstdint>\n#include <dirent.h>\n', 1)
header = header.replace('''    struct GuestFile {
        int hostFd = -1;
        uint32_t openFlags = 0;
        uint32_t descriptorFlags = 0;
    };
''', '''    struct GuestFile {
        int hostFd = -1;
        uint32_t openFlags = 0;
        uint32_t descriptorFlags = 0;
        DIR* directoryStream = nullptr;
    };
''', 1)
header = header.replace('''    int allocateGuestFd(int hostFd, uint32_t openFlags, uint32_t descriptorFlags);
''', '''    int allocateGuestFd(int hostFd,
                        uint32_t openFlags,
                        uint32_t descriptorFlags,
                        DIR* directoryStream = nullptr);
''', 1)
header_path.write_text(header)

source_path = Path('runtime/LC32DarwinSyscalls.cpp')
source = source_path.read_text()
source = source.replace('''DarwinSyscalls::~DarwinSyscalls() {
    for (const auto& entry : guestFiles_) {
        ::close(entry.second.hostFd);
    }
}
''', '''DarwinSyscalls::~DarwinSyscalls() {
    for (const auto& entry : guestFiles_) {
        if (entry.second.directoryStream != nullptr) {
            ::closedir(entry.second.directoryStream);
        }
        ::close(entry.second.hostFd);
    }
}
''', 1)
source = source.replace('''int DarwinSyscalls::allocateGuestFd(int hostFd,
                                    uint32_t openFlags,
                                    uint32_t descriptorFlags) {
''', '''int DarwinSyscalls::allocateGuestFd(int hostFd,
                                    uint32_t openFlags,
                                    uint32_t descriptorFlags,
                                    DIR* directoryStream) {
''', 1)
source = source.replace('''            guestFiles_.emplace(candidate, GuestFile{hostFd, openFlags, descriptorFlags});
''', '''            guestFiles_.emplace(candidate,
                                GuestFile{hostFd,
                                          openFlags,
                                          descriptorFlags,
                                          directoryStream});
''', 1)
source = source.replace('''            const uint32_t descriptorFlags =
                (flags & kGuestOpenCloseExec) != 0 ? kGuestFdCloseExec : 0u;
            const int guestFd = allocateGuestFd(hostFd, flags, descriptorFlags);
            if (guestFd < 0) {
                ::close(hostFd);
                return fail(number, EMFILE, "open guest fd table");
            }
''', '''            DIR* directoryStream = nullptr;
            struct stat openedStat{};
            if (::fstat(hostFd, &openedStat) != 0) {
                const int savedError = errno;
                ::close(hostFd);
                return fail(number, savedError, "open fstat");
            }
            if (S_ISDIR(openedStat.st_mode)) {
                const int directoryFd = ::dup(hostFd);
                if (directoryFd < 0) {
                    const int savedError = errno;
                    ::close(hostFd);
                    return fail(number, savedError, "open directory dup");
                }
                directoryStream = ::fdopendir(directoryFd);
                if (directoryStream == nullptr) {
                    const int savedError = errno;
                    ::close(directoryFd);
                    ::close(hostFd);
                    return fail(number, savedError, "open directory stream");
                }
            }
            const uint32_t descriptorFlags =
                (flags & kGuestOpenCloseExec) != 0 ? kGuestFdCloseExec : 0u;
            const int guestFd = allocateGuestFd(hostFd,
                                                flags,
                                                descriptorFlags,
                                                directoryStream);
            if (guestFd < 0) {
                if (directoryStream != nullptr) ::closedir(directoryStream);
                ::close(hostFd);
                return fail(number, EMFILE, "open guest fd table");
            }
''', 1)
source = source.replace('''            const int hostFd = file->second.hostFd;
            guestFiles_.erase(file);
            if (::close(hostFd) != 0) return fail(number, errno, "close host call");
''', '''            const int hostFd = file->second.hostFd;
            DIR* directoryStream = file->second.directoryStream;
            guestFiles_.erase(file);
            if (directoryStream != nullptr && ::closedir(directoryStream) != 0) {
                const int savedError = errno;
                ::close(hostFd);
                return fail(number, savedError, "close directory stream");
            }
            if (::close(hostFd) != 0) return fail(number, errno, "close host call");
''', 1)

case_needle = '        case 340: {\n'
case_body = r'''        case 344: {
            const int guestFd = static_cast<int>(state.r[0]);
            const uint32_t bufferAddress = state.r[1];
            const size_t bufferSize = state.r[2];
            const uint32_t positionAddress = state.r[3];
            if (bufferSize == 0 || bufferSize > kMaximumTransfer) {
                return fail(number, EINVAL, "getdirentries64 buffer size");
            }
            if (!memory_.write || positionAddress == 0) {
                return fail(number, EFAULT, "getdirentries64 memory");
            }
            const auto file = guestFiles_.find(guestFd);
            if (file == guestFiles_.end()) {
                return fail(number, EBADF, "getdirentries64 guest fd");
            }
            DIR* stream = file->second.directoryStream;
            if (stream == nullptr) {
                return fail(number, ENOTDIR, "getdirentries64 not directory");
            }

            const long initialCookie = ::telldir(stream);
            std::vector<uint8_t> output;
            output.reserve(bufferSize);
            uint64_t finalPosition = initialCookie < 0 ? 0u : static_cast<uint64_t>(initialCookie);

            for (;;) {
                const long entryCookie = ::telldir(stream);
                errno = 0;
                struct dirent* entry = ::readdir(stream);
                if (entry == nullptr) {
                    if (errno != 0) {
                        if (initialCookie >= 0) ::seekdir(stream, initialCookie);
                        return fail(number, errno, "getdirentries64 readdir");
                    }
                    break;
                }

                const size_t nameLength = ::strnlen(entry->d_name, 1024u);
                if (nameLength > UINT16_MAX) {
                    if (initialCookie >= 0) ::seekdir(stream, initialCookie);
                    return fail(number, EOVERFLOW, "getdirentries64 name length");
                }
                const size_t recordSize = (21u + nameLength + 1u + 3u) & ~size_t(3u);
                if (recordSize > UINT16_MAX) {
                    if (initialCookie >= 0) ::seekdir(stream, initialCookie);
                    return fail(number, EOVERFLOW, "getdirentries64 record length");
                }
                if (recordSize > bufferSize - output.size()) {
                    if (entryCookie >= 0) ::seekdir(stream, entryCookie);
                    if (output.empty()) {
                        return fail(number, EINVAL, "getdirentries64 buffer too small");
                    }
                    break;
                }

                const long nextCookie = ::telldir(stream);
                const uint64_t inode = static_cast<uint64_t>(entry->d_ino);
                const uint64_t seekOffset =
                    nextCookie < 0 ? finalPosition : static_cast<uint64_t>(nextCookie);
                const uint16_t recordLength = static_cast<uint16_t>(recordSize);
                const uint16_t guestNameLength = static_cast<uint16_t>(nameLength);
                const uint8_t type = static_cast<uint8_t>(entry->d_type);
                const size_t base = output.size();
                output.resize(base + recordSize, 0);
                std::memcpy(output.data() + base + 0u, &inode, sizeof(inode));
                std::memcpy(output.data() + base + 8u, &seekOffset, sizeof(seekOffset));
                std::memcpy(output.data() + base + 16u,
                            &recordLength,
                            sizeof(recordLength));
                std::memcpy(output.data() + base + 18u,
                            &guestNameLength,
                            sizeof(guestNameLength));
                std::memcpy(output.data() + base + 20u, &type, sizeof(type));
                std::memcpy(output.data() + base + 21u,
                            entry->d_name,
                            nameLength + 1u);
                finalPosition = seekOffset;
            }

            if (!output.empty() &&
                !memory_.write(bufferAddress, output.data(), output.size())) {
                if (initialCookie >= 0) ::seekdir(stream, initialCookie);
                return fail(number, EFAULT, "getdirentries64 guest buffer write");
            }
            if (!memory_.write(positionAddress,
                               &finalPosition,
                               sizeof(finalPosition))) {
                if (initialCookie >= 0) ::seekdir(stream, initialCookie);
                return fail(number, EFAULT, "getdirentries64 position write");
            }
            return ok(number,
                      static_cast<int32_t>(output.size()),
                      "getdirentries64");
        }
'''
if source.count(case_needle) != 1:
    raise SystemExit('getdirentries64 insertion point not unique')
source = source.replace(case_needle, case_body + case_needle, 1)
source_path.write_text(source)

test_path = Path('runtime/tests/LC32DarwinSyscallsTests.cpp')
test = test_path.read_text()
test = test.replace('#include <iostream>\n', '#include <iostream>\n#include <set>\n', 1)
test = test.replace('''    constexpr uint32_t kRlimitAddress = 0x1700u;
    constexpr uint32_t kStackAddress = 0x3000u;
''', '''    constexpr uint32_t kRlimitAddress = 0x1700u;
    constexpr uint32_t kDirectoryBufferAddress = 0x2000u;
    constexpr uint32_t kDirectoryPositionAddress = 0x2f00u;
    constexpr uint32_t kStackAddress = 0x3000u;
''', 1)
test = test.replace('''    std::filesystem::create_directories(root / "usr/lib");
''', '''    std::filesystem::create_directories(root / "usr/lib/Frameworks");
''', 1)
insert_needle = '''    putCString(kPathAddress, "/usr/lib/libA.dylib");

    state = {};
    state.r[12] = 33;
'''
insert_body = r'''    putCString(kPathAddress, "/usr/lib");
    state = {};
    state.r[12] = 5;
    state.r[0] = kPathAddress;
    state.r[1] = 0u;
    const auto directoryOpened = rooted.dispatch(state, 0x80u, false);
    assert(directoryOpened.handled && directoryOpened.errorNumber == 0);
    const int directoryFd = static_cast<int>(state.r[0]);

    state = {};
    state.r[12] = 344;
    state.r[0] = static_cast<uint32_t>(directoryFd);
    state.r[1] = kDirectoryBufferAddress;
    state.r[2] = 8u;
    state.r[3] = kDirectoryPositionAddress;
    const auto tinyDirectoryRead = rooted.dispatch(state, 0x80u, false);
    assert(tinyDirectoryRead.handled && tinyDirectoryRead.errorNumber == EINVAL);

    std::memset(lowMemory.data() + kDirectoryBufferAddress, 0, 1024u);
    uint64_t directoryPosition = 0;
    std::memcpy(lowMemory.data() + kDirectoryPositionAddress,
                &directoryPosition,
                sizeof(directoryPosition));
    state = {};
    state.r[12] = 344;
    state.r[0] = static_cast<uint32_t>(directoryFd);
    state.r[1] = kDirectoryBufferAddress;
    state.r[2] = 1024u;
    state.r[3] = kDirectoryPositionAddress;
    const auto directoryRead = rooted.dispatch(state, 0x80u, false);
    assert(directoryRead.handled && directoryRead.errorNumber == 0);
    assert(directoryRead.returnValue > 0);

    std::set<std::string> directoryNames;
    size_t directoryOffset = 0;
    while (directoryOffset < static_cast<size_t>(directoryRead.returnValue)) {
        uint16_t recordLength = 0;
        uint16_t nameLength = 0;
        std::memcpy(&recordLength,
                    lowMemory.data() + kDirectoryBufferAddress + directoryOffset + 16u,
                    sizeof(recordLength));
        std::memcpy(&nameLength,
                    lowMemory.data() + kDirectoryBufferAddress + directoryOffset + 18u,
                    sizeof(nameLength));
        assert(recordLength >= 24u && (recordLength & 3u) == 0u);
        assert(directoryOffset + recordLength <=
               static_cast<size_t>(directoryRead.returnValue));
        directoryNames.emplace(reinterpret_cast<char*>(
                                   lowMemory.data() + kDirectoryBufferAddress +
                                   directoryOffset + 21u),
                               nameLength);
        directoryOffset += recordLength;
    }
    assert(directoryNames.count(".") == 1u);
    assert(directoryNames.count("..") == 1u);
    assert(directoryNames.count("libA.dylib") == 1u);
    assert(directoryNames.count("libAlias.dylib") == 1u);
    assert(directoryNames.count("Frameworks") == 1u);

    state = {};
    state.r[12] = 344;
    state.r[0] = static_cast<uint32_t>(directoryFd);
    state.r[1] = kDirectoryBufferAddress;
    state.r[2] = 1024u;
    state.r[3] = kDirectoryPositionAddress;
    const auto directoryEnd = rooted.dispatch(state, 0x80u, false);
    assert(directoryEnd.handled && directoryEnd.errorNumber == 0);
    assert(directoryEnd.returnValue == 0);

    state = {};
    state.r[12] = 6;
    state.r[0] = static_cast<uint32_t>(directoryFd);
    const auto directoryClosed = rooted.dispatch(state, 0x80u, false);
    assert(directoryClosed.handled && directoryClosed.errorNumber == 0);

    putCString(kPathAddress, "/usr/lib/libA.dylib");

    state = {};
    state.r[12] = 33;
'''
if test.count(insert_needle) != 1:
    raise SystemExit('directory test insertion point not unique')
test = test.replace(insert_needle, insert_body, 1)
test_path.write_text(test)
