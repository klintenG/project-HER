// Actual Chromium frame-seeking determinism and subtitle-profile evidence.
const fs=require('fs'),path=require('path'),crypto=require('crypto');
const {bundle}=require('@remotion/bundler');
const {openBrowser,selectComposition,renderStill}=require('@remotion/renderer');
(async()=>{
 const props=JSON.parse(fs.readFileSync(process.argv[2],'utf8'));
 const out=path.resolve(process.argv[3]);fs.mkdirSync(out,{recursive:true});
 const serveUrl=await bundle({entryPoint:path.resolve(__dirname,'src/index.ts'),publicDir:path.resolve(__dirname,'public')});
 const browser=await openBrowser('chrome');
 try{
   const composition=await selectComposition({serveUrl,id:'ProjectHEREditorial',inputProps:props,puppeteerInstance:browser});
   const frames=[0,100,composition.durationInFrames-1,100];const hashes=[];
   for(let i=0;i<frames.length;i++){
     const output=path.join(out,`seek-${i}-frame-${frames[i]}.png`);
     await renderStill({serveUrl,composition,inputProps:props,frame:frames[i],output,imageFormat:'png',puppeteerInstance:browser});
     hashes.push(crypto.createHash('sha256').update(fs.readFileSync(output)).digest('hex'));
   }
   if(hashes[1]!==hashes[3])throw Error('Repeated frame differs after seeking to closing frame');
   const captionProps={...props,subtitleMode:'complete'};
   const captionComposition=await selectComposition({serveUrl,id:'ProjectHEREditorial',inputProps:captionProps,puppeteerInstance:browser});
   if(captionComposition.props.subtitleMode!=='complete')throw Error('Subtitle profile did not reach composition');
   await renderStill({serveUrl,composition:captionComposition,inputProps:captionProps,frame:100,output:path.join(out,'complete-caption-profile.png'),imageFormat:'png',puppeteerInstance:browser});
   fs.writeFileSync(path.join(out,'determinism.json'),JSON.stringify({frames,hashes,identical:hashes[1]===hashes[3]},null,2));
   console.log('Pixel-identical repeated frame after out-of-order seeking; opening, closing and complete-caption profile rendered.');
 }finally{await browser.close({silent:true});}
})().catch(e=>{console.error(e);process.exit(1);});
