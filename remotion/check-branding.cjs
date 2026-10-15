const ts=require('typescript'),fs=require('fs'),assert=require('node:assert/strict');
const modulePath=require('path').resolve(__dirname,'src/branding/timing.ts');
const source=ts.transpileModule(fs.readFileSync(modulePath,'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022}}).outputText;
const m={exports:{}};new Function('require','module','exports',source)(require,m,m.exports);
const {schedule,outroFrames,classicFrames,config}=m.exports;
for(const fps of [24,25,30,60])for(const seconds of [3,14,15,20,29,30,45,66.8,90,180]){
 const n=Math.ceil(seconds*fps),e=schedule(n,fps,{deterministicSeed:'test'});
 assert.deepEqual(e,schedule(n,fps,{deterministicSeed:'test'}));
 assert.equal(outroFrames(fps),Math.round(2.7*fps));
 if(seconds<15)assert.equal(e.length,0);
 if(seconds>=30){assert.equal(e.filter(x=>x.kind==='credit').length,1);assert.equal(e.filter(x=>x.kind==='protective').length,2);}
 e.forEach((x,i)=>{assert(x.start>=2*fps);assert(x.end<=n-2*fps);assert(x.hold>=3*fps&&x.hold<=5*fps);assert(x.opacity>=.08&&x.opacity<=.12);if(i)assert(x.start-e[i-1].end>=1.75*fps);});
}
assert.equal(outroFrames(30),81);assert.equal(outroFrames(30,{enabled:false}),0);
assert.equal(outroFrames(30,{outro:{enabled:false}}),0);
assert.deepEqual(schedule(2004,30,{enabled:false}),[]);
assert.throws(()=>config({protectiveOverlayOpacityRange:[.1,.15]}));
assert.equal(classicFrames({fps:30,screens:[{duration:1.01},{duration:1,audio_duration:2},{duration:1,word_timings:[{end:3}]}]}),181);
console.log('Branding: deterministic schedule, all frame rates, short fallbacks, full holds, spacing, limits and narration-safe durations passed.');
