#!/usr/bin/env python3
from pathlib import Path
R=Path('build/LiveExec32'); H=R/'GuestFrameworks/CoreGraphics/LC32CoreGraphicsBridge.h'; G=R/'GuestFrameworks/CoreGraphics/CoreGraphics.m'; X=R/'HostFrameworks/CoreGraphics/CoreGraphics.mm'
h=H.read_text(); a='    LC32CoreGraphicsOpSizeMakeWithDictionaryRepresentation = 187,\n'
if 'LC32CoreGraphicsOpPDFDocumentAllowsCopying = 188' not in h:
 if a not in h: raise SystemExit('PDF opcode anchor missing')
 h=h.replace(a,a+r'''    LC32CoreGraphicsOpPDFDocumentAllowsCopying = 188,
    LC32CoreGraphicsOpPDFDocumentAllowsPrinting = 189,
    LC32CoreGraphicsOpPDFDocumentCreateWithProvider = 190,
    LC32CoreGraphicsOpPDFDocumentCreateWithURL = 191,
    LC32CoreGraphicsOpPDFDocumentGetNumberOfPages = 192,
    LC32CoreGraphicsOpPDFDocumentGetPage = 193,
    LC32CoreGraphicsOpPDFDocumentIsEncrypted = 194,
    LC32CoreGraphicsOpPDFDocumentIsUnlocked = 195,
    LC32CoreGraphicsOpPDFPageGetDictionary = 196,
    LC32CoreGraphicsOpPDFPageGetRotationAngle = 197,
'''); H.write_text(h)
g=G.read_text()
if 'bool CGPDFDocumentAllowsCopying(' not in g:
 g+=r'''
bool CGPDFDocumentAllowsCopying(CGPDFDocumentRef d){return d&&LC32_CG_CALL(LC32CoreGraphicsOpPDFDocumentAllowsCopying,LC32_CG_HOST(d));}
bool CGPDFDocumentAllowsPrinting(CGPDFDocumentRef d){return d&&LC32_CG_CALL(LC32CoreGraphicsOpPDFDocumentAllowsPrinting,LC32_CG_HOST(d));}
CGPDFDocumentRef CGPDFDocumentCreateWithProvider(CGDataProviderRef p){return p?(CGPDFDocumentRef)LC32_CG_CALL(LC32CoreGraphicsOpPDFDocumentCreateWithProvider,LC32_CG_HOST(p)):NULL;}
CGPDFDocumentRef CGPDFDocumentCreateWithURL(CFURLRef u){return u?(CGPDFDocumentRef)LC32_CG_CALL(LC32CoreGraphicsOpPDFDocumentCreateWithURL,LC32_CG_HOST(u)):NULL;}
size_t CGPDFDocumentGetNumberOfPages(CGPDFDocumentRef d){return d?(size_t)LC32_CG_CALL(LC32CoreGraphicsOpPDFDocumentGetNumberOfPages,LC32_CG_HOST(d)):0;}
CGPDFPageRef CGPDFDocumentGetPage(CGPDFDocumentRef d,size_t n){return d?(CGPDFPageRef)LC32_CG_CALL(LC32CoreGraphicsOpPDFDocumentGetPage,LC32_CG_HOST(d),LC32_CG_U32(n)):NULL;}
bool CGPDFDocumentIsEncrypted(CGPDFDocumentRef d){return d&&LC32_CG_CALL(LC32CoreGraphicsOpPDFDocumentIsEncrypted,LC32_CG_HOST(d));}
bool CGPDFDocumentIsUnlocked(CGPDFDocumentRef d){return d&&LC32_CG_CALL(LC32CoreGraphicsOpPDFDocumentIsUnlocked,LC32_CG_HOST(d));}
CGPDFDictionaryRef CGPDFPageGetDictionary(CGPDFPageRef p){return p?(CGPDFDictionaryRef)LC32_CG_CALL(LC32CoreGraphicsOpPDFPageGetDictionary,LC32_CG_HOST(p)):NULL;}
int CGPDFPageGetRotationAngle(CGPDFPageRef p){return p?(int32_t)LC32_CG_CALL(LC32CoreGraphicsOpPDFPageGetRotationAngle,LC32_CG_HOST(p)):0;}
'''; G.write_text(g)
x=X.read_text()
if 'case LC32CoreGraphicsOpPDFDocumentAllowsCopying:' not in x:
 c=r'''
        case LC32CoreGraphicsOpPDFDocumentAllowsCopying: case LC32CoreGraphicsOpPDFDocumentAllowsPrinting: case LC32CoreGraphicsOpPDFDocumentIsEncrypted: case LC32CoreGraphicsOpPDFDocumentIsUnlocked:{if(!RequireCoreGraphicsSlots(call,1))return 0;CGPDFDocumentRef d=SlotHostObject<CGPDFDocumentRef>(call,0);if(!d)return 0;if(opcode==LC32CoreGraphicsOpPDFDocumentAllowsCopying)return CGPDFDocumentAllowsCopying(d);if(opcode==LC32CoreGraphicsOpPDFDocumentAllowsPrinting)return CGPDFDocumentAllowsPrinting(d);if(opcode==LC32CoreGraphicsOpPDFDocumentIsEncrypted)return CGPDFDocumentIsEncrypted(d);return CGPDFDocumentIsUnlocked(d);}
        case LC32CoreGraphicsOpPDFDocumentCreateWithProvider:{if(!RequireCoreGraphicsSlots(call,1))return 0;CGDataProviderRef p=SlotHostObject<CGDataProviderRef>(call,0);CGPDFDocumentRef r=p?CGPDFDocumentCreateWithProvider(p):nullptr;return r?LC32GuestObjectForOwnedHostObject(r):0;}
        case LC32CoreGraphicsOpPDFDocumentCreateWithURL:{if(!RequireCoreGraphicsSlots(call,1))return 0;CFURLRef u=SlotHostObject<CFURLRef>(call,0);CGPDFDocumentRef r=u?CGPDFDocumentCreateWithURL(u):nullptr;return r?LC32GuestObjectForOwnedHostObject(r):0;}
        case LC32CoreGraphicsOpPDFDocumentGetNumberOfPages:{if(!RequireCoreGraphicsSlots(call,1))return 0;CGPDFDocumentRef d=SlotHostObject<CGPDFDocumentRef>(call,0);return d?static_cast<u32>(CGPDFDocumentGetNumberOfPages(d)):0;}
        case LC32CoreGraphicsOpPDFDocumentGetPage:{if(!RequireCoreGraphicsSlots(call,2))return 0;CGPDFDocumentRef d=SlotHostObject<CGPDFDocumentRef>(call,0);CGPDFPageRef r=d?CGPDFDocumentGetPage(d,SlotU32(call,1)):nullptr;return r?[(id)r guest_self]:0;}
        case LC32CoreGraphicsOpPDFPageGetDictionary:{if(!RequireCoreGraphicsSlots(call,1))return 0;CGPDFPageRef p=SlotHostObject<CGPDFPageRef>(call,0);CGPDFDictionaryRef r=p?CGPDFPageGetDictionary(p):nullptr;return r?[(id)r guest_self]:0;}
        case LC32CoreGraphicsOpPDFPageGetRotationAngle:{if(!RequireCoreGraphicsSlots(call,1))return 0;CGPDFPageRef p=SlotHostObject<CGPDFPageRef>(call,0);return p?static_cast<u32>(CGPDFPageGetRotationAngle(p)):0;}
'''
 z='    }\n    return 0;\n}\n\n__END_DECLS'
 if z not in x: raise SystemExit('PDF switch anchor missing')
 x=x.replace(z,c+z,1); X.write_text(x)
