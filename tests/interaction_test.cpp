// SPDX-License-Identifier: MIT
#include <cassert>
#include <initializer_list>
#include "../firmware/Franky/Interaction.h"
using Franky::Interaction;
using Franky::Pending;

int main() {
  Franky::TalkButton button;
  assert(!button.press(true,100));
  assert(!button.press(false,105));
  assert(!button.press(true,110));
  assert(!button.press(true,139));
  assert(button.press(true,140)); // one stable press after contact bounce
  assert(!button.press(false,145));
  assert(!button.press(true,150));
  assert(!button.press(true,180)); // brief bounce cannot Stop its own recording
  assert(!button.press(false,200));
  assert(!button.press(false,230));
  assert(!button.press(true,300));
  assert(button.press(true,330)); // a new intentional press requests Stop
  Franky::TalkButton rollover;
  assert(!rollover.press(true,UINT32_MAX-10));
  assert(rollover.press(true,20));
  Interaction s;
  assert(s.canConfigure());
  s.begin(3); // passive monitoring allows settings/manual talk
  assert(s.busy && s.canConfigure());
  s.cancel(Pending::WebTalk);
  assert(s.busy && s.stopping && !s.canConfigure());
  assert(s.takePending(false)==Pending::None); // never start overlapping capture
  s.finish(true,true,false); // late follow-up from cancelled work is discarded
  assert(!s.followUpReady && s.takePending(false)==Pending::WebTalk);
  assert(s.takePending(false)==Pending::None); // queued only once
  s.begin(1);
  assert(!s.canConfigure());
  s.cancel();
  s.finish(true,true,false);
  assert(!s.followUpReady && s.takePending(true)==Pending::None);

  for(bool held:{false,true}) {
    s.begin(3);s.cancel(Pending::HeldTalk);
    assert(s.takePending(held)==Pending::None);
    s.finish(false,true,false);
    assert(s.takePending(held)==(held?Pending::HeldTalk:Pending::None));
  }
  s.begin(3);s.cancel(Pending::WebTalk);s.cancel(); // Stop clears queued talk
  s.finish(false,true,false);
  assert(s.takePending(false)==Pending::None);
  s.begin(1);s.finish(true,true,true); // pause prevents follow-up
  assert(!s.followUpReady);
  s.begin(1);s.finish(true,true,false);
  assert(s.followUpReady);
  s.cancel(); // stop during gap before follow-up
  assert(!s.followUpReady);
  s.begin(3); // Stop does not prevent a later wake job
  assert(s.busy && !s.stopping && s.wakeMonitoring);
}
