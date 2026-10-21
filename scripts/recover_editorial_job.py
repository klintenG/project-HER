"""Recover a paid editorial job using saved media only; providers are disabled.

Usage: python scripts/recover_editorial_job.py --job output/editorial_<id>
"""
import argparse
import json
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))


from agent.editorial.recovery import recover

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--job',required=True);parser.add_argument('--prepare-only',action='store_true');args=parser.parse_args()
    print(recover(args.job,not args.prepare_only))
