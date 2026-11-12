// SPDX-License-Identifier: MIT
#pragma once
#include <Adafruit_ST7789.h>
#include <Adafruit_GFX.h>
#include <math.h>
#include "Board.h"
#include "FrogArt.h"

enum class Mood { Idle, Listening, Thinking, Speaking, Happy, Error, Setup };
class Face {
  Adafruit_ST7789 screen{Board::lcdCS,Board::lcdDC,-1};
  GFXcanvas16 canvas{320,200};
  uint32_t lastFrame=0;
  void ellipse(int x,int y,int rx,int ry,uint16_t color) {
    for(int dy=-ry;dy<=ry;dy++) {
      int dx=int(rx*sqrtf(1.0f-float(dy*dy)/float(ry*ry)));
      canvas.drawFastHLine(x-dx,y+dy,2*dx+1,color);
    }
  }
  void shapes(const FrogArt::Shape* list,size_t count) {
    canvas.fillScreen(FrogArt::background);
    for(size_t i=0;i<count;i++) {
      const auto& s=list[i];
      if(s.kind==0) ellipse(s.x,s.y,s.a,s.b,s.color);
      else canvas.drawLine(s.x,s.y,s.a,s.b,s.color);
    }
  }
  void show() { screen.drawRGBBitmap(0,0,canvas.getBuffer(),320,200); }
  template<size_t N> void paint(const FrogArt::Shape (&list)[N]) { shapes(list,N); show(); }
  // Talking face: the speaking pose without its last two shapes (the fixed
  // open mouth), plus a mouth sized from the audio loudness (0 closed .. 3 wide).
  // Mouth position and colours match scripts/generate_frog.py.
  void paintTalking(uint8_t level) {
    constexpr size_t fixedMouthShapes=2;
    constexpr uint16_t dark=0x11e6, pink=0xecf0;
    constexpr int16_t height[4]={3,8,14,20};
    shapes(FrogArt::speaking,sizeof(FrogArt::speaking)/sizeof(FrogArt::speaking[0])-fixedMouthShapes);
    int16_t h=height[level>3?3:level];
    ellipse(160,144,32,h,dark);
    if(h>11) ellipse(160,150,18,h-11,pink);
    show();
  }
public:
  bool begin(int brightness) {
    if(!canvas.getBuffer()) return false;
    SPI.begin(Board::lcdClock,-1,Board::lcdData,Board::lcdCS);
    screen.init(240,320); screen.setRotation(1); screen.fillScreen(FrogArt::background);
    ledcAttach(Board::backlight,5000,8); level(brightness); return true;
  }
  void level(int percent) { ledcWrite(Board::backlight,percent*255/100); }
  // mouth: 0..3 from Audio::mouth; used only while speaking.
  void draw(Mood mood,const String& status,const String& detail,uint8_t mouth=0) {
    // Faster frames while talking so the mouth follows the words.
    uint32_t now=millis(); if(now-lastFrame<(mood==Mood::Speaking?60u:110u)) return; lastFrame=now;
    if(!canvas.getBuffer()) return;
    switch(mood) {
      case Mood::Listening: paint(FrogArt::listening); break;
      case Mood::Thinking: if((now/650)%2) paint(FrogArt::thinking); else paint(FrogArt::thinking2); break;
      case Mood::Speaking: paintTalking(mouth); break;
      case Mood::Happy: paint(FrogArt::happy); break;
      case Mood::Error: paint(FrogArt::error); break;
      case Mood::Setup: paint(FrogArt::setup); break;
      default: if(now%4600<180) paint(FrogArt::blink); else paint(FrogArt::idle); break;
    }
    screen.fillRect(0,200,320,40,FrogArt::background);
    screen.setTextWrap(false); screen.setTextColor(0xf7d7); screen.setTextSize(2); screen.setCursor(10,201);
    screen.print(status.substring(0,25));
    screen.setTextSize(1); screen.setTextColor(0xa653); screen.setCursor(10,225); screen.print(detail.substring(0,49));
  }
};
