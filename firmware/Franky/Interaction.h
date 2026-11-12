// SPDX-License-Identifier: MIT
#pragma once
#include <stdint.h>

namespace Franky {
enum class Pending { None, HeldTalk, WebTalk, SoundTest };

struct TalkButton {
  bool raw=false, stable=false;
  uint32_t changedAt=0;
  bool press(bool down,uint32_t now) {
    if(down!=raw){raw=down;changedAt=now;}
    if(raw==stable || uint32_t(now-changedAt)<30)return false;
    stable=raw;
    return stable;
  }
};

// Main-task state only. The worker receives cancellation through an atomic flag.
struct Interaction {
  bool busy=false, wakeMonitoring=false, stopping=false, followUpReady=false;
  Pending pending=Pending::None;

  bool canConfigure() const { return !stopping && (!busy || wakeMonitoring); }
  void begin(uint8_t kind) {
    busy=true; wakeMonitoring=kind==3; stopping=false; followUpReady=false;
  }
  void cancel(Pending next=Pending::None) {
    pending=next; followUpReady=false; stopping=busy; wakeMonitoring=false;
  }
  void finish(bool followUp, bool handsFree, bool paused) {
    followUpReady=followUp && handsFree && !paused && !stopping;
    busy=false; wakeMonitoring=false; stopping=false;
  }
  Pending takePending(bool held) {
    if(busy) return Pending::None;
    Pending next=pending; pending=Pending::None;
    return next==Pending::HeldTalk && !held ? Pending::None : next;
  }
};
}
