r"""sprite3d.py: a 3D model from a 2D sprite (a PNG with a clear background, the object upright: tip up, grip down).

    python sprite3d.py SPRITE.png [switches]

Four ways to give the flat picture its depth (--method):
    slab     every pixel the same thickness: a plate (what Minecraft does with its item pictures)
    round    thicker the farther a pixel is from the outline: a pillow (the "inflation" method)
    turned   every row a circle as wide as the row: a shape off a lathe (bottles, candles, goblets, gems, wands)
    shaped   by part (the default): a blade is a ridge, a shaft or grip is round, an axe or mace head is a plate with
             a bevelled edge, a guard is a block, a gem is a dome. The parts come from a parts picture (--parts), or
             are guessed from the sprite (the guess is saved, to be corrected in a paint program and given back)

Switches:
    --method slab|round|turned|shaped   (shaped)
    --parts FILE.png               the parts picture: same size as the sprite, each pixel painted its part's colour;
                                   FILE.txt beside it gives each part's label, shape and settings (regions.py). The
                                   guess is written as NAME_parts.png + NAME_parts.txt to start from
    --kind auto|sword|axe|mace|object   what the guess takes the sprite for (auto: a weapon when it is long with a
                                   narrow handle at its foot; otherwise an object, made one lathe, dome or plate part
                                   by its outline)
    --thickness N                  the greatest half-thickness, in sprite pixels (1.5)
    --rim N                        the half-thickness at the outline, in sprite pixels (0.4; slab: the thickness)
    --outline sharp|flat|wrap      the sprite's dark outline (with --mesh pixels; low poly is always sharp). sharp (the default): not drawn; it takes the colour beside
                                   it and the shape runs to a sharp edge at the silhouette, with no rim. flat: kept as a
                                   thin dark flange round the edge. wrap: follows the shape up its sides (dark bands)
    --sides inner|outline          the edge faces' colour: the nearest pixel that is not black (inner), or the outline's own
    --turn 0|90|180|270            turn the sprite clockwise by that many degrees first, so a sprite drawn lying down
                                   stands tip up (0); a --parts picture is turned the same way
    --upright auto|off|DEG         a sprite drawn tilted (a sword corner to corner) is stood tip up first: auto (the
                                   default) measures the tilt and stands it up when it is long and leans 12 to 78
                                   degrees; DEG turns it that many degrees clockwise; off leaves it. It is turned by
                                   cleanEdge (its own colours) and drawn 1.5x bigger, saved as NAME_upright.png in the
                                   out folder; --parts and --paint pictures are then painted over that picture
    --paint FILE.png               the thickness picture, drawn over the sprite (same size, turned with it): a clear
                                   pixel is as made; black cuts the pixel away; any other grey scales its thickness by
                                   grey/128 (64 half as thick, 128 as made, 255 twice); a pixel painted 120 or more
                                   always stays (even the handle outline that --handle inner leaves off)
    --handle inner|full            a shaft's or grip's width (sharp outline only): inner (the default) its coloured
                                   middle, as wide as the handle looks in the sprite; full: middle and outline together
    --mesh lowpoly|pixels          lowpoly (the default): very few polygons, each part one simple closed shape (a
                                   handle a six-sided prism of about 20 triangles, a blade a diamond section swept
                                   along its outline, a head or guard a bevelled plate with a sharp edge); the colours
                                   come from the texture (the sprite enlarged, laid on from the front and back,
                                   nearest pixel). pixels: a block of model for every pixel (thousands of faces)
    --detail 1|2|3|4|6|8           finer than the sprite (1): every sprite pixel becomes N x N smaller ones. The
                                   outline is enlarged smooth by cleanEdge (slopes and curves, the sprite's own colours,
                                   nothing blended), and the depth comes from an inflation (Poisson) solve, so handles
                                   are round and blades come to a smooth sharp edge instead of steps
    --original FILE.png            the original sprite, shown first on the sheet
    --out DIR                      where the results go (beside the sprite, in NAME_3d)
    --name NAME                    the results' name (the sprite's file name)
    --px N                         screen pixels a sprite pixel on the pictures (8)
    --views N                      how many angles on the sheet, from the front round to the back (7), plus one from above
    --view YAW PITCH FILE.png      one picture more at that angle, degrees, on a clear background (may be repeated)
    --no-obj  --no-sheet           leave that result out
    --json                         every line printed is one JSON record with an "ev" field (for the window)

Results in the out folder: NAME.obj + NAME.mtl + NAME_tex.png (the model, one unit a sprite pixel, y up, the grip
at the bottom), NAME_parts.png (shaped: the parts used), NAME_sheet.png (original, sprite, parts, the model from
every side), and the --view pictures. Every face has one sprite pixel's own colour: no blending, no new colours.
The mesh is checked: closed all round (every edge shared by two faces), front and back alike.
Needs numpy and Pillow."""
import sys, os, json, math
import numpy as np
from PIL import Image, ImageDraw

PARTS = {"blade": (0, 0, 255), "shaft": (0, 255, 0), "grip": (255, 255, 0), "guard": (0, 255, 255),
         "head": (255, 128, 0), "gem": (255, 0, 255)}
NAMES = list(PARTS)
JSON = False


def say(ev_name, plain=None, **kw):
    if JSON: print(json.dumps(dict(ev=ev_name, **kw)), flush=True)
    elif plain is not None: print(plain, flush=True)


# ---------------------------------------------------------------- the parts
def runs(mask_row):
    """the runs of set pixels in a row: (first, past-last)"""
    out, x, w = [], 0, len(mask_row)
    while x < w:
        if mask_row[x]:
            x0 = x
            while x < w and mask_row[x]: x += 1
            out.append((x0, x))
        else: x += 1
    return out


