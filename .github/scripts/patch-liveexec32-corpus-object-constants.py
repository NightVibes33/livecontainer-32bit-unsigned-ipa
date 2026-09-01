#!/usr/bin/env python3
"""Add exact host-backed object constants required by the 40-app corpus."""
from pathlib import Path

root = Path("build/LiveExec32/GuestFrameworks")
constants = {
    'AVFoundation': [
        ('AVAssetExportPreset1280x720', 'string'),
        ('AVAssetExportPreset1920x1080', 'string'),
        ('AVAssetExportPreset640x480', 'string'),
        ('AVAssetExportPreset960x540', 'string'),
        ('AVAssetExportPresetAppleM4A', 'string'),
        ('AVAssetExportPresetPassthrough', 'string'),
        ('AVChannelLayoutKey', 'string'),
        ('AVEncoderBitRateKey', 'string'),
        ('AVLinearPCMIsNonInterleaved', 'string'),
        ('AVPlayerItemFailedToPlayToEndTimeNotification', 'string'),
        ('AVPlayerItemNewAccessLogEntryNotification', 'string'),
        ('AVPlayerItemNewErrorLogEntryNotification', 'string'),
        ('AVPlayerItemPlaybackStalledNotification', 'string'),
        ('AVURLAssetPreferPreciseDurationAndTimingKey', 'string'),
        ('AVURLAssetReferenceRestrictionsKey', 'string'),
        ('AVVideoAverageBitRateKey', 'string'),
        ('AVVideoCodecH264', 'string'),
        ('AVVideoCodecKey', 'string'),
        ('AVVideoCompressionPropertiesKey', 'string'),
        ('AVVideoHeightKey', 'string'),
        ('AVVideoMaxKeyFrameIntervalKey', 'string'),
        ('AVVideoProfileLevelH264High40', 'string'),
        ('AVVideoProfileLevelKey', 'string'),
        ('AVVideoWidthKey', 'string'),
        ('AVAssetExportPresetHighestQuality', 'string'),
        ('AVCaptureDeviceWasConnectedNotification', 'string'),
        ('AVCaptureDeviceWasDisconnectedNotification', 'string'),
    ],
    'Accounts': [
        ('ACAccountStoreDidChangeNotification', 'string'),
        ('ACAccountTypeIdentifierFacebook', 'string'),
        ('ACAccountTypeIdentifierTwitter', 'string'),
        ('ACFacebookAppIdKey', 'string'),
        ('ACFacebookAudienceEveryone', 'string'),
        ('ACFacebookAudienceFriends', 'string'),
        ('ACFacebookAudienceKey', 'string'),
        ('ACFacebookAudienceOnlyMe', 'string'),
        ('ACFacebookPermissionsKey', 'string'),
    ],
    'AddressBookUI': [
        ('ABPersonEmailAddressesProperty', 'string'),
        ('ABPersonPhoneNumbersProperty', 'string'),
        ('ABPersonUrlAddressesProperty', 'string'),
    ],
    'AssetsLibrary': [
        ('ALAssetPropertyAssetURL', 'string'),
        ('ALAssetPropertyDate', 'string'),
        ('ALAssetPropertyDuration', 'string'),
        ('ALAssetPropertyLocation', 'string'),
        ('ALAssetPropertyOrientation', 'string'),
        ('ALAssetPropertyRepresentations', 'string'),
        ('ALAssetPropertyType', 'string'),
        ('ALAssetPropertyURLs', 'string'),
        ('ALAssetTypePhoto', 'string'),
        ('ALAssetTypeVideo', 'string'),
        ('ALAssetsGroupPropertyName', 'string'),
        ('ALAssetsGroupPropertyType', 'string'),
        ('ALAssetsGroupPropertyURL', 'string'),
        ('ALAssetsLibraryChangedNotification', 'string'),
    ],
    'CFNetwork': [
        ('kCFGetAddrInfoFailureKey', 'string'),
        ('kCFHTTPAuthenticationSchemeBasic', 'string'),
        ('kCFStreamPropertyHTTPFinalURL', 'string'),
        ('kCFStreamPropertyHTTPRequestBytesWrittenCount', 'string'),
        ('kCFStreamPropertySSLPeerTrust', 'string'),
        ('kCFHTTPAuthenticationSchemeDigest', 'string'),
        ('kCFStreamPropertyHTTPProxyHost', 'string'),
        ('kCFStreamPropertyHTTPProxyPort', 'string'),
        ('kCFStreamPropertyHTTPSProxyHost', 'string'),
        ('kCFStreamPropertyHTTPSProxyPort', 'string'),
    ],
    'CoreBluetooth': [
        ('CBAdvertisementDataManufacturerDataKey', 'string'),
        ('CBAdvertisementDataServiceUUIDsKey', 'string'),
        ('CBCentralManagerOptionShowPowerAlertKey', 'string'),
        ('CBCentralManagerScanOptionAllowDuplicatesKey', 'string'),
    ],
    'CoreData': [
        ('NSErrorMergePolicy', 'object'),
        ('NSInMemoryStoreType', 'string'),
        ('NSInsertedObjectsKey', 'string'),
        ('NSManagedObjectContextDidSaveNotification', 'string'),
        ('NSManagedObjectContextObjectsDidChangeNotification', 'string'),
        ('NSMergeByPropertyObjectTrumpMergePolicy', 'object'),
        ('NSMergeByPropertyStoreTrumpMergePolicy', 'object'),
        ('NSOverwriteMergePolicy', 'object'),
        ('NSRefreshedObjectsKey', 'string'),
        ('NSRollbackMergePolicy', 'object'),
        ('NSSQLiteErrorDomain', 'string'),
        ('NSSQLiteManualVacuumOption', 'string'),
        ('NSSQLitePragmasOption', 'string'),
        ('NSUpdatedObjectsKey', 'string'),
        ('NSDeletedObjectsKey', 'string'),
        ('NSManagedObjectContextWillSaveNotification', 'string'),
    ],
    'CoreFoundation': [
        ('kCFStreamPropertySOCKSPassword', 'string'),
        ('kCFStreamPropertySOCKSProxy', 'string'),
        ('kCFStreamPropertySOCKSProxyHost', 'string'),
        ('kCFStreamPropertySOCKSProxyPort', 'string'),
        ('kCFStreamPropertySOCKSUser', 'string'),
        ('kCFStreamPropertySocketSecurityLevel', 'string'),
        ('kCFStringTransformToLatin', 'string'),
    ],
    'CoreGraphics': [
        ('kCGColorSpaceSRGB', 'string'),
    ],
    'CoreImage': [
        ('kCIInputImageKey', 'string'),
        ('kCIOutputImageKey', 'string'),
        ('kCIInputScaleKey', 'string'),
    ],
    'CoreLocation': [
        ('kCLErrorDomain', 'string'),
    ],
    'CoreMedia': [
        ('kCMSampleAttachmentKey_DisplayImmediately', 'string'),
        ('kCMSampleAttachmentKey_DoNotDisplay', 'string'),
    ],
    'CoreTelephony': [
        ('CTRadioAccessTechnologyCDMA1x', 'string'),
        ('CTRadioAccessTechnologyCDMAEVDORev0', 'string'),
        ('CTRadioAccessTechnologyCDMAEVDORevA', 'string'),
        ('CTRadioAccessTechnologyCDMAEVDORevB', 'string'),
        ('CTRadioAccessTechnologyDidChangeNotification', 'string'),
        ('CTRadioAccessTechnologyEdge', 'string'),
        ('CTRadioAccessTechnologyGPRS', 'string'),
        ('CTRadioAccessTechnologyHSDPA', 'string'),
        ('CTRadioAccessTechnologyHSUPA', 'string'),
        ('CTRadioAccessTechnologyLTE', 'string'),
        ('CTRadioAccessTechnologyWCDMA', 'string'),
        ('CTRadioAccessTechnologyeHRPD', 'string'),
    ],
    'CoreText': [
        ('kCTFontPostScriptNameKey', 'string'),
        ('kCTFontSymbolicTrait', 'string'),
        ('kCTFontTraitsAttribute', 'string'),
        ('kCTForegroundColorFromContextAttributeName', 'string'),
        ('kCTRunDelegateAttributeName', 'string'),
        ('kCTSuperscriptAttributeName', 'string'),
    ],
    'CoreVideo': [
        ('kCVPixelBufferCGBitmapContextCompatibilityKey', 'string'),
        ('kCVPixelBufferCGImageCompatibilityKey', 'string'),
    ],
    'EventKit': [
        ('EKEventStoreChangedNotification', 'string'),
    ],
    'Foundation': [
        ('NSErrorFailingURLStringKey', 'string'),
        ('NSKeyedArchiveRootObjectKey', 'string'),
        ('NSMetadataItemURLKey', 'string'),
        ('NSMetadataQueryUpdateAddedItemsKey', 'string'),
        ('NSMetadataQueryUpdateChangedItemsKey', 'string'),
        ('NSMetadataQueryUpdateRemovedItemsKey', 'string'),
        ('NSURLAuthenticationMethodClientCertificate', 'string'),
        ('NSURLErrorFailingURLPeerTrustErrorKey', 'string'),
        ('NSUbiquitousKeyValueStoreChangedKeysKey', 'string'),
        ('NSMetadataItemFSNameKey', 'string'),
        ('NSMetadataQueryUbiquitousDocumentsScope', 'string'),
        ('NSURLAuthenticationMethodHTTPBasic', 'string'),
        ('NSURLAuthenticationMethodHTTPDigest', 'string'),
        ('NSURLSessionDownloadTaskResumeData', 'string'),
    ],
    'GLKit': [
        ('GLKTextureLoaderOriginBottomLeft', 'string'),
    ],
    'ImageIO': [
        ('kCGImageDestinationLossyCompressionQuality', 'string'),
        ('kCGImageProperty8BIMDictionary', 'string'),
        ('kCGImagePropertyCIFFDictionary', 'string'),
        ('kCGImagePropertyDNGDictionary', 'string'),
        ('kCGImagePropertyExifAuxDictionary', 'string'),
        ('kCGImagePropertyExifDateTimeDigitized', 'string'),
        ('kCGImagePropertyExifDateTimeOriginal', 'string'),
        ('kCGImagePropertyExifDictionary', 'string'),
        ('kCGImagePropertyGIFDelayTime', 'string'),
        ('kCGImagePropertyGIFDictionary', 'string'),
        ('kCGImagePropertyGIFLoopCount', 'string'),
        ('kCGImagePropertyGIFUnclampedDelayTime', 'string'),
        ('kCGImagePropertyGPSAltitude', 'string'),
        ('kCGImagePropertyGPSDateStamp', 'string'),
        ('kCGImagePropertyGPSDictionary', 'string'),
        ('kCGImagePropertyGPSLatitude', 'string'),
        ('kCGImagePropertyGPSLatitudeRef', 'string'),
        ('kCGImagePropertyGPSLongitude', 'string'),
        ('kCGImagePropertyGPSLongitudeRef', 'string'),
        ('kCGImagePropertyGPSTimeStamp', 'string'),
        ('kCGImagePropertyIPTCDictionary', 'string'),
        ('kCGImagePropertyJFIFDictionary', 'string'),
        ('kCGImagePropertyMakerAppleDictionary', 'string'),
        ('kCGImagePropertyMakerCanonDictionary', 'string'),
        ('kCGImagePropertyMakerNikonDictionary', 'string'),
        ('kCGImagePropertyOrientation', 'string'),
        ('kCGImagePropertyPNGDictionary', 'string'),
        ('kCGImagePropertyPixelHeight', 'string'),
        ('kCGImagePropertyPixelWidth', 'string'),
        ('kCGImagePropertyRawDictionary', 'string'),
        ('kCGImagePropertyTIFFDictionary', 'string'),
        ('kCGImagePropertyTIFFMake', 'string'),
        ('kCGImagePropertyTIFFModel', 'string'),
        ('kCGImageSourceShouldAllowFloat', 'string'),
        ('kCGImageSourceShouldCache', 'string'),
        ('kCGImageSourceTypeIdentifierHint', 'string'),
    ],
    'MapKit': [
        ('MKLaunchOptionsDirectionsModeDriving', 'string'),
        ('MKLaunchOptionsDirectionsModeKey', 'string'),
        ('MKLaunchOptionsDirectionsModeWalking', 'string'),
        ('MKLaunchOptionsMapCenterKey', 'string'),
        ('MKLaunchOptionsMapTypeKey', 'string'),
        ('MKLaunchOptionsShowsTrafficKey', 'string'),
    ],
    'MediaPlayer': [
        ('MPMediaEntityPropertyPersistentID', 'string'),
        ('MPMediaItemPropertyAlbumPersistentID', 'string'),
        ('MPMediaItemPropertyAlbumTrackNumber', 'string'),
        ('MPMediaItemPropertyArtistPersistentID', 'string'),
        ('MPMediaItemPropertyArtwork', 'string'),
        ('MPMediaItemPropertyAssetURL', 'string'),
        ('MPMediaItemPropertyComments', 'string'),
        ('MPMediaItemPropertyIsCloudItem', 'string'),
        ('MPMediaItemPropertyLastPlayedDate', 'string'),
        ('MPMediaItemPropertyLyrics', 'string'),
        ('MPMediaItemPropertyMediaType', 'string'),
        ('MPMediaItemPropertyPersistentID', 'string'),
        ('MPMediaItemPropertyPlayCount', 'string'),
        ('MPMediaItemPropertyPlaybackDuration', 'string'),
        ('MPMediaItemPropertyRating', 'string'),
        ('MPMediaItemPropertyReleaseDate', 'string'),
        ('MPMediaItemPropertySkipCount', 'string'),
        ('MPMediaLibraryDidChangeNotification', 'string'),
        ('MPMediaPlaylistPropertyName', 'string'),
        ('MPMediaPlaylistPropertyPersistentID', 'string'),
        ('MPMediaPlaybackIsPreparedToPlayDidChangeNotification', 'string'),
        ('MPMoviePlayerThumbnailErrorKey', 'string'),
        ('MPMoviePlayerThumbnailImageKey', 'string'),
        ('MPMoviePlayerThumbnailImageRequestDidFinishNotification', 'string'),
    ],
    'MobileCoreServices': [
        ('kUTTagClassFilenameExtension', 'string'),
        ('kUTTagClassMIMEType', 'string'),
        ('kUTTypeAudio', 'string'),
        ('kUTTypeAudioInterchangeFileFormat', 'string'),
        ('kUTTypeAudiovisualContent', 'string'),
        ('kUTTypeBMP', 'string'),
        ('kUTTypeCompositeContent', 'string'),
        ('kUTTypeConformsToKey', 'string'),
        ('kUTTypeContent', 'string'),
        ('kUTTypeData', 'string'),
        ('kUTTypeFileURL', 'string'),
        ('kUTTypeFlatRTFD', 'string'),
        ('kUTTypeGIF', 'string'),
        ('kUTTypeHTML', 'string'),
        ('kUTTypeItem', 'string'),
        ('kUTTypeJPEG', 'string'),
        ('kUTTypeJPEG2000', 'string'),
        ('kUTTypeMP3', 'string'),
        ('kUTTypeMPEG4', 'string'),
        ('kUTTypeMPEG4Audio', 'string'),
        ('kUTTypePDF', 'string'),
        ('kUTTypePNG', 'string'),
        ('kUTTypePlainText', 'string'),
        ('kUTTypePropertyList', 'string'),
        ('kUTTypeRTF', 'string'),
        ('kUTTypeRTFD', 'string'),
        ('kUTTypeTIFF', 'string'),
        ('kUTTypeTagSpecificationKey', 'string'),
        ('kUTTypeText', 'string'),
        ('kUTTypeURL', 'string'),
        ('kUTTypeUTF8PlainText', 'string'),
        ('kUTTypeVCard', 'string'),
        ('kUTTypeVideo', 'string'),
        ('kUTTypeWaveformAudio', 'string'),
        ('kUTTypeWebArchive', 'string'),
        ('kUTTypeZipArchive', 'string'),
    ],
    'Photos': [
        ('PHImageErrorKey', 'string'),
        ('PHImageResultIsDegradedKey', 'string'),
    ],
    'QuartzCore': [
        ('kCATransactionAnimationDuration', 'string'),
    ],
    'Security': [
        ('kSecAttrAuthenticationType', 'string'),
        ('kSecAttrAuthenticationTypeDefault', 'string'),
        ('kSecAttrCreationDate', 'string'),
        ('kSecAttrIsPermanent', 'string'),
        ('kSecAttrKeySizeInBits', 'string'),
        ('kSecAttrSecurityDomain', 'string'),
        ('kSecAttrServer', 'string'),
        ('kSecAttrSynchronizableAny', 'string'),
        ('kSecClassIdentity', 'string'),
        ('kSecClassInternetPassword', 'string'),
        ('kSecImportExportPassphrase', 'string'),
        ('kSecImportItemIdentity', 'string'),
        ('kSecMatchLimitAll', 'string'),
        ('kSecMatchPolicy', 'string'),
        ('kSecPrivateKeyAttrs', 'string'),
        ('kSecPublicKeyAttrs', 'string'),
        ('kSecAttrKeyClassPrivate', 'string'),
    ],
    'Social': [
        ('SLServiceTypeSinaWeibo', 'string'),
        ('SLServiceTypeTencentWeibo', 'string'),
    ],
    'StoreKit': [
        ('SKStoreProductParameterAffiliateToken', 'string'),
        ('SKStoreProductParameterCampaignToken', 'string'),
        ('SKStoreProductParameterProviderToken', 'string'),
    ],
    'UIKit': [
        ('UIAccessibilityVoiceOverStatusChanged', 'string'),
        ('UIApplicationOpenSettingsURLString', 'string'),
        ('UIApplicationStatusBarFrameUserInfoKey', 'string'),
        ('UICollectionElementKindSectionFooter', 'string'),
        ('UICollectionElementKindSectionHeader', 'string'),
        ('UIPasteboardTypeListURL', 'string'),
        ('UITableViewIndexSearch', 'string'),
        ('UIKeyInputDownArrow', 'string'),
        ('UIKeyInputEscape', 'string'),
        ('UIKeyInputLeftArrow', 'string'),
        ('UIKeyInputRightArrow', 'string'),
        ('UIKeyInputUpArrow', 'string'),
    ],
}

