from pathlib import Path

path = Path("build/LiveExec32/GuestFrameworks/CoreFoundation/CFConstants.m")
source = path.read_text()
anchor = 'NSString * const NSGenericException = @"NSGenericException";'
if source.count(anchor) != 1:
    raise SystemExit("expected exactly one CoreFoundation Foundation-spellings anchor")
locale_constants = """__attribute__((weak)) NSString * const NSLocaleScriptCode = @"script code";
__attribute__((weak)) NSString * const NSLocaleVariantCode = @"variant code";
__attribute__((weak)) NSString * const NSLocaleExemplarCharacterSet = @"exemplar character set";
__attribute__((weak)) NSString * const NSLocaleCalendar = @"calendar";
__attribute__((weak)) NSString * const NSLocaleCollationIdentifier = @"collation identifier";
__attribute__((weak)) NSString * const NSLocaleUsesMetricSystem = @"uses metric system";
__attribute__((weak)) NSString * const NSLocaleMeasurementSystem = @"measurement system";
__attribute__((weak)) NSString * const NSLocaleDecimalSeparator = @"decimal separator";
__attribute__((weak)) NSString * const NSLocaleGroupingSeparator = @"grouping separator";
__attribute__((weak)) NSString * const NSLocaleCurrencySymbol = @"currency symbol";
__attribute__((weak)) NSString * const NSLocaleCollatorIdentifier = @"collator identifier";
__attribute__((weak)) NSString * const NSLocaleQuotationBeginDelimiterKey = @"quotation begin delimiter";
__attribute__((weak)) NSString * const NSLocaleQuotationEndDelimiterKey = @"quotation end delimiter";
__attribute__((weak)) NSString * const NSLocaleAlternateQuotationBeginDelimiterKey = @"alternate quotation begin delimiter";
__attribute__((weak)) NSString * const NSLocaleAlternateQuotationEndDelimiterKey = @"alternate quotation end delimiter";

"""
calendar_constants = """NSString * const NSBuddhistCalendar = @"buddhist";
NSString * const NSChineseCalendar = @"chinese";
NSString * const NSHebrewCalendar = @"hebrew";
NSString * const NSIslamicCalendar = @"islamic";
NSString * const NSIslamicCivilCalendar = @"islamic-civil";
NSString * const NSJapaneseCalendar = @"japanese";
NSString * const NSRepublicOfChinaCalendar = @"roc";
NSString * const NSPersianCalendar = @"persian";
NSString * const NSIndianCalendar = @"indian";
NSString * const NSISO8601Calendar = @"iso8601";
NSString * const NSURLUbiquitousItemDownloadingStatusKey = @"NSURLUbiquitousItemDownloadingStatusKey";
const CFLocaleKey kCFLocaleCalendarIdentifier = CFSTR("calendar");
const CFStreamPropertyKey kCFStreamPropertyAppendToFile = CFSTR("kCFStreamPropertyAppendToFile");
const int kCFStreamErrorDomainSSL = 3;
const int kCFStreamErrorDomainSOCKS = 5;

"""
path.write_text(source.replace(anchor, locale_constants + calendar_constants + anchor))
utilities_path = Path("build/LiveExec32/GuestFrameworks/CoreFoundation/CFUtilities.m")
utilities_source = utilities_path.read_text()
utilities_anchor = "CFNotificationCenterRef CFNotificationCenterGetLocalCenter(void) {"
if utilities_source.count(utilities_anchor) != 1:
    raise SystemExit("expected one CoreFoundation utilities anchor")
