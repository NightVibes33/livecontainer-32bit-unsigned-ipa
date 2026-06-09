//
//  Dyld.m
//  LiveContainer
//
//  Created by s s on 2025/2/7.
//
#include <dlfcn.h>
#include <limits.h>
#include <stdlib.h>
#include <sys/mman.h>
#import "../../litehook/src/litehook.h"
#import "LCMachOUtils.h"
#include "mach_excServer.h"
#import "../utils.h"
#import "../dyld_bypass_validation.h"
@import Darwin;
@import Foundation;
@import MachO;

typedef uint32_t dyld_platform_t;

typedef struct {
    dyld_platform_t platform;
    uint32_t        version;
} dyld_build_version_t;

uint32_t lcImageIndex = 0;
uint32_t appMainImageIndex = 0;
void* appExecutableHandle = 0;
bool hookedDlopen = false;
bool tweakLoaderLoaded = false;
bool appExecutableFileTypeOverwritten = false;
const char* lcMainBundlePath = NULL;
#if is32BitSupported
static bool lcDlopenReroutedTo32BitLayer = false;
static char lcDlopen32BitLayerPath[PATH_MAX];
#endif

void* (*orig_dlopen)(const char *path, int mode) = dlopen;
void* (*orig_dlsym)(void * __handle, const char * __symbol) = dlsym;
uint32_t (*orig_dyld_image_count)(void) = _dyld_image_count;
const struct mach_header* (*orig_dyld_get_image_header)(uint32_t image_index) = _dyld_get_image_header;
intptr_t (*orig_dyld_get_image_vmaddr_slide)(uint32_t image_index) = _dyld_get_image_vmaddr_slide;
const char* (*orig_dyld_get_image_name)(uint32_t image_index) = _dyld_get_image_name;
int (*orig_fcntl)(int fildes, int cmd, void *param) = 0;

uint32_t guestAppSdkVersion = 0;
uint32_t guestAppSdkVersionSet = 0;
bool (*orig_dyld_program_sdk_at_least)(void* dyldPtr, dyld_build_version_t version);
uint32_t (*orig_dyld_get_program_sdk_version)(void* dyldPtr);

static void overwriteAppExecutableFileType(void) {
    struct mach_header_64* appImageMachOHeader = (struct mach_header_64*) orig_dyld_get_image_header(appMainImageIndex);
    kern_return_t kret = builtin_vm_protect(mach_task_self(), (vm_address_t)appImageMachOHeader, sizeof(appImageMachOHeader), false, PROT_READ | PROT_WRITE | VM_PROT_COPY);
    if(kret != KERN_SUCCESS) {
        NSLog(@"[LC] failed to change appImageMachOHeader to rw");
    } else {
        NSLog(@"[LC] changed appImageMachOHeader to rw");
        appImageMachOHeader->filetype = MH_EXECUTE;
        builtin_vm_protect(mach_task_self(), (vm_address_t)appImageMachOHeader, sizeof(appImageMachOHeader), false,  PROT_READ);
    }
}

static inline int translateImageIndex(int origin) {
    if(origin == lcImageIndex) {
        if(!appExecutableFileTypeOverwritten) {
            overwriteAppExecutableFileType();
            appExecutableFileTypeOverwritten = true;
        }
        
        return appMainImageIndex;
    }
    
    return origin;
}

void* hook_dlsym(void * __handle, const char * __symbol) {
    if(__handle == (void*)RTLD_MAIN_ONLY) {
        if(strcmp(__symbol, MH_EXECUTE_SYM) == 0) {
            if(!appExecutableFileTypeOverwritten) {
                overwriteAppExecutableFileType();
                appExecutableFileTypeOverwritten = true;
            }
            return (void*)orig_dyld_get_image_header(appMainImageIndex);
        }
        __handle = appExecutableHandle;
    } else if (__handle != (void*)RTLD_SELF && __handle != (void*)RTLD_NEXT) {
        void* ans = orig_dlsym(__handle, __symbol);
        if(!ans) {
            return 0;
        }
        for(int i = 0; i < gRebindCount; i++) {
            global_rebind rebind = gRebinds[i];
            if(ans == rebind.replacee) {
                return rebind.replacement;
            }
        }
        return ans;
    }
    
    __attribute__((musttail)) return orig_dlsym(__handle, __symbol);
}

uint32_t hook_dyld_image_count(void) {
    return orig_dyld_image_count() - 1 - (uint32_t)tweakLoaderLoaded;
}

const struct mach_header* hook_dyld_get_image_header(uint32_t image_index) {
    __attribute__((musttail)) return orig_dyld_get_image_header(translateImageIndex(image_index));
}

intptr_t hook_dyld_get_image_vmaddr_slide(uint32_t image_index) {
    __attribute__((musttail)) return orig_dyld_get_image_vmaddr_slide(translateImageIndex(image_index));
}

const char* hook_dyld_get_image_name(uint32_t image_index) {
    __attribute__((musttail)) return orig_dyld_get_image_name(translateImageIndex(image_index));
}

void hideLiveContainerImageCallback(const struct mach_header* header, intptr_t vmaddr_slide) {
    Dl_info info;
    dladdr(header, &info);
    if(!strncmp(info.dli_fname, lcMainBundlePath, strlen(lcMainBundlePath)) || strstr(info.dli_fname, "/procursus/") != 0) {
        char fakePath[PATH_MAX];
        snprintf(fakePath, sizeof(fakePath), "/usr/lib/%p.dylib", header);
        kern_return_t ret = vm_protect(mach_task_self(), (vm_address_t)info.dli_fname, PATH_MAX, false, PROT_READ | PROT_WRITE);
        if(ret != KERN_SUCCESS) {
            os_thread_self_restrict_tpro_to_rw();
        }
        strcpy((char *)info.dli_fname, fakePath);
        if(ret != KERN_SUCCESS) {
            os_thread_self_restrict_tpro_to_ro();
        }
    }
}

void* getDSCAddr(void) {
    task_dyld_info_data_t dyldInfo;
    
    uint32_t count = TASK_DYLD_INFO_COUNT;
    task_info(mach_task_self_, TASK_DYLD_INFO, (task_info_t)&dyldInfo, &count);
    struct dyld_all_image_infos *infos = (struct dyld_all_image_infos *)dyldInfo.all_image_info_addr;
    return (void*)infos->sharedCacheBaseAddress;
}

