#!/usr/bin/env python3
from pathlib import Path
p=Path('build/LiveExec32/GuestFrameworks/AudioToolbox/AudioToolbox.m');s=p.read_text()
if 'LC32GuestAUGraphMagic' not in s:
 s+=r'''
#pragma mark Guest-owned AUGraph compatibility
#define LC32GuestAUGraphMagic 0x4c434147u
#define LC32GuestAUGraphMaximumNodes 64u
typedef struct {AUNode id;AudioComponentDescription desc;AudioUnit unit;AURenderCallbackStruct callback;BOOL hasCallback;} LC32GuestAUGraphNode;
typedef struct {uint32_t magic;pthread_mutex_t mutex;BOOL opened,initialized,running;AUNode next;uint32_t count;LC32GuestAUGraphNode nodes[LC32GuestAUGraphMaximumNodes];} LC32GuestAUGraph;
static LC32GuestAUGraph *LC32Graph(AUGraph v){LC32GuestAUGraph *g=(LC32GuestAUGraph *)v;return g&&g->magic==LC32GuestAUGraphMagic?g:NULL;}
static LC32GuestAUGraphNode *LC32GraphFind(LC32GuestAUGraph *g,AUNode id){for(uint32_t i=0;i<g->count;i++)if(g->nodes[i].id==id)return &g->nodes[i];return NULL;}
static OSStatus LC32GraphUnit(LC32GuestAUGraphNode *n){return n->unit?noErr:AudioComponentInstanceNew((AudioComponent)&LC32SilentRemoteIOComponent,(AudioComponentInstance *)&n->unit);}
OSStatus NewAUGraph(AUGraph *out){if(!out)return kAudio_ParamError;*out=NULL;LC32GuestAUGraph *g=calloc(1,sizeof(*g));if(!g)return kAudio_MemFullError;if(pthread_mutex_init(&g->mutex,NULL)){free(g);return kAudio_MemFullError;}g->magic=LC32GuestAUGraphMagic;g->next=1;*out=(AUGraph)g;return noErr;}
OSStatus DisposeAUGraph(AUGraph value){LC32GuestAUGraph *g=LC32Graph(value);if(!g)return kAudio_ParamError;AUGraphStop(value);pthread_mutex_lock(&g->mutex);for(uint32_t i=0;i<g->count;i++)if(g->nodes[i].unit)AudioComponentInstanceDispose((AudioComponentInstance)g->nodes[i].unit);g->magic=0;pthread_mutex_unlock(&g->mutex);pthread_mutex_destroy(&g->mutex);free(g);return noErr;}
OSStatus AUGraphAddNode(AUGraph value,const AudioComponentDescription *desc,AUNode *out){LC32GuestAUGraph *g=LC32Graph(value);if(!g||!desc||!out)return kAudio_ParamError;pthread_mutex_lock(&g->mutex);if(g->count==LC32GuestAUGraphMaximumNodes){pthread_mutex_unlock(&g->mutex);return kAudio_MemFullError;}LC32GuestAUGraphNode *n=&g->nodes[g->count++];n->id=g->next++;n->desc=*desc;*out=n->id;pthread_mutex_unlock(&g->mutex);return noErr;}
OSStatus AUGraphOpen(AUGraph value){LC32GuestAUGraph *g=LC32Graph(value);if(!g)return kAudio_ParamError;pthread_mutex_lock(&g->mutex);OSStatus status=noErr;for(uint32_t i=0;i<g->count&&status==noErr;i++)status=LC32GraphUnit(&g->nodes[i]);if(status==noErr)g->opened=YES;pthread_mutex_unlock(&g->mutex);return status;}
OSStatus AUGraphClose(AUGraph value){LC32GuestAUGraph *g=LC32Graph(value);if(!g)return kAudio_ParamError;AUGraphStop(value);pthread_mutex_lock(&g->mutex);for(uint32_t i=0;i<g->count;i++){if(g->nodes[i].unit)AudioComponentInstanceDispose((AudioComponentInstance)g->nodes[i].unit);g->nodes[i].unit=NULL;}g->opened=g->initialized=NO;pthread_mutex_unlock(&g->mutex);return noErr;}
OSStatus AUGraphNodeInfo(AUGraph value,AUNode id,AudioComponentDescription *desc,AudioUnit *unit){LC32GuestAUGraph *g=LC32Graph(value);if(!g)return kAudio_ParamError;pthread_mutex_lock(&g->mutex);LC32GuestAUGraphNode *n=LC32GraphFind(g,id);OSStatus status=n?LC32GraphUnit(n):kAUGraphErr_NodeNotFound;if(status==noErr){if(desc)*desc=n->desc;if(unit)*unit=n->unit;}pthread_mutex_unlock(&g->mutex);return status;}
OSStatus AUGraphConnectNodeInput(AUGraph value,AUNode source,UInt32 sourceOutput,AUNode destination,UInt32 destinationInput){(void)sourceOutput;(void)destinationInput;LC32GuestAUGraph *g=LC32Graph(value);if(!g)return kAudio_ParamError;pthread_mutex_lock(&g->mutex);BOOL found=LC32GraphFind(g,source)&&LC32GraphFind(g,destination);pthread_mutex_unlock(&g->mutex);return found?noErr:kAUGraphErr_NodeNotFound;}
OSStatus AUGraphSetNodeInputCallback(AUGraph value,AUNode id,UInt32 input,const AURenderCallbackStruct *callback){(void)input;LC32GuestAUGraph *g=LC32Graph(value);if(!g||!callback||!callback->inputProc)return kAudio_ParamError;pthread_mutex_lock(&g->mutex);LC32GuestAUGraphNode *n=LC32GraphFind(g,id);if(n){n->callback=*callback;n->hasCallback=YES;}pthread_mutex_unlock(&g->mutex);return n?noErr:kAUGraphErr_NodeNotFound;}
OSStatus AUGraphInitialize(AUGraph value){LC32GuestAUGraph *g=LC32Graph(value);if(!g)return kAudio_ParamError;OSStatus status=AUGraphOpen(value);if(status)return status;pthread_mutex_lock(&g->mutex);g->initialized=YES;pthread_mutex_unlock(&g->mutex);return noErr;}
OSStatus AUGraphUninitialize(AUGraph value){LC32GuestAUGraph *g=LC32Graph(value);if(!g)return kAudio_ParamError;AUGraphStop(value);pthread_mutex_lock(&g->mutex);g->initialized=NO;pthread_mutex_unlock(&g->mutex);return noErr;}
OSStatus AUGraphIsInitialized(AUGraph value,Boolean *out){LC32GuestAUGraph *g=LC32Graph(value);if(!g||!out)return kAudio_ParamError;pthread_mutex_lock(&g->mutex);*out=g->initialized;pthread_mutex_unlock(&g->mutex);return noErr;}
OSStatus AUGraphIsRunning(AUGraph value,Boolean *out){LC32GuestAUGraph *g=LC32Graph(value);if(!g||!out)return kAudio_ParamError;pthread_mutex_lock(&g->mutex);*out=g->running;pthread_mutex_unlock(&g->mutex);return noErr;}
OSStatus AUGraphStart(AUGraph value){LC32GuestAUGraph *g=LC32Graph(value);if(!g)return kAudio_ParamError;OSStatus status=AUGraphInitialize(value);if(status)return status;pthread_mutex_lock(&g->mutex);LC32GuestAUGraphNode *output=NULL,*source=NULL;for(uint32_t i=0;i<g->count;i++){if(!source&&g->nodes[i].hasCallback)source=&g->nodes[i];if(!output&&g->nodes[i].desc.componentType==kAudioUnitType_Output)output=&g->nodes[i];}if(!output&&g->count)output=&g->nodes[0];if(!output){pthread_mutex_unlock(&g->mutex);return kAUGraphErr_NodeNotFound;}status=LC32GraphUnit(output);if(status==noErr&&source)status=AudioUnitSetProperty(output->unit,kAudioUnitProperty_SetRenderCallback,kAudioUnitScope_Global,0,&source->callback,sizeof(source->callback));if(status==noErr)status=AudioUnitInitialize(output->unit);if(status==noErr)status=AudioOutputUnitStart(output->unit);if(status==noErr)g->running=YES;pthread_mutex_unlock(&g->mutex);return status;}
OSStatus AUGraphStop(AUGraph value){LC32GuestAUGraph *g=LC32Graph(value);if(!g)return kAudio_ParamError;pthread_mutex_lock(&g->mutex);OSStatus status=noErr;for(uint32_t i=0;i<g->count;i++)if(g->nodes[i].unit){OSStatus current=AudioOutputUnitStop(g->nodes[i].unit);if(status==noErr&&current!=noErr)status=current;}g->running=NO;pthread_mutex_unlock(&g->mutex);return status;}
'''
 p.write_text(s)
