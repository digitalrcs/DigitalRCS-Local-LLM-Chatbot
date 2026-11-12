// SPDX-License-Identifier: MIT
#pragma once
#include <stddef.h>
#include <stdint.h>
#include <atomic>

// Reads the bridge's /v1/converse frame stream; see bridge/conversation.py.
// Each frame is 1 byte type, 4 bytes little-endian length, then the payload:
//   J metadata JSON, C cue PCM, T sentence text, P speech PCM, E end JSON,
//   H zero-length heartbeat while the bridge is preparing more speech.
// Templates keep this free of Arduino types so it can be tested on a PC.
namespace Franky {

// Receives frames. Audio arrives in even-sized pieces of at most 1 KB.
struct FrameSink {
  virtual ~FrameSink()=default;
  virtual bool onText(char type,const char* text,size_t length)=0;  // J, T, E
  virtual bool onAudio(char type,const uint8_t* pcm,size_t bytes)=0; // C, P
  virtual bool onWait()=0;  // Feed silence or sleep; false aborts on playback failure.
};

constexpr size_t maxTextFrame=8192;
constexpr uint32_t frameIdleTimeoutMs=60000;

// Reads exactly `count` bytes. Calls sink.onWait() while nothing has arrived.
// Fails on cancel, a sink failure, a closed connection, or 60 s without any data.
template<class Client,class Clock>
bool readExact(Client& in,uint8_t* out,size_t count,FrameSink& sink,const std::atomic<bool>& cancel,Clock now) {
  size_t got=0; uint32_t last=now();
  while(got<count) {
    if(cancel.load()) return false;
    int ready=in.available();
    if(ready>0) {
      size_t want=count-got<size_t(ready)?count-got:size_t(ready);
      int n=in.read(out+got,want);
      if(n<=0) return false;
      got+=size_t(n); last=now(); continue;
    }
    if(!in.connected() || uint32_t(now()-last)>frameIdleTimeoutMs) return false;
    if(!sink.onWait()) return false;
  }
  return true;
}

// Reads frames until E. `text` must hold maxTextFrame+1 bytes. Returns true
// only when the E frame arrived and every handler accepted its frame.
template<class Client,class Clock>
bool readFrames(Client& in,FrameSink& sink,uint8_t* text,const std::atomic<bool>& cancel,Clock now) {
  uint8_t header[5], chunk[1024];
  while(readExact(in,header,sizeof(header),sink,cancel,now)) {
    char type=char(header[0]);
    uint32_t length=uint32_t(header[1])|uint32_t(header[2])<<8|uint32_t(header[3])<<16|uint32_t(header[4])<<24;
    if(type=='H') {
      if(length!=0) return false;
    } else if(type=='C' || type=='P') {
      if(length%2) return false;
      while(length) {
        size_t n=length<sizeof(chunk)?length:sizeof(chunk);
        if(!readExact(in,chunk,n,sink,cancel,now) || !sink.onAudio(type,chunk,n)) return false;
        length-=n;
      }
    } else if(type=='J' || type=='T' || type=='E') {
      if(length>maxTextFrame || !readExact(in,text,length,sink,cancel,now)) return false;
      text[length]=0;
      if(!sink.onText(type,reinterpret_cast<const char*>(text),length)) return false;
      if(type=='E') return true;
    } else return false;
  }
  return false;
}
}
