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
#include "Interaction.h"
#include "FrameReader.h"
#include "VoiceTypes.h"

struct Job { char url[160]; int volume,brightness,threshold; bool held; uint8_t kind; };
struct Event { Mood mood; bool done,settings,engaged,pause,followUp; int volume,brightness; char text[200]; };
QueueHandle_t jobs,events;
Audio audio;
Face face;
Preferences prefs;
WebServer web(80);
DNSServer dns;
String ssid,password,bridge,csrf,state="Starting",statusDetail,lastText;
int volume=60,brightness=80;
bool audioReady=false,ap=false,hadConnection=false,greeted=false;
bool handsFree=false,paused=false;
Franky::Interaction interaction;
int wakeThreshold=120;
std::atomic<bool> cancelListening{false};
Mood mood=Mood::Setup;
uint32_t restartAt=0,offlineSince=0,upSince=0,downSince=0,lastInteraction=0,nextListenAt=0;

void notify(Mood m,const String& text,bool done=false,bool settings=false,int vol=0,int bright=0,bool engaged=false,bool pause=false,bool followUp=false) {
  Event e{}; e.mood=m; e.done=done; e.settings=settings; e.volume=vol; e.brightness=bright;
  e.engaged=engaged;e.pause=pause;e.followUp=followUp;
  text.toCharArray(e.text,sizeof(e.text)); xQueueSend(events,&e,portMAX_DELAY);
}

// ---------------------------------------------------------------------------
// Voice worker. Runs on its own FreeRTOS task (core 0) and owns the microphone,
// speaker and bridge connections. It reports progress to the main loop only
// through notify(); the main loop cancels it only through cancelListening.
// ---------------------------------------------------------------------------

// Chimes never change, so each is fetched from the bridge once and kept in
// PSRAM. Only the voice task touches this cache, so it needs no lock.
CachedCue cueCache[]={{"listening",nullptr,0},{"followup",nullptr,0},{"thinking",nullptr,0},{"paused",nullptr,0}};

CachedCue* cachedCue(BridgeClient& client,const char* kind) {
  for(auto& cue:cueCache) {
    if(strcmp(cue.kind,kind)) continue;
    if(!cue.data) {
      ReplyBuffer reply(480000);
      if(!client.cue(kind,reply)) return nullptr;
      cue.data=static_cast<uint8_t*>(heap_caps_malloc(reply.used,MALLOC_CAP_SPIRAM|MALLOC_CAP_8BIT));
      if(!cue.data) return nullptr;
      memcpy(cue.data,reply.data,reply.used); cue.bytes=reply.used;
    }
    return &cue;
  }
  return nullptr;  // Not a chime (for example "welcome", which uses the selected voice).
}

bool playCue(BridgeClient& client,const char* kind,int level) {
  bool ok;
  if(CachedCue* cue=cachedCue(client,kind)) ok=audio.play(cue->data,cue->bytes,level,cancelListening);
  else {
    ReplyBuffer reply(480000);
    ok=client.cue(kind,reply)&&audio.play(reply.data,reply.used,level,cancelListening);
  }
  Serial.printf("Cue %s: %s\n",kind,ok?"played":"failed");
  return ok;
}


const char* systemPrompt="You are Franky, a friendly English-speaking frog companion. Answer in one to three short sentences, at most 70 words. Use plain spoken text without markdown. Be accurate and admit uncertainty. Never claim to have changed device controls; the device handles those separately.";

void addMessage(JsonArray messages,const char* role,const String& text) {
  JsonObject item=messages.add<JsonObject>(); item["role"]=role; item["content"]=text;
}
// System prompt plus the previous turn, if any.
void addContext(JsonArray messages,const History& history) {
  addMessage(messages,"system",systemPrompt);
  if(history.user.length()) {addMessage(messages,"user",history.user);addMessage(messages,"assistant",history.reply);}
}

void finishReply(const Job& job,bool ok) {
  bool followUp=ok&&(job.kind==1||job.kind==3||job.kind==4);
  notify(ok?Mood::Happy:Mood::Error,ok?"Ready for another question":"Speaker playback failed",true,false,0,0,false,false,followUp);
}