void* getCachedSymbol(NSString* symbolName, mach_header_u* header) {
    if(!header) {
        return NULL;
    }
    NSDictionary* symbolOffsetDict = [NSUserDefaults.lcSharedDefaults objectForKey:@"symbolOffsetCache"][symbolName];
    if(!symbolOffsetDict) {
        return NULL;
    }
    NSData* cachedSymbolUUID = symbolOffsetDict[@"uuid"];
    if(!cachedSymbolUUID) {
        return NULL;
    }
    const uint8_t* uuid = LCGetMachOUUID(header);
    if(!uuid || memcmp(uuid, [cachedSymbolUUID bytes], 16)) {
        return NULL;
    }
    
    return (void*)header + [symbolOffsetDict[@"offset"] unsignedLongLongValue];
}

void saveCachedSymbol(NSString* symbolName, mach_header_u* header, uint64_t offset) {
    if(!header) {
        NSLog(@"[LC] symbol cache skipped: %@ has no image header", symbolName);
        return;
    }
    const uint8_t* uuid = LCGetMachOUUID(header);
    if(!uuid) {
        NSLog(@"[LC] symbol cache skipped: %@ has no image UUID", symbolName);
        return;
    }
    NSMutableDictionary* allSymbolOffsetDict = [[NSUserDefaults.lcSharedDefaults objectForKey:@"symbolOffsetCache"] mutableCopy];
    if(!allSymbolOffsetDict) {
        allSymbolOffsetDict = [[NSMutableDictionary alloc] init];
    }
    
    allSymbolOffsetDict[symbolName] = @{
        @"uuid": [NSData dataWithBytes:uuid length:16],
        @"offset": @(offset),
    };
    [NSUserDefaults.lcSharedDefaults setObject:allSymbolOffsetDict forKey:@"symbolOffsetCache"];
}

bool hook_dyld_program_sdk_at_least(void* dyldApiInstancePtr, dyld_build_version_t version) {
    // we are targeting ios, so we hard code 2
    if(version.platform == 0xffffffff){
        return version.version <= guestAppSdkVersionSet;
    } else if (version.platform == 2){
        return version.version <= guestAppSdkVersion;
    } else {
        return false;
    }
}

uint32_t hook_dyld_get_program_sdk_version(void* dyldApiInstancePtr) {
    return guestAppSdkVersion;
}


static bool LCAddressHasProtection(const void* address, size_t length, vm_prot_t protection) {
    if(!address || length == 0) {
        return false;
    }
    vm_address_t region = (vm_address_t)address;
    vm_size_t regionSize = 0;
    vm_region_basic_info_data_64_t info;
    mach_msg_type_number_t infoCount = VM_REGION_BASIC_INFO_COUNT_64;
    mach_port_t objectName = MACH_PORT_NULL;
    kern_return_t ret = vm_region_64(mach_task_self(), &region, &regionSize, VM_REGION_BASIC_INFO_64, (vm_region_info_t)&info, &infoCount, &objectName);
    if(objectName != MACH_PORT_NULL) {
        mach_port_deallocate(mach_task_self(), objectName);
    }
    if(ret != KERN_SUCCESS || !(info.protection & protection)) {
        return false;
    }
    uintptr_t ptr = (uintptr_t)address;
    uintptr_t start = (uintptr_t)region;
    uintptr_t end = start + (uintptr_t)regionSize;
    return ptr >= start && ptr <= end && length <= end - ptr;
}

static bool LCReadPointer(const void* address, void** value) {
    if(!LCAddressHasProtection(address, sizeof(void*), VM_PROT_READ)) {
        return false;
    }
    void* pointer = *(void* const*)address;
    if(!pointer) {
        return false;
    }
    *value = pointer;
    return true;
}

static bool LCShouldSkipDyldApiHook(const char* functionName) {
#if !TARGET_OS_SIMULATOR
    if(!functionName || getenv("LC_ENABLE_IOS27_PRIVATE_DYLD_API_HOOKS")) {
        return false;
    }
    NSOperatingSystemVersion version = NSProcessInfo.processInfo.operatingSystemVersion;
    if(version.majorVersion >= 27 && !strcmp(functionName, "_NSGetExecutablePath")) {
        NSLog(@"[LC] dyld hook skipped: %s is disabled on iOS %ld.%ld fallback path", functionName, (long)version.majorVersion, (long)version.minorVersion);
        return true;
    }
#endif
    return false;
}

static bool LCIsAdrp(uint32_t instruction) {
    return (instruction & 0x9f000000) == 0x90000000;
}

static uint32_t LCInstructionRd(uint32_t instruction) {
    return instruction & 0x1F;
}

static uint32_t LCInstructionRn(uint32_t instruction) {
    return (instruction >> 5) & 0x1F;
}

static bool LCIsBranchImmediate(uint32_t instruction) {
    return (instruction & 0xFC000000) == 0x14000000;
}

static bool LCIsBranchRegister(uint32_t instruction) {
    return (instruction & 0xFFFFFC1F) == 0xD61F0000;
}

static uint32_t* LCBranchImmediateTarget(uint32_t* pc, uint32_t instruction) {
    int32_t imm26 = instruction & 0x03FFFFFF;
    if(imm26 & 0x02000000) {
        imm26 |= ~0x03FFFFFF;
    }
    return (uint32_t*)((uint8_t*)pc + (((intptr_t)imm26) << 2));
}

static bool LCIsArm64eMovImmediate(uint32_t instruction) {
    return (instruction & 0x7F800000) == 0x52800000;
}

static bool LCIsArm64eLdrPreIndex64(uint32_t instruction) {
    return (instruction & 0xFFE00C00) == 0xF8400C00;
}

static bool LCIsLdrUnsignedImmediate(uint32_t instruction) {
    return (instruction & 0xFFC00000) == 0xF9400000;
}

static bool LCIsLdrLiteral64(uint32_t instruction) {
    return (instruction & 0xFF000000) == 0x58000000;
}

static uintptr_t LCLdrUnsignedImmediateOffset(uint32_t instruction) {
    uint32_t size = (instruction & 0xC0000000) >> 30;
    return ((instruction & 0x3FFC00) >> 10) << size;
}

static void* LCLdrLiteralAddress(uint32_t* pc, uint32_t instruction) {
    int32_t imm19 = (instruction >> 5) & 0x7FFFF;
    if(imm19 & 0x40000) {
        imm19 |= ~0x7FFFF;
    }
    return (void*)((uint8_t*)pc + (((intptr_t)imm19) << 2));
}

static bool LCIsReasonableDyldVtableOffset(uintptr_t offset) {
    return offset >= sizeof(void*) && offset < 0x4000 && (offset % sizeof(void*)) == 0;
}

