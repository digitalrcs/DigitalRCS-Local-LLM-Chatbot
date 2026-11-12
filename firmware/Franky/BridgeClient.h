// SPDX-License-Identifier: MIT
#pragma once
#include <Arduino.h>
#include <HTTPClient.h>
#include <WiFiClient.h>
#include <ArduinoJson.h>
#include <esp_heap_caps.h>
#include "CancellableClient.h"
#include "FrameReader.h"

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
enum class ConverseResult { Done, Unsupported, Failed };

class BridgeClient {
  String base;
  const std::atomic<bool>& cancel;
  static constexpr const char* boundary="FrankyAudioBoundary7d2";
  static String formHead(const char* name,const char* file=nullptr) {
    String head=String("--")+boundary+"\r\nContent-Disposition: form-data; name=\""+name+"\"";
    if(file) head+=String("; filename=\"")+file+"\"\r\nContent-Type: audio/wav";
    return head+"\r\n\r\n";
  }
  // Multipart body: optional encoded text fields, then a mono 16 kHz WAV file.
  static size_t uploadSize(const String& fields,size_t samples) {
    return fields.length()+formHead("file","recording.wav").length()+44+samples*2+String(boundary).length()+8;
  }
  static void writeUpload(ReplyBuffer& body,const String& fields,const int16_t* pcm,size_t samples) {
    String head=formHead("file","recording.wav");
    String suffix=String("\r\n--")+boundary+"--\r\n";
    body.write(reinterpret_cast<const uint8_t*>(fields.c_str()),fields.length());
    body.write(reinterpret_cast<const uint8_t*>(head.c_str()),head.length());
    uint8_t header[44]={};
    size_t wavLength=44+samples*2;
    auto put32=[&](int p,uint32_t n) { for(int i=0;i<4;i++) header[p+i]=(n>>(i*8))&255; };
    auto put16=[&](int p,uint16_t n) {header[p]=n&255;header[p+1]=n>>8;};
    memcpy(header,"RIFF",4); put32(4,wavLength-8); memcpy(header+8,"WAVEfmt ",8);
    put32(16,16); put16(20,1); put16(22,1); put32(24,16000); put32(28,32000); put16(32,2); put16(34,16);
    memcpy(header+36,"data",4); put32(40,samples*2);
    body.write(header,44); body.write(reinterpret_cast<const uint8_t*>(pcm),samples*2);
    body.write(reinterpret_cast<const uint8_t*>(suffix.c_str()),suffix.length());
  }
public:
  BridgeClient(const String& url,const std::atomic<bool>& flag):base(url),cancel(flag) {}
  bool request(const char* endpoint,const char* type,const uint8_t* body,size_t length,ReplyBuffer& reply,uint16_t timeout=60000) {
    if(cancel.load() || !reply.data) return false;
    CancellableClient transport(cancel); HTTPClient http;
    http.setConnectTimeout(3000); http.setTimeout(timeout); http.setReuse(false);
    if(!http.begin(transport,base+endpoint)) return false;
    http.addHeader("Content-Type",type);
    int status=http.POST(const_cast<uint8_t*>(body),length);
    bool ok=false;
    if(status==200 && (http.getSize()<0 || size_t(http.getSize())<=reply.capacity)) {
      int received=http.writeToStream(&reply);
      ok=received>=0 && !reply.overflow && reply.used>0;
    }
    http.end(); return ok && !cancel.load();
  }
  bool json(const char* endpoint,JsonDocument& input,JsonDocument& output) {
    String payload; serializeJson(input,payload); ReplyBuffer reply(16000);
    return request(endpoint,"application/json",reinterpret_cast<const uint8_t*>(payload.c_str()),payload.length(),reply)
      && !deserializeJson(output,reply.data,reply.used);
  }
  bool transcribe(const int16_t* pcm,size_t samples,JsonDocument& output,bool wake=false) {
    ReplyBuffer body(uploadSize("",samples)); if(!body.data) return false;
    writeUpload(body,"",pcm,samples);
    ReplyBuffer reply(8000);
    String type=String("multipart/form-data; boundary=")+boundary;
    return request(wake?"/v1/audio/wake":"/v1/audio/transcriptions",type.c_str(),body.data,body.used,reply,wake?8000:60000)
      && !body.overflow && !deserializeJson(output,reply.data,reply.used);
  }
  // One request per question: uploads the recording plus the conversation so
  // far (JSON message list), then passes each streamed frame to `sink` while
  // the bridge is still writing the reply. Unsupported means an older bridge
  // without /v1/converse; the caller then uses the step-by-step requests.
  ConverseResult converse(const int16_t* pcm,size_t samples,const String& messages,Franky::FrameSink& sink) {
    if(cancel.load()) return ConverseResult::Failed;
    String fields=formHead("messages")+messages+"\r\n";
    ReplyBuffer body(uploadSize(fields,samples)), text(Franky::maxTextFrame);
    if(!body.data || !text.data) return ConverseResult::Failed;
    writeUpload(body,fields,pcm,samples);
    if(body.overflow) return ConverseResult::Failed;
    CancellableClient transport(cancel); HTTPClient http;
    http.setConnectTimeout(3000); http.setTimeout(60000); http.setReuse(false);
    http.useHTTP10(true); // Plain byte stream without chunked encoding.
    if(!http.begin(transport,base+"/v1/converse")) return ConverseResult::Failed;
    http.addHeader("Content-Type",String("multipart/form-data; boundary=")+boundary);
    int status=http.POST(body.data,body.used);
    ConverseResult result=status==404?ConverseResult::Unsupported:ConverseResult::Failed;
    if(status==200 && Franky::readFrames(transport,sink,text.data,cancel,[]{return uint32_t(millis());}))
      result=ConverseResult::Done;
    http.end();
    return cancel.load()?ConverseResult::Failed:result;
  }
  bool speech(const String& text,ReplyBuffer& output) {
    JsonDocument json; json["input"]=text; String payload; serializeJson(json,payload);
    return request("/v1/audio/speech","application/json",reinterpret_cast<const uint8_t*>(payload.c_str()),payload.length(),output)
      && output.used%2==0;
  }
  bool cue(const char* kind,ReplyBuffer& output) {
    JsonDocument json;json["kind"]=kind;String payload;serializeJson(json,payload);
    return request("/v1/audio/cue","application/json",reinterpret_cast<const uint8_t*>(payload.c_str()),payload.length(),output)
      && output.used%2==0;
  }
};