// Local speaker test: short, quiet sine. No network request or microphone.
void speakerTest(const Job& job) {
  ReplyBuffer tone(24000);
  bool ok=false;
  if(tone.data) {
    for(int i=0;i<12000;i++) {
      int16_t sample=int16_t(2500*sinf(2*PI*440*i/24000.0f));
      tone.data[2*i]=sample&255; tone.data[2*i+1]=(sample>>8)&255;
    }
    ok=audio.play(tone.data,24000,job.volume,cancelListening);
  }
  notify(ok?Mood::Happy:Mood::Error,ok?"Speaker test complete":"Speaker unavailable",true);
}

// Hands-free: listen for "Hello Franky". Returns true when a question should follow.
bool wakeStage(BridgeClient& client,const Job& job) {
  ReplyBuffer snippet(16000*4*2);
  size_t count=snippet.data?audio.utterance(reinterpret_cast<int16_t*>(snippet.data),16000*4,15000,job.threshold,cancelListening):0;
  if(cancelListening.load() || count==0){notify(Mood::Idle,"Say Hello Franky",true);return false;}
  JsonDocument detection;
  bool heard=client.transcribe(reinterpret_cast<int16_t*>(snippet.data),count,detection,true);
  if(!cancelListening.load() && heard && detection["pause"].is<bool>() && detection["pause"].as<bool>()) {
    notify(Mood::Idle,"Listening paused - BOOT resumes",false,false,0,0,false,true);
    playCue(client,"paused",job.volume);
    notify(Mood::Idle,"Listening paused - BOOT resumes",true);return false;
  }
  if(cancelListening.load() || !heard || !detection["wake"].is<bool>() || !detection["wake"].as<bool>()) {
    notify(heard?Mood::Idle:Mood::Error,heard?"Say Hello Franky":"Wake service unavailable",true);return false;
  }
  notify(Mood::Listening,"Hello! I'm listening",false,false,0,0,true);
  if(!playCue(client,"listening",job.volume)){notify(Mood::Error,"Ready chime unavailable",true);return false;}
  if(cancelListening.load()){notify(Mood::Idle,"Listening cancelled",true);return false;}
  return true;
}

// Hands-free follow-up: chime, then listen for another question.
bool followUpStage(BridgeClient& client,const Job& job) {
  notify(Mood::Happy,"Ready for your next question");
  if(!playCue(client,"followup",job.volume)){notify(Mood::Error,"Ready chime unavailable",true);return false;}
  if(cancelListening.load()){notify(Mood::Idle,"Listening cancelled",true);return false;}
  return true;
}

size_t questionSamples(const Job& job) { return 16000*((job.held||job.kind==3||job.kind==4)?10:6); }

// Records one question. Returns the sample count, or 0 after reporting why.
size_t recordQuestion(const Job& job,ReplyBuffer& recording) {
  const bool automatic=job.kind==3||job.kind==4;
  notify(Mood::Listening,automatic?"Listening - take your time":"Listening...");
  size_t limit=questionSamples(job),count=0;
  if(recording.data)count=automatic
    ?audio.utterance(reinterpret_cast<int16_t*>(recording.data),limit,15000,job.threshold,cancelListening,1500)
    :audio.record(reinterpret_cast<int16_t*>(recording.data),limit,job.held,cancelListening);
  if(cancelListening.load()){notify(Mood::Idle,"Listening cancelled",true);return 0;}
  if(count<3200) { notify(automatic?Mood::Idle:Mood::Error,automatic?"Say Hello Franky":"Hold BOOT a little longer",true); return 0; }
  return count;
}

// Applies a volume/brightness command parsed by the bridge and sets the spoken
// confirmation. Returns false after reporting an invalid command.
bool applyControl(JsonVariant command,Job& job,String& answer) {
  if(command["error"].is<const char*>()) {answer=command["error"].as<String>();return true;}
  const char* target=command["target"] | ""; const char* mode=command["mode"] | "";
  bool typed=command["value"].is<int>();
  if(!typed || !Franky::control(target,mode,command["value"].as<int>(),job.volume,job.brightness)) {
    notify(Mood::Error,"Invalid device command",true); return false;
  }
  notify(Mood::Happy,"Settings updated",false,true,job.volume,job.brightness);
  answer=String(target)+" is now "+String(!strcmp(target,"volume")?job.volume:job.brightness)+" percent.";
  return true;
}
bool hasDeviceControl(JsonVariant command) { return command["error"].is<const char*>() || command.is<JsonObject>(); }

