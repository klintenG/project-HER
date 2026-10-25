"""Transactional registry on the application's existing SQLite/Firestore stores."""
from __future__ import annotations
import hashlib
import re
import time
import unicodedata
import uuid
from datetime import datetime
from zoneinfo import ZoneInfo


def normalize(value):
    value = unicodedata.normalize('NFKD',str(value)).casefold()
    return ' '.join(re.findall(r'[a-z0-9]+',value))


def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()


def similarity(a,b):
    x,y = set(normalize(a).split()),set(normalize(b).split())
    return len(x & y)/max(1,len(x | y))


def duplicate(candidate, previous, threshold=.78):
    """Character overlap alone is never sufficient; compare the narrative arc."""
    for field in ('canonical_story_id','title','narrative_fingerprint','script_hash'):
        if candidate.get(field) and normalize(candidate[field]) == normalize(previous.get(field,'')):
            return field
    aliases = set(map(normalize,candidate.get('canonical_aliases',[]))) | {normalize(candidate.get('canonical_story_id',''))}
    old = set(map(normalize,previous.get('canonical_aliases',[]))) | {normalize(previous.get('canonical_story_id',''))}
    if (aliases & old) - {''}: return 'canonical_alias'
    a = ' '.join(candidate.get('major_plot_events',[])) + ' ' + candidate.get('ending','')
    b = ' '.join(previous.get('major_plot_events',[])) + ' ' + previous.get('ending','')
    if a.strip() and b.strip() and similarity(a,b) >= threshold: return 'narrative_events'
    return None


class Registry:
    def __init__(self, store): self.store = store
    def snapshot(self):
        return self.store.get('autopilot-index') or {'stories':[], 'publications':[], 'alerts':[]}
    def update(self, key, **fields):
        def change(tx):
            row = tx.get(key)
            if row is None: raise ValueError('Record not found')
            row.update(fields,updated_at=time.time());tx.set(key,row)
            return row
        return self.store.atomic(change)
    def stories(self):
        return [row for key in self.snapshot()['stories'] if (row:=self.store.get(key))]
    def publications(self):
        return [row for key in self.snapshot()['publications'] if (row:=self.store.get(key))]
    def reserve(self, candidate, threshold=.78, generation_mode='AUTOPILOT'):
        # This registry is optional for manual callers; no validation or LLM call.
        if generation_mode != 'AUTOPILOT': return None
        sid = uuid.uuid4().hex
        def reserve(tx):
            index = tx.get('autopilot-index') or {'stories':[], 'publications':[], 'alerts':[]}
            # All reads precede writes: required by Firestore transactions.
            history = [tx.get(key) for key in index['stories']]
            for previous in history:
                if previous and (reason:=duplicate(candidate,previous,threshold)):
                    raise ValueError('Duplicate story: '+reason)
            row = {**candidate,'story_id':sid,'video_id':sid,'creation_mode':'AUTOPILOT',
                   'generation_status':'RESERVED','publication_status':'UNUSED','created_at':time.time(),
                   'reservation_expires_at':time.time()+7200,'duplicate_validation':'PASS'}
            index['stories'].append('story:'+sid)
            tx.set('story:'+sid,row);tx.set('autopilot-index',index)
            return row
        return self.store.atomic(reserve)
    def spend(self, amount, limit, task, sid=''):
        day=datetime.now(ZoneInfo('Asia/Kolkata')).date().isoformat()
        key='cost:'+day
        def charge(tx):
            row=tx.get(key) or {'reserved_usd':0,'entries':[]}
            if row['reserved_usd']+amount > limit:raise ValueError('Daily expenditure reservation limit reached')
            row['reserved_usd']+=amount
            row['entries'].append({'task':task,'story_id':sid,'reserved_usd':amount,'at':time.time()})
            tx.set(key,row)
        self.store.atomic(charge)
    def alert(self, message):
        import logging
        logging.getLogger(__name__).error('AUTOPILOT_ALERT %s',message)
        def save(tx):
            index=tx.get('autopilot-index') or {'stories':[], 'publications':[], 'alerts':[]}
            index['alerts']=(index['alerts']+[{'message':message,'at':time.time()}])[-50:]
            tx.set('autopilot-index',index)
        self.store.atomic(save)
    def claim(self,key,seconds=3600):
        token=uuid.uuid4().hex
        def claim(tx):
            current=tx.get(key)
            if current and current['expires_at']>time.time():return None
            tx.set(key,{'token':token,'expires_at':time.time()+seconds})
            return token
        return self.store.atomic(claim)
    def release(self,key,token):
        def release(tx):
            row=tx.get(key)
            if row and row['token']==token:tx.set(key,{'token':token,'expires_at':0})
        self.store.atomic(release)

    def import_legacy(self, path):
        """One-time read of existing history; never reset history after parse errors."""
        import json
        from pathlib import Path
        path=Path(path)
        if not path.exists() or self.store.get('legacy-history-imported'):return
        rows=json.loads(path.read_text()).get('stories',[])
        def migrate(tx):
            index=tx.get('autopilot-index') or {'stories':[], 'publications':[], 'alerts':[]}
            marker=tx.get('legacy-history-imported')
            if marker:return
            records=[]
            for old in rows:
                if old.get('status')=='rejected':continue
                sid='legacy-'+digest(str(old.get('id'))+old.get('title',''))[:24]
                title=old.get('title','Untitled')
                row={'story_id':sid,'video_id':sid,'title':title,'normalized_title':normalize(title),
                    'canonical_story_id':'','canonical_aliases':[], 'category':old.get('genre','OTHER'),
                    'story_origin':'UNKNOWN_LEGACY','story_summary':old.get('synopsis',''),
                    'major_plot_events':[old.get('synopsis','')], 'ending':'',
                    'script_hash':digest(normalize(old['full_story'])) if old.get('full_story') else '',
                    'creation_mode':'LEGACY','generation_status':'ARCHIVED','publication_status':old.get('status','').upper(),
                    'published_platforms':old.get('platforms_published',[]),'created_at':0,
                    'duplicate_validation':'Imported history; canonical identity unavailable'}
                key='story:'+sid
                if key not in index['stories']:index['stories'].append(key);records.append((key,row))
            for key,row in records:tx.set(key,row)
            tx.set('autopilot-index',index);tx.set('legacy-history-imported',{'count':len(records),'at':time.time()})
        self.store.atomic(migrate)
