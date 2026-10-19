"""Scene planning: beat typing, beat-aware prompts, layout variety, motion bounds, cutout extraction."""
import tempfile
import unittest
from pathlib import Path
from PIL import Image, ImageDraw
from agent.editorial import scene_plan as sp
from agent.editorial import cutout_style as cs
from agent.editorial.models import LayerMotion

THOR = [
    ('Thor, the mighty God of Thunder, was feared across the nine realms.', 'CHARACTER_INTRO'),
    ('One morning, Thor woke up to discover his magical hammer, Mjölnir, was missing.', {'ACTION', 'EVENT'}),
    ('A giant named Thrym had stolen it and kept the hammer buried deep underground.', {'EVENT', 'ACTION', 'CONTEXT'}),
    ('But Freyja refused.', 'CONFLICT'),
    ('Wearing a bridal gown and veil, he entered the giant\'s palace.', 'ACTION'),
    ('Thor ate an entire ox, eight salmon, and drank three barrels of mead!', 'ACTION'),
    ('The giant ordered Thor\'s stolen hammer to be placed in the bride\'s lap to bless the marriage.', 'EVENT'),
    ('Thor grabbed the hammer. Ripped off his disguise.', 'TWIST'),
    ('And unleashed his fury, killing Thrym and the giants gathered there!', 'CONFLICT'),
]
SISYPHUS = [
    ('His name was Sisyphus.', 'CHARACTER_INTRO'),
    ('He tricked Thanatos into putting on his own magical chains.', 'ACTION'),
    ('But somehow, he escaped again!', 'ACTION'),
    ('They condemned him to push an enormous boulder up a mountain.', {'EVENT', 'ACTION'}),
    ('Every time he reached the top the boulder rolled all the way back down.', 'ACTION'),
]


def types_for(rows, actors=1):
    plans = sp.plan_story([sp.BeatInput(text=t, index=i, total=len(rows), actors=['A'] * actors, first_mention=i == 0) for i, (t, _) in enumerate(rows)])
    return plans


class ClassificationTests(unittest.TestCase):
    def check(self, rows):
        for (text, expected), plan in zip(rows, types_for(rows)):
            allowed = expected if isinstance(expected, set) else {expected}
            self.assertIn(plan.beat_type, allowed, text)

    def test_thor_beats(self):
        self.check(THOR)

    def test_sisyphus_beats(self):
        self.check(SISYPHUS)

    def test_planner_hint_wins_and_bad_hint_is_ignored(self):
        self.assertEqual(sp.classify_beat(sp.BeatInput(text='Anything.', hint='twist')), 'TWIST')
        self.assertNotEqual(sp.classify_beat(sp.BeatInput(text='He ran away.', hint='NOPE')), 'NOPE')

    def test_every_type_has_mode_category_template_motion(self):
        for t in sp.BEAT_TYPES:
            self.assertIn(t, sp.VISUAL_MODES)
            self.assertIn(sp.CATEGORY_FOR_TYPE[t], sp.ASSET_CATEGORIES)
            self.assertIn(sp.TEMPLATE_FOR_TYPE[t], sp.TEMPLATES)
            LayerMotion(**sp.motion_spec(t), elements=[])
            LayerMotion(**sp.motion_spec(t, True), elements=[])

    def test_meaning_change_changes_plan_not_just_character(self):
        plans = types_for(THOR)
        self.assertEqual(len({p.visual_intent for p in plans}), len(plans))
        self.assertGreaterEqual(len({p.beat_type for p in plans}), 4)


