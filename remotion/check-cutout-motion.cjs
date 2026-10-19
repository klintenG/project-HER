// Renderer invariants: legacy defaults, exact-onset action visibility, stagger,
// deterministic seeking, and finite bounded transforms throughout short shots.
const fs=require('fs');
const path=require('path');
const ts=require('typescript');
const assert=require('node:assert/strict');
const cache=new Map();
function load(file){
  const resolved=path.resolve(__dirname,'src/editorial',file+'.ts');
  if(cache.has(resolved))return cache.get(resolved);
  const source=ts.transpileModule(fs.readFileSync(resolved,'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022}}).outputText;
  const module={exports:{}};cache.set(resolved,module.exports);
  new Function('require','module','exports',source)((name)=>name.startsWith('./')?load(name.slice(2)):require(name),module,module.exports);
  return module.exports;
}
const {cutoutMotionAt}=load('cutoutMotion');
const oldMotion={entrance:'slide_left',exit:'fade',entranceFrames:9,driftX:24,driftY:-24,scaleTo:1.06,tilt:0,parallaxDepth:.5,elements:[]};
const legacy={startFrame:10,endFrame:90,motion:oldMotion};
const action={...legacy,motion:{...oldMotion,initialOpacity:1,exitFrames:4,entranceTravel:42,focusFrame:32,focusScale:1.025}};
for(const layer of [legacy,action,{...action,endFrame:15}]){
  for(let f=layer.startFrame;f<layer.endFrame;f++){
    const state=cutoutMotionAt(layer,f);
    for(const value of Object.values(state))assert(Number.isFinite(value),'legacy or short-shot transform must remain finite');
    assert(state.scale>0&&state.opacity>=0&&state.opacity<=1,'visible bounded transform');
  }
}
assert(cutoutMotionAt(action,10).opacity===1,'mandatory action cannot fade away at its spoken onset');
assert(cutoutMotionAt(action,11,5,.5).opacity===0,'supporting piece must stay hidden before its stagger');
const seek=cutoutMotionAt(action,32);cutoutMotionAt(action,70);cutoutMotionAt(action,12);
assert.deepEqual(cutoutMotionAt(action,32),seek,'seek order must not accumulate motion');
assert(cutoutMotionAt(action,60).x>cutoutMotionAt(action,25).x,'uphill action travels forward');
console.log('Cutout motion invariants passed.');
