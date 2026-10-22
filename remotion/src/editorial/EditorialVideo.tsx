import {ProjectHERBrandingController,useBrandClosing} from '../branding/Branding';
import {BrandingInput} from '../branding/timing';
import React,{useEffect,useMemo,useState} from 'react';
import {AbsoluteFill,Audio,Sequence,Img,staticFile,useCurrentFrame,delayRender,continueRender,cancelRender} from 'remotion';
import {Timeline,Layer,Word,Bounds} from './types';
import {validateTimeline} from './contract';
import {clamp,stateAt} from './motion';

const url=(s:string)=>staticFile(s);
const color='#414249';
// Label contexts only: historical quotations and narration are never censored.
const cleanName=(text:string)=>text.replace(/(?:\s*\n\s*|\s+)(?:AI[- ]?generated(?: illustration)?|AI illustration|illustration|stock (?:image|photo)|generated image|concept art|visual)\s*$/i,'').trim();

const PhraseBlock:React.FC<{layer:Layer;words:Map<string,Word>;frame:number;toneColor:string}>=({layer,words,frame,toneColor})=>{
  const p=layer.phrase!;
  // Keep every word in the final geometry from the first frame. Opacity alone
  // changes. Line breaks are measured with the same bundled font in Python.
  const common={fontFamily:'EditorialPoppins',fontWeight:p.weight,fontSize:p.size,lineHeight:1.19,color:toneColor,textAlign:p.align} as const;
  if(p.label)return <div style={{...common,whiteSpace:'pre-line'}}>{cleanName(p.label)}</div>;
  const first=words.get(p.wordIds[0])!.start*30-p.anticipationFrames;
  return <div style={common}>{p.lines.map((line,n)=><div key={n} style={{whiteSpace:'nowrap',minHeight:p.size*1.19}}>{line.map((id,i)=>{
    const w=words.get(id)!;const onset=(p.mode==='phrase_reveal'||p.mode==='connector')?first:w.start*30-p.anticipationFrames;
    const t=clamp((frame-onset)/6);const eased=1-Math.pow(1-t,3);
    return <span key={id} style={{display:'inline-block',visibility:frame>=onset?'visible':'hidden',clipPath:`inset(0 0 ${(1-eased)*100}% 0)`,fontWeight:p.emphasis.includes(id)?700:p.weight,transform:`translateY(${(1-eased)*18}px)`}}>{w.text}{i<line.length-1?'\u00a0':''}</span>;
  })}</div>)}</div>;
};

const Box:React.FC<{angle:number}>=({angle})=><div style={{width:'100%',height:'100%',perspective:1100}}>
  <div style={{position:'absolute',left:'8%',top:'26%',width:'84%',height:'58%',transform:'rotateX(30deg) rotateZ(-6deg)',transformStyle:'preserve-3d'}}>
    <div style={{position:'absolute',inset:0,background:'linear-gradient(120deg,#9f7c52,#4c392c)',border:'12px solid #8f6d47',boxShadow:'inset 0 0 35px #281f1e'}}/>
    <div style={{position:'absolute',left:'40%',top:'34%',width:'20%',height:'30%',background:'linear-gradient(130deg,#eef1f4,#92a9bf 50%,#f2f4f6)',clipPath:'polygon(24% 0,76% 0,100% 40%,50% 100%,0 40%)'}}/>
    <div style={{position:'absolute',inset:0,transformOrigin:'50% 0%',transform:`rotateX(${angle}deg)`,background:'linear-gradient(145deg,#b18e60,#654a31)',border:'7px solid #b39973',backfaceVisibility:'visible',boxShadow:'0 8px 14px #0002'}}>
      <div style={{position:'absolute',left:'43%',bottom:10,width:'14%',height:12,background:'#c8b489'}}/>
    </div>
  </div>
</div>;

