"""Scene planning: narration beat -> beat type -> intent -> visual mode -> cutout assets -> motion.

Pipeline position (see also event_storyboard.plan and reference.choreograph)::

    narration -> story beats -> classify_beat -> visual_intent -> select_visual_mode
              -> asset_category / beat-aware prompt -> layout template + motion spec
              -> (assets.py) generate, background-remove, style cutout
              -> (reference.py / EditorialVideo.tsx) animate and render

Everything here is deterministic and offline (no model calls, no randomness), so the same
narration always yields the same plan. A planner LLM may *hint* a beat type; the hint is
validated and falls back to the heuristics below. Nothing here changes narration text.

Design rule enforced by every prompt: story visuals are ISOLATED CUTOUTS for compositing into
the editorial motion-graphics canvas. They are never rectangular scene cards, never full
backgrounds. Props and small environment accents are allowed only as part of one connected
silhouette on a flat backdrop (so background removal keeps them) or as separate accent cutouts.
"""
from __future__ import annotations
import re
from dataclasses import dataclass, field, asdict
from typing import Optional

BEAT_TYPES = ('HOOK', 'CHARACTER_INTRO', 'CONTEXT', 'ACTION', 'EVENT', 'REACTION', 'CONFLICT', 'TWIST', 'OUTRO')
VISUAL_MODES = {
    'HOOK': 'hook_teaser_composition',
    'CHARACTER_INTRO': 'portrait_hero_cutout',
    'CONTEXT': 'context_accent_cutout',
    'ACTION': 'action_character_cutout',
    'EVENT': 'event_scenario_composition',
    'REACTION': 'expressive_reaction_cutout',
    'CONFLICT': 'conflict_duel_cutout',
    'TWIST': 'twist_climax_composition',
    'OUTRO': 'outro_hero_reveal',
}
ASSET_CATEGORIES = ('character', 'action', 'event', 'object', 'environment')
CATEGORY_FOR_TYPE = {
    'HOOK': 'event', 'CHARACTER_INTRO': 'character', 'CONTEXT': 'environment', 'ACTION': 'action',
    'EVENT': 'event', 'REACTION': 'action', 'CONFLICT': 'event', 'TWIST': 'event', 'OUTRO': 'character',
}
# Template names double as Remotion beat templates (models.Template).
TEMPLATES = ('hero-intro', 'dual-tension', 'action-focus', 'event-montage', 'twist-composition', 'reaction-beat')
TEMPLATE_FOR_TYPE = {
    'HOOK': 'twist-composition', 'CHARACTER_INTRO': 'hero-intro', 'CONTEXT': 'event-montage',
    'ACTION': 'action-focus', 'EVENT': 'event-montage', 'REACTION': 'reaction-beat',
    'CONFLICT': 'dual-tension', 'TWIST': 'twist-composition', 'OUTRO': 'hero-intro',
}
# Used to avoid two identical templates in a row (no repeated single-template look).
ALTERNATE_TEMPLATE = {
    'hero-intro': 'action-focus', 'action-focus': 'event-montage', 'event-montage': 'action-focus',
    'dual-tension': 'event-montage', 'twist-composition': 'action-focus', 'reaction-beat': 'action-focus',
}