utilities_extra = r"""CFLocaleIdentifier CFLocaleCreateCanonicalLanguageIdentifierFromString(
        CFAllocatorRef allocator, CFStringRef localeIdentifier) {
    (void)allocator;
    if(!localeIdentifier) return NULL;
    NSString *canonical = [NSLocale
        canonicalLanguageIdentifierFromString:(NSString *)localeIdentifier];
    return (CFLocaleRef)[canonical copy];
}

CFStringRef CFLocaleCopyDisplayNameForPropertyValue(
        CFLocaleRef displayLocale, CFLocaleKey key, CFStringRef value) {
    if(!displayLocale || !key || !value) return NULL;
    return (CFStringRef)[[(NSLocale *)displayLocale
        displayNameForKey:(NSString *)key value:(NSString *)value] copy];
}

void CFShow(CFTypeRef object) {
    NSString *description = [(id)object description];
    fprintf(stderr, "%s\n", description ? [description UTF8String] : "(null)");
}

"""
utilities_path.write_text(utilities_source.replace(utilities_anchor, utilities_extra + utilities_anchor))

string_path = Path("build/LiveExec32/GuestFrameworks/CoreFoundation/CFString.m")
string_source = string_path.read_text()
string_anchor = "CFStringEncoding CFStringGetFastestEncoding(CFStringRef string) {"
if string_source.count(string_anchor) != 1:
    raise SystemExit("expected one CoreFoundation string anchor")
string_extra = r"""CFStringEncoding CFStringGetSystemEncoding(void) {
    return CFStringConvertNSStringEncodingToEncoding(
        [NSString defaultCStringEncoding]);
}

CFStringRef CFStringGetNameOfEncoding(CFStringEncoding encoding) {
    return CFStringConvertEncodingToIANACharSetName(encoding);
}

"""
string_path.write_text(string_source.replace(string_anchor, string_extra + string_anchor))
allocator_extra = r"""

#include <string.h>

@interface LC32CFGuestAllocator : NSObject {
@public
    CFAllocatorContext _context;
}
@end

@implementation LC32CFGuestAllocator
- (void)dealloc {
    if(_context.release && _context.info) _context.release(_context.info);
    [super dealloc];
}
@end

static __thread CFAllocatorRef LC32ThreadDefaultAllocator;

static LC32CFGuestAllocator *LC32CustomAllocator(CFAllocatorRef allocator) {
    if(!allocator || allocator == kCFAllocatorSystemDefault ||
       allocator == kCFAllocatorMalloc ||
       allocator == kCFAllocatorMallocZone ||
       allocator == kCFAllocatorNull) return nil;
    return [(id)allocator isKindOfClass:[LC32CFGuestAllocator class]]
        ? (LC32CFGuestAllocator *)allocator : nil;
}

CFAllocatorRef CFAllocatorCreate(CFAllocatorRef allocator,
                                 CFAllocatorContext *context) {
    (void)allocator;
    if(!context || context->version != 0) return NULL;
    LC32CFGuestAllocator *result = [LC32CFGuestAllocator new];
    result->_context = *context;
    if(result->_context.retain && result->_context.info)
        result->_context.info = (void *)result->_context.retain(result->_context.info);
    return (CFAllocatorRef)result;
}

CFAllocatorRef CFAllocatorGetDefault(void) {
    return LC32ThreadDefaultAllocator ?: kCFAllocatorSystemDefault;
}

void CFAllocatorSetDefault(CFAllocatorRef allocator) {
    CFAllocatorRef replacement = allocator ?: kCFAllocatorSystemDefault;
    if(replacement == LC32ThreadDefaultAllocator) return;
    if(LC32CustomAllocator(replacement)) CFRetain(replacement);
    CFAllocatorRef previous = LC32ThreadDefaultAllocator;
    LC32ThreadDefaultAllocator = replacement;
    if(LC32CustomAllocator(previous)) CFRelease(previous);
}

void CFAllocatorGetContext(CFAllocatorRef allocator,
                           CFAllocatorContext *context) {
    if(!context) return;
    LC32CFGuestAllocator *custom = LC32CustomAllocator(allocator);
    if(custom) *context = custom->_context;
    else memset(context, 0, sizeof(*context));
}

void *CFAllocatorAllocate(CFAllocatorRef allocator, CFIndex size,
                          CFOptionFlags hint) {
    if(size < 0) return NULL;
    CFAllocatorRef selected = allocator ?: CFAllocatorGetDefault();
    if(selected == kCFAllocatorNull) return NULL;
    LC32CFGuestAllocator *custom = LC32CustomAllocator(selected);
    if(custom && custom->_context.allocate)
        return custom->_context.allocate(size, hint, custom->_context.info);
    return malloc((size_t)size);
}

void *CFAllocatorReallocate(CFAllocatorRef allocator, void *pointer,
                            CFIndex size, CFOptionFlags hint) {
    if(size < 0) return NULL;
    CFAllocatorRef selected = allocator ?: CFAllocatorGetDefault();
    if(selected == kCFAllocatorNull) return NULL;
    LC32CFGuestAllocator *custom = LC32CustomAllocator(selected);
    if(custom && custom->_context.reallocate)
        return custom->_context.reallocate(pointer, size, hint, custom->_context.info);
    return realloc(pointer, (size_t)size);
}

void CFAllocatorDeallocate(CFAllocatorRef allocator, void *pointer) {
    if(!pointer) return;
    CFAllocatorRef selected = allocator ?: CFAllocatorGetDefault();
    if(selected == kCFAllocatorNull) return;
    LC32CFGuestAllocator *custom = LC32CustomAllocator(selected);
    if(custom && custom->_context.deallocate)
        custom->_context.deallocate(pointer, custom->_context.info);
    else free(pointer);
}
"""
constants_source = path.read_text()
if "@interface LC32CFGuestAllocator" in constants_source:
    raise SystemExit("CoreFoundation allocator patch already applied")
