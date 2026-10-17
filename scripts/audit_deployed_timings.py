"""Read only projected job timing fields; never fetch input text or media tokens."""
import argparse
import json
import math
import statistics
import subprocess
import time
from pathlib import Path
import requests


def main():
    p=argparse.ArgumentParser();p.add_argument('--project',required=True);p.add_argument('--output',type=Path,required=True);args=p.parse_args()
    token=subprocess.check_output(['gcloud','auth','print-access-token'],text=True).strip()
    fields=['created_at','updated_at','status','result.duration']
    query={'structuredQuery':{'from':[{'collectionId':'her_portfolio'}],
        'select':{'fields':[{'fieldPath':field} for field in fields]},
        'where':{'fieldFilter':{'field':{'fieldPath':'status'},'op':'EQUAL','value':{'stringValue':'completed'}}},'limit':100}}
    response=requests.post(f'https://firestore.googleapis.com/v1/projects/{args.project}/databases/(default)/documents:runQuery',
        headers={'Authorization':'Bearer '+token},json=query,timeout=30)
    if response.status_code!=200:
        raise RuntimeError('Projected timing query failed: HTTP '+str(response.status_code))
    rows=[]
    def number(value):return float(value.get('doubleValue',value.get('integerValue',0)))
    for result in response.json():
        fields=result.get('document',{}).get('fields',{})
        if not fields:continue
        created=number(fields.get('created_at',{}));updated=number(fields.get('updated_at',{}))
        duration=number(fields.get('result',{}).get('mapValue',{}).get('fields',{}).get('duration',{}))
        rows.append({'created_at':created,'updated_at':updated,'wall_seconds':updated-created,'output_seconds':duration})
    comparable=sorted(row['wall_seconds'] for row in rows if 45<=row['output_seconds']<=90 and row['wall_seconds']>0)
    report={'scope':'Existing completed durable jobs; configurations/cache state are unknown. Not a paired benchmark.',
        'retrieved_at_epoch':time.time(),'jobs':rows,'comparable_count':len(comparable)}
    if comparable:report.update(p50_seconds=statistics.median(comparable),p95_seconds=comparable[math.ceil(.95*len(comparable))-1])
    args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(json.dumps(report,indent=2))
    print({key:value for key,value in report.items() if key!='jobs'})

if __name__=='__main__':main()
