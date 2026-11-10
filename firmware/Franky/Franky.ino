// SPDX-License-Identifier: MIT
// Copyright (c) 2026 DigitalRCS. New application; see ../PROVENANCE.md.
#include <Arduino.h>
#include <WiFi.h>
#include <WebServer.h>
#include <DNSServer.h>
#include <ESPmDNS.h>
#include <Preferences.h>
#include <ArduinoJson.h>
#include "Board.h"
#include "Audio.h"
#include "Face.h"
#include "BridgeClient.h"
#include "ControlLogic.h"
#include "ConnectionRules.h"
#include "SetupPage.h"

struct Job { char url[160]; int volume,brightness; bool held; uint8_t kind; };
struct Event { Mood mood; bool done,settings; int volume,brightness; char text[200]; };
QueueHandle_t jobs,events;
Audio audio;
Face face;
Preferences prefs;
WebServer web(80);
DNSServer dns;
String ssid,password,bridge,csrf,state="Starting",statusDetail,lastText;
int volume=60,brightness=80;
bool busy=false,audioReady=false,ap=false,hadConnection=false,greeted=false;
Mood mood=Mood::Setup;
uint32_t restartAt=0,offlineSince=0,upSince=0,downSince=0,lastInteraction=0;

void notify(Mood m,const String& text,bool done=false,bool settings=false,int vol=0,int bright=0) {
  Event e{}; e.mood=m; e.done=done; e.settings=settings; e.volume=vol; e.brightness=bright;
  text.toCharArray(e.text,sizeof(e.text)); xQueueSend(events,&e,portMAX_DELAY);
}

void voiceTask(void*) {
  Job job;
  String previousUser,previousReply;
  while(true) {
    if(xQueueReceive(jobs,&job,portMAX_DELAY)!=pdTRUE) continue;
    BridgeClient client(job.url);
    String answer;
    bool ok=true;
    if(job.kind==2) {
      // Local speaker test: short, quiet sine. No network request or microphone.
      ReplyBuffer tone(24000);
      if(tone.data) {
        for(int i=0;i<12000;i++) {
          int16_t sample=int16_t(2500*sinf(2*PI*440*i/24000.0f));
          tone.data[2*i]=sample&255; tone.data[2*i+1]=(sample>>8)&255;
        }
        ok=audio.play(tone.data,24000,job.volume);
      } else ok=false;
      notify(ok?Mood::Happy:Mood::Error,ok?"Speaker test complete":"Speaker unavailable",true); continue;
    }
    if(job.kind==0) answer="Hello! I'm Franky, your little frog companion. Hold the boot button to talk to me.";
    else {
      notify(Mood::Listening,"Listening...");
      size_t limit=16000*(job.held?10:6);
      ReplyBuffer recording(limit*2);
      size_t count=recording.data?audio.record(reinterpret_cast<int16_t*>(recording.data),limit,job.held):0;
      if(count<3200) { notify(Mood::Error,"Hold BOOT a little longer",true); continue; }
      notify(Mood::Thinking,"Hearing your words...");
      JsonDocument transcript;
      if(!client.transcribe(reinterpret_cast<int16_t*>(recording.data),count,transcript)) {
        notify(Mood::Error,"Speech service unavailable",true); continue;
      }
      if(!transcript["text"].is<String>()) { notify(Mood::Error,"Invalid transcription reply",true); continue; }
      String words=transcript["text"].as<String>(); words.trim();
      if(words.length()==0 || words.length()>2000) { notify(Mood::Error,"I didn't catch that",true); continue; }
      JsonVariant command=transcript["control"];
      if(command["error"].is<const char*>()) answer=command["error"].as<String>();
      else if(command.is<JsonObject>()) {
        const char* target=command["target"] | ""; const char* mode=command["mode"] | "";
        bool typed=command["value"].is<int>();
        if(!typed || !Franky::control(target,mode,command["value"].as<int>(),job.volume,job.brightness)) {
          notify(Mood::Error,"Invalid device command",true); continue;
        }
        notify(Mood::Happy,"Settings updated",false,true,job.volume,job.brightness);
        answer=String(target)+" is now "+String(!strcmp(target,"volume")?job.volume:job.brightness)+" percent.";
      } else {
        notify(Mood::Thinking,"Thinking...");
        JsonDocument request,response;
        JsonArray messages=request["messages"].to<JsonArray>();
        auto add=[&](const char* role,const String& text) { JsonObject item=messages.add<JsonObject>();item["role"]=role;item["content"]=text; };
        add("system","You are Franky, a friendly English-speaking frog companion. Answer in one to three short sentences, at most 70 words. Use plain spoken text without markdown. Be accurate and admit uncertainty. Never claim to have changed device controls; the device handles those separately.");
        if(previousUser.length()) {add("user",previousUser);add("assistant",previousReply);}
        add("user",words);
        if(!client.json("/v1/chat/completions",request,response)) { notify(Mood::Error,"Chat service unavailable",true); continue; }
        if(!response["choices"][0]["message"]["content"].is<String>()) { notify(Mood::Error,"Invalid chat reply",true); continue; }
        answer=response["choices"][0]["message"]["content"].as<String>(); answer.trim();
        if(answer.length()==0 || answer.length()>1800) { notify(Mood::Error,"Reply is empty or too long",true); continue; }
        previousUser=words; previousReply=answer;
      }
    }
    notify(Mood::Thinking,"Preparing my voice...");
    ReplyBuffer pcm(2880000);
    if(!client.speech(answer,pcm)) {notify(Mood::Error,"Voice service unavailable",true);continue;}
    notify(Mood::Speaking,answer);
    ok=audio.play(pcm.data,pcm.used,job.volume);
    notify(ok?Mood::Happy:Mood::Error,ok?"Ready for another question":"Speaker playback failed",true);
  }
}