path.write_text(constants_source + allocator_extra)
heap_extra = r"""

@interface LC32CFBinaryHeap : NSObject {
@public
    const void **_values;
    CFIndex _count;
    CFIndex _capacity;
    CFAllocatorRef _allocator;
    CFBinaryHeapCallBacks _callbacks;
    CFBinaryHeapCompareContext _compareContext;
}
@end

static CFComparisonResult LC32HeapCompare(LC32CFBinaryHeap *heap,
                                          const void *first,
                                          const void *second) {
    if(heap->_callbacks.compare)
        return heap->_callbacks.compare(first, second,
                                        heap->_compareContext.info);
    if(first == second) return kCFCompareEqualTo;
    return (uintptr_t)first < (uintptr_t)second
        ? kCFCompareLessThan : kCFCompareGreaterThan;
}

@implementation LC32CFBinaryHeap
- (NSString *)description {
    NSMutableString *result = [NSMutableString stringWithString:@"<CFBinaryHeap>("];
    for(CFIndex index = 0; index < _count; index++) {
        if(index) [result appendString:@", "];
        CFStringRef valueDescription = _callbacks.copyDescription
            ? _callbacks.copyDescription(_values[index]) : NULL;
        if(valueDescription) {
            [result appendString:(NSString *)valueDescription];
            CFRelease(valueDescription);
        } else {
            [result appendFormat:@"%p", _values[index]];
        }
    }
    [result appendString:@")"];
    return result;
}
- (void)dealloc {
    if(_callbacks.release)
        for(CFIndex index = 0; index < _count; index++)
            _callbacks.release(_allocator, _values[index]);
    if(_compareContext.release && _compareContext.info)
        _compareContext.release(_compareContext.info);
    if(_values) CFAllocatorDeallocate(_allocator, (void *)_values);
    if(LC32CustomAllocator(_allocator)) CFRelease(_allocator);
    [super dealloc];
}
@end

CFBinaryHeapRef CFBinaryHeapCreate(
        CFAllocatorRef allocator, CFIndex capacity,
        const CFBinaryHeapCallBacks *callbacks,
        const CFBinaryHeapCompareContext *compareContext) {
    if(capacity < 0 || (callbacks && callbacks->version != 0) ||
       (compareContext && compareContext->version != 0)) return NULL;
    LC32CFBinaryHeap *heap = [LC32CFBinaryHeap new];
    heap->_allocator = allocator ?: CFAllocatorGetDefault();
    if(LC32CustomAllocator(heap->_allocator)) CFRetain(heap->_allocator);
    if(callbacks) heap->_callbacks = *callbacks;
    if(compareContext) heap->_compareContext = *compareContext;
    if(heap->_compareContext.retain && heap->_compareContext.info)
        heap->_compareContext.info = (void *)heap->_compareContext.retain(
            heap->_compareContext.info);
    heap->_capacity = capacity > 0 ? capacity : 4;
    heap->_values = CFAllocatorAllocate(heap->_allocator,
        heap->_capacity * (CFIndex)sizeof(void *), 0);
    if(!heap->_values) { [heap release]; return NULL; }
    return (CFBinaryHeapRef)heap;
}

void CFBinaryHeapAddValue(CFBinaryHeapRef heapRef, const void *value) {
    LC32CFBinaryHeap *heap = (LC32CFBinaryHeap *)heapRef;
    if(!heap) return;
    if(heap->_count == heap->_capacity) {
        if(heap->_capacity > INT32_MAX / 2) return;
        CFIndex next = heap->_capacity * 2;
        void *grown = CFAllocatorReallocate(heap->_allocator,
            (void *)heap->_values, next * (CFIndex)sizeof(void *), 0);
        if(!grown) return;
        heap->_values = grown;
        heap->_capacity = next;
    }
    heap->_values[heap->_count++] = heap->_callbacks.retain
        ? heap->_callbacks.retain(heap->_allocator, value) : value;
}

CFIndex CFBinaryHeapGetCount(CFBinaryHeapRef heapRef) {
    LC32CFBinaryHeap *heap = (LC32CFBinaryHeap *)heapRef;
    return heap ? heap->_count : 0;
}

Boolean CFBinaryHeapContainsValue(CFBinaryHeapRef heapRef,
                                  const void *value) {
    LC32CFBinaryHeap *heap = (LC32CFBinaryHeap *)heapRef;
    if(!heap) return false;
    for(CFIndex index = 0; index < heap->_count; index++)
        if(LC32HeapCompare(heap, heap->_values[index], value)
           == kCFCompareEqualTo) return true;
    return false;
}

const void *CFBinaryHeapGetMinimum(CFBinaryHeapRef heapRef) {
    LC32CFBinaryHeap *heap = (LC32CFBinaryHeap *)heapRef;
    if(!heap || !heap->_count) return NULL;
    const void *minimum = heap->_values[0];
    for(CFIndex index = 1; index < heap->_count; index++)
        if(LC32HeapCompare(heap, heap->_values[index], minimum)
           == kCFCompareLessThan) minimum = heap->_values[index];
    return minimum;
}

void CFBinaryHeapGetValues(CFBinaryHeapRef heapRef, const void **values) {
    LC32CFBinaryHeap *heap = (LC32CFBinaryHeap *)heapRef;
    if(!heap || !values || !heap->_count) return;
    const CFIndex bytes = heap->_count * (CFIndex)sizeof(void *);
    const void **ordered = CFAllocatorAllocate(heap->_allocator, bytes, 0);
    if(!ordered) return;
    memcpy(ordered, heap->_values, (size_t)bytes);
    for(CFIndex index = 1; index < heap->_count; index++) {
        const void *candidate = ordered[index];
        CFIndex insertion = index;
        while(insertion > 0 && LC32HeapCompare(heap, candidate,
              ordered[insertion - 1]) == kCFCompareLessThan) {
            ordered[insertion] = ordered[insertion - 1];
            insertion--;
        }
        ordered[insertion] = candidate;
    }
    memcpy(values, ordered, (size_t)bytes);
    CFAllocatorDeallocate(heap->_allocator, (void *)ordered);
}

void CFBinaryHeapRemoveMinimumValue(CFBinaryHeapRef heapRef) {
    LC32CFBinaryHeap *heap = (LC32CFBinaryHeap *)heapRef;
    if(!heap || !heap->_count) return;
    CFIndex minimumIndex = 0;
    for(CFIndex index = 1; index < heap->_count; index++)
        if(LC32HeapCompare(heap, heap->_values[index],
                          heap->_values[minimumIndex]) == kCFCompareLessThan)
            minimumIndex = index;
    const void *removed = heap->_values[minimumIndex];
    heap->_count--;
    if(minimumIndex != heap->_count)
        heap->_values[minimumIndex] = heap->_values[heap->_count];
    if(heap->_callbacks.release)
        heap->_callbacks.release(heap->_allocator, removed);
}
"""
constants_source = path.read_text()
if "@interface LC32CFBinaryHeap" in constants_source:
    raise SystemExit("CoreFoundation binary heap patch already applied")