_W = lambda *words: re.compile(r'\b(?:' + '|'.join(words) + r')\b', re.I)
RX = {
    'hook': re.compile(r'^\s*(?:what if|imagine|picture this|nobody|no one|ever wonder|have you ever|can you|the (?:strangest|most (?:\w+ ){0,2}(?:story|tale))|\w[^.!?]*\?)', re.I),
    'twist': _W('revealed?', 'reveals', 'unmasked?', 'threw off', 'throws off', 'ripped off', 'tore off', 'turned out', 'in truth',
                'it was (?:actually|really)', 'but then', 'suddenly', 'all along', 'the truth', 'true (?:form|identity)', 'transformed'),
    'reaction': _W('gasp(?:ed)?', 'stunned', 'shock(?:ed)?', 'horrified', 'terrified', 'trembl\\w+', 'furious', 'enraged', 'astonish\\w+',
                   'afraid', 'fear(?:ed)?', 'wept', 'cried', 'laughed', 'smiled', 'blush\\w*', 'recoil\\w*', 'stared', 'panick?\\w*', 'frozen', 'speechless'),
    'conflict': _W('refus\\w+', 'demand\\w*', 'argu\\w+', 'threat\\w+', 'battle[sd]?', 'fight\\w*', 'fought', 'war', 'duel\\w*', 'clash\\w*',
                   'against', 'defeat\\w*', 'slew', 'slain', 'attack\\w*', 'rival\\w*', 'confront\\w*', 'rejected?', 'declined?', 'defied?', 'kill\\w*', 'unleash\\w*', 'fury', 'sla[iy]\\w*', 'murder\\w*', 'strangl\\w+', 'smash\\w*', 'crush\\w*'),
    'action': _W('grabbed', 'grab\\w*', 'ate', 'eat\\w*', 'devour\\w*', 'push\\w*', 'rolled?', 'roll\\w+', 'trick\\w+', 'chain\\w*', 'chained', 'dress\\w*',
                 'disguis\\w+', 'climb\\w*', 'swung', 'swing\\w*', 'lift\\w*', 'carr\\w+', 'threw', 'throw\\w*', 'stole', 'steal\\w*', 'snatch\\w*',
                 'escap\\w+', 'fled', 'flee\\w*', 'ran', 'run\\w*', 'jump\\w*', 'drank', 'drink\\w*', 'struck', 'strike\\w*', 'bound', 'tied', 'opened',
                 'wore', 'wear\\w*', 'pulled', 'pull\\w*', 'held', 'hold\\w*', 'forged', 'cast', 'rode', 'rid\\w+', 'dragged', 'fetch\\w*', 'retriev\\w+'),
    'event': _W('feast\\w*', 'banquet', 'wedding', 'ceremony', 'council', 'trial', 'judg\\w+', 'condemn\\w*', 'doom\\w*', 'sentence[sd]?', 'punish\\w+', 'curse[sd]?', 'bless\\w*',
                'gathered', 'arriv\\w+', 'journey\\w*', 'summon\\w*', 'assembl\\w+', 'sacrific\\w+', 'ritual', 'celebrat\\w+', 'negotiat\\w+', 'plan(?:ned|s)?', 'agreed?', 'bargain\\w*', 'vanish\\w*', 'missing', 'stolen'),
    'outro': _W('legacy', 'remembered', 'to this day', 'still', 'forever', 'today', 'that is why', "that's why", 'reminds?', 'eternal\\w*', 'endless\\w*', 'ever since', 'allegory', 'symbol\\w*', 'moral', 'lesson', 'endures?'),
    'intro': _W('was (?:a|an|the)', 'known as', 'god of', 'goddess of', 'king of', 'queen of', 'ruler of', 'famed', 'mighty', 'legendary', 'son of', 'daughter of'),
}
ROLE_TO_TYPE = {'character_intro': 'CHARACTER_INTRO', 'reaction': 'REACTION', 'reveal': 'TWIST'}


@dataclass
class BeatInput:
    """Everything classification needs; all fields except text are optional planner signals."""
    text: str
    index: int = 0
    total: int = 1
    role: Optional[str] = None          # EventSpec.role
    verb: Optional[str] = None          # EventSpec.verb
    event_type: Optional[str] = None
    actors: list = field(default_factory=list)
    objects: list = field(default_factory=list)
    setting: str = ''
    emotion: str = ''
    hint: Optional[str] = None          # planner-supplied beat type
    first_mention: bool = False         # first time an actor appears in the story


@dataclass
class ScenePlan:
    beat_type: str
    visual_intent: str
    visual_mode: str
    asset_category: str
    template: str
    mirror: bool
    prompt_kind: str
    motion: dict
    style: dict

    def as_dict(self):
        return asdict(self)