print('AudioToolbox: added guest-owned AUGraph over safe RemoteIO PCM output')


# Typed parameter, format-property and ExtAudioFile creation bridge batch.
R=Path('build/LiveExec32');H=R/'GuestFrameworks/AudioToolbox/LC32AudioToolboxBridge.h';G=R/'GuestFrameworks/AudioToolbox/AudioToolbox.m';X=R/'HostFrameworks/AudioToolbox/AudioToolbox.mm'
h=H.read_text();a='    LC32AudioToolboxOpRemoteIOOutputStop = 43,\n'
if 'LC32AudioToolboxOpAudioFormatGetProperty = 44' not in h:
 if a not in h:raise SystemExit('audio opcode anchor missing')
 h=h.replace(a,a+r'''    LC32AudioToolboxOpAudioFormatGetProperty = 44,
    LC32AudioToolboxOpAudioUnitGetParameter = 45,
    LC32AudioToolboxOpAudioUnitSetParameter = 46,
    LC32AudioToolboxOpExtAudioFileCreateWithURL = 47,
    LC32AudioToolboxOpExtAudioFileWrapAudioFileID = 48,
''');H.write_text(h)
g=G.read_text()
old='    AURenderCallbackStruct renderCallback;\n    pthread_mutex_t mutex;'
if 'parameters[64]' not in g:
 if old not in g:raise SystemExit('silent unit field anchor missing')
 g=g.replace(old,'    AURenderCallbackStruct renderCallback;\n    struct { AudioUnitParameterID id; AudioUnitScope scope; AudioUnitElement element; AudioUnitParameterValue value; BOOL used; } parameters[64];\n    pthread_mutex_t mutex;',1)
