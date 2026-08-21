"""Import-only xformers.ops placeholder; standard attention remains active."""


def memory_efficient_attention(*args: object, **kwargs: object) -> None:
    raise RuntimeError("Wonder3D xformers fallback must use standard PyTorch attention")
