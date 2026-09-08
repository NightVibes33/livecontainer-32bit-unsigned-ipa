#!/usr/bin/env python3
from pathlib import Path
p=Path("build/LiveExec32/GuestFrameworks/CoreMedia/CoreMedia.m")
s=p.read_text()
if "LC32BlockBufferStorage" not in s:
    s += r"""

#pragma mark - Guest-owned contiguous CMBlockBuffer
#import <Foundation/Foundation.h>

typedef struct {
    void *block;
    size_t length;
    CFAllocatorRef allocator;
    CMBlockBufferCustomBlockSource source;
    Boolean custom;
    Boolean shouldFree;
} LC32BlockBufferStorage;

@interface LC32BlockBuffer : NSObject {
@public
    NSMutableData *data;
    LC32BlockBufferStorage *storage;
    size_t storageCount;
    size_t storageCapacity;
}
@end

@implementation LC32BlockBuffer
- (id)init {
    if((self = [super init])) data = [NSMutableData new];
    return self;
}
- (void)dealloc {
    for(size_t i = 0; i < storageCount; i++) {
        LC32BlockBufferStorage *entry = &storage[i];
        if(!entry->shouldFree || !entry->block) continue;
        if(entry->custom && entry->source.FreeBlock) {
            entry->source.FreeBlock(entry->source.refCon,
                                    entry->block, entry->length);
        } else {
            CFAllocatorDeallocate(entry->allocator ?: kCFAllocatorDefault,
                                  entry->block);
        }
        if(entry->allocator) CFRelease(entry->allocator);
    }
    free(storage);
    [data release];
    [super dealloc];
}
@end

static LC32BlockBuffer *LC32BB(CMBlockBufferRef value) {
    id object = (id)value;
    return [object isKindOfClass:[LC32BlockBuffer class]]
        ? (LC32BlockBuffer *)object : nil;
}

static Boolean LC32BlockBufferRemember(LC32BlockBuffer *buffer,
                                       LC32BlockBufferStorage entry) {
    if(!entry.shouldFree) return true;
    if(buffer->storageCount == buffer->storageCapacity) {
        size_t capacity = buffer->storageCapacity
            ? buffer->storageCapacity * 2 : 4;
        if(capacity < buffer->storageCapacity ||
           capacity > SIZE_MAX / sizeof(*buffer->storage)) return false;
        void *grown = realloc(buffer->storage,
                              capacity * sizeof(*buffer->storage));
        if(!grown) return false;
        buffer->storage = grown;
        buffer->storageCapacity = capacity;
    }
    if(entry.allocator) CFRetain(entry.allocator);
    buffer->storage[buffer->storageCount++] = entry;
    return true;
}

OSStatus CMBlockBufferCreateEmpty(CFAllocatorRef allocator,
                                  uint32_t capacity,
                                  CMBlockBufferFlags flags,
                                  CMBlockBufferRef *out) {
    (void)allocator; (void)capacity; (void)flags;
    if(!out) return kCMBlockBufferBadPointerParameterErr;
    *out = NULL;
    LC32BlockBuffer *buffer = [LC32BlockBuffer new];
    if(!buffer) return kCMBlockBufferStructureAllocationFailedErr;
    *out = (CMBlockBufferRef)buffer;
    return kCMBlockBufferNoErr;
}

OSStatus CMBlockBufferAppendMemoryBlock(
    CMBlockBufferRef value, void *memoryBlock, size_t blockLength,
    CFAllocatorRef blockAllocator,
    const CMBlockBufferCustomBlockSource *customBlockSource,
    size_t offsetToData, size_t dataLength, CMBlockBufferFlags flags) {
    (void)flags;
    LC32BlockBuffer *buffer = LC32BB(value);
    if(!buffer) return kCMBlockBufferBadPointerParameterErr;
    if(offsetToData > blockLength || dataLength > blockLength - offsetToData)
        return kCMBlockBufferBadLengthParameterErr;
    if(customBlockSource && customBlockSource->version != 0)
        return kCMBlockBufferBadCustomBlockSourceErr;

    LC32BlockBufferStorage entry = {0};
    entry.block = memoryBlock;
    entry.length = blockLength;
    entry.allocator = blockAllocator;
    entry.custom = customBlockSource != NULL;
    if(customBlockSource) entry.source = *customBlockSource;

    if(!entry.block && blockLength) {
        if(customBlockSource && customBlockSource->AllocateBlock)
            entry.block = customBlockSource->AllocateBlock(
                customBlockSource->refCon, blockLength);
        else
            entry.block = CFAllocatorAllocate(
                blockAllocator ?: kCFAllocatorDefault, blockLength, 0);
        if(!entry.block) return kCMBlockBufferBlockAllocationFailedErr;
        entry.shouldFree = true;
    } else if(entry.block && blockAllocator != kCFAllocatorNull) {
        entry.shouldFree = true;
    }

    NSUInteger oldLength = [buffer->data length];
    if(dataLength > NSUIntegerMax - oldLength) {
        if(entry.shouldFree) {
            if(entry.custom && entry.source.FreeBlock)
                entry.source.FreeBlock(entry.source.refCon,
                                       entry.block, entry.length);
            else
                CFAllocatorDeallocate(entry.allocator ?: kCFAllocatorDefault,
                                      entry.block);
        }
        return kCMBlockBufferBadLengthParameterErr;
    }
    @try {
        [buffer->data increaseLengthBy:dataLength];
    } @catch(id exception) {
        (void)exception;
        if(entry.shouldFree) {
            if(entry.custom && entry.source.FreeBlock)
                entry.source.FreeBlock(entry.source.refCon,
                                       entry.block, entry.length);
            else
                CFAllocatorDeallocate(entry.allocator ?: kCFAllocatorDefault,
                                      entry.block);
        }
        return kCMBlockBufferBlockAllocationFailedErr;
    }
    if(dataLength)
        memcpy((uint8_t *)[buffer->data mutableBytes] + oldLength,
               (uint8_t *)entry.block + offsetToData, dataLength);
    if(!LC32BlockBufferRemember(buffer, entry)) {
        [buffer->data setLength:oldLength];
        if(entry.shouldFree) {
            if(entry.custom && entry.source.FreeBlock)
                entry.source.FreeBlock(entry.source.refCon,
                                       entry.block, entry.length);
            else
                CFAllocatorDeallocate(entry.allocator ?: kCFAllocatorDefault,
                                      entry.block);
        }
        return kCMBlockBufferStructureAllocationFailedErr;
    }
    return kCMBlockBufferNoErr;
}

size_t CMBlockBufferGetDataLength(CMBlockBufferRef value) {
    LC32BlockBuffer *buffer = LC32BB(value);
    return buffer ? [buffer->data length] : 0;
}

OSStatus CMBlockBufferGetDataPointer(CMBlockBufferRef value, size_t offset,
                                     size_t *lengthAtOffset,
                                     size_t *totalLength, char **pointer) {
    LC32BlockBuffer *buffer = LC32BB(value);
    if(!buffer || !pointer) return kCMBlockBufferBadPointerParameterErr;
    size_t length = [buffer->data length];
    if(offset > length) return kCMBlockBufferBadOffsetParameterErr;
    if(lengthAtOffset) *lengthAtOffset = length - offset;
    if(totalLength) *totalLength = length;
    *pointer = (char *)[buffer->data mutableBytes] + offset;
    return kCMBlockBufferNoErr;
}

OSStatus CMBlockBufferAccessDataBytes(CMBlockBufferRef value, size_t offset,
                                      size_t length, void *temporaryBlock,
                                      char **returnedPointer) {
    (void)temporaryBlock;
    LC32BlockBuffer *buffer = LC32BB(value);
    if(!buffer || !returnedPointer)
        return kCMBlockBufferBadPointerParameterErr;
    size_t total = [buffer->data length];
    if(offset > total || length > total - offset)
        return kCMBlockBufferBadLengthParameterErr;
    *returnedPointer = (char *)[buffer->data mutableBytes] + offset;
    return kCMBlockBufferNoErr;
}
"""
    p.write_text(s)
print("CoreMedia: added checked guest-owned contiguous CMBlockBuffer behavior")