const SemanticRelation:React.FC<{timeline:Timeline;frame:number;words:Map<string,Word>}>=({timeline,frame,words})=>{
  const beat=timeline.beats.find(b=>b.startFrame<=frame&&frame<b.endFrame);
  if(!beat)return null;
  const phrase=timeline.layers.find(l=>beat.layerIds.includes(l.id)&&l.role==='phrase')?.phrase;
  const trigger=phrase?.wordIds.map(id=>words.get(id)!).find(w=>/pressure|intensif|sent|dispatch|fought|defeat|rivalr|fractur|weaken/i.test(w.text));
  if(!trigger)return null;
  const t=clamp((frame-trigger.start*30)/24),e=1-Math.pow(1-t,3);
  const split=beat.template==='split-outcome'&&/rivalr|fractur|weaken/i.test(trigger.text);
  if(beat.template!=='cause-effect'&&!split)return null;
  // Abstract relationship diagrams, never geographic routes or battle evidence.
  return <svg aria-label={split?'Symbolic alliance fracture':'Symbolic opposing pressure'} width={1080} height={1920} style={{position:'absolute',inset:0,opacity:t*.45,zIndex:1}}>
    <defs><marker id="editorial-arrow" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M 0 0 L 10 5 L 0 10 z" fill="#6a6a70"/></marker></defs>
    {split?<>
      <path d={`M 540 620 Q 540 650 ${540-250*e} 695`} fill="none" stroke="#6a6a70" strokeWidth={4} markerEnd="url(#editorial-arrow)"/>
      <path d={`M 540 620 Q 540 650 ${540+250*e} 695`} fill="none" stroke="#6a6a70" strokeWidth={4} markerEnd="url(#editorial-arrow)"/>
    </>:<>
      <path d={`M 70 965 L ${70+100*e} 965`} fill="none" stroke="#6a6a70" strokeWidth={5} markerEnd="url(#editorial-arrow)"/>
      <path d={`M 1010 965 L ${1010-100*e} 965`} fill="none" stroke="#6a6a70" strokeWidth={5} markerEnd="url(#editorial-arrow)"/>
    </>}
  </svg>;
};