if 'OSStatus AudioUnitGetParameter(' not in g:
 g+=r'''
OSStatus AudioUnitGetParameter(AudioUnit unit,AudioUnitParameterID id,AudioUnitScope scope,AudioUnitElement element,AudioUnitParameterValue *out){LC32SilentAudioUnit *u=LC32SilentAudioUnitForHandle(unit);if(!u||!out)return kAudio_ParamError;pthread_mutex_lock(&u->mutex);OSStatus status=kAudioUnitErr_InvalidParameter;for(size_t i=0;i<64;i++)if(u->parameters[i].used&&u->parameters[i].id==id&&u->parameters[i].scope==scope&&u->parameters[i].element==element){*out=u->parameters[i].value;status=noErr;break;}pthread_mutex_unlock(&u->mutex);return status;}
OSStatus AudioUnitSetParameter(AudioUnit unit,AudioUnitParameterID id,AudioUnitScope scope,AudioUnitElement element,AudioUnitParameterValue value,UInt32 offset){(void)offset;LC32SilentAudioUnit *u=LC32SilentAudioUnitForHandle(unit);if(!u)return kAudio_ParamError;pthread_mutex_lock(&u->mutex);size_t freeIndex=64;for(size_t i=0;i<64;i++){if(u->parameters[i].used&&u->parameters[i].id==id&&u->parameters[i].scope==scope&&u->parameters[i].element==element){freeIndex=i;break;}if(!u->parameters[i].used&&freeIndex==64)freeIndex=i;}if(freeIndex==64){pthread_mutex_unlock(&u->mutex);return kAudioUnitErr_TooManyFramesToProcess;}u->parameters[freeIndex].id=id;u->parameters[freeIndex].scope=scope;u->parameters[freeIndex].element=element;u->parameters[freeIndex].value=value;u->parameters[freeIndex].used=YES;pthread_mutex_unlock(&u->mutex);return noErr;}
OSStatus AudioFormatGetProperty(AudioFormatPropertyID property,UInt32 specifierSize,const void *specifier,UInt32 *ioSize,void *out){if(!ioSize||(specifierSize&&!specifier))return kAudio_ParamError;return (OSStatus)LC32_AUDIO_CALL(LC32AudioToolboxOpAudioFormatGetProperty,LC32_AUDIO_U32(property),LC32_AUDIO_U32(specifierSize),LC32_AUDIO_U32((uintptr_t)specifier),LC32_AUDIO_U32((uintptr_t)ioSize),LC32_AUDIO_U32((uintptr_t)out));}
OSStatus ExtAudioFileCreateWithURL(CFURLRef url,AudioFileTypeID type,const AudioStreamBasicDescription *format,const AudioChannelLayout *layout,UInt32 flags,ExtAudioFileRef *out){if(!url||!format||!out)return kAudio_ParamError;return (OSStatus)LC32_AUDIO_CALL(LC32AudioToolboxOpExtAudioFileCreateWithURL,[(id)url host_self],LC32_AUDIO_U32(type),LC32_AUDIO_U32((uintptr_t)format),LC32_AUDIO_U32((uintptr_t)layout),LC32_AUDIO_U32(flags),LC32_AUDIO_U32((uintptr_t)out));}
OSStatus ExtAudioFileWrapAudioFileID(AudioFileID file,Boolean writing,ExtAudioFileRef *out){if(!file||!out)return kAudio_ParamError;return (OSStatus)LC32_AUDIO_CALL(LC32AudioToolboxOpExtAudioFileWrapAudioFileID,LC32_AUDIO_U32((uintptr_t)file),LC32_AUDIO_U32(writing),LC32_AUDIO_U32((uintptr_t)out));}
'''
G.write_text(g)
x=X.read_text()
if 'OSStatus DispatchCorpusAudioFormatGetProperty' not in x:
 helper=r'''
OSStatus DispatchCorpusAudioFormatGetProperty(const LC32AudioToolboxCall &call){if(!RequireSlots(call,5)||!SlotU32(call,3))return kAudio_ParamError;u32 specSize=SlotU32(call,1),requested=0;if(specSize>kMaximumPropertyBytes||!ReadGuestU32(SlotU32(call,3),requested)||requested>kMaximumPropertyBytes||(specSize&&!SlotU32(call,2))||(requested&&!SlotU32(call,4)))return kAudio_ParamError;std::vector<uint8_t> spec(specSize),out(requested?requested:1);if(specSize&&Dynarmic_mem_1read(SlotU32(call,2),specSize,reinterpret_cast<char *>(spec.data()))!=0)return kAudio_ParamError;UInt32 returned=requested;OSStatus status=AudioFormatGetProperty(SlotU32(call,0),specSize,specSize?spec.data():nullptr,&returned,requested?out.data():nullptr);if(!WriteGuestU32(SlotU32(call,3),returned))return kAudio_ParamError;if(status==noErr&&returned&&(returned>requested||Dynarmic_mem_1write(SlotU32(call,4),returned,reinterpret_cast<char *>(out.data()))!=0))return kAudio_ParamError;return status;}
OSStatus DispatchCorpusExtAudioFileCreate(const LC32AudioToolboxCall &call){if(!RequireSlots(call,6)||!SlotU32(call,0)||!SlotU32(call,2)||!SlotU32(call,5))return kAudio_ParamError;AudioStreamBasicDescription format={};if(Dynarmic_mem_1read(SlotU32(call,2),sizeof(format),reinterpret_cast<char *>(&format))!=0)return kAudio_ParamError;std::vector<uint8_t> layoutBytes;AudioChannelLayout *layout=nullptr;if(SlotU32(call,3)){struct{u32 tag,bitmap,count;} header={};if(Dynarmic_mem_1read(SlotU32(call,3),sizeof(header),reinterpret_cast<char *>(&header))!=0||header.count>1024)return kAudio_ParamError;size_t bytes=offsetof(AudioChannelLayout,mChannelDescriptions)+header.count*sizeof(AudioChannelDescription);layoutBytes.resize(bytes);if(Dynarmic_mem_1read(SlotU32(call,3),bytes,reinterpret_cast<char *>(layoutBytes.data()))!=0)return kAudio_ParamError;layout=reinterpret_cast<AudioChannelLayout *>(layoutBytes.data());}ExtAudioFileRef file=nullptr;OSStatus status=ExtAudioFileCreateWithURL(SlotHostObject<CFURLRef>(call,0),SlotU32(call,1),&format,layout,SlotU32(call,4),&file);if(status!=noErr)return status;u32 token=InsertExtAudioFile(file);if(!token||!WriteGuestU32(SlotU32(call,5),token)){if(token){auto e=TakeExtAudioFile(token);if(e&&e->file)ExtAudioFileDispose(e->file);}else ExtAudioFileDispose(file);return kAudio_ParamError;}return noErr;}
OSStatus DispatchCorpusExtAudioFileWrap(const LC32AudioToolboxCall &call){if(!RequireSlots(call,3)||!SlotU32(call,2))return kAudio_ParamError;auto source=FindAudioFile(SlotU32(call,0));if(!source)return kAudio_ParamError;ExtAudioFileRef file=nullptr;OSStatus status;{std::lock_guard<std::mutex> lock(source->mutex);if(!source->file)return kAudio_ParamError;status=ExtAudioFileWrapAudioFileID(source->file,SlotU32(call,1)!=0,&file);}if(status!=noErr)return status;u32 token=InsertExtAudioFile(file);if(!token||!WriteGuestU32(SlotU32(call,2),token)){if(token){auto e=TakeExtAudioFile(token);if(e&&e->file)ExtAudioFileDispose(e->file);}else ExtAudioFileDispose(file);return kAudio_ParamError;}return noErr;}

'''
 a='} // namespace\n\nextern "C" u32 LC32_AudioToolbox_Dispatch'
 if a not in x:raise SystemExit('audio helper anchor missing')
 x=x.replace(a,helper+a,1)
if 'case LC32AudioToolboxOpAudioFormatGetProperty:' not in x:
 cases=r'''
        case LC32AudioToolboxOpAudioFormatGetProperty:return static_cast<u32>(DispatchCorpusAudioFormatGetProperty(call));
        case LC32AudioToolboxOpExtAudioFileCreateWithURL:return static_cast<u32>(DispatchCorpusExtAudioFileCreate(call));
        case LC32AudioToolboxOpExtAudioFileWrapAudioFileID:return static_cast<u32>(DispatchCorpusExtAudioFileWrap(call));
'''
 a='        case LC32AudioToolboxOpRemoteIOOutputStart:'
 if a not in x:raise SystemExit('audio switch anchor missing')
 x=x.replace(a,cases+a,1)
X.write_text(x)
print('AudioToolbox: added parameters, format properties, and ExtAudioFile creation')


