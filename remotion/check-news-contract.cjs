// Paid-service-free cross-language contract check, using the installed TypeScript compiler.
const fs=require('fs');const path=require('path');const ts=require('typescript');const Module=require('module');
const cache={};
function load(name){
 if(cache[name])return cache[name].exports;
 const filename=path.resolve(__dirname,'src',name+'.ts');
 const code=ts.transpileModule(fs.readFileSync(filename,'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022}}).outputText;
 const module=new Module(filename);cache[name]=module;module.filename=filename;module.paths=Module._nodeModulePaths(path.dirname(filename));
 const original=module.require.bind(module);module.require=(id)=>id.startsWith('./news-')?load(id.slice(2)):original(id);
 module._compile(code,filename);return module.exports;
}
(async()=>{
 const {validateNewsManifest}=load('news-types');
 const fixture=JSON.parse(fs.readFileSync(process.argv[2]||path.resolve(__dirname,'../output/news_validation/news_manifest.json'),'utf8'));
 await validateNewsManifest(fixture);
 const mutations=[d=>d.audio.script_hash='stale',d=>d.extra='unchecked',d=>d.beats[0].layers=[],d=>d.beats[0].texts[0].rect.y=.1,d=>d.script.sentences[0].claim_ids=['missing']];
 for(const change of mutations){const altered=JSON.parse(JSON.stringify(fixture));change(altered);let rejected=false;try{await validateNewsManifest(altered);}catch{rejected=true;}if(!rejected)throw Error('Malformed News contract accepted');}
 console.log('News Zod contract: fixture accepted; five malformed variants rejected.');
})().catch(error=>{console.error(error);process.exit(1);});