static bool LCFindDyldApiVtableOffset(uint32_t* baseAddr, uint32_t adrpOffset, uintptr_t* vtableOffset) {
    for(uint32_t offset = adrpOffset + 2; offset < adrpOffset + 24; ++offset) {
        uint32_t instruction = baseAddr[offset];
        if(LCIsArm64eMovImmediate(instruction)) {
            uintptr_t imm16 = (instruction & 0x1FFFE0) >> 5;
            if(LCIsReasonableDyldVtableOffset(imm16)) {
                *vtableOffset = imm16;
                return true;
            }
        }

        if(LCIsArm64eLdrPreIndex64(instruction)) {
            int32_t imm9 = (instruction & 0x1FF000) >> 12;
            if(imm9 & 0x100) {
                imm9 |= ~0x1FF;
            }
            if(imm9 > 0 && LCIsReasonableDyldVtableOffset((uintptr_t)imm9)) {
                *vtableOffset = (uintptr_t)imm9;
                return true;
            }
        }

        if(LCIsLdrUnsignedImmediate(instruction)) {
            uintptr_t candidateOffset = LCLdrUnsignedImmediateOffset(instruction);
            if(LCIsReasonableDyldVtableOffset(candidateOffset)) {
                *vtableOffset = candidateOffset;
                return true;
            }
        }
    }

    return false;
}

static bool LCFindDyldApiObjectStorage(uint32_t* baseAddr, uint32_t adrpOffset, void** objectStorage) {
    uint32_t* adrpInstPtr = baseAddr + adrpOffset;
    if(!LCAddressHasProtection(adrpInstPtr, sizeof(uint32_t) * 8, VM_PROT_READ) || !LCIsAdrp(*adrpInstPtr)) {
        return false;
    }

    uint32_t adrpReg = LCInstructionRd(*adrpInstPtr);
    uintptr_t address = aarch64_emulate_adrp(*adrpInstPtr, (uint64_t)adrpInstPtr);
    if(!address) {
        return false;
    }

    for(uint32_t offset = adrpOffset + 1; offset < adrpOffset + 10; ++offset) {
        uint32_t instruction = baseAddr[offset];
        uint32_t dst = 0;
        uint32_t src = 0;
        uint32_t imm = 0;
        if(aarch64_emulate_add_imm(instruction, &dst, &src, &imm) && dst == adrpReg && src == adrpReg) {
            address += imm;
            continue;
        }
        if(LCIsLdrUnsignedImmediate(instruction) && LCInstructionRn(instruction) == adrpReg) {
            *objectStorage = (void*)(address + LCLdrUnsignedImmediateOffset(instruction));
            return true;
        }
    }

    return false;
}

static bool LCBuildVtableFunctionPtrFromObject(void* objectPtr, uintptr_t vtableOffset, void*** vtableFunctionPtr) {
    void* vtablePtr = NULL;
    if(!LCReadPointer(objectPtr, &vtablePtr)) {
        return false;
    }
    void** candidate = (void**)((uint8_t*)vtablePtr + vtableOffset);
    if(!LCAddressHasProtection(candidate, sizeof(void*), VM_PROT_READ)) {
        return false;
    }
    *vtableFunctionPtr = candidate;
    return true;
}

static bool LCBuildVtableFunctionPtrFromStorage(void* objectStorage, uintptr_t vtableOffset, void*** vtableFunctionPtr) {
    void* objectPtr = NULL;
    if(!LCReadPointer(objectStorage, &objectPtr)) {
        return false;
    }
    return LCBuildVtableFunctionPtrFromObject(objectPtr, vtableOffset, vtableFunctionPtr);
}

static bool LCFindDyldApiObjectLiteral(uint32_t* baseAddr, uint32_t offset, void** objectPtr) {
    uint32_t* instPtr = baseAddr + offset;
    if(!LCAddressHasProtection(instPtr, sizeof(uint32_t), VM_PROT_READ) || !LCIsLdrLiteral64(*instPtr)) {
        return false;
    }
    void* literalAddress = LCLdrLiteralAddress(instPtr, *instPtr);
    return LCReadPointer(literalAddress, objectPtr);
}

static bool LCTryFindDyldApiVtableFunctionPtr(uint32_t* baseAddr, uint32_t offset, void*** vtableFunctionPtr) {
    uintptr_t vtableOffset = 0;
    if(!LCFindDyldApiVtableOffset(baseAddr, offset, &vtableOffset)) {
        return false;
    }

    void* objectStorage = NULL;
    if(LCFindDyldApiObjectStorage(baseAddr, offset, &objectStorage) && LCBuildVtableFunctionPtrFromStorage(objectStorage, vtableOffset, vtableFunctionPtr)) {
        return true;
    }

    void* literalObjectPtr = NULL;
    if(LCFindDyldApiObjectLiteral(baseAddr, offset, &literalObjectPtr) && LCBuildVtableFunctionPtrFromObject(literalObjectPtr, vtableOffset, vtableFunctionPtr)) {
        return true;
    }

    return false;
}

static bool LCTryResolveRegisterBranchStub(uint32_t* baseAddr, uint32_t** target) {
    if(!LCAddressHasProtection(baseAddr, sizeof(uint32_t) * 8, VM_PROT_READ)) {
        return false;
    }
    for(uint32_t offset = 0; offset < 4; ++offset) {
        uint32_t adrpInst = baseAddr[offset];
        if(!LCIsAdrp(adrpInst)) {
            continue;
        }
        uint32_t reg = LCInstructionRd(adrpInst);
        uintptr_t address = aarch64_emulate_adrp(adrpInst, (uint64_t)(baseAddr + offset));
        if(!address) {
            continue;
        }
        for(uint32_t i = offset + 1; i < offset + 7; ++i) {
            uint32_t instruction = baseAddr[i];
            uint32_t dst = 0;
            uint32_t src = 0;
            uint32_t imm = 0;
            if(aarch64_emulate_add_imm(instruction, &dst, &src, &imm) && dst == reg && src == reg) {
                address += imm;
                continue;
            }
            if(LCIsLdrUnsignedImmediate(instruction) && LCInstructionRn(instruction) == reg && LCInstructionRd(instruction) == reg) {
                void* resolved = NULL;
                if(!LCReadPointer((void*)(address + LCLdrUnsignedImmediateOffset(instruction)), &resolved)) {
                    return false;
                }
                address = (uintptr_t)resolved;
                continue;
            }
            if(LCIsBranchRegister(instruction) && LCInstructionRn(instruction) == reg) {
                uint32_t* candidate = (uint32_t*)address;
                if(LCAddressHasProtection(candidate, sizeof(uint32_t), VM_PROT_READ)) {
                    *target = candidate;
                    return true;
                }
                return false;
            }
        }
    }
    return false;
}