# ExtAudioFile write bridge with persistent storage for asynchronous writes.
h=H.read_text();a='    LC32AudioToolboxOpExtAudioFileWrapAudioFileID = 48,\n'
if 'LC32AudioToolboxOpExtAudioFileWrite = 49' not in h:
 if a not in h:raise SystemExit('ExtAudio write opcode anchor missing')
 h=h.replace(a,a+r'''    LC32AudioToolboxOpExtAudioFileWrite = 49,
    LC32AudioToolboxOpExtAudioFileWriteAsync = 50,
''');H.write_text(h)
g=G.read_text()
if 'OSStatus ExtAudioFileWrite(' not in g:
 g+=r'''
OSStatus ExtAudioFileWrite(ExtAudioFileRef file,UInt32 frames,const AudioBufferList *data){if(!file||!data)return kAudio_ParamError;return (OSStatus)LC32_AUDIO_CALL(LC32AudioToolboxOpExtAudioFileWrite,LC32_AUDIO_U32((uintptr_t)file),LC32_AUDIO_U32(frames),LC32_AUDIO_U32((uintptr_t)data));}
OSStatus ExtAudioFileWriteAsync(ExtAudioFileRef file,UInt32 frames,const AudioBufferList *data){if(!file||!data)return kAudio_ParamError;return (OSStatus)LC32_AUDIO_CALL(LC32AudioToolboxOpExtAudioFileWriteAsync,LC32_AUDIO_U32((uintptr_t)file),LC32_AUDIO_U32(frames),LC32_AUDIO_U32((uintptr_t)data));}
''';G.write_text(g)
x=X.read_text()
old='struct ExtAudioFileEntry {\n    ExtAudioFileRef file = nullptr;\n    std::mutex mutex;\n};'
if 'asyncWriteBuffers' not in x:
 if old not in x:raise SystemExit('ExtAudio entry anchor missing')
 x=x.replace(old,'struct ExtAudioFileEntry {\n    ExtAudioFileRef file = nullptr;\n    std::unique_ptr<uint8_t[]> asyncWriteList;\n    std::vector<std::vector<uint8_t>> asyncWriteBuffers;\n    std::mutex mutex;\n};',1)
if 'OSStatus DispatchCorpusExtAudioFileWrite' not in x:
 helper=r'''
bool ReadCorpusGuestAudioBufferList(u32 address,std::unique_ptr<uint8_t[]> &listStorage,std::vector<std::vector<uint8_t>> &buffers){u32 count=0;if(!address||!ReadGuestU32(address,count)||!count||count>kMaximumAudioBuffers)return false;size_t guestBytes=static_cast<size_t>(count)*sizeof(GuestAudioBuffer);uint64_t entries=static_cast<uint64_t>(address)+sizeof(u32);if(entries+guestBytes>static_cast<uint64_t>(UINT32_MAX)+1)return false;std::vector<GuestAudioBuffer> guest(count);if(Dynarmic_mem_1read(static_cast<u32>(entries),guestBytes,reinterpret_cast<char *>(guest.data()))!=0)return false;size_t listBytes=offsetof(AudioBufferList,mBuffers)+static_cast<size_t>(count)*sizeof(AudioBuffer);listStorage=std::make_unique<uint8_t[]>(listBytes);memset(listStorage.get(),0,listBytes);AudioBufferList *list=reinterpret_cast<AudioBufferList *>(listStorage.get());list->mNumberBuffers=count;buffers.clear();buffers.resize(count);size_t total=0;for(u32 i=0;i<count;i++){if(guest[i].byteSize>kMaximumAudioBytes-total||(guest[i].byteSize&&(!guest[i].data||static_cast<uint64_t>(guest[i].data)+guest[i].byteSize>static_cast<uint64_t>(UINT32_MAX)+1)))return false;total+=guest[i].byteSize;buffers[i].resize(guest[i].byteSize);if(guest[i].byteSize&&Dynarmic_mem_1read(guest[i].data,guest[i].byteSize,reinterpret_cast<char *>(buffers[i].data()))!=0)return false;list->mBuffers[i].mNumberChannels=guest[i].channels;list->mBuffers[i].mDataByteSize=guest[i].byteSize;list->mBuffers[i].mData=guest[i].byteSize?buffers[i].data():nullptr;}return true;}
OSStatus DispatchCorpusExtAudioFileWrite(const LC32AudioToolboxCall &call,bool asynchronous){if(!RequireSlots(call,3))return kAudio_ParamError;auto entry=FindExtAudioFile(SlotU32(call,0));if(!entry)return kAudio_ParamError;std::unique_ptr<uint8_t[]> list;std::vector<std::vector<uint8_t>> buffers;if(!ReadCorpusGuestAudioBufferList(SlotU32(call,2),list,buffers))return kAudio_ParamError;std::lock_guard<std::mutex> lock(entry->mutex);if(!entry->file)return kAudio_ParamError;if(asynchronous){entry->asyncWriteList=std::move(list);entry->asyncWriteBuffers=std::move(buffers);return ExtAudioFileWriteAsync(entry->file,SlotU32(call,1),reinterpret_cast<AudioBufferList *>(entry->asyncWriteList.get()));}return ExtAudioFileWrite(entry->file,SlotU32(call,1),reinterpret_cast<AudioBufferList *>(list.get()));}

'''
 a='} // namespace\n\nextern "C" u32 LC32_AudioToolbox_Dispatch'
 if a not in x:raise SystemExit('ExtAudio write helper anchor missing')
 x=x.replace(a,helper+a,1)
if 'case LC32AudioToolboxOpExtAudioFileWrite:' not in x:
 cases=r'''
        case LC32AudioToolboxOpExtAudioFileWrite:return static_cast<u32>(DispatchCorpusExtAudioFileWrite(call,false));
        case LC32AudioToolboxOpExtAudioFileWriteAsync:return static_cast<u32>(DispatchCorpusExtAudioFileWrite(call,true));
'''
 a='        case LC32AudioToolboxOpRemoteIOOutputStart:'
 if a not in x:raise SystemExit('ExtAudio write switch anchor missing')
 x=x.replace(a,cases+a,1)
X.write_text(x)
print('AudioToolbox: added safe synchronous and persistent asynchronous ExtAudioFile writes')


