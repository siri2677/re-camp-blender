"""Process-local compatibility aliases for the pinned Wonder3D stack."""

from __future__ import annotations

import os

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
