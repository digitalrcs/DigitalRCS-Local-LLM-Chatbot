"""Compile the firmware's frame reader against a fake socket and clock.

Checks frame parsing, 1 KB even-sized audio pieces, heartbeats, sink failures,
cancellation, truncated streams and the idle timeout. Run with Python and a
C++17 compiler.
"""
from pathlib import Path
import subprocess
import tempfile

root = Path(__file__).resolve().parents[1]
sketch = (root / 'firmware/Franky/Franky.ino').read_text()
wait_start = sketch.index('  bool onWait() override {', sketch.index('struct StreamPlayer'))
player_wait = sketch[wait_start:sketch.index('\n  void close(', wait_start)]
harness = r'''
#include <cassert>
#include <cstring>
#include <string>
#include <vector>
#include "FrameReader.h"

uint32_t ticks=0;
uint32_t clockNow(){return ticks;}
std::atomic<bool> cancel{false};

// Delivers the stream in small pieces with gaps, like a real socket.
struct FakeClient {
  std::vector<uint8_t> data; size_t at=0; int gapEvery=3, calls=0; bool open=true;
  int available(){ if(at>=data.size()) return 0; if(++calls%gapEvery==0) return 0; size_t left=data.size()-at; return int(left<700?left:700); }
  int read(uint8_t* out,size_t n){ memcpy(out,&data[at],n); at+=n; return int(n); }
  bool connected(){ return open && at<data.size(); }
};
void put(std::vector<uint8_t>& out,char type,const std::string& payload){
  uint32_t n=payload.size(); out.push_back(uint8_t(type));
  for(int i=0;i<4;i++) out.push_back(uint8_t(n>>(8*i)));
  out.insert(out.end(),payload.begin(),payload.end());
}
struct Sink : Franky::FrameSink {
  std::string types,text; size_t audioBytes=0,pieces=0,waits=0,largest=0; bool oddPiece=false;
  bool onText(char t,const char* s,size_t n) override { types+=t; text+=std::string(s,n)+"|"; assert(s[n]==0); return true; }
  bool onAudio(char t,const uint8_t*,size_t n) override { if(types.empty()||types.back()!=t) types+=t; audioBytes+=n; ++pieces; largest=n>largest?n:largest; oddPiece|=n%2; return true; }
  bool onWait() override { ++waits; ticks+=10; return true; }
};
uint8_t text[Franky::maxTextFrame+1];

// Compile the real StreamPlayer waiting method against a failing audio device.
// This verifies that the application passes silence-write failures to the reader.
struct WaitAudio {
  bool ok=true; size_t writes=0;
  bool writePlayback(const uint8_t*,size_t,int,const std::atomic<bool>& flag) {
    ++writes; ticks+=10; return ok && !flag.load();
  }
} audio;
const std::atomic<bool>& cancelListening=cancel;
void delay(int ms){ticks+=uint32_t(ms);}
struct PlayerWaitSink : Sink {
  bool open=true; int volume=60;
PLAYER_WAIT_METHOD
};

// Releases complete frames on a virtual schedule; no real sleeping or network.
struct ScheduledClient : FakeClient {
  struct Release { size_t end; uint32_t when; };
  std::vector<Release> releases; size_t next=0; bool stayOpen=false;
  void add(uint32_t when,char type,const std::string& payload) {
    put(data,type,payload); releases.push_back({data.size(),when});
  }
  int available() {
    while(next<releases.size() && at==releases[next].end) ++next;
    if(next==releases.size() || ticks<releases[next].when) return 0;
    return int(releases[next].end-at);
  }
  bool connected(){ return stayOpen || at<data.size(); }
};

int main(){
  {FakeClient c; put(c.data,'J',"{\"text\":\"hi\"}"); put(c.data,'C',std::string(3000,'\1'));
   put(c.data,'T',"Hello."); put(c.data,'P',std::string(2500,'\2')); put(c.data,'E',"{\"reply\":\"Hello.\"}");
   Sink s; assert(Franky::readFrames(c,s,text,cancel,clockNow));
   assert(s.types=="JCTPE"); assert(s.audioBytes==5500); assert(s.largest<=1024 && !s.oddPiece); assert(s.waits>0);
   assert(s.text=="{\"text\":\"hi\"}|Hello.|{\"reply\":\"Hello.\"}|");}
  {FakeClient c; put(c.data,'J',"{}"); put(c.data,'P',"abc"); Sink s;           // odd PCM length
   assert(!Franky::readFrames(c,s,text,cancel,clockNow));}
  {FakeClient c; put(c.data,'X',"{}"); Sink s;                                   // unknown type
   assert(!Franky::readFrames(c,s,text,cancel,clockNow));}
  {FakeClient c; put(c.data,'J',"{}"); put(c.data,'P',std::string(4000,'\0')); c.data.resize(c.data.size()-100); Sink s; // cut off
   assert(!Franky::readFrames(c,s,text,cancel,clockNow));}
  {FakeClient c; put(c.data,'T',std::string(Franky::maxTextFrame+1,'a')); Sink s;  // oversized text
   assert(!Franky::readFrames(c,s,text,cancel,clockNow));}
  {FakeClient c; put(c.data,'J',"{}"); c.data.push_back('E'); c.open=true; Sink s;  // stalls forever
   struct Stall : FakeClient { bool connected(){return true;} } st; st.data=c.data;
   ticks=0; assert(!Franky::readFrames(st,s,text,cancel,clockNow)); assert(ticks>Franky::frameIdleTimeoutMs);}
  {FakeClient c; put(c.data,'J',"{}"); put(c.data,'E',"{}"); Sink s; cancel=true;  // cancelled
   assert(!Franky::readFrames(c,s,text,cancel,clockNow)); assert(s.types.empty()); cancel=false;}
  // Slow generation plus synthesis may exceed 60 s overall. Heartbeats keep
  // the live stream open without being exposed as text/audio to the player.
  {ScheduledClient c; c.add(0,'J',"{}");
   for(uint32_t second=1;second<=70;++second) c.add(second*1000,'H',"");
   c.add(71000,'T',"Hello."); c.add(71000,'P',std::string(2,'\0')); c.add(71000,'E',"{\"reply\":\"Hello.\"}");
   Sink s; ticks=0; assert(Franky::readFrames(c,s,text,cancel,clockNow));
   assert(ticks==71000 && s.types=="JTPE" && s.audioBytes==2);}
  {FakeClient c; put(c.data,'J',"{}"); put(c.data,'H',"x"); put(c.data,'E',"{}"); Sink s;
   assert(!Franky::readFrames(c,s,text,cancel,clockNow)); assert(s.types=="J");}
  // A heartbeat is not a permanent exemption from the no-data timeout.
  {ScheduledClient c; c.add(0,'J',"{}"); c.add(1000,'H',""); c.stayOpen=true;
   Sink s; ticks=0; assert(!Franky::readFrames(c,s,text,cancel,clockNow));
   assert(ticks>61000 && ticks<61200 && s.types=="J");}
  // A failed silence write after spoken audio must abort before accepting E.
  {struct WaitBeforeEnd : FakeClient {
     size_t endAt=0; bool waited=false;
     int available(){if(at==endAt&&!waited){waited=true;return 0;}return FakeClient::available();}
   } c;
   PlayerWaitSink s; audio.ok=false; audio.writes=0;
   c.gapEvery=100000; put(c.data,'J',"{}"); put(c.data,'T',"Hello."); put(c.data,'P',std::string(2,'\0'));
   c.endAt=c.data.size(); put(c.data,'E',"{\"reply\":\"Hello.\"}");
   assert(!Franky::readFrames(c,s,text,cancel,clockNow));
   assert(audio.writes==1 && s.types=="JTP" && s.audioBytes==2 && c.at==c.endAt);
   audio.ok=true;}
  // Terminal validation belongs to the player. Rejection must propagate even
  // if speech was already delivered before the failure report.
  {struct RejectEnd : Sink {
     bool onText(char t,const char* value,size_t n) override {Sink::onText(t,value,n);return t!='E';}
   } s;
   FakeClient c; put(c.data,'J',"{}"); put(c.data,'T',"First sentence."); put(c.data,'P',std::string(2,'\0'));
   put(c.data,'E',"{\"error\":\"Voice unavailable\",\"partial_reply\":\"First sentence.\"}");
   assert(!Franky::readFrames(c,s,text,cancel,clockNow)); assert(s.audioBytes==2);}
  {ScheduledClient c; c.add(0,'J',"{}"); c.add(1000,'H',""); c.add(2000,'E',"{}");
   struct CancelWait : Sink {bool onWait() override {Sink::onWait();cancel=true;return true;}} s;
   ticks=0; assert(!Franky::readFrames(c,s,text,cancel,clockNow)); assert(s.types=="J"); cancel=false;}
}
'''.replace('PLAYER_WAIT_METHOD', player_wait)
with tempfile.TemporaryDirectory(prefix='franky-frames-') as folder:
    test = Path(folder) / 'test.cpp'
    binary = Path(folder) / 'test.exe'
    test.write_text(harness)
    subprocess.run(['g++', '-std=c++17', '-Wall', '-Wextra', '-Werror', '-I', str(root / 'firmware/Franky'),
                    str(test), '-o', str(binary)], check=True)
    subprocess.run([str(binary)], check=True)
print('PASS: frames and heartbeats parse; malformed, stalled, cancelled and sink-failed streams fail.')
