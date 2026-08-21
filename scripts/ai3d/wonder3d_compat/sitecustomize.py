"""Process-local compatibility aliases for the pinned Wonder3D stack."""

from __future__ import annotations

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
