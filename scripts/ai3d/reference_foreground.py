"""Shared canvas segmentation for reference scoring and Blender projection.

Input is display/sRGB RGBA bytes, in either row order. This is deliberately
limited to light neutral reference-sheet canvas, not a semantic segmenter.
Only border-connected pixels are removed; enclosed white clothing is retained.
"""
from collections import deque

ALGORITHM = 'LIGHT_NEUTRAL_BORDER_CANVAS_V002'


def foreground_mask(rgba, width, height):
    if width < 1 or height < 1 or len(rgba) != width * height * 4:
        raise ValueError('invalid RGBA buffer dimensions')
    traversable = bytearray(width * height)
    for i in range(width * height):
        r, g, b, a = rgba[i * 4:i * 4 + 4]
        traversable[i] = a <= 2 or (min(r, g, b) >= 214 and max(r, g, b) - min(r, g, b) <= 25)
    visited = bytearray(width * height)
    queue = deque()

    def enqueue(i):
        if traversable[i] and not visited[i]:
            visited[i] = 1
            queue.append(i)

    for x in range(width):
        enqueue(x)
        enqueue((height - 1) * width + x)
    for y in range(height):
        enqueue(y * width)
        enqueue(y * width + width - 1)
    while queue:
        i = queue.popleft()
        x, y = i % width, i // width
        if x: enqueue(i - 1)
        if x + 1 < width: enqueue(i + 1)
        if y: enqueue(i - width)
        if y + 1 < height: enqueue(i + width)
    mask = bytearray(0 if visited[i] or rgba[i * 4 + 3] <= 2 else 255
                     for i in range(width * height))
    left, bottom, right, top = width, height, -1, -1
    active = 0
    for i, value in enumerate(mask):
        if value:
            x, y = i % width, i // width
            left, right = min(left, x), max(right, x)
            bottom, top = min(bottom, y), max(top, y)
            active += 1
    if not active:
        raise ValueError('reference foreground is empty')
    return mask, {
        'algorithm': ALGORITHM,
        'size': [width, height],
        'foregroundBoundsInclusive': [left, bottom, right, top],
        'foregroundPixelRatio': round(active / (width * height), 6),
        'backgroundPixelRatio': round(1 - active / (width * height), 6),
        'limitations': 'LIGHT_NEUTRAL_CANVAS_ONLY_NOT_SEMANTIC_SEGMENTATION',
    }
