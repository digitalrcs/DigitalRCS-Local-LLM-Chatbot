// Exercise the shipped page scripts with deterministic device/bridge responses.
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const tick = () => new Promise(resolve => setImmediate(resolve));
const response = data => ({ok: true, json: async () => data});
const deferred = () => { let resolve; const promise = new Promise(r => { resolve = r; }); return {promise, resolve}; };

async function page(file, fetch) {
  const elements = {}, timers = new Map(); let timerId = 0;
  function element(id) {
    return elements[id] ||= {
      value: ({volume: '60', brightness: '80', wakeThreshold: '120'})[id] || '',
      textContent: '', checked: false, disabled: false, hidden: true, options: [],
      add(option) { this.options.push(option); }, replaceChildren() { this.options = []; },
      play: async () => {},
    };
  }
  const context = vm.createContext({
    document: {getElementById: element}, fetch, AbortController,
    Option: function (text, value) { this.text = text; this.value = value; },
    URL: {createObjectURL: () => 'blob:test', revokeObjectURL: () => {}},
    setTimeout: (fn, ms) => {timers.set(++timerId, {fn, ms}); return timerId;},
    clearTimeout: id => timers.delete(id),
  });
  const html = fs.readFileSync(path.join(__dirname, '..', file), 'utf8');
  vm.runInContext(html.match(/<script>([\s\S]*?)<\/script>/)[1], context);
  await tick();
  return {context, element, timers};
}

async function devicePage({failFirst = false} = {}) {
  const status = {token: 'synthetic', busy: false, stopping: false, paused: false,
    hands_free: false, wake_monitoring: false, state: 'Ready', connected: true,
    audio: true, wake_threshold: 120, ssid: 'Test network', bridge: 'http://example.test:8766',
    volume: 60, brightness: 80};
  const requests = [];
  const hooks = {status: null, post: null};
  let failed = false;
  const p = await page('firmware/setup.html', async (url, options) => {
    requests.push({url, data: options.body ? JSON.parse(options.body) : undefined});
    if (url === '/status') {
      if (failFirst && !failed) {failed = true; throw Error('offline');}
      if (hooks.status) return hooks.status(options);
      return response({...status});
    }
    const data = JSON.parse(options.body);
    if (hooks.post) await hooks.post(url, data);
    if (url === '/controls') Object.assign(status, data);
    if (url === '/listening') {
      if ('enabled' in data) status.hands_free = data.enabled;
      if ('threshold' in data) status.wake_threshold = data.threshold;
      if ('paused' in data) status.paused = data.paused;
    }
    if (url === '/talk') status.busy = true;
    if (url === '/stop') {status.stopping = true;status.pending_manual = false;status.follow_up_pending = false;}
    return response({ok: true});
  });
  return {...p, status, requests, hooks,
    edit(id, value) {const e = p.element(id); if (id === 'handsFree') e.checked = value; else e.value = String(value); e.oninput();},
    posted(url) {return requests.filter(r => r.url === url).map(r => r.data);},
  };
}

test('initial connection failure recovers all fields on first successful poll', async () => {
  const p = await devicePage({failFirst: true});
  assert.equal(p.element('talk').disabled, true);
  assert.equal(p.element('apply').disabled, true);
  await p.context.load();
  assert.equal(p.element('ssid').value, 'Test network');
  assert.equal(p.element('bridge').value, 'http://example.test:8766');
  assert.equal(p.element('talk').disabled, false);
});

test('a brightness save cannot overwrite an external volume change', async () => {
  const p = await devicePage();
  p.status.volume = 20;
  await p.context.load();
  assert.equal(p.element('volume').value, 20);
  p.edit('brightness', 45);
  await p.element('apply').onclick();
  assert.deepEqual(p.posted('/controls'), [{brightness: 45}]);
  assert.equal(p.status.volume, 20);
});

test('polling preserves unsaved edits while updating untouched fields', async () => {
  const p = await devicePage();
  p.edit('brightness', 45);p.status.volume = 20;p.status.brightness = 90;
  await p.context.load();
  assert.equal(p.element('brightness').value, '45');
  assert.equal(p.element('volume').value, 20);
});

