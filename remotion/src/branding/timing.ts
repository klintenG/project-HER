import {z} from 'zod';
export const BrandingSchema=z.object({
  enabled:z.boolean().default(true),theme:z.literal('projecther').default('projecther'),
  alwaysOnCornerLogo:z.boolean().default(true),showTaglineWhenReadable:z.boolean().default(true),
  creditEnabled:z.boolean().default(true),creditHoldSeconds:z.number().min(3).max(5).default(4),
  creditWindowStrategy:z.literal('midTimeline').default('midTimeline'),
  protectiveOverlayEnabled:z.boolean().default(true),protectiveOverlayOccurrences:z.number().int().min(0).max(6).default(2),
  protectiveOverlayHoldSeconds:z.number().min(3).max(5).default(4),
  protectiveOverlayOpacityRange:z.tuple([z.number().min(.08).max(.14),z.number().min(.08).max(.14)]).default([.08,.12]),
  deterministicSeed:z.string().default('projecther'),contrast:z.enum(['dark','light']).default('dark'),
  creditBottomRatio:z.number().min(.04).max(.3).default(.09),
  outro:z.object({enabled:z.boolean().default(true),durationSeconds:z.number().min(2).max(3).default(2.7),theme:z.enum(['midnightNavy','ivory','softBlur']).default('midnightNavy')}).default({}),
});
export type BrandingInput=z.input<typeof BrandingSchema>;
export const config=(input?:BrandingInput)=>BrandingSchema.parse(input??{});
export const outroFrames=(fps:number,input?:BrandingInput)=>{const c=config(input);return c.enabled&&c.outro.enabled?Math.round(c.outro.durationSeconds*fps):0;};
export type Event={kind:'credit'|'protective';start:number;end:number;fade:number;hold:number;anchor:number;opacity:number};
export type QuietWindow={start:number;end:number};
export function schedule(story:number,fps:number,input?:BrandingInput,windows:QuietWindow[]=[]):Event[]{
 const c=config(input);if(!c.enabled||story/fps<15)return [];
 let seed=2166136261;for(const ch of c.deterministicSeed)seed=Math.imul(seed^ch.charCodeAt(0),16777619)>>>0;
 const events:Event[]=[];const gap=Math.ceil(1.75*fps),margin=Math.ceil(2*fps);
 const place=(kind:Event['kind'],fraction:number,index:number)=>{
  const fade=Math.round((kind==='credit'?.45:.5)*fps),hold=Math.round((kind==='credit'?c.creditHoldSeconds:c.protectiveOverlayHoldSeconds)*fps),length=hold+2*fade;
  const target=Math.round(story*fraction-length/2);
  const candidates=Array.from({length:Math.max(0,story-length-2*margin+1)},(_,i)=>i+margin)
   .filter(start=>kind!=='credit'||Math.abs((start+length/2)/story-.5)<=.05)
   .filter(start=>events.every(e=>start>=e.end+gap||start+length+gap<=e.start));
  const score=(start:number)=>Math.abs(start-target)+(windows.length&&!windows.some(w=>start>=w.start&&start+length<=w.end)?story:0);
  candidates.sort((a,b)=>score(a)-score(b)||a-b);if(!candidates.length)return;
  const lo=Math.min(...c.protectiveOverlayOpacityRange),hi=Math.max(...c.protectiveOverlayOpacityRange);
  events.push({kind,start:candidates[0],end:candidates[0]+length,fade,hold,anchor:(seed+index)%2,opacity:lo+(hi-lo)*(seed%997)/997});
 };
 if(c.creditEnabled)place('credit',.5,0);
 if(c.protectiveOverlayEnabled&&(story/fps>=30||!events.length)){
  const count=story/fps<30?Math.min(1,c.protectiveOverlayOccurrences):c.protectiveOverlayOccurrences;
  for(let i=0;i<count;i++)place('protective',(i+1)/(count+1)+(i<count/2?-.1:.1),i);
 }
 return events.sort((a,b)=>a.start-b.start);
}
export function screenFrames(s:{duration:number;audio_duration?:number;word_timings?:{end:number}[]},fps:number){return Math.max(1,Math.ceil(Math.max(s.duration,s.audio_duration??0,...(s.word_timings??[]).map(w=>w.end))*fps));}
export const classicFrames=(p:{screens:Parameters<typeof screenFrames>[0][];fps:number;source_duration_frames?:number})=>p.source_duration_frames??p.screens.reduce((n,s)=>n+screenFrames(s,p.fps),0);