print('CoreGraphics: added 10 typed PDF document/page exports')


# Second PDF batch: non-callback arrays, contexts, document outputs, geometry, streams and strings.
h=H.read_text(); a='    LC32CoreGraphicsOpPDFPageGetRotationAngle = 197,\n'
if 'LC32CoreGraphicsOpPDFArrayGetCount = 198' not in h:
 if a not in h: raise SystemExit('second PDF opcode anchor missing')
 h=h.replace(a,a+r'''    LC32CoreGraphicsOpPDFArrayGetCount = 198,
    LC32CoreGraphicsOpPDFContentStreamCreateWithPage = 199,
    LC32CoreGraphicsOpPDFContextClose = 200,
    LC32CoreGraphicsOpPDFContextCreate = 201,
    LC32CoreGraphicsOpPDFContextSetURLForRect = 202,
    LC32CoreGraphicsOpPDFDocumentGetVersion = 203,
    LC32CoreGraphicsOpPDFDocumentUnlockWithPassword = 204,
    LC32CoreGraphicsOpPDFPageGetBoxRect = 205,
    LC32CoreGraphicsOpPDFPageGetDrawingTransform = 206,
    LC32CoreGraphicsOpPDFStreamCopyData = 207,
    LC32CoreGraphicsOpPDFStreamGetDictionary = 208,
    LC32CoreGraphicsOpPDFStringGetLength = 209,
'''); H.write_text(h)
g=G.read_text()
if 'size_t CGPDFArrayGetCount(' not in g:
 g+=r'''
size_t CGPDFArrayGetCount(CGPDFArrayRef a){return a?(size_t)LC32_CG_CALL(LC32CoreGraphicsOpPDFArrayGetCount,LC32_CG_HOST(a)):0;}
CGPDFContentStreamRef CGPDFContentStreamCreateWithPage(CGPDFPageRef p){return p?(CGPDFContentStreamRef)LC32_CG_CALL(LC32CoreGraphicsOpPDFContentStreamCreateWithPage,LC32_CG_HOST(p)):NULL;}
void CGPDFContextClose(CGContextRef c){if(c)(void)LC32_CG_CALL(LC32CoreGraphicsOpPDFContextClose,LC32_CG_HOST(c));}
CGContextRef CGPDFContextCreate(CGDataConsumerRef c,const CGRect *r,CFDictionaryRef aux){return c?(CGContextRef)LC32_CG_CALL(LC32CoreGraphicsOpPDFContextCreate,LC32_CG_HOST(c),LC32_CG_U32(r!=NULL),r?LC32_CG_F32(r->origin.x):0,r?LC32_CG_F32(r->origin.y):0,r?LC32_CG_F32(r->size.width):0,r?LC32_CG_F32(r->size.height):0,LC32_CG_HOST(aux)):NULL;}
void CGPDFContextSetURLForRect(CGContextRef c,CFURLRef u,CGRect r){if(c&&u)(void)LC32_CG_CALL(LC32CoreGraphicsOpPDFContextSetURLForRect,LC32_CG_HOST(c),LC32_CG_HOST(u),LC32_CG_F32(r.origin.x),LC32_CG_F32(r.origin.y),LC32_CG_F32(r.size.width),LC32_CG_F32(r.size.height));}
void CGPDFDocumentGetVersion(CGPDFDocumentRef d,int *major,int *minor){if(d&&major&&minor)(void)LC32_CG_CALL(LC32CoreGraphicsOpPDFDocumentGetVersion,LC32_CG_HOST(d),LC32_CG_U32((uintptr_t)major),LC32_CG_U32((uintptr_t)minor));}
bool CGPDFDocumentUnlockWithPassword(CGPDFDocumentRef d,const char *p){if(!d||!p)return false;size_t n=strnlen(p,LC32CoreGraphicsMaximumFilenameBytes+1);return n<=LC32CoreGraphicsMaximumFilenameBytes&&LC32_CG_CALL(LC32CoreGraphicsOpPDFDocumentUnlockWithPassword,LC32_CG_HOST(d),LC32_CG_U32((uintptr_t)p),LC32_CG_U32(n));}
CGRect CGPDFPageGetBoxRect(CGPDFPageRef p,CGPDFBox b){CGRect r=CGRectZero;if(p)(void)LC32_CG_CALL(LC32CoreGraphicsOpPDFPageGetBoxRect,LC32_CG_HOST(p),LC32_CG_U32(b),LC32_CG_U32((uintptr_t)&r));return r;}
CGAffineTransform CGPDFPageGetDrawingTransform(CGPDFPageRef p,CGPDFBox b,CGRect r,int rotate,bool preserve){CGAffineTransform t=CGAffineTransformIdentity;if(p)(void)LC32_CG_CALL(LC32CoreGraphicsOpPDFPageGetDrawingTransform,LC32_CG_HOST(p),LC32_CG_U32(b),LC32_CG_F32(r.origin.x),LC32_CG_F32(r.origin.y),LC32_CG_F32(r.size.width),LC32_CG_F32(r.size.height),LC32_CG_U32(rotate),LC32_CG_U32(preserve),LC32_CG_U32((uintptr_t)&t));return t;}
CFDataRef CGPDFStreamCopyData(CGPDFStreamRef s,CGPDFDataFormat *f){return s&&f?(CFDataRef)LC32_CG_CALL(LC32CoreGraphicsOpPDFStreamCopyData,LC32_CG_HOST(s),LC32_CG_U32((uintptr_t)f)):NULL;}
CGPDFDictionaryRef CGPDFStreamGetDictionary(CGPDFStreamRef s){return s?(CGPDFDictionaryRef)LC32_CG_CALL(LC32CoreGraphicsOpPDFStreamGetDictionary,LC32_CG_HOST(s)):NULL;}
size_t CGPDFStringGetLength(CGPDFStringRef s){return s?(size_t)LC32_CG_CALL(LC32CoreGraphicsOpPDFStringGetLength,LC32_CG_HOST(s)):0;}
'''; G.write_text(g)
x=X.read_text()
if 'case LC32CoreGraphicsOpPDFArrayGetCount:' not in x:
 c=r'''
        case LC32CoreGraphicsOpPDFArrayGetCount:{if(!RequireCoreGraphicsSlots(call,1))return 0;CGPDFArrayRef a=SlotHostObject<CGPDFArrayRef>(call,0);return a?static_cast<u32>(CGPDFArrayGetCount(a)):0;}
        case LC32CoreGraphicsOpPDFContentStreamCreateWithPage:{if(!RequireCoreGraphicsSlots(call,1))return 0;CGPDFPageRef p=SlotHostObject<CGPDFPageRef>(call,0);CGPDFContentStreamRef r=p?CGPDFContentStreamCreateWithPage(p):nullptr;return r?LC32GuestObjectForOwnedHostObject(r):0;}
        case LC32CoreGraphicsOpPDFContextClose:{if(!RequireCoreGraphicsSlots(call,1))return 0;CGContextRef c=SlotHostObject<CGContextRef>(call,0);if(!c)return 0;CGPDFContextClose(c);return 1;}
        case LC32CoreGraphicsOpPDFContextCreate:{if(!RequireCoreGraphicsSlots(call,7))return 0;CGDataConsumerRef c=SlotHostObject<CGDataConsumerRef>(call,0);u32 present=SlotU32(call,1);if(!c||present>1)return 0;CGRect r=SlotRect(call,2);CGContextRef out=CGPDFContextCreate(c,present?&r:nullptr,SlotHostObject<CFDictionaryRef>(call,6));return out?LC32GuestObjectForOwnedHostObject(out):0;}
        case LC32CoreGraphicsOpPDFContextSetURLForRect:{if(!RequireCoreGraphicsSlots(call,6))return 0;CGContextRef c=SlotHostObject<CGContextRef>(call,0);CFURLRef u=SlotHostObject<CFURLRef>(call,1);if(!c||!u)return 0;CGPDFContextSetURLForRect(c,u,SlotRect(call,2));return 1;}
        case LC32CoreGraphicsOpPDFDocumentGetVersion:{if(!RequireCoreGraphicsSlots(call,3))return 0;CGPDFDocumentRef d=SlotHostObject<CGPDFDocumentRef>(call,0);if(!d)return 0;int major=0,minor=0;CGPDFDocumentGetVersion(d,&major,&minor);return Dynarmic_mem_1write(SlotU32(call,1),sizeof(major),reinterpret_cast<char *>(&major))==0&&Dynarmic_mem_1write(SlotU32(call,2),sizeof(minor),reinterpret_cast<char *>(&minor))==0;}
        case LC32CoreGraphicsOpPDFDocumentUnlockWithPassword:{if(!RequireCoreGraphicsSlots(call,3))return 0;CGPDFDocumentRef d=SlotHostObject<CGPDFDocumentRef>(call,0);std::vector<char> p;if(!d||!ReadGuestCoreGraphicsBytes(SlotU32(call,1),SlotU32(call,2),p))return 0;return CGPDFDocumentUnlockWithPassword(d,p.data());}
        case LC32CoreGraphicsOpPDFPageGetBoxRect:{if(!RequireCoreGraphicsSlots(call,3))return 0;CGPDFPageRef p=SlotHostObject<CGPDFPageRef>(call,0);if(!p)return 0;CGRect r=CGPDFPageGetBoxRect(p,(CGPDFBox)SlotU32(call,1));CGFloat v[4]={r.origin.x,r.origin.y,r.size.width,r.size.height};return WriteGuestCoreGraphicsFloats(SlotU32(call,2),v,4);}
        case LC32CoreGraphicsOpPDFPageGetDrawingTransform:{if(!RequireCoreGraphicsSlots(call,10))return 0;CGPDFPageRef p=SlotHostObject<CGPDFPageRef>(call,0);u32 preserve=SlotU32(call,8);if(!p||preserve>1)return 0;CGAffineTransform t=CGPDFPageGetDrawingTransform(p,(CGPDFBox)SlotU32(call,1),SlotRect(call,2),(int32_t)SlotU32(call,6),preserve!=0);CGFloat v[6]={t.a,t.b,t.c,t.d,t.tx,t.ty};return WriteGuestCoreGraphicsFloats(SlotU32(call,9),v,6);}
        case LC32CoreGraphicsOpPDFStreamCopyData:{if(!RequireCoreGraphicsSlots(call,2))return 0;CGPDFStreamRef s=SlotHostObject<CGPDFStreamRef>(call,0);if(!s)return 0;CGPDFDataFormat f;CFDataRef d=CGPDFStreamCopyData(s,&f);if(!d||Dynarmic_mem_1write(SlotU32(call,1),sizeof(f),reinterpret_cast<char *>(&f))!=0){if(d)CFRelease(d);return 0;}return LC32GuestObjectForOwnedHostObject(d);}
        case LC32CoreGraphicsOpPDFStreamGetDictionary:{if(!RequireCoreGraphicsSlots(call,1))return 0;CGPDFStreamRef s=SlotHostObject<CGPDFStreamRef>(call,0);CGPDFDictionaryRef d=s?CGPDFStreamGetDictionary(s):nullptr;return d?[(id)d guest_self]:0;}
        case LC32CoreGraphicsOpPDFStringGetLength:{if(!RequireCoreGraphicsSlots(call,1))return 0;CGPDFStringRef s=SlotHostObject<CGPDFStringRef>(call,0);return s?static_cast<u32>(CGPDFStringGetLength(s)):0;}
'''
 z='    }\n    return 0;\n}\n\n__END_DECLS'
 if z not in x:raise SystemExit('second PDF switch anchor missing')
 x=x.replace(z,c+z,1);X.write_text(x)
