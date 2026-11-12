// SPDX-License-Identifier: MIT
#pragma once
#include <Arduino.h>
#include <ESP_I2S.h>
#include <Wire.h>
#include <atomic>
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
    // ES7210 has two address-select pins. LA064 module revisions may use
    // any of its four 7-bit addresses; probe only that documented range.
    uint8_t adcAddress=0;
    for(uint8_t address=0x40;address<=0x43;address++) {
      Wire.beginTransmission(address);
      if(Wire.endTransmission()==0) { adcAddress=address;break; }
    }
    if(!adcAddress) { Serial.println("No ES7210 found at 0x40-0x43");return false; }
    Serial.printf("ES7210 found at 0x%02x\n",adcAddress);
    busInit(dacBus,ES8311_CODEC_DEFAULT_ADDR>>1); busInit(adcBus,adcAddress);
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
  size_t record(int16_t* output,size_t capacity,bool held,const std::atomic<bool>& cancel) {
    if (cancel.load() || !mode(true)) return 0;
    int16_t stereo[512]; size_t count=0;
    // Discard settling noise after powering the microphone.
    for(int i=0;i<8;i++) i2s.readBytes(reinterpret_cast<char*>(stereo),sizeof(stereo));
    while(!cancel.load() && count<capacity && (!held || digitalRead(Board::talk)==LOW)) {
      size_t bytes=i2s.readBytes(reinterpret_cast<char*>(stereo),sizeof(stereo));
      if (!bytes || bytes%4) break;
      for(size_t i=0;i<bytes/2 && count<capacity;i+=2) output[count++]=stereo[i];
      delay(1);
    }
    stop(); return count;
  }
  bool play(const uint8_t* pcm,size_t bytes,int volume,const std::atomic<bool>& cancel) {
    if (cancel.load() || !bytes || bytes%2 || !beginPlayback()) return false;
    bool ok=writePlayback(pcm,bytes,volume,cancel);
    endPlayback(ok);
    return ok;
  }
  // Streamed playback: beginPlayback once, writePlayback for each piece of
  // audio as it arrives, endPlayback at the end. The speaker stays on between
  // pieces so sentences join without clicks.
  bool beginPlayback() {
    mouthLoudness=0; mouthSamples=0; mouth.store(0);
    return mode(false);
  }
  // Plays mono signed 16-bit little-endian PCM. Returns false on cancel or an
  // I2S failure. i2s.write blocks while the DMA buffer is full, which paces
  // the caller to real time.
  bool writePlayback(const uint8_t* pcm,size_t bytes,int volume,const std::atomic<bool>& cancel) {
    int16_t stereo[512]; size_t offset=0;
    while(offset+1<bytes && !cancel.load()) {
      size_t n=min(size_t(256),(bytes-offset)/2);
      uint32_t loudness=0;
      for(size_t i=0;i<n;i++) {
        int16_t value=int16_t(uint16_t(pcm[offset+2*i]) | uint16_t(pcm[offset+2*i+1])<<8);
        loudness+=value<0?uint32_t(-int32_t(value)):uint32_t(value);
        int16_t scaled=int32_t(value)*volume/100;
        stereo[2*i]=scaled; stereo[2*i+1]=scaled;
      }
      size_t sent=i2s.write(reinterpret_cast<uint8_t*>(stereo),n*4);
      if(sent!=n*4) return false;
      updateMouth(loudness,n);
      offset+=n*2; delay(1);
    }
    return !cancel.load();
  }
  // finished=true lets the last DMA buffer drain before the amplifier turns off.
  void endPlayback(bool finished) {
    if(finished) delay(100);
    mouth.store(0);
    stop();
  }
  // Mouth opening for the face: 0 closed to 3 wide. The voice task writes it
  // while playing; the display loop on the other core only reads it.
  std::atomic<uint8_t> mouth{0};
private:
  uint32_t mouthLoudness=0, mouthSamples=0;
  // Averages about 43 ms of audio (1024 samples at 24 kHz). Loudness is
  // measured before volume scaling so the mouth moves the same at any volume.
  // The mouth opens at once and closes one step at a time, so it does not flicker.
  void updateMouth(uint32_t loudness,size_t samples) {
    mouthLoudness+=loudness; mouthSamples+=samples;
    if(mouthSamples<1024) return;
    uint32_t mean=mouthLoudness/mouthSamples;
    mouthLoudness=0; mouthSamples=0;
    uint8_t level=mean>4500?3:mean>2000?2:mean>600?1:0, now=mouth.load();
    mouth.store(level>=now?level:uint8_t(now-1));
  }
public:
  // Record an utterance with 256 ms pre-roll and 800 ms trailing silence.
  // Bounded waiting and cancellation keep pause/BOOT responsive. Energy gating
  // is deliberately simple; the bridge's local VAD validates speech afterward.
  size_t utterance(int16_t* output,size_t capacity,uint32_t waitMs,int threshold,const std::atomic<bool>& cancel,uint32_t silenceMs=800) {
    if(cancel.load() || !mode(true)) return 0;
    int16_t stereo[512],pre[4096]{};
    size_t ring=0,filled=0,count=0,quiet=0,voiced=0;
    bool started=false;uint32_t began=millis();
    const size_t quietLimit=size_t(silenceMs)*16;
    for(int i=0;i<8;i++)i2s.readBytes(reinterpret_cast<char*>(stereo),sizeof(stereo));
    while(!cancel.load() && count<capacity) {
      if(!started && millis()-began>=waitMs)break;
      size_t bytes=i2s.readBytes(reinterpret_cast<char*>(stereo),sizeof(stereo));
      if(!bytes || bytes%4)break;
      size_t n=bytes/4;uint32_t energy=0;
      for(size_t i=0;i<n;i++)energy+=abs(int(stereo[2*i]));
      bool loud=energy/n>=uint32_t(threshold);
      if(!started && loud) {
        started=true;
        for(size_t i=0;i<filled && count<capacity;i++)output[count++]=pre[(ring+4096-filled+i)%4096];
      }
      if(started) {
        for(size_t i=0;i<n && count<capacity;i++)output[count++]=stereo[2*i];
        if(loud){quiet=0;voiced+=n;}else quiet+=n;
        if(quiet>=quietLimit) {
          if(voiced>=1600)break;
          // A click or bump must not consume the entire listening window.
          started=false;count=quiet=voiced=ring=filled=0;
        }
      } else {
        for(size_t i=0;i<n;i++){pre[ring]=stereo[2*i];ring=(ring+1)%4096;if(filled<4096)filled++;}
      }
      delay(1);
    }
    stop();return cancel.load() || voiced<1600?0:count;
  }
};