static uint32_t* LCResolveDyldThunkStart(uint32_t* baseAddr) {
    uint32_t* current = baseAddr;
    for(uint32_t depth = 0; depth < 4; ++depth) {
        if(!LCAddressHasProtection(current, sizeof(uint32_t) * 8, VM_PROT_READ)) {
            break;
        }

        uint32_t* target = NULL;
        if(LCTryResolveRegisterBranchStub(current, &target)) {
            current = target;
            continue;
        }

        bool followedBranch = false;
        for(uint32_t offset = 0; offset < 4; ++offset) {
            uint32_t instruction = current[offset];
            if(LCIsBranchImmediate(instruction)) {
                target = LCBranchImmediateTarget(current + offset, instruction);
                if(LCAddressHasProtection(target, sizeof(uint32_t), VM_PROT_READ)) {
                    current = target;
                    followedBranch = true;
                }
                break;
            }
        }
        if(!followedBranch) {
            break;
        }
    }
    return current;
}

static bool LCFindDyldApiVtableFunctionPtr(uint32_t* baseAddr, uint32_t preferredAdrpOffset, void*** vtableFunctionPtr, uint32_t* matchedAdrpOffset) {
    uint32_t* resolvedBaseAddr = LCResolveDyldThunkStart(baseAddr);
    if(resolvedBaseAddr != baseAddr) {
        NSLog(@"[LC] dyld hook followed API stub from %p to %p", baseAddr, resolvedBaseAddr);
    }

    if(LCTryFindDyldApiVtableFunctionPtr(resolvedBaseAddr, preferredAdrpOffset, vtableFunctionPtr)) {
        *matchedAdrpOffset = preferredAdrpOffset;
        return true;
    }

    if(LCTryFindDyldApiVtableFunctionPtr(resolvedBaseAddr, preferredAdrpOffset + 20, vtableFunctionPtr)) {
        *matchedAdrpOffset = preferredAdrpOffset + 20;
        return true;
    }

    for(uint32_t offset = 0; offset < 128; ++offset) {
        if(offset == preferredAdrpOffset || offset == preferredAdrpOffset + 20) {
            continue;
        }
        if(LCTryFindDyldApiVtableFunctionPtr(resolvedBaseAddr, offset, vtableFunctionPtr)) {
            *matchedAdrpOffset = offset;
            return true;
        }
    }

    return false;
}

bool performHookDyldApi(const char* functionName, uint32_t adrpOffset, void** origFunction, void* hookFunction) {
    if(LCShouldSkipDyldApiHook(functionName)) {
        return false;
    }
    
    uint32_t* baseAddr = dlsym(RTLD_DEFAULT, functionName);
    if(!baseAddr) {
        NSLog(@"[LC] dyld hook skipped: %s was not found", functionName);
        return false;
    }
    /*
     arm64e 26.4b1+ has extra 20 instructions between adrpOffset and adrp
     arm64e
     1ad450b90  e10300aa   mov     x1, x0
     1ad450b94  487b2090   adrp    x8, dyld4::gAPIs
     1ad450b98  000140f9   ldr     x0, [x8]  {dyld4::gAPIs} may contain offset
     1ad450b9c  100040f9   ldr     x16, [x0]
     1ad450ba0  f10300aa   mov     x17, x0
     1ad450ba4  517fecf2   movk    x17, #0x63fa, lsl #0x30
     1ad450ba8  301ac1da   autda   x16, x17
     1ad450bac  114780d2   mov     x17, #0x238
     1ad450bb0  1002118b   add     x16, x16, x17
     1ad450bb4  020240f9   ldr     x2, [x16]
     1ad450bb8  e30310aa   mov     x3, x16
     1ad450bbc  f00303aa   mov     x16, x3
     1ad450bc0  7085f3f2   movk    x16, #0x9c2b, lsl #0x30
     1ad450bc4  50081fd7   braa    x2, x16

     arm64
     00000001ac934c80         mov        x1, x0
     00000001ac934c84         adrp       x8, #0x1f462d000
     00000001ac934c88         ldr        x0, [x8, #0xf88]                            ; __ZN5dyld45gDyldE
     00000001ac934c8c         ldr        x8, [x0]
     00000001ac934c90         ldr        x2, [x8, #0x258]
     00000001ac934c94         br         x2
     */
    uint32_t matchedAdrpOffset = 0;
    void** vtableFunctionPtr = 0;
    if(!LCFindDyldApiVtableFunctionPtr(baseAddr, adrpOffset, &vtableFunctionPtr, &matchedAdrpOffset)) {
        NSLog(@"[LC] dyld hook skipped: %s API thunk layout changed", functionName);
        return false;
    }
    if(matchedAdrpOffset != adrpOffset) {
        NSLog(@"[LC] dyld hook resolved moved %s thunk at instruction offset %u", functionName, matchedAdrpOffset);
    }
    
    if(!vtableFunctionPtr) {
        NSLog(@"[LC] dyld hook skipped: %s vtable function pointer was not found", functionName);
        return false;
    }
    void* originalFunction = NULL;
    if(!LCReadPointer(vtableFunctionPtr, &originalFunction) || !LCAddressHasProtection(originalFunction, sizeof(uint32_t), VM_PROT_EXECUTE)) {
        NSLog(@"[LC] dyld hook skipped: %s resolved vtable entry is not executable", functionName);
        return false;
    }
    kern_return_t ret = builtin_vm_protect(mach_task_self(), (mach_vm_address_t)vtableFunctionPtr, sizeof(uintptr_t), false, PROT_READ | PROT_WRITE | VM_PROT_COPY);
    if(ret != KERN_SUCCESS) {
        if(!os_tpro_is_supported()) {
            NSLog(@"[LC] dyld hook skipped: %s vm_protect failed: %d", functionName, ret);
            return false;
        }
        os_thread_self_restrict_tpro_to_rw();
    }
    *origFunction = originalFunction;
    *(uint64_t*)vtableFunctionPtr = (uint64_t)hookFunction;
    builtin_vm_protect(mach_task_self(), (mach_vm_address_t)vtableFunctionPtr, sizeof(uintptr_t), false, PROT_READ);
    if(ret != KERN_SUCCESS && os_tpro_is_supported()) {
        os_thread_self_restrict_tpro_to_ro();
    }
    return true;
}