def classify_beat(b: BeatInput) -> str:
    """Deterministic beat type. Priority encodes dramatic importance, not frequency."""
    text = b.text or ''
    probe = ' '.join([text, b.verb or '', b.event_type or ''])
    hint = (b.hint or '').upper()
    if hint in BEAT_TYPES:
        if hint == 'CHARACTER_INTRO' and RX['action'].search(probe):
            return 'ACTION'
        return hint
    last = b.index == b.total - 1 and b.total > 1
    if b.role in ROLE_TO_TYPE and not (b.role == 'reveal' and not RX['twist'].search(probe) and b.index < 2):
        if b.role == 'character_intro' and RX['action'].search(probe):
            return 'ACTION'
        return ROLE_TO_TYPE[b.role]
    if (b.first_mention or b.index == 0) and RX['intro'].search(text) and not RX['action'].search(probe):
        return 'CHARACTER_INTRO'
    if RX['twist'].search(probe) and not last:
        return 'TWIST'
    if last and RX['outro'].search(text):
        return 'OUTRO'
    if RX['reaction'].search(probe) and not RX['conflict'].search(probe):
        return 'REACTION'
    if RX['conflict'].search(probe):
        return 'CONFLICT'
    if b.index == 0 and RX['hook'].search(text):
        return 'HOOK'
    if (b.first_mention or b.index == 0) and (RX['intro'].search(text) or not (RX['action'].search(probe) or RX['event'].search(probe))):
        return 'CHARACTER_INTRO'
    if RX['event'].search(probe) or len(set(b.actors)) >= 3:
        return 'EVENT'
    if RX['action'].search(probe) or b.verb:
        return 'ACTION'
    if last:
        return 'OUTRO'
    if b.actors:
        return 'ACTION' if len(set(b.actors)) == 1 else 'EVENT'
    return 'CONTEXT'


def visual_intent(beat_type: str, b: BeatInput) -> str:
    """What the viewer must understand with sound off; used in prompts and QC."""
    who = ' and '.join(dict.fromkeys(b.actors)) or 'the story subject'
    what = ', '.join(dict.fromkeys(b.objects))
    core = (b.text or '').strip().rstrip('.')
    return {
        'HOOK': f'A dramatic teaser frame that makes the central tension of "{core}" instantly legible.',
        'CHARACTER_INTRO': f'Introduce {who} clearly: recognisable face, costume and presence, heroic stance.',
        'CONTEXT': f'Establish the situation "{core}" with the key object or place accent' + (f' ({what})' if what else '') + '.',
        'ACTION': f'Show {who} physically performing exactly this action: {core}' + (f', with {what}' if what else '') + '.',
        'EVENT': f'Show the scenario "{core}" as one connected tableau of {who}' + (f' with {what}' if what else '') + '.',
        'REACTION': f'Show {who} visibly reacting (face and body language) to: {core}.',
        'CONFLICT': f'Show the opposition between {who} in a clear confrontation: {core}.',
        'TWIST': f'The strongest dramatic reveal of the story: {core}. Maximum tension and surprise.',
        'OUTRO': f'A resonant closing image of {who} that reflects the meaning of: {core}.',
    }[beat_type]


def select_visual_mode(beat_type: str) -> str:
    return VISUAL_MODES[beat_type]


def asset_category(beat_type: str, b: Optional[BeatInput] = None) -> str:
    """Primary asset category; pure-object beats become object/environment cutouts."""
    if b is not None:
        if not b.actors and b.objects:
            return 'object'
        probe = ' '.join([b.text or '', b.verb or '', b.event_type or ''])
        if beat_type == 'OUTRO' and RX['action'].search(probe):
            return 'action'
    return CATEGORY_FOR_TYPE[beat_type]


def select_layout(beat_type: str, previous_template: Optional[str] = None, previous_mirror: bool = False, actor_count: int = 1):
    """Template per beat type, rotated if identical to the previous beat. Returns (template, mirror)."""
    template = TEMPLATE_FOR_TYPE[beat_type]
    if beat_type == 'CONFLICT' and actor_count < 2:
        template = 'action-focus'
    if template == previous_template and beat_type not in ('TWIST',):
        template = ALTERNATE_TEMPLATE[template]
    # Mirror horizontally against the previous composition to vary screen balance.
    mirror = (not previous_mirror) if previous_template is not None else False
    return template, mirror


# ---- Beat-aware cutout prompts -----------------------------------------------------------------
CUTOUT_SUFFIX = (
    'OUTPUT RULES FOR CUTOUT COMPOSITING: one single isolated foreground cutout on a perfectly flat, solid, '
    'evenly lit mid-gray (#808080) backdrop that shares no colour with the subject. All figures and props touch or overlap '
    'so they form ONE connected silhouette. At least 15 percent empty margin on every side; nothing cropped at the frame edge. '
    'NO scenery, NO room interior, NO walls, NO floor plane, NO horizon, NO vignette, NO border, NO frame, NO cast background shadow. '
    'At most small attached props that physically touch the subject. Crisp clean edges, readable at phone size, '
    'premium editorial illustration, same illustration style and character designs as the supplied references. '
    'No text, lettering, captions, logos or watermarks.')

