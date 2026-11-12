"""Exercise the actual PCM playback loop with cancellable fake I2S."""
from pathlib import Path
import subprocess
import tempfile

root = Path(__file__).resolve().parents[1]
source = (root / 'firmware/Franky/Audio.h').read_text()
method = source[source.index('  bool play('):source.index('  // Record an utterance')]
harness = r'''
#include <atomic>
#include <cassert>
#include <cstdint>
#include <cstddef>
#include <algorithm>
using std::min;
void delay(int) {}
std::atomic<bool> cancel{false};
int writes=0, cancelAt=0;bool failWrite=false;
struct FakeI2S {
  size_t write(uint8_t*,size_t n){++writes;if(writes==cancelAt)cancel.store(true);return failWrite?0:n;}
};
struct Audio {
  FakeI2S i2s;bool stopped=false;int modes=0;
  bool mode(bool){++modes;return true;}
  void stop(){stopped=true;}
METHOD
};
int main(){
  uint8_t pcm[4096]{};
  {Audio a;assert(a.play(pcm,sizeof(pcm),60,cancel));assert(writes==8&&a.stopped);}
  writes=0;cancelAt=2;
  {Audio a;assert(!a.play(pcm,sizeof(pcm),60,cancel));assert(writes==2&&a.stopped);}
  writes=0;
  {Audio a;assert(!a.play(pcm,sizeof(pcm),60,cancel));assert(!writes&&!a.modes);}
  cancel=false;cancelAt=0;failWrite=true;
  {Audio a;assert(!a.play(pcm,sizeof(pcm),60,cancel));assert(a.stopped);}
}
'''.replace('METHOD', method)
with tempfile.TemporaryDirectory(prefix='franky-playback-') as folder:
    test = Path(folder) / 'test.cpp'
    binary = Path(folder) / 'test.exe'
    test.write_text(harness)
    subprocess.run(['g++', '-std=c++17', '-Wall', '-Wextra', '-Werror', str(test), '-o', str(binary)], check=True)
    subprocess.run([str(binary)], check=True)
print('PASS: playback completes, stops between chunks, honours pre-cancel, handles I2S failure.')