def guess_parts(a, kind="auto"):
    """a first guess of each pixel's part (an index into NAMES, -1 clear) from an upright sprite"""
    h, w = a.shape[:2]
    op = a[..., 3] > 0
    rows = [y for y in range(h) if op[y].any()]
    part = np.full((h, w), -1, int)
    if not rows: return part, kind
    top, bot = rows[0], rows[-1]
    width = np.array([int(op[y].sum()) for y in range(h)])
    span = bot - top + 1
    # the handle: the narrow rows from the bottom up
    narrow = int(np.percentile(width[top:bot + 1], 30)) + 1
    y = bot
    while y >= top and width[y] <= narrow: y -= 1
    handle_top = y + 1                                    # the first row of the bottom's narrow stretch
    widest = top + int(np.argmax(width[top:bot + 1]))
    if kind == "auto":
        kind = "sword" if (widest - top) > span * 0.45 or width[widest] < 8 else "axe"
    r, g, b = a[..., 0].astype(int), a[..., 1].astype(int), a[..., 2].astype(int)
    brown = op & (r > b + 30) & (r > g + 15) & (r < 200)
    if kind == "sword":
        # the guard: the widest row of the lower half and the rows beside it that are wider than the blade
        lower = [yy for yy in range(top + span // 2, bot + 1)]
        gy = max(lower, key=lambda yy: width[yy])
        blade_w = int(np.median(width[top + 2:max(top + 3, gy - 1)])) if gy - top > 4 else width[top]
        g0 = g1 = gy
        while g0 - 1 >= top and width[g0 - 1] > blade_w + 1: g0 -= 1
        while g1 + 1 <= bot and width[g1 + 1] > blade_w + 1: g1 += 1
        for yy in range(top, bot + 1):
            part[yy][op[yy]] = NAMES.index("blade") if yy < g0 else NAMES.index("guard") if yy <= g1 else NAMES.index("grip")
        # the guard's top rows where only the dark outline is wider than the blade (the blade's own colours still run
        # down the middle): the middle stays blade, so the guard's top is not painted steel
        lit = op & (r + g + b >= 60)
        yy = g0
        while yy < g1 and g0 > top:
            bx = np.nonzero(lit[g0 - 1])[0]; lx = np.nonzero(lit[yy])[0]
            if not len(bx) or not len(lx) or lx[0] < bx[0] or lx[-1] > bx[-1]: break
            part[yy, bx[0]:bx[-1] + 1][op[yy, bx[0]:bx[-1] + 1]] = NAMES.index("blade")
            yy += 1
    else:
        # the shaft's columns: the handle's own, continued up through the head
        # the shaft's columns: those of the rows just above the foot. Going up, a row is still shaft while the
        # shaft's own dark outline stands on both sides of it (a blade's tail hanging beside it is head); the first
        # row where the outline is broken is the head, and so is everything above it
        low = op[max(top, bot - 4):bot, :] if bot - top > 5 else op[top:bot + 1, :]
        hx = [x for x in range(w) if low[:, x].any()] or list(range(w))
        x0, x1 = hx[0], hx[-1] + 1
        dark = op & (r + g + b < 60)
        grip_top = bot + 1
        while grip_top - 1 >= top and (brown[grip_top - 1, x0:x1].any() or grip_top - 1 == bot): grip_top -= 1
        if grip_top >= bot: grip_top = bot - max(2, (bot - handle_top) // 3)
        in_head = False
        for yy in range(bot, top - 1, -1):
            if not in_head and yy < bot - 1 and not (dark[yy, x0] and dark[yy, x1 - 1]): in_head = True
            for x in range(w):
                if not op[yy, x]: continue
                if in_head or not (x0 <= x < x1): part[yy, x] = NAMES.index("head")
                else: part[yy, x] = NAMES.index("grip" if yy >= grip_top else "shaft")
    gem = op & (((r > 180) & (g < 120) & (b < 120)) | ((r > 200) & (g > 130) & (b < 70)))
    handle = (part == NAMES.index("shaft")) | (part == NAMES.index("grip"))          # (a red band or gold pommel on a handle is handle)
    part[gem & ~handle] = NAMES.index("gem")
    return part, kind


def trim_handle(a, part, keep):
    """the pixels a shaft's or grip's dark outline takes up, so the handle is as wide as its coloured middle (what the
    eye reads as the handle in the original) and not as wide as middle and outline together. Per row, per shaft or
    grip run: the outline on either side of the coloured span goes; a row with no colour at all (a dark ring) takes
    the span of the nearest coloured row of the handle. keep: pixels painted to stay. A boolean mask, True = remove"""
    h, w = part.shape
    op = a[..., 3] > 0
    lit = op & (a[..., :3].astype(int).sum(-1) >= 60)
    handle = (part == NAMES.index("shaft")) | (part == NAMES.index("grip"))
    out = np.zeros((h, w), bool)
    spans = {}
    for y in range(h):
        for x0, x1 in runs(handle[y]):
            xs = [x for x in range(x0, x1) if lit[y, x]]
            spans[(y, x0, x1)] = (xs[0], xs[-1] + 1) if xs else None
    for (y, x0, x1), s in spans.items():
        if s is None:
            near = sorted(((abs(yy - y), v) for (yy, a0, a1), v in spans.items() if v and a0 < x1 and x0 < a1), key=lambda t: t[0])
            if not near: continue
            s = near[0][1]
            if near[0][0] > 2: continue                     # (a dark run far from any coloured row: left as it is)
        for x in range(x0, x1):
            if not (s[0] <= x < s[1]) and not keep[y, x]: out[y, x] = True
    return out


def read_paint(path, a, turn=0):
    """the thickness picture (the same size as the sprite, painted in grey): a clear pixel is as made; black cuts the
    pixel away; any other grey scales its thickness by grey / 128 (128 as made, 64 half, 255 twice). Returns the
    scale (1 where clear), the pixels cut away, and the pixels painted at all (these stay, whatever trims them)"""
    p = np.asarray(turn_image(Image.open(path).convert("RGBA"), turn))
    if p.shape != a.shape: raise ValueError("the thickness picture is %dx%d, the sprite %dx%d" % (p.shape[1], p.shape[0], a.shape[1], a.shape[0]))
    painted = (p[..., 3] > 0) & (a[..., 3] > 0)
    g = p[..., :3].astype(float).mean(-1)
    scale = np.where(painted, g / 128.0, 1.0)
    cut = painted & (g < 8)
    return scale, cut, painted & (g >= 120)               # (made thinner: not brought back; kept or thicker: brought back)


def turn_image(im, turn):
    """the picture turned clockwise by 0, 90, 180 or 270 degrees (no pixel changed, none lost)"""
    return {0: im, 90: im.transpose(Image.ROTATE_270), 180: im.transpose(Image.ROTATE_180), 270: im.transpose(Image.ROTATE_90)}[turn]


def read_parts(path, a, turn=0):
    p = np.asarray(turn_image(Image.open(path).convert("RGBA"), turn))
    if p.shape != a.shape: raise ValueError("the parts picture is %dx%d, the sprite %dx%d" % (p.shape[1], p.shape[0], a.shape[1], a.shape[0]))
    part = np.full(a.shape[:2], -1, int)
    for y in range(a.shape[0]):
        for x in range(a.shape[1]):
            if a[y, x, 3] == 0:
                if p[y, x, 3]: raise ValueError("pixel %d,%d is clear in the sprite but painted in the parts picture" % (x, y))
                continue
            c = tuple(int(v) for v in p[y, x, :3])
            if p[y, x, 3] == 0 or c not in PARTS.values():
                raise ValueError("pixel %d,%d of the parts picture is %s: not one of %s" % (x, y, c, ", ".join("%s %s" % kv for kv in PARTS.items())))
            part[y, x] = list(PARTS.values()).index(c)
    return part


def parts_image(part):
    h, w = part.shape
    im = np.zeros((h, w, 4), np.uint8)
    for k, n in enumerate(NAMES): im[part == k] = PARTS[n] + (255,)
    return Image.fromarray(im)


# ---------------------------------------------------------------- the depth of each pixel
def _edt1(f):
    """one row of the squared distance transform of a sampled function (Felzenszwalb and Huttenlocher, Theory of
    Computing 2012: the lower envelope of parabolas, linear time)"""
    n = len(f); d = np.empty(n); v = np.zeros(n, int); z = np.empty(n + 1)
    idx = np.nonzero(np.isfinite(f))[0]
    if not len(idx): return np.full(n, np.inf)
    k = 0; v[0] = idx[0]; z[0] = -np.inf; z[1] = np.inf
    for q in idx[1:]:
        while True:
            p = v[k]
            s = ((f[q] + q * q) - (f[p] + p * p)) / (2.0 * q - 2.0 * p)
            if s <= z[k]: k -= 1; continue
            break
        k += 1; v[k] = q; z[k] = s; z[k + 1] = np.inf
    k = 0
    for q in range(n):
        while z[k + 1] < q: k += 1
        d[q] = (q - v[k]) ** 2 + f[v[k]]
    return d


def edt(op):
    """each set pixel's exact distance to the nearest clear pixel's centre (the picture's surround counts as clear)"""
    p = np.pad(op, 1)
    f = np.where(p, np.inf, 0.0)
    f = np.array([_edt1(c) for c in f.T]).T
    f = np.array([_edt1(r) for r in f])
    return np.sqrt(f[1:-1, 1:-1])


def distance_out(op):
    """each set pixel's distance to the nearest clear pixel's edge (pixels; 0.5 for a pixel on the outline)"""
    return np.where(op, edt(op) - 0.5, 0.0)


def inflate(region, open_to=None, iters=600):
    """Baran and Lehtinen's inflation (Notes on inflating curves, MIT 2009): h with the Poisson equation lap h = -4
    inside each region, h = 0 outside the shape. region: an int picture (-1 outside, else a region number).
    open_to: pairs of region numbers whose shared edge is free (no flux, so the shape runs on smoothly across it)
    instead of a wall. Solved by conjugate gradients without building the matrix. sqrt(h/2) is then a circle's half
    height across a strip of any width, and sqrt(h) a half-sphere on a disc"""
    inside = region >= 0
    if not inside.any(): return np.zeros(region.shape)
    R = np.pad(region, 1, constant_values=-1)
    same = []                                           # for each of the 4 neighbours: in the same region (coupled)
    free = []                                           # a neighbour in an open region: neither coupled nor a wall
    for dy, dx in ((-1, 0), (1, 0), (0, -1), (0, 1)):
        nb = R[1 + dy:R.shape[0] - 1 + dy, 1 + dx:R.shape[1] - 1 + dx]
        same.append(inside & (nb == region))
        f = np.zeros(region.shape, bool)
        if open_to:
            for a, b in open_to:
                f |= inside & (((region == a) & (nb == b)) | ((region == b) & (nb == a)))
        free.append(f)
    deg = 4.0 - sum(f.astype(float) for f in free) + 1e-9
    def A(x):
        y = deg * x
        xp = np.pad(x, 1)
        for (dy, dx), s in zip(((-1, 0), (1, 0), (0, -1), (0, 1)), same):
            y -= np.where(s, xp[1 + dy:xp.shape[0] - 1 + dy, 1 + dx:xp.shape[1] - 1 + dx], 0.0)
        return np.where(inside, y, 0.0)
    b = np.where(inside, 4.0, 0.0)
    x = np.zeros(region.shape); r = b - A(x); p = r.copy(); rr = (r * r).sum()
    for _ in range(iters):
        Ap = A(p); al = rr / max((p * Ap).sum(), 1e-30)
        x += al * p; r -= al * Ap; rn = (r * r).sum()
        if rn < 1e-10 * b.size: break
        p = r + (rn / rr) * p; rr = rn
    return np.clip(x, 0, None)


def height_field(a, method, part, T, rim):
    h, w = a.shape[:2]
    op = a[..., 3] > 0
    H = np.zeros((h, w))
    if method == "slab":
        H[op] = T
        return H
    d = distance_out(op)
    if method == "round":
        R = max(d.max(), 0.5)
        H[op] = T * np.sqrt(np.clip(d[op] * (2 * R - d[op]), 0, None)) / R
        return np.where(op, np.maximum(H, rim), 0)
    for y in range(h):
        for k in range(len(NAMES)):
            for x0, x1 in runs(part[y] == k):
                hw = (x1 - x0) / 2.0
                for x in range(x0, x1):
                    off = abs(x + 0.5 - (x0 + hw))
                    n = NAMES[k]
                    if n == "blade": v = T * (1 - off / hw)
                    elif n in ("shaft", "grip"): v = math.sqrt(max(hw * hw - off * off, 0)) * (0.85 if n == "grip" else 1.0)
                    elif n == "guard": v = T * (0.6 if d[y, x] < 1 else 1.0)
                    elif n == "head": v = T * min(1.0, d[y, x] / 2.0)
                    else: v = T + 0.5
                    H[y, x] = max(v, rim)
    return thinner_than_handle(H, part)


BLADE_OF_HANDLE, HEAD_OF_HANDLE, GUARD_OF_HANDLE = 0.6, 0.85, 1.1


def thinner_than_handle(H, part):
    """a blade is always thinner than the handle, as on a real sword: at its thickest a blade is BLADE_OF_HANDLE of the
    handle's thickness, an axe or mace head HEAD_OF_HANDLE (the handle's thickness: its round middle, the 95th
    percentile of the shaft and grip). Nothing changes when there is no handle"""
    if part is None: return H
    hand = ((part == NAMES.index("shaft")) | (part == NAMES.index("grip"))) & (H > 0)
    if not hand.any(): return H
    hp = float(np.percentile(H[hand], 95))
    H = H.copy()
    for n, k in (("blade", BLADE_OF_HANDLE), ("head", HEAD_OF_HANDLE)):
        m = part == NAMES.index(n)
        if m.any() and H[m].max() > k * hp: H[m] *= k * hp / H[m].max()
    m = part == NAMES.index("guard")                    # a guard is as thick as the grip it sits on (up or down), so
    if m.any() and H[m].max() > 0: H[m] *= GUARD_OF_HANDLE * hp / H[m].max()   # it does not vanish behind the grip
    return H


# ---------------------------------------------------------------- finer than the sprite's pixels (--detail N)
def no_outline(a):
    """the sprite with its outer dark outline painted in the colour beside it (the nearest pixel that is not dark), so
    the enlargement smooths the silhouette and not a black ring. Dark pixels further in (details) stay"""
    op = a[..., 3] > 0
    dark = op & (a[..., :3].astype(int).sum(-1) < 60)
    lit = op & ~dark
    edge = dark & (distance_out(op) <= 1.6)
    out = a.copy()
    ly, lx = np.nonzero(lit)
    if not len(ly): return out
    for y, x in zip(*np.nonzero(edge)):
        k = int(np.argmin((ly - y) ** 2 * 1.0 + (lx - x) ** 2 * 1.01))
        out[y, x, :3] = a[ly[k], lx[k], :3]
    return out


def enlarge(a, N, cache_dir=None):
    """the sprite N times larger by cleanEdge (torcado, MIT; cleanedge.py beside this file): slopes and curves
    smoothed, no colour blended, every pixel one of the sprite's own colours. Kept in cache_dir by content"""
    import hashlib
    key = hashlib.sha1(a.tobytes() + bytes(a.shape[:2]) + bytes([N])).hexdigest()[:16]
    cf = os.path.join(cache_dir, "enlarged_%dx_%s.png" % (N, key)) if cache_dir else None
    if cf and os.path.exists(cf): return np.asarray(Image.open(cf).convert("RGBA"))
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from cleanedge import CleanEdge
    ce = CleanEdge(Image.fromarray(a))
    h, w = a.shape[:2]
    out = np.zeros((h * N, w * N, 4), np.uint8)
    for fy in range(h * N):
        for fx in range(w * N):
            c = ce.sample((fx + 0.5) / N, (fy + 0.5) / N)
            if c[3] > 0: out[fy, fx] = [round(k * 255) for k in c]
    if cf: Image.fromarray(out).save(cf)
    return out


def fine_map(src, op_fine, N, fill=-1):
    """a per-sprite-pixel value spread to the fine pixels: each takes its own sprite pixel's, or (a fine pixel the
    smoothing added outside the sprite's pixels) the nearest sprite pixel's that has one"""
    h, w = src.shape
    has = src != fill if src.dtype.kind in "iu" else np.isfinite(src)
    out = np.full(op_fine.shape, fill, src.dtype)
    hy, hx = np.nonzero(has)
    for fy, fx in zip(*np.nonzero(op_fine)):
        y, x = fy // N, fx // N
        if has[y, x]: out[fy, fx] = src[y, x]; continue
        k = int(np.argmin((hy + 0.5 - (fy + 0.5) / N) ** 2 + (hx + 0.5 - (fx + 0.5) / N) ** 2))
        out[fy, fx] = src[hy[k], hx[k]]
    return out


def fine_height(fa, fpart, method, T, N):
    """the half-thickness of every fine pixel (in fine pixels) from the inflation (inflate): shaft and grip round
    (sqrt(h/2), a circle across them), a blade a lens running to a sharp edge, an axe or mace head a plate with a
    rounded bevel, a guard a block, a gem a bead. Parts meet without a wall between them, except a gem"""
    op = fa[..., 3] > 0
    TN = T * N
    H = np.zeros(op.shape)
    if method == "slab": return np.where(op, TN, 0.0)
    if method == "round":
        h = inflate(np.where(op, 0, -1)); hm = max(h.max(), 1e-9)
        return np.where(op, TN * np.sqrt(h / hm), 0.0)
    if method == "turned":                              # every fine row a circle as wide as the row
        for y in range(op.shape[0]):
            for x0, x1 in runs(op[y]):
                hw = (x1 - x0) / 2.0
                for x in range(x0, x1): H[y, x] = math.sqrt(max(hw * hw - (x + 0.5 - x0 - hw) ** 2, 0))
        return H
    ix = {n: k for k, n in enumerate(NAMES)}
    region = np.where(op, fpart, -1)
    opn = [(ix[a], ix[b]) for a, b in (("shaft", "grip"), ("shaft", "head"), ("grip", "head"), ("blade", "guard"),
                                       ("guard", "grip"), ("shaft", "guard"), ("blade", "head"), ("guard", "head"))]
    h = inflate(region, opn)
    for n, k in ix.items():
        m = region == k
        if not m.any(): continue
        hk = h[m]
        if n in ("shaft", "grip"): v = np.sqrt(hk / 2.0)
        elif n == "blade": v = TN * (hk / max(hk.max(), 1e-9)) ** 0.8
        elif n == "head": v = TN * (hk / max(hk.max(), 1e-9)) ** 0.6          # (a lens: thickest at the haft, thin at the cutting edge)
        elif n == "guard": v = np.minimum(TN * 1.1, np.sqrt(hk / 2.0) * 1.8)          # (a bar standing out a little past the blade)
        else: v = TN + np.sqrt(hk / 2.0) * 0.8
        H[m] = v
    return thinner_than_handle(H, region)


# ---------------------------------------------------------------- the mesh
def build_mesh(a, H, rim, sides="inner", outline="sharp"):
    """triangles (n, 3, 3) with x right, y up (0 the sprite's foot), z toward the viewer; the sprite pixel each takes
    its colour from (n, 2); unit one sprite pixel. sides: the colour of the faces round the edge: "outline" the edge
    pixel's own (black, when the sprite has a black outline), "inner" the nearest pixel that is not black (so the
    model seen edge-on is steel and wood, not a black bar)"""
    h, w = a.shape[:2]
    op = a[..., 3] > 0
    side_of = {}
    if sides == "inner" or outline == "sharp":
        lit = op & (a[..., :3].astype(int).sum(-1) >= 60)
        ly, lx = np.nonzero(lit)
        if len(ly):
            for y in range(h):
                for x in range(w):
                    if op[y, x] and not lit[y, x]:
                        k = int(np.argmin((ly - y) ** 2 * 1.0 + (lx - x) ** 2 * 1.01))      # (a tie: the same row first)
                        side_of[(x, y)] = (int(lx[k]), int(ly[k]))
    P = np.pad(op, 1)
    Hp = np.pad(H, 1)
    C = np.zeros((h + 1, w + 1))                           # the corners' half-thickness
    Dk = np.pad(op & (a[..., :3].astype(int).sum(-1) < 60), 1)
    # outline "sharp": the sprite's dark outline (dark pixels within two of the edge) is not drawn as black at all: it
    # takes the colour beside it, and the shape runs down to nothing at the silhouette (a sharp edge, no rim)
    Edge = (Dk[1:-1, 1:-1] & (distance_out(op) <= 1.6)) if outline == "sharp" else np.zeros((h, w), bool)
    for cy in range(h + 1):
        for cx in range(w + 1):
            m = P[cy:cy + 2, cx:cx + 2]
            if not m.any(): continue
            mean = Hp[cy:cy + 2, cx:cx + 2][m].mean()
            C[cy, cx] = mean if m.all() else min(mean, rim)
            # outline "flat": a corner that touches an outline (dark) pixel stays at the rim's height, so the outline is
            # a thin flat flange round the model (a dark seam seen from the side) and never wraps up the sides
            if outline == "flat" and Dk[cy:cy + 2, cx:cx + 2].any(): C[cy, cx] = min(C[cy, cx], rim)
    if outline == "sharp":
        # a part one pixel wide (a spike's tip, a thin prong) would have every corner on the silhouette and so no
        # thickness at all: its corners keep a little, so it stays solid (a small blunt end, not a sheet of paper)
        thin = [(y, x) for y in range(h) for x in range(w) if op[y, x] and not C[y:y + 2, x:x + 2].any()]
        for y, x in thin: C[y:y + 2, x:x + 2] = np.maximum(C[y:y + 2, x:x + 2], 0.3)
    tris, pix = [], []
    X = lambda cx: cx - w / 2.0
    Y = lambda cy: float(h - cy)
    def add(p, q, r, px, py): tris.append((p, q, r)); pix.append((px, py))
    for y in range(h):
        for x in range(w):
            if not op[y, x]: continue
            c = [(y, x), (y, x + 1), (y + 1, x + 1), (y + 1, x)]            # round the pixel, clockwise on screen
            fx, fy = (side_of.get((x, y), (x, y)) if outline == "sharp" and Edge[y, x] else (x, y))
            for s in (1, -1):                                               # front, back
                v = [(X(cx), Y(cy), s * C[cy, cx]) for cy, cx in c]
                order = (0, 3, 2, 0, 2, 1) if abs(C[c[0]] - C[c[2]]) <= abs(C[c[1]] - C[c[3]]) else (0, 3, 1, 3, 2, 1)
                for k in (0, 3):
                    t = [v[order[k]], v[order[k + 1]], v[order[k + 2]]]
                    if s < 0: t.reverse()
                    add(t[0], t[1], t[2], fx, fy)
            for (dy, dx), (e0, e1) in (((-1, 0), (0, 1)), ((0, 1), (1, 2)), ((1, 0), (2, 3)), ((0, -1), (3, 0))):
                if P[y + 1 + dy, x + 1 + dx]: continue                       # a neighbour there: no rim on that side
                (ay, ax), (by, bx) = c[e0], c[e1]
                if C[ay, ax] == 0 and C[by, bx] == 0: continue
                fa, fb = (X(ax), Y(ay), C[ay, ax]), (X(bx), Y(by), C[by, bx])
                ba, bb = (X(ax), Y(ay), -C[ay, ax]), (X(bx), Y(by), -C[by, bx])
                sx_, sy_ = side_of.get((x, y), (x, y))
                add(fa, fb, bb, sx_, sy_); add(fa, bb, ba, sx_, sy_)
    return np.array(tris, float), np.array(pix, int)


def check_mesh(tris, opaque):
    """what is wrong with the mesh (an empty list: sound), and how many edges are pinched (two pixels meeting corner
    to corner: four faces on one edge)"""
    bad = []
    if not np.isfinite(tris).all(): bad.append("a vertex is not a number")
    edges = {}
    for t in np.round(tris, 3):
        for i in range(3):
            p, q = tuple(t[i]), tuple(t[(i + 1) % 3])
            if p == q: continue
            k = (p, q) if p < q else (q, p)
            edges[k] = edges.get(k, 0) + 1
    odd = sum(1 for n in edges.values() if n not in (2, 4))
    pinch = sum(1 for n in edges.values() if n == 4)
    if odd: bad.append("%d edges are not shared by two faces (the mesh is open)" % odd)
    front = {tuple(v) for v in np.round(tris.reshape(-1, 3), 3)}
    if front != {(x, y, -z if z else 0.0) for x, y, z in front} and front != {(x, y, -z) for x, y, z in front}:
        bad.append("front and back differ")
    if len(tris) < 4 * opaque: bad.append("%d faces for %d pixels: too few" % (len(tris), opaque))
    vol = float(np.einsum("ij,ij->i", tris[:, 0], np.cross(tris[:, 1], tris[:, 2])).sum()) / 6.0 if len(tris) else 0.0
    if vol <= 0: bad.append("the faces point inward (enclosed volume %.2f)" % vol)
    return bad, pinch


def write_obj(folder, name, tris, pix, sprite):
    h, w = np.asarray(sprite).shape[:2]
    vs, vt, lines = {}, {}, []
    for t, (px, py) in zip(np.round(tris, 4), pix):
        uv = (round((px + 0.5) / w, 6), round(1 - (py + 0.5) / h, 6))
        ti = vt.setdefault(uv, len(vt) + 1)
        lines.append("f " + " ".join("%d/%d" % (vs.setdefault(tuple(p), len(vs) + 1), ti) for p in t))
    with open(os.path.join(folder, name + ".obj"), "w") as f:
        f.write("# made by sprite3d.py from %s; one unit a sprite pixel, y up\nmtllib %s.mtl\nusemtl sprite\n" % (name, name))
        f.write("".join("v %g %g %g\n" % p for p in vs) + "".join("vt %g %g\n" % u for u in vt) + "\n".join(lines) + "\n")
    with open(os.path.join(folder, name + ".mtl"), "w") as f:
        f.write("newmtl sprite\nKd 1 1 1\nKa 0 0 0\nd 1\nillum 1\nmap_Kd %s_tex.png\n" % name)
    sprite.save(os.path.join(folder, name + "_tex.png"))
    return len(vs)


# ---------------------------------------------------------------- pictures of the model
def render(tris, pix, a, yaw, pitch, px, size):
    """the model seen from yaw (0 the front, 90 edge-on) and pitch (above), degrees: an RGBA picture, clear ground"""
    cy, sy, cp, sp = math.cos(math.radians(yaw)), math.sin(math.radians(yaw)), math.cos(math.radians(pitch)), math.sin(math.radians(pitch))
    Ry = np.array([[cy, 0, sy], [0, 1, 0], [-sy, 0, cy]])
    Rx = np.array([[1, 0, 0], [0, cp, -sp], [0, sp, cp]])
    R = Rx @ Ry
    lo, hi = tris.reshape(-1, 3).min(0), tris.reshape(-1, 3).max(0)
    v = (tris - (lo + hi) / 2) @ R.T
    n = np.cross(v[:, 1] - v[:, 0], v[:, 2] - v[:, 0])
    ln = np.linalg.norm(n, axis=1); ln[ln == 0] = 1
    n /= ln[:, None]
    L = np.array([-0.45, 0.55, 0.70]); L /= np.linalg.norm(L)
    shade = 0.50 + 0.50 * np.clip(n @ L, 0, 1)
    out = np.zeros((size, size, 4), np.uint8)
    zb = np.full((size, size), -1e9)
    sx = v[..., 0] * px + size / 2.0
    syy = -v[..., 1] * px + size / 2.0
    for i in range(len(v)):
        if n[i, 2] <= 0: continue                           # turned away (the mesh is closed)
        x0, x1 = max(int(math.floor(sx[i].min())), 0), min(int(math.ceil(sx[i].max())), size - 1)
        y0, y1 = max(int(math.floor(syy[i].min())), 0), min(int(math.ceil(syy[i].max())), size - 1)
        if x1 < x0 or y1 < y0: continue
        gx, gy = np.meshgrid(np.arange(x0, x1 + 1) + 0.5, np.arange(y0, y1 + 1) + 0.5)
        ax, ay, bx, by, cx, cyy = sx[i, 0], syy[i, 0], sx[i, 1], syy[i, 1], sx[i, 2], syy[i, 2]
        den = (by - cyy) * (ax - cx) + (cx - bx) * (ay - cyy)
        if abs(den) < 1e-9: continue
        w0 = ((by - cyy) * (gx - cx) + (cx - bx) * (gy - cyy)) / den
        w1 = ((cyy - ay) * (gx - cx) + (ax - cx) * (gy - cyy)) / den
        w2 = 1 - w0 - w1
        z = w0 * v[i, 0, 2] + w1 * v[i, 1, 2] + w2 * v[i, 2, 2]
        sub = zb[y0:y1 + 1, x0:x1 + 1]
        m = (w0 >= -1e-6) & (w1 >= -1e-6) & (w2 >= -1e-6) & (z > sub)
        if not m.any(): continue
        sub[m] = z[m]
        col = a[pix[i, 1], pix[i, 0], :3].astype(float) * shade[i]
        out[y0:y1 + 1, x0:x1 + 1][m] = (int(col[0] + 0.5), int(col[1] + 0.5), int(col[2] + 0.5), 255)
    return Image.fromarray(out)


def render_uv(tris, uvs, tex, yaw, pitch, px, size):
    """the model seen from yaw / pitch with its texture (nearest pixel), for a model whose faces carry texture
    coordinates (the low-poly kind): every screen pixel takes the texture pixel under it"""
    cy, sy, cp, sp = math.cos(math.radians(yaw)), math.sin(math.radians(yaw)), math.cos(math.radians(pitch)), math.sin(math.radians(pitch))
    R = np.array([[1, 0, 0], [0, cp, -sp], [0, sp, cp]]) @ np.array([[cy, 0, sy], [0, 1, 0], [-sy, 0, cy]])
    lo, hi = tris.reshape(-1, 3).min(0), tris.reshape(-1, 3).max(0)
    v = (tris - (lo + hi) / 2) @ R.T
    n = np.cross(v[:, 1] - v[:, 0], v[:, 2] - v[:, 0]); ln = np.linalg.norm(n, axis=1); ln[ln == 0] = 1; n /= ln[:, None]
    L = np.array([-0.45, 0.55, 0.70]); L /= np.linalg.norm(L)
    shade = 0.50 + 0.50 * np.clip(n @ L, 0, 1)
    th, tw = tex.shape[:2]
    out = np.zeros((size, size, 4), np.uint8); zb = np.full((size, size), -1e9)
    sx = v[..., 0] * px + size / 2.0; syy = -v[..., 1] * px + size / 2.0
    for i in range(len(v)):
        if n[i, 2] <= 0: continue
        x0, x1 = max(int(math.floor(sx[i].min())), 0), min(int(math.ceil(sx[i].max())), size - 1)
        y0, y1 = max(int(math.floor(syy[i].min())), 0), min(int(math.ceil(syy[i].max())), size - 1)
        if x1 < x0 or y1 < y0: continue
        gx, gy = np.meshgrid(np.arange(x0, x1 + 1) + 0.5, np.arange(y0, y1 + 1) + 0.5)
        ax, ay, bx, by, cx, cyy = sx[i, 0], syy[i, 0], sx[i, 1], syy[i, 1], sx[i, 2], syy[i, 2]
        den = (by - cyy) * (ax - cx) + (cx - bx) * (ay - cyy)
        if abs(den) < 1e-9: continue
        w0 = ((by - cyy) * (gx - cx) + (cx - bx) * (gy - cyy)) / den
        w1 = ((cyy - ay) * (gx - cx) + (ax - cx) * (gy - cyy)) / den
        w2 = 1 - w0 - w1
        z = w0 * v[i, 0, 2] + w1 * v[i, 1, 2] + w2 * v[i, 2, 2]
        sub = zb[y0:y1 + 1, x0:x1 + 1]
        m = (w0 >= -1e-6) & (w1 >= -1e-6) & (w2 >= -1e-6) & (z > sub)
        if not m.any(): continue
        sub[m] = z[m]
        u = w0 * uvs[i, 0, 0] + w1 * uvs[i, 1, 0] + w2 * uvs[i, 2, 0]
        t = w0 * uvs[i, 0, 1] + w1 * uvs[i, 1, 1] + w2 * uvs[i, 2, 1]
        X = np.clip((u * tw).astype(int), 0, tw - 1); Y = np.clip(((1 - t) * th).astype(int), 0, th - 1)
        col = tex[Y[m], X[m], :3].astype(float) * shade[i]
        o = out[y0:y1 + 1, x0:x1 + 1]
        o[m, :3] = (col + 0.5).astype(np.uint8); o[m, 3] = 255
    return Image.fromarray(out)


def write_obj_uv(folder, name, tris, uvs, tex):
    """an .obj whose faces carry their own texture coordinates (the low-poly kind)"""
    vs, vt, lines = {}, {}, []
    for t, uv in zip(np.round(tris, 4), np.round(uvs, 6)):
        lines.append("f " + " ".join("%d/%d" % (vs.setdefault(tuple(p), len(vs) + 1), vt.setdefault(tuple(q), len(vt) + 1)) for p, q in zip(t, uv)))
    with open(os.path.join(folder, name + ".obj"), "w") as f:
        f.write("# made by sprite3d.py from %s (low poly); one unit a sprite pixel, y up; texture: nearest pixel\nmtllib %s.mtl\nusemtl sprite\n" % (name, name))
        f.write("".join("v %g %g %g\n" % p for p in vs) + "".join("vt %g %g\n" % u for u in vt) + "\n".join(lines) + "\n")
    with open(os.path.join(folder, name + ".mtl"), "w") as f:
        f.write("newmtl sprite\nKd 1 1 1\nKa 0 0 0\nd 1\nillum 1\nmap_Kd %s_tex.png\n" % name)
    Image.fromarray(tex).save(os.path.join(folder, name + "_tex.png"))
    return len(vs)


def sheet(path, cells, cell):
    """cells: (label, picture); one row, magenta ground, labels white on navy"""
    pad = 10
    im = Image.new("RGBA", (len(cells) * (cell + pad) + pad, cell + 24 + 2 * pad), (255, 0, 255, 255))
    d = ImageDraw.Draw(im)
    for k, (label, pic) in enumerate(cells):
        x = pad + k * (cell + pad)
        d.rectangle((x, pad, x + cell, pad + 20), fill=(0, 0, 60, 255)); d.text((x + 5, pad + 4), label, fill=(255, 255, 255, 255))
        if pic is not None: im.paste(pic, (x + (cell - pic.width) // 2, pad + 24 + (cell - pic.height) // 2), pic)
    im.save(path)


# ---------------------------------------------------------------- the command line
def main(argv):
    global JSON
    a = list(argv)
    def opt(name, d, n=1):
        if name in a:
            i = a.index(name); v = a[i + 1:i + 1 + n]; del a[i:i + 1 + n]
            return v[0] if n == 1 else v
        return d
    def flag(name):
        if name in a: a.remove(name); return True
        return False
    JSON = flag("--json")
    method, kind = opt("--method", "shaped"), opt("--kind", "auto")
    T, px, nviews = float(opt("--thickness", "1.5")), int(opt("--px", "8")), int(opt("--views", "7"))
    rim, sides, outline = float(opt("--rim", "0.4")), opt("--sides", "inner"), opt("--outline", "sharp")
    parts_file, original, out, name = opt("--parts", ""), opt("--original", ""), opt("--out", ""), opt("--name", "")
    no_obj, no_sheet = flag("--no-obj"), flag("--no-sheet")
    paint_file, handle_w = opt("--paint", ""), opt("--handle", "inner")
    mesh_kind = opt("--mesh", "lowpoly")
    try: detail = int(opt("--detail", "1"))
    except ValueError: detail = 0
    upright_opt = opt("--upright", "auto")
    try: upright_deg = None if upright_opt == "auto" else 0.0 if upright_opt == "off" else float(upright_opt)
    except ValueError: upright_opt = "bad"
    try: turn = int(opt("--turn", "0")) % 360
    except ValueError: turn = -1
    views = []
    while "--view" in a: views.append(opt("--view", None, 3))
    if len(a) != 1 or a[0].startswith("--") or method not in ("slab", "round", "shaped", "turned") or kind not in ("auto", "sword", "axe", "mace", "object") or turn not in (0, 90, 180, 270) or handle_w not in ("inner", "full") or detail not in (1, 2, 3, 4, 6, 8) or mesh_kind not in ("lowpoly", "pixels") or upright_opt == "bad":
        say("error", __doc__, text="usage: sprite3d.py SPRITE.png [--method slab|round|turned|shaped] [--parts FILE] [--kind auto|sword|axe|mace] [--turn 0|90|180|270] ...")
        return 2
    src = a[0]
    if mesh_kind == "lowpoly" and outline != "sharp":
        say("note", "low poly: the outline is built sharp (seam and wrapped are for --mesh pixels)")
        outline = "sharp"
    try:
        sprite = Image.open(src).convert("RGBA")
        if not (np.asarray(sprite)[..., 3] > 0).any(): raise ValueError("the sprite has no pixels (all clear)")
        name = name or os.path.splitext(os.path.basename(src))[0]
        out = out or os.path.join(os.path.dirname(os.path.abspath(src)), name + "_3d")
        os.makedirs(out, exist_ok=True)
        # a tilted sprite stood up first (upright.py), then turned
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); import upright as UP
        sprite, stood = UP.stand_up(sprite, upright_deg)
        if stood:
            ufile = os.path.join(out, name + "_upright.png"); sprite.save(ufile)
            say("upright", "stood up: turned %.1f degrees clockwise, now %dx%d (%s)" % (stood, sprite.width, sprite.height, ufile),
                img=ufile, angle=round(stood, 1))
        sprite = turn_image(sprite, turn)
        arr = np.asarray(sprite)
        if method == "slab": rim = T
        elif outline == "sharp": rim = 0.0
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); import regions as RG
        # the parts: each pixel's part, each part's label, shape and settings (regions.py)
        if method == "shaped":
            if parts_file: region, specs = RG.read(parts_file, arr, turn_image, turn); what = "from the parts picture"
            else: region, specs, what = RG.guess(arr, kind, guess_parts, NAMES); what = "guessed as " + what
        else:
            region, specs = RG.whole(arr, {"slab": "box", "round": "dome", "turned": "lathe"}[method]); what = "all one " + method
        pfile = os.path.join(out, name + "_parts.png"); RG.write(pfile, region, specs)
        say("parts", "parts: %s (%s)" % (", ".join("%s %s %d" % (sp["label"], sp["shape"], int((region == k).sum())) for k, sp in enumerate(specs)), what),
            img=pfile, guessed=not parts_file, kind=what, n=len(specs))
        part = RG.to_old(region, specs, NAMES)              # (the old part numbers, for the many-faces mesher)
        # what is drawn on the sprite: the thickness picture (cut away, thinner, thicker), and the handle's outline
        scale, cut, keep = (read_paint(paint_file, arr, turn) if paint_file else
                            (np.ones(arr.shape[:2]), np.zeros(arr.shape[:2], bool), np.zeros(arr.shape[:2], bool)))
        # the handle outline trim goes by the parts labelled handle or grip and built round
        handle_like = np.isin(region, [k for k, sp in enumerate(specs) if sp["label"] in ("handle", "grip") and sp["shape"] in ("roundbar", "lathe")])
        part_h = np.where(handle_like, NAMES.index("shaft"), np.where(region >= 0, NAMES.index("head"), -1))
        gone = cut.copy()
        if part_h is not None and outline == "sharp" and handle_w == "inner": gone |= trim_handle(arr, part_h, keep)
        if gone.any():
            arr = arr.copy(); arr[gone, 3] = 0
            part = np.where(gone, -1, part); part_h = np.where(gone, -1, part_h); region = np.where(gone, -1, region)
            if not (arr[..., 3] > 0).any(): raise ValueError("everything is cut away")
        if paint_file or gone.any():
            gm = np.zeros(arr.shape[:2] + (4,), np.uint8); gm[gone & ~cut] = (0, 0, 60, 170)
            gfile = os.path.join(out, name + "_left_off.png"); Image.fromarray(gm).save(gfile)          # (the window shows it over the sprite)
            say("paint", "drawn: %d pixels cut away (%d of them the handle's outline), %d thinner, %d thicker"
                % (int(gone.sum()), int((gone & ~cut).sum()), int(((scale < 0.98) & ~gone).sum()), int(((scale > 1.02) & ~gone).sum())),
                img=gfile, cut=int(cut.sum()), trimmed=int((gone & ~cut).sum()), thinner=int(((scale < 0.98) & ~gone).sum()), thicker=int(((scale > 1.02) & ~gone).sum()))
        tex_arr, tex_img = arr, sprite                    # the picture the faces take their colours from
        uvs = None
        if mesh_kind == "lowpoly":
            # few polygons: each part one simple closed shape, the colours from the texture laid over it
            sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); import lowpoly
            N = detail if detail > 1 else 4
            base = no_outline(arr) if outline == "sharp" else arr
            fa = enlarge(base, N, out)
            op_f = fa[..., 3] > 0
            fregion = fine_map(region, op_f, N)
            fscale = fine_map(np.where(arr[..., 3] > 0, scale, np.nan), op_f, N, np.nan)
            tris, uvs, notes = lowpoly.build_regions(fa, fregion, specs, N, T, fscale, BLADE_OF_HANDLE, HEAD_OF_HANDLE)
            tex_arr = lowpoly.bleed(fa); tex_img = Image.fromarray(tex_arr)
            say("lowpoly", "low poly: %d triangles (%s)" % (len(tris), ", ".join("%s %s" % kv for kv in notes.items())), triangles=len(tris), parts=notes)
        elif detail > 1:
            # finer than the sprite: every sprite pixel N x N fine ones. The outline is painted over (sharp), the
            # sprite enlarged by cleanEdge (smooth slopes, its own colours), the depth from the inflation
            N = detail
            base = no_outline(arr) if outline == "sharp" else arr
            fa = enlarge(base, N, out)
            op_f = fa[..., 3] > 0
            fpart = fine_map(part, op_f, N)
            fscale = fine_map(np.where(arr[..., 3] > 0, scale, np.nan), op_f, N, np.nan)
            Hf = fine_height(fa, fpart, method, T, N) * np.where(op_f, fscale, 0.0)
            tris, pix = build_mesh(fa, Hf, T * N if method == "slab" else 0.0, sides, outline)
            tris = tris / N
            tex_arr, tex_img = fa, Image.fromarray(fa)
            say("detail", "detail: %dx, %d fine pixels" % (N, int(op_f.sum())), n=N, pixels=int(op_f.sum()))
        else:
            if method == "turned":                         # every row a circle round its own middle: a shape off a lathe
                H = height_field(arr, "shaped", part, T, rim)
            else: H = height_field(arr, method, part, T, rim)
            H = H * scale
            tris, pix = build_mesh(arr, H, rim, sides, outline)
        size = int(max(arr.shape[0], arr.shape[1]) * px * 1.25) // 2 * 2
        opaque = int((tex_arr[..., 3] > 0).sum()) if uvs is None else 0
        bad, pinch = check_mesh(tris, opaque)
        if uvs is not None: bad = [b for b in bad if b != "front and back differ"]          # (a part moved forward is meant)
        draw = (lambda yw, pt: render(tris, pix, tex_arr, yw, pt, px, size)) if uvs is None else (lambda yw, pt: render_uv(tris, uvs, tex_arr, yw, pt, px, size))
        lo, hi = tris.reshape(-1, 3).min(0), tris.reshape(-1, 3).max(0)
        say("mesh", "mesh: %d faces from %d pixels, %.1f wide x %.1f tall x %.1f thick; %s%s"
            % (len(tris), opaque, hi[0] - lo[0], hi[1] - lo[1], hi[2] - lo[2], "sound" if not bad else "PROBLEMS: " + "; ".join(bad),
               ", %d pinched edges" % pinch if pinch else ""),
            faces=len(tris), pixels=opaque, wide=round(float(hi[0] - lo[0]), 2), tall=round(float(hi[1] - lo[1]), 2), thick=round(float(hi[2] - lo[2]), 2),
            nproblems=len(bad), problem=bad[0] if bad else "", pinched=pinch, method=method)
        if not no_obj:
            nv = write_obj(out, name, tris, pix, tex_img) if uvs is None else write_obj_uv(out, name, tris, uvs, tex_arr)
            say("obj", "model: %s (%d points)" % (os.path.join(out, name + ".obj"), nv), file=os.path.join(out, name + ".obj"), points=nv)
        for yaw, pitch, f in views:
            draw(float(yaw), float(pitch)).save(f)
            say("view", "view: %s" % f, img=os.path.abspath(f), yaw=float(yaw), pitch=float(pitch))
        if not no_sheet:
            big = lambda im, k=px: im.resize((im.width * k, im.height * k), Image.NEAREST)
            cells = []
            if original:
                o = Image.open(original).convert("RGBA")
                cells.append(("original", big(o, max(1, size // max(o.size)))))
            cells.append(("sprite", big(sprite)))
            if part is not None: cells.append(("parts", big(parts_image(part))))
            for k in range(nviews):
                yaw = 180.0 * k / max(nviews - 1, 1)
                cells.append(("%s, turned %d" % (method, yaw), draw(yaw, 0)))
            cells.append(("from above", draw(20, 60)))
            sf = os.path.join(out, name + "_sheet.png"); sheet(sf, cells, size)
            say("sheet", "sheet: %s" % sf, img=sf)
        say("done", "done" if not bad else "done, with problems", ok=not bad, out=out)
        return 0 if not bad else 1
    except Exception as e:
        say("error", "error: %s" % e, text="%s: %s" % (type(e).__name__, e))
        return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
