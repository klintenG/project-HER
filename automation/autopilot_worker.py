"""Cloud Run Job/local worker entry point. No laptop timer or browser required."""
from __future__ import annotations
import argparse
import logging
import time
from .autopilot import Autopilot


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('action',choices=['generate','schedule','verify','dry-run','retry','prepare','pipeline','publish-now'])
    parser.add_argument('--command-id',default='')
    parser.add_argument('--force',action='store_true')
    args=parser.parse_args()
    logging.basicConfig(level=logging.INFO)
    service=Autopilot();registry=service.registry
    row={}
    key='command:'+args.command_id if args.command_id else None
    token=registry.claim('lock:'+key,7200) if key else None
    if key and not token:return
    try:
        if key:
            row=registry.store.get(key)
            if not row or row.get('status') in ('completed','failed'):return
            registry.update(key,status='running',started_at=time.time())
        def progress(**fields):
            if key:registry.update(key,progress={**fields,'updated_at':time.time()})
        action={'generate':lambda:service.generate(force=args.force,progress=progress),
                'schedule':lambda:service.schedule(force=args.force),
                'verify':service.verify,
                'dry-run':lambda:service.schedule(force_dry_run=True,force=args.force),
                'retry':service.retry_failed,
                'prepare':service.prepare_existing,
                'publish-now':lambda:service.publish_now(row.get('story_id','')),
                'pipeline':lambda:{'generated':service.generate(force=True,progress=progress),'scheduled':service.schedule(force=True)}}[args.action]
        result=action()
        if key:registry.update(key,status='completed',completed_at=time.time(),result=result)
    except Exception as exc:
        from agent.portfolio_api import safe_message
        message=safe_message(exc)
        if key:registry.update(key,status='failed',completed_at=time.time(),error=message)
        registry.alert(args.action+' failed: '+message)
        raise
    finally:
        if key and token:registry.release('lock:'+key,token)


if __name__=='__main__':main()
