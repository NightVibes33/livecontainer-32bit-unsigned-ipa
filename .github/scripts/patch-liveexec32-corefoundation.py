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
