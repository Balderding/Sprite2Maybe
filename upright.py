"""Stand a tilted sprite upright (a sword drawn corner to corner becomes tip up, grip down).

The tilt is the long axis of the visible pixels (snapped to 45, 26.6 or 63.4 degrees when within 8 of one of them).
The sprite is turned by cleanEdge (cleanedge.py: every pixel stays one of the sprite's own colours) and drawn 1.5x
bigger (smaller if it would not fit twice the sprite's size), then its outline is tidied the way work\\swordrot does
it: background touching a colour becomes outline, a notch of outline biting into the body is filled, and outline
that faces only background is peeled off (so the outline stays one pixel wide). The outline steps are done only
when the sprite's colours were fenced in by its outline to begin with.
"""
import math
import numpy as np
from PIL import Image
from cleanedge import CleanEdge, crop

SNAP = (45.0, math.degrees(math.atan(0.5)), math.degrees(math.atan(2.0)))
MIN_TILT, MAX_TILT, LONG = 12.0, 78.0, 2.5     # stood up only when tilted this much and this long (axis ratio)


def masks(a):
    op = a[..., 3] > 0
    blk = op & (a[..., :3].astype(int).sum(-1) < 40)
    return op, blk, op & ~blk


def near(m, diag=False):
    p = np.pad(m, 1)
    r = p[:-2, 1:-1] | p[2:, 1:-1] | p[1:-1, :-2] | p[1:-1, 2:]
    if diag:
        r |= p[:-2, :-2] | p[:-2, 2:] | p[2:, :-2] | p[2:, 2:]
    return r


def _outline_colour(a):
    op, blk, col = masks(a)
    return tuple(int(v) for v in np.median(a[blk][:, :3], 0)) + (255,) if blk.any() else (0, 0, 0, 255)


def close(a, ink):
    a = a.copy(); op, blk, col = masks(a)
    a[~op & near(col)] = ink
    return a


def notch(a):
    a = a.copy(); op, blk, col = masks(a); src = a.copy()
    H, W = a.shape[:2]
    for y in range(1, H - 1):
        for x in range(1, W - 1):
            if blk[y, x] and col[y - 1, x] and col[y + 1, x] and (col[y, x - 1] != col[y, x + 1]) and (blk[y, x - 1] or blk[y, x + 1]):
                a[y, x] = src[y, x + 1] if col[y, x + 1] else src[y, x - 1]
    return a


def peel(a):
    a = a.copy()
    while True:
        op, blk, col = masks(a)
        kill = blk & ~near(col) & near(~op)
        if not kill.any():
            return a
        a[kill] = 0


def tilt_of(a):
    """(degrees, long): + leans right, - leans left; long = how many times longer than wide the sprite is"""
    ys, xs = np.nonzero(a[..., 3] > 0)
    if len(xs) < 3:
        return 0.0, 1.0
    w, v = np.linalg.eigh(np.cov(np.vstack([xs, ys]).astype(float)))
    longness = math.sqrt(max(w[1], 1e-9) / max(w[0], 1e-9))
    vx, vy = v[0, 1], v[1, 1]
    if vy > 0:
        vx, vy = -vx, -vy                      # point the axis at its upper end
    t = math.degrees(math.atan2(vx, -vy))
    for sn in SNAP:
        if abs(abs(t) - sn) <= 8:
            return math.copysign(sn, t), longness
    return t, longness


def stand_up(im, angle=None):
    """(picture, degrees turned clockwise). angle None: measured, and 0 (the picture as it is) when the sprite is not
    both tilted and long; otherwise turned by that many degrees clockwise."""
    im = im.convert("RGBA"); a0 = np.asarray(im)
    if angle is None:
        t, longness = tilt_of(a0)
        if longness < LONG or not (MIN_TILT <= abs(t) <= MAX_TILT):
            return im, 0.0
        angle = -t
    if abs(angle) < 0.01:
        return im, 0.0
    op, blk, col = masks(a0)
    exposed = (col & near(~op)).sum() / max(1, col.sum())
    fenced = (blk & near(col, True)).sum() / max(1, blk.sum())
    outlined = blk.sum() > 0 and exposed < 0.15 and fenced > 0.9
    ink = _outline_colour(a0)
    cap = 2 * max(im.width, im.height)
    ce = CleanEdge(im)
    scale = 1.5
    while True:
        a = np.asarray(ce.render(angle, scale))
        if outlined:
            a = peel(notch(close(a, ink)))
        o = crop(Image.fromarray(a))
        if (o.width <= cap and o.height <= cap) or scale <= 0.8:
            break
        scale = round(scale - 0.05, 2)
    side = max(cap, o.width, o.height)
    can = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    can.paste(o, ((side - o.width) // 2, (side - o.height) // 2))
    return can, float(angle)