path.write_text(constants_source + heap_extra)
stream_path = Path("build/LiveExec32/GuestFrameworks/CoreFoundation/CFStream.m")
stream_source = stream_path.read_text()
stream_anchor = "void CFStreamCreatePairWithSocket(CFAllocatorRef allocator,"
if stream_source.count(stream_anchor) != 1:
    raise SystemExit("expected one CoreFoundation stream creation anchor")
stream_extra = r"""CFReadStreamRef CFReadStreamCreateWithFile(CFAllocatorRef allocator,
                                               CFURLRef fileURL) {
    (void)allocator;
    if(!fileURL) return NULL;
    return (CFReadStreamRef)[[NSInputStream alloc]
        initWithURL:(NSURL *)fileURL];
}

CFWriteStreamRef CFWriteStreamCreateWithFile(CFAllocatorRef allocator,
                                              CFURLRef fileURL) {
    (void)allocator;
    if(!fileURL || ![(NSURL *)fileURL isFileURL]) return NULL;
    return (CFWriteStreamRef)[[NSOutputStream alloc]
        initToFileAtPath:[(NSURL *)fileURL path] append:NO];
}

"""
stream_path.write_text(stream_source.replace(stream_anchor, stream_extra + stream_anchor))

url_source = utilities_path.read_text()
url_anchor = "CFStringRef CFURLCreateStringByReplacingPercentEscapes("
if url_source.count(url_anchor) != 1:
    raise SystemExit("expected one CoreFoundation URL compatibility anchor")
