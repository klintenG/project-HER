"""Exercise one real-person portrait route from a saved, source-linked story."""
import json
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from agent.news_models import Script,Evidence
from agent.news_script import NewsLLM
from agent.editorial.assets import acquire
from agent.cutout_processor import CutoutProcessor
from agent.news_models import NewsError


def main():
    previous=Path(sys.argv[1]);entity_id=sys.argv[2];out=Path(sys.argv[3]);out.mkdir(parents=True,exist_ok=True)
    preview=json.loads((previous/'news_preview.json').read_text());script=Script.model_validate(preview['script']);evidence=Evidence.model_validate(preview['evidence'])
    person=next(e for e in script.entities if e.id==entity_id)
    sentence=next(s for s in script.sentences if entity_id in s.entity_ids).model_copy(update={'entity_ids':[entity_id]})
    script=Script.model_validate({**script.model_dump(),'sentences':[sentence.model_dump()],'narration':sentence.text,'entities':[person.model_dump()]})
    processor=None;diagnostics={}
    if '--reference-edit' in sys.argv[4:]:
        class ExerciseReferenceEdit(CutoutProcessor):
            def process(self,source,dest,**kwargs):
                if Path(source).suffix=='.image':raise NewsError('Explicit QA exercise: test reference-guided generation instead of direct photo.')
                return super().process(source,dest,**kwargs)
        processor=ExerciseReferenceEdit();diagnostics['forcedReferenceEditForQA']=True
    entities,assets=acquire(script,out/'assets',asset_mode='auto',llm=NewsLLM(),evidence=evidence,diagnostics=diagnostics,processor=processor)
    (out/'person_review.json').write_text(json.dumps({'entities':[e.model_dump() for e in entities],'assets':[a.model_dump() for a in assets],'diagnostics':diagnostics},ensure_ascii=False,indent=2))
    print('Person assets ready: '+person.name+'; alpha='+str(assets[0].alpha)+'; '+assets[0].source,flush=True)


if __name__=='__main__':main()
