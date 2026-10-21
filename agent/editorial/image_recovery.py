"""Local recovery of paid artwork. Never substitutes an unrelated scene or calls a provider."""
from pathlib import Path
import json
from PIL import Image, ImageOps, UnidentifiedImageError
from agent.news_models import NewsError


def deliver_with_warnings():
    import config
    return config.IMAGE_FAILURE_POLICY=='deliver_with_warnings'


def usable(path):
    try:
        with Image.open(path) as im:
            im.load()
            return im.width>=32 and im.height>=32 and (im.mode!='RGBA' or im.getchannel('A').getbbox() is not None)
    except (OSError,ValueError,UnidentifiedImageError):return False


def preserve(entity, raw, cut, output, reason, record=None, provider='saved generated artwork'):
    """Keep the scene as a true cutout; repair masks locally, never use panels."""
    from .assets import prepare, label_fallback
    from agent.cutout_processor import repair_cutout, usable_cutout, CutoutQualityError
    output=Path(output);output.mkdir(parents=True,exist_ok=True)
    source=None;method='saved_scene_cutout'
    if cut and usable(cut):
        with Image.open(cut) as image:
            if usable_cutout(image):source=Path(cut)
    if source is None and raw and usable(raw):
        source=output/(Path(raw).stem+'-alpha-recovered.png')
        try:method=repair_cutout(raw,source)
        except CutoutQualityError as exc:
            if record is not None:
                record.update(route='unavailable_cutout',degraded=True,fallbackMethod='unavailable_cutout',reviewWarning=str(reason)+'; '+str(exc),recoveryNoGeneration=True)
            return label_fallback(entity.model_copy(update={'name':'Visual unavailable'}),output,'Original saved; background isolation unavailable. '+str(reason))
    if source is None:
        raise NewsError('No decodable image was saved for '+entity.id+'. Recovery will not submit another paid request.','recoverable_media_failure')
    asset=prepare(entity,source,output,source=provider,license='Generated illustration',attribution=provider,role='context',factual=False)
    asset=asset.model_copy(update={'confidence':.2,'assetRole':'CONTEXT','fallback':'Quality warning: scene retained as transparent cutout; semantic approval unchanged. '+str(reason)})
    if record is not None:
        record.update(route=method,degraded=True,fallbackMethod=method,reviewWarning=str(reason),recoveryNoGeneration=True)
    return asset


def saved_request(records, key):
    """An accepted/reserved request can never become another POST on resume."""
    return next((r for r in reversed(records) if r.get('asset_key')==key),None)


def request_fingerprint(text, **settings):
    import hashlib
    return hashlib.sha256(json.dumps({'text':text,**settings},sort_keys=True,default=str).encode()).hexdigest()
