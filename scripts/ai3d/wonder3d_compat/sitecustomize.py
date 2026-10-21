"""Process-local compatibility aliases for the pinned Wonder3D stack."""

from __future__ import annotations

import os
import sys
import types


def _load_state_dict_into_model_legacy(model_to_load: object, state_dict: dict) -> list[str]:
    """Backport the small loader removed from modern Diffusers.

    Wonder3D's custom UNet copied the Diffusers 0.19 loader and imports this
    private helper directly.  The modern equivalent still exposes the same
    PyTorch ``_load_from_state_dict`` contract, so keeping this tiny backport
    is safer than installing an old global Diffusers build in a Kaggle
    runtime.
    """

    state_dict = state_dict.copy()
    error_messages: list[str] = []

    def load(module: object, prefix: str = "") -> None:
        args = (state_dict, prefix, {}, True, [], [], error_messages)
        module._load_from_state_dict(*args)  # type: ignore[attr-defined]
        for name, child in module._modules.items():  # type: ignore[attr-defined]
            if child is not None:
                load(child, prefix + name + ".")

    load(model_to_load)
    return error_messages


def _install_diffusers_compatibility() -> None:
    """Install import aliases required by the pinned provider on new runtimes."""

    try:
        import diffusers.models.attention as attention
        import diffusers.models.modeling_utils as modeling_utils
        import diffusers.models.unets.unet_2d_blocks as unet_2d_blocks
        import diffusers.utils as diffusers_utils
        from diffusers.utils import torch_utils

        if not hasattr(modeling_utils, "_load_state_dict_into_model"):
            modeling_utils._load_state_dict_into_model = _load_state_dict_into_model_legacy
        sys.modules.setdefault("diffusers.models.unet_2d_blocks", unet_2d_blocks)
        if not hasattr(diffusers_utils, "DIFFUSERS_CACHE"):
            diffusers_utils.DIFFUSERS_CACHE = os.path.expanduser("~/.cache/diffusers")
        if not hasattr(diffusers_utils, "HF_HUB_OFFLINE"):
            diffusers_utils.HF_HUB_OFFLINE = False
        try:
            from diffusers.models.normalization import AdaGroupNorm

            if not hasattr(attention, "AdaGroupNorm"):
                attention.AdaGroupNorm = AdaGroupNorm
        except Exception:
            pass
        try:
            from diffusers.models.transformers import dual_transformer_2d

            sys.modules.setdefault("diffusers.models.dual_transformer_2d", dual_transformer_2d)
        except Exception:
            pass
        if not hasattr(diffusers_utils, "maybe_allow_in_graph"):
            diffusers_utils.maybe_allow_in_graph = torch_utils.maybe_allow_in_graph
        if not hasattr(diffusers_utils, "randn_tensor"):
            diffusers_utils.randn_tensor = torch_utils.randn_tensor
    except Exception:
        # The provider process will report the original import error if a
        # future runtime moves one of these symbols again.
        pass


