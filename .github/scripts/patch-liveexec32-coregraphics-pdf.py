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
