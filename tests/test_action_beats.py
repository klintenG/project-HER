"""Narrative regression cases; names are fixture data, not planner branches."""
import unittest
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, AsyncMock, patch
from agent.news_models import Entity, Sentence, Script
from agent.editorial.visuals import plan_visuals
from agent.editorial.assets import acquire
from agent.cutout_processor import CutoutProcessor
from tests.news_fixtures import subject_image
import config


def fixture(lines, people):
    entities=[Entity(id=name.lower(),name=name,kind=kind,identity='fictional',description=description)
              for name,kind,description in people]
    sentences=[Sentence(id=f's{i}',text=line,phrase=line,claim_ids=['fixture'],role='hook' if i==0 else 'development',
                        entity_ids=[e.id for e in entities if e.name.casefold() in line.casefold()])
               for i,line in enumerate(lines)]
    return Script(summary='Action fixture',narration=' '.join(lines),entities=entities,sentences=sentences)


class ActionBeatTests(unittest.TestCase):
    def test_interaction_states_replace_portrait_without_rewriting_words(self):
        lines=['Fenrir was a fearsome wolf.', 'Tyr placed his hand inside Fenrir’s jaws.',
               'The ribbon tightened around Fenrir.', 'Fenrir bit Tyr’s hand.']
        script=fixture(lines,[('Fenrir','animal','Large charcoal wolf, silver muzzle, red eyes, standing'),
                              ('Tyr','person','Norse god with brown armor and braided hair, standing'),
                              ('ribbon','object','White magical ribbon')])
        audit={};planned,rows=plan_visuals(script,diagnostics=audit)
        self.assertEqual(planned.narration,script.narration)
        self.assertEqual([x['kind'] for x in audit['visualPlan']['actionBeats']],['hand_contact','binding','bite'])
        for sentence,row in zip(planned.sentences[1:],rows[1:]):
            self.assertTrue(sentence.entity_ids[0].startswith('action-'))
            self.assertEqual(row['cues'][0]['entityId'],sentence.entity_ids[0])
            self.assertNotIn('fenrir',sentence.entity_ids)
        self.assertEqual(planned.sentences[0].entity_ids,['fenrir'])

    def test_uphill_and_return_are_distinct_visual_states(self):
        lines=['Sisyphus was a king.', 'Sisyphus pushed a boulder uphill.',
               'The boulder rolled back down the hill as Sisyphus watched.']
        script=fixture(lines,[('Sisyphus','person','Ancient king in a purple tunic and gold cloak')])
        planned,_=plan_visuals(script)
        self.assertEqual(planned.sentences[0].entity_ids,['sisyphus'])
        self.assertNotEqual(planned.sentences[1].entity_ids[0],planned.sentences[2].entity_ids[0])
        self.assertTrue(all(s.entity_ids[0].startswith('action-') for s in planned.sentences[1:]))

    def test_existing_suitable_variant_is_reused(self):
        script=fixture(['Mira stood still.', 'Mira pushed a boulder uphill.'],
                       [('Mira','person','Purple tunic, standing')])
        action=Entity(id='mira-action',name='Mira',kind='person',identity='fictional',
                      description='Mira visibly pushing a boulder uphill in her purple tunic')
        script.entities.append(action)
        script.sentences[1].entity_ids=['mira-action']
        audit={};planned,_=plan_visuals(script,diagnostics=audit)
        self.assertEqual(planned.sentences[1].entity_ids,['mira-action'])
        self.assertEqual(audit['visualPlan']['actionBeats'][0]['decision'],'reuse_action_variant')

    def test_action_generation_uses_established_cutout_as_reference(self):
        script=fixture(['Mira stood still.', 'Mira pushed a boulder uphill.'],
                       [('Mira','person','Purple tunic, dark hair, standing')])
        planned,_=plan_visuals(script)
        generator=MagicMock()
        async def create(prompt,path,reference=None):
            subject_image('mira').save(path)
            return 'fixture'
        generator.subject=AsyncMock(side_effect=create)
        generator.real_subject=AsyncMock(side_effect=create)
        review=MagicMock(return_value={'subjectMatch':True,'usable':True,'geometricPlaceholder':False,
            'contextAppropriate':True,'subjectConfidence':.9,'actionVisible':True,
            'contactVisible':True,'portraitOnly':False,'recognizable':True,'sameClothingOrFur':True})
        with tempfile.TemporaryDirectory() as root,patch('agent.editorial.vision.VisualReview',return_value=review),\
             patch.object(config,'NEWS_IDENTITY_IMAGE_CACHE',Path(root)/'image-cache'),\
             patch.object(config,'NEWS_CUTOUT_CACHE',Path(root)/'cutout-cache'):
            _,assets=acquire(planned,Path(root),processor=CutoutProcessor(segmenter=lambda image,model:image),
                             image_generator=generator,visual_review=review)
            self.assertEqual(len(assets),2)
            self.assertEqual(generator.real_subject.call_count,1)
            self.assertEqual(Path(generator.real_subject.call_args.args[2].path),Path(assets[0].path))


if __name__=='__main__':unittest.main()
