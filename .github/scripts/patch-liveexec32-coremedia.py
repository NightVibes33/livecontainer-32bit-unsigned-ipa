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


p=Path("build/LiveExec32/GuestFrameworks/CoreMedia/CoreMedia.m")
s=p.read_text()
if "LC32SampleBuffer" not in s:
    s += r"""

#pragma mark - Guest-owned CMFormatDescription and CMSampleBuffer
#import <CoreVideo/CoreVideo.h>

typedef struct {
    CMMediaType mediaType;
    FourCharCode mediaSubtype;
    CMVideoDimensions dimensions;
    AudioStreamBasicDescription audio;
    Boolean hasAudio;
} LC32FormatDescriptionFields;

@interface LC32FormatDescription : NSObject {
@public
    LC32FormatDescriptionFields fields;
}
@end
@implementation LC32FormatDescription @end

@interface LC32SampleBuffer : NSObject {
@public
    CMBlockBufferRef dataBuffer;
    CVImageBufferRef imageBuffer;
    CMFormatDescriptionRef format;
    CMSampleBufferMakeDataReadyCallback makeReady;
    void *makeReadyRefcon;
    Boolean ready;
    Boolean valid;
    CMItemCount sampleCount;
    CMSampleTimingInfo *timing;
    CMItemCount timingCount;
    NSMutableArray *sampleAttachments;
}
@end

@implementation LC32SampleBuffer
- (id)init {
    if((self = [super init])) valid = true;
    return self;
}
- (void)dealloc {
    if(dataBuffer) CFRelease(dataBuffer);
    if(imageBuffer) CFRelease(imageBuffer);
    if(format) CFRelease(format);
    free(timing);
    [sampleAttachments release];
    [super dealloc];
}
@end

static LC32SampleBuffer *LC32SB(CMSampleBufferRef value) {
    id object = (id)value;
    return [object isKindOfClass:[LC32SampleBuffer class]]
        ? (LC32SampleBuffer *)object : nil;
}

OSStatus CMAudioFormatDescriptionCreate(
    CFAllocatorRef allocator, const AudioStreamBasicDescription *asbd,
    size_t layoutSize, const AudioChannelLayout *layout,
    size_t magicCookieSize, const void *magicCookie,
    CFDictionaryRef extensions, CMAudioFormatDescriptionRef *out) {
    (void)allocator; (void)extensions;
    if(!out || !asbd || (layoutSize && !layout) ||
       (magicCookieSize && !magicCookie))
        return kCMFormatDescriptionError_InvalidParameter;
    *out = NULL;
    LC32FormatDescription *description = [LC32FormatDescription new];
    if(!description) return kCMFormatDescriptionError_AllocationFailed;
    description->fields.mediaType = kCMMediaType_Audio;
    description->fields.mediaSubtype = asbd->mFormatID;
    description->fields.audio = *asbd;
    description->fields.hasAudio = true;
    *out = (CMAudioFormatDescriptionRef)description;
    return noErr;
}

const AudioStreamBasicDescription *
CMAudioFormatDescriptionGetStreamBasicDescription(
    CMAudioFormatDescriptionRef value) {
    id object = (id)value;
    if(![object isKindOfClass:[LC32FormatDescription class]]) return NULL;
    LC32FormatDescription *description = (LC32FormatDescription *)object;
    return description->fields.hasAudio ? &description->fields.audio : NULL;
}

OSStatus CMVideoFormatDescriptionCreateForImageBuffer(
    CFAllocatorRef allocator, CVImageBufferRef imageBuffer,
    CMVideoFormatDescriptionRef *out) {
    (void)allocator;
    if(!out || !imageBuffer) return kCMFormatDescriptionError_InvalidParameter;
    *out = NULL;
    size_t width = CVPixelBufferGetWidth((CVPixelBufferRef)imageBuffer);
    size_t height = CVPixelBufferGetHeight((CVPixelBufferRef)imageBuffer);
    if(!width || !height || width > INT32_MAX || height > INT32_MAX)
        return kCMFormatDescriptionError_InvalidParameter;
    LC32FormatDescription *description = [LC32FormatDescription new];
    if(!description) return kCMFormatDescriptionError_AllocationFailed;
    description->fields.mediaType = kCMMediaType_Video;
    description->fields.mediaSubtype =
        CVPixelBufferGetPixelFormatType((CVPixelBufferRef)imageBuffer);
    description->fields.dimensions = (CMVideoDimensions){
        (int32_t)width, (int32_t)height
    };
    *out = (CMVideoFormatDescriptionRef)description;
    return noErr;
}

static OSStatus LC32SampleBufferAllocate(
    CMBlockBufferRef dataBuffer, CVImageBufferRef imageBuffer,
    Boolean dataReady, CMSampleBufferMakeDataReadyCallback makeReady,
    void *makeReadyRefcon, CMFormatDescriptionRef format,
    CMItemCount sampleCount, CMItemCount timingCount,
    const CMSampleTimingInfo *timing, CMSampleBufferRef *out) {
    if(!out || sampleCount < 0 || timingCount < 0 ||
       (timingCount && !timing) ||
       (timingCount != 0 && timingCount != 1 && timingCount != sampleCount))
        return kCMSampleBufferError_InvalidEntryCount;
    *out = NULL;
    LC32SampleBuffer *sample = [LC32SampleBuffer new];
    if(!sample) return kCMSampleBufferError_AllocationFailed;
    if(dataBuffer) sample->dataBuffer = (CMBlockBufferRef)CFRetain(dataBuffer);
    if(imageBuffer) sample->imageBuffer = (CVImageBufferRef)CFRetain(imageBuffer);
    if(format) sample->format = (CMFormatDescriptionRef)CFRetain(format);
    sample->ready = dataReady;
    sample->makeReady = makeReady;
    sample->makeReadyRefcon = makeReadyRefcon;
    sample->sampleCount = sampleCount;
    sample->timingCount = timingCount;
    if(timingCount) {
        if((size_t)timingCount > SIZE_MAX / sizeof(*sample->timing)) {
            [sample release];
            return kCMSampleBufferError_AllocationFailed;
        }
        sample->timing = malloc((size_t)timingCount * sizeof(*sample->timing));
        if(!sample->timing) {
            [sample release];
            return kCMSampleBufferError_AllocationFailed;
        }
        memcpy(sample->timing, timing,
               (size_t)timingCount * sizeof(*sample->timing));
    }
    *out = (CMSampleBufferRef)sample;
    return noErr;
}

OSStatus CMSampleBufferCreate(
    CFAllocatorRef allocator, CMBlockBufferRef dataBuffer, Boolean dataReady,
    CMSampleBufferMakeDataReadyCallback makeDataReadyCallback,
    void *makeDataReadyRefcon, CMFormatDescriptionRef formatDescription,
    CMItemCount numSamples, CMItemCount numSampleTimingEntries,
    const CMSampleTimingInfo *sampleTimingArray,
    CMItemCount numSampleSizeEntries, const size_t *sampleSizeArray,
    CMSampleBufferRef *out) {
    (void)allocator;
    if(numSampleSizeEntries < 0 ||
       (numSampleSizeEntries && !sampleSizeArray) ||
       (numSampleSizeEntries != 0 && numSampleSizeEntries != 1 &&
        numSampleSizeEntries != numSamples))
        return kCMSampleBufferError_InvalidEntryCount;
    return LC32SampleBufferAllocate(dataBuffer, NULL, dataReady,
        makeDataReadyCallback, makeDataReadyRefcon, formatDescription,
        numSamples, numSampleTimingEntries, sampleTimingArray, out);
}

OSStatus CMSampleBufferCreateForImageBuffer(
    CFAllocatorRef allocator, CVImageBufferRef imageBuffer, Boolean dataReady,
    CMSampleBufferMakeDataReadyCallback makeDataReadyCallback,
    void *makeDataReadyRefcon, CMVideoFormatDescriptionRef formatDescription,
    const CMSampleTimingInfo *sampleTiming, CMSampleBufferRef *out) {
    (void)allocator;
    if(!imageBuffer || !formatDescription || !sampleTiming)
        return kCMSampleBufferError_RequiredParameterMissing;
    return LC32SampleBufferAllocate(NULL, imageBuffer, dataReady,
        makeDataReadyCallback, makeDataReadyRefcon,
        (CMFormatDescriptionRef)formatDescription, 1, 1, sampleTiming, out);
}

Boolean CMSampleBufferDataIsReady(CMSampleBufferRef value) {
    LC32SampleBuffer *sample = LC32SB(value);
    if(!sample || !sample->valid) return false;
    if(!sample->ready && sample->makeReady) {
        CMSampleBufferMakeDataReadyCallback callback = sample->makeReady;
        sample->makeReady = NULL;
        if(callback(value, sample->makeReadyRefcon) == noErr)
            sample->ready = true;
    }
    return sample->ready;
}

CMBlockBufferRef CMSampleBufferGetDataBuffer(CMSampleBufferRef value) {
    LC32SampleBuffer *sample = LC32SB(value);
    return sample && sample->valid ? sample->dataBuffer : NULL;
}

CMFormatDescriptionRef CMSampleBufferGetFormatDescription(
    CMSampleBufferRef value) {
    LC32SampleBuffer *sample = LC32SB(value);
    return sample && sample->valid ? sample->format : NULL;
}

CVImageBufferRef CMSampleBufferGetImageBuffer(CMSampleBufferRef value) {
    LC32SampleBuffer *sample = LC32SB(value);
    return sample && sample->valid ? sample->imageBuffer : NULL;
}

CMItemCount CMSampleBufferGetNumSamples(CMSampleBufferRef value) {
    LC32SampleBuffer *sample = LC32SB(value);
    return sample && sample->valid ? sample->sampleCount : 0;
}

CMTime CMSampleBufferGetPresentationTimeStamp(CMSampleBufferRef value) {
    LC32SampleBuffer *sample = LC32SB(value);
    return sample && sample->valid && sample->timingCount
        ? sample->timing[0].presentationTimeStamp : kCMTimeInvalid;
}

CMTime CMSampleBufferGetOutputPresentationTimeStamp(CMSampleBufferRef value) {
    return CMSampleBufferGetPresentationTimeStamp(value);
}

CFArrayRef CMSampleBufferGetSampleAttachmentsArray(CMSampleBufferRef value,
                                                   Boolean createIfNecessary) {
    LC32SampleBuffer *sample = LC32SB(value);
    if(!sample || !sample->valid) return NULL;
    if(!sample->sampleAttachments && createIfNecessary) {
        sample->sampleAttachments = [NSMutableArray new];
        for(CMItemCount i = 0; i < sample->sampleCount; i++)
            [sample->sampleAttachments addObject:[NSMutableDictionary dictionary]];
    }
    return (CFArrayRef)sample->sampleAttachments;
}

OSStatus CMSampleBufferGetSampleTimingInfoArray(
    CMSampleBufferRef value, CMItemCount entryCount,
    CMSampleTimingInfo *arrayToFill, CMItemCount *entriesNeededOut) {
    LC32SampleBuffer *sample = LC32SB(value);
    if(!sample || !sample->valid || entryCount < 0 ||
       (entryCount && !arrayToFill))
        return kCMSampleBufferError_InvalidMediaFormat;
    if(entriesNeededOut) *entriesNeededOut = sample->timingCount;
    CMItemCount copyCount = entryCount < sample->timingCount
        ? entryCount : sample->timingCount;
    if(copyCount)
        memcpy(arrayToFill, sample->timing,
               (size_t)copyCount * sizeof(*arrayToFill));
    if(entryCount == 0 && !arrayToFill) return noErr;
    return entryCount < sample->timingCount
        ? kCMSampleBufferError_ArrayTooSmall : noErr;
}

OSStatus CMSampleBufferGetAudioBufferListWithRetainedBlockBuffer(
    CMSampleBufferRef value, size_t *sizeNeededOut,
    AudioBufferList *bufferListOut, size_t bufferListSize,
    CFAllocatorRef structureAllocator, CFAllocatorRef blockAllocator,
    uint32_t flags, CMBlockBufferRef *blockBufferOut) {
    (void)structureAllocator; (void)blockAllocator; (void)flags;
    LC32SampleBuffer *sample = LC32SB(value);
    const size_t needed = offsetof(AudioBufferList, mBuffers) +
        sizeof(AudioBuffer);
    if(sizeNeededOut) *sizeNeededOut = needed;
    if(blockBufferOut) *blockBufferOut = NULL;
    if(!sample || !sample->valid || !sample->ready || !sample->dataBuffer)
        return kCMSampleBufferError_BufferNotReady;
    const AudioStreamBasicDescription *asbd =
        sample->format ? CMAudioFormatDescriptionGetStreamBasicDescription(
            (CMAudioFormatDescriptionRef)sample->format) : NULL;
    if(!asbd) return kCMSampleBufferError_InvalidMediaFormat;
    if(!bufferListOut || bufferListSize < needed)
        return kCMSampleBufferError_ArrayTooSmall;
    size_t atOffset = 0, total = 0;
    char *bytes = NULL;
    OSStatus status = CMBlockBufferGetDataPointer(sample->dataBuffer, 0,
        &atOffset, &total, &bytes);
    if(status != noErr || atOffset < total || total > UINT32_MAX)
        return kCMSampleBufferError_InvalidMediaFormat;
    memset(bufferListOut, 0, needed);
    bufferListOut->mNumberBuffers = 1;
    bufferListOut->mBuffers[0].mNumberChannels = asbd->mChannelsPerFrame;
    bufferListOut->mBuffers[0].mDataByteSize = (UInt32)total;
    bufferListOut->mBuffers[0].mData = bytes;
    if(blockBufferOut)
        *blockBufferOut = (CMBlockBufferRef)CFRetain(sample->dataBuffer);
    return noErr;
}

OSStatus CMSampleBufferInvalidate(CMSampleBufferRef value) {
    LC32SampleBuffer *sample = LC32SB(value);
    if(!sample) return kCMSampleBufferError_Invalidated;
    sample->valid = false;
    sample->ready = false;
    sample->makeReady = NULL;
    return noErr;
}
"""
    p.write_text(s)
print("CoreMedia: added owned video descriptions and timed sample buffers")