# AudioFileStream lifecycle and synchronous guest callback bridge.
h=H.read_text();a='    LC32AudioToolboxOpExtAudioFileWriteAsync = 50,\n'
if 'LC32AudioToolboxOpAudioFileStreamOpen = 51' not in h:
 if a not in h:raise SystemExit('stream opcode anchor missing')
 h=h.replace(a,a+r'''    LC32AudioToolboxOpAudioFileStreamOpen = 51,
    LC32AudioToolboxOpAudioFileStreamClose = 52,
    LC32AudioToolboxOpAudioFileStreamGetProperty = 53,
    LC32AudioToolboxOpAudioFileStreamGetPropertyInfo = 54,
    LC32AudioToolboxOpAudioFileStreamParseBytes = 55,
    LC32AudioToolboxOpAudioFileStreamSeek = 56,
''');H.write_text(h)
g=G.read_text()
if 'OSStatus AudioFileStreamOpen(' not in g:
 g+=r'''
OSStatus AudioFileStreamOpen(void *client,AudioFileStream_PropertyListenerProc propertyProc,AudioFileStream_PacketsProc packetsProc,AudioFileTypeID hint,AudioFileStreamID *out){if(!propertyProc||!packetsProc||!out)return kAudio_ParamError;return (OSStatus)LC32_AUDIO_CALL(LC32AudioToolboxOpAudioFileStreamOpen,LC32_AUDIO_U32((uintptr_t)client),LC32_AUDIO_U32((uintptr_t)propertyProc),LC32_AUDIO_U32((uintptr_t)packetsProc),LC32_AUDIO_U32(hint),LC32_AUDIO_U32((uintptr_t)out));}
OSStatus AudioFileStreamClose(AudioFileStreamID stream){return stream?(OSStatus)LC32_AUDIO_CALL(LC32AudioToolboxOpAudioFileStreamClose,LC32_AUDIO_U32((uintptr_t)stream)):kAudio_ParamError;}
OSStatus AudioFileStreamGetProperty(AudioFileStreamID stream,AudioFileStreamPropertyID property,UInt32 *ioSize,void *out){if(!stream||!ioSize)return kAudio_ParamError;return (OSStatus)LC32_AUDIO_CALL(LC32AudioToolboxOpAudioFileStreamGetProperty,LC32_AUDIO_U32((uintptr_t)stream),LC32_AUDIO_U32(property),LC32_AUDIO_U32((uintptr_t)ioSize),LC32_AUDIO_U32((uintptr_t)out));}
OSStatus AudioFileStreamGetPropertyInfo(AudioFileStreamID stream,AudioFileStreamPropertyID property,UInt32 *outSize,Boolean *outWritable){if(!stream||!outSize)return kAudio_ParamError;return (OSStatus)LC32_AUDIO_CALL(LC32AudioToolboxOpAudioFileStreamGetPropertyInfo,LC32_AUDIO_U32((uintptr_t)stream),LC32_AUDIO_U32(property),LC32_AUDIO_U32((uintptr_t)outSize),LC32_AUDIO_U32((uintptr_t)outWritable));}
OSStatus AudioFileStreamParseBytes(AudioFileStreamID stream,UInt32 count,const void *data,AudioFileStreamParseFlags flags){if(!stream||(count&&!data))return kAudio_ParamError;return (OSStatus)LC32_AUDIO_CALL(LC32AudioToolboxOpAudioFileStreamParseBytes,LC32_AUDIO_U32((uintptr_t)stream),LC32_AUDIO_U32(count),LC32_AUDIO_U32((uintptr_t)data),LC32_AUDIO_U32(flags));}
OSStatus AudioFileStreamSeek(AudioFileStreamID stream,SInt64 packet,SInt64 *outOffset,AudioFileStreamSeekFlags *ioFlags){if(!stream||!outOffset||!ioFlags)return kAudio_ParamError;return (OSStatus)LC32_AUDIO_CALL(LC32AudioToolboxOpAudioFileStreamSeek,LC32_AUDIO_U32((uintptr_t)stream),(uint64_t)packet,LC32_AUDIO_U32((uintptr_t)outOffset),LC32_AUDIO_U32((uintptr_t)ioFlags));}
''';G.write_text(g)
x=X.read_text()
if 'struct CorpusAudioFileStreamEntry' not in x:
 helper=r'''
struct CorpusAudioFileStreamEntry{AudioFileStreamID stream=nullptr;u32 token=0,client=0,propertyProc=0,packetsProc=0,currentGuestData=0;const uint8_t *currentHostData=nullptr;u32 currentBytes=0;std::mutex mutex;};
std::mutex corpusAudioFileStreamsMutex;std::unordered_map<u32,std::shared_ptr<CorpusAudioFileStreamEntry>> corpusAudioFileStreams;std::atomic<u32> nextCorpusAudioFileStreamToken{1};
std::shared_ptr<CorpusAudioFileStreamEntry> FindCorpusAudioFileStream(u32 token){std::lock_guard<std::mutex> l(corpusAudioFileStreamsMutex);auto i=corpusAudioFileStreams.find(token);return i==corpusAudioFileStreams.end()?nullptr:i->second;}
u32 InsertCorpusAudioFileStream(const std::shared_ptr<CorpusAudioFileStreamEntry>& e){std::lock_guard<std::mutex> l(corpusAudioFileStreamsMutex);for(size_t n=0;n<UINT32_MAX;n++){u32 token=nextCorpusAudioFileStreamToken.fetch_add(1,std::memory_order_relaxed);if(token&&corpusAudioFileStreams.emplace(token,e).second){e->token=token;return token;}}return 0;}
std::shared_ptr<CorpusAudioFileStreamEntry> TakeCorpusAudioFileStream(u32 token){std::lock_guard<std::mutex> l(corpusAudioFileStreamsMutex);auto i=corpusAudioFileStreams.find(token);if(i==corpusAudioFileStreams.end())return {};auto e=i->second;corpusAudioFileStreams.erase(i);return e;}
u32 AllocateCorpusGuestBytes(size_t size){return size&&size<=UINT32_MAX?AllocateGuestAudioFileCallbackBytes(static_cast<u32>(size)):0;}
void CorpusAudioFileStreamPropertyCallback(void *raw,AudioFileStreamID,AudioFileStreamPropertyID property,AudioFileStreamPropertyFlags *flags){auto *e=static_cast<CorpusAudioFileStreamEntry *>(raw);if(!e||!e->propertyProc||!Dynarmic_guest_thread_is_registered())return;u32 guestFlags=AllocateCorpusGuestBytes(sizeof(u32));if(!guestFlags)return;u32 value=flags?*flags:0;WriteGuestU32(guestFlags,value);u32 args[]={e->client,e->token,property,guestFlags};InvokeGuestAudioQueueFunction(e->propertyProc,args,4);if(flags&&ReadGuestU32(guestFlags,value))*flags=value;guest_free(guestFlags);}
void CorpusAudioFileStreamPacketsCallback(void *raw,UInt32 bytes,UInt32 packets,const void *input,AudioStreamPacketDescription *descriptions){auto *e=static_cast<CorpusAudioFileStreamEntry *>(raw);if(!e||!e->packetsProc||!Dynarmic_guest_thread_is_registered())return;u32 guestData=0;if(input&&e->currentHostData){ptrdiff_t offset=static_cast<const uint8_t *>(input)-e->currentHostData;if(offset>=0&&static_cast<uint64_t>(offset)+bytes<=e->currentBytes)guestData=e->currentGuestData+static_cast<u32>(offset);}u32 guestDescriptions=0;if(descriptions&&packets){size_t size=static_cast<size_t>(packets)*sizeof(AudioStreamPacketDescription);if(size<=kMaximumPropertyBytes){guestDescriptions=AllocateCorpusGuestBytes(size);if(guestDescriptions)Dynarmic_mem_1write(guestDescriptions,size,reinterpret_cast<char *>(descriptions));}}u32 args[]={e->client,e->token,bytes,packets,guestData,guestDescriptions};InvokeGuestAudioQueueFunction(e->packetsProc,args,6);if(guestDescriptions)guest_free(guestDescriptions);}
OSStatus DispatchCorpusAudioFileStreamOpen(const LC32AudioToolboxCall &call){if(!RequireSlots(call,5)||!SlotU32(call,1)||!SlotU32(call,2)||!SlotU32(call,4))return kAudio_ParamError;auto e=std::make_shared<CorpusAudioFileStreamEntry>();e->client=SlotU32(call,0);e->propertyProc=SlotU32(call,1);e->packetsProc=SlotU32(call,2);OSStatus status=AudioFileStreamOpen(e.get(),CorpusAudioFileStreamPropertyCallback,CorpusAudioFileStreamPacketsCallback,SlotU32(call,3),&e->stream);if(status!=noErr)return status;u32 token=InsertCorpusAudioFileStream(e);if(!token||!WriteGuestU32(SlotU32(call,4),token)){if(token)TakeCorpusAudioFileStream(token);AudioFileStreamClose(e->stream);return kAudio_ParamError;}return noErr;}
OSStatus DispatchCorpusAudioFileStreamProperty(const LC32AudioToolboxCall &call,bool info){if(!RequireSlots(call,4))return kAudio_ParamError;auto e=FindCorpusAudioFileStream(SlotU32(call,0));if(!e)return kAudio_ParamError;std::lock_guard<std::mutex> lock(e->mutex);if(info){UInt32 size=0;Boolean writable=false;OSStatus status=AudioFileStreamGetPropertyInfo(e->stream,SlotU32(call,1),&size,&writable);if(!WriteGuestU32(SlotU32(call,2),size)||(SlotU32(call,3)&&Dynarmic_mem_1write(SlotU32(call,3),1,reinterpret_cast<char *>(&writable))!=0))return kAudio_ParamError;return status;}u32 requested=0;if(!ReadGuestU32(SlotU32(call,2),requested)||requested>kMaximumPropertyBytes||(requested&&!SlotU32(call,3)))return kAudio_ParamError;std::vector<uint8_t> out(requested?requested:1);UInt32 returned=requested;OSStatus status=AudioFileStreamGetProperty(e->stream,SlotU32(call,1),&returned,requested?out.data():nullptr);if(!WriteGuestU32(SlotU32(call,2),returned))return kAudio_ParamError;if(status==noErr&&returned&&(returned>requested||Dynarmic_mem_1write(SlotU32(call,3),returned,reinterpret_cast<char *>(out.data()))!=0))return kAudio_ParamError;return status;}
OSStatus DispatchCorpusAudioFileStreamParse(const LC32AudioToolboxCall &call){if(!RequireSlots(call,4))return kAudio_ParamError;auto e=FindCorpusAudioFileStream(SlotU32(call,0));u32 count=SlotU32(call,1);if(!e||count>kMaximumAudioBytes||(count&&!SlotU32(call,2)))return kAudio_ParamError;std::vector<uint8_t> bytes(count);if(count&&Dynarmic_mem_1read(SlotU32(call,2),count,reinterpret_cast<char *>(bytes.data()))!=0)return kAudio_ParamError;std::lock_guard<std::mutex> lock(e->mutex);e->currentGuestData=SlotU32(call,2);e->currentHostData=bytes.data();e->currentBytes=count;OSStatus status=AudioFileStreamParseBytes(e->stream,count,count?bytes.data():nullptr,SlotU32(call,3));e->currentGuestData=0;e->currentHostData=nullptr;e->currentBytes=0;return status;}
OSStatus DispatchCorpusAudioFileStreamSeek(const LC32AudioToolboxCall &call){if(!RequireSlots(call,4))return kAudio_ParamError;auto e=FindCorpusAudioFileStream(SlotU32(call,0));u32 flags=0;if(!e||!ReadGuestU32(SlotU32(call,3),flags))return kAudio_ParamError;SInt64 offset=0;std::lock_guard<std::mutex> lock(e->mutex);OSStatus status=AudioFileStreamSeek(e->stream,static_cast<SInt64>(call.slots[1]),&offset,reinterpret_cast<AudioFileStreamSeekFlags *>(&flags));if(Dynarmic_mem_1write(SlotU32(call,2),sizeof(offset),reinterpret_cast<char *>(&offset))!=0||!WriteGuestU32(SlotU32(call,3),flags))return kAudio_ParamError;return status;}

'''
 a='} // namespace\n\nextern "C" u32 LC32_AudioToolbox_Dispatch'
 if a not in x:raise SystemExit('stream helper anchor missing')
 x=x.replace(a,helper+a,1)
