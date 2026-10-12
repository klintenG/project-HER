// Compile source with the installed TS compiler. No extra runtime test framework.
const fs=require('fs'),path=require('path'),ts=require('typescript'),Module=require('module');
const cache={};
function load(name){
 if(cache[name])return cache[name].exports;
 const filename=path.resolve(__dirname,'src/editorial',name+'.ts');
 const code=ts.transpileModule(fs.readFileSync(filename,'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022,esModuleInterop:true,resolveJsonModule:true}}).outputText;
 const m=new Module(filename);cache[name]=m;m.filename=filename;m.paths=Module._nodeModulePaths(path.dirname(filename));
 const original=m.require.bind(m);m.require=id=>id.startsWith('./')&&!id.endsWith('.json')?load(id.slice(2)):original(id);m._compile(code,filename);return m.exports;
}
async function main(){
 const {validateTimelineHash}=load('contract'),{stateAt}=load('motion');
 const suite=JSON.parse(fs.readFileSync(process.argv[2],'utf8'));
 for(const c of suite.cases){let accepted=true;try{await validateTimelineHash(c.value);}catch{accepted=false;}if(accepted!==c.accept)throw Error('Cross-language disagreement: '+c.name);}
 const m=suite.cases[0].value;
 for(const e of m.events){
   const l=m.layers.find(l=>l.id===e.targetIds[0]);
   const at=stateAt(l,[e],Math.floor((e.startFrame+e.endFrame)/2));
   const again=stateAt(l,[e],Math.floor((e.startFrame+e.endFrame)/2));
   if(JSON.stringify(at)!==JSON.stringify(again))throw Error('Non-deterministic seeking');
 }
 for(const row of suite.motion){const s=stateAt(row.layer,[row.event],row.frame);for(const [key,value] of Object.entries(row.expected)){if(Math.abs(s[key]-value)>1e-6)throw Error('Wrong intermediate '+row.event.type+' '+key);}}
 console.log(`${suite.cases.length} Python/Remotion conformance cases and ${suite.motion.length} intermediate motion states passed.`);
}
main().catch(e=>{console.error(e);process.exit(1);});
