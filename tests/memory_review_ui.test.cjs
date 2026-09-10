const test = require('node:test');
const assert = require('node:assert/strict');
const ui = require('../src/sparkle/dashboard/memory-review.js');
class Element {
  constructor(tag) { this.tag=tag; this.children=[]; this.events={}; this.textContent=''; }
  set innerHTML(_) { throw Error('HTML interpretation forbidden'); }
  appendChild(e) { this.children.push(e); }
  replaceChildren() { this.children=[]; }
  addEventListener(name,fn) { this.events[name]=fn; }
}
const document={createElement:tag=>new Element(tag)};
const flatten=e=>[e,...e.children.flatMap(flatten)];
function setup(overrides={}, options={}) {
  const proposal={id:'a'.repeat(32),digest:'b'.repeat(64),status:'pending',expired:false,conflict:false,target_blocked:false,
    payload:{id:'a'.repeat(32),category:'profile',key:'name',value:'<img src=x onerror=steal()>',expires_at:2000},
    verification:{status:'VERIFIED',reason:'exact'},evidence:[{source_ref:'<script>untrusted</script>'}],...overrides};
  const container=new Element('div'), calls=[]; let reloads=0;
  ui.render({container,proposals:[proposal],document,now:()=>1000*1000,confirm:()=>true,
    api:async(...args)=>calls.push(args),onChange:async()=>{reloads++;},...options});
  const nodes=flatten(container);
  const button=name=>nodes.find(e=>e.tag==='button' && e.textContent.startsWith(name));
  return {container,nodes,calls,button,strict:nodes.find(e=>e.tag==='input'),reloads:()=>reloads};
}
test('untrusted claims and evidence remain literal text',()=>{
 const s=setup(); assert(s.nodes.some(e=>e.textContent==='<img src=x onerror=steal()>'));
 assert(s.nodes.some(e=>e.textContent.includes('<script>')));
 assert(s.nodes.some(e=>e.textContent.includes('b'.repeat(64))));
});
test('approval binds exact identity and verified policy',async()=>{
 const s=setup(); await s.button('Approve').events.click();
 assert.equal(s.calls.length,1); assert.equal(s.calls[0][0],'/api/memory/review');
 assert.deepEqual(JSON.parse(s.calls[0][1].body),{proposal_id:'a'.repeat(32),digest:'b'.repeat(64),decision:'approve',require_verified:true});
 assert.equal(s.reloads(),1);
});
test('cancel makes no request',async()=>{const s=setup({}, {confirm:()=>false}); await s.button('Approve').events.click(); assert.equal(s.calls.length,0);});
test('inconclusive requires explicit operator override',async()=>{
 const s=setup({verification:{status:'INCONCLUSIVE'}}); assert(s.button('Approve').disabled);
 s.strict.checked=false;s.strict.events.change();assert(!s.button('Approve').disabled);
 await s.button('Approve').events.click();assert.equal(JSON.parse(s.calls[0][1].body).require_verified,false);
});
test('unsafe and missing evidence fails closed',async()=>{
 for(const override of [{verification:{status:'REJECTED'}},{verification:{}},{expired:true},{conflict:true},{target_blocked:true},{conflict:undefined},{digest:'bad'},{payload:{expires_at:1e300}}]) {
  const s=setup(override);s.strict.checked=false;s.strict.events.change();assert(s.button('Approve').disabled);
  await s.button('Approve').events.click();assert.equal(s.calls.length,0);
 }
});
test('expiry is rechecked at click time',async()=>{let now=1000000;const s=setup({}, {now:()=>now});now=3000000;await s.button('Approve').events.click();assert.equal(s.calls.length,0);});
test('duplicate clicks cannot duplicate in-flight request',async()=>{
 let release;let count=0;const s=setup({}, {api:()=>{count++;return new Promise(resolve=>{release=resolve;});}});
 const pending=s.button('Approve').events.click();await s.button('Approve').events.click();assert.equal(count,1);release();await pending;
});
test('server rejection is not displayed as success or leaked',async()=>{
 const s=setup({}, {api:async()=>{throw Error('private error');}});await s.button('Approve').events.click();
 assert.equal(s.reloads(),0);assert(!s.button('Approve').disabled);
 assert(s.nodes.some(e=>e.textContent.startsWith('Request failed')));assert(!s.nodes.some(e=>e.textContent.includes('private error')));
});
test('revalidation is separate from approval',async()=>{const s=setup();await s.button('Revalidate').events.click();assert.equal(s.calls[0][0],'/api/memory/validate');assert(!('decision' in JSON.parse(s.calls[0][1].body)));});
test('completed proposals cannot displace pending and audit stays text',()=>{
 const container=new Element('div');ui.render({container,proposals:[{status:'approved'}],document});assert.equal(container.children[0].textContent,'No pending proposals.');
 ui.history(container,[{id:1,action:'deleted',snapshot:'<script>private</script>'}],document);assert(flatten(container).some(e=>e.textContent.includes('<script>')));
});