test('an edit made during a save is retained for the next save', async () => {
  const p = await devicePage();const gate = deferred();
  p.hooks.post = () => gate.promise;
  p.edit('brightness', 45);
  const first = p.element('apply').onclick();
  await tick();p.edit('brightness', 70);gate.resolve();await first;
  assert.equal(p.element('brightness').value, '70');
  p.hooks.post = null;
  await p.element('apply').onclick();
  assert.deepEqual(p.posted('/controls'), [{brightness: 45}, {brightness: 70}]);
});

test('failed saves retain edits and display the server error', async () => {
  const p = await devicePage();p.edit('volume', 35);
  p.hooks.post = () => {throw Error('Try again after this reply.');};
  await p.element('apply').onclick();
  assert.equal(p.element('volume').value, '35');
  assert.match(p.element('message').textContent, /Try again/);
  p.hooks.post = null;await p.element('apply').onclick();
  assert.equal(p.status.volume, 35);
});

test('passive monitoring permits controls; active and stopping states lock them', async () => {
  const p = await devicePage();
  p.status.busy = true;p.status.wake_monitoring = true;await p.context.load();
  for (const id of ['talk', 'apply', 'saveConnection']) assert.equal(p.element(id).disabled, false, id);
  p.status.wake_monitoring = false;await p.context.load();
  for (const id of ['talk', 'apply', 'saveConnection']) assert.equal(p.element(id).disabled, true, id);
  assert.equal(p.element('stop').disabled, false);
  await p.element('stop').onclick();
  assert.deepEqual(p.posted('/stop'), [{}]);
  assert.equal(p.element('stop').disabled, true);
  assert.match(p.element('state').textContent, /Stopping/);
});

test('pause does not save unrelated dirty listening settings', async () => {
  const p = await devicePage();
  p.edit('handsFree', true);p.edit('wakeThreshold', 240);
  await p.element('pause').onclick();
  assert.deepEqual(p.posted('/listening'), [{paused: true}]);
  assert.equal(p.element('handsFree').checked, true);
  assert.equal(p.element('wakeThreshold').value, '240');
  await p.element('saveListening').onclick();
  assert.deepEqual(p.posted('/listening')[1], {enabled: true, threshold: 240});
  assert.equal(p.status.paused, true);
});

test('Stop remains usable between a reply and its queued follow-up', async () => {
  const p = await devicePage();
  p.status.busy = false;p.status.follow_up_pending = true;
  await p.context.load();
  assert.equal(p.element('stop').disabled, false);
  await p.element('stop').onclick();
  assert.deepEqual(p.posted('/stop'), [{}]);
});

test('Stop can cancel queued manual Talk while passive capture is stopping', async () => {
  const p = await devicePage();
  p.status.busy = true;p.status.stopping = true;p.status.pending_manual = true;
  await p.context.load();
  assert.equal(p.element('stop').disabled, false);
  await p.element('stop').onclick();
  assert.deepEqual(p.posted('/stop'), [{}]);
  assert.equal(p.status.pending_manual, false);
  assert.equal(p.element('stop').disabled, true);
});

test('overlapping status refreshes share one request', async () => {
  const p = await devicePage();const gate = deferred();
  p.hooks.status = () => gate.promise;
  const first = p.context.load(), second = p.context.load();
  assert.equal(first, second);
  gate.resolve(response({...p.status}));await first;
  assert.equal(p.requests.filter(r => r.url === '/status').length, 2);
});

test('a pre-save status response cannot overwrite the successful save', async () => {
  const p = await devicePage();const gate = deferred();const old = {...p.status};
  p.hooks.status = () => gate.promise;
  const poll = p.context.load();p.edit('brightness', 35);
  const save = p.element('apply').onclick();await tick();
  p.hooks.status = null;gate.resolve(response(old));await Promise.all([poll, save]);
  assert.equal(p.element('brightness').value, 35);
});

