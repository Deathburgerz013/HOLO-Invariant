"""Local read-only operator console for Holo/Sim."""

from __future__ import annotations

import json
import threading
import webbrowser
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from holosim.config import DEFAULT_CHAIN_FILE
from holosim.continuity_topology import build_continuity_topology
from holosim.idx_public_check import check_idx_packet
from holosim.service import get_service


LOOPBACK_HOSTS = {"127.0.0.1", "localhost", "::1"}

INDEX_HTML = r'''<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>HOLO — Local Continuity</title>
  <style>
    :root {
      color-scheme: dark;
      --bg: #050608;
      --panel: rgba(15, 18, 25, .82);
      --line: rgba(148, 173, 255, .17);
      --text: #f3f6ff;
      --muted: #8992a8;
      --cyan: #58e7ff;
      --violet: #9a7cff;
      --green: #59f2ad;
      --red: #ff6b82;
      --amber: #ffc766;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      min-height: 100vh;
      color: var(--text);
      font-family: Inter, ui-sans-serif, system-ui, -apple-system, Segoe UI, sans-serif;
      background:
        radial-gradient(circle at 18% 6%, rgba(88,231,255,.12), transparent 28rem),
        radial-gradient(circle at 88% 12%, rgba(154,124,255,.13), transparent 30rem),
        linear-gradient(145deg, #030406, #090b12 55%, #050608);
    }
    body::before {
      content: "";
      position: fixed;
      inset: 0;
      pointer-events: none;
      opacity: .18;
      background-image:
        linear-gradient(var(--line) 1px, transparent 1px),
        linear-gradient(90deg, var(--line) 1px, transparent 1px);
      background-size: 48px 48px;
      mask-image: linear-gradient(to bottom, black, transparent 70%);
    }
    main { width: min(1180px, calc(100% - 32px)); margin: 0 auto; padding: 32px 0 72px; }
    header { display: flex; justify-content: space-between; gap: 24px; align-items: end; margin-bottom: 24px; }
    .eyebrow { color: var(--cyan); font: 700 11px/1.2 ui-monospace, monospace; letter-spacing: .22em; }
    h1 { margin: 8px 0 5px; font-size: clamp(34px, 6vw, 72px); line-height: .92; letter-spacing: -.055em; }
    .subtitle { color: var(--muted); margin: 0; max-width: 650px; }
    button {
      border: 1px solid rgba(88,231,255,.35);
      border-radius: 999px;
      padding: 10px 16px;
      color: var(--text);
      background: rgba(88,231,255,.08);
      cursor: pointer;
      font: 700 12px ui-monospace, monospace;
      letter-spacing: .08em;
    }
    button:hover { background: rgba(88,231,255,.16); }
    .header-actions { display: flex; align-items: center; gap: 10px; }
    .header-link { color: var(--cyan); text-decoration: none; border: 1px solid rgba(88,231,255,.35); border-radius: 999px; padding: 10px 14px; font: 800 10px/1 ui-monospace, monospace; letter-spacing: .12em; }
    .header-link:hover { background: rgba(88,231,255,.12); }
    .grid { display: grid; grid-template-columns: repeat(12, 1fr); gap: 14px; }
    .panel {
      position: relative;
      overflow: hidden;
      border: 1px solid var(--line);
      border-radius: 18px;
      background: var(--panel);
      box-shadow: 0 18px 70px rgba(0,0,0,.28);
      backdrop-filter: blur(18px);
    }
    .metric { grid-column: span 3; padding: 18px; min-height: 128px; }
    .metric::after {
      content: ""; position: absolute; inset: auto -20% -70% 20%; height: 100px;
      background: radial-gradient(circle, rgba(88,231,255,.16), transparent 65%);
    }
    .label { color: var(--muted); font: 700 10px ui-monospace, monospace; letter-spacing: .14em; text-transform: uppercase; }
    .value { margin-top: 14px; font-size: clamp(24px, 4vw, 40px); font-weight: 750; letter-spacing: -.04em; }
    .value.small { font: 600 15px/1.5 ui-monospace, monospace; overflow-wrap: anywhere; }
    .good { color: var(--green); }
    .bad { color: var(--red); }
    .wide { grid-column: span 8; }
    .side { grid-column: span 4; }
    .section-head { display: flex; justify-content: space-between; align-items: center; padding: 18px 20px; border-bottom: 1px solid var(--line); }
    h2 { margin: 0; font-size: 15px; letter-spacing: -.01em; }
    .count { color: var(--muted); font: 11px ui-monospace, monospace; }
    .timeline { max-height: 520px; overflow: auto; }
    .event { display: grid; grid-template-columns: 52px 160px 1fr; gap: 12px; padding: 15px 20px; border-bottom: 1px solid rgba(148,173,255,.09); }
    .event:last-child { border-bottom: 0; }
    .idx { color: var(--cyan); font: 700 12px ui-monospace, monospace; }
    .time { color: var(--muted); font: 11px/1.45 ui-monospace, monospace; }
    .preview { min-width: 0; font: 12px/1.5 ui-monospace, monospace; color: #d9dff0; overflow-wrap: anywhere; }
    .empty { padding: 52px 20px; text-align: center; color: var(--muted); }
    .details { padding: 18px 20px; display: grid; gap: 16px; }
    .detail { display: grid; gap: 6px; }
    .detail code { color: #dbe3ff; font: 11px/1.5 ui-monospace, monospace; overflow-wrap: anywhere; }
    .authority { border: 1px solid rgba(154,124,255,.24); border-radius: 14px; padding: 14px; background: rgba(154,124,255,.07); }
    .authority strong { color: var(--violet); font-size: 12px; }
    .authority p { margin: 8px 0 0; color: var(--muted); font-size: 12px; line-height: 1.5; }
    .error { display: none; margin-bottom: 14px; border: 1px solid rgba(255,107,130,.35); background: rgba(255,107,130,.09); color: #ffbcc7; padding: 12px 15px; border-radius: 12px; }
    footer { color: #596174; font: 10px ui-monospace, monospace; margin-top: 18px; text-align: right; }
    @media (max-width: 860px) {
      header { align-items: flex-start; flex-direction: column; }
      .metric { grid-column: span 6; }
      .wide, .side { grid-column: span 12; }
    }
    @media (max-width: 560px) {
      main { width: min(100% - 20px, 1180px); padding-top: 20px; }
      .metric { grid-column: span 12; }
      .event { grid-template-columns: 44px 1fr; }
      .event .preview { grid-column: 1 / -1; }
    }
  </style>
</head>
<body>
  <main>
    <header>
      <div>
        <div class="eyebrow">HOLO / OPERATOR CONSOLE</div>
        <h1>Local continuity.</h1>
        <p class="subtitle">Verified chain state from the selected local evidence file. Read-only by design.</p>
      </div>
      <div class="header-actions">
        <a class="header-link" href="/playground">PLAYGROUND</a>
        <a class="header-link" href="/topology">TOPOLOGY</a>
        <button id="refresh">REFRESH STATE</button>
      </div>
    </header>
    <div id="error" class="error"></div>
    <section class="grid">
      <article class="panel metric"><div class="label">Chain status</div><div id="chainStatus" class="value">—</div></article>
      <article class="panel metric"><div class="label">Verified entries</div><div id="entries" class="value">0</div></article>
      <article class="panel metric"><div class="label">Latest index</div><div id="latestIndex" class="value">—</div></article>
      <article class="panel metric"><div class="label">Compression ratio</div><div id="compression" class="value">—</div></article>

      <article class="panel wide">
        <div class="section-head"><h2>Verified timeline</h2><span id="eventCount" class="count">0 EVENTS</span></div>
        <div id="timeline" class="timeline"><div class="empty">No retained entries yet.</div></div>
      </article>

      <aside class="panel side">
        <div class="section-head"><h2>Current head</h2><span class="count">SHA-256</span></div>
        <div class="details">
          <div class="detail"><span class="label">Head hash</span><code id="headHash">GENESIS</code></div>
          <div class="detail"><span class="label">Chain file</span><code id="chainFile">—</code></div>
          <div class="detail"><span class="label">Anchor</span><code id="anchor">—</code></div>
          <div class="detail"><span class="label">Active hash</span><code id="activeHash">—</code></div>
          <div class="authority"><strong>OBSERVATIONAL SURFACE</strong><p>This console verifies and displays retained state. It grants no write, execution, acceptance, or truth authority.</p></div>
        </div>
      </aside>
    </section>
    <footer id="generated">WAITING FOR LOCAL STATE</footer>
  </main>
  <script>
    const $ = (id) => document.getElementById(id);
    const escapeHtml = (value) => String(value ?? "").replace(/[&<>'"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[c]));
    const compactTime = (value) => value ? String(value).replace('T', ' ').replace('+00:00Z', 'Z') : '—';

    function render(data) {
      const status = data.service || {};
      const verify = status.verify || {};
      const health = status.health || {};
      const identity = status.identity || {};
      const timeline = Array.isArray(data.timeline) ? data.timeline : [];
      $('chainStatus').textContent = verify.status === 'ok' ? 'VERIFIED' : 'ERROR';
      $('chainStatus').className = 'value ' + (verify.status === 'ok' ? 'good' : 'bad');
      $('entries').textContent = verify.entries ?? 0;
      $('latestIndex').textContent = verify.latest_idx ?? '—';
      $('compression').textContent = health.compression_ratio == null ? '—' : String(health.compression_ratio);
      $('headHash').textContent = verify.latest_hash || 'GENESIS';
      $('chainFile').textContent = verify.chain_file || identity.chain_file || '—';
      $('anchor').textContent = identity.anchor || '—';
      $('activeHash').textContent = identity.active_hash || '—';
      $('eventCount').textContent = `${timeline.length} EVENT${timeline.length === 1 ? '' : 'S'}`;
      $('generated').textContent = `LOCAL SNAPSHOT ${data.generated_at || ''}`;
      $('timeline').innerHTML = timeline.length ? timeline.slice().reverse().map(item => `
        <div class="event">
          <div class="idx">#${escapeHtml(item.idx)}</div>
          <div class="time">${escapeHtml(compactTime(item.timestamp))}<br>${escapeHtml(item.type || 'plain')}</div>
          <div class="preview">${escapeHtml(item.preview || '')}</div>
        </div>`).join('') : '<div class="empty">No retained entries yet.</div>';
    }

    async function refresh() {
      $('error').style.display = 'none';
      try {
        const response = await fetch('/api/snapshot', {cache: 'no-store'});
        const data = await response.json();
        if (!response.ok) throw new Error(data.error || `HTTP ${response.status}`);
        render(data);
      } catch (error) {
        $('error').textContent = `Unable to verify local state: ${error.message}`;
        $('error').style.display = 'block';
        $('chainStatus').textContent = 'UNAVAILABLE';
        $('chainStatus').className = 'value bad';
      }
    }

    $('refresh').addEventListener('click', refresh);
    refresh();
    setInterval(refresh, 5000);
  </script>
</body>
</html>'''