// Plays the bridge's streamed reply as it arrives and keeps the screen in step.
struct StreamPlayer : Franky::FrameSink {
  int volume; bool open=false, spoke=false;
  JsonDocument meta,end;
  explicit StreamPlayer(int level):volume(level) {}
  bool onText(char type,const char* text,size_t length) override {
    if(type=='E') {
      if(deserializeJson(end,text,length) || !end.is<JsonObject>()) return false;
      // Even a partially spoken reply is a failed turn when the bridge reports
      // an error. Reject E so it cannot commit history or open a follow-up.
      return end["error"].isUnbound();
    }
    if(type=='T') {spoke=true;notify(Mood::Speaking,String(text));return true;}
    if(deserializeJson(meta,text,length)) return false;  // 'J': what the bridge heard.
    if(meta["pause"]|false) notify(Mood::Idle,"Listening paused - BOOT resumes",false,false,0,0,false,true);
    else if(meta["end_conversation"]|false) notify(Mood::Speaking,"You're welcome");
    else if(!hasDeviceControl(meta["control"]) && String(meta["text"]|"").length()) notify(Mood::Thinking,"Thinking...");
    return true;
  }
  bool onAudio(char,const uint8_t* pcm,size_t bytes) override {
    if(!open && !(open=audio.beginPlayback())) return false;
    return audio.writePlayback(pcm,bytes,volume,cancelListening);
  }
  // While the bridge is still working, keep the open speaker fed with silence
  // (about 11 ms per call) so the I2S DMA never replays stale audio.
  bool onWait() override {
    static const uint8_t silence[512]={};
    if(open) return audio.writePlayback(silence,sizeof(silence),volume,cancelListening);
    delay(2);
    return !cancelListening.load();
  }
  void close(bool finished) { if(open){audio.endPlayback(finished);open=false;} }
};

// Fast path: one streamed request per question (bridge 0.4 and later).
Turn streamedTurn(BridgeClient& client,ReplyBuffer& recording,size_t count,Job& job,History& history,String& answer) {
  JsonDocument context; addContext(context.to<JsonArray>(),history);
  String messages; serializeJson(context,messages);
  StreamPlayer player(job.volume);
  ConverseResult result=client.converse(reinterpret_cast<int16_t*>(recording.data),count,messages,player);
  player.close(result==ConverseResult::Done && !cancelListening.load());
  if(result==ConverseResult::Unsupported) return Turn::Unsupported;
  if(cancelListening.load()){notify(Mood::Idle,"Stopped",true);return Turn::Finished;}
  if(result!=ConverseResult::Done || !player.meta["text"].is<String>()) {
    notify(Mood::Error,player.spoke?"Reply was cut off":"Conversation service unavailable",true);return Turn::Finished;
  }
  if(player.meta["pause"]|false){notify(Mood::Idle,"Listening paused - BOOT resumes",true);return Turn::Finished;}
  if(player.meta["end_conversation"]|false){history=History();notify(Mood::Idle,"Say Hello Franky",true);return Turn::Finished;}
  String words=player.meta["text"].as<String>(); words.trim();
  if(words.length()==0 || words.length()>2000){notify(Mood::Error,"I didn't catch that",true);return Turn::Finished;}
  JsonVariant command=player.meta["control"];
  if(hasDeviceControl(command)) return applyControl(command,job,answer)?Turn::Speak:Turn::Finished;
  if(!player.spoke || !player.end["reply"].is<String>()) {
    Serial.printf("Reply failed: %s\n",player.end["error"]|"no reply");
    notify(Mood::Error,"Chat service unavailable",true);return Turn::Finished;
  }
  history.user=words; history.reply=player.end["reply"].as<String>();
  finishReply(job,true);
  return Turn::Finished;
}

