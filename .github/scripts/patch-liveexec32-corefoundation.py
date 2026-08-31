from pathlib import Path

path = Path("build/LiveExec32/GuestFrameworks/CoreFoundation/CFConstants.m")
source = path.read_text()
anchor = 'NSString * const NSGenericException = @"NSGenericException";'
if source.count(anchor) != 1:
    raise SystemExit("expected exactly one CoreFoundation Foundation-spellings anchor")
locale_constants = """__attribute__((weak)) NSString * const NSLocaleIdentifier = @"identifier";
__attribute__((weak)) NSString * const NSLocaleLanguageCode = @"language code";
__attribute__((weak)) NSString * const NSLocaleCountryCode = @"country code";
__attribute__((weak)) NSString * const NSLocaleScriptCode = @"script code";
__attribute__((weak)) NSString * const NSLocaleVariantCode = @"variant code";
__attribute__((weak)) NSString * const NSLocaleExemplarCharacterSet = @"exemplar character set";
__attribute__((weak)) NSString * const NSLocaleCalendar = @"calendar";
__attribute__((weak)) NSString * const NSLocaleCollationIdentifier = @"collation identifier";
__attribute__((weak)) NSString * const NSLocaleUsesMetricSystem = @"uses metric system";
__attribute__((weak)) NSString * const NSLocaleMeasurementSystem = @"measurement system";
__attribute__((weak)) NSString * const NSLocaleDecimalSeparator = @"decimal separator";
__attribute__((weak)) NSString * const NSLocaleGroupingSeparator = @"grouping separator";
__attribute__((weak)) NSString * const NSLocaleCurrencySymbol = @"currency symbol";
__attribute__((weak)) NSString * const NSLocaleCurrencyCode = @"currency code";
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

"""
path.write_text(source.replace(anchor, locale_constants + calendar_constants + anchor))
