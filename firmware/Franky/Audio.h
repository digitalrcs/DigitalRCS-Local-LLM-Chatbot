// SPDX-License-Identifier: MIT
#pragma once
#include <Arduino.h>
#include <ESP_I2S.h>
#include <Wire.h>
#include "Board.h"
#include "src/codec/es8311_codec.h"
#include "src/codec/es7210_adc.h"

// Adapter only: register programming belongs to the unchanged Apache-2.0 drivers.
class Audio {
  struct Bus { audio_codec_ctrl_if_t api{}; uint8_t address; } dacBus{}, adcBus{};
  const audio_codec_if_t *dac=nullptr, *adc=nullptr;
  I2SClass i2s;
  bool running=false;
  static bool ready(const audio_codec_ctrl_if_t*) { return true; }
  static int readReg(const audio_codec_ctrl_if_t* api,int reg,int regLen,void* data,int length) {
    if (regLen!=1 || length!=1) return ESP_CODEC_DEV_INVALID_ARG;
    auto* bus=reinterpret_cast<const Bus*>(api);
    Wire.beginTransmission(bus->address); Wire.write(uint8_t(reg));
    if (Wire.endTransmission(false)!=0) return ESP_CODEC_DEV_READ_FAIL;
    if (Wire.requestFrom(bus->address,uint8_t(1))!=1) return ESP_CODEC_DEV_READ_FAIL;
    *static_cast<uint8_t*>(data)=Wire.read(); return 0;
  }
  static int writeReg(const audio_codec_ctrl_if_t* api,int reg,int regLen,void* data,int length) {
    if (regLen!=1 || length!=1) return ESP_CODEC_DEV_INVALID_ARG;
    auto* bus=reinterpret_cast<const Bus*>(api);
    Wire.beginTransmission(bus->address); Wire.write(uint8_t(reg));
    Wire.write(*static_cast<uint8_t*>(data));
    return Wire.endTransmission()==0?0:ESP_CODEC_DEV_WRITE_FAIL;
  }
  void busInit(Bus& bus,uint8_t address) {
    bus.address=address; bus.api.is_open=ready; bus.api.read_reg=readReg; bus.api.write_reg=writeReg;
  }
public:
  bool begin() {
    pinMode(Board::amplifier,OUTPUT); digitalWrite(Board::amplifier,LOW);
    if (!Wire.begin(Board::sda,Board::scl,100000)) return false;
    busInit(dacBus,ES8311_CODEC_DEFAULT_ADDR>>1); busInit(adcBus,ES7210_CODEC_DEFAULT_ADDR>>1);
    es8311_codec_cfg_t d{}; d.ctrl_if=&dacBus.api; d.codec_mode=ESP_CODEC_DEV_WORK_MODE_DAC;
    d.pa_pin=-1; d.use_mclk=true; d.no_dac_ref=true; d.mclk_div=256;
    es7210_codec_cfg_t a{}; a.ctrl_if=&adcBus.api; a.mic_selected=ES7210_SEL_MIC1|ES7210_SEL_MIC2; a.mclk_div=256;
    dac=es8311_codec_new(&d); adc=es7210_codec_new(&a);
    return dac && adc;
  }
  void stop() {
    digitalWrite(Board::amplifier,LOW);
    if (running) { if(dac) dac->enable(dac,false); if(adc) adc->enable(adc,false); i2s.end(); running=false; }
  }
  bool mode(bool recording) {
    stop();
    i2s.setPins(Board::bclk,Board::ws,recording?-1:Board::audioOut,recording?Board::audioIn:-1,Board::mclk);
    uint32_t rate=recording?16000:24000;
    if (!i2s.begin(I2S_MODE_STD,rate,I2S_DATA_BIT_WIDTH_16BIT,I2S_SLOT_MODE_STEREO)) return false;
    running=true;
    esp_codec_dev_sample_info_t fmt{}; fmt.bits_per_sample=16; fmt.channel=2; fmt.sample_rate=rate; fmt.mclk_multiple=256;
    auto* codec=recording?adc:dac;
    if (!codec || codec->set_fs(codec,&fmt) || codec->enable(codec,true)) { stop(); return false; }
    if (recording) { if(adc->set_mic_gain(adc,24.0f)) { stop(); return false; } }
    else { if(dac->set_vol(dac,-6.0f) || dac->mute(dac,false)) { stop(); return false; } digitalWrite(Board::amplifier,HIGH); }
    i2s.setTimeout(200); return true;
  }
  size_t record(int16_t* output,size_t capacity,bool held) {
    if (!mode(true)) return 0;
    int16_t stereo[512]; size_t count=0;
    // Discard settling noise after powering the microphone.
    for(int i=0;i<8;i++) i2s.readBytes(reinterpret_cast<char*>(stereo),sizeof(stereo));
    while(count<capacity && (!held || digitalRead(Board::talk)==LOW)) {
      size_t bytes=i2s.readBytes(reinterpret_cast<char*>(stereo),sizeof(stereo));
      if (!bytes || bytes%4) break;
      for(size_t i=0;i<bytes/2 && count<capacity;i+=2) output[count++]=stereo[i];
      delay(1);
    }
    stop(); return count;
  }
  bool play(const uint8_t* pcm,size_t bytes,int volume) {
    if (!bytes || bytes%2 || !mode(false)) return false;
    int16_t stereo[512]; size_t offset=0;
    while(offset<bytes) {
      size_t n=min(size_t(256),(bytes-offset)/2);
      for(size_t i=0;i<n;i++) {
        int16_t value=int16_t(uint16_t(pcm[offset+2*i]) | uint16_t(pcm[offset+2*i+1])<<8);
        int16_t scaled=int32_t(value)*volume/100;
        stereo[2*i]=scaled; stereo[2*i+1]=scaled;
      }
      size_t sent=i2s.write(reinterpret_cast<uint8_t*>(stereo),n*4);
      if(sent!=n*4) { stop(); return false; }
      offset+=n*2; delay(1);
    }
    delay(100); stop(); return true;
  }
};
