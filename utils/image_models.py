"""Replicate image model capabilities and schema translation.

Selection belongs to config.py; this module only describes supported adapters.
Unknown model IDs require an explicit, compatible adapter setting.
"""
from __future__ import annotations

from dataclasses import dataclass
import re


class ImageModelConfigError(ValueError):
    pass


@dataclass(frozen=True)
class Adapter:
    name: str
    text: bool = True
    references: int = 0  # 0: none, 1: one, -1: multiple


ADAPTERS = {
    "flux_schnell": Adapter("flux_schnell"),
    "flux_pro": Adapter("flux_pro"),
    "flux_dev": Adapter("flux_dev", references=1),
    "pruna_edit": Adapter("pruna_edit", text=False, references=-1),
    "flux_kontext": Adapter("flux_kontext", references=1),
    "nano_banana": Adapter("nano_banana", references=-1),
}
KNOWN_MODELS = {
    "black-forest-labs/flux-schnell": "flux_schnell",
    "black-forest-labs/flux-1.1-pro": "flux_pro",
    "black-forest-labs/flux-dev": "flux_dev",
    "black-forest-labs/flux-kontext-pro": "flux_kontext",
    "black-forest-labs/flux-kontext-dev": "flux_kontext",
    "prunaai/p-image-edit": "pruna_edit",
    "google/nano-banana-pro": "nano_banana",
}


def adapter_for(model: str, adapter_name: str | None = None) -> Adapter:
    if not isinstance(model, str) or not re.fullmatch(r"[a-zA-Z0-9_.-]+/[a-zA-Z0-9_.-]+", model):
        raise ImageModelConfigError(f"Invalid Replicate image model ID: {model!r}")
    known = KNOWN_MODELS.get(model)
    if known and adapter_name and adapter_name != known:
        raise ImageModelConfigError(f"{model} requires adapter {known}, not {adapter_name}")
    name = adapter_name or known
    if name not in ADAPTERS:
        raise ImageModelConfigError(f"Unsupported image model {model}; set its role's PROJECTHER_IMAGE_*_ADAPTER to a verified compatible adapter")
    return ADAPTERS[name]


def validate_role(role: str, model: str, adapter_name: str | None = None) -> Adapter:
    adapter = adapter_for(model, adapter_name)
    if role in ("continuity", "premium", "alternate_edit") and not adapter.references:
        raise ImageModelConfigError(f"Continuity model {model} cannot edit a reference image")
    if role in ("identity", "support", "support_fallback") and not adapter.text:
        raise ImageModelConfigError(f"{role} model {model} requires a reference image")
    return adapter


def build_input(model: str, prompt: str, references: list[str] | None = None,
                aspect_ratio: str = "1:1", turbo: bool | None = None,
                seed: int | None = None, adapter_name: str | None = None) -> dict:
    adapter = adapter_for(model, adapter_name)
    refs = references or []
    if refs and adapter.references == 0:
        raise ImageModelConfigError(f"{model} does not support reference-image editing")
    if len(refs) > 1 and adapter.references == 1:
        raise ImageModelConfigError(f"{model} supports only one reference image; {len(refs)} were supplied")
    if not refs and not adapter.text:
        raise ImageModelConfigError(f"{model} requires at least one reference image")
    result = {"prompt": prompt, "aspect_ratio": aspect_ratio or "1:1"}
    if adapter.name == "pruna_edit":
        result["images"] = refs
        if turbo is not None:
            result["turbo"] = bool(turbo)
    elif adapter.name == "nano_banana":
        result.update(output_format="png", resolution="2K", allow_fallback_model=False)
        if refs:
            result["image_input"] = refs
    elif adapter.name == "flux_kontext":
        result["output_format"] = "png"
        if model == "black-forest-labs/flux-kontext-pro":
            result["prompt_upsampling"] = False
        if refs:
            result["input_image"] = refs[0]
    elif adapter.name == "flux_dev":
        result.update(output_format="png", num_outputs=1, num_inference_steps=28, megapixels="1")
        if refs:
            result["image"] = refs[0]
    elif adapter.name == "flux_schnell":
        result.update(output_format="png", num_outputs=1, num_inference_steps=4)
    elif adapter.name == "flux_pro":
        result.update(output_format="png", prompt_upsampling=False)
    if seed is not None and adapter.name != "nano_banana":
        result["seed"] = seed
    return result