void saveLevels(int newVolume,int newBrightness) {
  if(newVolume!=volume) {volume=newVolume;prefs.putInt("volume",volume);}
  if(newBrightness!=brightness) {brightness=newBrightness;prefs.putInt("bright",brightness);face.level(brightness);}
}
void startJob(uint8_t kind,bool held=false) {
  if(busy || !audioReady || (kind!=2 && (WiFi.status()!=WL_CONNECTED || bridge.isEmpty()))) return;
  Job job{}; bridge.toCharArray(job.url,sizeof(job.url)); job.volume=volume;job.brightness=brightness;job.kind=kind;job.held=held;
  if(xQueueSend(jobs,&job,0)==pdTRUE) {busy=true;lastInteraction=millis();}
}
void jsonReply(int code,JsonDocument& doc) {
  String out;serializeJson(doc,out);web.sendHeader("Cache-Control","no-store");web.send(code,"application/json",out);
}
void errorReply(int code,const char* text) {JsonDocument d;d["error"]=text;jsonReply(code,d);}
bool authorized() {
  if(web.header("X-Franky-Token")!=csrf) {errorReply(403,"Refresh the page and try again");return false;}
  if(busy) {errorReply(409,"Franky is busy. Try again after his reply.");return false;}
  return true;
}
bool readBody(JsonDocument& doc) {
  if(web.arg("plain").length()>1024 || deserializeJson(doc,web.arg("plain")) || !doc.is<JsonObject>()) {
    errorReply(400,"Invalid request");return false;
  }
  return true;
}
bool validBridge(const String& value) {
  return Franky::bridgeAddress(value.c_str());
}
void openSetup() {
  if(ap) return;
  WiFi.mode(WIFI_AP_STA);
  if(WiFi.softAP("DigitalRCS","11181118")) {ap=true;dns.start(53,"*",WiFi.softAPIP());}
  mood=Mood::Setup;state="Setup mode";statusDetail="DigitalRCS Wi-Fi > 192.168.4.1";
}
void routes() {
  const char* headers[]={"X-Franky-Token"};web.collectHeaders(headers,1);
  web.on("/",HTTP_GET,[]{web.sendHeader("Cache-Control","no-store");web.send_P(200,"text/html",setupPage);});
  web.on("/status",HTTP_GET,[]{
    JsonDocument d;d["version"]="0.2.0-dev";d["state"]=state;d["busy"]=busy;d["audio"]=audioReady;d["connected"]=WiFi.status()==WL_CONNECTED;
    d["ssid"]=ssid;d["bridge"]=bridge;d["volume"]=volume;d["brightness"]=brightness;d["token"]=csrf;d["text"]=lastText;
    d["ip"]=WiFi.localIP().toString();d["psram_free"]=ESP.getFreePsram();jsonReply(200,d);
  });
  web.on("/controls",HTTP_POST,[]{
    if(!authorized())return;JsonDocument d;if(!readBody(d))return;
    if(!d["volume"].is<int>()||!d["brightness"].is<int>()) {errorReply(400,"Use whole percentages");return;}
    int v=d["volume"],b=d["brightness"];
    if(v<0||v>100||b<10||b>100){errorReply(400,"Volume: 0-100; brightness: 10-100");return;}
    saveLevels(v,b);d.clear();d["ok"]=true;jsonReply(200,d);
  });
  web.on("/configure",HTTP_POST,[]{
    if(!authorized())return;JsonDocument d;if(!readBody(d))return;
    if(!d["ssid"].is<String>()||!d["password"].is<String>()||!d["bridge"].is<String>()){errorReply(400,"Missing connection settings");return;}
    String name=d["ssid"].as<String>(),secret=d["password"].as<String>(),url=d["bridge"].as<String>();url.trim();while(url.endsWith("/"))url.remove(url.length()-1);
    if(name.isEmpty()||name.length()>32||secret.length()>63||(!secret.isEmpty()&&secret.length()<8)||!validBridge(url)) {
      errorReply(400,"Check Wi-Fi name/password and use http://PC-ADDRESS:8766 for the bridge");return;
    }
    if(secret.isEmpty()&&name==ssid)secret=password;
    prefs.putString("ssid",name);prefs.putString("pass",secret);prefs.putString("bridge",url);
    d.clear();d["ok"]=true;jsonReply(200,d);restartAt=millis()+1500;
  });
  web.on("/talk",HTTP_POST,[]{
    if(!authorized())return;
    if(!audioReady||WiFi.status()!=WL_CONNECTED||bridge.isEmpty()){errorReply(503,"Connect Wi-Fi and the voice bridge first; check audio hardware");return;}
    startJob(1);JsonDocument d;d["ok"]=busy;jsonReply(busy?202:503,d);
  });
  web.on("/test-sound",HTTP_POST,[]{
    if(!authorized())return;if(!audioReady){errorReply(503,"Audio hardware unavailable");return;}startJob(2);JsonDocument d;d["ok"]=busy;jsonReply(busy?202:503,d);
  });
  web.on("/about",HTTP_GET,[]{web.send(200,"text/plain","Franky firmware 0.2.0-dev\nCopyright 2026 DigitalRCS. Original application and artwork: MIT.\nCodec drivers: Espressif, Apache-2.0. Display: Adafruit BSD. Arduino core and other dependencies retain their licenses.\nNo warranty. Source and full notices: https://github.com/digitalrcs/DigitalRCS-Local-LLM-Chatbot\n");});
  web.onNotFound([]{if(ap){web.sendHeader("Location","http://192.168.4.1");web.send(302,"text/plain","");}else errorReply(404,"Not found");});
  web.begin();
}

