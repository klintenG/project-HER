"""Operator-only toggle of daily admission limits; does not create jobs or reset counts."""
import argparse
import subprocess
import requests


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    choices=parser.add_mutually_exclusive_group(required=True)
    choices.add_argument('--enable',action='store_true')
    choices.add_argument('--disable',action='store_true')
    parser.add_argument('--project',default='project-her-510715')
    args=parser.parse_args()
    token=subprocess.check_output(['gcloud','auth','print-access-token'],text=True).strip()
    url=f'https://firestore.googleapis.com/v1/projects/{args.project}/databases/(default)/documents/her_portfolio/policy'
    response=requests.patch(url,headers={'Authorization':'Bearer '+token},params={'updateMask.fieldPaths':'daily_limits_disabled'},json={'fields':{'daily_limits_disabled':{'booleanValue':args.disable}}},timeout=30)
    response.raise_for_status()
    check=requests.get(url,headers={'Authorization':'Bearer '+token},timeout=30)
    check.raise_for_status()
    assert check.json()['fields']['daily_limits_disabled']['booleanValue']==args.disable
    print('Daily generation limits '+('disabled' if args.disable else 'enabled')+'. Concurrency, input validation and job authorization remain enforced. Existing counters are preserved.')


if __name__=='__main__':
    main()