if 'case LC32AudioToolboxOpAudioFileStreamOpen:' not in x:
 cases=r'''
        case LC32AudioToolboxOpAudioFileStreamOpen:return static_cast<u32>(DispatchCorpusAudioFileStreamOpen(call));
        case LC32AudioToolboxOpAudioFileStreamClose:{if(!RequireSlots(call,1))return static_cast<u32>(kAudio_ParamError);auto e=TakeCorpusAudioFileStream(SlotU32(call,0));if(!e)return static_cast<u32>(kAudio_ParamError);std::lock_guard<std::mutex> lock(e->mutex);return static_cast<u32>(AudioFileStreamClose(e->stream));}
        case LC32AudioToolboxOpAudioFileStreamGetProperty:return static_cast<u32>(DispatchCorpusAudioFileStreamProperty(call,false));
        case LC32AudioToolboxOpAudioFileStreamGetPropertyInfo:return static_cast<u32>(DispatchCorpusAudioFileStreamProperty(call,true));
        case LC32AudioToolboxOpAudioFileStreamParseBytes:return static_cast<u32>(DispatchCorpusAudioFileStreamParse(call));
        case LC32AudioToolboxOpAudioFileStreamSeek:return static_cast<u32>(DispatchCorpusAudioFileStreamSeek(call));
'''
 a='        case LC32AudioToolboxOpRemoteIOOutputStart:'
 if a not in x:raise SystemExit('stream switch anchor missing')
 x=x.replace(a,cases+a,1)
X.write_text(x)
print('AudioToolbox: added tokenized AudioFileStream lifecycle and guest callbacks')


