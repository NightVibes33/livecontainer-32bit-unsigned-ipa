#import <CoreMedia/CoreMedia.h>
#import <CoreVideo/CoreVideo.h>
#include <assert.h>
#include <stdlib.h>
#include <string.h>
static int allocations, frees, readyCalls;
static OSStatus makeReady(CMSampleBufferRef sample, void *context) {
    assert(sample && context == (void *)0x5678); readyCalls++; return noErr;
}
static void *allocateBlock(void *context, size_t size) {
    assert(context == (void *)0x1234); allocations++;
    unsigned char *p = malloc(size); memset(p, 0x31, size); return p;
}
static void freeBlock(void *context, void *memory, size_t size) {
    assert(context == (void *)0x1234 && size == 8); frees++; free(memory);
}
int main(void) {
    CMBlockBufferRef block = 0;
    assert(CMBlockBufferCreateEmpty(0, 2, 0, &block) == noErr && block);
    unsigned char first[] = {0,1,2,3,4,5};
    assert(CMBlockBufferAppendMemoryBlock(block, first, sizeof(first),
        kCFAllocatorNull, 0, 1, 4, 0) == noErr);
    CMBlockBufferCustomBlockSource source;
    memset(&source, 0, sizeof(source));
    source.version = 0;
    source.AllocateBlock = allocateBlock;
    source.FreeBlock = freeBlock;
    source.refCon = (void *)0x1234;
    assert(CMBlockBufferAppendMemoryBlock(block, 0, 8, 0, &source,
        2, 3, 0) == noErr);
    assert(allocations == 1 && frees == 0);
    assert(CMBlockBufferGetDataLength(block) == 7);
    size_t at = 0, total = 0; char *bytes = 0;
    assert(CMBlockBufferGetDataPointer(block, 2, &at, &total, &bytes) == noErr);
    assert(at == 5 && total == 7 && bytes[0] == 3);
    bytes[0] = 9;
    char temporary[4], *range = 0;
    assert(CMBlockBufferAccessDataBytes(block, 1, 4, temporary, &range) == noErr);
    assert(range[1] == 9 && range[3] == 0x31);
    assert(CMBlockBufferAccessDataBytes(block, 6, 2, temporary, &range) != noErr);

    CVPixelBufferRef pixel = 0;
    assert(CVPixelBufferCreate(0, 8, 6, kCVPixelFormatType_32BGRA,
                               0, &pixel) == noErr && pixel);
    CMVideoFormatDescriptionRef format = 0;
    assert(CMVideoFormatDescriptionCreateForImageBuffer(0, pixel,
                                                        &format) == noErr);
    CMSampleTimingInfo timing = {
        CMTimeMake(1, 30), CMTimeMake(10, 30), kCMTimeInvalid
    };
    CMSampleBufferRef imageSample = 0;
    assert(CMSampleBufferCreateForImageBuffer(0, pixel, true, 0, 0,
        format, &timing, &imageSample) == noErr && imageSample);
    assert(CMSampleBufferDataIsReady(imageSample));
    assert(CMSampleBufferGetImageBuffer(imageSample) == pixel);
    assert(CMSampleBufferGetFormatDescription(imageSample) == format);
    assert(CMSampleBufferGetDataBuffer(imageSample) == 0);
    assert(CMSampleBufferGetNumSamples(imageSample) == 1);
    assert(CMTimeGetSeconds(CMSampleBufferGetPresentationTimeStamp(imageSample))
           == CMTimeGetSeconds(timing.presentationTimeStamp));
    assert(CMTimeGetSeconds(CMSampleBufferGetOutputPresentationTimeStamp(imageSample))
           == CMTimeGetSeconds(timing.presentationTimeStamp));
    assert(CFArrayGetCount(CMSampleBufferGetSampleAttachmentsArray(
        imageSample, true)) == 1);
    CMItemCount needed = 0;
    assert(CMSampleBufferGetSampleTimingInfoArray(imageSample, 0, 0,
                                                  &needed) == noErr);
    assert(needed == 1);
    CMSampleTimingInfo copied;
    assert(CMSampleBufferGetSampleTimingInfoArray(imageSample, 1, &copied,
                                                  &needed) == noErr);
    assert(CMTimeGetSeconds(copied.duration) == CMTimeGetSeconds(timing.duration));

    CMSampleBufferRef dataSample = 0;
    size_t sampleSize = CMBlockBufferGetDataLength(block);
    assert(CMSampleBufferCreate(0, block, false, makeReady, (void *)0x5678,
        format, 1, 1, &timing, 1, &sampleSize, &dataSample) == noErr);
    assert(CMSampleBufferGetDataBuffer(dataSample) == block);
    assert(CMSampleBufferDataIsReady(dataSample) && readyCalls == 1);
    assert(CMSampleBufferDataIsReady(dataSample) && readyCalls == 1);
    assert(CMSampleBufferInvalidate(imageSample) == noErr);
    assert(!CMSampleBufferDataIsReady(imageSample));

    CFRelease(dataSample);
    CFRelease(imageSample);
    CFRelease(format);
    CVPixelBufferRelease(pixel);
    CFRelease(block);
    assert(frees == 1);
    return 0;
}