print('CoreGraphics: added 12 typed non-callback PDF exports')


# Third PDF batch: typed borrowed objects, scanner outputs and persistent string bytes.
h=H.read_text();a='    LC32CoreGraphicsOpPDFStringGetLength = 209,\n'
if 'LC32CoreGraphicsOpPDFArrayGetObject = 210' not in h:
 if a not in h:raise SystemExit('third PDF opcode anchor missing')
 h=h.replace(a,a+r'''    LC32CoreGraphicsOpPDFArrayGetObject = 210,
    LC32CoreGraphicsOpPDFObjectGetType = 211,
    LC32CoreGraphicsOpPDFScannerPopNumber = 212,
    LC32CoreGraphicsOpPDFScannerPopObject = 213,
    LC32CoreGraphicsOpPDFStringCopyBytes = 214,
''');H.write_text(h)
g=G.read_text()
if 'bool CGPDFArrayGetObject(' not in g:
 g+=r'''
bool CGPDFArrayGetObject(CGPDFArrayRef a,size_t i,CGPDFObjectRef *v){return a&&v&&LC32_CG_CALL(LC32CoreGraphicsOpPDFArrayGetObject,LC32_CG_HOST(a),LC32_CG_U32(i),LC32_CG_U32((uintptr_t)v));}
CGPDFObjectType CGPDFObjectGetType(CGPDFObjectRef o){return o?(CGPDFObjectType)LC32_CG_CALL(LC32CoreGraphicsOpPDFObjectGetType,LC32_CG_HOST(o)):kCGPDFObjectTypeNull;}
bool CGPDFScannerPopNumber(CGPDFScannerRef s,CGPDFReal *v){return s&&v&&LC32_CG_CALL(LC32CoreGraphicsOpPDFScannerPopNumber,LC32_CG_HOST(s),LC32_CG_U32((uintptr_t)v));}
bool CGPDFScannerPopObject(CGPDFScannerRef s,CGPDFObjectRef *v){return s&&v&&LC32_CG_CALL(LC32CoreGraphicsOpPDFScannerPopObject,LC32_CG_HOST(s),LC32_CG_U32((uintptr_t)v));}
const unsigned char *CGPDFStringGetBytePtr(CGPDFStringRef s){if(!s)return NULL;size_t n=CGPDFStringGetLength(s);if(!n)return (const unsigned char *)"";unsigned char *p=LC32GetAssociatedGuestBuffer((id)s,(uint32_t)n);return p&&LC32_CG_CALL(LC32CoreGraphicsOpPDFStringCopyBytes,LC32_CG_HOST(s),LC32_CG_U32((uintptr_t)p),LC32_CG_U32(n))?p:NULL;}
''';G.write_text(g)
x=X.read_text()
if 'case LC32CoreGraphicsOpPDFArrayGetObject:' not in x:
 c=r'''
        case LC32CoreGraphicsOpPDFArrayGetObject:{if(!RequireCoreGraphicsSlots(call,3))return 0;CGPDFArrayRef a=SlotHostObject<CGPDFArrayRef>(call,0);if(!a)return 0;CGPDFObjectRef o=nullptr;if(!CGPDFArrayGetObject(a,SlotU32(call,1),&o)||!o)return 0;u32 guest=[(id)o guest_self];return guest&&Dynarmic_mem_1write(SlotU32(call,2),sizeof(guest),reinterpret_cast<char *>(&guest))==0;}
        case LC32CoreGraphicsOpPDFObjectGetType:{if(!RequireCoreGraphicsSlots(call,1))return 0;CGPDFObjectRef o=SlotHostObject<CGPDFObjectRef>(call,0);return o?static_cast<u32>(CGPDFObjectGetType(o)):0;}
        case LC32CoreGraphicsOpPDFScannerPopNumber:{if(!RequireCoreGraphicsSlots(call,2))return 0;CGPDFScannerRef s=SlotHostObject<CGPDFScannerRef>(call,0);if(!s)return 0;CGPDFReal value=0;if(!CGPDFScannerPopNumber(s,&value))return 0;CGFloat out=value;return WriteGuestCoreGraphicsFloats(SlotU32(call,1),&out,1);}
        case LC32CoreGraphicsOpPDFScannerPopObject:{if(!RequireCoreGraphicsSlots(call,2))return 0;CGPDFScannerRef s=SlotHostObject<CGPDFScannerRef>(call,0);if(!s)return 0;CGPDFObjectRef o=nullptr;if(!CGPDFScannerPopObject(s,&o)||!o)return 0;u32 guest=[(id)o guest_self];return guest&&Dynarmic_mem_1write(SlotU32(call,1),sizeof(guest),reinterpret_cast<char *>(&guest))==0;}
        case LC32CoreGraphicsOpPDFStringCopyBytes:{if(!RequireCoreGraphicsSlots(call,3))return 0;CGPDFStringRef s=SlotHostObject<CGPDFStringRef>(call,0);size_t n=SlotU32(call,2);if(!s||!n||n!=CGPDFStringGetLength(s))return 0;const unsigned char *p=CGPDFStringGetBytePtr(s);return p&&Dynarmic_mem_1write(SlotU32(call,1),n,const_cast<char *>(reinterpret_cast<const char *>(p)))==0;}
'''
 z='    }\n    return 0;\n}\n\n__END_DECLS'
 if z not in x:raise SystemExit('third PDF switch anchor missing')
 x=x.replace(z,c+z,1);X.write_text(x)