bool initGuestSDKVersionInfo(void) {
    void* dyldBase = getDyldBase();
    if(!dyldBase) {
        NSLog(@"[LC] SDK spoof disabled: dyld base was not found");
        return false;
    }
    // it seems Apple is constantly changing findVersionSetEquivalent's signature so we directly search sVersionMap instead
    uint32_t* versionMapPtr = getCachedSymbol(@"__ZN5dyld3L11sVersionMapE", dyldBase);
    if(!versionMapPtr) {
#if !TARGET_OS_SIMULATOR
        const char* dyldPath = "/usr/lib/dyld";
        uint64_t offset = LCFindSymbolOffset(dyldPath, "__ZN5dyld3L11sVersionMapE");
#else
        void *result = litehook_find_symbol(dyldBase, "__ZN5dyld3L11sVersionMapE");
        uint64_t offset = result ? (uint64_t)result - (uint64_t)dyldBase : 0;
#endif
        if(offset == 0) {
            NSLog(@"[LC] SDK spoof disabled: dyld version map symbol was not found");
            return false;
        }
        versionMapPtr = dyldBase + offset;
        saveCachedSymbol(@"__ZN5dyld3L11sVersionMapE", dyldBase, offset);
    }
    
    if(!versionMapPtr) {
        NSLog(@"[LC] SDK spoof disabled: dyld version map was not found");
        return false;
    }
    // however sVersionMap's struct size is also unknown, but we can figure it out
    // we assume the size is 10K so we won't need to change this line until maybe iOS 40
    uint32_t* versionMapEnd = versionMapPtr + 2560;
    // ensure the first is versionSet and the third is iOS version (5.0.0)
    if(versionMapPtr[0] != 0x07db0901 || versionMapPtr[2] != 0x00050000) {
        NSLog(@"[LC] SDK spoof disabled: dyld version map layout changed");
        return false;
    }
    // get struct size. we assume size is smaller then 128. appearently Apple won't have so many platforms
    uint32_t size = 0;
    for(int i = 1; i < 128; ++i) {
        // find the next versionSet (for 6.0.0)
        if(versionMapPtr[i] == 0x07dc0901) {
            size = i;
            break;
        }
    }
    if(!size) {
        NSLog(@"[LC] SDK spoof disabled: dyld version map size was not detected");
        return false;
    }
    
    NSOperatingSystemVersion currentVersion = [[NSProcessInfo processInfo] operatingSystemVersion];
    uint32_t maxVersion = ((uint32_t)currentVersion.majorVersion << 16) | ((uint32_t)currentVersion.minorVersion << 8);
    
    uint32_t candidateVersion = 0;
    uint32_t candidateVersionEquivalent = 0;
    uint32_t newVersionSetVersion = 0;
    for(uint32_t* nowVersionMapItem = versionMapPtr; nowVersionMapItem < versionMapEnd; nowVersionMapItem += size) {
        newVersionSetVersion = nowVersionMapItem[2];
        if (newVersionSetVersion > guestAppSdkVersion) { break; }
        candidateVersion = newVersionSetVersion;
        candidateVersionEquivalent = nowVersionMapItem[0];
        if(newVersionSetVersion >= maxVersion) { break; }
    }
    
    if (newVersionSetVersion == 0xffffffff && candidateVersion == 0) {
        candidateVersionEquivalent = newVersionSetVersion;
    }

    guestAppSdkVersionSet = candidateVersionEquivalent;
    
    return true;
}

#if TARGET_OS_MACCATALYST || TARGET_OS_SIMULATOR
void DyldHookLoadableIntoProcess(void) {
    uint32_t *patchAddr = (uint32_t *)litehook_find_symbol(getDyldBase(), "__ZNK6mach_o6Header19loadableIntoProcessENS_8PlatformE7CStringb");
    size_t patchSize = sizeof(uint32_t[2]);

    kern_return_t kret;
    kret = builtin_vm_protect(mach_task_self(), (vm_address_t)patchAddr, patchSize, false, PROT_READ | PROT_WRITE | VM_PROT_COPY);
    assert(kret == KERN_SUCCESS);

    patchAddr[0] = 0xD2800020; // mov x0, #1
    patchAddr[1] = 0xD65F03C0; // ret

    kret = builtin_vm_protect(mach_task_self(), (vm_address_t)patchAddr, patchSize, false, PROT_READ | PROT_EXEC);
    assert(kret == KERN_SUCCESS);
}
#endif

void DyldHooksInit(bool hideLiveContainer, bool hookDlopen, uint32_t spoofSDKVersion) {
    // iterate through loaded images and find LiveContainer it self
    int imageCount = _dyld_image_count();
    for(int i = 0; i < imageCount; ++i) {
        const struct mach_header* currentImageHeader = _dyld_get_image_header(i);
        if(currentImageHeader->filetype == MH_EXECUTE) {
            lcImageIndex = i;
            break;
        }
    }
    
    if(NSUserDefaults.isLiveProcess) {
        lcMainBundlePath = NSUserDefaults.lcMainBundle.bundlePath.stringByDeletingLastPathComponent.stringByDeletingLastPathComponent.fileSystemRepresentation;
    } else {
        lcMainBundlePath = NSUserDefaults.lcMainBundle.bundlePath.fileSystemRepresentation;
    }
    orig_dyld_get_image_header = _dyld_get_image_header;
    
    // hook dlsym to solve RTLD_MAIN_ONLY, hook other functions to hide LiveContainer itself
    litehook_rebind_symbol(LITEHOOK_REBIND_GLOBAL, dlsym, hook_dlsym, nil);
    if(hideLiveContainer) {
        litehook_rebind_symbol(LITEHOOK_REBIND_GLOBAL, _dyld_image_count, hook_dyld_image_count, nil);
        litehook_rebind_symbol(LITEHOOK_REBIND_GLOBAL, _dyld_get_image_header, hook_dyld_get_image_header, nil);
        litehook_rebind_symbol(LITEHOOK_REBIND_GLOBAL, _dyld_get_image_vmaddr_slide, hook_dyld_get_image_vmaddr_slide, nil);
        litehook_rebind_symbol(LITEHOOK_REBIND_GLOBAL, _dyld_get_image_name, hook_dyld_get_image_name, nil);
        _dyld_register_func_for_add_image((void (*)(const struct mach_header *, intptr_t))hideLiveContainerImageCallback);
    }
    
    appExecutableFileTypeOverwritten = !hideLiveContainer;
    
    if(spoofSDKVersion) {
        guestAppSdkVersion = spoofSDKVersion;
        if(!initGuestSDKVersionInfo() ||
           !performHookDyldApi("dyld_program_sdk_at_least", 1, (void**)&orig_dyld_program_sdk_at_least, hook_dyld_program_sdk_at_least) ||
           !performHookDyldApi("dyld_get_program_sdk_version", 0, (void**)&orig_dyld_get_program_sdk_version, hook_dyld_get_program_sdk_version)) {
            return;
        }
    }
    
    hookedDlopen = hookDlopen;
    if(hookDlopen) {
        litehook_rebind_symbol(LITEHOOK_REBIND_GLOBAL, dlopen, jitless_hook_dlopen, nil);
    }
    
#if TARGET_OS_MACCATALYST || TARGET_OS_SIMULATOR
    DyldHookLoadableIntoProcess();
#endif
}

