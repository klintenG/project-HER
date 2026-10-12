import React, {useEffect, useState} from 'react';
import {AbsoluteFill, Audio, Img, staticFile, useCurrentFrame, delayRender, continueRender, cancelRender} from 'remotion';
import {NewsManifestSchema, validateNewsManifest, Manifest, Beat, Layer, Text} from './news-types';
const clamp=(v:number)=>Math.max(0,Math.min(1,v));
const ease=(v:number)=>1-Math.pow(1-clamp(v),3);
const assetURL=(path:string)=>staticFile(path);

const NewsText:React.FC<{text:Text;frame:number;end:number;m:Manifest}>=({text,frame,end,m})=>{
  let wordIndex=0;
  const size=text.size*m.width/1080;
  const emphasis=new Set(text.emphasis.flatMap(phrase=>phrase.split(/\s+/u)));
  return <div style={{position:'absolute',left:text.rect.x*m.width,top:text.rect.y*m.height,width:text.rect.w*m.width,height:text.rect.h*m.height,fontFamily:'NewsPoppins',fontWeight:text.weight,fontSize:size,lineHeight:1.12,color:m.theme.text,textAlign:'center'}}>
    {text.lines.map((line,index)=><div key={index} style={{whiteSpace:'nowrap',height:size*1.12}}>
      {line.split(/\s+/u).map((word,i)=>{const reveal=text.reveal_frames[wordIndex++];return <React.Fragment key={i}><span style={{display:'inline-block',fontWeight:emphasis.has(word.replace(/[.,:!?]/g,''))?700:text.weight,opacity:clamp((frame-reveal)/m.theme.transition_frames)*clamp((end-frame)/m.theme.transition_frames)}}>{word}</span>{i<line.split(/\s+/u).length-1?' ':''}</React.Fragment>;})}
    </div>)}
  </div>;
};
const Cutout:React.FC<{layer:Layer;beat:Beat;previous?:Beat;following?:Beat;frame:number;m:Manifest}>=({layer,beat,previous,following,frame,m})=>{
  const a=m.assets.find(a=>a.id===layer.asset_id)!;
  const n=m.theme.transition_frames;
  const entering=layer.persist?1:clamp((frame-layer.reveal)/n);
  const leaving=following?.layers?.some(l=>l.id===layer.id)?1:clamp((beat.end-frame)/n);
  let rect={...layer.rect};
  const old=previous?.layers?.find(l=>l.id===layer.id);
  if(layer.persist&&old){const t=ease((frame-beat.start)/n);rect={x:old.rect.x+(rect.x-old.rect.x)*t,y:old.rect.y+(rect.y-old.rect.y)*t,w:old.rect.w+(rect.w-old.rect.w)*t,h:old.rect.h+(rect.h-old.rect.h)*t};}
  const scale=1+.025*Math.sin(clamp((frame-layer.reveal)/18)*Math.PI);
  return <div style={{position:'absolute',left:rect.x*m.width,top:(rect.y+(1-ease(entering))*.008)*m.height,width:rect.w*m.width,height:rect.h*m.height,opacity:entering*leaving*layer.opacity,transform:`scale(${scale})`,zIndex:layer.z,filter:`drop-shadow(${m.width*.004}px ${m.width*.005}px ${m.width*.007}px rgba(35,35,35,.14))`}}>
    <Img src={assetURL(a.path)} style={{width:'92%',height:'92%',margin:'4%',objectFit:'contain',...(layer.portrait_fade?{maskImage:'linear-gradient(to bottom,black 87%,transparent 100%)'}:{})}}/>
  </div>;
};

export const NewsVideo:React.FC<Manifest>=(props)=>{
  const m=NewsManifestSchema.parse(props); const frame=useCurrentFrame();
  const [handle]=useState(()=>delayRender('Loading bundled News fonts'));
  useEffect(()=>{
    const fonts=[new FontFace('NewsPoppins',`url("${assetURL(m.theme.font_semibold)}")`,{weight:'600'}),new FontFace('NewsPoppins',`url("${assetURL(m.theme.font_bold)}")`,{weight:'700'})];
    Promise.all([validateNewsManifest(m),Promise.all(fonts.map(f=>f.load()))]).then(([,loaded])=>{loaded.forEach(f=>document.fonts.add(f));continueRender(handle);}).catch(cancelRender);
    return ()=>fonts.forEach(f=>document.fonts.delete(f));
  },[handle,m.theme.font_semibold,m.theme.font_bold]);
  const index=m.beats.findIndex(b=>b.start<=frame&&frame<b.end); const beat=m.beats[index];
  return <AbsoluteFill style={{background:'radial-gradient(ellipse at 50% 48%,#FAF9F6,#F2F0EC 75%,#EDEBE6)',overflow:'hidden'}}>
    <Audio src={assetURL(m.audio.path)}/>
    {/* Foreground mask is a final safeguard; geometry is already measured and inset. */}
    <AbsoluteFill style={{clipPath:'inset(20% 8% 15% 8%)'}}>
      {beat?.layers?.map(l=><Cutout key={l.id} layer={l} beat={beat} previous={m.beats[index-1]} following={m.beats[index+1]} frame={frame} m={m}/>)}
      <AbsoluteFill style={{zIndex:20}}>{beat?.texts.map(t=><NewsText key={t.id} text={t} frame={frame} end={beat.end} m={m}/>)}</AbsoluteFill>
      {m.theme.branding&&<div style={{position:'absolute',top:m.height*.203,left:m.width*.15,width:m.width*.7,textAlign:'center',fontFamily:'NewsPoppins',fontWeight:600,fontSize:Math.min(m.width,m.height)*.014,color:m.theme.secondary,zIndex:30}}>{m.theme.branding}</div>}
    </AbsoluteFill>
  </AbsoluteFill>;
};