print('CoreGraphics: added 5 typed PDF object/scanner/string exports')


# Fourth batch: real host-to-guest CoreGraphics callback execution.
h=H.read_text();a='    LC32CoreGraphicsOpPDFStringCopyBytes = 214,\n'
if 'LC32CoreGraphicsOpFunctionCreate = 215' not in h:
 if a not in h:raise SystemExit('callback opcode anchor missing')
 h=h.replace(a,a+r'''    LC32CoreGraphicsOpFunctionCreate = 215,
    LC32CoreGraphicsOpPathApply = 216,
    LC32CoreGraphicsOpPDFDictionaryApplyFunction = 217,
''');H.write_text(h)
g=G.read_text()
if 'CGFunctionRef CGFunctionCreate(' not in g:
 g+=r'''
CGFunctionRef CGFunctionCreate(void *info,size_t domainDimension,const CGFloat *domain,size_t rangeDimension,const CGFloat *range,const CGFunctionCallbacks *callbacks){if(!callbacks||!callbacks->evaluate)return NULL;return (CGFunctionRef)LC32_CG_CALL(LC32CoreGraphicsOpFunctionCreate,LC32_CG_U32((uintptr_t)info),LC32_CG_U32(domainDimension),LC32_CG_U32((uintptr_t)domain),LC32_CG_U32(rangeDimension),LC32_CG_U32((uintptr_t)range),LC32_CG_U32(callbacks->version),LC32_CG_U32((uintptr_t)callbacks->evaluate),LC32_CG_U32((uintptr_t)callbacks->releaseInfo));}
void CGPathApply(CGPathRef path,void *info,CGPathApplierFunction function){if(path&&function)(void)LC32_CG_CALL(LC32CoreGraphicsOpPathApply,LC32_CG_HOST(path),LC32_CG_U32((uintptr_t)info),LC32_CG_U32((uintptr_t)function));}
void CGPDFDictionaryApplyFunction(CGPDFDictionaryRef d,CGPDFDictionaryApplierFunction function,void *info){if(d&&function)(void)LC32_CG_CALL(LC32CoreGraphicsOpPDFDictionaryApplyFunction,LC32_CG_HOST(d),LC32_CG_U32((uintptr_t)function),LC32_CG_U32((uintptr_t)info));}
''';G.write_text(g)
x=X.read_text()
if 'struct CoreGraphicsFunctionCallbackContext' not in x:
 helper=r'''
struct CoreGraphicsGuestStackBuffer {
    u32 original=0,address=0;size_t size=0;
    CoreGraphicsGuestStackBuffer(const void *bytes,size_t count){if(!count||!Dynarmic_guest_thread_is_registered()||!threadHandle.jit)return;size=(count+7u)&~size_t{7};original=threadHandle.jit->Regs()[Reg::SP];if(original<size)return;address=(original-static_cast<u32>(size))&~7u;if(static_cast<uint64_t>(address)+count>static_cast<uint64_t>(UINT32_MAX)+1)return;threadHandle.jit->Regs()[Reg::SP]=address;if(Dynarmic_mem_1write(address,count,const_cast<char *>(reinterpret_cast<const char *>(bytes)))!=0){threadHandle.jit->Regs()[Reg::SP]=original;address=0;}}
    ~CoreGraphicsGuestStackBuffer(){if(address&&threadHandle.jit)threadHandle.jit->Regs()[Reg::SP]=original;}
    bool read(void *bytes,size_t count){return address&&count<=size&&Dynarmic_mem_1read(address,count,reinterpret_cast<char *>(bytes))==0;}
};
bool InvokeCoreGraphicsGuestVoid(u32 function,const u32 *arguments,size_t count){if(!function||count>LC32_GUEST_BLOCK_CALLBACK_MAX_ARGUMENTS)return false;if(Dynarmic_guest_thread_is_registered()){LC32InvokeGuestC(function,false,static_cast<int>(count),const_cast<u32 *>(arguments));return true;}LC32GuestBlockCallbackDescriptor d={};d.kind=LC32GuestBlockCallbackKindFunction;d.guestInvoke=function;d.argumentCount=static_cast<u32>(count);d.resultKind=LC32GuestBlockValueVoid;for(size_t i=0;i<count;i++){d.arguments[i].kind=LC32GuestBlockValueUnsigned32;d.arguments[i].value=arguments[i];}return Dynarmic_submit_guest_function_callback(&d);}
struct CoreGraphicsFunctionCallbackContext{u32 info=0,evaluate=0,release=0;size_t domainDimension=0,rangeDimension=0;};
void CoreGraphicsFunctionEvaluate(void *raw,const CGFloat *input,CGFloat *output){auto *c=static_cast<CoreGraphicsFunctionCallbackContext *>(raw);if(!c||!output)return;for(size_t i=0;i<c->rangeDimension;i++)output[i]=0;if(!c->evaluate||!input||!Dynarmic_guest_thread_is_registered())return;std::vector<float> storage(c->domainDimension+c->rangeDimension);for(size_t i=0;i<c->domainDimension;i++)storage[i]=static_cast<float>(input[i]);CoreGraphicsGuestStackBuffer b(storage.data(),storage.size()*sizeof(float));if(!b.address)return;u32 args[]={c->info,b.address,b.address+static_cast<u32>(c->domainDimension*sizeof(float))};if(!InvokeCoreGraphicsGuestVoid(c->evaluate,args,3)||!b.read(storage.data(),storage.size()*sizeof(float)))return;for(size_t i=0;i<c->rangeDimension;i++)output[i]=storage[c->domainDimension+i];}
void CoreGraphicsFunctionRelease(void *raw){auto *c=static_cast<CoreGraphicsFunctionCallbackContext *>(raw);if(!c)return;if(c->release){u32 args[]={c->info};InvokeCoreGraphicsGuestVoid(c->release,args,1);}delete c;}
struct CoreGraphicsPathCallbackContext{u32 info=0,function=0;};
void CoreGraphicsPathCallback(void *raw,const CGPathElement *element){auto *c=static_cast<CoreGraphicsPathCallbackContext *>(raw);if(!c||!c->function||!element||!Dynarmic_guest_thread_is_registered())return;size_t n=element->type==kCGPathElementAddCurveToPoint?3:element->type==kCGPathElementAddQuadCurveToPoint?2:element->type==kCGPathElementCloseSubpath?0:1;std::vector<u32> words(2+n*2);words[0]=static_cast<u32>(element->type);words[1]=n?0:0;for(size_t i=0;i<n;i++){float x=element->points[i].x,y=element->points[i].y;memcpy(&words[2+i*2],&x,4);memcpy(&words[3+i*2],&y,4);}CoreGraphicsGuestStackBuffer b(words.data(),words.size()*4);if(!b.address)return;if(n){u32 points=b.address+8;Dynarmic_mem_1write(b.address+4,4,reinterpret_cast<char *>(&points));}u32 args[]={c->info,b.address};InvokeCoreGraphicsGuestVoid(c->function,args,2);}
struct CoreGraphicsPDFDictionaryContext{u32 function=0,info=0;};
void CoreGraphicsPDFDictionaryCallback(const char *key,CGPDFObjectRef value,void *raw){auto *c=static_cast<CoreGraphicsPDFDictionaryContext *>(raw);if(!c||!c->function||!key||!Dynarmic_guest_thread_is_registered())return;CoreGraphicsGuestStackBuffer b(key,strlen(key)+1);if(!b.address)return;u32 guestValue=value?[(id)value guest_self]:0;u32 args[]={b.address,guestValue,c->info};InvokeCoreGraphicsGuestVoid(c->function,args,3);}

'''
 a='} // namespace\n\n__BEGIN_DECLS'
 if a not in x:raise SystemExit('callback namespace anchor missing')
 x=x.replace(a,helper+a,1)