PLAYGROUND_HTML = r'''<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>HOLO — Continuity Playground</title>
  <style>
    :root{color-scheme:dark;--bg:#030408;--panel:rgba(11,15,24,.84);--line:rgba(129,164,255,.2);--text:#f4f7ff;--muted:#8290aa;--cyan:#4ce8ff;--violet:#9d79ff;--green:#4ef0a5;--red:#ff647d;--amber:#ffc45c}
    *{box-sizing:border-box} body{margin:0;min-height:100vh;color:var(--text);font-family:Inter,system-ui,sans-serif;background:radial-gradient(circle at 50% 30%,rgba(85,45,170,.18),transparent 30rem),radial-gradient(circle at 15% 8%,rgba(76,232,255,.12),transparent 24rem),linear-gradient(145deg,#020307,#090c16 55%,#030408)}
    body:before{content:"";position:fixed;inset:0;pointer-events:none;opacity:.16;background-image:linear-gradient(var(--line) 1px,transparent 1px),linear-gradient(90deg,var(--line) 1px,transparent 1px);background-size:44px 44px;mask-image:radial-gradient(circle at center,black,transparent 78%)}
    main{width:min(1260px,calc(100% - 28px));margin:auto;padding:26px 0 60px}.top{display:flex;justify-content:space-between;gap:20px;align-items:flex-end;margin-bottom:18px}.eyebrow,.label{font:700 10px ui-monospace,monospace;letter-spacing:.18em;color:var(--cyan)}h1{margin:7px 0 4px;font-size:clamp(36px,6vw,76px);line-height:.9;letter-spacing:-.06em}.sub{margin:0;color:var(--muted)}a{color:var(--cyan);text-decoration:none;font:700 11px ui-monospace,monospace}.layout{display:grid;grid-template-columns:minmax(0,1fr) minmax(340px,.7fr);gap:14px}.panel{border:1px solid var(--line);border-radius:18px;background:var(--panel);backdrop-filter:blur(18px);box-shadow:0 22px 80px rgba(0,0,0,.32);overflow:hidden}.head{padding:15px 18px;border-bottom:1px solid var(--line);display:flex;justify-content:space-between;align-items:center}.head h2{font-size:13px;margin:0}.inputs{display:grid;grid-template-columns:1fr 1fr;gap:12px;padding:14px}textarea{width:100%;min-height:230px;resize:vertical;border:1px solid var(--line);border-radius:13px;background:rgba(2,4,9,.72);color:#dfe8ff;padding:13px;font:11px/1.55 ui-monospace,monospace;outline:none}textarea:focus{border-color:rgba(76,232,255,.55)}button{border:1px solid rgba(76,232,255,.42);border-radius:999px;padding:11px 17px;color:var(--text);background:rgba(76,232,255,.1);cursor:pointer;font:800 11px ui-monospace,monospace;letter-spacing:.1em}button:hover{background:rgba(76,232,255,.19)}.actions{padding:0 14px 15px;display:flex;justify-content:flex-end;gap:8px}.graph{min-height:430px;display:grid;place-items:center;padding:10px;background:radial-gradient(circle,rgba(157,121,255,.08),transparent 60%)}svg{width:100%;height:auto;max-height:430px}.edge{stroke:rgba(134,152,210,.32);stroke-width:2;stroke-dasharray:7 8}.edge.pass{stroke:var(--green);filter:drop-shadow(0 0 7px var(--green))}.edge.abort{stroke:var(--red);filter:drop-shadow(0 0 7px var(--red))}.core{fill:#050711;stroke:var(--violet);stroke-width:2;filter:drop-shadow(0 0 18px rgba(157,121,255,.65))}.moving{fill:#050711;stroke:var(--cyan);stroke-width:2;filter:drop-shadow(0 0 16px rgba(76,232,255,.5))}.nodeText{fill:#eff3ff;font:700 13px ui-monospace,monospace;text-anchor:middle}.nodeSub{fill:#8290aa;font:10px ui-monospace,monospace;text-anchor:middle}.receipt{padding:14px 18px 18px}.state{font-size:clamp(32px,5vw,58px);font-weight:850;letter-spacing:-.05em;margin:7px 0}.state.pass{color:var(--green)}.state.abort,.state.error{color:var(--red)}pre{margin:12px 0 0;white-space:pre-wrap;overflow-wrap:anywhere;border:1px solid var(--line);border-radius:12px;background:rgba(1,3,7,.7);padding:12px;color:#cfd9f2;font:10px/1.5 ui-monospace,monospace}.notice{margin-top:12px;padding:12px;border:1px solid rgba(157,121,255,.25);border-radius:12px;color:var(--muted);font-size:11px;line-height:1.5}.notice strong{color:var(--violet)}@media(max-width:900px){.layout{grid-template-columns:1fr}.inputs{grid-template-columns:1fr}.top{align-items:flex-start;flex-direction:column}}
  </style>
</head>
<body><main>
  <div class="top"><div><div class="eyebrow">HOLO / CONTINUITY PLAYGROUND</div><h1>See the gate decide.</h1><p class="sub">Frozen authority compared with a moving Spine. Nothing is retained.</p></div><a href="/">← OPERATOR CONSOLE</a></div>
  <div class="layout">
    <section class="panel"><div class="head"><h2>RELATIONAL INPUT</h2><span class="label">INLINE / READ ONLY</span></div><div class="inputs">
      <label><span class="label">FROZEN IDX</span><textarea id="frozenInput">IDX:v=1;n=1
S1=CORE@0682c5f2076f099c34cfdd15a9e063849ed437a49677e6fcc5b4198c76575be5
ACTIVE_HASH=frozen-head</textarea></label>
      <label><span class="label">MOVING SPINE</span><textarea id="packetInput">{
  "version": 1,
  "active_hash": "frozen-head",
  "slots": [{"name": "CORE", "payload": "original"}]
}</textarea></label>
    </div><div class="actions"><button id="mismatch">LOAD MISMATCH</button><button id="check">CHECK RELATION</button></div></section>
    <aside class="panel"><div class="head"><h2>VISIBLE RELATION</h2><span class="label">MISMATCH → ABORT</span></div><div class="graph">
      <svg id="continuityGraph" viewBox="0 0 520 390" role="img" aria-label="Frozen IDX and moving Spine relation">
        <defs><radialGradient id="well"><stop offset="0" stop-color="#24134e"/><stop offset="1" stop-color="#030408"/></radialGradient></defs>
        <circle cx="260" cy="195" r="150" fill="url(#well)" opacity=".72"/><line id="relationEdge" class="edge" x1="170" y1="195" x2="350" y2="195"/>
        <circle class="core" cx="145" cy="195" r="68"/><text class="nodeText" x="145" y="190">FROZEN IDX</text><text class="nodeSub" x="145" y="210">admission authority</text>
        <circle class="moving" cx="375" cy="195" r="68"/><text class="nodeText" x="375" y="190">MOVING SPINE</text><text class="nodeSub" x="375" y="210">candidate state</text>
        <circle cx="260" cy="195" r="15" fill="#080b13" stroke="#8290aa"/><text id="gateMark" class="nodeText" x="260" y="201">?</text>
      </svg>
    </div><div class="receipt"><div class="label">DECISION RECEIPT</div><div id="decision" class="state">WAITING</div><div id="reason" class="sub">No comparison has run.</div><pre id="receipt">{}</pre><div class="notice"><strong>OBSERVATIONAL ONLY.</strong> This page compares supplied values. It grants no truth, acceptance, write, or execution authority.</div></div></aside>
  </div>
</main><script>
  const $=id=>document.getElementById(id); const edge=$('relationEdge');
  function show(data){const state=String(data.status||'ERROR').toLowerCase();$('decision').textContent=data.status||'ERROR';$('decision').className='state '+state;$('reason').textContent=data.code||data.error||'No code';$('receipt').textContent=JSON.stringify(data,null,2);edge.className='edge '+(state==='pass'?'pass':'abort');$('gateMark').textContent=state==='pass'?'✓':'×';}
  async function check(){try{const response=await fetch('/api/idx-check',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({frozen_idx:$('frozenInput').value,packet:JSON.parse($('packetInput').value)})});show(await response.json());}catch(error){show({status:'ERROR',code:'LOCAL_INPUT_INVALID',error:String(error),write_authority:'NONE',execution_authority:'NONE'});}}
  $('check').addEventListener('click',check);$('mismatch').addEventListener('click',()=>{const value=JSON.parse($('packetInput').value);value.slots[0].payload=value.slots[0].payload==='original'?'changed':'original';$('packetInput').value=JSON.stringify(value,null,2);check();});
</script></body></html>'''