url_extra = r"""Boolean CFURLCreateDataAndPropertiesFromResource(
        CFAllocatorRef allocator, CFURLRef url, CFDataRef *resourceData,
        CFDictionaryRef *properties, CFArrayRef desiredProperties,
        SInt32 *errorCode) {
    (void)allocator;
    if(resourceData) *resourceData = NULL;
    if(properties) *properties = NULL;
    if(errorCode) *errorCode = 0;
    if(!url) {
        if(errorCode) *errorCode = kCFURLImproperArgumentsError;
        return false;
    }
    NSData *data = [NSData dataWithContentsOfURL:(NSURL *)url];
    if(!data) {
        if(errorCode) *errorCode = kCFURLResourceNotFoundError;
        return false;
    }
    if(resourceData) *resourceData = (CFDataRef)[data copy];
    if(properties) {
        NSDictionary *values = desiredProperties
            ? [(NSURL *)url resourceValuesForKeys:(NSArray *)desiredProperties
                                            error:nil]
            : @{};
        *properties = (CFDictionaryRef)[(values ?: @{}) copy];
    }
    return true;
}

CFURLRef _CFBundleCopyBundleURLForExecutableURL(CFURLRef executableURL) {
    if(!executableURL || ![(NSURL *)executableURL isFileURL]) return NULL;
    NSString *executablePath = [[(NSURL *)executableURL path]
        stringByStandardizingPath];
    NSString *candidate = [executablePath stringByDeletingLastPathComponent];
    while([candidate length] > 1) {
        NSBundle *bundle = [NSBundle bundleWithPath:candidate];
        NSString *bundleExecutable = [[bundle executablePath]
            stringByStandardizingPath];
        if(bundle && [bundleExecutable isEqualToString:executablePath])
            return (CFURLRef)[[bundle bundleURL] copy];
        NSString *parent = [candidate stringByDeletingLastPathComponent];
        if([parent isEqualToString:candidate]) break;
        candidate = parent;
    }
    return NULL;
}

"""
utilities_path.write_text(url_source.replace(url_anchor, url_extra + url_anchor))
coremedia_path = Path("build/LiveExec32/GuestFrameworks/CoreMedia/CoreMedia.m")
coremedia_source = coremedia_path.read_text()
if "CMTime CMTimeAdd(CMTime left, CMTime right)" in coremedia_source:
    raise SystemExit("CoreMedia arithmetic patch already applied")
