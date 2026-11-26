"""Packaged, dependency-free EnvPath interface. All source/model text uses textContent."""

PAGE = r'''<!doctype html>
<html lang="en" data-theme="space"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>EnvPath · Local workspace</title>
<style nonce="__TOKEN__">
:root{--ink:#20382f;--muted:#687970;--paper:#f6f5ef;--line:#dfe4d9;--green:#285d47;--accent:#d9e8b0;--error:#a34332}*{box-sizing:border-box}body{margin:0;background:var(--paper);color:var(--ink);font:15px/1.5 system-ui,-apple-system,Segoe UI,sans-serif}button,input,textarea,select{font:inherit}button{cursor:pointer}button:disabled{opacity:.45;cursor:default}button:focus-visible,input:focus-visible,textarea:focus-visible,select:focus-visible{outline:3px solid #99b864;outline-offset:3px}button{border:1px solid var(--line);border-radius:10px;background:white;color:var(--ink);padding:9px 14px}button:hover:not(:disabled){background:#edf2e6}header{background:#18372c;color:#fff;padding:18px 30px;display:flex;align-items:center;justify-content:space-between;gap:20px}.brand{font-size:24px;font-weight:750;letter-spacing:-1px}.brand span{color:#cfdfab}.tag{font-size:12px;color:#c9d6cb;letter-spacing:.04em}.local{font-size:12px;border:1px solid #507160;padding:5px 10px;border-radius:20px}.intro{padding:24px 30px 20px;display:flex;justify-content:space-between;gap:24px;align-items:end}h1{font-size:30px;line-height:1.1;margin:0 0 8px;letter-spacing:-1px}p{margin:0}.sub{color:var(--muted)}#status{font-size:12px;text-align:right;max-width:380px;overflow-wrap:anywhere}.layout{display:grid;grid-template-columns:300px minmax(300px,1fr) 300px;gap:16px;padding:0 24px 24px;min-height:calc(100vh - 190px)}.panel{background:#fff;border:1px solid var(--line);border-radius:16px;overflow:hidden;display:flex;flex-direction:column;min-width:0}.panel-head{padding:18px 18px 14px;border-bottom:1px solid var(--line);display:flex;justify-content:space-between;align-items:center;gap:8px}.panel-head h2{font-size:15px;margin:0}.eyebrow{font-size:10px;letter-spacing:.14em;text-transform:uppercase;color:var(--muted);margin-bottom:3px}.small{font-size:12px;color:var(--muted)}.search{padding:16px;display:flex;gap:6px}input,textarea,select{border:1px solid var(--line);background:#fafbf7;border-radius:9px;padding:10px;color:var(--ink);max-width:100%}input{width:100%;min-width:0}.search button{padding:8px}#results{padding:0 16px 16px;max-height:32vh;overflow:auto}.source{width:100%;text-align:left;margin-bottom:8px;padding:12px;background:#f8faf5;border-radius:10px}.source strong{display:block;font-size:12px}.source .preview{display:block;font-size:12px;line-height:1.55;color:var(--muted);margin-top:6px;overflow-wrap:anywhere}#record{border-top:1px solid var(--line);padding:16px;overflow:auto;max-height:44vh}.record-title{font-size:13px;font-weight:700}.hash{font:10px/1.6 ui-monospace,monospace;overflow-wrap:anywhere;color:var(--muted)}pre{white-space:pre-wrap;overflow-wrap:anywhere;font:12px/1.6 ui-monospace,monospace;background:#f8faf5;border:1px solid var(--line);padding:12px;border-radius:8px}#record pre{max-height:250px;overflow:auto}.links{display:flex;flex-wrap:wrap;gap:6px}.links button{font-size:11px;padding:5px 7px}.chat{min-height:520px}#transcript{flex:1;padding:22px;overflow:auto;max-height:58vh}.welcome{max-width:430px;margin:50px auto;text-align:center}.compass{font-size:38px;color:var(--green);margin-bottom:12px}.welcome .small{margin-top:22px}.welcome h3{font-size:23px;letter-spacing:-.6px;margin:0 0 8px}.suggestions{display:flex;flex-wrap:wrap;justify-content:center;gap:8px;margin-top:24px}.suggestions button{font-size:12px}.message{margin:0 0 20px;max-width:100%;white-space:pre-wrap;overflow-wrap:anywhere}.message.user{background:#edf3e7;border:1px solid #dce7d3;margin-left:10%;border-radius:12px;padding:12px 15px}.message.assistant{padding:4px 0}.message .who{font-size:10px;letter-spacing:.12em;text-transform:uppercase;font-weight:750;color:var(--muted);margin-bottom:5px}.message.error{color:var(--error);border-left:3px solid var(--error);padding:8px 12px}.composer{border-top:1px solid var(--line);padding:16px}#message{resize:vertical;width:100%;min-height:90px;max-height:180px;display:block;background:white}.compose-actions{display:flex;justify-content:space-between;align-items:center;gap:12px;margin-top:10px}.primary{background:var(--green);color:white;border-color:var(--green)}.primary:hover:not(:disabled){background:#1c4935}.draft-body{padding:16px;display:flex;flex-direction:column;gap:12px}label{font-size:12px;font-weight:650}label select,label textarea{display:block;width:100%;margin-top:6px}#draft-content{resize:vertical;min-height:160px}#draft-target{padding:10px;border:1px dashed #b7c9aa;border-radius:8px;font-size:12px;overflow-wrap:anywhere}#draft-preview{max-height:180px;overflow:auto;margin:0}#tools{padding:0 16px 16px;overflow:auto;max-height:30vh}details{border:1px solid var(--line);border-radius:8px;padding:8px;margin:8px 0;font-size:12px}summary{cursor:pointer}details pre{max-height:170px;overflow:auto;font-size:11px}#notice{font-size:12px;color:var(--error);padding:0 30px 14px;min-height:18px}.draft-status{font-size:12px;color:var(--green)}.chat-head button{font-size:11px;padding:6px 9px}.footer{font-size:11px;color:var(--muted);padding:0 26px 16px}@media(max-width:1180px){.layout{grid-template-columns:260px minmax(300px,1fr)}.draft-panel{grid-column:1/-1}.draft-body{display:grid;grid-template-columns:1fr 1fr}.draft-body label:first-child{grid-column:1}.draft-body label:nth-child(2){grid-column:2;grid-row:1/4}#draft-content{min-height:130px}.draft-panel #tools{max-height:200px}}@media(max-width:720px){header{padding:16px 18px}.tag{display:none}.intro{padding:22px 18px;display:block}#status{text-align:left;margin-top:14px}.layout{padding:0 12px 16px;display:flex;flex-direction:column}.chat{order:0}.evidence{order:1}.draft-panel{order:2}.draft-body{display:flex}h1{font-size:26px}#transcript{max-height:55vh}.welcome{margin:28px auto}#notice{padding-left:18px}}

/* HOLO_APPEARANCE_OPTIONS_V1 */
:root[data-theme="space"] {color-scheme:dark;--ink:#e7e7e9;--muted:#a5a5ae;--paper:#030304;--line:#303037;--green:#b8c7d5;--accent:#b8c7d5;--error:#f29a90;--surface:#101013;--field:#19191e;--surface-hover:#25252c;--message:#1b1b22;--header:#08080a;--button-text:#030304}
:root[data-theme="light"] {color-scheme:light;--surface:#fff;--field:#fafbf7;--surface-hover:#edf2e6;--message:#edf3e7;--header:#18372c;--button-text:#fff}
body {background:var(--paper);color:var(--ink)}
header {background:var(--header)}
.panel,button {background:var(--surface);color:var(--ink)}
input,textarea,select,#message {background:var(--field);color:var(--ink)}
button:hover:not(:disabled) {background:var(--surface-hover)}
.source,pre {background:var(--field);color:var(--ink)}
.message.user {background:var(--message);border-color:var(--line)}
.primary {background:var(--green);border-color:var(--green);color:var(--button-text)}
.primary:hover:not(:disabled) {background:var(--green);filter:brightness(.9)}
:root[data-theme="space"] .brand span,:root[data-theme="space"] .compass {color:var(--green)}
:root[data-theme="space"] .tag,:root[data-theme="space"] .local {color:#c9c9cf}
:root[data-theme="space"] .local {border-color:#45454d}
:root[data-theme="space"] .draft-status {color:var(--green)}
:root[data-theme="space"] button:focus-visible,:root[data-theme="space"] input:focus-visible,:root[data-theme="space"] textarea:focus-visible,:root[data-theme="space"] select:focus-visible {outline-color:var(--green)}
.appearance-toggle {margin-left:auto}
.appearance-panel {position:fixed;z-index:20;right:16px;top:72px;width:min(340px,calc(100vw - 32px));padding:18px;border:1px solid var(--line);border-radius:14px;background:var(--surface);box-shadow:0 12px 42px #0008}
.appearance-panel[hidden] {display:none}
.appearance-panel h2 {margin:0 0 12px;font-size:18px}
.appearance-panel label {display:block;margin:12px 0}
.appearance-panel select,.appearance-panel input[type="color"] {display:block;width:100%;margin-top:6px}
.appearance-panel input[type="color"] {height:44px;padding:4px;cursor:pointer}
.appearance-actions {display:flex;gap:8px;justify-content:flex-end;margin-top:14px}
@media(max-width:720px){.appearance-panel{top:70px}}

/* HOLO_APPEARANCE_MOTION_V2 */
:root[data-theme="space"] body {background:#030304}
.appearance-panel input[type="range"] {display:block;width:100%;margin-top:8px;accent-color:var(--green)}
.appearance-panel select {width:100%}
.appearance-panel .motion-hint {margin-top:5px}
/* A quiet, fixed light field. Never covers the controls or catches clicks. */
body::before {content:"";position:fixed;inset:-45vmax;z-index:0;pointer-events:none;opacity:0;visibility:hidden;background:conic-gradient(from 0deg,transparent 0deg,#ff2d550d 22deg,transparent 45deg,#31e9ff14 68deg,transparent 90deg,#b26aff12 112deg,transparent 135deg,#ffb12b0c 158deg,transparent 180deg,#ff2d550d 202deg,transparent 225deg,#31e9ff14 248deg,transparent 270deg,#b26aff12 292deg,transparent 315deg,#ffb12b0c 338deg,transparent 360deg);mask-image:radial-gradient(ellipse at center,black 0%,transparent 65%);transform-origin:center;transition:opacity .25s}
:root[data-theme="space"][data-effect="kaleidoscope"] body::before {visibility:visible;opacity:.85;animation:holo-orbit var(--motion-period,24s) linear infinite}
/* RGB uses the same animated accent as the controls, over the theme's base color. */
:root[data-effect="rgb"] body {
  background-image:radial-gradient(ellipse at 50% 35%,
    color-mix(in srgb,var(--accent) 32%,var(--paper)),
    color-mix(in srgb,var(--accent) 12%,var(--paper)) 72%,var(--paper));
  background-attachment:fixed;
}
@keyframes holo-orbit {to {transform:rotate(360deg)}}
/* Keep foreground surfaces above the atmospheric effect. */
body>header,body>.intro,body>#notice,body>main,body>.footer,body>.appearance-panel {position:relative;z-index:1}
.appearance-panel {position:fixed!important;z-index:20!important}
@media(prefers-reduced-motion:reduce){:root[data-effect="kaleidoscope"] body::before {animation:none!important}}
/* HOLO_FRACTALS_V3: low-resolution canvas, behind the UI. */
#holo-fractal-field {position:fixed;inset:0;width:100%;height:100%;z-index:0;pointer-events:none;opacity:0;transition:opacity .25s;image-rendering:auto}
:root[data-theme="space"][data-effect="fractal"] #holo-fractal-field,
:root[data-theme="space"][data-effect="fractal-kaleidoscope"] #holo-fractal-field {opacity:1}
:root[data-effect="fractal"] body::before,:root[data-effect="fractal-kaleidoscope"] body::before {visibility:hidden;opacity:0;animation:none}
@media(prefers-reduced-motion:reduce){#holo-fractal-field{display:none!important}}

/* HOLO_BACKGROUND_VIEW_V1: hide workspace without removing its state. */
#workspace-reveal {position:fixed;top:12px;right:16px;z-index:40;background:rgba(12,12,16,.78);color:#f3f3f5;border:1px solid #52525b;border-radius:10px;padding:10px 14px}
#workspace-reveal[hidden] {display:none}
body>header,body>.intro,body>#notice,body>main,body>.footer {transition:transform .35s ease,opacity .35s ease}
body.background-view>header {transform:translateY(-110%);opacity:0;pointer-events:none}
body.background-view>.intro,body.background-view>#notice,body.background-view>main,body.background-view>.footer {transform:translateY(105vh);opacity:0;pointer-events:none}
body.background-view {overflow:hidden}
@media(prefers-reduced-motion:reduce){body>header,body>.intro,body>#notice,body>main,body>.footer{transition:none!important}}

.workspace-controls{display:flex;flex-wrap:wrap;align-items:center;gap:8px;padding:0 24px 12px}
.workspace-controls button[aria-pressed="true"]{border-color:var(--green)}
.workspace-controls button[aria-disabled="true"]{opacity:.55;cursor:default}
.layout{gap:0;grid-template-columns:var(--workspace-tracks,1fr 16px 2fr 16px 1fr)}
.layout>.panel{grid-column:auto;min-width:0}
.layout>[hidden],#workspace-resize-controls[hidden]{display:none!important}
.appearance-panel{max-height:calc(100dvh - 88px);overflow-y:auto}
.appearance-panel h3{font-size:14px;margin:0 0 8px}
.workspace-layout-options{border-bottom:1px solid var(--line);padding-bottom:12px;margin-bottom:12px}
#workspace-resize-controls{display:flex;align-items:center;gap:6px;margin-bottom:8px}
#workspace-resize-controls select{flex:1;min-width:0;margin:0}
.workspace-layout-options button,#workspace-resize-controls select{min-height:44px}
#workspace-resize-controls button{min-width:44px}
.workspace-divider{display:grid;place-items:center;min-width:0;cursor:col-resize;touch-action:none}
.workspace-divider::before{content:"";height:100%;width:2px;border-radius:2px;background:var(--line)}
.workspace-divider:hover::before,.workspace-divider:focus-visible::before{background:var(--green)}
.workspace-divider:focus-visible{outline:2px solid var(--green);outline-offset:-2px}
@media(min-width:1051px){.draft-body{display:flex}}
@media(max-width:1050px){
  .layout{display:block;padding:0 12px 16px;min-height:0}
  .workspace-controls{padding:0 12px 12px}
  .workspace-controls button{min-height:44px}
}
#workspace-scene{position:fixed;inset:0;width:100%;height:100%;pointer-events:none;z-index:0;background:#020309}
#workspace-scene[hidden]{display:none}
:root[data-background]:not([data-background="default"]) body::before{visibility:hidden;animation:none}
:root[data-background]:not([data-background="default"]) body{background-image:none}
:root[data-background]:not([data-background="default"]) #holo-fractal-field{display:none}
#games-panel{margin:0 24px 16px;padding:14px;background:var(--surface);border:1px solid var(--line);border-radius:16px}
.games-toolbar{display:flex;align-items:center;justify-content:space-between;gap:12px;margin-bottom:12px}
.games-toolbar h2{margin:0}
#games-player{display:block;border:0;width:100%;height:clamp(380px,70vh,820px);border-radius:8px}
#media-panel{margin:0 24px 16px;padding:clamp(14px,2vw,26px);background:var(--surface);border:1px solid var(--line);border-radius:16px}
#media-panel [hidden]{display:none!important}
.media-heading,.media-form,.media-player-caption,.media-links{display:flex;align-items:center;gap:12px}
.media-heading,.media-player-caption{justify-content:space-between}
.media-heading h2,.media-guide h3{margin:0}
.media-form{margin:14px 0 8px}
.media-form input{flex:1}
.media-form button{white-space:nowrap}
.media-links{flex-wrap:wrap;margin-bottom:12px;font-size:13px}
#media-panel a{color:var(--green)}
.media-grid{display:grid;grid-template-columns:minmax(0,1fr) minmax(210px,280px);gap:18px}
#media-player,#media-empty{width:100%;aspect-ratio:16/9;border:0;border-radius:10px;background:#08080c}
#media-empty{display:grid;place-content:center;justify-items:center;gap:12px;padding:12px;color:#c8c8d0;text-align:center}
.media-player-caption{flex-wrap:wrap;font-size:13px;margin-top:8px;overflow-wrap:anywhere}
.media-guide{padding:14px;border:1px solid var(--line);border-radius:10px;background:var(--field)}
.media-guide ul{margin:10px 0 0;padding:0;list-style:none;display:grid;gap:8px}
.media-guide #media-results:empty{display:none}
.media-guide #media-results{max-height:340px;overflow:auto;border-top:1px solid var(--line);padding-top:10px}
.media-result{display:grid;gap:4px;overflow-wrap:anywhere}
.media-play{text-align:left;display:grid;gap:3px;width:100%}
.media-result>a{justify-self:start;padding:4px 6px}
@media(max-width:720px){#media-panel{margin-inline:12px}.media-grid{grid-template-columns:1fr}.media-form{gap:6px}}
#projects-panel{margin:0 24px 16px;padding:clamp(14px,2vw,26px);background:var(--surface);border:1px solid var(--line);border-radius:16px}
.projects-heading,.projects-actions{display:flex;align-items:center;gap:10px;flex-wrap:wrap}
.projects-heading{justify-content:space-between;margin-bottom:14px}
.projects-heading h2,.projects-references h3{margin:0}
.projects-grid{display:grid;grid-template-columns:minmax(140px,230px) minmax(0,1fr);gap:18px}
.projects-sidebar,.projects-references section{background:var(--field);border:1px solid var(--line);border-radius:10px;padding:12px;min-width:0}
#projects-panel ul{list-style:none;margin:8px 0 0;padding:0;display:grid;gap:6px}
#project-list{max-height:55vh;overflow:auto}
#projects-panel li{display:flex;gap:6px;flex-wrap:wrap}
#projects-panel button{overflow-wrap:anywhere}
#project-list button{width:100%;text-align:left}
#project-list button[aria-current="true"]{border-color:var(--green)}
#project-form{display:grid;gap:12px}
#project-form label>input,#project-form label>textarea{display:block;width:100%;margin-top:5px}
#project-draft{resize:vertical}
.projects-references{display:grid;grid-template-columns:1fr 1fr;gap:10px}
.projects-references h3{font-size:14px;margin-bottom:8px}
.project-files{padding:12px;border:1px solid var(--line);border-radius:10px;background:var(--field)}
.project-files h3{font-size:14px;margin:0 0 8px}
#project-file-content{max-height:300px;overflow:auto;white-space:pre-wrap;overflow-wrap:anywhere}
#project-status{font-size:13px;color:var(--muted)}
@media(max-width:720px){#projects-panel{margin-inline:12px}.projects-grid,.projects-references{grid-template-columns:1fr}#project-list{max-height:25vh}}
#envpath-sidebar {position:fixed;inset:0 auto 0 0;width:188px;z-index:10;display:flex;flex-direction:column;align-items:stretch;gap:14px;padding:20px 14px;border-right:1px solid var(--line)}
#envpath-sidebar .local {align-self:flex-start;font-size:10px}
#envpath-sidebar nav,.sidebar-actions {display:flex;flex-direction:column;gap:6px}
.sidebar-actions {margin-top:auto}
#envpath-sidebar .appearance-toggle {margin:0}
#envpath-sidebar button {text-align:left}
#book-open {padding:10px 14px;border:1px solid var(--line);border-radius:10px;background:var(--surface);color:var(--ink);text-decoration:none;font-size:14px}
#book-open:hover {background:var(--surface-hover)}
#book-open:focus-visible {outline:2px solid var(--accent);outline-offset:2px}
#envpath-sidebar button[aria-current="page"] {border-color:var(--accent);background:var(--surface-hover)}
body {padding-left:188px}
body.background-view {padding-left:0}
body.background-view>#envpath-sidebar {transform:translateX(-110%)}
#workspace-home[hidden] {display:none}
#appearance-panel {inset:auto auto 16px 200px;max-height:calc(100dvh - 32px);overflow:auto}
@media(max-width:800px) {
  body {padding-left:0}
  #envpath-sidebar {position:sticky;top:0;inset-inline:auto;width:auto;gap:8px;padding:8px 12px;border-right:0;border-bottom:1px solid var(--line)}
  #envpath-sidebar nav,.sidebar-actions {flex-direction:row;flex-wrap:wrap}
  #envpath-sidebar .local {display:none}
  #appearance-panel {inset:12px 12px auto auto}
}
</style></head><body><canvas id="workspace-scene" aria-hidden="true" hidden></canvas><canvas id="holo-fractal-field" aria-hidden="true"></canvas>
<button id="workspace-reveal" type="button" aria-label="Show workspace" hidden>Show UI</button>
<header id="envpath-sidebar">
<div class="brand">Env<span>Path</span></div><span class="local">LOCAL · HOLO CONNECTED</span>
<nav aria-label="EnvPath sections"><button id="home-open" type="button" aria-current="page" aria-controls="workspace-home">Home</button>
<button id="projects-open" type="button" aria-controls="projects-panel" aria-expanded="false">Projects</button>
<a id="book-open" hidden target="_blank" rel="noopener noreferrer">Continuity Book ↗</a>
<button id="media-open" type="button" aria-controls="media-panel" aria-expanded="false">Media</button>
<button id="games-open" hidden type="button" aria-controls="games-panel" aria-expanded="false">Games</button>
</nav>
<div class="sidebar-actions"><button id="workspace-hide" type="button" aria-label="Hide workspace to view background">Hide UI</button><button id="appearance-toggle" class="appearance-toggle" type="button" aria-controls="appearance-panel" aria-expanded="false">Options</button></div>
</header>
<aside id="appearance-panel" class="appearance-panel" aria-label="Options" hidden>
<h2 id="options-heading" tabindex="-1">Options</h2>
<section class="workspace-layout-options" aria-labelledby="workspace-layout-heading">
<h3 id="workspace-layout-heading">Workspace layout</h3>
<div id="workspace-resize-controls" role="group" aria-label="Resize panes">
<select id="workspace-resize-edge" aria-label="Pane divider"></select>
<button id="workspace-smaller" type="button" aria-label="Move divider left">←</button>
<button id="workspace-larger" type="button" aria-label="Move divider right">→</button>
</div>
<button id="workspace-reset" type="button">Reset layout</button>
</section>
<h3>Appearance</h3>
<label for="appearance-theme">Theme<select id="appearance-theme"><option value="space">Black space</option><option value="light">Original light</option></select></label><label for="appearance-background">Background<select id="appearance-background"><option value="default">Theme default</option><option value="stars">Starfield</option><option value="black-hole">Black hole</option><option value="electric">Electric</option><option value="matrix">Matrix-style rain</option><option value="binary-matrix">Binary Matrix</option></select></label><label for="appearance-accent">Accent color<input id="appearance-accent" type="color" value="#b8c7d5"></label><label for="appearance-effect">Color motion<select id="appearance-effect"><option value="off">Off (static color)</option><option value="rgb">RGB cycle</option><option value="kaleidoscope">Kaleidoscope</option><option value="fractal">Fractal</option><option value="fractal-kaleidoscope">Fractal kaleidoscope</option></select></label><label for="appearance-brightness">Fractal brightness<input id="appearance-brightness" type="range" min="1" max="10" step="1" value="4"></label><label for="appearance-complexity">Fractal complexity<input id="appearance-complexity" type="range" min="1" max="10" step="1" value="4"></label><label for="appearance-speed">Motion speed<input id="appearance-speed" type="range" min="1" max="10" step="1" value="4"></label><p class="small motion-hint">Animation stays behind controls. Reduced-motion settings are respected.</p><p class="small">Preferences stay in this browser. No changes to retained evidence.</p><div class="appearance-actions"><button id="appearance-reset" type="button">Reset</button><button id="appearance-close" type="button">Close</button></div></aside>

<section class="intro"><div><h1>A place to continue.</h1><p class="sub">Find what was retained. Explore what comes next.</p></div><div id="status" role="status">Checking selected evidence…</div></section>
<div id="notice" role="alert"></div>
<main>
<section id="projects-panel" aria-labelledby="projects-heading" hidden>
<div class="projects-heading"><h2 id="projects-heading">Projects</h2><button id="projects-close" type="button">Close</button></div>
<div class="projects-grid">
<aside class="projects-sidebar" aria-label="Saved projects">
<button id="project-new" type="button">New project</button>
<ul id="project-list"></ul>
</aside>
<form id="project-form">
<label>Name<input id="project-name" maxlength="100" required></label>
<label>Next step<input id="project-next" maxlength="1000"></label>
<label>Working draft<textarea id="project-draft" maxlength="4000" rows="6"></textarea></label>
<div class="projects-actions">
<button id="project-capture-draft" type="button">Copy workspace draft</button>
<button id="project-open-draft" type="button">Open text in Draft</button>
</div>
<div class="projects-references">
<section><h3>Evidence</h3><button id="project-add-evidence" type="button">Add selected record</button><ul id="project-evidence"></ul></section>
<section><h3>Videos</h3><button id="project-add-video" type="button">Add current video</button><ul id="project-videos"></ul></section>
</div>
<section class="project-files" aria-labelledby="project-files-heading">
<h3 id="project-files-heading">Files</h3>
<button id="project-attach" type="button" disabled>Attach file</button>
<input id="project-file-picker" type="file" accept=".txt,.md" hidden>
<p class="small">Save the project first. UTF-8 .txt and .md, up to 24 KiB each.</p>
<ul id="project-files"></ul>
<div id="project-file-preview" hidden><strong id="project-file-title"></strong><pre id="project-file-content"></pre></div>
</section>
<div class="projects-actions"><button id="project-save" class="primary" type="submit">Save project</button><p id="project-status" role="status"></p></div>
</form>
</div>
</section>
<section id="media-panel" data-search-enabled="no" aria-labelledby="media-heading" hidden>
<div class="media-heading"><h2 id="media-heading">Media</h2><button id="media-close" type="button">Close</button></div>
<form id="media-search" class="media-form">
<input id="media-query" aria-label="Search YouTube or paste a video link" placeholder="Search YouTube or paste a video link" maxlength="240" required>
<button id="media-submit" type="submit">Search / Open</button>
</form>
<div class="media-links">
<p id="media-status" role="status"></p><a id="media-search-source" target="_blank" rel="noopener noreferrer" hidden>Search on YouTube ↗</a>
</div>
<div class="media-grid">
<div class="media-screen">
<div id="media-empty"><p>Choose a channel or open a YouTube video.</p><button id="media-resume" type="button" hidden>Reopen last video</button></div>
<iframe id="media-player" title="YouTube player" referrerpolicy="strict-origin-when-cross-origin" allow="encrypted-media; picture-in-picture; fullscreen" allowfullscreen hidden></iframe>
<div class="media-player-caption"><strong id="media-title"></strong><a id="media-watch-source" target="_blank" rel="noopener noreferrer" hidden>Watch on YouTube ↗</a></div>
</div>
<div class="media-guide">
<h3>Live TV</h3><ul id="media-channels"></ul>
<ul id="media-results" aria-label="YouTube search results"></ul>
</div>
</div>
</section>
<section id="games-panel" data-player-url="" aria-labelledby="games-heading" hidden>
<div class="games-toolbar"><h2 id="games-heading">Games</h2><button id="games-close" type="button">Hide player</button></div>
<iframe id="games-player" title="Nintendo 64 emulator" sandbox="allow-scripts allow-same-origin allow-downloads" allow="fullscreen; gamepad"></iframe>
</section>
<div id="workspace-home">
<div class="workspace-controls" role="group" aria-label="Workspace layout">
<button type="button" data-workspace-pane="evidence" aria-controls="workspace-evidence" aria-pressed="true">Evidence</button>
<button type="button" data-workspace-pane="chat" aria-controls="workspace-chat" aria-pressed="true">Chat</button>
<button type="button" data-workspace-pane="draft" aria-controls="workspace-draft" aria-pressed="true">Draft</button>
</div>
<div class="layout" id="workspace-layout">
<section class="panel evidence" id="workspace-evidence"><div class="panel-head"><div><div class="eyebrow">Retained evidence</div><h2>Find a record</h2></div><button id="refresh" aria-label="Refresh chain status">↻</button></div>
<form class="search" id="search-form"><input id="query" placeholder="Search retained words…" maxlength="200" aria-label="Search retained evidence" required><button type="submit">Find</button></form>
<div id="results"><p class="small">Search the selected HOLO chain. Original records and correction links stay visible.</p></div><div id="record" hidden></div></section>
<section class="panel chat" id="workspace-chat"><div class="panel-head chat-head"><div><div class="eyebrow">Local conversation</div><h2>Workspace chat</h2></div><button id="new-chat">New chat</button></div>
<div id="transcript" role="log" aria-label="Chat transcript"><div id="welcome" class="welcome"><div class="compass" aria-hidden="true">↗</div><h3>Start with a question.</h3><p class="sub">Ask about retained evidence, explore an idea, or prepare a note for review.</p><div class="suggestions"><button data-prompt="Find retained records about continuity and show their correction links.">Find continuity evidence</button><button data-prompt="Help me prepare a short note about an idea I want to explore.">Explore an idea</button></div><p class="small">Chat uses your local Ollama model.<br>Search and draft export work independently.</p></div></div>
<form id="chat-form" class="composer"><textarea id="message" maxlength="4000" placeholder="What would you like to work on?" aria-label="Your message" required></textarea><div class="compose-actions"><span id="turn-status" class="small" role="status">Ready</span><div><button id="stop" type="button" disabled>Stop</button> <button id="send" type="submit" class="primary">Send ↗</button></div></div></form></section>
<section class="panel draft-panel" id="workspace-draft"><div class="panel-head"><div><div class="eyebrow">Before persistence</div><h2>Draft for review</h2></div></div><div class="draft-body">
<label>Draft type<select id="draft-kind"><option value="note">New note</option><option value="correction">Correction proposal</option></select></label>
<label>Content<textarea id="draft-content" maxlength="4000" placeholder="Write a note, or propose a correction…"></textarea></label>
<div id="draft-target" hidden>Open an original record, then select “Use as target.”</div>
<button id="prepare">Prepare draft</button><p class="small">Preparation and download do not add to retained memory. Review and persistence remain separate.</p><div id="draft-status" class="draft-status" role="status"></div><pre id="draft-preview" hidden></pre><button id="download" disabled>Download proposal JSON</button></div>
<div class="panel-head"><h2>Tool activity</h2><span class="small">This chat</span></div><div id="tools"><p class="small">Actual tool results appear here.</p></div></section>
</div></div></main><div class="footer">Retained evidence is historical. Chat is model output. Drafts are proposals. None grants authority.</div>
<script nonce="__TOKEN__">
'use strict';
const $=id=>document.getElementById(id),token='__TOKEN__';let history=[],turn=null,target=null,draft=null,stopped=false;
function notice(text=''){$('notice').textContent=text}
async function api(route,data){const response=await fetch('/api/'+route,{method:'POST',headers:{'Content-Type':'application/json','X-EnvPath-Token':token},body:JSON.stringify(data)});const result=await response.json();if(!response.ok)throw Error(result.error||'Request failed');return result}
function el(tag,text,cls){const e=document.createElement(tag);if(text!==undefined)e.textContent=text;if(cls)e.className=cls;return e}
function busy(on){$('send').disabled=on;$('stop').disabled=!on;$('new-chat').disabled=on;$('turn-status').textContent=on?'Working locally…':'Ready'}
async function status(){try{const s=await api('status',{});$('status').replaceChildren(el('div',s.entries?s.entries+' retained records · chain intact':'No retained records yet'),el('div','Model: '+s.model,'small'));$('status').title=s.chain_file+'\nHead: '+(s.head_hash||'empty');notice()}catch(e){$('status').textContent='Evidence unavailable';notice(e.message)}}
async function search(query){const r=await api('search',{query});$('results').replaceChildren(el('p',r.total_matches+' matches'+(r.results_truncated?' · showing first 12':''),'small'));for(const n of r.matches){const b=el('button',undefined,'source');b.append(el('strong','#'+n.idx+' · '+n.kind),el('span',n.preview+(n.preview_truncated?' … [preview only]':''),'preview'));b.onclick=()=>read(n.idx,n.hash).catch(e=>notice(e.message));$('results').append(b)}if(!r.matches.length)$('results').append(el('p','No match. Try another word.','small'));return r}
async function read(idx,record_hash){const r=await api('read',{idx,record_hash});showRecord(r);return r}
function showRecord(r){const n=r.record;selectedProjectRecord={idx:n.idx,hash:n.hash};$('record').hidden=false;$('record').replaceChildren(el('div','#'+n.idx+' · '+n.kind,'record-title'),el('div',n.hash,'hash'),el('pre',JSON.stringify(n.content,null,2)));if(n.kind==='record'){const b=el('button','Use as correction target');b.onclick=()=>{target={idx:n.idx,hash:n.hash};$('draft-kind').value='correction';syncTarget();invalidateDraft()};$('record').append(b)}if(r.links.length){$('record').append(el('p','Correction / revalidation links','small'));const box=el('div',undefined,'links');for(const related of r.related||[]){const b=el('button','#'+related.idx+' · '+related.kind);b.onclick=()=>read(related.idx,related.hash).catch(e=>notice(e.message));box.append(b)}$('record').append(box)}else $('record').append(el('p','No recorded correction or revalidation links.','small'))}
function syncTarget(){$('draft-target').hidden=$('draft-kind').value!=='correction';$('draft-target').textContent=target?'Target #'+target.idx+' · '+target.hash:'Open an original record, then select “Use as target.”'}
function invalidateDraft(){draft=null;$('download').disabled=true;$('draft-preview').hidden=true;$('draft-status').textContent=''}
function showDraft(value){draft=value;$('draft-preview').hidden=false;$('draft-preview').textContent=JSON.stringify(value,null,2);$('download').disabled=false;$('draft-status').textContent='Proposal ready for review · not persisted';$('draft-content').value=value.content;$('draft-kind').value=value.kind;target=value.target;syncTarget()}
function message(role,text){$('welcome')?.remove();const box=el('div',undefined,'message '+role);box.append(el('div',role==='user'?'You':role==='error'?'Turn incomplete':'EnvPath','who'));const body=el('div',text);box.append(body);$('transcript').append(box);$('transcript').scrollTop=$('transcript').scrollHeight;return body}
function toolEvent(event){const d=el('details');d.append(el('summary',event.name+(event.result.error?' · failed':' · returned')),el('pre',JSON.stringify(event.result,null,2)));$('tools').append(d);if(event.name==='prepare_draft'&&!event.result.error)showDraft(event.result)}
$('search-form').onsubmit=async e=>{e.preventDefault();try{notice();await search($('query').value)}catch(err){notice(err.message)}};
$('refresh').onclick=status;$('draft-kind').onchange=()=>{syncTarget();invalidateDraft()};$('draft-content').oninput=invalidateDraft;
$('prepare').onclick=async()=>{try{notice();const data={kind:$('draft-kind').value,content:$('draft-content').value};if(data.kind==='correction'){if(!target)throw Error('Open an original record and choose a correction target first.');data.target_idx=target.idx;data.target_hash=target.hash}showDraft(await api('draft',data))}catch(e){invalidateDraft();notice(e.message)}};
$('download').onclick=()=>{if(!draft)return;const blob=new Blob([JSON.stringify(draft,null,2)+'\n'],{type:'application/json'});const url=URL.createObjectURL(blob);const a=el('a');a.href=url;a.download='envpath-'+draft.kind+'-proposal.json';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000)};
$('stop').onclick=async()=>{if(!turn)return;stopped=true;$('turn-status').textContent='Stopping…';try{await api('cancel',{turn_id:turn})}catch(e){notice(e.message)}};
$('new-chat').onclick=()=>{history=[];$('transcript').replaceChildren();$('tools').replaceChildren(el('p','Actual tool results appear here.','small'));invalidateDraft();$('turn-status').textContent='New chat · history cleared'};
document.querySelectorAll('[data-prompt]').forEach(b=>b.onclick=()=>{$('message').value=b.dataset.prompt;$('message').focus()});
$('message').onkeydown=e=>{if(e.key==='Enter'&&(e.ctrlKey||e.metaKey)){e.preventDefault();if(!turn)$('chat-form').requestSubmit()}};
$('chat-form').onsubmit=async e=>{e.preventDefault();if(turn)return;const prompt=$('message').value.trim();if(!prompt)return;notice();message('user',prompt);const output=message('assistant','');turn=crypto.randomUUID();stopped=false;busy(true);let completed=false,cancelled=false;
try{const response=await fetch('/api/chat',{method:'POST',headers:{'Content-Type':'application/json','X-EnvPath-Token':token},body:JSON.stringify({message:prompt,history,turn_id:turn})});if(!response.ok){const failure=await response.json();throw Error(failure.error||'Chat unavailable')}const reader=response.body.getReader(),decoder=new TextDecoder();let buffer='';while(true){const chunk=await reader.read();buffer+=decoder.decode(chunk.value||new Uint8Array(),{stream:!chunk.done});let at;while((at=buffer.indexOf('\n'))>=0){const line=buffer.slice(0,at);buffer=buffer.slice(at+1);if(!line)continue;const event=JSON.parse(line);if(event.event==='delta'){output.textContent+=event.text;$('transcript').scrollTop=$('transcript').scrollHeight}if(event.event==='tool')toolEvent(event);if(event.event==='error')throw Error(event.message);if(event.event==='cancelled'){cancelled=true;$('turn-status').textContent='Stopped · partial answer excluded from history'}if(event.event==='done'){completed=true;output.textContent=event.answer}}if(chunk.done)break}if(completed&&!stopped){history.push({role:'user',content:prompt},{role:'assistant',content:output.textContent});while(history.length>12||new TextEncoder().encode(JSON.stringify(history)).length>24000)history.splice(0,2);$('message').value=''}else if(cancelled||stopped){message('error','Stopped. Any partial text above is incomplete and was not added to chat history.')}else throw Error('Stream ended without a completed answer');
}catch(err){invalidateDraft();message('error',err.message);notice(err.message)}finally{turn=null;busy(false);if(!completed||stopped)$('turn-status').textContent=stopped?'Stopped':'Turn incomplete'}};

// Appearance preferences are local UI state, not HOLO evidence or authority.
// Appearance preferences are local presentation state, never retained HOLO evidence.
const appearanceKey='envpath.appearance.v1';
const appearanceDefaults={theme:'space',accent:'#b8c7d5',effect:'off',speed:4,brightness:4,complexity:4,background:'default'};
const backgroundScenes=['default','stars','black-hole','electric','matrix','binary-matrix'];
const motionEffects=['off','rgb','kaleidoscope','fractal','fractal-kaleidoscope'];
const reducedMotion=window.matchMedia('(prefers-reduced-motion: reduce)');
let appearance={...appearanceDefaults},motionFrame=0,lastMotionFrame=0,fractalFrame=0,lastFractalFrame=0;
function validAccent(v){return typeof v==='string'&&/^#[0-9a-fA-F]{6}$/.test(v)}
function readAppearance(){try{const p=JSON.parse(localStorage.getItem(appearanceKey));return {background:backgroundScenes.includes(p?.background)?p.background:'default',theme:p&&p.theme==='light'?'light':'space',accent:p&&validAccent(p.accent)?p.accent:appearanceDefaults.accent,effect:p&&motionEffects.includes(p.effect)?p.effect:'off',speed:p&&Number.isInteger(p.speed)&&p.speed>=1&&p.speed<=10?p.speed:4,brightness:p&&Number.isInteger(p.brightness)&&p.brightness>=1&&p.brightness<=10?p.brightness:4,complexity:p&&Number.isInteger(p.complexity)&&p.complexity>=1&&p.complexity<=10?p.complexity:4}}catch(_){return {...appearanceDefaults}}}
function setAccent(value){document.documentElement.style.setProperty('--green',value);document.documentElement.style.setProperty('--accent',value)}
const sceneCanvas = $('workspace-scene');
const sceneContext = sceneCanvas.getContext('2d');
const sceneGlyphs = '01電星光影界空';
const sceneStars = Array.from({length: 360}, (_, index) => {
  const sample = offset => {
    const value = Math.sin((index + 1) * 127.1 + offset * 311.7) * 43758.5453;
    return value - Math.floor(value);
  };
  return [sample(1), sample(2), sample(3), sample(4)];
});

function drawStars(ctx, width, height, time) {
  const cloud = ctx.createRadialGradient(width * .53, height * .44, 0, width * .53, height * .44, width * .52);
  cloud.addColorStop(0, '#172441');
  cloud.addColorStop(.48, '#080e20');
  cloud.addColorStop(1, '#020309');
  ctx.fillStyle = cloud;
  ctx.fillRect(0, 0, width, height);
  for (const [x, y, depth, phase] of sceneStars) {
    ctx.fillStyle = phase > .77 ? '#f5c9a2' : '#c3dbff';
    ctx.globalAlpha = (.24 + depth * .7) * (.84 + .16 * Math.cos(time * 1.4 + phase * 18));
    const size = .65 + depth ** 5 * 1.9;
    ctx.fillRect(x * width, y * height, size, size);
  }
  ctx.globalAlpha = 1;
}

function drawBlackHole(ctx, width, height, time, accent) {
  ctx.save();
  ctx.translate(width * .52, height * .48);
  ctx.rotate(-.22);
  const radius = Math.min(width, height) * .16;
  const glow = ctx.createRadialGradient(0, 0, radius * .7, 0, 0, radius * 3);
  glow.addColorStop(0, accent);
  glow.addColorStop(1, 'transparent');
  ctx.globalAlpha = .24;
  ctx.fillStyle = glow;
  ctx.fillRect(-radius * 3, -radius * 3, radius * 6, radius * 6);

  ctx.strokeStyle = accent;
  for (let band = 0; band < 15; band++) {
    const distance = radius * (1.35 + band * .115);
    ctx.globalAlpha = .22 + .13 * Math.cos(band * .7 + time);
    ctx.lineWidth = Math.max(1, radius * .075);
    ctx.beginPath();
    ctx.ellipse(0, 0, distance, distance * .28, 0, 0, Math.PI * 2);
    ctx.stroke();
  }
  ctx.globalAlpha = 1;
  ctx.fillStyle = '#000';
  ctx.lineWidth = Math.max(1, radius * .034);
  ctx.beginPath();
  ctx.arc(0, 0, radius, 0, Math.PI * 2);
  ctx.fill();
  ctx.stroke();

  for (let band = 0; band < 11; band++) {
    const distance = radius * (1.42 + band * .1);
    ctx.globalAlpha = .47 + .27 * Math.cos(band * .53 + time);
    ctx.lineWidth = Math.max(1, radius * .055);
    ctx.beginPath();
    ctx.ellipse(0, 0, distance, distance * .28, 0, .02, Math.PI - .02);
    ctx.stroke();
  }
  ctx.restore();
}

function drawElectric(ctx, width, height, time, accent) {
  ctx.fillStyle = '#040611';
  ctx.fillRect(0, 0, width, height);
  ctx.strokeStyle = accent;
  ctx.shadowColor = accent;
  ctx.shadowBlur = 14;
  for (let strand = 0; strand < 7; strand++) {
    ctx.globalAlpha = strand === 0 ? .9 : .34;
    ctx.lineWidth = strand === 0 ? 2.3 : 1;
    ctx.beginPath();
    ctx.moveTo(0, height * (.36 + strand * .045));
    for (let step = 1; step <= 48; step++) {
      const x = step / 48;
      const wave = Math.sin(x * 15 + time * .9 + strand) * .095;
      const spark = Math.sin(step * 27.7 + strand * 13 + time * 2.2) * .035;
      const spread = Math.sin(x * Math.PI) * strand * .045;
      ctx.lineTo(x * width, height * (.39 + spread + wave + spark));
    }
    ctx.stroke();
  }
  ctx.globalAlpha = 1;
  ctx.shadowBlur = 0;
}

function drawMatrix(ctx, width, height, time, hue, binary) {
  ctx.save();
  ctx.fillStyle = '#020905';
  ctx.fillRect(0, 0, width, height);
  const columnWidth = binary ? Math.min(16, width / continuityBytes.length) : 16;
  const rowHeight = binary ? Math.min(17, height / 9) : 17;
  if (binary) ctx.textBaseline = 'top';
  ctx.font = '300 ' + Math.min(12, rowHeight, columnWidth) + 'px ui-monospace, monospace';
  for (let column = 0; column * columnWidth < width; column++) {
    const [seed, phase] = sceneStars[column];
    const head = (Math.floor(time * (4 + seed * 8) + phase * 100) % (Math.ceil(height / 17) + 15));
    const streamHue = hue === null ? 143 : (hue + phase * 150) % 360;
    const headColor = 'hsl(' + streamHue + ' 92% 88%)';
    const tailColor = 'hsl(' + streamHue + ' 90% 55%)';
    if (binary) {
      const bits = continuityBytes[column % continuityBytes.length];
      const travel = height - rowHeight * bits.length;
      const top = ((phase + time * (.13 + seed * .13)) % 1) * travel;
      for (let row = 0; row < bits.length; row++) {
        ctx.fillStyle = row === bits.length - 1 ? headColor : tailColor;
        ctx.globalAlpha = .48 + row * .055;
        ctx.fillText(bits[row], column * columnWidth, top + row * rowHeight, Math.min(8, columnWidth));
      }
      continue;
    }
    for (let trail = 0; trail < 15; trail++) {
      ctx.fillStyle = trail === 0 ? headColor : tailColor;
      ctx.globalAlpha = (1 - trail / 15) * .8;
      const glyph = (column * 7 + head * 3 + trail * 5) % sceneGlyphs.length;
      ctx.fillText(sceneGlyphs[glyph], column * columnWidth, (head - trail) * 17, 8);
    }
  }
  ctx.restore();
}

const continuityBytes = Array.from(new TextEncoder().encode('Holo/Sim Continuity Engine'),
  byte => byte.toString(2).padStart(8, '0'));

function drawScene(time, accent, hue = null) {
  if (!sceneContext || appearance.background === 'default') return;
  const scale = Math.min(1, 820 / window.innerWidth, 500 / window.innerHeight);
  const width = Math.max(1, Math.round(window.innerWidth * scale));
  const height = Math.max(1, Math.round(window.innerHeight * scale));
  if (sceneCanvas.width !== width || sceneCanvas.height !== height) {
    sceneCanvas.width = width;
    sceneCanvas.height = height;
  }
  const seconds = time * (.35 + appearance.speed * .16) / 1000;
  if (appearance.background === 'electric') drawElectric(sceneContext, width, height, seconds, accent);
  else if (appearance.background === 'matrix' || appearance.background === 'binary-matrix') {
    drawMatrix(sceneContext, width, height, seconds, hue, appearance.background === 'binary-matrix');
  }
  else {
    drawStars(sceneContext, width, height, seconds);
    if (appearance.background === 'black-hole') drawBlackHole(sceneContext, width, height, seconds, accent);
  }
}

function animateAppearance(time) {
  const cycle = ['rgb', 'kaleidoscope'].includes(appearance.effect);
  if (time - lastMotionFrame >= 40) {
    const period = (50 - appearance.speed * 4) * 1000;
    const hue = (time % period) / period * 360;
    const accent = cycle ? 'hsl(' + hue.toFixed(1) + ' 95% 72%)' : appearance.accent;
    if (cycle) setAccent(accent);
    drawScene(time, accent, appearance.effect === 'rgb' ? hue : null);
    lastMotionFrame = time;
  }
  motionFrame = requestAnimationFrame(animateAppearance);
}
// Draw a bounded Julia-set approximation into a small canvas. No network or writes.
const fractalCanvas=$('holo-fractal-field');
const fractalContext=fractalCanvas.getContext('2d',{alpha:true});
function renderFractal(time){
  if(!fractalContext)return;
  const w=192,h=108;
  if(fractalCanvas.width!==w||fractalCanvas.height!==h){fractalCanvas.width=w;fractalCanvas.height=h}
  const pixels=fractalContext.createImageData(w,h);
  const maxIterations=12+appearance.complexity*5;
  const t=time*0.00004*(0.4+appearance.speed*0.16);
  const zoom=1.15+0.24*Math.sin(t*0.7);
  const cr=-0.745+0.065*Math.cos(t),ci=0.19+0.065*Math.sin(t*0.73);
  const mirrored=appearance.effect==='fractal-kaleidoscope';
  const sectors=8;
  const exposure=appearance.brightness/10;
  for(let y=0;y<h;y++)for(let x=0;x<w;x++){
    let nx=(x-w/2)/(h*0.5)*zoom,ny=(y-h/2)/(h*0.5)*zoom;
    if(mirrored){
      const r=Math.hypot(nx,ny),sector=Math.PI*2/sectors;
      let a=(Math.atan2(ny,nx)+t*0.18)%sector;
      if(a<0)a+=sector;
      a=Math.min(a,sector-a);
      nx=r*Math.cos(a);ny=r*Math.sin(a);
      nx-=0.5;
    }
    let zx=nx,zy=ny,i=0;
    for(;i<maxIterations&&zx*zx+zy*zy<16;i++){
      const next=zx*zx-zy*zy+cr;
      zy=2*zx*zy+ci;zx=next;
    }
    const idx=(y*w+x)*4;
    if(i===maxIterations)continue;
    const band=Math.sin(i*0.23+t*0.5)*0.5+0.5;
    const intensity=Math.min(1,(0.15+0.85*band)*exposure*0.65);
    const hue=(i*9+t*30)%360;
    // Three phase-shifted channels give restrained RGB highlights on black.
    pixels.data[idx]=Math.round((0.5+0.5*Math.sin(hue*Math.PI/180))*255*intensity);
    pixels.data[idx+1]=Math.round((0.5+0.5*Math.sin((hue+120)*Math.PI/180))*255*intensity);
    pixels.data[idx+2]=Math.round((0.5+0.5*Math.sin((hue+240)*Math.PI/180))*255*intensity);
    pixels.data[idx+3]=200;
  }
  fractalContext.putImageData(pixels,0,0);
}
function animateFractal(time){
  if(!['fractal','fractal-kaleidoscope'].includes(appearance.effect)||reducedMotion.matches||document.hidden){fractalFrame=0;return}
  if(time-lastFractalFrame>=90){renderFractal(time);lastFractalFrame=time}
  fractalFrame=requestAnimationFrame(animateFractal);
}
function syncMotion(){
  if(motionFrame){cancelAnimationFrame(motionFrame);motionFrame=0}
  if(fractalFrame){cancelAnimationFrame(fractalFrame);fractalFrame=0}
  const canAnimate=!reducedMotion.matches&&!document.hidden;
  const active=canAnimate&&appearance.effect!=='off';
  const hasScene=appearance.background!=='default';
  document.documentElement.dataset.background=appearance.background;
  sceneCanvas.hidden=!hasScene;
  document.documentElement.dataset.effect=active?appearance.effect:'off';
  document.documentElement.style.setProperty('--motion-period',(50-appearance.speed*4)+'s');
  setAccent(appearance.accent);
  lastMotionFrame=0;
  if(!document.hidden)drawScene(0,appearance.accent);
  const animateScene=hasScene&&sceneContext;
  if(canAnimate&&(animateScene||['rgb','kaleidoscope'].includes(appearance.effect)))motionFrame=requestAnimationFrame(animateAppearance);
  lastFractalFrame=0;
  if(!hasScene&&active&&['fractal','fractal-kaleidoscope'].includes(appearance.effect)&&appearance.theme==='space'&&!document.hidden&&fractalContext)fractalFrame=requestAnimationFrame(animateFractal);
}
function applyAppearance(p){
  appearance={...p};
  document.documentElement.dataset.theme=p.theme;
  $('appearance-theme').value=p.theme;
  $('appearance-background').value=p.background;
  $('appearance-accent').value=p.accent;
  $('appearance-effect').value=p.effect;
  $('appearance-speed').value=String(p.speed);
  $('appearance-brightness').value=String(p.brightness);
  $('appearance-complexity').value=String(p.complexity);
  syncMotion();
}
function saveAppearance(p){applyAppearance(p);try{localStorage.setItem(appearanceKey,JSON.stringify(p))}catch(_){/* UI remains usable without storage */}}
function updateAppearance(changes){saveAppearance({...appearance,...changes})}
function toggleAppearance(open) {
  $('appearance-toggle').setAttribute('aria-expanded', String(open));
  if (!open && $('appearance-panel').contains(document.activeElement)) $('appearance-toggle').focus();
  $('appearance-panel').hidden = !open;
  if (open) $('options-heading').focus();
}
$('appearance-toggle').onclick=()=>toggleAppearance($('appearance-panel').hidden);
$('appearance-close').onclick=()=>toggleAppearance(false);
$('appearance-theme').onchange=()=>updateAppearance({theme:$('appearance-theme').value});
$('appearance-accent').oninput=()=>updateAppearance({accent:$('appearance-accent').value});
$('appearance-effect').onchange=()=>updateAppearance({effect:$('appearance-effect').value});
$('appearance-speed').oninput=()=>updateAppearance({speed:Number($('appearance-speed').value)});
$('appearance-brightness').oninput=()=>updateAppearance({brightness:Number($('appearance-brightness').value)});
$('appearance-complexity').oninput=()=>updateAppearance({complexity:Number($('appearance-complexity').value)});
$('appearance-background').onchange=()=>updateAppearance({background:$('appearance-background').value});
document.addEventListener('visibilitychange',syncMotion);
window.addEventListener('resize', () => {
  if (!document.hidden && reducedMotion.matches) drawScene(0, appearance.accent);
});
$('appearance-reset').onclick=()=>{applyAppearance({...appearanceDefaults});try{localStorage.removeItem(appearanceKey)}catch(_){}};
document.addEventListener('keydown',e=>{if(e.key==='Escape'&&!$('appearance-panel').hidden)toggleAppearance(false)});
if(reducedMotion.addEventListener)reducedMotion.addEventListener('change',syncMotion);
else if(reducedMotion.addListener)reducedMotion.addListener(syncMotion);

function setBackgroundView(hidden){
  const workspaceRegions = document.querySelectorAll('body > header, body > .intro, body > #notice, body > main, body > .footer');
  if (hidden) {
    toggleAppearance(false);
    $('workspace-reveal').hidden = false;
    $('workspace-reveal').focus();
  }
  for (const region of workspaceRegions) region.inert = hidden;
  document.body.classList.toggle('background-view', hidden);
  $('workspace-hide').setAttribute('aria-pressed', String(hidden));
  if (!hidden) {
    $('workspace-hide').focus();
    $('workspace-reveal').hidden = true;
  }
}
$('workspace-hide').onclick=()=>setBackgroundView(true);
$('workspace-reveal').onclick=()=>setBackgroundView(false);
document.addEventListener('keydown',e=>{
  if(e.defaultPrevented||e.altKey||e.ctrlKey||e.metaKey||e.repeat||e.key.toLowerCase()!=='h')return;
  const t=e.target;
  if(t&&(t.isContentEditable||t.closest('input,textarea,select,[contenteditable="true"]')))return;
  e.preventDefault();setBackgroundView(!document.body.classList.contains('background-view'));
});
const layoutKey = 'envpath.layout.v1';
const workspacePanes = ['evidence', 'chat', 'draft'];
const workspaceLabels = {evidence: 'Evidence', chat: 'Chat', draft: 'Draft'};
const compactWorkspace = window.matchMedia('(max-width: 1050px)');
const layoutContainer = $('workspace-layout');
const resizeEdge = $('workspace-resize-edge');
const minimumShare = 18;

function defaultWorkspace() {
  return {version: 1, sizes: {evidence: 25, chat: 50, draft: 25}, visible: [...workspacePanes], active: 'chat'};
}

function readWorkspace() {
  try {
    const saved = JSON.parse(localStorage.getItem(layoutKey));
    if (saved?.version !== 1) return defaultWorkspace();
    const visible = workspacePanes.filter(id => Array.isArray(saved.visible) && saved.visible.includes(id));
    const shares = workspacePanes.map(id => saved.sizes?.[id]);
    if (!visible.length || shares.some(value => !Number.isFinite(value) || value < minimumShare) ||
        Math.abs(shares.reduce((sum, value) => sum + value, 0) - 100) > 0.01 ||
        !workspacePanes.includes(saved.active)) return defaultWorkspace();
    return {version: 1, sizes: Object.fromEntries(workspacePanes.map((id, i) => [id, shares[i]])),
            visible, active: saved.active};
  } catch (_) {
    return defaultWorkspace();
  }
}

let workspace = readWorkspace();
const workspaceButtons = [...document.querySelectorAll('[data-workspace-pane]')];
const workspaceDividers = workspacePanes.slice(0, -1).map(id => {
  const divider = el('div', undefined, 'workspace-divider');
  divider.tabIndex = 0;
  divider.setAttribute('role', 'separator');
  divider.setAttribute('aria-orientation', 'vertical');
  $('workspace-' + id).after(divider);
  return divider;
});

function saveWorkspace() {
  try { localStorage.setItem(layoutKey, JSON.stringify(workspace)); } catch (_) { /* Layout still works in memory. */ }
}

function updateWorkspaceSizes() {
  const visible = workspace.visible;
  const tracks = visible.map(id => 'minmax(0,' + workspace.sizes[id] + 'fr)');
  layoutContainer.style.setProperty('--workspace-tracks', tracks.join(' 16px '));
  workspaceDividers.forEach((divider, index) => {
    const left = workspacePanes[index];
    const right = visible[visible.indexOf(left) + 1];
    if (divider.hidden || !right) return;
    const total = workspace.sizes[left] + workspace.sizes[right];
    divider.setAttribute('aria-valuemin', String(minimumShare));
    divider.setAttribute('aria-valuetext', Math.round(100 * workspace.sizes[left] / visible.reduce((sum, id) => sum + workspace.sizes[id], 0)) + '% of available pane space');
    divider.setAttribute('aria-valuemax', String(Math.floor(total - minimumShare)));
    divider.setAttribute('aria-valuenow', String(Math.floor(workspace.sizes[left])));
  });
  const left = resizeEdge.value;
  const right = visible[visible.indexOf(left) + 1];
  for (const [button, pane] of [[$('workspace-smaller'), left], [$('workspace-larger'), right]]) {
    const disabled = !left || workspace.sizes[pane] <= minimumShare + 0.001;
    if (disabled && document.activeElement === button) resizeEdge.focus();
    button.disabled = disabled;
  }
}

function renderWorkspace() {
  const compact = compactWorkspace.matches;
  const shown = compact ? [workspace.active] : workspace.visible;
  for (const button of workspaceButtons) {
    const id = button.dataset.workspacePane;
    const visible = shown.includes(id);
    const panel = $('workspace-' + id);
    if (!visible && panel.contains(document.activeElement)) button.focus();
    panel.hidden = !visible;
    button.setAttribute('aria-pressed', String(visible));
    button.setAttribute('aria-disabled', String(visible && (compact || shown.length === 1)));
  }
  const selectedEdge = resizeEdge.value;
  resizeEdge.replaceChildren();
  workspaceDividers.forEach((divider, index) => {
    const left = workspacePanes[index];
    const right = shown[shown.indexOf(left) + 1];
    const hideDivider = compact || !shown.includes(left) || !right;
    if (hideDivider && document.activeElement === divider) {
      const fallback = shown.includes(left) ? left : shown[0];
      workspaceButtons.find(button => button.dataset.workspacePane === fallback).focus();
    }
    divider.hidden = hideDivider;
    if (hideDivider) return;
    const label = workspaceLabels[left] + ' / ' + workspaceLabels[right];
    divider.setAttribute('aria-label', label);
    divider.setAttribute('aria-controls', 'workspace-' + left);
    const option = el('option', label);
    option.value = left;
    resizeEdge.append(option);
  });
  if ([...resizeEdge.options].some(option => option.value === selectedEdge)) resizeEdge.value = selectedEdge;
  const resizeControls = $('workspace-resize-controls');
  if (!resizeEdge.options.length && resizeControls.contains(document.activeElement)) $('workspace-reset').focus();
  resizeControls.hidden = !resizeEdge.options.length;
  updateWorkspaceSizes();
}

function resizeWorkspace(left, size, persist = true) {
  const index = workspace.visible.indexOf(left);
  const right = workspace.visible[index + 1];
  if (index < 0 || !right || compactWorkspace.matches) return;
  const total = workspace.sizes[left] + workspace.sizes[right];
  workspace.sizes[left] = Math.max(minimumShare, Math.min(total - minimumShare, size));
  workspace.sizes[right] = total - workspace.sizes[left];
  updateWorkspaceSizes();
  if (persist) saveWorkspace();
}

for (const button of workspaceButtons) {
  button.onclick = () => {
    if (button.getAttribute('aria-disabled') === 'true') return;
    const id = button.dataset.workspacePane;
    if (compactWorkspace.matches) workspace.active = id;
    else {
      workspace.visible = workspacePanes.filter(pane =>
        pane === id ? !workspace.visible.includes(pane) : workspace.visible.includes(pane));
    }
    renderWorkspace();
    saveWorkspace();
  };
}

workspaceDividers.forEach((divider, index) => {
  const left = workspacePanes[index];
  divider.onkeydown = event => {
    const size = workspace.sizes[left];
    const positions = {ArrowLeft: size - 2, ArrowRight: size + 2, Home: 0, End: 100};
    if (!Object.hasOwn(positions, event.key)) return;
    const next = positions[event.key];
    event.preventDefault();
    resizeWorkspace(left, next);
  };
  let drag = null;
  divider.onpointerdown = event => {
    if (event.button !== 0 || drag) return;
    const panelWidth = workspace.visible.reduce((width, id) => width + $('workspace-' + id).getBoundingClientRect().width, 0);
    const total = workspace.visible.reduce((sum, id) => sum + workspace.sizes[id], 0);
    if (!panelWidth) return;
    drag = {id: event.pointerId, x: event.clientX, size: workspace.sizes[left], scale: total / panelWidth};
    divider.setPointerCapture(event.pointerId);
  };
  divider.onpointermove = event => {
    if (drag?.id === event.pointerId) resizeWorkspace(left, drag.size + (event.clientX - drag.x) * drag.scale, false);
  };
  divider.onlostpointercapture = () => {
    drag = null;
    saveWorkspace();
  };
});

resizeEdge.onchange = updateWorkspaceSizes;
$('workspace-smaller').onclick = () => resizeWorkspace(resizeEdge.value, workspace.sizes[resizeEdge.value] - 2);
$('workspace-larger').onclick = () => resizeWorkspace(resizeEdge.value, workspace.sizes[resizeEdge.value] + 2);
$('workspace-reset').onclick = () => {
  workspace = defaultWorkspace();
  renderWorkspace();
  saveWorkspace();
};
compactWorkspace.addEventListener('change', renderWorkspace);
renderWorkspace();

const gamesPanel = $('games-panel');
const gamesButton = $('games-open');
function showGames(show) {
  if (show && !$('games-player').hasAttribute('src')) {
    $('games-player').src = gamesPanel.dataset.playerUrl;
  }
  gamesPanel.hidden = !show;
  gamesButton.setAttribute('aria-expanded', String(show));
  (show ? $('games-close') : gamesButton).focus();
}
gamesButton.onclick = () => selectSection('games');
$('games-close').onclick = () => selectSection('home');
const mediaPanel = $('media-panel');
const mediaButton = $('media-open');
const mediaPlayer = $('media-player');
const mediaStatus = $('media-status');
const mediaResults = $('media-results');
const mediaKey = 'envpath.media.video.v1';
const videoIdPattern = /^[A-Za-z0-9_-]{11}$/;
const liveChannels = [
  {id: 'HvZt-nh9sGg', title: 'France 24 English', channel: 'International news', official: 'https://www.france24.com/en/live'},
  {id: 'M3HKLzjvKPc', title: 'NASA Space Station Views', channel: 'Earth and orbit', official: 'https://www.nasa.gov/live/'}
];

function youtubeVideoId(input) {
  if (videoIdPattern.test(input)) return input;
  try {
    const url = new URL(input);
    if (url.protocol !== 'https:' || url.username || url.password || url.port) return null;
    let id;
    if (url.hostname === 'youtu.be') id = url.pathname.split('/')[1];
    if (['youtube.com', 'www.youtube.com', 'm.youtube.com'].includes(url.hostname)) {
      if (url.pathname === '/watch') id = url.searchParams.get('v');
      else id = url.pathname.match(/^\/(?:live|shorts|embed)\/([^/]+)\/?$/)?.[1];
    }
    return id && videoIdPattern.test(id) ? id : null;
  } catch (_) {
    return null;
  }
}

function playMedia(video) {
  if (!videoIdPattern.test(video.id)) return;
  const title = video.title || 'YouTube video';
  selectedProjectVideo = {id: video.id, title};
  $('media-empty').hidden = true;
  $('media-title').textContent = title;
  mediaPlayer.title = title;
  mediaPlayer.hidden = false;
  mediaPlayer.src = 'https://www.youtube-nocookie.com/embed/' + video.id;
  $('media-watch-source').href = 'https://www.youtube.com/watch?v=' + video.id;
  $('media-watch-source').hidden = false;
  mediaStatus.textContent = '';
  try { localStorage.setItem(mediaKey, JSON.stringify({id: video.id, title})); } catch (_) {}
  $('media-resume').hidden = false;
}

function showMedia(show) {
  mediaPanel.hidden = !show;
  mediaButton.setAttribute('aria-expanded', String(show));
  if (show) $('media-query').focus();
  else {
    mediaPlayer.removeAttribute('src');
    mediaPlayer.hidden = true;
    $('media-empty').hidden = false;
    $('media-watch-source').hidden = true;
    mediaButton.focus();
  }
}

function mediaRow(video) {
  const row = el('li', undefined, 'media-result');
  const play = el('button', undefined, 'media-play');
  play.type = 'button';
  play.append(el('strong', video.title), el('span', video.channel, 'small'));
  play.onclick = () => playMedia(video);
  row.append(play);
  if (video.official) {
    const source = el('a', 'Official feed', 'small');
    source.href = video.official;
    source.target = '_blank';
    source.rel = 'noopener noreferrer';
    row.append(source);
  }
  return row;
}

$('media-channels').append(...liveChannels.map(mediaRow));
mediaButton.onclick = () => selectSection('media');
$('media-close').onclick = () => selectSection('home');
$('media-resume').onclick = () => {
  try {
    const video = JSON.parse(localStorage.getItem(mediaKey));
    if (video && typeof video.id === 'string' && typeof video.title === 'string') playMedia(video);
  } catch (_) {}
};
try {
  const last = JSON.parse(localStorage.getItem(mediaKey));
  $('media-resume').hidden = !(typeof last?.id === 'string' && videoIdPattern.test(last.id));
} catch (_) {}

$('media-search').onsubmit = async event => {
  event.preventDefault();
  const value = $('media-query').value.trim();
  if (!value) return;
  const id = youtubeVideoId(value);
  if (id) {
    playMedia({id});
    return;
  }
  if (/^https?:\/\//i.test(value)) {
    mediaStatus.textContent = 'Enter a YouTube video link or a search term.';
    return;
  }
  const fallback = $('media-search-source');
  fallback.href = 'https://www.youtube.com/results?search_query=' + encodeURIComponent(value);
  fallback.hidden = false;
  mediaResults.replaceChildren();
  if (mediaPanel.dataset.searchEnabled !== 'yes') {
    mediaStatus.textContent = 'Open results on YouTube, then paste a video link here.';
    return;
  }
  const submit = $('media-submit');
  submit.disabled = true;
  mediaStatus.textContent = 'Searching YouTube…';
  try {
    const {videos} = await api('media-search', {query: value});
    mediaResults.append(...videos.map(mediaRow));
    mediaStatus.textContent = videos.length ? '' : 'No embeddable videos found.';
  } catch (error) {
    mediaStatus.textContent = error.message;
  } finally {
    submit.disabled = false;
  }
};

const projectsPanel = $('projects-panel');
const projectsButton = $('projects-open');
const projectsForm = $('project-form');
const projectStatus = $('project-status');
let currentProject;
let savedProject;
let projectBusy = false;
let selectedProjectRecord;
let selectedProjectVideo;

function projectDocument() {
  return {name: $('project-name').value, draft: $('project-draft').value,
    next_step: $('project-next').value, evidence: currentProject.evidence, videos: currentProject.videos};
}

function projectMaySwitch() {
  return !projectBusy && (JSON.stringify(projectDocument()) === savedProject ||
    confirm('Discard unsaved changes to this project?'));
}

function referenceRows(container, references, label, open) {
  $(container).replaceChildren(...references.map((reference, index) => {
    const row = el('li');
    const button = el('button', label(reference));
    button.type = 'button';
    button.onclick = () => open(reference);
    const remove = el('button', 'Remove');
    remove.type = 'button';
    remove.setAttribute('aria-label', 'Remove ' + label(reference));
    remove.onclick = () => {
      if (projectBusy) return;
      references.splice(index, 1);
      renderProjectLinks();
    };
    row.append(button, remove);
    return row;
  }));
}

function renderProjectLinks() {
  referenceRows('project-evidence', currentProject.evidence, record => 'Record #' + record.idx, async record => {
    try {
      await read(record.idx, record.hash);
      const evidenceButton = document.querySelector('[data-workspace-pane="evidence"]');
      if ($('workspace-evidence').hidden) evidenceButton.click();
      $('workspace-evidence').scrollIntoView({block: 'start'});
    } catch (error) {
      projectStatus.textContent = error.message;
    }
  });
  referenceRows('project-videos', currentProject.videos, video => video.title, video => {
    selectSection('media');
    playMedia(video);
    mediaPanel.scrollIntoView({block: 'start'});
  });
}

function renderProjectFiles() {
  $('project-attach').disabled = !currentProject.id;
  $('project-files').replaceChildren(...currentProject.files.map(file => {
    const row = el('li');
    const open = el('button', file.name);
    open.type = 'button';
    open.onclick = async () => {
      const projectId = currentProject.id;
      try {
        const {file: result} = await api('project-file', {project_id: projectId, file_id: file.id});
        if (currentProject.id !== projectId) return;
        $('project-file-title').textContent = result.name;
        $('project-file-content').textContent = result.content;
        $('project-file-preview').hidden = false;
      } catch (error) {
        if (currentProject.id === projectId) projectStatus.textContent = error.message;
      }
    };
    row.append(open);
    return row;
  }));
}

function loadProject(project) {
  currentProject = project;
  $('project-name').value = project.name;
  $('project-draft').value = project.draft;
  $('project-next').value = project.next_step;
  savedProject = JSON.stringify(projectDocument());
  renderProjectLinks();
  $('project-file-preview').hidden = true;
  $('project-file-content').textContent = '';
  renderProjectFiles();
}

function newProject() {
  loadProject({id: null, revision: 0, name: '', draft: '', next_step: '', evidence: [], videos: [], files: []});
}

async function refreshProjects() {
  const {projects} = await api('projects', {});
  $('project-list').replaceChildren(...projects.map(project => {
    const row = el('li');
    const open = el('button', project.name);
    open.type = 'button';
    if (project.id === currentProject.id) open.setAttribute('aria-current', 'true');
    open.onclick = async () => {
      if (!projectMaySwitch()) return;
      projectBusy = true;
      try {
        const response = await api('project-read', {project_id: project.id});
        loadProject(response.project);
        for (const button of $('project-list').querySelectorAll('button')) button.removeAttribute('aria-current');
        open.setAttribute('aria-current', 'true');
        projectStatus.textContent = '';
      } catch (error) {
        projectStatus.textContent = error.message;
      } finally {
        projectBusy = false;
      }
    };
    row.append(open);
    return row;
  }));
}

function addProjectLink(reference, list, key, missingMessage) {
  if (projectBusy) return;
  if (!reference) projectStatus.textContent = missingMessage;
  else if (list.some(item => item[key] === reference[key])) projectStatus.textContent = 'Already in this project.';
  else if (list.length >= 24) projectStatus.textContent = 'This project has reached the link limit.';
  else {
    list.push(reference);
    renderProjectLinks();
    projectStatus.textContent = 'Link added. Save the project to keep it.';
  }
}

function showProjects(show) {
  projectsPanel.hidden = !show;
  projectsButton.setAttribute('aria-expanded', String(show));
  (show ? $('project-new') : projectsButton).focus();
  if (show) refreshProjects().catch(error => { projectStatus.textContent = error.message; });
}

function selectSection(section) {
  const sections = [
    ['games', gamesPanel, gamesButton, showGames],
    ['media', mediaPanel, mediaButton, showMedia],
    ['projects', projectsPanel, projectsButton, showProjects],
  ];
  for (const [name, panel, button, show] of sections) {
    if (name !== section && !panel.hidden) show(false);
    button.removeAttribute('aria-current');
  }
  const home = $('home-open');
  $('workspace-home').hidden = section !== 'home';
  if (section === 'home') {
    home.setAttribute('aria-current', 'page');
    home.focus();
    return;
  }
  home.removeAttribute('aria-current');
  const [, panel, button, show] = sections.find(([name]) => name === section);
  button.setAttribute('aria-current', 'page');
  if (panel.hidden) show(true);
}

$('home-open').onclick = () => selectSection('home');
newProject();
projectsButton.onclick = () => selectSection('projects');
$('projects-close').onclick = () => selectSection('home');
$('project-new').onclick = () => {
  if (!projectMaySwitch()) return;
  newProject();
  $('project-list').querySelector('[aria-current]')?.removeAttribute('aria-current');
  projectStatus.textContent = '';
  $('project-name').focus();
};
$('project-capture-draft').onclick = () => {
  if (!projectBusy) $('project-draft').value = $('draft-content').value;
};
$('project-open-draft').onclick = () => {
  const field = $('draft-content');
  if (field.value && field.value !== $('project-draft').value &&
      !confirm('Replace the current workspace draft text?')) return;
  field.value = $('project-draft').value;
  $('draft-kind').value = 'note';
  target = null;
  syncTarget();
  invalidateDraft();
  if ($('workspace-draft').hidden) document.querySelector('[data-workspace-pane="draft"]').click();
  field.focus();
};
$('project-add-evidence').onclick = () => addProjectLink(
  selectedProjectRecord, currentProject.evidence, 'hash', 'Open an evidence record first.');
$('project-add-video').onclick = () => addProjectLink(
  selectedProjectVideo, currentProject.videos, 'id', 'Open a video in Media first.');
$('project-attach').onclick = () => {
  if (!projectBusy && currentProject.id) $('project-file-picker').click();
};
$('project-file-picker').onchange = async event => {
  const picker = event.currentTarget;
  const file = picker.files[0];
  picker.value = '';
  if (!file || projectBusy || !currentProject.id) return;
  if (!/\.(txt|md)$/i.test(file.name) || file.size > 24 * 1024) {
    projectStatus.textContent = 'Choose a UTF-8 .txt or .md file up to 24 KiB.';
    return;
  }
  projectBusy = true;
  $('project-attach').disabled = true;
  try {
    const content = new TextDecoder('utf-8', {fatal: true}).decode(await file.arrayBuffer());
    const result = await api('project-attach', {project_id: currentProject.id, name: file.name, content});
    currentProject.files.push(result.file);
    renderProjectFiles();
    projectStatus.textContent = 'File attached and saved locally.';
  } catch (error) {
    projectStatus.textContent = error.message;
  } finally {
    projectBusy = false;
    $('project-attach').disabled = !currentProject.id;
  }
};
projectsForm.onsubmit = async event => {
  event.preventDefault();
  if (projectBusy) return;
  projectBusy = true;
  const document = projectDocument();
  const fields = [...projectsForm.querySelectorAll('input, textarea, button')];
  for (const field of fields) field.disabled = true;
  try {
    const {project} = await api('project-save', {
      project_id: currentProject.id, revision: currentProject.revision, document
    });
    loadProject(project);
    projectStatus.textContent = 'Project saved locally.';
    await refreshProjects();
  } catch (error) {
    projectStatus.textContent = error.message;
  } finally {
    for (const field of fields) field.disabled = false;
    $('project-attach').disabled = !currentProject.id;
    projectBusy = false;
  }
};

applyAppearance(readAppearance());
status();
</script></body></html>'''
