"""Acceptance checks for semantic staging, traceability, safe zones and rollback."""
import copy
import unittest
from types import SimpleNamespace
from unittest.mock import patch
from agent.editorial.models import Asset, Beat, Bounds, Layer, Phrase, Word
from agent.editorial.shot_direction import MotionSettings, FAMILIES, composition, direct
from agent.editorial.scene_plan import BeatInput, plan_beat


def fixture(kind='ACTION', count=1, alpha=True, role='object'):
    narration='Sisyphus was a Greek king.' if kind=='CHARACTER_INTRO' else 'Sisyphus pushes the huge boulder.'
    action='Sisyphus standing proudly' if kind=='CHARACTER_INTRO' else 'pushing uphill'
    scene=plan_beat(BeatInput(text=narration,hint=kind)).as_dict()
    assets=[Asset(id=f'a{i}',entityId=f'e{i}',path='fixture.png',originalPath='fixture.png',role=role,subject='Sisyphus pushes',source='fixture',license='test',attribution='test',width=500,height=700,alpha=alpha,factual=role in ('map','photo','document'),preparation='trimmed_alpha' if alpha else 'rectangle',fallback='illustration',confidence=1,sha256='test') for i in range(count)]
    visuals=[Layer(id=f'l{i}',entityId=f'e{i}',assetId=f'a{i}',role='object',startFrame=0,endFrame=90,bounds=Bounds(x=100,y=600,w=700,h=800)) for i in range(count)]
    words=[Word(id=f'w{i}',sectionId='s',text=t,start=i*.3,end=(i+1)*.3,provenance='provider',confidence=1) for i,t in enumerate(narration.split())]
    text=Layer(id='text',role='phrase',startFrame=0,endFrame=90,bounds=Bounds(x=90,y=300,w=900,h=250),phrase=Phrase(wordIds=[w.id for w in words],lines=[[w.id for w in words]],size=80,mode='word_accumulate'))
    m=dict(layers=[*visuals,text],assets=assets,words=words,events=[],diagnostics={},warnings=[],beats=[Beat(id='b',sectionIds=['s'],layerIds=[l.id for l in [*visuals,text]],startFrame=0,endFrame=90,template='action-focus',purpose=narration)])
    script=SimpleNamespace(sentence_storyboard=[dict(sentence_id='s',primary_entity_id='e0',secondary_entity_ids=[f'e{i}' for i in range(1,count)],main_action=action,scene_plan=scene)])
    return m,script


