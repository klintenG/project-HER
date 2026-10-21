import unittest
from types import SimpleNamespace as NS
from agent.editorial import event_storyboard as es


def script(text='Ares freed Thanatos. Sisyphus was dragged away.'):
    return NS(entities=[NS(id='a',name='Ares',description=''),NS(id='s',name='Sisyphus',description='A king of Corinth')],
              sentences=[NS(id='s2',text=text,entity_ids=['a'])])


class RepairTests(unittest.TestCase):
    def test_partition_realigned_to_exact_words(self):
        sc=script()
        beats=[{'beat_id':'b1','section_id':'s2','narration_excerpt':'ares freed thanatos'},
               {'beat_id':'b1','section_id':'s2','narration_excerpt':'Sisyphus was dragged'}]
        _,out=es._repair_plan(sc,[],beats)
        self.assertEqual(' '.join(b['narration_excerpt'] for b in out).split(),sc.sentences[0].text.split())
        self.assertEqual(len({b['beat_id'] for b in out}),2)

    def test_bible_completed_and_missing_section_gets_beat(self):
        sc=script()
        bible,out=es._repair_plan(sc,[{'entity_id':'a','description':'Ares, god of war'},{'entity_id':'zzz','description':'x'*12}],[])
        self.assertEqual({b['entity_id'] for b in bible},{'a','s'})
        self.assertEqual(len(out),1)
        self.assertEqual(out[0]['narration_excerpt'],sc.sentences[0].text)

    def test_p0_intro_demoted(self):
        sc=script()
        _,out=es._repair_plan(sc,[],[{'beat_id':'s2_1','section_id':'s2','narration_excerpt':sc.sentences[0].text,'criticality':'P0','role':'character_intro'}])
        self.assertEqual(out[0]['role'],'action_tableau')

    def test_typography_repair_and_validation(self):
        sc=script()
        # Test _repair_plan normalizes typography with P1 or action role
        beats = [{'beat_id':'s2_1','section_id':'s2','narration_excerpt':sc.sentences[0].text,
                  'criticality':'P1','role':'action_tableau','media_source':'typography',
                  'actor_ids':['a'],'verb':'freed','object_ids':[],'setting':'underworld',
                  'visual_intent':'Ares freeing','must_show':['Ares freeing Thanatos'],
                  'confidence':0.9,'concept':{'subject':'Ares','action':'breaking chains','important_objects':[],
                  'setting':'underworld','emotion':'anger','state_change':'freed','visual_focus':'Ares breaking chains',
                  'description':'Ares breaking chains','identity_ids':['a'],'secondary_ids':[],'relevance':0.8,
                  'narrative_importance':0.8,'novelty':0.8,'readability':0.8}}]
        _, out = es._repair_plan(sc, [], beats)
        # Action role must be normalized to generated_scene
        self.assertEqual(out[0]['media_source'], 'generated_scene')

        # Conceptual typography beat with P1 must be normalized to P2
        beats2 = [{'beat_id':'s2_1','section_id':'s2','narration_excerpt':sc.sentences[0].text,
                   'event_type':'event',
                   'criticality':'P1','role':'reveal','media_source':'typography',
                   'actor_ids':['a'],'verb':'freed','object_ids':[],'setting':'underworld',
                   'visual_intent':'Key reveal','must_show':['Key reveal text'],
                   'confidence':0.9,'concept':{'subject':'Concept','action':'','important_objects':[],
                   'setting':'','emotion':'','state_change':'','visual_focus':'Key reveal',
                   'description':'Key reveal text with at least twenty characters','identity_ids':['a'],'secondary_ids':[],'relevance':0.8,
                   'narrative_importance':0.8,'novelty':0.8,'readability':0.8}}]
        _, out2 = es._repair_plan(sc, [], beats2)
        self.assertEqual(out2[0]['criticality'], 'P2')
        self.assertEqual(out2[0]['media_source'], 'typography')
        self.assertFalse(out2[0]['physical_action'])

        # Test EventSpec model validation passes cleanly on the repaired beat
        spec = es.EventSpec.model_validate(out2[0])
        self.assertEqual(spec.criticality, 'P2')
        self.assertEqual(spec.media_source, 'typography')

    def test_onset_anchor_realign(self):
        # 1. Skipped intervening words (e.g. adverbs)
        self.assertEqual(es.realign_onset_anchor('The gods eventually caught him', 'gods caught him'), 'caught him')

        # 2. Casing and punctuation
        self.assertEqual(es.realign_onset_anchor('During the ceremony, she grabbed the hammer.', 'Grabbed The Hammer'), 'grabbed the hammer')
        self.assertEqual(es.realign_onset_anchor('During the ceremony, she grabbed the hammer.', 'grabbed the hammer.'), 'grabbed the hammer.')

        # 3. Completely unspoken text
        self.assertIsNone(es.realign_onset_anchor('During the ceremony, she grabbed the hammer.', 'unspoken action'))

    def test_plan_realigns_onset_anchor_without_aborting(self):
        from tests.test_sentence_storyboard import script_for
        source = script_for(['The gods eventually caught him and bound him.'])
        response = {
            'continuity_bible': [{'entity_id': 'identity', 'description': 'Main character appearance description', 'wardrobe_states': {}, 'prop_designs': []}],
            'beats': [{
                'beat_id': 's0_1', 'section_id': 's0',
                'narration_excerpt': 'The gods eventually caught him and bound him.',
                'onset_anchor': 'gods caught him',
                'event_type': 'event', 'actor_ids': ['identity'], 'verb': 'caught', 'object_ids': [],
                'setting': 'Olympus', 'causal_link': '', 'visual_intent': 'Gods catching him',
                'must_show': ['Gods catching him visibly'], 'must_not_show': [],
                'role': 'action_tableau', 'criticality': 'P1', 'confidence': 0.9,
                'concept': {
                    'subject': 'Gods', 'action': 'catching him', 'important_objects': [],
                    'setting': 'Olympus', 'emotion': 'triumph', 'state_change': 'caught',
                    'visual_focus': 'Gods catching him', 'description': 'Gods catching him in a high quality illustration',
                    'identity_ids': ['identity'], 'secondary_ids': [], 'relevance': 0.8,
                    'narrative_importance': 0.8, 'novelty': 0.8, 'readability': 0.8
                }
            }]
        }
        script, _ = es.plan(source, None, lambda instruction, *_: {'accepted': True} if instruction.startswith('Audit event') else response, {})
        self.assertEqual(script.event_plan['beats'][0]['onset_anchor'], 'caught him')


if __name__=='__main__': unittest.main()
