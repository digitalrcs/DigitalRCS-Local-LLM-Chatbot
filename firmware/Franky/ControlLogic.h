// SPDX-License-Identifier: MIT
#pragma once
#include <cstring>
namespace Franky {
inline int clamp(int value, int low, int high) { return value<low?low:(value>high?high:value); }
inline bool control(const char* target, const char* mode, int value, int& volume, int& brightness) {
  if (!target || !mode) return false;
  int* selected=nullptr; int minimum=0;
  if (!strcmp(target,"volume")) selected=&volume;
  else if (!strcmp(target,"brightness")) { selected=&brightness; minimum=10; }
  else return false;
  if (!strcmp(mode,"query")) return true;
  if (!strcmp(mode,"set")) {
    if (value<0 || value>100) return false;
    *selected=clamp(value,minimum,100); return true;
  }
  if (!strcmp(mode,"delta")) {
    if (value < -100 || value>100) return false;
    *selected=clamp(*selected+value,minimum,100); return true;
  }
  return false;
}
}