// Compatible path for older bridges: transcribe, chat and speech as separate requests.
Turn stepTurn(BridgeClient& client,ReplyBuffer& recording,size_t count,Job& job,History& history,String& answer,History& next) {
  JsonDocument transcript;
  if(!client.transcribe(reinterpret_cast<int16_t*>(recording.data),count,transcript)) {
    notify(Mood::Error,"Speech service unavailable",true); return Turn::Finished;
  }
  if(cancelListening.load()){notify(Mood::Idle,"Listening cancelled",true);return Turn::Finished;}
  if(transcript["pause"].is<bool>() && transcript["pause"].as<bool>()) {
    notify(Mood::Idle,"Listening paused - BOOT resumes",false,false,0,0,false,true);
    playCue(client,"paused",job.volume);
    notify(Mood::Idle,"Listening paused - BOOT resumes",true);return Turn::Finished;
  }
  if(transcript["end_conversation"].is<bool>() && transcript["end_conversation"].as<bool>()) {
    notify(Mood::Speaking,"You're welcome");
    playCue(client,"welcome",job.volume);
    history=History();
    notify(Mood::Idle,"Say Hello Franky",true);return Turn::Finished;
  }
  if(!transcript["text"].is<String>()) { notify(Mood::Error,"Invalid transcription reply",true); return Turn::Finished; }
  String words=transcript["text"].as<String>(); words.trim();
  if(words.length()==0 || words.length()>2000) { notify(Mood::Error,"I didn't catch that",true); return Turn::Finished; }
  JsonVariant command=transcript["control"];
  if(hasDeviceControl(command)) return applyControl(command,job,answer)?Turn::Speak:Turn::Finished;
  notify(Mood::Thinking,"Thinking...");
  playCue(client,"thinking",job.volume);
  if(cancelListening.load()){notify(Mood::Idle,"Listening cancelled",true);return Turn::Finished;}
  JsonDocument request,response;
  JsonArray messages=request["messages"].to<JsonArray>();
  addContext(messages,history);
  addMessage(messages,"user",words);
  if(!client.json("/v1/chat/completions",request,response)) { notify(Mood::Error,"Chat service unavailable",true); return Turn::Finished; }
  if(!response["choices"][0]["message"]["content"].is<String>()) { notify(Mood::Error,"Invalid chat reply",true); return Turn::Finished; }
  answer=response["choices"][0]["message"]["content"].as<String>(); answer.trim();
  if(answer.length()==0 || answer.length()>1800) { notify(Mood::Error,"Reply is empty or too long",true); return Turn::Finished; }
  next.user=words; next.reply=answer;
  return Turn::Speak;
}

// Speaks a complete answer through /v1/audio/speech (greeting, device
// confirmations, and replies from older bridges).
void speakAnswer(BridgeClient& client,const Job& job,const String& answer,History& history,const History& next) {
  if(cancelListening.load()){notify(Mood::Idle,"Stopped",true);return;}
  notify(Mood::Thinking,"Preparing my voice...");
  ReplyBuffer pcm(2880000);
  if(!client.speech(answer,pcm)) {notify(Mood::Error,"Voice service unavailable",true);return;}
  if(cancelListening.load()){notify(Mood::Idle,"Stopped",true);return;}
  notify(Mood::Speaking,answer);
  bool ok=audio.play(pcm.data,pcm.used,job.volume,cancelListening);
  if(cancelListening.load()){notify(Mood::Idle,"Stopped",true);return;}
  if(ok && next.user.length()) history=next;
  finishReply(job,ok);
}

void voiceTask(void*) {
  Job job;
  History history;
  // Cleared after an older bridge answers 404; a restart checks again.
  bool streaming=true;
  while(true) {
    if(xQueueReceive(jobs,&job,portMAX_DELAY)!=pdTRUE) continue;
    BridgeClient client(job.url,cancelListening);
    if(job.kind==2) {speakerTest(job);continue;}
    if(job.kind==3 && !wakeStage(client,job)) continue;
    if(job.kind==4 && !followUpStage(client,job)) continue;
    String answer; History next;
    if(job.kind==0) {
      answer="Hello! I'm Franky, your little frog companion. I'm ready when you need me.";
      // Fetch the chimes now so the first conversation does not wait for them.
      for(const char* kind:{"listening","thinking","followup"}) cachedCue(client,kind);
    } else {
      ReplyBuffer recording(questionSamples(job)*2);
      size_t count=recordQuestion(job,recording);
      if(!count) continue;
      notify(Mood::Thinking,"Hearing your words...");
      Turn turn=streaming?streamedTurn(client,recording,count,job,history,answer):Turn::Unsupported;
      if(turn==Turn::Unsupported) {streaming=false;turn=stepTurn(client,recording,count,job,history,answer,next);}
      if(turn==Turn::Finished) continue;
    }
    speakAnswer(client,job,answer,history,next);
  }
}