void* getGuestAppHeader(void) {
    return (void*)orig_dyld_get_image_header(appMainImageIndex);
}

bool LCUpdateAppMainImageIndexForPath(const char *path) {
    if(!path) {
        return false;
    }
    NSString *targetPath = [[NSString stringWithUTF8String:path] stringByStandardizingPath];
    uint32_t imageCount = orig_dyld_image_count();
    for(uint32_t i = appMainImageIndex; i < imageCount; i++) {
        const char *imageName = orig_dyld_get_image_name(i);
        if(!imageName) {
            continue;
        }
        NSString *imagePath = [[NSString stringWithUTF8String:imageName] stringByStandardizingPath];
        if([imagePath isEqualToString:targetPath]) {
            appMainImageIndex = i;
            return true;
        }
    }
    return false;
}

#pragma mark - Fix black screen
#if !TARGET_OS_SIMULATOR
#define HOOK_LOCK_1ST_ARG void *ptr,
#else
#define HOOK_LOCK_1ST_ARG
#endif
static void *lockPtrToIgnore;
static mach_port_t tidToIgnore;
void hook_libdyld_os_unfair_recursive_lock_lock_with_options(HOOK_LOCK_1ST_ARG void* lock, uint32_t options) {
    if(!lockPtrToIgnore) lockPtrToIgnore = lock;
    if(lock != lockPtrToIgnore || tidToIgnore != mach_thread_self()) {
        os_unfair_recursive_lock_lock_with_options(lock, options);
    }
}
void hook_libdyld_os_unfair_recursive_lock_unlock(HOOK_LOCK_1ST_ARG void* lock) {
    if(lock != lockPtrToIgnore || tidToIgnore != mach_thread_self()) {
        os_unfair_recursive_lock_unlock(lock);
    }
}

bool hook_libdyld_os_unfair_recursive_lock_trylock(HOOK_LOCK_1ST_ARG void* lock) {
    if(!lockPtrToIgnore) lockPtrToIgnore = lock;
    if(lock != lockPtrToIgnore || tidToIgnore != mach_thread_self()) {
        return os_unfair_recursive_lock_trylock(lock);
    }
    return true;
}

// return index of that function in vtable
int searchVtable(void** vtable, void *func) {
    for(int i = 0; i < 100; ++i) {
        if(vtable[i] == func) {
            return i;
        }
    }
    return -1;
}

#if is32BitSupported
void LCClearDlopen32BitLayerReroute(void) {
    lcDlopenReroutedTo32BitLayer = false;
    lcDlopen32BitLayerPath[0] = 0;
}

bool LCWasDlopenReroutedTo32BitLayer(void) {
    return lcDlopenReroutedTo32BitLayer;
}

const char *LCLastDlopen32BitLayerPath(void) {
    return lcDlopen32BitLayerPath[0] ? lcDlopen32BitLayerPath : NULL;
}

static bool LCShouldRerouteDlopenTo32BitLayer(const char *path) {
    if(!path) {
        return false;
    }
    NSString *pathString = [NSString stringWithUTF8String:path];
    if(![pathString containsString:@"/Documents/Applications/"] ||
       ![pathString containsString:@".app/"] ||
       [pathString containsString:@"/Frameworks/"] ||
       [pathString.pathExtension length] > 0) {
        return false;
    }
    __block bool has64bitSlice = false;
    NSString *error = LCParseMachO(path, true, ^(const char *path, struct mach_header_64 *header, int fd, void *filePtr) {
        if(header->cputype == CPU_TYPE_ARM64) {
            has64bitSlice = true;
        }
    });
    if(error) {
        return false;
    }
    return !has64bitSlice;
}

static NSString *LCResolveBundled32BitLayerExecPathForDlopen(void) {
    NSFileManager *fm = NSFileManager.defaultManager;
    const char *homePath = getenv("LC_HOME_PATH");
    if(homePath) {
        NSString *documentsLayer = [NSString stringWithFormat:@"%s/Documents/LiveExec32.app/LiveExec32", homePath];
        if([fm fileExistsAtPath:documentsLayer]) {
            return documentsLayer;
        }
    }

    NSString *bundlePath = NSBundle.mainBundle.bundlePath;
    if([bundlePath hasSuffix:@"PlugIns/LiveProcess.appex"]) {
        bundlePath = bundlePath.stringByDeletingLastPathComponent.stringByDeletingLastPathComponent;
    }
    NSString *bundledLayer = [bundlePath stringByAppendingPathComponent:@"LiveExec32.app/LiveExec32"];
    if([fm fileExistsAtPath:bundledLayer]) {
        return bundledLayer;
    }
    return nil;
}
#endif

