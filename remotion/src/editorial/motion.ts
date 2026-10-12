import {Event,Layer} from './types';
export const clamp=(v:number)=>Math.max(0,Math.min(1,v));
export const ease=(v:number)=>1-Math.pow(1-clamp(v),3);
export const progress=(e:Event,f:number)=>e.easing==='linear'?clamp((f-e.startFrame)/(e.endFrame-e.startFrame)):ease((f-e.startFrame)/(e.endFrame-e.startFrame));
export function stateAt(layer:Layer,events:Event[],frame:number){
  const s={x:0,y:0,scale:1,opacity:layer.opacity,assetId:layer.assetId,swapAsset:null as string|null,swap:0,value:layer.value,angle:-105,bounds:{...layer.bounds}};
  for(const e of events.filter(e=>e.targetIds.includes(layer.id)&&frame>=e.startFrame)){
    const t=progress(e,frame),index=e.targetIds.indexOf(layer.id);
    if(e.type==='focus_shift')s.scale=e.scaleFrom+((index===0?e.scaleTo:e.secondaryScale)-e.scaleFrom)*t;
    if(e.type==='settle'||e.type==='emphasis'){s.scale=e.scaleFrom+(e.scaleTo-e.scaleFrom)*t;s.y+=e.dy*(1-t);s.opacity*=e.opacityFrom+(e.opacityTo-e.opacityFrom)*t;}
    if(e.type==='transfer'||e.type==='context_change'){s.x+=e.dx*t;s.y+=e.dy*t;}
    if(e.type==='map_separate'){s.x+=e.dx*(index===0?-1:1)*t;s.y+=e.dy*(index===0?-1:1)*t;}
    if(e.type==='year_counter')s.value=frame>=e.endFrame?e.toValue:Math.round(e.fromValue+(e.toValue-e.fromValue)*t);
    if(e.type==='object_action')s.angle=e.angleFrom+(e.angleTo-e.angleFrom)*t;
    if(e.type==='representation_swap'){s.swapAsset=e.assetId;s.swap=t;}
    if(e.type==='fade')s.opacity*=e.opacityFrom+(e.opacityTo-e.opacityFrom)*t;
    if(e.type==='reframe'&&e.boundsFrom&&e.boundsTo){
      for(const key of ['x','y','w','h'] as const)s.bounds[key]=e.boundsFrom[key]+(e.boundsTo[key]-e.boundsFrom[key])*t;
    }
  }
  return s;
}