class ShotDirectionTests(unittest.TestCase):
    def test_all_types_have_resolved_tracks_and_original_action(self):
        for kind in FAMILIES:
            m,s=fixture(kind,3);direct(m,s,None)
            shot=m['diagnostics']['shotDirection']['shots'][0]
            self.assertEqual(shot['beatType'],kind)
            self.assertEqual({t['assetId'] for t in shot['objectTracks']},{'a0','a1','a2'})
            self.assertTrue(all(t['depictedAction']==s.sentence_storyboard[0]['main_action'] for t in shot['objectTracks']))
            self.assertTrue(all(t['startFrame']<t['endFrame']<=90 for t in shot['objectTracks']))
            self.assertEqual(shot['textTracks'][0]['wordIds'],[w.id for w in m['words']])

    def test_primary_geometry_safe_and_text_disjoint(self):
        for choices in FAMILIES.values():
            for family in choices:
                for mirror in (False,True):
                    text,boxes=composition(family,3,mirror)
                    for b in [text,*boxes]:
                        self.assertGreaterEqual(b.x,0);self.assertLessEqual(b.x+b.w,1080)
                        self.assertGreaterEqual(b.y,1920*.13);self.assertLessEqual(b.y+b.h,1920*.84+1)
                    for hero in boxes:
                        self.assertTrue(text.x+text.w<=hero.x or hero.x+hero.w<=text.x or text.y+text.h<=hero.y or hero.y+hero.h<=text.y)

    def test_successive_assets_are_not_shrunk_into_false_dual_composition(self):
        m,s=fixture('CONFLICT',2)
        m['layers'][0].endFrame=45;m['layers'][1].startFrame=45
        direct(m,s,None)
        tracks=m['diagnostics']['shotDirection']['shots'][0]['objectTracks']
        self.assertTrue(all(t['bounds']['w']>=800 for t in tracks))
        self.assertEqual([(t['startFrame'],t['endFrame']) for t in tracks],[(0,45),(45,90)])

    def test_persistent_subject_reframes_when_a_second_subject_arrives(self):
        m,s=fixture('CONFLICT',2);m['layers'][1].startFrame=45
        direct(m,s,None)
        reframes=[e for e in m['events'] if e.type=='reframe' and e.targetIds==['l0']]
        self.assertTrue(any(e.startFrame==45 and e.boundsTo.w<e.boundsFrom.w for e in reframes))

    def test_bad_intro_hint_cannot_hide_an_action_and_outro_keeps_action(self):
        from agent.editorial.scene_plan import classify_beat,asset_category,build_prompt
        b=BeatInput(text='Thor ate an ox.',hint='CHARACTER_INTRO',role='character_intro')
        self.assertEqual(classify_beat(b),'ACTION')
        b=BeatInput(text='And he pushes it forever.',actors=['Sisyphus'])
        self.assertEqual(asset_category('OUTRO',b),'action')
        self.assertIn('rather than a neutral portrait',build_prompt('OUTRO',action=b.text))

    def test_rollback_is_no_op(self):
        m,s=fixture();old=copy.deepcopy(m)
        direct(m,s,None,MotionSettings(enabled=False));self.assertEqual(m,old)

    def test_action_visible_at_onset_and_no_portrait_substitution(self):
        m,s=fixture();direct(m,s,None)
        hero=m['layers'][0]
        self.assertEqual(hero.assetId,'a0');self.assertEqual(hero.motion.initialOpacity,1)
        self.assertLess(hero.motion.driftY,0);self.assertEqual(hero.motion.tilt,0)
        self.assertLessEqual(hero.motion.entranceFrames,30)

    def test_generated_rectangle_rejected_documentary_allowed(self):
        m,s=fixture(alpha=False)
        with self.assertRaisesRegex(ValueError,'scene-card'):direct(m,s,None)
        mislabeled,s=fixture(alpha=False,role='photo')
        mislabeled['assets'][0].factual=False
        with self.assertRaisesRegex(ValueError,'scene-card'):direct(mislabeled,s,None)
        for role in ('photo','map','document'):
            m,s=fixture(alpha=False,role=role);direct(m,s,None)
            self.assertEqual(m['assets'][0].preparation,'rectangle')

    def test_deterministic_and_invalid_settings_fail(self):
        a,s=fixture();b=copy.deepcopy(a);direct(a,s,None);direct(b,s,None);self.assertEqual(a,b)
        with patch.dict('os.environ',{'HER_EDITORIAL_MOTION_V2_INTENSITY':'chaos'}):
            with self.assertRaises(ValueError):MotionSettings.configured()

    def test_stale_or_missing_elements_preserve_combined_action(self):
        import tempfile
        from pathlib import Path
        from PIL import Image,ImageDraw
        from agent.editorial.cutout_style import extract_elements,read_elements
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'action.png';image=Image.new('RGBA',(500,300))
            d=ImageDraw.Draw(image);d.rectangle((20,30,190,280),fill='red');d.rectangle((340,50,480,270),fill='blue');image.save(path)
            parts=extract_elements(path);self.assertEqual(len(parts),2)
            Path(parts[0]['path']).unlink();self.assertEqual(read_elements(path),[])
            extract_elements(path);image.putpixel((40,40),(0,0,0,255));image.save(path)
            self.assertEqual(read_elements(path),[])

    def test_layout_streak_uses_semantically_compatible_alternative(self):
        m,s=fixture('ACTION');first=s.sentence_storyboard[0]
        # Three distinct narration sections may reuse the same action only when
        # Phase 1 explicitly says their state and depiction are interchangeable.
        for i in (1,2):
            sid='s'+str(i);row=copy.deepcopy(first);row['sentence_id']=sid;s.sentence_storyboard.append(row)
            t=copy.deepcopy(m['layers'][-1]);t.id='text'+str(i);t.startFrame=i*90;t.endFrame=(i+1)*90;m['layers'].append(t)
            b=copy.deepcopy(m['beats'][0]);b.id='b'+str(i);b.sectionIds=[sid];b.layerIds=['l0',t.id];b.startFrame=i*90;b.endFrame=(i+1)*90;m['beats'].append(b)
        m['layers'][0].endFrame=270
        direct(m,s,None)
        families=[p['layoutId'] for p in m['diagnostics']['shotDirection']['shots']]
        self.assertNotEqual(families[1],families[2])

    def test_short_beats_and_disabled_text(self):
        m,s=fixture();m['layers'][0].endFrame=5;m['beats'][0].endFrame=5
        direct(m,s,None,MotionSettings(kineticText=False))
        self.assertEqual(m['layers'][0].motion.exitFrames,1)
        self.assertLessEqual(m['layers'][0].motion.entranceFrames,5)
        self.assertEqual(m['layers'][-1].phrase.animation,'word_slide')

if __name__=='__main__':unittest.main()