void saveLevels(int newVolume,int newBrightness) {
  if(newVolume!=volume) {volume=newVolume;prefs.putInt("volume",volume);}
  if(newBrightness!=brightness) {brightness=newBrightness;prefs.putInt("bright",brightness);face.level(brightness);}
}
void startJob(uint8_t kind,bool held=false) {
  if(interaction.busy || !audioReady || (kind!=2 && (WiFi.status()!=WL_CONNECTED || bridge.isEmpty()))) return;
  if(paused && kind!=2)return;
  Job job{}; bridge.toCharArray(job.url,sizeof(job.url)); job.volume=volume;job.brightness=brightness;job.kind=kind;job.held=held;job.threshold=wakeThreshold;
  cancelListening.store(false);
  if(xQueueSend(jobs,&job,0)==pdTRUE) {interaction.begin(kind);lastInteraction=millis();}
}
void cancelWork(Franky::Pending next=Franky::Pending::None) {
  cancelListening.store(true);
  interaction.cancel(next);
  nextListenAt=millis()+700;
  state=next!=Franky::Pending::None?"Waiting for microphone...":interaction.busy?"Stopping current request...":"Stopped";
  mood=Mood::Idle;
}
void jsonReply(int code,JsonDocument& doc) {
  String out;serializeJson(doc,out);web.sendHeader("Cache-Control","no-store");web.send(code,"application/json",out);
}
void errorReply(int code,const char* text) {JsonDocument d;d["error"]=text;jsonReply(code,d);}
bool authorized(bool requireAvailable=true) {
  if(web.header("X-Franky-Token")!=csrf) {errorReply(403,"Refresh the page and try again");return false;}
  if(requireAvailable && !interaction.canConfigure()) {errorReply(409,"Franky is busy. Stop the current reply or try again afterward.");return false;}
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
    JsonDocument d;d["version"]="0.4.0-dev";d["state"]=state;d["busy"]=interaction.busy;d["audio"]=audioReady;d["connected"]=WiFi.status()==WL_CONNECTED;
    d["ssid"]=ssid;d["bridge"]=bridge;d["volume"]=volume;d["brightness"]=brightness;d["token"]=csrf;d["text"]=lastText;
    d["hands_free"]=handsFree;d["paused"]=paused;d["wake_monitoring"]=interaction.wakeMonitoring;d["wake_threshold"]=wakeThreshold;d["stopping"]=interaction.stopping;d["follow_up_pending"]=interaction.followUpReady;
    d["pending_manual"]=interaction.pending!=Franky::Pending::None;
    d["ip"]=WiFi.localIP().toString();d["psram_free"]=ESP.getFreePsram();jsonReply(200,d);
  });
  web.on("/listening",HTTP_POST,[]{
    // Partial updates avoid overwriting settings changed in another browser.
    if(!authorized(false))return;
    JsonDocument d;if(!readBody(d))return;
    bool hasEnabled=!d["enabled"].isUnbound(),hasPaused=!d["paused"].isUnbound(),hasThreshold=!d["threshold"].isUnbound();
    if((!hasEnabled&&!hasPaused&&!hasThreshold)||(hasEnabled&&!d["enabled"].is<bool>())||(hasPaused&&!d["paused"].is<bool>())||(hasThreshold&&!d["threshold"].is<int>())) {errorReply(400,"Invalid listening settings");return;}
    int threshold=hasThreshold?d["threshold"].as<int>():wakeThreshold;
    if(threshold<60||threshold>1200){errorReply(400,"Sensitivity threshold: 60-1200");return;}
    if(hasEnabled)handsFree=d["enabled"].as<bool>();if(hasPaused)paused=d["paused"].as<bool>();wakeThreshold=threshold;
    prefs.putBool("handsfree",handsFree);prefs.putBool("paused",paused);prefs.putInt("wakethresh",threshold);
    if(paused||(hasEnabled&&!handsFree)||interaction.wakeMonitoring)cancelWork();
    interaction.pending=Franky::Pending::None;interaction.followUpReady=false;
    d.clear();d["ok"]=true;jsonReply(200,d);
  });
  web.on("/controls",HTTP_POST,[]{
    if(!authorized())return;JsonDocument d;if(!readBody(d))return;
    bool hasVolume=!d["volume"].isUnbound(),hasBrightness=!d["brightness"].isUnbound();
    if((!hasVolume&&!hasBrightness)||(hasVolume&&!d["volume"].is<int>())||(hasBrightness&&!d["brightness"].is<int>())) {errorReply(400,"Use whole percentages");return;}
    int v=hasVolume?d["volume"].as<int>():volume,b=hasBrightness?d["brightness"].as<int>():brightness;
    if(v<0||v>100||b<10||b>100){errorReply(400,"Volume: 0-100; brightness: 10-100");return;}
    if(interaction.wakeMonitoring)cancelWork();
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
    if(interaction.wakeMonitoring)cancelWork();
    prefs.putString("ssid",name);prefs.putString("pass",secret);prefs.putString("bridge",url);
    d.clear();d["ok"]=true;jsonReply(200,d);restartAt=millis()+1500;
  });
  web.on("/talk",HTTP_POST,[]{
    if(!authorized())return;
    if(!audioReady||WiFi.status()!=WL_CONNECTED||bridge.isEmpty()){errorReply(503,"Connect Wi-Fi and the voice bridge first; check audio hardware");return;}
    if(paused){errorReply(409,"Resume listening first");return;}
    if(interaction.wakeMonitoring){cancelWork(Franky::Pending::WebTalk);JsonDocument d;d["ok"]=true;jsonReply(202,d);return;}
    startJob(1);JsonDocument d;d["ok"]=interaction.busy;jsonReply(interaction.busy?202:503,d);
  });
  web.on("/stop",HTTP_POST,[]{
    if(!authorized(false))return;
    cancelWork();JsonDocument d;d["ok"]=true;d["stopping"]=interaction.stopping;jsonReply(202,d);
  });
  web.on("/test-sound",HTTP_POST,[]{
    if(!authorized())return;if(!audioReady){errorReply(503,"Audio hardware unavailable");return;}
    if(interaction.wakeMonitoring)cancelWork(Franky::Pending::SoundTest);else startJob(2);
    JsonDocument d;d["ok"]=interaction.busy;jsonReply(interaction.busy?202:503,d);
  });
  web.on("/about",HTTP_GET,[]{web.send(200,"text/plain","Franky firmware 0.4.0-dev\nCopyright 2026 DigitalRCS. Original application and artwork: MIT.\nCodec drivers: Espressif, Apache-2.0. Display: Adafruit BSD. Arduino core and other dependencies retain their licenses.\nNo warranty. Source and full notices: https://github.com/digitalrcs/DigitalRCS-Local-LLM-Chatbot\n");});
  web.onNotFound([]{if(ap){web.sendHeader("Location","http://192.168.4.1");web.send(302,"text/plain","");}else errorReply(404,"Not found");});
  web.begin();
}

