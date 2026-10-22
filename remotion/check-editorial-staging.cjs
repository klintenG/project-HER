// Exercise the actual frame evaluator, including restoration and fade composition.
const fs=require('fs'),path=require('path'),ts=require('typescript'),Module=require('module');
const filename=path.resolve(__dirname,'src/editorial/motion.ts');
const compiled=ts.transpileModule(fs.readFileSync(filename,'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS}}).outputText;
const module_=new Module(filename);module_._compile(compiled,filename);
const {stateAt}=module_.exports;
const assert=(ok,why)=>{if(!ok)throw Error(why);};
const near=(a,b)=>Math.abs(a-b)<1e-9;
const layer={id:'actor',opacity:1,bounds:{x:190,y:650,w:700,h:700}};
const base={targetIds:['actor'],easing:'linear',scaleFrom:1,scaleTo:1,dy:0,dx:0,opacityFrom:1,opacityTo:1};
const events=[
 {...base,type:'spotlight',startFrame:0,endFrame:10,opacityTo:.64},
 {...base,type:'spotlight',startFrame:20,endFrame:30,opacityFrom:.64,opacityTo:1},
 {...base,type:'fade',startFrame:40,endFrame:50,opacityTo:0},
 {...base,type:'reframe',startFrame:0,endFrame:18,boundsFrom:layer.bounds,boundsTo:{x:70,y:660,w:500,h:680}},
];
assert(near(stateAt(layer,events,15).opacity,.64),'supporting subject must recede');
assert(near(stateAt(layer,events,25).opacity,.82),'focus must restore from the previous opacity');
assert(near(stateAt(layer,events,35).opacity,1),'restored focus must reach full opacity without cumulative dimming');
assert(near(stateAt(layer,events,45).opacity,.5),'exit fade must still work after spotlight restoration');
assert(near(stateAt(layer,events,9).bounds.x,130),'midpoint must travel between centered and side layouts');
assert(JSON.stringify(stateAt(layer,events,9))===JSON.stringify(stateAt(layer,events,9)),'seeking must be deterministic');
console.log('Narrated spotlight restoration, independent exit fade, center-to-side midpoint and deterministic seeking passed.');