# AudioConverter lifecycle and complex input callback bridge.
h=H.read_text();a='    LC32AudioToolboxOpAudioFileStreamSeek = 56,\n'
if 'LC32AudioToolboxOpAudioConverterNew = 57' not in h:
 if a not in h:raise SystemExit('converter opcode anchor missing')
 h=h.replace(a,a+r'''    LC32AudioToolboxOpAudioConverterNew = 57,
    LC32AudioToolboxOpAudioConverterDispose = 58,
    LC32AudioToolboxOpAudioConverterFillComplexBuffer = 59,
''');H.write_text(h)
g=G.read_text()
if 'OSStatus AudioConverterNew(' not in g:
 g+=r'''
OSStatus AudioConverterNew(const AudioStreamBasicDescription *source,const AudioStreamBasicDescription *destination,AudioConverterRef *out){if(!source||!destination||!out)return kAudio_ParamError;return (OSStatus)LC32_AUDIO_CALL(LC32AudioToolboxOpAudioConverterNew,LC32_AUDIO_U32((uintptr_t)source),LC32_AUDIO_U32((uintptr_t)destination),LC32_AUDIO_U32((uintptr_t)out));}
OSStatus AudioConverterDispose(AudioConverterRef converter){return converter?(OSStatus)LC32_AUDIO_CALL(LC32AudioToolboxOpAudioConverterDispose,LC32_AUDIO_U32((uintptr_t)converter)):kAudio_ParamError;}
OSStatus AudioConverterFillComplexBuffer(AudioConverterRef converter,AudioConverterComplexInputDataProc proc,void *user,UInt32 *ioPackets,AudioBufferList *output,AudioStreamPacketDescription *descriptions){if(!converter||!proc||!ioPackets||!output)return kAudio_ParamError;return (OSStatus)LC32_AUDIO_CALL(LC32AudioToolboxOpAudioConverterFillComplexBuffer,LC32_AUDIO_U32((uintptr_t)converter),LC32_AUDIO_U32((uintptr_t)proc),LC32_AUDIO_U32((uintptr_t)user),LC32_AUDIO_U32((uintptr_t)ioPackets),LC32_AUDIO_U32((uintptr_t)output),LC32_AUDIO_U32((uintptr_t)descriptions));}
''';G.write_text(g)
x=X.read_text()
if 'struct CorpusAudioConverterEntry' not in x:
 helper=r'''
struct CorpusAudioConverterEntry{AudioConverterRef converter=nullptr;u32 token=0;std::mutex mutex;};
std::mutex corpusAudioConvertersMutex;std::unordered_map<u32,std::shared_ptr<CorpusAudioConverterEntry>> corpusAudioConverters;std::atomic<u32> nextCorpusAudioConverterToken{1};
std::shared_ptr<CorpusAudioConverterEntry> FindCorpusAudioConverter(u32 token){std::lock_guard<std::mutex> l(corpusAudioConvertersMutex);auto i=corpusAudioConverters.find(token);return i==corpusAudioConverters.end()?nullptr:i->second;}
u32 InsertCorpusAudioConverter(const std::shared_ptr<CorpusAudioConverterEntry>& e){std::lock_guard<std::mutex> l(corpusAudioConvertersMutex);for(size_t n=0;n<UINT32_MAX;n++){u32 token=nextCorpusAudioConverterToken.fetch_add(1,std::memory_order_relaxed);if(token&&corpusAudioConverters.emplace(token,e).second){e->token=token;return token;}}return 0;}
std::shared_ptr<CorpusAudioConverterEntry> TakeCorpusAudioConverter(u32 token){std::lock_guard<std::mutex> l(corpusAudioConvertersMutex);auto i=corpusAudioConverters.find(token);if(i==corpusAudioConverters.end())return {};auto e=i->second;corpusAudioConverters.erase(i);return e;}
struct CorpusAudioConverterCallbackContext{CorpusAudioConverterEntry *entry=nullptr;u32 guestProc=0,guestUser=0;std::vector<std::vector<uint8_t>> inputBuffers;std::vector<AudioStreamPacketDescription> packetDescriptions;};
OSStatus CorpusAudioConverterInputCallback(AudioConverterRef,UInt32 *ioPackets,AudioBufferList *ioData,AudioStreamPacketDescription **outDescriptions,void *raw){auto *c=static_cast<CorpusAudioConverterCallbackContext *>(raw);if(!c||!c->entry||!c->guestProc||!ioPackets||!ioData||!Dynarmic_guest_thread_is_registered())return kAudio_ParamError;u32 capacity=ioData->mNumberBuffers;if(!capacity||capacity>kMaximumAudioBuffers)capacity=1;size_t listBytes=sizeof(u32)+static_cast<size_t>(capacity)*sizeof(GuestAudioBuffer);u32 scratch=AllocateCorpusGuestBytes(sizeof(u32)+listBytes+sizeof(u32));if(!scratch)return kAudio_MemFullError;u32 packetAddress=scratch,listAddress=scratch+sizeof(u32),descriptionPointerAddress=listAddress+static_cast<u32>(listBytes);WriteGuestU32(packetAddress,*ioPackets);WriteGuestU32(listAddress,capacity);std::vector<GuestAudioBuffer> empty(capacity);Dynarmic_mem_1write(listAddress+sizeof(u32),empty.size()*sizeof(GuestAudioBuffer),reinterpret_cast<char *>(empty.data()));WriteGuestU32(descriptionPointerAddress,0);u32 args[]={c->entry->token,packetAddress,listAddress,descriptionPointerAddress,c->guestUser};OSStatus status=static_cast<OSStatus>(LC32InvokeGuestC(c->guestProc,false,5,args));u32 packets=0,count=0,guestDescriptions=0;if(status==noErr&&ReadGuestU32(packetAddress,packets)&&ReadGuestU32(listAddress,count)&&count&&count<=capacity&&ReadGuestU32(descriptionPointerAddress,guestDescriptions)){std::vector<GuestAudioBuffer> guest(count);if(Dynarmic_mem_1read(listAddress+sizeof(u32),guest.size()*sizeof(GuestAudioBuffer),reinterpret_cast<char *>(guest.data()))!=0)status=kAudio_ParamError;else{c->inputBuffers.clear();c->inputBuffers.resize(count);size_t total=0;ioData->mNumberBuffers=count;for(u32 i=0;i<count&&status==noErr;i++){if(guest[i].byteSize>kMaximumAudioBytes-total||(guest[i].byteSize&&(!guest[i].data||static_cast<uint64_t>(guest[i].data)+guest[i].byteSize>static_cast<uint64_t>(UINT32_MAX)+1))){status=kAudio_ParamError;break;}total+=guest[i].byteSize;c->inputBuffers[i].resize(guest[i].byteSize);if(guest[i].byteSize&&Dynarmic_mem_1read(guest[i].data,guest[i].byteSize,reinterpret_cast<char *>(c->inputBuffers[i].data()))!=0){status=kAudio_ParamError;break;}ioData->mBuffers[i].mNumberChannels=guest[i].channels;ioData->mBuffers[i].mDataByteSize=guest[i].byteSize;ioData->mBuffers[i].mData=guest[i].byteSize?c->inputBuffers[i].data():nullptr;}if(status==noErr&&outDescriptions){if(guestDescriptions&&packets){size_t bytes=static_cast<size_t>(packets)*sizeof(AudioStreamPacketDescription);if(bytes>kMaximumPropertyBytes){status=kAudio_ParamError;}else{c->packetDescriptions.resize(packets);if(Dynarmic_mem_1read(guestDescriptions,bytes,reinterpret_cast<char *>(c->packetDescriptions.data()))!=0)status=kAudio_ParamError;else *outDescriptions=c->packetDescriptions.data();}}else *outDescriptions=nullptr;}if(status==noErr)*ioPackets=packets;}}else if(status==noErr)status=kAudio_ParamError;guest_free(scratch);return status;}
OSStatus DispatchCorpusAudioConverterNew(const LC32AudioToolboxCall &call){if(!RequireSlots(call,3)||!SlotU32(call,0)||!SlotU32(call,1)||!SlotU32(call,2))return kAudio_ParamError;AudioStreamBasicDescription source={},destination={};if(Dynarmic_mem_1read(SlotU32(call,0),sizeof(source),reinterpret_cast<char *>(&source))!=0||Dynarmic_mem_1read(SlotU32(call,1),sizeof(destination),reinterpret_cast<char *>(&destination))!=0)return kAudio_ParamError;auto e=std::make_shared<CorpusAudioConverterEntry>();OSStatus status=AudioConverterNew(&source,&destination,&e->converter);if(status!=noErr)return status;u32 token=InsertCorpusAudioConverter(e);if(!token||!WriteGuestU32(SlotU32(call,2),token)){if(token)TakeCorpusAudioConverter(token);AudioConverterDispose(e->converter);return kAudio_ParamError;}return noErr;}
OSStatus DispatchCorpusAudioConverterFill(const LC32AudioToolboxCall &call){if(!RequireSlots(call,6)||!SlotU32(call,1)||!SlotU32(call,3)||!SlotU32(call,4))return kAudio_ParamError;auto e=FindCorpusAudioConverter(SlotU32(call,0));if(!e)return kAudio_ParamError;u32 requested=0,count=0;if(!ReadGuestU32(SlotU32(call,3),requested)||!ReadGuestU32(SlotU32(call,4),count)||!count||count>kMaximumAudioBuffers)return kAudio_ParamError;size_t guestBytes=static_cast<size_t>(count)*sizeof(GuestAudioBuffer);std::vector<GuestAudioBuffer> guest(count);if(Dynarmic_mem_1read(SlotU32(call,4)+sizeof(u32),guestBytes,reinterpret_cast<char *>(guest.data()))!=0)return kAudio_ParamError;size_t listBytes=offsetof(AudioBufferList,mBuffers)+static_cast<size_t>(count)*sizeof(AudioBuffer);auto listStorage=std::make_unique<uint8_t[]>(listBytes);memset(listStorage.get(),0,listBytes);AudioBufferList *list=reinterpret_cast<AudioBufferList *>(listStorage.get());list->mNumberBuffers=count;std::vector<std::vector<uint8_t>> output(count);size_t total=0;for(u32 i=0;i<count;i++){if(guest[i].byteSize>kMaximumAudioBytes-total||(guest[i].byteSize&&(!guest[i].data||static_cast<uint64_t>(guest[i].data)+guest[i].byteSize>static_cast<uint64_t>(UINT32_MAX)+1)))return kAudio_ParamError;total+=guest[i].byteSize;output[i].resize(guest[i].byteSize);list->mBuffers[i].mNumberChannels=guest[i].channels;list->mBuffers[i].mDataByteSize=guest[i].byteSize;list->mBuffers[i].mData=guest[i].byteSize?output[i].data():nullptr;}std::vector<AudioStreamPacketDescription> descriptions(SlotU32(call,5)?requested:0);CorpusAudioConverterCallbackContext context{e.get(),SlotU32(call,1),SlotU32(call,2)};UInt32 returned=requested;OSStatus status;{std::lock_guard<std::mutex> lock(e->mutex);if(!e->converter)return kAudio_ParamError;status=AudioConverterFillComplexBuffer(e->converter,CorpusAudioConverterInputCallback,&context,&returned,list,descriptions.empty()?nullptr:descriptions.data());}if(!WriteGuestU32(SlotU32(call,3),returned))return kAudio_ParamError;for(u32 i=0;i<count;i++){u32 bytes=list->mBuffers[i].mDataByteSize;if(bytes>guest[i].byteSize)return kAudio_ParamError;u32 entry=SlotU32(call,4)+sizeof(u32)+i*sizeof(GuestAudioBuffer);if(!WriteGuestU32(entry+offsetof(GuestAudioBuffer,byteSize),bytes))return kAudio_ParamError;if(status==noErr&&bytes&&Dynarmic_mem_1write(guest[i].data,bytes,reinterpret_cast<char *>(output[i].data()))!=0)return kAudio_ParamError;}if(status==noErr&&SlotU32(call,5)&&returned){size_t bytes=static_cast<size_t>(returned)*sizeof(AudioStreamPacketDescription);if(returned>requested||Dynarmic_mem_1write(SlotU32(call,5),bytes,reinterpret_cast<char *>(descriptions.data()))!=0)return kAudio_ParamError;}return status;}

'''
 a='} // namespace\n\nextern "C" u32 LC32_AudioToolbox_Dispatch'
 if a not in x:raise SystemExit('converter helper anchor missing')
 x=x.replace(a,helper+a,1)
if 'case LC32AudioToolboxOpAudioConverterNew:' not in x:
 cases=r'''
        case LC32AudioToolboxOpAudioConverterNew:return static_cast<u32>(DispatchCorpusAudioConverterNew(call));
        case LC32AudioToolboxOpAudioConverterDispose:{if(!RequireSlots(call,1))return static_cast<u32>(kAudio_ParamError);auto e=TakeCorpusAudioConverter(SlotU32(call,0));if(!e)return static_cast<u32>(kAudio_ParamError);std::lock_guard<std::mutex> lock(e->mutex);OSStatus status=AudioConverterDispose(e->converter);e->converter=nullptr;return static_cast<u32>(status);}
        case LC32AudioToolboxOpAudioConverterFillComplexBuffer:return static_cast<u32>(DispatchCorpusAudioConverterFill(call));
'''
 a='        case LC32AudioToolboxOpRemoteIOOutputStart:'
 if a not in x:raise SystemExit('converter switch anchor missing')
 x=x.replace(a,cases+a,1)
X.write_text(x)
print('AudioToolbox: added tokenized AudioConverter and complex guest input callbacks')