const EditorialStory:React.FC<Timeline>=(props)=>{
  const closing=useBrandClosing();const m=useMemo(()=>validateTimeline(props),[props]);const frame=useCurrentFrame();
  const words=useMemo(()=>new Map(m.words.map(w=>[w.id,w])),[m]);
  const assets=useMemo(()=>new Map(m.assets.map(a=>[a.id,a])),[m]);
  const reference=m.editorialStyleVersion==='reference-v2';
  const current=m.sections.find(s=>s.start*30<=frame&&s.end*30>frame);
  const beat=m.beats.find(b=>b.startFrame<=frame&&frame<b.endFrame);
  const progress=current?clamp((frame-current.start*30)/Math.max(1,(current.end-current.start)*30)):0;
  const darkness=reference&&beat?.template==='environment-change'&&/dark|night|eclips|sun disappeared|light vanished/i.test(current?.text??'');
  const sunrise=reference&&beat?.template==='dramatic-reveal'&&/sun|light|day|dawn|radiant/i.test(current?.text??'');
  const toneColor=darkness?'#f9f7f1':color;
  const background=darkness?`radial-gradient(ellipse at 50% 44%,#888b94 0%,#626977 ${Math.round(50+progress*15)}%,#273349 100%)`:sunrise?`radial-gradient(circle at 53% 45%,#fff8c9 0%,#f3da8a ${Math.round(22+progress*34)}%,#dbb36f 78%,#8a755f 100%)`:reference?'radial-gradient(ellipse at 50% 44%,#f1f0f2 0%,#dedde1 70%,#cbc9ce 100%)':'radial-gradient(ellipse 90% 50% at 50% 50%,#eeeef1 0%,#e2e0e5 35%,#b2b0b7 100%)';
  const [handle]=useState(()=>delayRender('Loading deterministic editorial fonts'));
  useEffect(()=>{
    const fonts=[new FontFace('EditorialPoppins',`url("${url(m.fonts.semibold)}")`,{weight:'600'}),new FontFace('EditorialPoppins',`url("${url(m.fonts.bold)}")`,{weight:'700'})];
    Promise.all(fonts.map(f=>f.load())).then(loaded=>{loaded.forEach(f=>document.fonts.add(f));continueRender(handle);}).catch(cancelRender);
    return()=>fonts.forEach(f=>document.fonts.delete(f));
  },[handle,m.fonts.semibold,m.fonts.bold]);
  const draw=(layer:Layer,parentBounds?:Bounds):React.ReactNode=>{
    if(frame<layer.startFrame||frame>=layer.endFrame)return null;
    // Complete captions replace editorial spoken text; identity labels remain.
    if((closing||m.subtitleMode==='complete')&&layer.phrase?.wordIds.length)return null;
    const s=stateAt(layer,m.events,frame),b=parentBounds?{...s.bounds,y:parentBounds.h+18,w:parentBounds.w}:s.bounds;
    const asset=s.assetId?assets.get(s.assetId):null;
    const style:React.CSSProperties={position:'absolute',left:b.x,top:b.y,width:b.w,height:b.h,zIndex:layer.z,
      transformOrigin:layer.origin,transform:`translate(${s.x}px,${s.y}px) scale(${s.scale})`,opacity:s.opacity};
    const imageStyle:React.CSSProperties={width:'100%',height:'100%',objectFit:'contain',maskImage:layer.mask==='lower_fade'?'linear-gradient(to bottom,black 0%,black 75%,transparent 100%)':undefined};
    return <div key={layer.id} style={style}>
      {asset&&layer.shadow&&<>
        {layer.role!=='map'&&<div style={{position:'absolute',left:'-6%',bottom:'-1%',width:'100%',height:'10%',borderRadius:'50%',background:'#252735',opacity:.1,filter:'blur(15px)'}}/>}
        <Img src={url(asset.path)} style={{...imageStyle,position:'absolute',inset:0,transformOrigin:'50% 97%',transform:'skewX(48deg) scaleY(.24)',filter:'brightness(0) blur(5px)',opacity:.13*(1-s.swap)}}/>
        {s.swapAsset&&<Img src={url(assets.get(s.swapAsset)!.path)} style={{...imageStyle,position:'absolute',inset:0,transformOrigin:'50% 97%',transform:'skewX(48deg) scaleY(.24)',filter:'brightness(0) blur(5px)',opacity:.13*s.swap}}/>}
      </>}
      {asset&&<Img src={url(asset.path)} style={{...imageStyle,opacity:1-s.swap}}/>}
      {s.swapAsset&&<Img src={url(assets.get(s.swapAsset)!.path)} style={{...imageStyle,position:'absolute',inset:0,opacity:s.swap}}/>}
      {layer.phrase&&<PhraseBlock layer={layer} words={words} frame={frame} toneColor={toneColor}/>}
      {layer.role==='year'&&<div style={{fontFamily:'EditorialPoppins',fontSize:170,fontWeight:700,color,textAlign:'center',fontVariantNumeric:'tabular-nums'}}>{s.value}</div>}
      {layer.role==='box'&&<><div style={{position:'absolute',left:'-5%',top:'70%',width:'96%',height:'12%',borderRadius:'50%',background:'#252735',opacity:.12,filter:'blur(15px)'}}/><Box angle={s.angle}/></>}
      {m.layers.filter(child=>child.parentId===layer.id).map(child=>draw(child,b))}
    </div>;
  };
  const captionWords=current?current.wordIds.map(id=>words.get(id)!):[];
  const active=Math.max(0,captionWords.reduce((last,w,i)=>w.start*30<=frame?i:last,-1));const chunk=captionWords.slice(Math.floor(active/6)*6,Math.floor(active/6)*6+6);
  return <AbsoluteFill style={{background,overflow:'hidden'}}>
    {!closing&&m.audio.map((a,i)=><Sequence key={i} from={a.offsetFrames}><Audio src={url(a.path)} volume={a.gain}/></Sequence>)}
    {reference&&m.subtitleMode!=='complete'&&<SemanticRelation timeline={m} frame={frame} words={words}/>}
    {m.layers.filter(l=>!l.parentId).map(layer=>draw(layer))}
    {!closing&&(m.subtitleMode==='complete'||(m.narrationDriven&&!reference))&&chunk.length>0&&<div style={{position:'absolute',left:90,top:reference?1530:m.narrationDriven?1480:360,width:900,color:toneColor,fontFamily:'EditorialPoppins',fontSize:m.narrationDriven?48:60,fontWeight:600,textAlign:'center',lineHeight:1.3}}>{chunk.map((w,i)=><React.Fragment key={w.id}><span style={{fontWeight:m.narrationDriven&&w.start*30<=frame&&w.end*30>frame?700:600}}>{w.text}</span>{i<chunk.length-1?' ':''}</React.Fragment>)}</div>}
  </AbsoluteFill>;
};

export const EditorialVideo:React.FC<Timeline & {branding?:BrandingInput}>=({branding,...story})=><ProjectHERBrandingController storyFrames={story.durationInFrames} branding={{creditEnabled:false,protectiveOverlayEnabled:false,...branding}} regions={story.layers.filter(l=>l.phrase&&!l.parentId).map(l=>({start:l.startFrame,end:l.endFrame,x:l.bounds.x/story.width,y:l.bounds.y/story.height,w:l.bounds.w/story.width,h:l.bounds.h/story.height}))} windows={story.beats.filter(b=>b.template!=="final-reveal").map(b=>({start:b.startFrame+15,end:b.endFrame-15}))}><EditorialStory {...story}/></ProjectHERBrandingController>;