class VarietyTests(unittest.TestCase):
    def test_no_identical_neighbouring_templates_except_twist(self):
        for rows in (THOR, SISYPHUS):
            plans = types_for(rows)
            for a, b in zip(plans, plans[1:]):
                if b.beat_type != 'TWIST':
                    self.assertNotEqual(a.template, b.template)

    def test_layout_mirrors_alternate(self):
        plans = types_for(THOR)
        self.assertTrue(all(a.mirror != b.mirror for a, b in zip(plans, plans[1:])))

    def test_geometry_never_overlaps_caption_and_stays_on_canvas(self):
        for template in sp.TEMPLATES:
            for count in (1, 2, 3):
                for mirror in (False, True):
                    for below in (False, True):
                        cap, boxes = sp.geometry(template, count, mirror, below)
                        for box in [cap, *boxes]:
                            self.assertTrue(0 <= box['x'] and box['x'] + box['w'] <= 1080 and 0 <= box['y'] and box['y'] + box['h'] <= 1920, (template, box))
                        main = boxes[0]
                        separated = main['y'] >= cap['y'] + cap['h'] - 80 or cap['y'] >= main['y'] + main['h'] - 80 or main['x'] >= cap['x'] + cap['w'] or cap['x'] >= main['x'] + main['w']
                        self.assertTrue(separated, (template, cap, main))


class PromptTests(unittest.TestCase):
    def test_prompts_are_beat_specific_and_cutout_oriented(self):
        prompts = {t: sp.build_prompt(t, subjects='Thor', action='grabbing Mjölnir from the bride\'s lap', objects='Mjölnir hammer') for t in sp.BEAT_TYPES}
        self.assertEqual(len(set(prompts.values())), len(prompts))
        for text in prompts.values():
            for required in ('flat', 'isolated', 'NO scenery', 'No text'):
                self.assertIn(required, text)
            self.assertNotIn('Keep table, floor and environmental fragments', text)
        self.assertIn('NOT a standing portrait', prompts['ACTION'])
        self.assertIn('twist', prompts['TWIST'].lower())
        self.assertIn('Expressive', prompts['REACTION'])

    def test_accent_prompts(self):
        self.assertIn('Isolated object cutout', sp.accent_prompt('object', 'iron chains'))
        self.assertIn('Environment accent', sp.accent_prompt('environment', 'stone archway'))


class CutoutTests(unittest.TestCase):
    def blobs(self, folder, two=True):
        image = Image.new('RGBA', (600, 400), (0, 0, 0, 0))
        draw = ImageDraw.Draw(image)
        draw.ellipse((40, 60, 240, 340), fill=(200, 60, 60, 255))
        if two:
            draw.rectangle((430, 120, 560, 330), fill=(60, 60, 200, 255))
        path = Path(folder) / 'cut.png'
        image.save(path)
        return path

    def test_elements_split_and_sidecar(self):
        with tempfile.TemporaryDirectory() as d:
            path = self.blobs(d)
            elements = cs.extract_elements(path)
            self.assertEqual(len(elements), 2)
            self.assertEqual(len(cs.read_elements(path)), 2)
            self.assertGreater(elements[0]['share'], elements[1]['share'])
            for el in elements:
                self.assertTrue(Path(el['path']).is_file())
                with Image.open(el['path']) as piece:
                    self.assertEqual(piece.mode, 'RGBA')

    def test_single_piece_has_no_elements(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertEqual(cs.extract_elements(self.blobs(d, two=False)), [])
            self.assertEqual(cs.read_elements(Path(d) / 'cut.png'), [])

    def test_stylize_adds_stroke_behind_subject_without_a_background(self):
        with tempfile.TemporaryDirectory() as d:
            path = self.blobs(d, two=False)
            before = Image.open(path).convert('RGBA')
            self.assertTrue(cs.stylize(path, sp.style_spec('TWIST')))
            after = Image.open(path).convert('RGBA')
            content = before.getchannel('A').getbbox()
            self.assertGreater(after.width, content[2] - content[0] + 8)  # stroke/glow grows around the subject
            corners = [after.getpixel(p)[3] for p in ((0, 0), (after.width - 1, 0), (0, after.height - 1), (after.width - 1, after.height - 1))]
            self.assertTrue(all(a < 40 for a in corners), corners)  # still a cutout, never a rectangle
            self.assertFalse(cs.stylize(path, None))


if __name__ == '__main__':
    unittest.main()
