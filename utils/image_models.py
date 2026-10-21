"""The complete supported Replicate image-model allowlist and request schemas."""
from __future__ import annotations
from dataclasses import dataclass


class ImageModelConfigError(ValueError):
    pass


@dataclass(frozen=True)
class Adapter:
    name: str
    text: bool = True
    references: int = 0


ADAPTERS = {
    'flux_schnell': Adapter('flux_schnell'),
    'seedream': Adapter('seedream', references=-1),
}
KNOWN_MODELS = {
    'black-forest-labs/flux-schnell': 'flux_schnell',
    'bytedance/seedream-4': 'seedream',
}


def adapter_for(model: str, adapter_name: str | None = None) -> Adapter:
    name=KNOWN_MODELS.get(model) if isinstance(model,str) else None
    if name is None:
        raise ImageModelConfigError(f'Unsupported image model {model!r}; only FLUX Schnell and Seedream 4 are supported')
    if adapter_name and adapter_name!=name:
        raise ImageModelConfigError(f'{model} requires adapter {name}, not {adapter_name}')
    return ADAPTERS[name]


def validate_role(role: str, model: str, adapter_name: str | None = None) -> Adapter:
    adapter=adapter_for(model,adapter_name)
    expected='seedream' if role in ('continuity','action','event','reference') else 'flux_schnell'
    if adapter.name!=expected:
        raise ImageModelConfigError(f'Image role {role} requires the {expected} adapter')
    return adapter


def build_input(model: str, prompt: str, references: list[str] | None = None,
                aspect_ratio: str = '1:1', seed: int | None = None,
                adapter_name: str | None = None, size: str = '2K',
                enhance_prompt: bool = True) -> dict:
    adapter=adapter_for(model,adapter_name)
    refs=references or []
    if refs and not adapter.references:
        raise ImageModelConfigError(f'{model} does not support reference-image editing')
    result={'prompt':prompt,'aspect_ratio':aspect_ratio or '1:1'}
    if adapter.name=='seedream':
        if len(refs)>10:raise ImageModelConfigError('Seedream supports at most 10 image references')
        if size not in ('1K','2K','4K'):raise ImageModelConfigError('Invalid Seedream size')
        result.update(size=size,enhance_prompt=enhance_prompt,max_images=1,sequential_image_generation='disabled')
        if refs:result['image_input']=refs
    else:
        result.update(output_format='png',num_outputs=1,num_inference_steps=4)
    if seed is not None:result['seed']=seed
    return result
