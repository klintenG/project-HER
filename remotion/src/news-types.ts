import {BrandingSchema} from './branding/timing';
/** Runtime Zod validation generated from the same field schema as Pydantic. */
import {z} from 'zod';
import {newsJSONSchema, Manifest} from './news-contract';
export type {Manifest, Beat, Layer, Text, Rect} from './news-contract';
function build(s: any): z.ZodTypeAny {
  if (s.$ref) return z.lazy(() => build((newsJSONSchema.$defs as any)[s.$ref.split('/').pop()]));
  if (s.const !== undefined) return z.literal(s.const);
  if (s.enum) return z.union(s.enum.map((v: any) => z.literal(v)) as [z.ZodTypeAny,z.ZodTypeAny,...z.ZodTypeAny[]]);
  if (s.anyOf) return z.union(s.anyOf.map(build) as [z.ZodTypeAny,z.ZodTypeAny,...z.ZodTypeAny[]]);
  if (s.type === 'null') return z.null();
  if (s.type === 'string') {let v=z.string(); if (s.minLength) v=v.min(s.minLength); if(s.pattern) v=v.regex(new RegExp(s.pattern)); return v;}
  if (s.type === 'boolean') return z.boolean();
  if (s.type === 'integer' || s.type === 'number') {
    let v=z.number().finite(); if(s.type==='integer') v=v.int();
    if(s.minimum!==undefined) v=v.min(s.minimum); if(s.maximum!==undefined) v=v.max(s.maximum);
    if(s.exclusiveMinimum!==undefined) v=v.gt(s.exclusiveMinimum); return v;
  }
  if (s.type === 'array') {let v=z.array(build(s.items)); if(s.minItems!==undefined)v=v.min(s.minItems); if(s.maxItems!==undefined)v=v.max(s.maxItems); return v;}
  if (s.type === 'object') {
    if (!s.properties) return z.record(build(s.additionalProperties || {}));
    const fields: Record<string,z.ZodTypeAny>={};
    for (const [key,value] of Object.entries(s.properties)) {const v=build(value); const field=value as any; fields[key]=(s.required||[]).includes(key)?v:('default' in field?v.default(field.default):v.optional());}
    return z.object(fields).strict();
  }
  return z.unknown();
}
export const NewsPropsSchema = (build(newsJSONSchema) as z.AnyZodObject).extend({branding:BrandingSchema.optional()});
export const NewsManifestSchema = (NewsPropsSchema as unknown as z.ZodType<Manifest>).superRefine((m,ctx)=>{
  const fail=(message:string)=>ctx.addIssue({code:z.ZodIssueCode.custom,message});
  const claims=new Set(m.evidence.claims.map(c=>c.id)); const sources=new Map(m.evidence.sources.map(s=>[s.id,s]));
  const entities=new Set(m.script.entities.map(e=>e.id)); const sentences=new Set(m.script.sentences.map(s=>s.id));
  const assets=new Map(m.assets.map(a=>[a.id,a])); const targets=new Set<string>(); const covered=new Set<string>();
  if(assets.size!==m.assets.length || sources.size!==m.evidence.sources.length || claims.size!==m.evidence.claims.length || entities.size!==m.script.entities.length || sentences.size!==m.script.sentences.length) fail('Duplicate IDs');
  const usedEntities=new Set(m.script.sentences.flatMap(s=>s.entity_ids));if(usedEntities.size!==entities.size||[...entities].some(id=>!usedEntities.has(id)))fail('Unused or missing concrete entity');
  if(m.script.narration!==m.script.sentences.map(s=>s.text).join(' '))fail('Narration differs from sentences');
  if(Math.abs(m.duration_frames/m.fps-m.audio.duration)>1/m.fps+.001)fail('Audio duration mismatch');
  for(const c of m.evidence.claims) for(const id of c.source_ids) if(!c.excerpts[id]?.trim() || !sources.get(id)?.text.includes(c.excerpts[id]))fail('Invalid evidence excerpt');
  for(const a of m.assets) {
    if(!entities.has(a.entity_id))fail('Unknown asset entity');
    const entity=m.script.entities.find(e=>e.id===a.entity_id);
    if(a.origin==='photo'&&(entity?.identity!=='real'||a.illustrative||!a.identity_verified||!a.source_url||!a.reference_entity||!a.license||!a.attribution))fail('Unattributed actual reference photo');
    if(a.origin==='reference_edit'&&(!a.illustrative||a.identity_verified||!a.reference_url||!a.image_model))fail('Invalid reference edit provenance');
  }
  for(const s of m.script.sentences) if(s.claim_ids.some(id=>!claims.has(id)) || s.entity_ids?.some(id=>!entities.has(id)))fail('Unknown sentence claim/entity');
  for(const boundaries of [m.audio.words||[],m.audio.phrases]) {let previous=0; for(const b of boundaries){if(!sentences.has(b.sentence_id)||b.start<previous-.001||b.end<=b.start||b.end>m.audio.duration+.05)fail('Invalid audio boundary'); previous=b.end;}}
  let previous=0;
  for(const b of m.beats){
    if(b.start!==previous||b.end<=b.start||b.end>m.duration_frames)fail('Invalid beat timeline'); previous=b.end;
    for(const sid of b.sentence_ids){if(!sentences.has(sid))fail('Unknown beat sentence'); covered.add(sid);}
    const represented=new Set(b.layers?.map(l=>l.entity_id));
    for(const s of m.script.sentences.filter(s=>b.sentence_ids.includes(s.id)))if(s.entity_ids?.some(id=>!represented.has(id)))fail('Missing essential subject');
    const rectangles=[...b.texts.map(t=>t.rect),...(b.layers||[]).filter(l=>l.overlap!=='context').map(l=>l.rect)];
    for(const r of [...b.texts.map(t=>t.rect),...(b.layers||[]).map(l=>l.rect)])if(r.x<.08-1e-6||r.x+r.w>.92+1e-6||r.y+r.h>.85+1e-6)fail('Unsafe foreground');
    for(let i=0;i<rectangles.length;i++) for(const r of rectangles.slice(i+1)){const a=rectangles[i];if(Math.min(a.x+a.w,r.x+r.w)-Math.max(a.x,r.x)>.001&&Math.min(a.y+a.h,r.y+r.h)-Math.max(a.y,r.y)>.001)fail('Foreground collision');}
    for(const l of b.layers||[]){if(l.overlap==='context'&&(l.opacity>.25||assets.get(l.asset_id)?.provider!=='verified_local'))fail('Unverified or distracting context');if(!assets.has(l.asset_id)||assets.get(l.asset_id)?.entity_id!==l.entity_id||l.reveal<b.start||l.reveal>=l.exit||l.exit<b.end||l.exit>m.duration_frames)fail('Invalid layer'); targets.add(l.id);}
    for(const t of b.texts){if(t.lines.join(' ')!==t.text||t.size*m.width/1080<28*Math.min(m.width,m.height)/1080||t.reveal_frames.some((f,i)=>i>0&&f<t.reveal_frames[i-1]))fail('Invalid display text/order');if(t.reveal_frames.length!==t.text.trim().split(/\s+/u).length||t.reveal_frames.some(f=>f<b.start||f>=b.end))fail('Invalid phrase timing');targets.add(t.id);}
  }
  if(previous!==m.duration_frames||covered.size!==sentences.size)fail('Incomplete storyboard');
  if(m.events.some(e=>!targets.has(e.target)||e.frame>=m.duration_frames))fail('Invalid event');
});

/** Audio/script identity also validated in browser and CLI metadata preparation. */
export async function validateNewsManifest(value: unknown): Promise<Manifest> {
  const m=NewsManifestSchema.parse(value);
  const digest=await crypto.subtle.digest('SHA-256',new TextEncoder().encode(m.script.narration));
  const hash=Array.from(new Uint8Array(digest)).map(v=>v.toString(16).padStart(2,'0')).join('');
  if(hash!==m.audio.script_hash)throw new Error('Stale audio alignment');
  return m;
}