coremedia_extra = r"""
CMTime CMTimeMultiplyByFloat64(CMTime time, Float64 multiplier);

CMTime CMTimeAdd(CMTime left, CMTime right) {
    return LC32CMTimeAdd(left, right);
}

CMTime CMTimeSubtract(CMTime left, CMTime right) {
    if(CMTIME_IS_POSITIVE_INFINITY(right)) right = kCMTimeNegativeInfinity;
    else if(CMTIME_IS_NEGATIVE_INFINITY(right)) right = kCMTimePositiveInfinity;
    else if(CMTIME_IS_NUMERIC(right)) {
        if(right.value == INT64_MIN) right = CMTimeMultiplyByFloat64(right, -1.0);
        else right.value = -right.value;
    }
    return LC32CMTimeAdd(left, right);
}

int32_t CMTimeCompare(CMTime left, CMTime right) {
    return LC32CMTimeCompare(left, right);
}

CMTime CMTimeMakeWithSeconds(Float64 seconds, int32_t preferredTimescale) {
    if(preferredTimescale <= 0 || isnan(seconds)) return kCMTimeInvalid;
    if(isinf(seconds)) return seconds < 0
        ? kCMTimeNegativeInfinity : kCMTimePositiveInfinity;
    const long double scaled = (long double)seconds * preferredTimescale;
    if(scaled < INT64_MIN || scaled > INT64_MAX) return scaled < 0
        ? kCMTimeNegativeInfinity : kCMTimePositiveInfinity;
    const int64_t value = (int64_t)(scaled < 0 ? scaled - 0.5L : scaled + 0.5L);
    CMTime result = CMTimeMake(value, preferredTimescale);
    if((long double)value != scaled) result.flags |= kCMTimeFlags_HasBeenRounded;
    return result;
}

CMTime CMTimeMultiply(CMTime time, int32_t multiplier) {
    if(!CMTIME_IS_VALID(time) || CMTIME_IS_INDEFINITE(time)) return time;
    if(multiplier == 0 && !CMTIME_IS_NUMERIC(time)) return kCMTimeInvalid;
    if(CMTIME_IS_POSITIVE_INFINITY(time)) return multiplier < 0
        ? kCMTimeNegativeInfinity : kCMTimePositiveInfinity;
    if(CMTIME_IS_NEGATIVE_INFINITY(time)) return multiplier < 0
        ? kCMTimePositiveInfinity : kCMTimeNegativeInfinity;
    int64_t product = 0;
    if(!__builtin_mul_overflow(time.value, (int64_t)multiplier, &product)) {
        time.value = product;
        return time;
    }
    return CMTimeMultiplyByFloat64(time, (Float64)multiplier);
}

CMTime CMTimeMultiplyByFloat64(CMTime time, Float64 multiplier) {
    if(!CMTIME_IS_VALID(time) || isnan(multiplier)) return kCMTimeInvalid;
    if(CMTIME_IS_INDEFINITE(time)) return time;
    if(multiplier == 0 && !CMTIME_IS_NUMERIC(time)) return kCMTimeInvalid;
    if(!CMTIME_IS_NUMERIC(time)) {
        const Boolean negative = (CMTIME_IS_NEGATIVE_INFINITY(time) !=
                                  (multiplier < 0));
        return negative ? kCMTimeNegativeInfinity : kCMTimePositiveInfinity;
    }
    if(isinf(multiplier)) {
        if(time.value == 0) return kCMTimeInvalid;
        const Boolean negative = ((time.value < 0) != (multiplier < 0));
        return negative ? kCMTimeNegativeInfinity : kCMTimePositiveInfinity;
    }
    const long double scaled = (long double)time.value * multiplier;
    if(scaled < INT64_MIN || scaled > INT64_MAX) return scaled < 0
        ? kCMTimeNegativeInfinity : kCMTimePositiveInfinity;
    time.value = (int64_t)(scaled < 0 ? scaled - 0.5L : scaled + 0.5L);
    time.flags |= kCMTimeFlags_HasBeenRounded;
    return time;
}

CMTimeRange CMTimeRangeMake(CMTime start, CMTime duration) {
    const CMTimeRange result = { start, duration };
    return result;
}

CFStringRef CMTimeCopyDescription(CFAllocatorRef allocator, CMTime time) {
    (void)allocator;
    NSString *description = [NSString stringWithFormat:
        @"{value=%lld, timescale=%d, flags=0x%x, epoch=%lld}",
        (long long)time.value, (int)time.timescale, (unsigned)time.flags,
        (long long)time.epoch];
    return (CFStringRef)[description copy];
}
"""
coremedia_path.write_text(coremedia_source + coremedia_extra)
hash_path = Path("build/LiveExec32/GuestFrameworks/CoreFoundation/CFType.m")
hash_source = hash_path.read_text()
hash_anchor = "CFHashCode CFHash(CFTypeRef object) {"
if hash_source.count(hash_anchor) != 1:
    raise SystemExit("expected one CoreFoundation hash anchor")
