// Render the real production composition; no separate demo renderer.
const fs=require('fs'),path=require('path'),ts=require('typescript'),crypto=require('crypto');
const {bundle}=require('@remotion/bundler');
const {openBrowser,selectComposition,renderMedia,renderStill}=require('@remotion/renderer');
const timing={exports:{}};new Function('require','module','exports',ts.transpileModule(fs.readFileSync(path.join(__dirname,'src/branding/timing.ts'),'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS}}).outputText)(require,timing,timing.exports);
(async()=>{
 const props=JSON.parse(fs.readFileSync(process.argv[2],'utf8')),out=path.resolve(process.argv[3]);fs.mkdirSync(out,{recursive:true});
 const serveUrl=await bundle({entryPoint:path.resolve(__dirname,'src/index.ts'),publicDir:path.resolve(__dirname,'public')});
 const browser=await openBrowser('chrome');
 try{
 const id='ProjectHEREditorial',composition=await selectComposition({serveUrl,id,inputProps:props,puppeteerInstance:browser});
 const events=timing.exports.schedule(props.durationInFrames,props.fps,props.branding,props.beats.filter(b=>b.template!=='final-reveal').map(b=>({start:b.startFrame+15,end:b.endFrame-15})));
 fs.writeFileSync(path.join(out,'schedule.json'),JSON.stringify({storyFrames:props.durationInFrames,totalFrames:composition.durationInFrames,fps:props.fps,events},null,2));
 const options={serveUrl,composition,inputProps:props,puppeteerInstance:browser};
 let last=-1;
 await renderMedia({...options,codec:'h264',outputLocation:path.join(out,'branded-story.mp4'),concurrency:3,crf:18,onProgress:({progress})=>{const p=Math.floor(progress*10);if(p!==last){last=p;console.log(`MP4 ${p*10}%`);}}});
 const frames=[0,events[0].start+events[0].fade+30,events.find(e=>e.kind==='credit').start+30,props.durationInFrames,props.durationInFrames+12,composition.durationInFrames-1,events[0].start+events[0].fade+30];
 const hashes=[];
 for(let i=0;i<frames.length;i++){
  const output=path.join(out,`studio-${i}.png`);await renderStill({...options,frame:frames[i],output,imageFormat:'png'});
  hashes.push(crypto.createHash('sha256').update(fs.readFileSync(output)).digest('hex'));
 }
 if(hashes[1]!==hashes[6])throw Error('Frame seeking changed branding');
 const checks=[];
 for(const [id,inputProps] of [['ProjectHER',{width:1920,height:1080}],['ProjectHER',{width:1080,height:1080}],['ProjectHERNews',{}]]){
  const c=await selectComposition({serveUrl,id,inputProps,puppeteerInstance:browser});
  const file=`${id}-${c.width}x${c.height}.mp4`;
  await renderMedia({serveUrl,composition:c,inputProps,puppeteerInstance:browser,codec:'h264',outputLocation:path.join(out,file),scale:.5,concurrency:2});
  checks.push({id,width:c.width,height:c.height,frames:c.durationInFrames,file});
 }
 fs.writeFileSync(path.join(out,'validation.json'),JSON.stringify({frames,hashes,deterministic:true,checks},null,2));
 console.log('Full story, Studio seek checks and classic/News smoke exports complete.');
 }finally{await browser.close({silent:true});}
})().catch(e=>{console.error(e);process.exit(1);});
