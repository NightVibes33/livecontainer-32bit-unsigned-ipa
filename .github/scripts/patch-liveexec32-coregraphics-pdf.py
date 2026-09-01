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
