// SPDX-License-Identifier: MIT
#include <cassert>
#include <initializer_list>
#include "../firmware/Franky/ControlLogic.h"
#include "../firmware/Franky/ConnectionRules.h"
int main() {
  struct Case {const char* target; const char* mode; int n,v,b; bool ok; int outV,outB;};
  const Case cases[]={
    {"volume","set",0,50,50,true,0,50},
    {"brightness","delta",10,20,95,true,20,100},
    {"volume","delta",-100,50,70,true,0,70},
    {"brightness","delta",-5,30,12,true,30,10},
    {"brightness","set",0,60,80,true,60,10},
    {"volume","set",101,20,80,false,20,80},
    {"brightness","delta",-101,40,60,false,40,60},
    {"color","set",50,10,90,false,10,90},
    {"volume","toggle",50,10,90,false,10,90},
    {"brightness","query",-5,20,42,true,20,42},
    {"volume","set",60,60,80,true,60,80},
    {nullptr,"set",50,60,80,false,60,80},
  };
  for(const auto& c:cases){int v=c.v,b=c.b;assert(Franky::control(c.target,c.mode,c.n,v,b)==c.ok);assert(v==c.outV&&b==c.outB);}
  for(const char* url:{"http://bridge-pc:8766","http://bridge.local","http://192.0.2.10:8766"}) assert(Franky::bridgeAddress(url));
  for(const char* url:{"http://localhost:8766","http://127.0.0.1","http://pc:0","http://pc:65536","http://pc:bad","http://pc/v1","http://user:pass@pc","https://pc","http://"}) assert(!Franky::bridgeAddress(url));
}