flat = [(framework, symbol) for framework, entries in constants.items()
        for symbol, _ in entries]
if len(flat) != 272 or len(set(flat)) != len(flat):
    raise SystemExit("corpus object-constant manifest must contain 272 unique exports")

source_header = r'''#import <Foundation/Foundation.h>
#import <Foundation/Foundation+LC32.h>
#import <objc/runtime.h>

/* Generated from the exhaustive 40-app ARM32 binding contract. String
 * constants bind to the exact native object, preserving host dictionary-key
 * and notification identity. The literal remains a valid fallback only when
 * a removed host symbol no longer exists. */
static id LC32CorpusStringConstant(const char *symbol, NSString *fallback) {
    const uint64_t hostObject = LC32Dlsym(symbol, NO);
    if(hostObject) [fallback bindHostSelf:hostObject];
    return fallback;
}

static id LC32CorpusObjectConstant(const char *symbol, const char *className) {
    const uint64_t hostObject = LC32Dlsym(symbol, NO);
    Class cls = objc_getClass(className);
    id object = cls ? class_createInstance(cls, 0) : nil;
    if(object && hostObject) [object bindHostSelf:hostObject];
    return object;
}
'''

for framework, entries in constants.items():
    directory = root / framework
    directory.mkdir(parents=True, exist_ok=True)
    declarations = []
    initializers = []
    for index, (symbol, kind) in enumerate(entries):
        storage = f"LC32CorpusObjectConstant{index}"
        declarations.append(f'id {storage} __asm__("_{symbol}");')
        if kind == "string":
            initializers.append(
                f'    {storage} = LC32CorpusStringConstant("{symbol}", @"{symbol}");')
        else:
            initializers.append(
                f'    {storage} = LC32CorpusObjectConstant("{symbol}", "NSMergePolicy");')
    source = source_header + "\n".join(declarations) + "\n\n"
    source += "__attribute__((constructor))\n"
    source += f"static void LC32Initialize{framework}CorpusConstants(void) {{\n"
    source += "\n".join(initializers) + "\n}\n"
    (directory / "LC32CorpusObjectConstants.m").write_text(source)
    print(f"{framework}: {len(entries)} host-backed object constants")
