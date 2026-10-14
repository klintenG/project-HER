"""News-only RGBA segmentation, conservative edge refinement, QA and content cache."""
from __future__ import annotations
import hashlib
import io
import json
import threading
import uuid
from pathlib import Path
import numpy as np
from PIL import Image, ImageFilter, ImageOps
import config
from agent.news_models import NewsError

class CutoutQualityError(NewsError):
    """An image cannot safely be used as a transparent subject."""


_SESSION_LOCK = threading.Lock()
_SESSIONS = {}


def mask_statistics(image, require_margin=True, allow_geometry=False, allow_group=False, allow_portrait_crop=False, allow_bottom_crop=False):
    if image.mode != "RGBA":
        raise NewsError("Cutout must be RGBA.")
    a = np.asarray(image.getchannel("A"))
    fg = a>32
    coverage = float(fg.mean())
    if not .025 <= coverage <= .88:
        raise NewsError(f"Unusable foreground coverage ({coverage:.3f}); empty/opaque rectangle.")
    ys,xs = np.where(fg)
    box = (int(xs.min()),int(ys.min()),int(xs.max()+1),int(ys.max()+1))
    margin = min(box[0]/image.width,box[1]/image.height,(image.width-box[2])/image.width,(image.height-box[3])/image.height)
    if require_margin and margin < .018:
        # Actual head-and-shoulders photos are intentionally cropped at the torso.
        # Never permit clipped hair/head or side clipping in the upper 55%.
        inset=max(1,round(image.width*.018)); upper=fg[:round(image.height*.55)]
        top_clipped = fg[:inset, :].sum() > 4
        upper_left_clipped = upper[:, :inset].sum() > 4
        upper_right_clipped = upper[:, -inset:].sum() > 4
        bottom_clipped = fg[-inset:, :].sum() > 4
        allow_bottom = allow_portrait_crop or allow_bottom_crop
        portrait_ok = (allow_bottom and not top_clipped and not upper_left_clipped and not upper_right_clipped)
        noise_only = not (top_clipped or upper_left_clipped or upper_right_clipped or bottom_clipped)
        if not (portrait_ok or noise_only):
            raise NewsError("Subject touches image edge; possible clipped head/limb/object.")
    if float((a<8).mean()) < .1:
        raise NewsError("No useful transparent background.")
    if allow_portrait_crop:
        # Dark suits against dark backgrounds can become ghosted while the face
        # survives. A portrait needs solid lower foreground, not a floating face.
        lower=a[box[1]+(box[3]-box[1])//2:box[3],box[0]:box[2]]
        visible=lower>8
        if visible.sum()>.05*fg.sum() and float((lower>230).sum()/max(1,visible.sum()))<.65:
            raise NewsError("Portrait clothing/torso became semitransparent; use a cleaner reference or reference-guided edit.")
    # A near-full foreground bounding rectangle suggests an unremoved backdrop/checkerboard.
    bounded = fg[box[1]:box[3],box[0]:box[2]]
    fill = float(bounded.mean())
    if fill > .98 and not allow_geometry:
        raise NewsError("Rectangular foreground mask; background was not isolated.")
    # Connected components on a bounded thumbnail: large detached blobs are suspect.
    small = np.asarray(Image.fromarray((fg*255).astype('uint8')).resize((128,128),Image.Resampling.NEAREST))>0
    visited = np.zeros_like(small)
    components=[]
    for y,x in zip(*np.where(small)):
        if visited[y,x]:
            continue
        stack=[(int(y),int(x))]; visited[y,x]=True; count=0
        top=bottom=int(y)
        while stack:
            yy,xx=stack.pop(); count+=1
            top=min(top,yy); bottom=max(bottom,yy)
            for ny,nx in ((yy-1,xx),(yy+1,xx),(yy,xx-1),(yy,xx+1)):
                if 0<=ny<128 and 0<=nx<128 and small[ny,nx] and not visited[ny,nx]:
                    visited[ny,nx]=True; stack.append((ny,nx))
        components.append((count,top,bottom+1))
    components.sort(reverse=True)
    counts=[c[0] for c in components]
    detached = sum(c for c in counts[1:] if c>30)/max(1,sum(counts))
    if detached > .045 and not allow_geometry:
        # Explicit groups can have separate people, but not a ground strip or
        # small disconnected debris. Keep the single-subject default strict.
        major=[c for c in components if c[0]>30]
        aligned=all(min(c[2],major[0][2])-max(c[1],major[0][1]) >=
            .5*min(c[2]-c[1],major[0][2]-major[0][1]) for c in major[1:])
        if not (allow_group and 2<=len(major)<=12 and aligned and
                all(c[0]>=major[0][0]*.12 for c in major[1:])):
            raise NewsError("Large detached background/extra foreground components.")
    semi = (a>8)&(a<230)
    halo = float(semi.sum()/max(1,fg.sum()))
    if halo > .55:
        raise NewsError("Excessive semitransparent fringe or unstable mask.")
    return {"coverage":coverage,"transparent_margin":margin,"rect_fill":fill,"detached_fraction":detached,"fringe_fraction":halo}


class CutoutProcessor:
    version = "news-cutout-1.5-rembg-2.0.57"
    def __init__(self, backend=None, models=None, segmenter=None):
        self.backend = backend or config.NEWS_CUTOUT_BACKEND
        self.models = models or config.NEWS_CUTOUT_MODELS
        self.segmenter = segmenter

    def segment(self,image,model):
        if self.segmenter:
            return self.segmenter(image,model)
        if self.backend != "rembg":
            raise NewsError("Opaque News asset needs NEWS_CUTOUT_BACKEND=rembg or a configured segmentation adapter.")
        try:
            from rembg import new_session, remove
        except ImportError as exc:
            raise NewsError("Install requirements-news.txt for CPU background removal; opaque images cannot be rendered in News.") from exc
        # Session initialization and inference serialized for safe worker reuse, never per frame.
        with _SESSION_LOCK:
            if model not in _SESSIONS:
                _SESSIONS[model] = new_session(model,providers=["CPUExecutionProvider"])
            return remove(image,session=_SESSIONS[model],alpha_matting=False)

    def process(self,source,dest,allow_geometry=False,allow_group=False,allow_portrait_crop=False,allow_bottom_crop=False):
        allow_bottom = allow_portrait_crop or allow_bottom_crop
        source,dest = Path(source),Path(dest)
        data=source.read_bytes()
        if len(data)>30_000_000:
            raise NewsError("Generated image exceeds size limit.")
        with Image.open(io.BytesIO(data)) as im:
            if im.width*im.height > 25_000_000:
                raise NewsError("Generated image exceeds pixel limit.")
            original=ImageOps.exif_transpose(im).convert("RGBA")
        cache_key=hashlib.sha256(data+(self.version+self.backend+str(self.models)+str(allow_geometry)+str(allow_group)+str(allow_portrait_crop)+str(allow_bottom_crop)).encode()).hexdigest()
        cache=Path(config.NEWS_CUTOUT_CACHE)/f"{cache_key}.png"
        meta=cache.with_suffix('.json')
        if cache.exists() and meta.exists():
            image=Image.open(cache).convert('RGBA')
            try:stats=mask_statistics(image,allow_geometry=allow_geometry,allow_group=allow_group)
            except NewsError as exc:raise CutoutQualityError(str(exc)) from exc
            dest.parent.mkdir(parents=True,exist_ok=True); image.save(dest)
            return stats,json.loads(meta.read_text())["segmentation"]
        candidates=[("provider_alpha",original)]
        errors=[]
        for model in [None]+list(self.models):
            if model is not None:
                try:
                    candidates=[(f"{self.backend}:{model}",self.segment(original,model).convert("RGBA"))]
                except Exception as exc:
                    errors.append(str(exc)); continue
            for method,candidate_image in candidates:
                variants = [candidate_image]
                if method != "provider_alpha":
                    variants.append(soft_edge_fade(candidate_image, fade_bottom=not allow_bottom))
                for v_idx, image in enumerate(variants):
                    try:
                        # Validate source borders before cropping: adding padding cannot repair a clipped subject.
                        mask_statistics(image,allow_geometry=allow_geometry,allow_group=allow_group,allow_portrait_crop=allow_portrait_crop,allow_bottom_crop=allow_bottom_crop)
                        alpha=image.getchannel('A')
                        # Tiny alpha dust is removed without eroding hair/fur or stripping white highlights.
                        alpha=alpha.point(lambda x: 0 if x<5 else x)
                        image.putalpha(alpha)
                        bounds=alpha.point(lambda x:255 if x>10 else 0).getbbox()
                        if not bounds:
                            raise NewsError("No visible subject remained after background removal.")
                        image=image.crop(bounds)
                        pad=max(8,round(max(image.size)*.045))
                        image=ImageOps.expand(image,border=pad,fill=(0,0,0,0))
                        stats=mask_statistics(image,allow_geometry=allow_geometry,allow_group=allow_group)
                        dest.parent.mkdir(parents=True,exist_ok=True); cache.parent.mkdir(parents=True,exist_ok=True)
                        image.save(dest,format="PNG")
                        temporary=cache.with_name(cache.stem+'-'+uuid.uuid4().hex+'.tmp')
                        image.save(temporary,format="PNG"); temporary.replace(cache)
                        metadata=meta.with_name(meta.stem+'-'+uuid.uuid4().hex+'.tmp')
                        metadata.write_text(json.dumps({"segmentation":method,"mask":stats})); metadata.replace(meta)
                        return stats,method
                    except Exception as exc:
                        if v_idx == len(variants) - 1:
                            errors.append(f"{method}: {exc}")
        raise CutoutQualityError("Cutout quality failed; regenerate isolated subject on a contrasting neutral background. "+"; ".join(errors))


def soft_edge_fade(image, inset_pct=0.025, fade_bottom=True):
    image=image.copy().convert("RGBA")
    a=np.asarray(image.getchannel('A'),dtype=float)
    h,w=a.shape
    iw=max(2,round(w*inset_pct))
    ih=max(2,round(h*inset_pct))
    rx=np.ones(w,dtype=float)
    rx[:iw]=np.linspace(0,1,iw)
    rx[-iw:]=np.linspace(1,0,iw)
    ry=np.ones(h,dtype=float)
    ry[:ih]=np.linspace(0,1,ih)
    if fade_bottom:
        ry[-ih:]=np.linspace(1,0,ih)
    mask=ry[:,None]*rx[None,:]
    image.putalpha(Image.fromarray((a*mask).astype('uint8')))
    return image


def portrait_fade(image):
    image=image.copy().convert("RGBA")
    a=np.asarray(image.getchannel('A'),dtype=float)
    ramp=np.clip((image.height-np.arange(image.height))/(image.height*.13),0,1)
    image.putalpha(Image.fromarray((a*ramp[:,None]).astype('uint8')))
    return image