void setup() {
  Serial.begin(115200);delay(300);Serial.println("DigitalRCS Franky independent firmware 0.2.0-dev");
  pinMode(Board::talk,INPUT_PULLUP);pinMode(Board::pageUp,INPUT_PULLUP);pinMode(Board::pageDown,INPUT_PULLUP);
  prefs.begin("franky2",false);
  ssid=prefs.getString("ssid","");password=prefs.getString("pass","");bridge=prefs.getString("bridge","");
  volume=Franky::clamp(prefs.getInt("volume",60),0,100);brightness=Franky::clamp(prefs.getInt("bright",80),10,100);
  face.begin(brightness);face.draw(Mood::Setup,"Hello, I'm Franky","Starting my little pond...");
  csrf=String(esp_random(),HEX)+String(esp_random(),HEX)+String(esp_random(),HEX)+String(esp_random(),HEX);
  audioReady=psramFound()&&audio.begin();Serial.printf("Audio: %s. PSRAM: %u bytes\n",audioReady?"ready":"unavailable",ESP.getPsramSize());
  jobs=xQueueCreate(1,sizeof(Job));events=xQueueCreate(8,sizeof(Event));
  if(!jobs||!events||xTaskCreatePinnedToCore(voiceTask,"franky-voice",16384,nullptr,1,nullptr,0)!=pdPASS) {
    audioReady=false;state="Not enough memory";mood=Mood::Error;
  }
  WiFi.persistent(false);WiFi.setHostname("DigitalRCS");WiFi.mode(WIFI_STA);WiFi.setSleep(false);
  if(ssid.length()){WiFi.begin(ssid.c_str(),password.c_str());state="Joining Wi-Fi...";offlineSince=millis();}
  else {
    // Reuse only the ESP32 Wi-Fi driver's saved station configuration, if any.
    // This is a documented platform API, not an upstream application format.
    WiFi.begin();state="Checking saved Wi-Fi";offlineSince=millis();
  }
  routes();lastInteraction=millis();
}
void loop() {
  web.handleClient();if(ap)dns.processNextRequest();
  Event event;
  while(events && xQueueReceive(events,&event,0)==pdTRUE) {
    mood=event.mood;lastText=event.text;
    state=mood==Mood::Speaking?"Franky is speaking":String(event.text);
    if(event.settings)saveLevels(event.volume,event.brightness);
    if(event.done){busy=false;lastInteraction=millis();}
  }
  bool connected=WiFi.status()==WL_CONNECTED;
  if(connected&&!hadConnection) {
    hadConnection=true;offlineSince=0;MDNS.begin("digitalrcs");
    if(ssid.isEmpty()) {
      ssid=WiFi.SSID();password=WiFi.psk();
      prefs.putString("ssid",ssid);prefs.putString("pass",password);
    }
    if(ap){dns.stop();WiFi.softAPdisconnect(true);WiFi.mode(WIFI_STA);ap=false;}
    state=audioReady?"Hello, I'm Franky":"Audio needs attention";mood=audioReady?Mood::Idle:Mood::Error;
    statusDetail="http://"+WiFi.localIP().toString();Serial.println("Connected. Device page: "+statusDetail);
  }
  if(!connected&&hadConnection){hadConnection=false;offlineSince=millis();greeted=false;MDNS.end();}
  if(!connected&&!ap&&millis()-offlineSince>20000)openSetup();
  if(connected&&!busy&&!greeted&&audioReady&&bridge.length()){greeted=true;startJob(0);}
  static bool pressed=false;
  bool down=digitalRead(Board::talk)==LOW;
  if(down&&!pressed&&!busy&&connected)startJob(1,true);
  pressed=down;
  if(!busy&&digitalRead(Board::pageUp)==LOW){if(!upSince)upSince=millis();if(millis()-upSince>3000)openSetup();}else upSince=0;
  if(!busy&&digitalRead(Board::pageDown)==LOW){if(!downSince)downSince=millis();if(millis()-downSince>70&&downSince!=UINT32_MAX){startJob(2);downSince=UINT32_MAX;}}else downSince=0;
  if(!busy&&!ap&&mood==Mood::Happy&&millis()-lastInteraction>1800){mood=Mood::Idle;state="Hold BOOT to talk";}
  if(!busy&&!ap&&mood==Mood::Error&&millis()-lastInteraction>10000&&audioReady){mood=Mood::Idle;state="Hold BOOT to retry";}
  face.draw(mood,state,statusDetail);
  if(restartAt&&int32_t(millis()-restartAt)>=0)ESP.restart();
  delay(5);
}
