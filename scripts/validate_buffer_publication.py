"""Controlled provider test using an existing READY video, separate from daily jobs.

Default prints payloads only. --confirm-live-test explicitly schedules real posts
while the normal Autopilot remains paused and BUFFER_DRY_RUN remains true.
"""
import argparse
import json
import time
from datetime import datetime,timezone
from zoneinfo import ZoneInfo
from automation.autopilot import Autopilot,PublicMedia
from automation.autopilot_store import digest
from automation.buffer_client import build_post


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--story-id',required=True)
    parser.add_argument('--due-at',required=True,help='Full timezone-aware ISO timestamp inside the IST publishing window')
    parser.add_argument('--confirm-live-test',action='store_true')
    args=parser.parse_args();service=Autopilot();registry=service.registry;cfg=service.settings
    due=datetime.fromisoformat(args.due_at.replace('Z','+00:00'))
    if due.tzinfo is None:raise ValueError('A timezone-aware test time is required')
    local=due.astimezone(ZoneInfo(cfg.timezone))
    if not cfg.publish_start<=local.strftime('%H:%M')<=cfg.publish_end:raise ValueError('Test publication must be inside the configured IST window')
    story=registry.store.get('story:'+args.story_id)
    if not story or story['generation_status']!='READY' or not story.get('quality',{}).get('passed'):raise ValueError('Use a validated READY video')
    PublicMedia.verify(story['media_url']);channels=service.buffer.discover()
    due_at=due.astimezone(timezone.utc).isoformat()
    payloads={p:build_post(p,c['id'],story['media_url'],due_at,story['social_metadata'],story['cover']['offset_ms']) for p,c in channels.items()}
    if not args.confirm_live_test:
        print(json.dumps({'dry_run':True,'payloads':payloads},indent=2));return
    if due<=datetime.now(timezone.utc):raise ValueError('Test time must be in the future')
    test_id=digest(story['story_id']+due_at)[:24]
    token=registry.claim('lock:controlled-test',600)
    if not token:raise ValueError('Another controlled test is running')
    try:
        def reserve(tx):
            index=tx.get('autopilot-index');saved=tx.get('story:'+args.story_id)
            records=[tx.get('publication:test:'+test_id+':'+p) for p in channels]
            if saved['publication_status']!='UNUSED' and not any(records):raise ValueError('This video is already assigned or published')
            for (platform,_),record in zip(channels.items(),records):
                if record:continue
                key='publication:test:'+test_id+':'+platform
                index['publications'].append(key)
                tx.set(key,{'key':key,'video_id':args.story_id,'publication_date':local.date().isoformat(),
                    'platform':platform,'status':'PENDING','due_at':due_at,'attempts':0,'controlled_test':True})
            saved['publication_status']='TEST_ASSIGNED'
            tx.set('story:'+args.story_id,saved);tx.set('autopilot-index',index)
        registry.store.atomic(reserve)
        for platform,payload in payloads.items():
            key='publication:test:'+test_id+':'+platform;record=registry.store.get(key)
            if record.get('buffer_post_id'):
                service._remote(record,service.buffer.get(record['buffer_post_id']));continue
            remote=service.buffer.posts(channels[platform]['id'])
            matches=[p for p in remote if p['text']==payload['text'] and p.get('dueAt') and datetime.fromisoformat(p['dueAt'].replace('Z','+00:00'))==due]
            if len(matches)==1:service._remote(record,matches[0]);continue
            if record['status'] in ('UNKNOWN','SUBMITTING') or len(matches)>1:raise ValueError('Ambiguous remote test result; reconcile before retrying')
            if sum(p['status'] in ('scheduled','buffer','sending') for p in remote)>=cfg.channel_queue_limit:raise ValueError('Buffer queue is full')
            registry.update(key,status='SUBMITTING',payload=payload,attempts=record['attempts']+1,channel_id=payload['channelId'])
            try:service._remote(record,service.buffer.create(payload))
            except Exception:
                registry.update(key,status='UNKNOWN');raise
        print(json.dumps({'test_id':test_id,'status':'scheduled_or_blocked; verify remote results before activation'}))
    finally:registry.release('lock:controlled-test',token)


if __name__=='__main__':main()