void *dlopen_nolock(const char *path, int mode) {
#if is32BitSupported
    const char *pathToOpen = path;
    if(LCShouldRerouteDlopenTo32BitLayer(path)) {
        NSString *layerExecPath = LCResolveBundled32BitLayerExecPathForDlopen();
        if(layerExecPath && [layerExecPath getFileSystemRepresentation:lcDlopen32BitLayerPath maxLength:sizeof(lcDlopen32BitLayerPath)]) {
            lcDlopenReroutedTo32BitLayer = true;
            pathToOpen = lcDlopen32BitLayerPath;
            NSLog(@"[LC] Rerouting 32-bit guest dlopen from %s to %s", path, pathToOpen);
        } else {
            NSLog(@"[LC] Could not resolve LiveExec32 for 32-bit guest dlopen: %s", path);
        }
    }
#else
    const char *pathToOpen = path;
#endif
    tidToIgnore = mach_thread_self();
    const char *libdyldPath = "/usr/lib/system/libdyld.dylib";
    mach_header_u *libdyldHeader = LCGetLoadedImageHeader(0, libdyldPath);
    if(!libdyldHeader) {
        NSLog(@"[LC] libdyld header not found; falling back to normal dlopen");
        return hookedDlopen ? jitless_hook_dlopen(pathToOpen, mode) : dlopen(pathToOpen, mode);
    }
#if !TARGET_OS_SIMULATOR
    NSString *lockPtrName = @"dyld4::LibSystemHelpers::os_unfair_recursive_lock_lock_with_options";
    NSString *unlockPtrName = @"dyld4::LibSystemHelpers::os_unfair_recursive_lock_unlock_with_options";
    NSString *tryLockPtrName = @"dyld4::LibSystemHelpers::os_unfair_recursive_lock_trylock";
    void **lockPtr = getCachedSymbol(lockPtrName, libdyldHeader);
    void **unlockPtr = getCachedSymbol(unlockPtrName, libdyldHeader);
    void **trylockPtr = 0;
    bool shouldPatchTrylock = false;
    if(@available(iOS 26.5, *)) {
        shouldPatchTrylock = true;
        trylockPtr = getCachedSymbol(tryLockPtrName, libdyldHeader);
    }
    
    if(!unlockPtr || !lockPtr || (shouldPatchTrylock && !trylockPtr)) {
        void **vtableLibSystemHelpers = litehook_find_dsc_symbol(libdyldPath, "__ZTVN5dyld416LibSystemHelpersE");
        if(!vtableLibSystemHelpers) {
            NSLog(@"[LC] dyld LibSystemHelpers vtable not found; falling back to normal dlopen");
            return hookedDlopen ? jitless_hook_dlopen(pathToOpen, mode) : dlopen(pathToOpen, mode);
        }
        
        if(!lockPtr) {
            void *lockFunc = litehook_find_dsc_symbol(libdyldPath, "__ZNK5dyld416LibSystemHelpers42os_unfair_recursive_lock_lock_with_optionsEP26os_unfair_recursive_lock_s24os_unfair_lock_options_t");
            int lockOffset = lockFunc ? searchVtable(vtableLibSystemHelpers, lockFunc) : -1;
            if(lockOffset == -1) {
                NSLog(@"[LC] dyld lock function layout changed; falling back to normal dlopen");
                return hookedDlopen ? jitless_hook_dlopen(pathToOpen, mode) : dlopen(pathToOpen, mode);
            }
            lockPtr = vtableLibSystemHelpers + lockOffset;
            saveCachedSymbol(lockPtrName, libdyldHeader, (uintptr_t)lockPtr - (uintptr_t)libdyldHeader);
        }
        
        if(!unlockPtr) {
            void *unlockFunc = litehook_find_dsc_symbol(libdyldPath, "__ZNK5dyld416LibSystemHelpers31os_unfair_recursive_lock_unlockEP26os_unfair_recursive_lock_s");
            int unlockOffset = unlockFunc ? searchVtable(vtableLibSystemHelpers, unlockFunc) : -1;
            if(unlockOffset == -1) {
                NSLog(@"[LC] dyld unlock function layout changed; falling back to normal dlopen");
                return hookedDlopen ? jitless_hook_dlopen(pathToOpen, mode) : dlopen(pathToOpen, mode);
            }
            unlockPtr = vtableLibSystemHelpers + unlockOffset;
            saveCachedSymbol(unlockPtrName, libdyldHeader, (uintptr_t)unlockPtr - (uintptr_t)libdyldHeader);
        }
        
        if(shouldPatchTrylock && !trylockPtr) {
            // after 26.5b2 dyld4::RuntimeLocks::couldDlopenLock is added and called when dlopen is called with RTLD_NO_LOAD,
            // which calls os_unfair_recursive_lock_trylock, so we should also hook that
            void *tryLockFunc = litehook_find_dsc_symbol(libdyldPath, "__ZNK5dyld416LibSystemHelpers32os_unfair_recursive_lock_trylockEP26os_unfair_recursive_lock_s");
            int trylockOffset = tryLockFunc ? searchVtable(vtableLibSystemHelpers, tryLockFunc) : -1;
            // in case people use b1, we don't use NSCAssert here
            if(trylockOffset != -1) {
                trylockPtr = vtableLibSystemHelpers + trylockOffset;
                saveCachedSymbol(tryLockPtrName, libdyldHeader, (uintptr_t)trylockPtr - (uintptr_t)libdyldHeader);
            } else {
                NSLog(@"dyld has changed: trylockOffset not found in vtable");
                shouldPatchTrylock = false;
            }
        }
    }
    
    if(!lockPtr || !unlockPtr) {
        NSLog(@"[LC] dyld lock pointers incomplete; falling back to normal dlopen");
        return hookedDlopen ? jitless_hook_dlopen(pathToOpen, mode) : dlopen(pathToOpen, mode);
    }
    kern_return_t ret;
    mach_vm_address_t vtablePageStart = (mach_vm_address_t)((uint64_t)lockPtr & ~(16384 - 1));
    
    ret = builtin_vm_protect(mach_task_self(), vtablePageStart, 16384, false, PROT_READ | PROT_WRITE | VM_PROT_COPY);
    if(ret != KERN_SUCCESS) {
        if(!os_tpro_is_supported()) {
            NSLog(@"[LC] dyld lock patch vm_protect failed; falling back to normal dlopen: %d", ret);
            return hookedDlopen ? jitless_hook_dlopen(pathToOpen, mode) : dlopen(pathToOpen, mode);
        }
        os_thread_self_restrict_tpro_to_rw();
    }
    void *origLockPtr = *lockPtr, *origUnlockPtr = *unlockPtr, *origTryLockPtr = 0;
    *lockPtr = hook_libdyld_os_unfair_recursive_lock_lock_with_options;
    *unlockPtr = hook_libdyld_os_unfair_recursive_lock_unlock;
    if(shouldPatchTrylock) {
        origTryLockPtr = *trylockPtr;
        *trylockPtr = hook_libdyld_os_unfair_recursive_lock_trylock;
    }
    
    ret = builtin_vm_protect(mach_task_self(), vtablePageStart, 16384, false, PROT_READ);
    if(ret != KERN_SUCCESS && os_tpro_is_supported()) {
        os_thread_self_restrict_tpro_to_rw();
    }
    
    void *result;
    if(hookedDlopen) {
        result = jitless_hook_dlopen(pathToOpen, mode);
    } else {
        result = dlopen(pathToOpen, mode);
    }
    
    ret = builtin_vm_protect(mach_task_self(), vtablePageStart, 16384, false, PROT_READ | PROT_WRITE);
    if(ret != KERN_SUCCESS && os_tpro_is_supported()) {
        os_thread_self_restrict_tpro_to_rw();
    }
    *lockPtr = origLockPtr;
    *unlockPtr = origUnlockPtr;
    if(shouldPatchTrylock) {
        *trylockPtr = origTryLockPtr;
    }
    
    ret = builtin_vm_protect(mach_task_self(), vtablePageStart, 16384, false, PROT_READ);
    if(ret != KERN_SUCCESS && os_tpro_is_supported()) {
        os_thread_self_restrict_tpro_to_rw();
    }
#else
    litehook_rebind_symbol(libdyldHeader, os_unfair_recursive_lock_lock_with_options, hook_libdyld_os_unfair_recursive_lock_lock_with_options, nil);
    litehook_rebind_symbol(libdyldHeader, os_unfair_recursive_lock_unlock, hook_libdyld_os_unfair_recursive_lock_unlock, nil);
    void *result = dlopen(path, mode);
    litehook_rebind_symbol(libdyldHeader, hook_libdyld_os_unfair_recursive_lock_lock_with_options, os_unfair_recursive_lock_lock_with_options, nil);
    litehook_rebind_symbol(libdyldHeader, hook_libdyld_os_unfair_recursive_lock_unlock, os_unfair_recursive_lock_unlock, nil);
#endif
    return result;
}

