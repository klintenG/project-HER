"""Global image/typography pacing without changing approved narration order."""
import hashlib
import random
from .image_policy import number


def pacing_settings():
    return (number('TYPOGRAPHY_BEAT_TARGET',4,True),
            max(1,number('TYPOGRAPHY_MIN_IMAGE_BEATS_BETWEEN',1,True)))


def pacing_issues(modes):
    target,gap=pacing_settings()
    positions=[i for i,mode in enumerate(modes) if mode=='typography']
    issues=[]
    if len(positions)>target:
        issues.append(f'Typography uses {len(positions)} beats; target maximum is {target}')
    if any(b-a<=gap for a,b in zip(positions,positions[1:])):
        issues.append(f'Typography beats must have at least {gap} image/reused-asset beats between them; consecutive text scenes are prohibited')
    if len(positions)>=3 and (positions[0]>=len(modes)/2 or positions[-1]<len(modes)/2 or positions[-1]-positions[0]<(len(modes)-1)/2):
        issues.append('Typography is clustered in one part of the story; distribute suitable low-priority conceptual beats across the narration')
    return issues


def planning_guidance(script):
    """Story-seeded variety is advisory; semantic suitability always wins."""
    target,gap=pacing_settings()
    count=len(script.sentences)
    k=min(target,(count+gap)//(gap+1))
    rng=random.Random(int(hashlib.sha256(script.narration.encode()).hexdigest()[:16],16))
    positions=[]
    for _ in range(32):
        # Map a random subset to spaced indices, keeping the opening visual.
        available=count-1-gap*max(0,k-1)
        if available<k:
            k=max(0,k-1);continue
        positions=[p+gap*i for i,p in enumerate(sorted(rng.sample(range(1,available+1),k)))]
        if not pacing_issues(['typography' if i in positions else 'image' for i in range(count)]):break
    return {'target_maximum':target,'minimum_image_beats_between':gap,
        'suggested_section_ids':[script.sentences[i].id for i in positions],
        'selection_rule':'Analyze the whole story first. Protect essential actions, character introductions and important reveals. Select only lower-priority conceptual beats that communicate clearly without images. Use story-seeded variation only among equally suitable candidates; suggested positions are optional. Never reorder narration, force four text scenes, or substitute text for required physical action. Spread text beats throughout the story; never place them consecutively or as an ending block.'}
