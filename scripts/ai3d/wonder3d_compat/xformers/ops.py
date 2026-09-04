"""Small PyTorch fallback for Wonder3D's optional xformers import.

The Kaggle-compatible path intentionally does not install xformers.  Some
diffusers versions still probe ``memory_efficient_attention`` while enabling
the optional processor, so an import-only stub is not sufficient.  This
implementation keeps the same common xformers tensor layouts and uses plain
PyTorch attention instead.
"""

from __future__ import annotations

import torch


def memory_efficient_attention(
    query: torch.Tensor,
    key: torch.Tensor,
    value: torch.Tensor,
    attn_bias: object | None = None,
    p: float = 0.0,
    scale: float | None = None,
    **_: object,
) -> torch.Tensor:
    original_ndim = query.ndim
    if original_ndim == 4:
        # xformers commonly uses [batch, sequence, heads, channels].
        q = query.permute(0, 2, 1, 3)
        k = key.permute(0, 2, 1, 3)
        v = value.permute(0, 2, 1, 3)
    elif original_ndim == 3:
        q, k, v = query.unsqueeze(1), key.unsqueeze(1), value.unsqueeze(1)
    else:
        raise ValueError(f"Unsupported xformers fallback rank: {original_ndim}")

    scale_value = scale if scale is not None else q.shape[-1] ** -0.5
    scores = torch.matmul(q, k.transpose(-2, -1)) * scale_value
    if torch.is_tensor(attn_bias):
        scores = scores + attn_bias
    weights = torch.softmax(scores, dim=-1)
    if p:
        weights = torch.dropout(weights, p, train=True)
    output = torch.matmul(weights, v)
    if original_ndim == 4:
        return output.permute(0, 2, 1, 3)
    return output.squeeze(1)
