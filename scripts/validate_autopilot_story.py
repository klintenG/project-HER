"""Explicit paid story-only smoke test. Never renders or publishes a video."""
import argparse
import json
import tempfile
from pathlib import Path
from agent.portfolio_store import SQLiteStore
from automation.autopilot_store import Registry
from automation.autopilot_config import Settings
from automation.autonomous_story_director import AutonomousStoryDirector


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--model',required=True)
    parser.add_argument('--resume',action='store_true')
    parser.add_argument('--category',choices=['MYTHOLOGY','FANTASY','SCIFI','FOLKLORE','OTHER'],default='SCIFI')
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    args.output.mkdir(parents=True,exist_ok=True)
    cfg=Settings(llm_model=args.model,category_weights={args.category:1},daily_cost_limit_usd=.8)
    registry=Registry(SQLiteStore(args.output/'story-smoke.sqlite3'))
    director=AutonomousStoryDirector(cfg,registry)
    story=registry.stories()[-1] if args.resume and registry.stories() else director.select()
    story=director.write(story)
    report={'story':story,'llm_calls':director.llm.calls,'usage':director.llm.usage,
        'actual_cost_usd':None,'reserved_usd':sum(x['reserved_usd'] for x in director.llm.usage)}
    (args.output/'story-smoke.json').write_text(json.dumps(report,indent=2))
    print(json.dumps({'title':story['title'],'category':story['category'],'editorial_score':story['editorial_score'],
        'calls':director.llm.calls,'words':len(story['script']['narration'].split()),'reserved_usd':report['reserved_usd']}))


if __name__=='__main__':main()