def _install_manual_pipeline_loader() -> None:
    """Load Wonder3D custom weights without Diffusers remote-code discovery.

    Diffusers 0.37+ expects ``mvdiffusion.models.*`` files to be copied into
    the Hugging Face checkpoint.  The pinned Wonder3D checkpoint predates
    that convention and keeps the custom UNet in its provider repository.
    This opt-in loader assembles the same pipeline from the pinned local
    class and the checkpoint's standard VAE/CLIP/scheduler components.
    """

    if os.environ.get("RE_CAMP_WONDER3D_MANUAL_PIPELINE", "0") != "1":
        return
    provider_repo = os.environ.get("RE_CAMP_WONDER3D_PROVIDER_REPO")
    if not provider_repo:
        return
    provider_path = os.path.abspath(provider_repo)
    if provider_path not in sys.path:
        sys.path.insert(0, provider_path)

    try:
        import torch
        from diffusers import AutoencoderKL, DDIMScheduler
        from mvdiffusion.models.unet_mv2d_condition import UNetMV2DConditionModel
        from mvdiffusion.pipelines.pipeline_mvdiffusion_image import MVDiffusionImagePipeline
        from transformers import CLIPImageProcessor, CLIPVisionModelWithProjection

        def manual_from_pretrained(cls: object, model_id: str, **kwargs: object) -> object:
            torch_dtype = kwargs.pop("torch_dtype", torch.float16)
            camera_embedding_type = kwargs.pop("camera_embedding_type", "e_de_da_sincos")
            num_views = int(kwargs.pop("num_views", 6))
            unet = UNetMV2DConditionModel.from_pretrained(
                model_id, subfolder="unet", torch_dtype=torch_dtype
            )
            return cls(
                vae=AutoencoderKL.from_pretrained(model_id, subfolder="vae", torch_dtype=torch_dtype),
                image_encoder=CLIPVisionModelWithProjection.from_pretrained(
                    model_id, subfolder="image_encoder", torch_dtype=torch_dtype
                ),
                unet=unet,
                scheduler=DDIMScheduler.from_pretrained(model_id, subfolder="scheduler"),
                safety_checker=None,
                feature_extractor=CLIPImageProcessor.from_pretrained(
                    model_id, subfolder="feature_extractor"
                ),
                requires_safety_checker=False,
                camera_embedding_type=camera_embedding_type,
                num_views=num_views,
            )

        MVDiffusionImagePipeline.from_pretrained = classmethod(manual_from_pretrained)
    except Exception as error:
        os.environ["RE_CAMP_WONDER3D_MANUAL_PIPELINE_ERROR"] = repr(error)


def _install_rembg_fallback() -> None:
    """Keep research-only view generation runnable when rembg is unavailable."""

    try:
        import rembg  # noqa: F401
        return
    except Exception:
        pass

    fallback = types.ModuleType("rembg")

    def remove(image: object, *args: object, **kwargs: object) -> object:
        del args, kwargs
        return image

    fallback.remove = remove  # type: ignore[attr-defined]
    sys.modules["rembg"] = fallback
    os.environ["RE_CAMP_WONDER3D_REMBG_FALLBACK"] = "1"


try:
    import huggingface_hub

    # transformers 5.x expects this legacy helper while Wonder3D's pinned
    # Hub version intentionally stays on the diffusers-compatible 0.23 line.
    if not hasattr(huggingface_hub, "is_offline_mode"):
        huggingface_hub.is_offline_mode = lambda: False
except Exception:  # pragma: no cover - provider startup reports the original error
    pass

try:
    import jax
except Exception:  # pragma: no cover - provider startup reports the original error
    jax = None


if jax is not None and hasattr(jax, "random"):
    # diffusers 0.19.x evaluates this legacy annotation during import.  Newer
    # JAX releases expose the equivalent generic Array type instead.
    _jax_array_type = getattr(jax, "Array", object)
    for _legacy_name in ("KeyArray", "PRNGKeyArray"):
        if not hasattr(jax.random, _legacy_name):
            setattr(jax.random, _legacy_name, _jax_array_type)


# The pinned Wonder3D script calls this optional optimization unconditionally
# and separately checks that xformers is importable.  A minimal marker package
# lives beside this file; the method below keeps the model on standard PyTorch
# attention instead of changing the provider source.
if os.environ.get("RE_CAMP_WONDER3D_DISABLE_XFORMERS", "1") != "0":
    try:
        from diffusers.models.modeling_utils import ModelMixin
        from diffusers.models.attention_processor import Attention

        def _standard_attention_fallback(self: object, *args: object, **kwargs: object) -> None:
            del self, args, kwargs
            return None

        ModelMixin.enable_xformers_memory_efficient_attention = _standard_attention_fallback

        _original_attention_forward = Attention.forward

        def _compat_attention_forward(self: object, *args: object, **kwargs: object) -> object:
            # Wonder3D's custom MV processor predates these optional keywords.
            kwargs.pop("sparse_mv_attention", None)
            kwargs.pop("mvcd_attention", None)
            return _original_attention_forward(self, *args, **kwargs)

        Attention.forward = _compat_attention_forward
    except Exception:  # pragma: no cover - provider startup reports import failures
        pass


# Apply these after the Hub/JAX aliases above.  The manual loader imports
# Transformers during interpreter startup, and Transformers 5 may otherwise
# inspect the Hub module before its legacy helper is present.
_install_diffusers_compatibility()
_install_rembg_fallback()
_install_manual_pipeline_loader()