PROMPT_TEMPLATES = {
    'CHARACTER_INTRO': 'Hero introduction cutout of {subjects}. Full-body, confident three-quarter stance, face fully visible, '
                       'costume and signature attributes clearly shown. {description}',
    'ACTION': 'Action cutout. {subjects} caught at the decisive moment of this exact action: {action}. Dynamic full-body pose with '
              'visible contact with {objects}. This is NOT a standing portrait: body, limbs and props must show the action. {description}',
    'EVENT': 'Event scenario cutout composition. {subjects} and {objects} arranged as ONE connected tableau depicting: {action}. '
             'Show every required participant and prop interacting; keep props (table, food, barrels, hammer, etc.) small and attached. {description}',
    'REACTION': 'Expressive reaction cutout. {subjects} reacting to: {action}. Exaggerated readable facial expression, '
                'body language and hand gestures, upper body to full body. {description}',
    'CONFLICT': 'Conflict cutout. {subjects} in direct confrontation: {action}. Opposed poses facing each other, clear tension in '
                'posture and gaze, connected by overlapping gesture or shared prop. {description}',
    'TWIST': 'Climactic twist cutout, the single most dramatic image in the story. {subjects}: {action}. Heroic low-angle pose, '
             'explosive body language, intense expression, strong rim lighting, maximum drama and impact. {description}',
    'HOOK': 'Teaser cutout composition that dramatises the story\'s central tension: {action}. {subjects}, {objects}. Bold and instantly '
            'readable, strong silhouette. {description}',
    'CONTEXT': 'Context accent cutout showing {objects} in the situation: {action}. Compact object-and-subject grouping, single focal '
               'point. {description}',
    'OUTRO': 'Closing hero cutout of {subjects} reflecting the story\'s meaning: {action}. Calm, resonant, iconic pose. {description}',
}
ACCENT_PROMPTS = {
    'object': 'Isolated object cutout: {subject}. A single prop with correct material and period design, shown large and clear, three-quarter view.',
    'environment': 'Environment accent cutout: {subject}. A small self-contained fragment (e.g. a single archway, table, tree, rock or altar) '
                   'that stands alone as one object, not a full scene.',
}


def build_prompt(beat_type: str, *, subjects='', action='', objects='', description='', state='', forbidden='', identity_note='') -> str:
    """Beat-aware prompt. Every variant ends with the same cutout/compositing output rules."""
    subjects = subjects or 'the story characters'
    objects = objects or 'any narrated props'
    if beat_type == 'OUTRO' and RX['action'].search(action):
        template = 'Closing action cutout of {subjects} reflecting the story\'s meaning: {action}. Depict the ongoing action rather than a neutral portrait. {description}'
    else:
        template = PROMPT_TEMPLATES[beat_type]
    body = template.format(subjects=subjects, action=action or 'the narrated moment', objects=objects,
                           description=(description or '').strip())
    extras = []
    if state:
        extras.append('Required costume and prop state: ' + state + '.')
    if identity_note:
        extras.append(identity_note)
    if forbidden:
        extras.append('Must NOT show: ' + forbidden + '.')
    return ' '.join([body, *extras, CUTOUT_SUFFIX]).replace('  ', ' ')


def accent_prompt(category: str, subject: str) -> str:
    return ACCENT_PROMPTS[category].format(subject=subject) + ' ' + CUTOUT_SUFFIX


# ---- Motion and style --------------------------------------------------------------------------
_ENTRANCE = {
    'HOOK': 'slam', 'CHARACTER_INTRO': 'rise', 'CONTEXT': 'pop', 'ACTION': 'slide', 'EVENT': 'pop',
    'REACTION': 'punch', 'CONFLICT': 'slide', 'TWIST': 'slam', 'OUTRO': 'rise',
}
_MOTION = {
    #            frames drift(x,y px)  scaleTo tilt  depth
    'HOOK': (14, (0, -26), 1.07, 0, .5), 'CHARACTER_INTRO': (20, (0, -14), 1.04, 0, .3),
    'CONTEXT': (16, (10, -10), 1.05, 0, .35), 'ACTION': (13, (34, -8), 1.08, 3, .6),
    'EVENT': (16, (-14, -18), 1.06, 0, .55), 'REACTION': (10, (0, -10), 1.09, -3, .45),
    'CONFLICT': (14, (22, 0), 1.07, 2, .6), 'TWIST': (12, (0, -34), 1.12, 0, .8), 'OUTRO': (24, (0, -10), 1.03, 0, .25),
}


