import {Layer} from './types';
import {clamp,ease} from './motion';

// Deterministic cutout motion for story layers: entrance, drift, scale/tilt and exit are pure
// functions of the frame, so seeking never accumulates state. Elements enter staggered with their own parallax depth.
const backOut=(v:number)=>{const c=1.70158,t=clamp(v)-1;return 1+(c+1)*t*t*t+c*t*t;};
const entranceState=(kind:string,e:number,t:number)=>{
  switch(kind){
    case 'slide_left':return {x:-(1-e)*240,y:0,scale:1,opacity:Math.min(1,e*2.2)};
    case 'slide_right':return {x:(1-e)*240,y:0,scale:1,opacity:Math.min(1,e*2.2)};
    case 'pop':return {x:0,y:0,scale:.55+.45*backOut(e),opacity:Math.min(1,e*3)};
    case 'punch':return {x:0,y:0,scale:1.22-.22*e,opacity:Math.min(1,e*4)};
    case 'slam':return {x:Math.sin(t*2.3)*(1-e)*14,y:Math.cos(t*2.9)*(1-e)*10,scale:1+.6*(1-backOut(e)),opacity:Math.min(1,e*5)};
    case 'fade':return {x:0,y:0,scale:1,opacity:e};
    default:return {x:0,y:(1-e)*80,scale:.94+.06*e,opacity:Math.min(1,e*2)};
  }
};
export const cutoutMotionAt=(layer:Layer,frame:number,delay=0,depth?:number)=>{
  const mo=layer.motion;if(!mo)return {x:0,y:0,scale:1,rotate:0,opacity:1};
  const pending=frame<layer.startFrame+delay;
  const t=Math.max(0,frame-layer.startFrame-delay),span=Math.max(1,layer.endFrame-layer.startFrame);
  const life=clamp((frame-layer.startFrame)/span),e=ease(t/mo.entranceFrames);
  const raw=entranceState(mo.entrance,e,t);
  const en={...raw,x:raw.x*((mo.entranceTravel??240)/240)};
  const d=depth===undefined?1:.45+depth*1.1;
  const left=layer.endFrame-frame,exiting=mo.exit==='none'||!(mo.exitFrames??6)?0:clamp(1-left/(mo.exitFrames??6));
  const focus=mo.focusFrame===null||mo.focusFrame===undefined?0:Math.max(0,1-Math.abs(frame-mo.focusFrame-5)/12);
  const focusScale=1+((mo.focusScale??1)-1)*ease(focus);
  return {x:en.x+mo.driftX*life*d,y:en.y+mo.driftY*life*d,scale:en.scale*focusScale*(1+(mo.scaleTo-1)*life)*(mo.exit==='shrink'?1-.06*exiting:1),
    rotate:mo.tilt*life,opacity:(pending?0:(mo.initialOpacity??0)+(1-(mo.initialOpacity??0))*en.opacity)*(1-(mo.exit==='none'?0:.9*exiting*exiting))};
};