hash_extra = r"""CFHashCode CFHashBytes(uint8_t *bytes, CFIndex length) {
    if(length < 0 || (length && !bytes)) return 0;
    uint32_t hash = 0, first, high;
    for(CFIndex index = 0; index < length; index++) {
        first = (hash << 4) + bytes[index];
        high = first & 0xF0000000U;
        if(high) first ^= high >> 24;
        first &= ~high;
        hash = first;
    }
    return (CFHashCode)hash;
}

CFHashCode CFStringHashNSString(CFStringRef string) {
    return string ? (CFHashCode)[(NSString *)string hash] : 0;
}

"""
hash_path.write_text(hash_source.replace(hash_anchor, hash_extra + hash_anchor))
cf_header_path = Path("build/LiveExec32/GuestFrameworks/CoreFoundation/LC32CoreFoundationBridge.h")
cf_header_source = cf_header_path.read_text()
cf_header_anchor = "    LC32CoreFoundationOpDateFormatterGetAbsoluteTimeFromString = 224,"
if cf_header_source.count(cf_header_anchor) != 1:
    raise SystemExit("expected one CoreFoundation opcode anchor")
cf_header_insert = cf_header_anchor + r"""
    LC32CoreFoundationOpPreferencesCopyKeyList = 225,
    LC32CoreFoundationOpPreferencesSetMultiple = 226,
    LC32CoreFoundationOpPreferencesSetValue = 227,
    LC32CoreFoundationOpPreferencesSynchronize = 228,"""
cf_header_path.write_text(cf_header_source.replace(cf_header_anchor, cf_header_insert))

prefs_path = Path("build/LiveExec32/GuestFrameworks/CoreFoundation/CFPreferences.m")
prefs_source = prefs_path.read_text()
if "CFArrayRef CFPreferencesCopyKeyList(" in prefs_source:
    raise SystemExit("CoreFoundation preferences patch already applied")
