// SPDX-License-Identifier: MIT
#pragma once
#include <Arduino.h>
#include <HTTPClient.h>
#include <WiFiClient.h>
#include <ArduinoJson.h>
#include <esp_heap_caps.h>

class ReplyBuffer : public Stream {
public:
  uint8_t* data; size_t used=0, capacity; bool overflow=false;
  explicit ReplyBuffer(size_t cap):capacity(cap) { data=static_cast<uint8_t*>(heap_caps_malloc(cap+1,MALLOC_CAP_SPIRAM|MALLOC_CAP_8BIT)); }
  ~ReplyBuffer() { free(data); }
  size_t write(uint8_t c) override { return write(&c,1); }
  size_t write(const uint8_t* p,size_t n) override {
    if(!data || n>capacity-used) { overflow=true; return 0; }
    memcpy(data+used,p,n); used+=n; data[used]=0; return n;
  }
  int available() override { return 0; } int peek() override { return -1; } int read() override { return -1; }
};
class BridgeClient {
  String base;
public:
  explicit BridgeClient(const String& url):base(url) {}
  bool request(const char* endpoint,const char* type,const uint8_t* body,size_t length,ReplyBuffer& reply) {
    if(!reply.data) return false;
    WiFiClient transport; HTTPClient http;
    http.setConnectTimeout(5000); http.setTimeout(60000); http.setReuse(false);
    if(!http.begin(transport,base+endpoint)) return false;
    http.addHeader("Content-Type",type);
    int status=http.POST(const_cast<uint8_t*>(body),length);
    bool ok=false;
    if(status==200 && (http.getSize()<0 || size_t(http.getSize())<=reply.capacity)) {
      int received=http.writeToStream(&reply);
      ok=received>=0 && !reply.overflow && reply.used>0;
    }
    http.end(); return ok;
  }
  bool json(const char* endpoint,JsonDocument& input,JsonDocument& output) {
    String payload; serializeJson(input,payload); ReplyBuffer reply(16000);
    return request(endpoint,"application/json",reinterpret_cast<const uint8_t*>(payload.c_str()),payload.length(),reply)
      && !deserializeJson(output,reply.data,reply.used);
  }
  bool transcribe(const int16_t* pcm,size_t samples,JsonDocument& output) {
    const char* boundary="FrankyAudioBoundary7d2";
    String prefix=String("--")+boundary+"\r\nContent-Disposition: form-data; name=\"file\"; filename=\"recording.wav\"\r\nContent-Type: audio/wav\r\n\r\n";
    String suffix=String("\r\n--")+boundary+"--\r\n";
    size_t wavLength=44+samples*2, total=prefix.length()+wavLength+suffix.length();
    ReplyBuffer body(total); if(!body.data) return false;
    body.write(reinterpret_cast<const uint8_t*>(prefix.c_str()),prefix.length());
    uint8_t header[44]={};
    auto put32=[&](int p,uint32_t n) { for(int i=0;i<4;i++) header[p+i]=(n>>(i*8))&255; };
    auto put16=[&](int p,uint16_t n) {header[p]=n&255;header[p+1]=n>>8;};
    memcpy(header,"RIFF",4); put32(4,wavLength-8); memcpy(header+8,"WAVEfmt ",8);
    put32(16,16); put16(20,1); put16(22,1); put32(24,16000); put32(28,32000); put16(32,2); put16(34,16);
    memcpy(header+36,"data",4); put32(40,samples*2);
    body.write(header,44); body.write(reinterpret_cast<const uint8_t*>(pcm),samples*2);
    body.write(reinterpret_cast<const uint8_t*>(suffix.c_str()),suffix.length());
    ReplyBuffer reply(8000);
    String type=String("multipart/form-data; boundary=")+boundary;
    return request("/v1/audio/transcriptions",type.c_str(),body.data,body.used,reply)
      && !deserializeJson(output,reply.data,reply.used);
  }
  bool speech(const String& text,ReplyBuffer& output) {
    JsonDocument json; json["input"]=text; String payload; serializeJson(json,payload);
    return request("/v1/audio/speech","application/json",reinterpret_cast<const uint8_t*>(payload.c_str()),payload.length(),output)
      && output.used%2==0;
  }
};
