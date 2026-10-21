"""Lift planned image-free beats into the existing measured phrase composition."""
from .models import Bounds
from .image_policy import enabled


def integrate(timeline, script):
    rows=[r for r in script.sentence_storyboard if r.get('media_source')=='typography']
    ids={r['sentence_id'] for r in rows}
    if not ids:return timeline
    word_ids={w.id for w in timeline.words if w.sectionId in ids}
    carriers={a.id for a in timeline.assets if a.source=='Remotion typography composition'}
    for layer in timeline.layers:
        if layer.assetId in carriers:layer.shadow=False
        if layer.phrase and set(layer.phrase.wordIds)&word_ids:
            # Existing line layout was measured by the bundled font engine.
            # Center that layout without changing its line breaks or font size.
            layer.bounds=Bounds(x=90,y=620,w=900,h=500)
            layer.phrase.animation='line_reveal'
            layer.phrase.mode='word_accumulate'
            layer.phrase.align='center'
    timeline.diagnostics['plannedTypography']={'sectionIds':sorted(ids),'wordIds':sorted(word_ids),
        'depthEnabled':enabled('ENABLE_REMOTION_3D_TEXT'),
        'timing':'measured narration word timestamps','subjectImagesGenerated':0}
    return timeline
