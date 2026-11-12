"""Compile actual transport against fake WiFiClient to check virtual cancellation."""
from pathlib import Path
import subprocess
import tempfile

root = Path(__file__).resolve().parents[1]
stub = r'''
#pragma once
#include <cstddef>
#include <cstdint>
#include <atomic>
struct IPAddress {};
extern std::atomic<bool> flag;
extern bool cancelOnConnect, cancelOnWrite;
class WiFiClient {
public:
  bool closed=false;int calls=0;unsigned long timeout=60000;
  virtual ~WiFiClient()=default;
  virtual int connect(const char*,uint16_t,int32_t){if(cancelOnConnect)flag=true;return 1;}
  virtual int connect(IPAddress,uint16_t,int32_t){if(cancelOnConnect)flag=true;return 1;}
  virtual void stop(){closed=true;}
  void setTimeout(unsigned long n){timeout=n;}
  virtual int available(){return 3;}
  virtual uint8_t connected(){return 1;}
  virtual int read(){return 42;}
  virtual int read(uint8_t*,size_t){return 3;}
  virtual size_t write(uint8_t){return 1;}
  virtual size_t write(const uint8_t*,size_t n){++calls;if(cancelOnWrite)flag=true;return n;}
};
'''
harness = r'''
#include <cassert>
#include "CancellableClient.h"
std::atomic<bool> flag{false};bool cancelOnConnect=false,cancelOnWrite=false;
int main(){
  uint8_t buffer[4096]{};
  {CancellableClient c(flag);WiFiClient& base=c;
   assert(base.available()==3&&base.connected());
   assert(base.read()==42&&base.read(buffer,3)==3);
   assert(base.write(buffer,sizeof(buffer))==sizeof(buffer)&&c.calls==4);
   flag=true;
   assert(!base.available()&&!base.connected()&&c.closed);
   assert(base.read()==-1&&base.read(buffer,3)==-1&&c.timeout==0);
   assert(base.write(buffer,3)==0);}
  flag=false;cancelOnWrite=true;
  {CancellableClient c(flag);assert(c.write(buffer,sizeof(buffer))==1024);assert(c.closed&&c.calls==1);}
  flag=false;cancelOnConnect=true;
  {CancellableClient c(flag);assert(c.connect("example.test",80,3000)==0&&c.closed);}
  flag=false;
  {CancellableClient c(flag);assert(c.connect(IPAddress{},80,3000)==0&&c.closed);}
}
'''
with tempfile.TemporaryDirectory(prefix='franky-network-') as folder:
    work = Path(folder)
    (work / 'WiFiClient.h').write_text(stub)
    (work / 'test.cpp').write_text(harness)
    binary = work / 'test.exe'
    subprocess.run(['g++', '-std=c++17', '-Wall', '-Wextra', '-Werror', '-I', str(work), '-I', str(root / 'firmware/Franky'), str(work / 'test.cpp'), '-o', str(binary)], check=True)
    subprocess.run([str(binary)], check=True)
print('PASS: transport polls, reads, chunked upload, and connection completion honour cancellation.')