def motion_spec(beat_type: str, mirror: bool = False) -> dict:
    frames, (dx, dy), scale_to, tilt, depth = _MOTION[beat_type]
    entrance = _ENTRANCE[beat_type]
    sign = -1 if mirror else 1
    if entrance == 'slide':
        entrance = 'slide_right' if mirror else 'slide_left'
    return dict(entrance=entrance, exit='shrink' if beat_type == 'TWIST' else 'fade', entranceFrames=frames,
                driftX=dx * sign, driftY=dy, scaleTo=scale_to, tilt=tilt * sign, parallaxDepth=depth)


def style_spec(beat_type: str) -> dict:
    """Optional sticker-stroke / glow / shadow so generated art reads as the same cutout family."""
    return dict(stroke=4 if beat_type != 'CHARACTER_INTRO' else 0, strokeColor='#f4f1ea',
                glow=26 if beat_type in ('TWIST', 'HOOK') else 0, glowColor='#f3c969', shadow=True)


def plan_beat(b: BeatInput, previous: Optional[ScenePlan] = None) -> ScenePlan:
    beat_type = classify_beat(b)
    template, mirror = select_layout(beat_type, previous.template if previous else None, previous.mirror if previous else False, len(set(b.actors)) or 1)
    return ScenePlan(beat_type=beat_type, visual_intent=visual_intent(beat_type, b), visual_mode=select_visual_mode(beat_type),
                     asset_category=asset_category(beat_type, b), template=template, mirror=mirror,
                     prompt_kind=beat_type, motion=motion_spec(beat_type, mirror), style=style_spec(beat_type))


def plan_story(beats: list[BeatInput]) -> list[ScenePlan]:
    """Plan a whole story in order, applying variety rules between neighbouring beats."""
    plans: list[ScenePlan] = []
    for b in beats:
        plans.append(plan_beat(b, plans[-1] if plans else None))
    return plans


# ---- Layout geometry (1080 x 1920 canvas; caption box, then asset boxes) ------------------------
def geometry(template: str, count: int, mirror: bool = False, text_below: bool = False):
    """Return (caption, [asset boxes]) as dicts x,y,w,h. Boxes never overlap the caption."""
    def box(x, y, w, h):
        return dict(x=x, y=y, w=w, h=h)
    def flip(b):
        return box(1080 - b['x'] - b['w'], b['y'], b['w'], b['h']) if mirror else b
    if template == 'hero-intro':
        cap = box(95, 300, 890, 230)
        main = box(180, 600, 720, 790)
        side = [box(30, 980, 260, 360), box(790, 980, 260, 360)]
        return cap, [main, *[flip(s) for s in side]][:max(1, count)]
    if template == 'action-focus':
        if text_below:
            cap, main = box(95, 1400, 890, 240), box(50, 360, 980, 1000)
        else:
            cap, main = box(95, 290, 890, 230), box(50, 560, 980, 880)
        return cap, [main, flip(box(740, 1010, 300, 380)), flip(box(40, 1050, 260, 330))][:max(1, count)]
    if template == 'event-montage':
        cap = box(95, 280, 890, 230)
        main = box(60, 560, 960, 790)
        return cap, [main, flip(box(730, 1000, 310, 400)), flip(box(30, 1060, 270, 340))][:max(1, count)]
    if template == 'dual-tension':
        cap = box(95, 290, 890, 230)
        if count >= 2:
            return cap, [box(30, 600, 560, 780), box(490, 660, 560, 740), flip(box(380, 1180, 320, 260))][:count]
        return cap, [box(40, 600, 1000, 760)]
    if template == 'twist-composition':
        cap = box(95, 1420, 890, 230)
        return cap, [box(10, 270, 1060, 1110), flip(box(760, 1040, 300, 380)), flip(box(30, 1060, 260, 330))][:max(1, count)]
    if template == 'reaction-beat':
        cap = flip(box(50, 700, 380, 620))
        return cap, [flip(box(440, 480, 600, 880)), flip(box(60, 1290, 260, 330))][:max(1, count)]
    raise ValueError('Unknown scene template: ' + template)