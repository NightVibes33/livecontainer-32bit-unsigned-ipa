#import <CoreMedia/CoreMedia.h>
#include <assert.h>
#include <stdlib.h>
#include <string.h>
static int allocations, frees;
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
    CMBlockBufferCustomBlockSource source = {
        0, allocateBlock, freeBlock, (void *)0x1234
    };
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
    CFRelease(block);
    assert(frees == 1);
    return 0;
}