prefs_extra = r"""

CFArrayRef CFPreferencesCopyKeyList(CFStringRef applicationID,
        CFStringRef userName, CFStringRef hostName) {
    if(!applicationID || !userName || !hostName) return NULL;
    return (CFArrayRef)LC32_CF_CALL(
        LC32CoreFoundationOpPreferencesCopyKeyList,
        LC32_CF_HOST(applicationID), LC32_CF_HOST(userName),
        LC32_CF_HOST(hostName));
}

void CFPreferencesSetMultiple(CFDictionaryRef keysToSet,
        CFArrayRef keysToRemove, CFStringRef applicationID,
        CFStringRef userName, CFStringRef hostName) {
    if(!applicationID || !userName || !hostName) return;
    LC32_CF_CALL(LC32CoreFoundationOpPreferencesSetMultiple,
        LC32_CF_HOST(keysToSet), LC32_CF_HOST(keysToRemove),
        LC32_CF_HOST(applicationID), LC32_CF_HOST(userName),
        LC32_CF_HOST(hostName));
}

void CFPreferencesSetValue(CFStringRef key, CFPropertyListRef value,
        CFStringRef applicationID, CFStringRef userName,
        CFStringRef hostName) {
    if(!key || !applicationID || !userName || !hostName) return;
    LC32_CF_CALL(LC32CoreFoundationOpPreferencesSetValue,
        LC32_CF_HOST(key), LC32_CF_HOST(value),
        LC32_CF_HOST(applicationID), LC32_CF_HOST(userName),
        LC32_CF_HOST(hostName));
}

Boolean CFPreferencesSynchronize(CFStringRef applicationID,
        CFStringRef userName, CFStringRef hostName) {
    return applicationID && userName && hostName && LC32_CF_CALL(
        LC32CoreFoundationOpPreferencesSynchronize,
        LC32_CF_HOST(applicationID), LC32_CF_HOST(userName),
        LC32_CF_HOST(hostName));
}
"""
prefs_path.write_text(prefs_source + prefs_extra)

host_cf_path = Path("build/LiveExec32/HostFrameworks/CoreFoundation/CoreFoundation.mm")
host_cf_source = host_cf_path.read_text()
host_cf_anchor = "        case LC32CoreFoundationOpPropertyListCreateWithData: {"
if host_cf_source.count(host_cf_anchor) != 1:
    raise SystemExit("expected one host CoreFoundation preferences anchor")
host_cf_extra = r"""        case LC32CoreFoundationOpPreferencesCopyKeyList: {
            if(!RequireSlots(call, 3)) return 0;
            CFStringRef app = SlotHostObject<CFStringRef>(call, 0);
            CFStringRef user = SlotHostObject<CFStringRef>(call, 1);
            CFStringRef host = SlotHostObject<CFStringRef>(call, 2);
            return app && user && host ? GuestForCreatedObject(
                CFPreferencesCopyKeyList(app, user, host)) : 0;
        }
        case LC32CoreFoundationOpPreferencesSetMultiple: {
            if(!RequireSlots(call, 5)) return 0;
            CFStringRef app = SlotHostObject<CFStringRef>(call, 2);
            CFStringRef user = SlotHostObject<CFStringRef>(call, 3);
            CFStringRef host = SlotHostObject<CFStringRef>(call, 4);
            if(!app || !user || !host) return 0;
            CFPreferencesSetMultiple(
                SlotHostObject<CFDictionaryRef>(call, 0),
                SlotHostObject<CFArrayRef>(call, 1), app, user, host);
            return 1;
        }
        case LC32CoreFoundationOpPreferencesSetValue: {
            if(!RequireSlots(call, 5)) return 0;
            CFStringRef key = SlotHostObject<CFStringRef>(call, 0);
            CFStringRef app = SlotHostObject<CFStringRef>(call, 2);
            CFStringRef user = SlotHostObject<CFStringRef>(call, 3);
            CFStringRef host = SlotHostObject<CFStringRef>(call, 4);
            if(!key || !app || !user || !host) return 0;
            CFPreferencesSetValue(key,
                SlotHostObject<CFPropertyListRef>(call, 1), app, user, host);
            return 1;
        }
        case LC32CoreFoundationOpPreferencesSynchronize: {
            if(!RequireSlots(call, 3)) return 0;
            CFStringRef app = SlotHostObject<CFStringRef>(call, 0);
            CFStringRef user = SlotHostObject<CFStringRef>(call, 1);
            CFStringRef host = SlotHostObject<CFStringRef>(call, 2);
            return app && user && host &&
                CFPreferencesSynchronize(app, user, host);
        }
"""
host_cf_path.write_text(host_cf_source.replace(host_cf_anchor, host_cf_extra + host_cf_anchor))
