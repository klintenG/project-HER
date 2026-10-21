"""Per-video image policy. Prices are estimates, never a claim of provider billing."""
from dataclasses import dataclass
import math
import os
from utils.image_models import adapter_for
from agent.news_models import NewsError


def enabled(name, default=True):
    value=os.getenv(name, str(default)).lower()
    if value not in ('true','false','1','0','yes','no'):
        raise ValueError(f'{name} must be a boolean')
    return value in ('true','1','yes')


def number(name, default, integer=False):
    raw=os.getenv(name, str(default))
    value=int(raw) if integer else float(raw)
    if not math.isfinite(value) or value<0:
        raise ValueError(f'{name} must be finite and nonnegative')
    return value


@dataclass(frozen=True)
class ImagePolicy:
    character: str
    object: str
    background: str
    simple: str
    action: str
    schnell_retries: int
    image_budget: float
    total_budget: float
    other_reserved: float
    schnell_price: float
    seedream_price: float
    max_images: int
    max_actions: int
    ratio: float

    @classmethod
    def load(cls):
        p=cls(*(os.getenv({'CHARACTER_IMAGE_MODEL':'IMAGE_CHARACTER_MODEL','OBJECT_IMAGE_MODEL':'IMAGE_PROP_MODEL','ACTION_IMAGE_MODEL':'IMAGE_ACTION_MODEL'}.get(name,name),os.getenv(name,default)) for name,default in (
            ('CHARACTER_IMAGE_MODEL','black-forest-labs/flux-schnell'),
            ('OBJECT_IMAGE_MODEL','black-forest-labs/flux-schnell'),
            ('BACKGROUND_IMAGE_MODEL','black-forest-labs/flux-schnell'),
            ('SIMPLE_IMAGE_MODEL','black-forest-labs/flux-schnell'),
            ('ACTION_IMAGE_MODEL','bytedance/seedream-4'))),
            number('SCHNELL_MAX_RETRIES',2,True),number('IMAGE_ESTIMATED_BUDGET_USD',number('MAX_IMAGE_BUDGET_USD',.60)),
            number('MAX_TOTAL_VIDEO_BUDGET_USD',.80),number('OTHER_SERVICES_RESERVED_USD',.08),
            number('SCHNELL_ESTIMATED_COST_USD',.003),number('SEEDREAM_ESTIMATED_COST_USD',.03),
            number('GENERATED_IMAGE_MAX',24,True),number('MAX_SEEDREAM_ACTION_IMAGES',16,True),
            number('TARGET_SCHNELL_RATIO',.70))
        if p.ratio>1: raise ValueError('TARGET_SCHNELL_RATIO must be <= 1')
        for model in (p.character,p.object,p.background,p.simple):
            if adapter_for(model).name!='flux_schnell': raise ValueError('Simple image roles require the Schnell adapter')
        if adapter_for(p.action).name!='seedream': raise ValueError('ACTION_IMAGE_MODEL requires Seedream 4')
        if number('SEEDREAM_MAX_RETRIES',0,True)!=0 or number('SEEDREAM_MAX_IMAGES',1,True)!=1 or os.getenv('SEEDREAM_SEQUENTIAL_GENERATION','disabled')!='disabled':
            raise ValueError('Seedream requires zero retries, one image and disabled sequential generation')
        if enabled('ENABLE_PREMIUM_FALLBACK',False) or enabled('ENABLE_AUTOMATIC_MODEL_SWITCHING',False):
            raise ValueError('Automatic premium fallback/model switching is unsupported by the smart image policy')
        return p

    def price(self,model):
        return self.seedream_price if model==self.action else self.schnell_price

    def check(self, spent, cost):
        if spent+cost>self.image_budget+1e-9 or spent+cost+self.other_reserved>self.total_budget+1e-9:
            raise NewsError(f'Generation budget conflict; no image request submitted. Planned/reserved images ${spent+cost:.3f} vs image budget ${self.image_budget:.3f}; including non-image reservation ${self.other_reserved:.3f}, total ${spent+cost+self.other_reserved:.3f} vs video budget ${self.total_budget:.3f}. Review MAX_IMAGE_BUDGET_USD (or IMAGE_ESTIMATED_BUDGET_USD) and MAX_TOTAL_VIDEO_BUDGET_USD.')


def negative_constraints(kinds, count=1):
    if not enabled('ENABLE_NEGATIVE_CONSTRAINTS'):return ''
    parts=['No captions, lettering, watermark, border, unrelated subjects or visual artifacts.']
    if 'person' in kinds:
        parts.append('Each human has exactly one head, two arms, two hands and two legs with anatomically appropriate fingers unless explicitly narrated otherwise; no missing, duplicated or fused limbs, fingers, floating body parts, distorted faces or impossible joints. Preserve clothing and identity; believable contact with props.')
    if 'animal' in kinds:
        parts.append('Correct species anatomy, natural posture and movement; appropriate limb, wing, head and tail counts; no duplicated parts, hybrids or unrelated animals.')
    if any(k not in ('person','animal') for k in kinds):
        parts.append('Correct object geometry and proportions; no duplicated, fused or floating tools, decorative alterations or impossible contact.')
    if count>1:
        parts.append(f'Exactly {count} requested characters, with correct identity assignment, eye direction and contact. No swapped faces, outfits or hairstyles, merged bodies or unintended people. Respect specified left/right placement; separate silhouettes unless the action requires contact.')
    return ' '.join(parts)


def scene_prompt(story, subject, visual, kinds, references=(), spatial='', presentation='', forbidden=()):
    """Both adapters embed constraints in prompt; neither accepts negative_prompt."""
    if not enabled('ENABLE_CONTEXT_AWARE_PROMPTS'):
        from .scene_plan import CUTOUT_SUFFIX
        return visual+' '+negative_constraints(kinds,len(references) or 1)+' '+'; '.join(forbidden)+' '+CUTOUT_SUFFIX
    return '\n'.join((
        'A. Story context: '+story,
        'B. Subject identity: '+subject,
        'C. Requested visual: '+visual,
        'D. Physical/spatial relationships: '+(spatial or 'Follow the narrated contact, direction and placement exactly; do not add interactions.'),
        'E. Visual presentation: '+(presentation or 'Existing cinematic editorial illustration style, readable three-quarter view, coherent soft light; flat contrasting backdrop for cutout extraction.'),
        'F. Preservation: '+('Reference order: '+', '.join(references)+'. Use reference images for identity only; do not carry unrequested props or preserve the reference pose. Preserve original faces, hair, costumes (unless the scene changes them), body proportions and artistic style. Change only narrated pose, expression, camera and setting.' if references else 'Establish a clear canonical subject design appropriate to the story era.'),
        'G. Negative constraints: '+negative_constraints(kinds,len(references) or 1)+' '+'; '.join(forbidden),
        'H. Output: isolated die-cut editorial artwork, not a scene panel. Full subject and essential contact props visible, 20 percent uniform contrasting matte around every subject edge. No square card, rectangular backdrop, picture frame, checkerboard texture, gradient or baked shadow. Request real alpha transparency if supported; never paint a checkerboard to imitate transparency. If alpha is unavailable, use the specified flat mid-gray matte for local background removal. 3:4 source for 9:16 compositing; generous margins and complete silhouettes.'))
