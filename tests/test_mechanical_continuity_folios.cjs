// Dependency-free DOM harness for the exact inline script in the installed book HTML.
// Run: node test_mechanical_continuity_folios.cjs holosim/mechanical_continuity_book.html
'use strict';
const fs = require('node:fs');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const {test} = require('node:test');
const path = require('node:path');
const htmlPath = process.argv[2] || 'holosim/mechanical_continuity_book.html';
const html = fs.readFileSync(path.resolve(htmlPath), 'utf8');
const script = html.match(/<script(?:\s[^>]*)?>([\s\S]*?)<\/script>/i)?.[1];
assert.ok(script, 'Expected inline book script');
class Node {
  constructor(tag = 'div') { this.tag = tag; this.children = []; this.listeners = {}; this.textContent = ''; this.hidden = false; this.className = ''; this.attributes = {}; }
  appendChild(child) { this.children.push(child); return child; }
  replaceChildren(...children) { this.children = children; }
  addEventListener(type, callback) { this.listeners[type] = callback; }
  setAttribute(name, value) { this.attributes[name] = value; }
  click() { assert.equal(typeof this.listeners.click, 'function', 'Expected clickable button'); return this.listeners.click(); }
}
function descendants(node) { return [node, ...node.children.flatMap(descendants)]; }
function setup(entries, pages) {
  const ids = Object.fromEntries(['heading','content','intro','section-tag','page-number'].map(id => [id, new Node()]));
  const calls = [];
  const context = vm.createContext({
    document: {getElementById: id => ids[id], createElement: tag => new Node(tag)},
    window: {scrollTo() {}}, URLSearchParams,
    fetch: async url => {
      calls.push(url);
      let value;
      if (url === '/api/contents') value = {lineage_hash:'lineage', contents:entries};
      else {
        const parsed = new URL(url, 'http://localhost');
        value = pages[JSON.stringify([parsed.searchParams.get('kind'), parsed.searchParams.get('id')])];
      }
      return value ? {ok:true, json:async()=>value} : {ok:false, json:async()=>({reason:'not found'})};
    },
  });
  vm.runInContext(script, context, {filename:htmlPath});
  const evalJS = expr => vm.runInContext(expr, context);
  return {ids, calls, evalJS, all: () => descendants(ids.content), buttons: () => descendants(ids.content).filter(n=>n.tag==='button'), settle: async()=>{for(let i=0;i<6;i++) await new Promise(resolve=>setImmediate(resolve));}};
}
const E = (kind,id,hash) => ({kind,id,record_hash:hash});
const P = (kind,id,hash,record) => ({kind,id,record_hash:hash,record});
const key = (kind,id) => JSON.stringify([kind,id]);
const system = E('systems','reader','sys-hash');
const observation = E('observations','reader-test','obs-hash');
const pages = {
  [key('systems','reader')]:P('systems','reader','sys-hash',{system_id:'reader',status:'OBSERVED'}),
  [key('observations','reader-test')]:P('observations','reader-test','obs-hash',{observation_id:'reader-test',system_id:'reader',source_id:'fixture'}),
};
test('observation reference navigates to distinct system and updates identity', async()=>{
  const h=setup([system,observation],pages); await h.settle();
  h.buttons().find(b=>descendants(b).some(n=>n.textContent==='reader-test')).click(); await h.settle();
  assert.equal(h.ids.heading.textContent,'observations / reader-test');
  const link=h.buttons().find(b=>b.textContent==='Open systems / reader');
  assert.ok(link,'Exact cross-record reference button missing'); link.click(); await h.settle();
  assert.equal(h.ids.heading.textContent,'systems / reader');
  assert.ok(h.all().some(n=>n.textContent==='sys-hash'));
  assert.ok(h.calls.some(url=>url.includes('kind=systems')&&url.includes('id=reader')));
});
test('system identity is not a self-reference',async()=>{
  const h=setup([system,observation],pages); await h.settle();
  h.buttons().find(b=>descendants(b).some(n=>n.textContent==='reader')).click(); await h.settle();
  assert.equal(h.ids.heading.textContent,'systems / reader');
  assert.ok(!h.buttons().some(b=>b.textContent==='Open systems / reader'));
});
test('missing reference is visible but not navigable',async()=>{
  const missing=P('observations','reader-test','obs-hash',{observation_id:'reader-test',system_id:'absent'});
  const h=setup([system,observation],{...pages,[key('observations','reader-test')]:missing}); await h.settle();
  h.buttons().find(b=>descendants(b).some(n=>n.textContent==='reader-test')).click(); await h.settle();
  assert.ok(h.all().some(n=>String(n.textContent).includes('Unresolved in retained contents')));
  assert.ok(!h.buttons().some(b=>String(b.textContent).startsWith('Open systems /')));
});
test('ambiguous record hash withholds navigation',async()=>{
  const correction=E('corrections','cor-1','cor-hash');
  const other=E('systems','second','sys-hash');
  const h=setup([system,other,correction],{
    ...pages,[key('corrections','cor-1')]:P('corrections','cor-1','cor-hash',{correction_id:'cor-1',target_record_hash:'sys-hash'})
  }); await h.settle();
  h.buttons().find(b=>descendants(b).some(n=>n.textContent==='cor-1')).click(); await h.settle();
  assert.ok(h.all().some(n=>String(n.textContent).includes('Ambiguous: 2 index entries')));
  assert.ok(!h.buttons().some(b=>String(b.textContent).startsWith('Open systems /')));
});
test('page hash mismatch is rejected before rendering record',async()=>{
  const h=setup([system],{[key('systems','reader')]:P('systems','reader','wrong-hash',{system_id:'reader'})}); await h.settle();
  h.buttons().find(b=>descendants(b).some(n=>n.textContent==='reader')).click(); await h.settle();
  assert.ok(h.all().some(n=>String(n.textContent).includes('disagrees with retained contents index')));
});