TOPOLOGY_HTML = r'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>HOLO - Continuity Topology</title><style>
:root{color-scheme:dark;--bg:#050711;--panel:rgba(10,14,24,.88);--line:rgba(130,153,220,.2);--text:#eef3ff;--muted:#8490aa;--cyan:#4ce8ff;--violet:#9d79ff;--green:#4ff0aa;--red:#ff647d}*{box-sizing:border-box}body{margin:0;min-height:100vh;background:radial-gradient(circle at 15% 5%,rgba(76,232,255,.1),transparent 28rem),radial-gradient(circle at 85% 10%,rgba(157,121,255,.12),transparent 30rem),#050711;color:var(--text);font-family:Inter,system-ui,sans-serif}main{width:min(1380px,calc(100% - 30px));margin:auto;padding:28px 0 60px}.top{display:flex;justify-content:space-between;align-items:end;gap:20px;margin-bottom:18px}.eyebrow,.label{color:var(--cyan);font:700 10px ui-monospace,monospace;letter-spacing:.2em}h1{margin:7px 0 4px;font-size:clamp(38px,6vw,76px);line-height:.92;letter-spacing:-.055em}.sub{margin:0;color:var(--muted)}nav{display:flex;gap:14px}a{color:var(--cyan);text-decoration:none;font:700 11px ui-monospace,monospace}.layout{display:grid;grid-template-columns:minmax(0,1fr) 390px;gap:14px}.panel{border:1px solid var(--line);border-radius:18px;background:var(--panel);overflow:hidden;box-shadow:0 22px 80px rgba(0,0,0,.3)}.head{padding:15px 18px;border-bottom:1px solid var(--line);display:flex;justify-content:space-between}.head h2{font-size:13px;margin:0}.legend{display:flex;gap:14px;color:var(--muted);font:10px ui-monospace,monospace}.legend i{display:inline-block;width:18px;border-top:2px solid;margin-right:5px}.continuity{color:#71809d}.correction{color:var(--violet)}.revalidation{color:var(--cyan)}#topologyGraph{width:100%;height:650px;display:block;background:radial-gradient(circle,rgba(157,121,255,.08),transparent 58%)}.edge{fill:none;stroke-width:1.7}.edge.continuity{stroke:#536078}.edge.correction{stroke:var(--violet);stroke-dasharray:7 5}.edge.revalidation{stroke:var(--cyan);stroke-dasharray:2 6}.node{cursor:pointer}.node circle{fill:#070a12;stroke-width:2}.node.record circle{stroke:#71809d}.node.correction circle{stroke:var(--violet)}.node.revalidation circle{stroke:var(--cyan)}.node:hover circle,.node.selected circle{stroke:var(--green);filter:drop-shadow(0 0 10px var(--green))}.node text{fill:var(--text);font:700 11px ui-monospace,monospace;text-anchor:middle;pointer-events:none}.receipt{padding:18px}.state{font-size:34px;font-weight:850;color:var(--green);margin:8px 0}pre{white-space:pre-wrap;overflow-wrap:anywhere;border:1px solid var(--line);border-radius:12px;background:#03050a;padding:13px;min-height:350px;color:#cfd9f2;font:10px/1.55 ui-monospace,monospace}.notice{color:var(--muted);font-size:11px;line-height:1.5;border:1px solid rgba(157,121,255,.25);padding:12px;border-radius:12px}.notice strong{color:var(--violet)}@media(max-width:900px){.layout{grid-template-columns:1fr}.top{align-items:start;flex-direction:column}#topologyGraph{height:520px}}
</style></head><body><main><div class="top"><div><div class="eyebrow">HOLO / CONTINUITY TOPOLOGY</div><h1>Relations, not replacements.</h1><p class="sub">A verified projection of retained records and their explicit links.</p></div><nav><a href="/">OPERATOR CONSOLE</a><a href="/playground">PLAYGROUND</a></nav></div><div class="layout"><section class="panel"><div class="head"><h2>VERIFIED RECORD GRAPH</h2><div class="legend"><span class="continuity"><i></i>CONTINUITY</span><span class="correction"><i></i>CORRECTION</span><span class="revalidation"><i></i>REVALIDATION</span></div></div><svg id="topologyGraph" role="img" aria-label="Verified continuity topology"></svg></section><aside class="panel receipt"><div class="label">NODE RECEIPT</div><div class="state" id="graphState">VERIFYING</div><pre id="nodeReceipt">Select a node to inspect its exact retained record.</pre><div class="notice"><strong>OBSERVATIONAL ONLY.</strong> This graph projects verified stored relations. It grants no truth, acceptance, write, or execution authority.</div></aside></div></main><script>
const svg=document.getElementById('topologyGraph'),receipt=document.getElementById('nodeReceipt'),state=document.getElementById('graphState');const NS='http://www.w3.org/2000/svg';function el(tag,attrs={}){const x=document.createElementNS(NS,tag);Object.entries(attrs).forEach(([k,v])=>x.setAttribute(k,v));return x}function render(data){const nodes=data.nodes||[],edges=data.edges||[];svg.replaceChildren();state.textContent=data.verified?'VERIFIED':'UNVERIFIED';if(!nodes.length){receipt.textContent='Verified empty chain. No retained relations.';return}const size=Math.max(920,520+Math.sqrt(nodes.length)*105),c=size/2;svg.setAttribute('viewBox',`0 0 ${size} ${size}`);const pos=new Map();nodes.forEach((n,i)=>{const a=i*2.3999632297-Math.PI/2,r=nodes.length===1?0:95+Math.sqrt(i)*54;pos.set(n.idx,[c+Math.cos(a)*r,c+Math.sin(a)*r])});edges.forEach(e=>{const a=pos.get(e.source),b=pos.get(e.target);if(a&&b)svg.append(el('line',{x1:a[0],y1:a[1],x2:b[0],y2:b[1],class:`edge ${e.kind}`}))});nodes.forEach(n=>{const [x,y]=pos.get(n.idx),g=el('g',{class:`node ${n.kind}`,tabindex:'0',role:'button','aria-label':`${n.kind} ${n.idx}`});g.append(el('circle',{cx:x,cy:y,r:29}));const t=el('text',{x,y:y+4});t.textContent=`#${n.idx}`;g.append(t);const select=()=>{svg.querySelectorAll('.node').forEach(q=>q.classList.remove('selected'));g.classList.add('selected');receipt.textContent=JSON.stringify(n,null,2)};g.addEventListener('click',select);g.addEventListener('keydown',e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();select()}});svg.append(g)});receipt.textContent=JSON.stringify(nodes[nodes.length-1],null,2)}fetch('/api/topology',{cache:'no-store'}).then(r=>r.json().then(j=>{if(!r.ok)throw Error(j.error||`HTTP ${r.status}`);return j})).then(render).catch(e=>{state.textContent='UNAVAILABLE';state.style.color='var(--red)';receipt.textContent=e.message});
</script></body></html>'''


def build_idx_playground_receipt(
    frozen_idx: str,
    packet: dict[str, Any],
) -> dict[str, Any]:
    '''Build one non-authoritative, non-retained admission receipt.'''
    result = check_idx_packet(frozen_idx, packet)
    return {
        **result,
        "accepted": False,
        "truth_claimed": False,
        "write_authority": "NONE",
        "execution_authority": "NONE",
    }


def build_operator_snapshot(
    chain_path: str | Path = DEFAULT_CHAIN_FILE,
    *,
    timeline_limit: int = 100,
) -> dict[str, Any]:
    """Build one verified, read-only snapshot for the browser console."""
    if type(timeline_limit) is not int or isinstance(timeline_limit, bool):
        raise TypeError("timeline_limit must be a plain integer")
    if not 1 <= timeline_limit <= 1000:
        raise ValueError("timeline_limit must be between 1 and 1000")

    service = get_service(chain_path)
    status = service.status()
    timeline = service.replay_timeline()[-timeline_limit:]

    return {
        "type": "holo_operator_snapshot",
        "version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "service": status,
        "timeline": timeline,
        "accepted": False,
        "truth_claimed": False,
        "write_authority": "NONE",
        "execution_authority": "NONE",
    }


class _OperatorServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, address: tuple[str, int], chain_path: str | Path):
        self.chain_path = Path(chain_path)
        super().__init__(address, _OperatorHandler)


class _OperatorHandler(BaseHTTPRequestHandler):
    server: _OperatorServer

    def _send(self, status: int, content_type: str, body: bytes) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Content-Security-Policy", "default-src 'self'; style-src 'unsafe-inline'; script-src 'unsafe-inline'; connect-src 'self'")
        self.end_headers()
        self.wfile.write(body)

    def _json(self, status: int, value: Any) -> None:
        self._send(
            status,
            "application/json; charset=utf-8",
            json.dumps(value, ensure_ascii=False).encode("utf-8"),
        )

    def do_GET(self) -> None:  # noqa: N802 - stdlib handler API
        path = urlsplit(self.path).path
        if path == "/":
            self._send(200, "text/html; charset=utf-8", INDEX_HTML.encode("utf-8"))
            return
        if path == "/topology":
            self._send(200, "text/html; charset=utf-8", TOPOLOGY_HTML.encode("utf-8"))
            return

        if path == "/playground":
            self._send(
                200,
                "text/html; charset=utf-8",
                PLAYGROUND_HTML.encode("utf-8"),
            )
            return
        if path == "/healthz":
            self._json(200, {"status": "ok", "write_authority": "NONE"})
            return
        if path == "/api/topology":
            try:
                topology = build_continuity_topology(self.server.chain_path)
            except (OSError, UnicodeError, ValueError, TypeError) as exc:
                self._json(500, {
                    "status": "error",
                    "error": str(exc),
                    "accepted": False,
                    "truth_claimed": False,
                    "write_authority": "NONE",
                    "execution_authority": "NONE",
                })
                return
            self._json(200, topology)
            return

        if path == "/api/snapshot":
            try:
                self._json(200, build_operator_snapshot(self.server.chain_path))
            except Exception as error:
                self._json(
                    500,
                    {
                        "status": "error",
                        "error": str(error),
                        "accepted": False,
                        "write_authority": "NONE",
                        "execution_authority": "NONE",
                    },
                )
            return
        self._json(404, {"status": "not_found", "path": path})

    def do_POST(self) -> None:  # noqa: N802 - stdlib handler API
        path = urlsplit(self.path).path
        if path != "/api/idx-check":
            self._json(404, {"status": "not_found", "path": path})
            return

        error_receipt = {
            "status": "ERROR",
            "code": "IDX_REQUEST_INVALID",
            "accepted": False,
            "truth_claimed": False,
            "write_authority": "NONE",
            "execution_authority": "NONE",
        }

        try:
            content_type = self.headers.get("Content-Type", "").split(";", 1)[0]
            if content_type.strip().lower() != "application/json":
                raise ValueError("Content-Type must be application/json")

            raw_length = self.headers.get("Content-Length")
            if raw_length is None:
                raise ValueError("Content-Length is required")
            length = int(raw_length)
            if not 1 <= length <= 1_000_000:
                raise ValueError("request body must be between 1 and 1000000 bytes")

            request = json.loads(self.rfile.read(length).decode("utf-8"))
            if type(request) is not dict or set(request) != {"frozen_idx", "packet"}:
                raise ValueError(
                    "IDX request must contain only frozen_idx and packet"
                )
            if type(request["frozen_idx"]) is not str:
                raise TypeError("frozen_idx must be a string")
            if type(request["packet"]) is not dict:
                raise TypeError("packet must be an object")

            result = build_idx_playground_receipt(
                request["frozen_idx"],
                request["packet"],
            )
            self._json(400 if result["status"] == "ERROR" else 200, result)
        except (TypeError, ValueError, UnicodeError, json.JSONDecodeError) as error:
            self._json(400, {**error_receipt, "error": str(error)})

    def log_message(self, format: str, *args: Any) -> None:
        return


def serve_operator_console(
    chain_path: str | Path = DEFAULT_CHAIN_FILE,
    *,
    host: str = "127.0.0.1",
    port: int = 8765,
    open_browser: bool = True,
    initial_path: str = "/",
) -> int:
    """Serve the local read-only console until interrupted."""
    if host not in LOOPBACK_HOSTS:
        raise ValueError("operator console host must be loopback-only")
    if type(port) is not int or isinstance(port, bool) or not 0 <= port <= 65535:
        raise ValueError("port must be an integer between 0 and 65535")
    if initial_path not in {"/", "/playground", "/topology"}:
        raise ValueError("initial path must be a local console route")

    server = _OperatorServer((host, port), chain_path)
    actual_port = server.server_address[1]
    url_host = "127.0.0.1" if host in {"localhost", "::1"} else host
    url = f"http://{url_host}:{actual_port}"
    launch_url = url if initial_path == "/" else f"{url}{initial_path}"
    print(f"HOLO operator console: {launch_url}")
    print(f"Verified chain: {Path(chain_path)}")
    print("Read-only local surface. Press Ctrl+C to stop.")

    if open_browser:
        threading.Timer(0.15, webbrowser.open, args=(launch_url,)).start()

    try:
        server.serve_forever(poll_interval=0.25)
    except KeyboardInterrupt:
        print("\nHOLO operator console stopped.")
    finally:
        server.server_close()
    return 0