if 'case LC32CoreGraphicsOpFunctionCreate:' not in x:
 c=r'''
        case LC32CoreGraphicsOpFunctionCreate:{if(!RequireCoreGraphicsSlots(call,8))return 0;size_t dn=SlotU32(call,1),rn=SlotU32(call,3);if(!dn||!rn||dn>4096||rn>4096||SlotU32(call,5)!=0||!SlotU32(call,6))return 0;std::vector<CGFloat> domain,range;const CGFloat *dp=nullptr,*rp=nullptr;if(!ReadGuestCGFloatArray(SlotU32(call,2),dn*2,true,domain,dp)||!ReadGuestCGFloatArray(SlotU32(call,4),rn*2,true,range,rp))return 0;auto *ctx=new(std::nothrow) CoreGraphicsFunctionCallbackContext{SlotU32(call,0),SlotU32(call,6),SlotU32(call,7),dn,rn};if(!ctx)return 0;CGFunctionCallbacks cb={0,CoreGraphicsFunctionEvaluate,CoreGraphicsFunctionRelease};CGFunctionRef f=CGFunctionCreate(ctx,dn,dp,rn,rp,&cb);if(!f){delete ctx;return 0;}return LC32GuestObjectForOwnedHostObject(f);}
        case LC32CoreGraphicsOpPathApply:{if(!RequireCoreGraphicsSlots(call,3))return 0;CGPathRef p=SlotHostObject<CGPathRef>(call,0);if(!p||!SlotU32(call,2))return 0;CoreGraphicsPathCallbackContext ctx={SlotU32(call,1),SlotU32(call,2)};CGPathApply(p,&ctx,CoreGraphicsPathCallback);return 1;}
        case LC32CoreGraphicsOpPDFDictionaryApplyFunction:{if(!RequireCoreGraphicsSlots(call,3))return 0;CGPDFDictionaryRef d=SlotHostObject<CGPDFDictionaryRef>(call,0);if(!d||!SlotU32(call,1))return 0;CoreGraphicsPDFDictionaryContext ctx={SlotU32(call,1),SlotU32(call,2)};CGPDFDictionaryApplyFunction(d,CoreGraphicsPDFDictionaryCallback,&ctx);return 1;}
'''
 z='    }\n    return 0;\n}\n\n__END_DECLS'
 if z not in x:raise SystemExit('callback switch anchor missing')
 x=x.replace(z,c+z,1)
