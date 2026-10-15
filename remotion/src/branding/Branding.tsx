import React,{createContext,useContext,useEffect,useState,useMemo} from 'react';
import {AbsoluteFill,Freeze,Sequence,useCurrentFrame,useVideoConfig,staticFile,delayRender,continueRender,cancelRender,interpolateColors} from 'remotion';
import {BrandingInput,config,schedule,QuietWindow,Event} from './timing';
export type ProtectedRegion={start:number;end:number;x:number;y:number;w:number;h:number};
const Closing=createContext(false);
export const useBrandClosing=()=>useContext(Closing);
const clamp=(n:number)=>Math.max(0,Math.min(1,n));
const smooth=(n:number)=>{const t=clamp(n);return t*t*(3-2*t);};
const navy='#111B2B',gold='#CBA96E',ivory='#F7F5F0';
export const ProjectHERBrandMark:React.FC<{width:number;color:string;tagline?:boolean;accent?:string}>=({width,color,tagline=true,accent=gold})=><svg width={width} height={width*(tagline?.31:.1833)} viewBox={tagline?"0 0 240 74":"0 8 240 44"} aria-label="projectHER" style={{display:'block',overflow:'visible'}}>
 <text textLength="240" lengthAdjust="spacingAndGlyphs" y="43" fontFamily="ProjectHERBrand" fontSize="40" letterSpacing="-1.6" fill={color}><tspan fontWeight="500">project</tspan><tspan fontWeight="700" fill={accent}>HER</tspan></text>
 {tagline&&<text x="120" y="67" textAnchor="middle" fontFamily="ProjectHERBrand" fontWeight="500" fontSize="11" letterSpacing="3.4" fill={color}>STORIES IN MOTION</text>}