void setup() {
  Serial.begin(115200);delay(300);Serial.println("DigitalRCS Franky independent firmware 0.4.0-dev");
  pinMode(Board::talk,INPUT_PULLUP);pinMode(Board::pageUp,INPUT_PULLUP);pinMode(Board::pageDown,INPUT_PULLUP);
  prefs.begin("franky2",false);
  ssid=prefs.getString("ssid","");password=prefs.getString("pass","");bridge=prefs.getString("bridge","");
  volume=Franky::clamp(prefs.getInt("volume",60),0,100);brightness=Franky::clamp(prefs.getInt("bright",80),10,100);
  handsFree=prefs.getBool("handsfree",false);paused=prefs.getBool("paused",false);
  wakeThreshold=Franky::clamp(prefs.getInt("wakethresh",120),60,1200);
  face.begin(brightness);face.draw(Mood::Setup,"Hello, I'm Franky","Starting my little pond...");
  csrf=String(esp_random(),HEX)+String(esp_random(),HEX)+String(esp_random(),HEX)+String(esp_random(),HEX);
  audioReady=psramFound()&&audio.begin();Serial.printf("Audio: %s. PSRAM: %u bytes\n",audioReady?"ready":"unavailable",ESP.getPsramSize());
  jobs=xQueueCreate(1,sizeof(Job));events=xQueueCreate(8,sizeof(Event));
  if(!jobs||!events||xTaskCreatePinnedToCore(voiceTask,"franky-voice",24576,nullptr,1,nullptr,0)!=pdPASS) {
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
    // A cancelled worker may have queued an event before it saw the flag.
    // Release it on done, but never apply stale settings or reopen follow-up.
    bool stopped=interaction.stopping;
    if(!stopped) {
      mood=event.mood;lastText=event.text;
      state=mood==Mood::Speaking?"Franky is speaking":String(event.text);
      if(event.settings)saveLevels(event.volume,event.brightness);
      if(event.engaged)interaction.wakeMonitoring=false;
      if(event.pause){paused=true;prefs.putBool("paused",true);}
    }
    if(event.done){
      nextListenAt=millis()+(interaction.wakeMonitoring?(event.mood==Mood::Error?2000:40):700);
      interaction.finish(event.followUp,handsFree,paused);
      if(stopped){state="Stopped";mood=Mood::Idle;lastText="";}
      lastInteraction=millis();
    }
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
  if(!connected&&hadConnection){hadConnection=false;offlineSince=millis();greeted=false;cancelWork();MDNS.end();}
  if(!connected&&!ap&&millis()-offlineSince>20000)openSetup();
  if(connected&&!interaction.busy&&!greeted&&audioReady&&bridge.length()){greeted=true;startJob(0);}
  static Franky::TalkButton talkButton;
  bool down=digitalRead(Board::talk)==LOW;
  if(talkButton.press(down,millis())) {
    if(paused){paused=false;prefs.putBool("paused",false);lastInteraction=millis();}
    else if(interaction.wakeMonitoring){cancelWork(Franky::Pending::HeldTalk);}
    else if(interaction.busy||interaction.followUpReady){cancelWork();}
    else if(connected)startJob(1,true);
  }
  auto pending=interaction.takePending(down);
  if(pending==Franky::Pending::HeldTalk)startJob(1,true);
  else if(pending==Franky::Pending::WebTalk)startJob(1);
  else if(pending==Franky::Pending::SoundTest)startJob(2);
  if(interaction.canConfigure()&&digitalRead(Board::pageUp)==LOW){if(!upSince)upSince=millis();if(millis()-upSince>3000){cancelWork();openSetup();}}else upSince=0;
  if(interaction.canConfigure()&&digitalRead(Board::pageDown)==LOW){if(!downSince)downSince=millis();if(millis()-downSince>70&&downSince!=UINT32_MAX){if(interaction.wakeMonitoring)cancelWork(Franky::Pending::SoundTest);else startJob(2);downSince=UINT32_MAX;}}else downSince=0;
  if(!interaction.busy&&!ap&&mood==Mood::Happy&&millis()-lastInteraction>1800){mood=Mood::Idle;state="Hold BOOT to talk";}
  if(!interaction.busy&&!ap&&mood==Mood::Error&&millis()-lastInteraction>10000&&audioReady){mood=Mood::Idle;state="Hold BOOT to retry";}
  if(paused){state="Listening paused";statusDetail="Press BOOT to resume";mood=Mood::Idle;}
  else if(handsFree&&!ap&&mood!=Mood::Error&&(!interaction.busy||interaction.wakeMonitoring)){state="Say Hello Franky";statusDetail="Wait for the chime, then ask";mood=Mood::Idle;}
  if(handsFree&&!paused&&!interaction.busy&&!ap&&connected&&greeted&&int32_t(millis()-nextListenAt)>=0){
    uint8_t kind=interaction.followUpReady?4:3;interaction.followUpReady=false;startJob(kind);
  }
  face.draw(mood,state,statusDetail,audio.mouth.load());
  if(restartAt&&int32_t(millis()-restartAt)>=0)ESP.restart();
  delay(5);
}
