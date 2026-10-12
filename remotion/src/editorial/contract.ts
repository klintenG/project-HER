import Ajv from 'ajv';
import schema from './schema.json';
import {Timeline} from './types';
const structural=new Ajv({allErrors:true, jsonPointers:true}).compile(schema);
const assert=(ok:unknown,message:string)=>{if(!ok)throw new Error('Editorial timeline: '+message);};
export function validateTimeline(value:unknown):Timeline {
  assert(structural(value),JSON.stringify(structural.errors));
  const m=value as Timeline;
  const registry=<T extends {id:string}>(rows:T[])=>{assert(new Set(rows.map(r=>r.id)).size===rows.length,'duplicate IDs');return new Map(rows.map(r=>[r.id,r]));};
  const words=registry(m.words),sections=registry(m.sections),entities=registry(m.entities),assets=registry(m.assets),layers=registry(m.layers);
  registry(m.beats);registry(m.events);
  assert(m.script===m.sections.map(s=>s.text).join(' '),'script/section mismatch');
  const masters=m.audio.filter(a=>a.kind==='master');assert(masters.length===1&&masters[0].offsetFrames===0,'master audio');
  m.audio.forEach(a=>assert(a.duration*30+a.offsetFrames<=m.durationInFrames+.01,'truncated audio'));
  let end=0;
  for(const w of m.words){assert(sections.has(w.sectionId)&&w.start>=end-.001&&w.end>w.start&&w.end<=masters[0].duration+.01,'alignment');end=w.end;}
  for(const s of m.sections){assert(s.wordIds.length&&s.end>s.start&&s.end<=masters[0].duration+.01,'section');assert(s.wordIds.every(id=>words.has(id)&&words.get(id)!.sectionId===s.id),'section words');assert(s.wordIds.map(id=>words.get(id)!.text).join('').replace(/ /g,'')===s.text.replace(/ /g,''),'display script');assert(s.wordIds.every(id=>words.get(id)!.start>=s.start-.001&&words.get(id)!.end<=s.end+.001),'word outside section');}
  assert(JSON.stringify(m.sections.flatMap(s=>s.wordIds))===JSON.stringify(m.words.map(w=>w.id)),'word coverage');
  m.entities.forEach(e=>assert(e.assetIds.every(id=>assets.get(id)?.entityId===e.id),'entity asset'));
  m.assets.forEach(a=>assert(entities.has(a.entityId)&&(a.factual||a.fallback),'asset identity/fallback'));
  for(const row of [...m.layers,...m.events,...m.beats,...m.transitions])assert(row.startFrame<row.endFrame&&row.endFrame<=m.durationInFrames,'interval');
  for(const l of m.layers){
    assert(!l.entityId||entities.has(l.entityId),'layer entity');assert(!l.assetId||assets.get(l.assetId)?.entityId===l.entityId,'layer asset');
    if(['subject','object','map','photo','document','shadow'].includes(l.role))assert(l.assetId,'visual asset required');
    if(['heading','phrase','label'].includes(l.role))assert(l.phrase,'phrase required');
    if(l.role==='year')assert(l.value!==null,'year value');
    const p=l.parentId?layers.get(l.parentId):null;
    assert(!l.parentId||(p&&!p.parentId&&p.id!==l.id&&p.startFrame<=l.startFrame&&p.endFrame>=l.endFrame),'parent');
    assert((l.anchor==='entity')===!!l.parentId,'anchor');assert(l.bounds.x+l.bounds.w<=1080&&l.bounds.y+l.bounds.h<=1920,'bounds');
    if(l.phrase){const q=l.phrase;assert(q.wordIds.every(id=>words.has(id))&&q.emphasis.every(id=>q.wordIds.includes(id)),'phrase refs');assert(JSON.stringify(q.lines.flat())===JSON.stringify(q.wordIds),'line breaks');assert(!!q.wordIds.length!==!!q.label,'label/word distinction');assert(q.wordIds.every(id=>words.get(id)!.start*30<l.endFrame),'phrase exits early');}
  }
  for(const b of m.beats)assert(b.layerIds.every(id=>layers.has(id))&&b.sectionIds.every(id=>sections.has(id)),'beat refs');
  for(const e of m.events){
    assert(e.targetIds.every(id=>layers.has(id)),'event refs');const ls=e.targetIds.map(id=>layers.get(id)!);
    assert(ls.every(l=>l.startFrame<=e.startFrame&&l.endFrame>=e.endFrame),'event outside layer');
    if(['focus_shift','map_separate'].includes(e.type))assert(ls.length>=2,'two targets required');
    if(e.type==='year_counter')assert(ls.every(l=>l.role==='year'),'year target');
    if(e.type==='object_action')assert(ls.every(l=>l.role==='box'),'box target');
    if(e.type==='map_separate')assert(ls.every(l=>assets.get(l.assetId!)?.preparation==='vetted_geometry'),'map provenance');
    if(e.type==='representation_swap')assert(ls.every(l=>assets.get(e.assetId!)?.entityId===l.entityId),'swap identity');
    if(e.type==='reframe')assert(ls.length===1&&e.boundsFrom&&e.boundsTo&&[e.boundsFrom,e.boundsTo].every(b=>b.x+b.w<=1080&&b.y+b.h<=1920),'reframe bounds');
  }
  for(const t of m.transitions)assert([...t.persist,...t.enter,...t.leave].every(id=>layers.has(id)),'transition refs');
  assert(m.beats.length&&m.beats[0].startFrame===0&&Math.max(...m.beats.map(b=>b.endFrame))===m.durationInFrames,'coverage');
  m.beats.slice(1).forEach((b,i)=>assert(b.startFrame<=m.beats[i].endFrame,'visual gap'));
  if(m.narrationDriven){
    m.beats.slice(1).forEach((b,i)=>assert(b.startFrame===m.beats[i].endFrame,'atomic partition'));
    const visuals=m.layers.filter(l=>l.assetId);
    for(const frame of new Set(visuals.map(l=>l.startFrame))){
      const active=visuals.filter(l=>l.startFrame<=frame&&frame<l.endFrame);
      assert(active.length<=3&&new Set(active.map(l=>l.entityId)).size===active.length,'conflicting atomic entities');
    }
    for(const l of visuals){
      const events=m.events.filter(e=>e.targetIds.includes(l.id)&&['settle','emphasis','focus_shift'].includes(e.type)).sort((a,b)=>a.startFrame-b.startFrame);
      events.slice(1).forEach((e,i)=>assert(events[i].endFrame<=e.startFrame,'conflicting atomic scale'));
    }
    const transitions=[...m.transitions].sort((a,b)=>a.startFrame-b.startFrame);
    transitions.slice(1).forEach((t,i)=>assert(transitions[i].endFrame<=t.startFrame,'overlapping atomic transitions'));
  }
  return m;
}
export async function validateTimelineHash(value:unknown){
  const m=validateTimeline(value);
  const digest=await crypto.subtle.digest('SHA-256',new TextEncoder().encode(m.script));
  const hash=Array.from(new Uint8Array(digest)).map(v=>v.toString(16).padStart(2,'0')).join('');
  assert(hash===m.scriptHash,'stale script hash');
  return m;
}