X.write_text(x)
print('CoreGraphics: added real CGFunction, CGPath and PDF dictionary guest callbacks')


# Fifth batch: type-safe PDF values and dynamically generated operator callbacks.
h=H.read_text();a='    LC32CoreGraphicsOpPDFDictionaryApplyFunction = 217,\n'
if 'LC32CoreGraphicsOpPDFObjectGetValue = 218' not in h:
 if a not in h:raise SystemExit('final PDF opcode anchor missing')
 h=h.replace(a,a+r'''    LC32CoreGraphicsOpPDFObjectGetValue = 218,
    LC32CoreGraphicsOpPDFOperatorTableCreate = 219,
    LC32CoreGraphicsOpPDFOperatorTableSetCallback = 220,
    LC32CoreGraphicsOpPDFScannerCreate = 221,
    LC32CoreGraphicsOpPDFScannerScan = 222,
''');H.write_text(h)
g=G.read_text()
if 'bool CGPDFObjectGetValue(' not in g:
 g+=r'''
bool CGPDFObjectGetValue(CGPDFObjectRef o,CGPDFObjectType type,void *value){if(!o)return false;if(type==kCGPDFObjectTypeName){if(!value)return false;uint32_t n=LC32_CG_CALL(LC32CoreGraphicsOpPDFObjectGetValue,LC32_CG_HOST(o),LC32_CG_U32(type),0,0);if(!n)return false;char *p=LC32GetAssociatedGuestBuffer((id)o,n);if(!p||!LC32_CG_CALL(LC32CoreGraphicsOpPDFObjectGetValue,LC32_CG_HOST(o),LC32_CG_U32(type),LC32_CG_U32((uintptr_t)p),LC32_CG_U32(n)))return false;*(const char **)value=p;return true;}return LC32_CG_CALL(LC32CoreGraphicsOpPDFObjectGetValue,LC32_CG_HOST(o),LC32_CG_U32(type),LC32_CG_U32((uintptr_t)value),0);}
CGPDFOperatorTableRef CGPDFOperatorTableCreate(void){return (CGPDFOperatorTableRef)LC32_CG_CALL0(LC32CoreGraphicsOpPDFOperatorTableCreate);}
void CGPDFOperatorTableSetCallback(CGPDFOperatorTableRef t,const char *name,CGPDFOperatorCallback callback){if(!t||!name||!callback)return;size_t n=strnlen(name,LC32CoreGraphicsMaximumFilenameBytes+1);if(n<=LC32CoreGraphicsMaximumFilenameBytes)(void)LC32_CG_CALL(LC32CoreGraphicsOpPDFOperatorTableSetCallback,LC32_CG_HOST(t),LC32_CG_U32((uintptr_t)name),LC32_CG_U32(n),LC32_CG_U32((uintptr_t)callback));}
CGPDFScannerRef CGPDFScannerCreate(CGPDFContentStreamRef stream,CGPDFOperatorTableRef table,void *info){return stream&&table?(CGPDFScannerRef)LC32_CG_CALL(LC32CoreGraphicsOpPDFScannerCreate,LC32_CG_HOST(stream),LC32_CG_HOST(table),LC32_CG_U32((uintptr_t)info)):NULL;}
bool CGPDFScannerScan(CGPDFScannerRef scanner){return scanner&&LC32_CG_CALL(LC32CoreGraphicsOpPDFScannerScan,LC32_CG_HOST(scanner));}
''';G.write_text(g)
x=X.read_text()
if '#include <objc/runtime.h>' not in x:x=x.replace('#include <vector>','#include <vector>\n#include <objc/runtime.h>',1)
if 'std::mutex pdfScannerCallbacksMutex;' not in x:
 helper=r'''
std::mutex pdfScannerCallbacksMutex;
std::unordered_map<CGPDFScannerRef,u32> pdfScannerGuestInfos;
std::vector<IMP> retainedPDFOperatorCallbackIMPs;
u32 GuestInfoForPDFScanner(CGPDFScannerRef scanner){std::lock_guard<std::mutex> lock(pdfScannerCallbacksMutex);auto i=pdfScannerGuestInfos.find(scanner);return i==pdfScannerGuestInfos.end()?0:i->second;}
void RegisterPDFScannerInfo(CGPDFScannerRef scanner,u32 info){std::lock_guard<std::mutex> lock(pdfScannerCallbacksMutex);pdfScannerGuestInfos[scanner]=info;}
IMP CreatePDFOperatorCallbackIMP(u32 guestCallback){
    if(!guestCallback)return nullptr;
    id block=[^(CGPDFScannerRef scanner){if(!scanner)return;u32 guestScanner=[(id)scanner guest_self];u32 args[]={guestScanner,GuestInfoForPDFScanner(scanner)};InvokeCoreGraphicsGuestVoid(guestCallback,args,2);} copy];
    IMP implementation=imp_implementationWithBlock(block);[block release];
    if(implementation){std::lock_guard<std::mutex> lock(pdfScannerCallbacksMutex);if(retainedPDFOperatorCallbackIMPs.size()>=4096){imp_removeBlock(implementation);return nullptr;}retainedPDFOperatorCallbackIMPs.push_back(implementation);}return implementation;
}

'''
 a='} // namespace\n\n__BEGIN_DECLS'
 if a not in x:raise SystemExit('final callback namespace anchor missing')
 x=x.replace(a,helper+a,1)
