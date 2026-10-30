"""Cloud Run Job entry point: render exactly one admitted portfolio job.

    python -m agent.portfolio_worker <job_id>

The web service dispatches one execution per admitted job and can therefore
scale to zero. This process claims the job transactionally (a duplicate or late
execution exits without provider work), heartbeats, enforces cancellation and
the job deadline, and never replays paid work. The container is ephemeral, so
scratch cleanup is best-effort hygiene only.
"""
from __future__ import annotations
import logging
import os
import re
import sys
import threading
import time

logger=logging.getLogger('agent.portfolio_worker')
CANCEL_GRACE=20
HEARTBEAT_SECONDS=15


def stop_descendants():
    """Terminate Remotion/Chromium/FFmpeg children before this process exits."""
    import psutil
    try:children=psutil.Process().children(recursive=True)
    except psutil.NoSuchProcess:return
    for child in reversed(children):
        try:child.terminate()
        except psutil.NoSuchProcess:pass
    _,remaining=psutil.wait_procs(children,timeout=5)
    for child in remaining:
        try:child.kill()
        except psutil.NoSuchProcess:pass


def watchdog(rt,jid,deadline,stop,*,exit_process=os._exit,clock=time.time,interval=HEARTBEAT_SECONDS,on_exit=None):
    """Heartbeat; hard-stop when cancellation is ignored or the deadline passes.

    Cooperative cancellation inside the News pipeline is tried first (it polls
    the same durable flag); this is the backstop equivalent to the supervisor
    that used to run in the web instance.
    """
    cancel_at=None
    def leave():
        # os._exit skips finally blocks: meter the billed time first (best effort).
        stop_descendants()
        if on_exit:
            try:on_exit()
            except Exception:pass
        exit_process(0)
    while not stop.wait(interval):
        try:
            rt.heartbeat(jid)
            job=rt.store.get('job:'+jid) or {}
        except Exception as exc:  # transient store errors must not kill the render
            logger.warning('Heartbeat failed job=%s type=%s',jid,type(exc).__name__);continue
        if job.get('status') in ('completed','failed','cancelled'):
            # Normal completion also lands here while diagnostics upload; allow it to finish.
            if stop.wait(180):return
            # Terminal recorded (e.g. stale detection) but the pipeline is still running.
            leave();return
        if job.get('cancel_requested') and cancel_at is None:cancel_at=clock()
        expired=clock()>deadline
        if expired or (cancel_at is not None and clock()-cancel_at>CANCEL_GRACE):
            cancelled=cancel_at is not None
            rt.update(jid,status='cancelled' if cancelled else 'failed',stage=None,
                      error='Generation cancelled.' if cancelled else 'Generation exceeded its deadline. No automatic paid retry was made.')
            rt.release(jid)
            leave();return


def main(argv=None):
    logging.basicConfig(level=logging.INFO,format='%(levelname)s %(name)s %(message)s')
    args=list(sys.argv[1:] if argv is None else argv)
    jid=args[0] if args else ''
    if not re.fullmatch(r'[0-9a-f]{32}',jid):
        logger.error('A 32-character job id argument is required.');return 2
    from .portfolio_api import CreateJob,cleanup_cloud_job,configured_runtime,prepare_worker_environment
    # Open the store before prepare_worker_environment() moves config.TEMP_DIR:
    # a local SQLite store lives under it and must resolve like the web process.
    rt=configured_runtime()
    started=time.monotonic()
    from utils.compute_meter import record_best_effort
    meter=lambda:record_best_effort('portfolio',started,store=rt.store)
    try:return run_claimed(rt,jid,CreateJob,cleanup_cloud_job,prepare_worker_environment,meter)
    finally:meter()  # every start is billed (>= 1 minute), including duplicate or cancelled ones


def run_claimed(rt,jid,CreateJob,cleanup_cloud_job,prepare_worker_environment,meter):
    owner=os.getenv('CLOUD_RUN_EXECUTION') or f'local-{os.getpid()}'
    state,request=rt.claim(jid,owner)
    if state in ('cancelled','expired'):
        rt.release(jid);logger.info('Job %s not started: %s',jid,state);return 0
    if state!='claimed':
        logger.info('Job %s already claimed, finished or missing; no work done.',jid);return 0
    try:data=CreateJob.model_validate(request)
    except Exception:
        rt.update(jid,status='failed',error='The stored request is invalid. No paid work was submitted.');rt.release(jid);return 0
    prepare_worker_environment(jid)
    job=rt.store.get('job:'+jid)
    stop=threading.Event()
    guard=threading.Thread(target=watchdog,args=(rt,jid,job['deadline'],stop),kwargs={'on_exit':meter},daemon=True);guard.start()
    try:
        rt.execute(jid,data)  # records completed/failed/cancelled and releases the slot
    finally:
        stop.set();guard.join(10)
        try:cleanup_cloud_job(jid)
        except Exception:pass
    logger.info('Job %s worker finished with status=%s',jid,(rt.store.get('job:'+jid) or {}).get('status'))
    return 0


if __name__=='__main__':
    sys.exit(main())