test('timed-out polling disables actions and can recover', async () => {
  const p = await devicePage();
  p.hooks.status = options => new Promise((resolve, reject) => {
    options.signal.addEventListener('abort', () => {const e = Error('timeout');e.name = 'AbortError';reject(e);});
  });
  const pending = p.context.load();
  for (const timer of p.timers.values()) if (timer.ms === 6000) timer.fn();
  await pending;
  for (const id of ['talk', 'apply', 'saveConnection', 'pause', 'saveListening', 'stop']) assert.equal(p.element(id).disabled, true, id);
  p.hooks.status = null;await p.context.load();
  assert.equal(p.element('talk').disabled, false);
});

test('readiness shows service messages and gates voice preview until ready', async () => {
  let ready = {status: 'starting', checks: {
    recognition: {status: 'starting', message: 'Loading recognition…'},
    voice: {status: 'starting', message: 'Loading voice…'},
    chat: {status: 'error', message: 'Load the selected model in LM Studio.'},
  }};
  let offline = false;
  const p = await page('bridge/voices.html', async url => {
    if (offline) throw Error('offline');
    return response(url === '/ready' ? ready : {voices: [{id: 'am_liam', name: 'Liam'}], selected: 'am_liam', engine: 'kokoro', provider: 'lmstudio'});
  });
  assert.match(p.element('readyState').textContent, /Starting/);
  assert.equal(p.element('chatReady').textContent, ready.checks.chat.message);
  assert.equal(p.element('preview').disabled, true);
  ready = {status: 'ready', checks: Object.fromEntries(['recognition', 'voice', 'chat'].map(k => [k, {status: 'ready', message: `${k} available`}]))};
  await p.context.readiness();
  assert.equal(p.element('readyState').textContent, 'Checks passed');
  assert.equal(p.element('preview').disabled, false);
  offline = true;await p.context.readiness();
  assert.match(p.element('readyState').textContent, /unreachable/);
  assert.equal(p.element('preview').disabled, true);
  assert.match(p.element('chatReady').textContent, /Status unavailable/);
});

async function connectionPage(settings) {
  const ready = {status: 'ready', checks: Object.fromEntries(['recognition', 'voice', 'chat'].map(k => [k, {status: 'ready', message: `${k} available`}]))};
  return page('bridge/voices.html', async url => response(url === '/ready' ? ready : {
    voices: [{id: 'am_liam', name: 'Liam'}], selected: 'am_liam', engine: 'kokoro', provider: 'lmstudio', ...settings,
  }));
}

test('connection settings distinguish the saved robot address from local LM Studio', async () => {
  const p = await connectionPage({public_bridge_url: 'http://192.0.2.20:8766', lm_studio_url: 'http://127.0.0.1:1234/v1'});
  assert.equal(p.element('publicBridgeAddress').textContent, 'http://192.0.2.20:8766');
  assert.equal(p.element('lmStudioAddress').textContent, 'http://127.0.0.1:1234/v1');
  assert.match(p.element('publicBridgeHelp').textContent, /same home network/);
  assert.match(p.element('lmStudioHelp').textContent, /localhost.*bridge server itself/);
});

test('unset robot address directs local setup without guessing browser localhost', async () => {
  const p = await connectionPage({public_bridge_url: '', lm_studio_url: 'http://127.0.0.1:1234/v1'});
  assert.equal(p.element('publicBridgeAddress').textContent, 'Not set');
  assert.match(p.element('publicBridgeHelp').textContent, /SET-BRIDGE-ADDRESS\.cmd/);
  assert.match(p.element('publicBridgeHelp').textContent, /localhost.*cannot be used/);
});

test('connection settings render supplied addresses as text and mark cloud routing', async () => {
  const address = '<img src=x onerror="throw Error(1)">';
  const p = await connectionPage({provider: 'gemini', public_bridge_url: address, lm_studio_url: address});
  assert.equal(p.element('publicBridgeAddress').textContent, address);
  assert.equal(p.element('lmStudioAddress').textContent, address);
  assert.equal(p.element('publicBridgeAddress').innerHTML, undefined);
  assert.equal(p.element('lmStudioAddress').innerHTML, undefined);
  assert.match(p.element('lmStudioHelp').textContent, /active chat provider is gemini/);
  assert.match(p.element('lmStudioHelp').textContent, /LM Studio is not currently used/);
});