if 'case LC32CoreGraphicsOpPDFObjectGetValue:' not in x:
 c=r'''
        case LC32CoreGraphicsOpPDFObjectGetValue:{if(!RequireCoreGraphicsSlots(call,4))return 0;CGPDFObjectRef o=SlotHostObject<CGPDFObjectRef>(call,0);CGPDFObjectType type=(CGPDFObjectType)SlotU32(call,1);u32 out=SlotU32(call,2),capacity=SlotU32(call,3);if(!o||type<kCGPDFObjectTypeNull||type>kCGPDFObjectTypeStream)return 0;if(type==kCGPDFObjectTypeNull)return CGPDFObjectGetValue(o,type,nullptr);if(type==kCGPDFObjectTypeName){const char *name=nullptr;if(!CGPDFObjectGetValue(o,type,&name)||!name)return 0;size_t n=strlen(name)+1;if(!out)return n<=UINT32_MAX?static_cast<u32>(n):0;return capacity>=n&&Dynarmic_mem_1write(out,n,const_cast<char *>(name))==0;}if(!out)return 0;if(type==kCGPDFObjectTypeBoolean){CGPDFBoolean v=false;if(!CGPDFObjectGetValue(o,type,&v))return 0;uint8_t b=v?1:0;return Dynarmic_mem_1write(out,1,reinterpret_cast<char *>(&b))==0;}if(type==kCGPDFObjectTypeInteger){CGPDFInteger v=0;if(!CGPDFObjectGetValue(o,type,&v)||v<INT32_MIN||v>INT32_MAX)return 0;int32_t q=static_cast<int32_t>(v);return Dynarmic_mem_1write(out,4,reinterpret_cast<char *>(&q))==0;}if(type==kCGPDFObjectTypeReal){CGPDFReal v=0;if(!CGPDFObjectGetValue(o,type,&v))return 0;CGFloat q=v;return WriteGuestCoreGraphicsFloats(out,&q,1);}const void *v=nullptr;if(!CGPDFObjectGetValue(o,type,&v)||!v)return 0;u32 guest=[(id)v guest_self];return guest&&Dynarmic_mem_1write(out,4,reinterpret_cast<char *>(&guest))==0;}
        case LC32CoreGraphicsOpPDFOperatorTableCreate:{if(!RequireCoreGraphicsSlots(call,0))return 0;CGPDFOperatorTableRef t=CGPDFOperatorTableCreate();return t?LC32GuestObjectForOwnedHostObject(t):0;}
        case LC32CoreGraphicsOpPDFOperatorTableSetCallback:{if(!RequireCoreGraphicsSlots(call,4))return 0;CGPDFOperatorTableRef t=SlotHostObject<CGPDFOperatorTableRef>(call,0);std::vector<char> name;if(!t||!ReadGuestCoreGraphicsBytes(SlotU32(call,1),SlotU32(call,2),name)||!SlotU32(call,3))return 0;IMP imp=CreatePDFOperatorCallbackIMP(SlotU32(call,3));if(!imp)return 0;CGPDFOperatorTableSetCallback(t,name.data(),reinterpret_cast<CGPDFOperatorCallback>(imp));return 1;}
        case LC32CoreGraphicsOpPDFScannerCreate:{if(!RequireCoreGraphicsSlots(call,3))return 0;CGPDFContentStreamRef s=SlotHostObject<CGPDFContentStreamRef>(call,0);CGPDFOperatorTableRef t=SlotHostObject<CGPDFOperatorTableRef>(call,1);if(!s||!t)return 0;CGPDFScannerRef scanner=CGPDFScannerCreate(s,t,reinterpret_cast<void *>(static_cast<uintptr_t>(SlotU32(call,2))));if(!scanner)return 0;RegisterPDFScannerInfo(scanner,SlotU32(call,2));return LC32GuestObjectForOwnedHostObject(scanner);}
        case LC32CoreGraphicsOpPDFScannerScan:{if(!RequireCoreGraphicsSlots(call,1))return 0;CGPDFScannerRef s=SlotHostObject<CGPDFScannerRef>(call,0);return s&&CGPDFScannerScan(s);}
'''
 z='    }\n    return 0;\n}\n\n__END_DECLS'
 if z not in x:raise SystemExit('final callback switch anchor missing')
 x=x.replace(z,c+z,1)
X.write_text(x)
print('CoreGraphics: added typed PDF values and dynamic guest operator callbacks')
