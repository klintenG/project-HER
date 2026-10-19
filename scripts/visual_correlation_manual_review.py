"""Extract actual encoded frames or apply checksum-bound manual observations."""
import argparse
import json
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from agent.editorial import event_storyboard as events
from agent.editorial.models import Timeline,digest
from agent.editorial.visuals import EditorialScript


def main():
    parser=argparse.ArgumentParser();parser.add_argument('run',type=Path);parser.add_argument('--apply',action='store_true');args=parser.parse_args()
    root=args.run.resolve();manifest=Timeline.model_validate_json((root/'editorial_manifest.json').read_text())
    script=EditorialScript.model_validate_json((root/'planned_script.json').read_text())
    reviews=json.loads((root/'frame_reviews.json').read_text()) if args.apply else {}
    def manual(instruction,data,paths):
        path=Path(paths[0]);review=reviews.get(path.stem)
        if not review or not review.get('observations') or not review.get('reviewer') or review.get('sha256')!=digest(path):
            raise ValueError('Manual encoded-frame observation missing or stale')
        return {**review['assessment'],'manualReviewEvidence':{k:review[k] for k in ('reviewer','observations','sha256')}}
    edl=events.verify_rendered(script,manifest,root/'editorial.mp4',root,manual)
    manifest.diagnostics['eventQuality']=edl['metrics']
    (root/'editorial_manifest.json').write_text(manifest.model_dump_json(indent=2))
    print(json.dumps(edl['metrics'],indent=2))

if __name__=='__main__':main()