</svg>;
const envelope=(e:Event,f:number)=>smooth((f-e.start)/e.fade)*smooth((e.end-1-f)/e.fade);
export const ProjectHERMadeWithCredit:React.FC<{event:Event;frame:number;color:string;bottom:number}>=({event,frame,color,bottom})=>{
 const {width,height}=useVideoConfig(),s=Math.min(width,height)/1080,p=envelope(event,frame);
 return <div style={{position:'absolute',bottom:height*bottom,left:0,width:'100%',display:'flex',alignItems:'center',justifyContent:'center',gap:20*s,opacity:p,transform:`translateY(${18*s*(1-p)}px)`,color,fontFamily:'ProjectHERBrand',fontWeight:500,lineHeight:1,fontSize:24*s}}>
 <span style={{width:100*s*p,height:s,background:color,opacity:.5}}/><span>Made with</span><ProjectHERBrandMark width={144*s} color={color} tagline={false}/><span style={{width:100*s*p,height:s,background:color,opacity:.5}}/>
 </div>;
};
export const ProjectHERProtectiveOverlay:React.FC<{event:Event;frame:number;color:string;regions:ProtectedRegion[]}>=({event,frame,color,regions})=>{
 const {width,height}=useVideoConfig();const drift=16*clamp((frame-event.start)/Math.max(1,event.end-event.start));
 const mask=`<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${width} ${height}"><rect width="100%" height="100%" fill="white"/>${regions.filter(r=>r.start<=frame&&frame<r.end).map(r=>`<rect x="${r.x*width}" y="${r.y*height}" width="${r.w*width}" height="${r.h*height}" rx="12" fill="black"/>`).join('')}</svg>`;
 return <AbsoluteFill style={{maskImage:`url("data:image/svg+xml,${encodeURIComponent(mask)}")`,maskSize:'100% 100%',maskMode:'luminance'}}><div style={{position:'absolute',left:width*.5+drift,top:height*(event.anchor?.58:.46),transform:'translate(-50%,-50%) rotate(-32deg)',opacity:envelope(event,frame)*event.opacity}}><ProjectHERBrandMark width={Math.min(width*.9,height*.68)} color={color} accent={color} tagline={false}/></div></AbsoluteFill>;
};
export const ProjectHERBrandingController:React.FC<{storyFrames:number;branding?:BrandingInput;windows?:QuietWindow[];regions?:ProtectedRegion[];children:React.ReactNode}>=({storyFrames,branding,windows,regions=[],children})=>{
 const frame=useCurrentFrame(),{width,height,fps}=useVideoConfig(),c=config(branding);
 const events=useMemo(()=>schedule(storyFrames,fps,branding,windows),[storyFrames,fps,branding,windows]);
 const [handle]=useState(()=>delayRender('ProjectHER bundled brand typography'));
 useEffect(()=>{if(!c.enabled){continueRender(handle);return;}const fonts=[500,700].map(weight=>new FontFace('ProjectHERBrand',`url("${staticFile('branding/Poppins-'+(weight===500?'Medium':'Bold')+'.ttf')}")`,{weight:String(weight)}));Promise.all(fonts.map(f=>f.load())).then(fs=>{fs.forEach(f=>document.fonts.add(f));continueRender(handle);}).catch(cancelRender);return()=>fonts.forEach(f=>document.fonts.delete(f));},[handle,c.enabled]);
 if(!c.enabled)return <>{children}</>;
 const closing=c.outro.enabled&&frame>=storyFrames,t=(frame-storyFrames)/fps,motion=smooth(t/.8),bg=smooth((t-.1)/.95);
 const s=Math.min(width,height)/1080,corner=220*s,size=corner*(1+1.3*motion);
 const x=(width-75*s-corner/2)*(1-motion)+width/2*motion;
 const y=(105*s+corner*.155)*(1-motion)+height*.48*motion;
 const initial=c.contrast==='light'?ivory:navy,final=c.outro.theme==='ivory'?navy:ivory;
 const color=interpolateColors(motion,[0,1],[initial,final]);
 const credit=events.find(e=>e.kind==='credit');
 const creditRegions=credit?regions.filter(r=>r.start<credit.end&&r.end>credit.start):[];
 // Reserve one stable row for the entire credit, even across a scene cut.
 const creditBottom=[c.creditBottomRatio,.12,.16,.20,.24,.28].find(bottom=>creditRegions.every(r=>1-bottom<r.y||1-bottom-.025>r.y+r.h))??c.creditBottomRatio;
 const event=!closing?events.find(e=>frame>=e.start&&frame<e.end):undefined;
 return <AbsoluteFill>
  <Sequence durationInFrames={storyFrames}>{children}</Sequence>
  {closing&&<Closing.Provider value={true}><Freeze frame={storyFrames-1}><AbsoluteFill style={{filter:`blur(${bg*10*s}px)`}}>{children}</AbsoluteFill></Freeze></Closing.Provider>}
  {closing&&<AbsoluteFill style={{opacity:bg,background:c.outro.theme==='ivory'?'radial-gradient(ellipse at 50% 48%,#fffdf8,#F7F5F0)':c.outro.theme==='softBlur'?'rgba(17,27,43,.88)':'radial-gradient(ellipse at 50% 48%,#19283e,#111B2B 72%)'}}/>}
  <AbsoluteFill style={{zIndex:1000,pointerEvents:'none',overflow:'hidden'}}>
   {event?.kind==='credit'&&<ProjectHERMadeWithCredit event={event} frame={frame} color={initial} bottom={creditBottom}/>}
   {event?.kind==='protective'&&<ProjectHERProtectiveOverlay event={event} frame={frame} color={initial} regions={regions}/>}
   {(c.alwaysOnCornerLogo||closing)&&<div style={{position:'absolute',left:x,top:y,transform:'translate(-50%,-50%)'}}><ProjectHERBrandMark width={size} color={color} tagline={c.showTaglineWhenReadable&&(corner>=130||closing)}/>
    {closing&&<div style={{position:'absolute',top:'120%',left:'43%',width:`${14*smooth((t-.65)/.55)}%`,height:2*s,background:gold,opacity:smooth((t-.65)/.55)}}/>}
   </div>}
  </AbsoluteFill>
 </AbsoluteFill>;
};
