import React from 'react';
import {useCurrentFrame,useVideoConfig,interpolate} from 'remotion';
// Brief animated layer over the opening scene; no additional title slide.

export const AutopilotHook:React.FC<{text:string}>=({text})=>{
 const frame=useCurrentFrame(),{fps}=useVideoConfig();
 const seconds=frame/fps;
 if(seconds>=2.8)return null;
 const enter=interpolate(seconds,[0,.45],[0,1],{extrapolateLeft:'clamp',extrapolateRight:'clamp'});
 const exit=interpolate(seconds,[2.3,2.8],[1,0],{extrapolateLeft:'clamp',extrapolateRight:'clamp'});
 return <div style={{position:'absolute',zIndex:900,left:'8%',right:'8%',top:'18%',padding:'24px 32px',
 background:'rgba(17,27,43,.94)',borderLeft:'8px solid #CBA96E',borderRadius:12,
 color:'#F7F5F0',fontFamily:'ProjectHERBrand, sans-serif',fontWeight:700,fontSize:64,lineHeight:1.14,
 textWrap:'balance',textAlign:'center',opacity:enter*exit,transform:`translateY(${(1-enter)*30}px)`}}>{text}</div>;
};
