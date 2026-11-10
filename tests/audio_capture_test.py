"""Compile the actual capture method against deterministic fake I2S/time.

Run with Python and a C++17 compiler on PATH. This checks timing and buffers,
not microphone or codec behavior.
"""
from pathlib import Path
import subprocess
import tempfile

root = Path(__file__).resolve().parents[1]
source = (root / 'firmware/Franky/Audio.h').read_text()
method = source[source.index('  size_t utterance('):source.rindex('\n};')]
harness = r'''
#include <atomic>
#include <cassert>
#include <cstdint>
#include <cstdlib>
#include <cstring>
#include <vector>
uint32_t ticks=0; int scenario=0;
std::atomic<bool> cancelled{false};
uint32_t millis(){return ticks;}
void delay(int ms){ticks+=ms;}
struct FakeI2S {
  size_t readBytes(char* bytes,size_t length){
    bool voice=(scenario==1 && ticks>=6000 && ticks<6500)
      || (scenario==2 && ((ticks>=1000&&ticks<1500)||(ticks>=2500&&ticks<3000)))
      || (scenario==3 && ticks>=1000&&ticks<1032)
      || scenario==4;
    auto* samples=reinterpret_cast<int16_t*>(bytes);
    for(size_t i=0;i<length/2;i++)samples[i]=voice?500:0;
    ticks+=16;
    if(scenario==5 && ticks>=2000)cancelled.store(true);
    return length;
  }
};
class Capture {
  FakeI2S i2s;
public:
  bool stopped=false;
  bool mode(bool){return true;}
  void stop(){stopped=true;}
METHOD
};
size_t run(int which,uint32_t silence=1500){
  scenario=which;ticks=0;cancelled.store(false);
  Capture capture;std::vector<int16_t> out(160002,12345);
  size_t n=capture.utterance(out.data()+1,160000,15000,120,cancelled,silence);
  assert(capture.stopped);assert(out.front()==12345&&out.back()==12345);
  assert(n<=160000);return n;
}
int main(){
  assert(run(0)==0);assert(ticks>=15000&&ticks<15300);
  assert(run(1)>16000);assert(ticks>7500&&ticks<8500); // six seconds to start
  assert(run(2)>48000);assert(ticks>4400); // 1.0 s pause stays in same question
  assert(run(2,800)<32000);assert(ticks<2600); // wake remains short
  assert(run(3)==0);assert(ticks>=15000); // isolated click does not close window
  assert(run(4)==160000); // continuous speech has bounded memory/duration
  assert(run(5)==0);assert(ticks<2100); // cancellation interrupts quiet waiting
}
'''.replace('METHOD', method)
with tempfile.TemporaryDirectory(prefix='franky-audio-test-') as folder:
    test = Path(folder)/'test.cpp'
    binary = Path(folder)/'audio-test.exe'
    test.write_text(harness)
    subprocess.run(['g++','-std=c++17','-Wall','-Wextra','-Werror',str(test),'-o',str(binary)],check=True)
    subprocess.run([str(binary)],check=True)
print('PASS: silence, delayed speech, phrase pauses, wake timing, clicks, capacity, cancellation.')
