"""Structural delivery gates and honest visual-review requirements."""
from .canonical import assert_locked


def audit_timeline(script,timeline,canonical):
    assert_locked(script,canonical)
    if timeline.scriptHash != canonical['sha256']:
        raise ValueError('Timeline does not use the locked narration.')
    if [w.text for w in timeline.words] != script.narration.split():
        raise ValueError('Missing, duplicated or rewritten narration words.')
    if any(w.provenance=='estimated_phrase' for w in timeline.words):
        raise ValueError('Editorial delivery requires measured word alignment.')
    if script.narrative_plan and script.sentence_storyboard:
        script.narrative_plan.validate_coverage(script)
    for row in script.sentence_storyboard:
        if set(row.get('depicted_entity_ids',row.get('identity_reference_ids',[]))) & set(row.get('secondary_entity_ids',[])):
            raise ValueError('Character appears in composite and secondary: '+row['sentence_id'])
    actions=timeline.diagnostics.get('actionChoreography',{}).get('actions',[])
    final_word=timeline.words[-1].end if timeline.words else 0
    hold=timeline.durationInFrames/timeline.fps-final_word
    if hold < .55:
        raise ValueError('Final narration needs a readable story hold before branding.')
    return {'scriptHash':canonical['sha256'],'wordCoveragePassed':True,
        'measuredAlignmentPassed':True,'duplicateMembershipPassed':True,
        'finalWordSeconds':final_word,'storyEndSeconds':timeline.durationInFrames/timeline.fps,
        'finalHoldSeconds':round(hold,3),'compositeFallbackActions':len(actions),
        'visualAcceptancePassed':False if actions else None,
        'manualReviewRequired':True,
        'scope':'Structural checks pass; rendered visual action/anatomy and audio listening require review.'}
