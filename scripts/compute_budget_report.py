"""Compare real Cloud Run Job usage with the monthly free tier (read-only).

    python scripts/compute_budget_report.py --days 30

Lists recent executions of the Project HER jobs with `gcloud run jobs executions list`,
bills each one like Cloud Run does (wall time, one-minute minimum, its own CPU/memory),
and reports per-day usage as a share of the free tier (240,000 vCPU-s and 450,000 GiB-s a
month). It also prints the median render time to calibrate HER_COMPUTE_VISITOR_JOB_SECONDS.
It never changes anything. Billing in the Cloud Billing report is the source of truth.
"""
import argparse
import json
import re
import statistics
import subprocess
from collections import defaultdict
from datetime import datetime, timezone

PROJECT='project-her-510715';REGION='us-central1'
JOBS=('her-autopilot','her-autopilot-light','her-portfolio-worker')
FREE_VCPU_SECONDS=240000.0;FREE_GIB_SECONDS=450000.0
FALLBACK={'her-autopilot':(4.0,8.0),'her-portfolio-worker':(4.0,8.0),'her-autopilot-light':(1.0,2.0)}
MIN_BILLED=60.0


def quantity(value,default):
    """'8Gi' -> 8.0 GiB, '2' -> 2.0, '1000m' -> 1.0, '512Mi' -> 0.5."""
    if value is None:return default
    match=re.fullmatch(r'\s*([0-9.]+)\s*(m|Ki|Mi|Gi|Ti)?\s*',str(value))
    if not match:return default
    number=float(match.group(1));unit=match.group(2)
    return number*{None:1.0,'m':0.001,'Ki':1/1048576,'Mi':1/1024,'Gi':1.0,'Ti':1024.0}[unit]


def parse_time(text):
    try:return datetime.fromisoformat(text.replace('Z','+00:00'))
    except (AttributeError,ValueError):return None


def execution_usage(item,job):
    """-> (UTC date, billed seconds, vCPU, GiB) or None if the execution has no usable times."""
    status=item.get('status',{})
    start=parse_time(status.get('startTime'));end=parse_time(status.get('completionTime'))
    if not start or not end or end<start:return None
    containers=(((item.get('spec',{}).get('template',{}) or {}).get('spec',{}) or {}).get('containers') or [{}])
    limits=(containers[0].get('resources') or {}).get('limits') or {}
    cpu_default,mem_default=FALLBACK.get(job,(4.0,8.0))
    seconds=max(MIN_BILLED,(end-start).total_seconds())
    return start.astimezone(timezone.utc).date().isoformat(),seconds,quantity(limits.get('cpu'),cpu_default),quantity(limits.get('memory'),mem_default)


def summarize(executions):
    """executions: list of (job, item). Returns per-day heavy-equivalent minutes and totals."""
    per_day=defaultdict(lambda:{'vcpu':0.0,'gib':0.0,'runs':0});render_seconds=[]
    for job,item in executions:
        usage=execution_usage(item,job)
        if not usage:continue
        day,seconds,cpu,mem=usage
        per_day[day]['vcpu']+=cpu*seconds;per_day[day]['gib']+=mem*seconds;per_day[day]['runs']+=1
        if job in ('her-autopilot','her-portfolio-worker') and seconds>=300:render_seconds.append(seconds)
    rows=[]
    for day in sorted(per_day):
        d=per_day[day]
        share=max(d['vcpu']/FREE_VCPU_SECONDS,d['gib']/FREE_GIB_SECONDS)   # fraction of the monthly pool
        rows.append({'day':day,'runs':d['runs'],'pool_percent':round(share*100,2),'heavy_minutes':round(share*56250/60,1)})
    total=sum(r['pool_percent'] for r in rows)
    return {'days':rows,'pool_percent_total':round(total,2),'median_render_seconds':round(statistics.median(render_seconds)) if render_seconds else None}


def fetch(job,limit):
    out=subprocess.run(['gcloud','run','jobs','executions','list','--job='+job,'--region='+REGION,'--project='+PROJECT,
        '--limit='+str(limit),'--format=json'],capture_output=True,text=True)
    if out.returncode:raise SystemExit('gcloud failed for '+job+': '+out.stderr.strip()[:300])
    return json.loads(out.stdout or '[]')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--days',type=int,default=30);parser.add_argument('--limit',type=int,default=500)
    args=parser.parse_args()
    cutoff=datetime.now(timezone.utc).timestamp()-args.days*86400
    executions=[]
    for job in JOBS:
        for item in fetch(job,args.limit):
            start=parse_time(item.get('status',{}).get('startTime'))
            if start and start.timestamp()>=cutoff:executions.append((job,item))
    report=summarize(executions)
    print('date        runs  pool%  heavy-min   (pool = monthly free tier; 100% of a month = ~937 heavy-min, ~31/day)')
    for row in report['days']:print(f"{row['day']}  {row['runs']:>4}  {row['pool_percent']:>5}  {row['heavy_minutes']:>8}")
    print(f"\nTotal over window: {report['pool_percent_total']}% of one month's free tier")
    if report['median_render_seconds']:print(f"Median long-run (render) duration: {report['median_render_seconds']} s -> set HER_COMPUTE_VISITOR_JOB_SECONDS near this")
    days=max(1,len(report['days']))
    print('Verdict: '+('within the free tier at this rate' if report['pool_percent_total']/days*30<=100 else 'on track to EXCEED the free tier; reduce renders/starts or accept the small overage'))


if __name__=='__main__':main()