#pragma mark - Workaround `file system sandbox blocked mmap()`
// when using multitask app in private container, we need to temporarily hook dyld's mmap
mach_port_t excPort;
void *exception_handler(void *unused) {
    mach_msg_server(mach_exc_server, sizeof(union __RequestUnion__catch_mach_exc_subsystem), excPort, MACH_MSG_OPTION_NONE);
    abort();
}

static void *LCOrigDlopenResolvingLoaderPath(const char *path, int mode) {
    void *callerAddr = __builtin_return_address(0);
    struct dl_info info;
    if (path && !strncmp(path, "@loader_path/", 13) && dladdr(callerAddr, &info)) {
        char resolvedPath[PATH_MAX];
        snprintf(resolvedPath, sizeof(resolvedPath), "%s/%s", dirname((char *)info.dli_fname), path + 13);
        return orig_dlopen(resolvedPath, mode);
    }
    return orig_dlopen(path, mode);
}

void *jitless_hook_dlopen(const char *path, int mode) {
    if (!excPort) {
        searchDyldFunctions();
        if(!orig_dyld_mmap) {
            NSLog(@"[LC] dyld mmap function not found; falling back to normal dlopen");
            return LCOrigDlopenResolvingLoaderPath(path, mode);
        }
        mach_port_allocate(mach_task_self(), MACH_PORT_RIGHT_RECEIVE, &excPort);
        mach_port_insert_right(mach_task_self(), excPort, excPort, MACH_MSG_TYPE_MAKE_SEND);
        pthread_t thread;
        pthread_create(&thread, NULL, exception_handler, NULL);
    }
    
    // save old thread states
    exception_mask_t mask = EXC_MASK_BREAKPOINT;
    mach_msg_type_number_t masksCnt = 1;
    exception_handler_t handler = excPort;
    exception_behavior_t behavior = EXCEPTION_STATE | MACH_EXCEPTION_CODES;
    thread_state_flavor_t flavor = ARM_THREAD_STATE64;
    arm_debug_state64_t origDebugState;
    mach_port_t thread = mach_thread_self();
    kern_return_t stateRet = thread_get_state(thread, ARM_DEBUG_STATE64, (thread_state_t)&origDebugState, &(mach_msg_type_number_t){ARM_DEBUG_STATE64_COUNT});
    if(stateRet != KERN_SUCCESS) {
        NSLog(@"[LC] failed to read ARM debug state; falling back to normal dlopen: %d", stateRet);
        return LCOrigDlopenResolvingLoaderPath(path, mode);
    }
    kern_return_t swapRet = thread_swap_exception_ports(thread, mask, handler, behavior, flavor, &mask, &masksCnt, &handler, &behavior, &flavor);
    if(swapRet != KERN_SUCCESS) {
        NSLog(@"[LC] failed to install dyld mmap exception hook; falling back to normal dlopen: %d", swapRet);
        return LCOrigDlopenResolvingLoaderPath(path, mode);
    }
    if(masksCnt != 1) {
        NSLog(@"[LC] unexpected saved exception port count while hooking dyld mmap: %u", masksCnt);
    }
    
    // hook dyld's mmap
    arm_debug_state64_t hookDebugState = {
        .__bvr = {(uint64_t)orig_dyld_mmap},
        .__bcr = {0x1e5},
    };
    thread_set_state(thread, ARM_DEBUG_STATE64, (thread_state_t)&hookDebugState, ARM_DEBUG_STATE64_COUNT);
    
    // fixup @loader_path since we cannot use musttail here
    void *result = LCOrigDlopenResolvingLoaderPath(path, mode);
    
    // restore old thread states
    thread_set_state(thread, ARM_DEBUG_STATE64, (thread_state_t)&origDebugState, ARM_DEBUG_STATE64_COUNT);
    thread_swap_exception_ports(thread, mask, handler, behavior, flavor, &mask, &masksCnt, &handler, &behavior, &flavor);
    
    return result;
}

void* jitless_hook_mmap(void *addr, size_t len, int prot, int flags, int fd, off_t offset) {
    void *map = __mmap(addr, len, prot, flags, fd, offset);
    // only handle mapping __TEXT segment from fd outside of permitted path
    if (map != MAP_FAILED || !(prot & PROT_EXEC) || fd < 0) return map;
    
    // to get around `file system sandbox blocked mmap()` we temporarily move it to permitted path
    char filePath[PATH_MAX];
    if (fcntl(fd, F_GETPATH, filePath) != 0) return map;
    char newTmpPath[PATH_MAX];
    sprintf(newTmpPath, "%s/Documents/%p.dylib", getenv("LP_HOME_PATH"), addr);
    rename(filePath, newTmpPath);
    map = __mmap(addr, len, prot, flags, fd, offset);
    rename(newTmpPath, filePath);
    
    return map;
}

kern_return_t catch_mach_exception_raise_state( mach_port_t exception_port, exception_type_t exception, const mach_exception_data_t code, mach_msg_type_number_t codeCnt, int *flavor, const thread_state_t old_state, mach_msg_type_number_t old_stateCnt, thread_state_t new_state, mach_msg_type_number_t *new_stateCnt) {
    arm_thread_state64_t *old = (arm_thread_state64_t *)old_state;
    arm_thread_state64_t *new = (arm_thread_state64_t *)new_state;
    uint64_t pc = arm_thread_state64_get_pc(*old);
    // TODO: merge with dyld bypass?
    if(pc == (uint64_t)orig_dyld_mmap) {
        *new = *old;
        *new_stateCnt = old_stateCnt;
        arm_thread_state64_set_pc_fptr(*new, jitless_hook_mmap);
        return KERN_SUCCESS;
    }
    NSLog(@"[DyldLVBypass] Unknown breakpoint at pc: %p", (void*)pc);
    return KERN_FAILURE;
}

kern_return_t catch_mach_exception_raise(mach_port_t exception_port, mach_port_t thread, mach_port_t task, exception_type_t exception, mach_exception_data_t code, mach_msg_type_number_t codeCnt) {
    abort();
}

kern_return_t catch_mach_exception_raise_state_identity(mach_port_t exception_port, mach_port_t thread, mach_port_t task, exception_type_t exception, mach_exception_data_t code, mach_msg_type_number_t codeCnt, int *flavor, thread_state_t old_state, mach_msg_type_number_t old_stateCnt, thread_state_t new_state, mach_msg_type_number_t *new_stateCnt) {
    abort();
}
