"""Cutout styling and multi-element extraction for story visuals.

* ``stylize`` adds the optional sticker stroke / glow so generated art matches the cutout family.
* ``extract_elements`` splits one composition's alpha into separate pieces (e.g. figure + hammer)
  so the renderer can animate them with their own stagger and parallax depth. Pieces are written
  beside the prepared cutout as a JSON sidecar; the full cutout always remains the fallback.

Pure PIL/numpy/scipy; deterministic; never changes subject pixels (stroke/glow go behind them).
"""
from __future__ import annotations
import json
import hashlib
import logging
from pathlib import Path
import numpy as np
from PIL import Image, ImageFilter
from scipy import ndimage

SIDECAR_SUFFIX = '.elements.json'
logger = logging.getLogger(__name__)

def checksum(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def stylize(path, style: dict | None) -> bool:
    """Apply stroke/glow behind the subject, in place. Returns True if the file changed."""
    if not style or not (style.get('stroke') or style.get('glow')):
        return False
    path = Path(path)
    with Image.open(path) as source:
        image = source.convert('RGBA')
    stroke, glow = int(style.get('stroke') or 0), int(style.get('glow') or 0)
    pad = stroke + glow * 2 + 4
    canvas = Image.new('RGBA', (image.width + pad * 2, image.height + pad * 2), (0, 0, 0, 0))
    canvas.paste(image, (pad, pad))
    alpha = canvas.getchannel('A')
    hard = alpha.point(lambda v: 255 if v > 40 else 0)
    layers = []
    if glow:
        halo = hard.filter(ImageFilter.MaxFilter(3 if glow < 20 else 5)).filter(ImageFilter.GaussianBlur(glow))
        halo = halo.point(lambda v: int(v * .55))
        layers.append(_solid(canvas.size, style.get('glowColor', '#f3c969'), halo))
    if stroke:
        grown = hard
        for _ in range(stroke):  # round-ish outline: repeated 3x3 max filter
            grown = grown.filter(ImageFilter.MaxFilter(3))
        grown = grown.filter(ImageFilter.GaussianBlur(.8))
        layers.append(_solid(canvas.size, style.get('strokeColor', '#f4f1ea'), grown))
    result = Image.new('RGBA', canvas.size, (0, 0, 0, 0))
    for layer in layers:
        result = Image.alpha_composite(result, layer)
    result = Image.alpha_composite(result, canvas)
    box = result.getchannel('A').point(lambda v: 255 if v > 8 else 0).getbbox()
    if box:
        result = result.crop((max(0, box[0] - 6), max(0, box[1] - 6), min(result.width, box[2] + 6), min(result.height, box[3] + 6)))
    result.save(path, format='PNG')
    return True


def _solid(size, color, alpha):
    layer = Image.new('RGBA', size, color)
    layer.putalpha(alpha)
    return layer


def _label(path, merge_fraction):
    with Image.open(path) as source:
        image = source.convert('RGBA')
    alpha = np.asarray(image.getchannel('A')) > 40
    if not alpha.any():
        return image, alpha, np.zeros(alpha.shape, int), []
    radius = max(2, int(max(alpha.shape) * merge_fraction))
    # Near neighbours merge (dilation scales with image size) so a figure and the prop it
    # holds stay one element, while genuinely separate pieces become elements.
    labels, _ = ndimage.label(ndimage.binary_dilation(alpha, structure=np.ones((3, 3)), iterations=radius))
    total = alpha.sum()
    found = []
    for index, sl in enumerate(ndimage.find_objects(labels), start=1):
        area = int(((labels[sl] == index) & alpha[sl]).sum())
        found.append((index, (sl[1].start, sl[0].start, sl[1].stop, sl[0].stop), area / total))
    found.sort(key=lambda row: -row[2])
    return image, alpha, labels, found


def components(path, *, min_fraction=.05, merge_fraction=.018, max_elements=4):
    """Significant connected parts of the cutout as (bbox, area_fraction), largest first."""
    _, _, _, found = _label(path, merge_fraction)
    return [(box, share) for _, box, share in found if share >= min_fraction][:max_elements]


def extract_elements(path, *, min_fraction=.05, merge_fraction=.018, max_elements=4):
    """Write element PNGs + sidecar next to ``path``. Returns the element list ([] if single piece)."""
    path = Path(path)
    sidecar = path.with_name(path.stem + SIDECAR_SUFFIX)
    image, alpha, labels, found = _label(path, merge_fraction)
    parts = [row for row in found if row[2] >= min_fraction][:max_elements]
    if len(parts) < 2:
        sidecar.unlink(missing_ok=True)
        return []
    width, height = image.size
    pixels = np.asarray(image)
    elements = []
    for i, (label, (x0, y0, x1, y1), share) in enumerate(parts):
        cropped = pixels.copy()
        cropped[~((labels == label) & (np.asarray(image.getchannel('A')) > 8))] = 0
        crop = Image.fromarray(cropped).crop((x0, y0, x1, y1))
        out = path.with_name(f'{path.stem}.element{i}.png')
        crop.save(out, format='PNG')
        elements.append(dict(path=str(out.resolve()), width=crop.width, height=crop.height,
                             x=x0 / width, y=y0 / height, w=(x1 - x0) / width, h=(y1 - y0) / height, share=round(share, 4), sha256=checksum(out)))
    sidecar.write_text(json.dumps({'version':2, 'sourceSha256':checksum(path), 'width': width, 'height': height, 'elements': elements}, indent=2))
    return elements


def read_elements(path):
    sidecar = Path(path).with_name(Path(path).stem + SIDECAR_SUFFIX)
    if not sidecar.is_file():
        return []
    try:
        data=json.loads(sidecar.read_text())
        elements=data.get('elements', [])
        if data.get('sourceSha256')!=checksum(path) or any(not Path(p['path']).is_file() or p.get('sha256')!=checksum(p['path']) for p in elements):
            logger.warning('Stale or missing cutout elements for %s; preserving combined action cutout',path)
            return []
        return elements
    except (OSError, ValueError, KeyError, TypeError):
        logger.warning('Invalid cutout sidecar for %s; preserving combined action cutout',path)
        return []