// SPDX-License-Identifier: MIT
// Generated from firmware/setup.html by scripts/embed_setup.py
#pragma once
const char setupPage[] PROGMEM = R"FRANKYPAGE(<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Franky · DigitalRCS</title>
<style>:root{color-scheme:light;--ink:#163c30;--paper:#f5f1e5;--green:#30694f}*{box-sizing:border-box}body{margin:0;background:var(--paper);color:var(--ink);font:17px/1.5 "Trebuchet MS",sans-serif}main{max-width:700px;margin:auto;padding:30px 22px 60px}.eyebrow{letter-spacing:.16em;font-size:12px;font-weight:bold;text-transform:uppercase}h1{font:56px/1.08 Georgia,serif;margin:18px 0 10px}h2{font:28px Georgia,serif;margin-top:0}.intro{max-width:460px;color:#536c5b}.badge{display:inline-block;padding:5px 12px;border-radius:24px;background:#d7e9c8;font-size:14px}section{padding:26px 0;border-top:1px solid #bdc9b5;margin-top:26px}label{display:block;font-weight:bold;margin:18px 0 5px}input,button{font:inherit;padding:13px;border:1px solid #9aaf95;border-radius:8px;width:100%;background:#fffef8;color:var(--ink)}input[type=range]{padding:0;accent-color:var(--green)}button{background:var(--green);color:#fff;border:0;cursor:pointer;margin-top:16px;font-weight:bold}button:disabled{opacity:.55;cursor:wait}.muted,small{color:#536c5b}small{display:block;margin-top:5px}output{float:right}a{color:var(--green)}.row{display:flex;gap:16px}.row>*{flex:1}#message{white-space:pre-wrap}details{margin-top:30px}summary{cursor:pointer;font-weight:bold}footer{margin-top:32px;font-size:13px}.frog{float:right;font-size:55px;margin:6px 0 0 16px}@media(max-width:420px){h1{font-size:46px}.row{display:block}}</style>
<main><div class="eyebrow">DigitalRCS · local companion</div><div class="frog" aria-hidden="true">🐸</div><h1>Hello, I'm Franky.</h1><p class="intro">A little frog. A curious mind. Make yourself comfortable and let's get connected.</p><span class="badge" id="state">Connecting to Franky…</span>
<p id="message" role="status" aria-live="polite"></p>
<section><h2>Make yourself heard</h2><p class="muted">Hold BOOT while speaking, then release. During a reply, press BOOT once to stop. Or use the controls below.</p><div class="row"><button id="talk" type="button" disabled>Talk to Franky</button><button id="stop" type="button" disabled>Stop current reply</button></div><small>Talk records for six seconds. Stop also cancels a question or follow-up; a pending network request may take a moment to finish.</small><div class="row"><div><label for="volume">Volume <output id="volumeValue">—</output></label><input id="volume" type="range" min="0" max="100" value="60"></div><div><label for="brightness">Brightness <output id="brightnessValue">—</output></label><input id="brightness" type="range" min="10" max="100" value="80"></div></div><button id="apply" type="button">Save sound &amp; display</button><p><a id="voices" hidden target="_blank" rel="noopener">Find your favorite voice ↗</a></p></section>
<section><h2>Hands-free conversations</h2><p class="muted">Say <strong>Hello Franky</strong>, wait for the rising chime, then ask your question. You have about 15 seconds to start, including after each answer. Say “stop listening” while he is waiting to pause. Press BOOT to resume.</p><p id="listeningState" role="status">Checking microphone…</p><button id="pause" type="button">Pause listening</button><label for="handsFree"><input id="handsFree" type="checkbox" style="width:auto"> Enable Hello Franky (experimental)</label><small>While enabled and unpaused, speech snippets from this room go to your local bridge PC for wake recognition. They are not sent to the chat provider. Voice wake recognition stops during replies. Use BOOT or Stop to interrupt; say “stop listening” while he is waiting to pause hands-free listening.</small><label for="wakeThreshold">Microphone threshold</label><input id="wakeThreshold" type="number" min="60" max="1200" value="120"><small>Lower values hear quieter speech; higher values ignore more room noise. Start at 120.</small><button id="saveListening" type="button">Save hands-free settings</button></section>
<section><h2>A place on your network</h2><p class="muted">Use your home 2.4 GHz Wi-Fi and the address of the PC running the voice bridge.</p><form id="connection"><label for="ssid">Wi-Fi name</label><input id="ssid" required maxlength="32" autocomplete="off"><label for="password">Wi-Fi password</label><input id="password" type="password" maxlength="63" autocomplete="new-password"><small>Leave blank to keep the saved password for the same network. For a new open network, leave it blank.</small><label for="bridge">Voice bridge / AI server address</label><input id="bridge" required placeholder="http://YOUR-PC-ADDRESS:8766" type="url"><small>Use the AI server’s LAN address on port 8766, shown in the bridge website’s Connection settings. Port 1234 belongs to LM Studio and is not the robot’s bridge address. Keep the AI server awake.</small><button id="saveConnection" type="submit" disabled>Save connection &amp; restart</button></form></section>
<details><summary>Setup and recovery</summary><p>On first use, join Wi-Fi <strong>DigitalRCS</strong>, password <strong>11181118</strong>, then open <strong>http://192.168.4.1</strong>. If home Wi-Fi fails, the setup hotspot returns.</p><p>To reopen setup without erasing settings, hold the Page Up button for three seconds while Franky is idle. Do not hold BOOT while powering on: it selects the ESP32 download mode.</p></details><footer>DigitalRCS Local LLM Chatbot · independent firmware preview<br>Local-network use only. <a href="/about">Licenses &amp; about</a></footer></main>
<script>
const $=id=>document.getElementById(id);
const fields={volume:'volume',brightness:'brightness',handsFree:'hands_free',wakeThreshold:'wake_threshold',ssid:'ssid',bridge:'bridge'};
const dirty=new Set();
let device=null,online=false,csrf='',loading=null,revision=0,writes=0;
function value(id){return id==='handsFree'?$(id).checked:['volume','brightness','wakeThreshold'].includes(id)?Number($(id).value):$(id).value}
function buttons(){
  const active=device?.busy&&!device?.wake_monitoring;
  const unavailable=!online||writes>0;
  const locked=unavailable||active||device?.stopping;
  $('talk').disabled=locked||device?.paused||!device?.connected||!device?.audio;
  $('apply').disabled=locked;
  $('saveConnection').disabled=locked;
  $('stop').disabled=!online||!(device?.busy||device?.follow_up_pending||device?.pending_manual)||(!!device?.stopping&&!device?.pending_manual);
  $('pause').disabled=unavailable;
  $('saveListening').disabled=unavailable;
  for(const id of [...Object.keys(fields),'password'])$(id).disabled=!online;
}
async function request(path,options={}){
  const controller=new AbortController();
  const timer=setTimeout(()=>controller.abort(),6000);
  try{
    const r=await fetch(path,{...options,signal:controller.signal,cache:'no-store'});
    const d=await r.json();
    if(!r.ok)throw Error(d.error||'Request failed. Try again.');
    return d;
  }catch(e){
    if(e.name==='AbortError')throw Error('Franky did not respond. Check the connection and try again.');
    throw e;
  }finally{clearTimeout(timer)}
}
function render(d){
  device=d;online=true;csrf=d.token;
  $('state').textContent=d.stopping?'Stopping current request…':d.state;
  $('pause').textContent=d.paused?'Resume listening':'Pause listening';
  $('listeningState').textContent=d.paused?'Microphone paused · BOOT resumes':d.hands_free?'Hello Franky enabled · local recognition':'BOOT button mode';
  for(const [id,key] of Object.entries(fields)){
    if(!dirty.has(id)){
      if(id==='handsFree')$(id).checked=!!d[key];
      else $(id).value=d[key]??'';
    }
  }
  for(const id of ['volume','brightness'])$(id+'Value').textContent=$(id).value+'%';
  $('voices').hidden=!(typeof d.bridge==='string'&&d.bridge.startsWith('http://'));
  if(!$('voices').hidden)$('voices').href=d.bridge;
  buttons();
}
function load(){
  if(loading)return loading;
  const started=revision;
  loading=(async()=>{
    try{const d=await request('/status');if(started===revision&&writes===0)render(d)}
    catch(e){if(started===revision&&writes===0){online=false;$('state').textContent='Franky is offline · reconnecting…';buttons()}}
  })().finally(()=>{loading=null});
  return loading;
}
async function freshStatus(){if(loading)await loading;await load()}
async function post(path,data){return request(path,{method:'POST',headers:{'Content-Type':'application/json','X-Franky-Token':csrf},body:JSON.stringify(data)})}
async function change(path,data,message,saved={}){
  if(!online)return;
  revision++;writes++;buttons();
  try{
    await post(path,data);
    for(const [id,sent] of Object.entries(saved))if(value(id)===sent)dirty.delete(id);
    $('message').textContent=message;
  }catch(e){$('message').textContent=e.message}
  finally{revision++;writes--;buttons();await freshStatus()}
}
for(const id of Object.keys(fields))$(id).oninput=()=>{
  dirty.add(id);
  if(id==='volume'||id==='brightness')$(id+'Value').textContent=$(id).value+'%';
};
$('talk').onclick=()=>change('/talk',{},'Talk requested. Watch Franky’s status for Listening before speaking.');
$('stop').onclick=()=>change('/stop',{},'Stop requested. The current reply and follow-up are cancelled.');
$('apply').onclick=()=>{
  const data={};for(const id of ['volume','brightness'])if(dirty.has(id))data[id]=value(id);
  if(!Object.keys(data).length){$('message').textContent='Sound and display settings are already up to date.';return}
  return change('/controls',data,'Saved your sound and display levels.',data);
};
$('connection').onsubmit=async e=>{
  e.preventDefault();
  const saved={ssid:value('ssid'),bridge:value('bridge')};
  const secret=$('password').value;
  await change('/configure',{...saved,password:secret},'Saved. Franky is restarting. Rejoin your home Wi-Fi, then use the address shown on his screen.',saved);
  // Never retain a submitted password in the page after the attempt.
  if($('password').value===secret)$('password').value='';
};
$('pause').onclick=()=>change('/listening',{paused:!device.paused},device.paused?'Listening resumed.':'Microphone paused. Press BOOT to resume.');
$('saveListening').onclick=()=>{
  const data={},saved={};
  for(const [id,key] of [['handsFree','enabled'],['wakeThreshold','threshold']])if(dirty.has(id)){data[key]=value(id);saved[id]=value(id)}
  if(!Object.keys(data).length){$('message').textContent='Hands-free settings are already up to date.';return}
  return change('/listening',data,'Saved hands-free settings.',saved);
};
async function poll(){await load();setTimeout(poll,2500)}
buttons();poll();
</script></html>
)FRANKYPAGE";
