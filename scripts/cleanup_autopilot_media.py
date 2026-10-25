"""Plan or delete only publishable objects after both platforms confirm SENT.

Default is read-only. Never applies a blanket bucket lifecycle rule: that could
remove queued, failed or ambiguous publications before Buffer fetches them.
"""
import argparse
import re
import time
from automation.autopilot import Autopilot,PublicMedia


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--execute',action='store_true')
    parser.add_argument('--retention-days',type=int,default=7);args=parser.parse_args()
    if args.retention_days<7:raise ValueError('Keep media at least seven days after confirmation')
    service=Autopilot();registry=service.registry;posts=registry.publications()
    public=None
    for story in registry.stories():
        sid=story['story_id'];records=[p for p in posts if p['video_id']==sid]
        if story.get('public_media_cleaned_at') or not re.fullmatch('[a-f0-9]{32}',sid):continue
        if len(records)!=2 or {p['platform'] for p in records}!={'instagram','youtube'}:continue
        if any(p['status']!='SENT' or not p.get('verified_at') for p in records):continue
        if max(p['verified_at'] for p in records)>time.time()-args.retention_days*86400:continue
        print(('DELETE ' if args.execute else 'ELIGIBLE ')+sid)
        if not args.execute:continue
        public=public or PublicMedia()
        for name in ('video.mp4','thumbnail.png'):
            blob=public.media.bucket.blob('autopilot/'+sid+'/'+name)
            if blob.exists(timeout=15):
                blob.reload(timeout=15)
                if name=='video.mp4' and (blob.metadata or {}).get('sha256')!=story.get('video_sha256'):raise ValueError('Cleanup video checksum mismatch')
                blob.delete(if_generation_match=blob.generation,timeout=30)
        registry.update('story:'+sid,media_url='',cover_url='',public_media_cleaned_at=time.time())


if __name__=='__main__':main()
