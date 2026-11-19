r"""regions.py: a sprite split into labelled parts, each with a shape and its own settings (transforms).

The parts are kept in two files beside each other:
    NAME_parts.png   the sprite's size; every pixel painted in its part's colour (clear where the sprite is clear)
    NAME_parts.txt   one line a part, each line one JSON object:
                     {"colour": [r, g, b], "label": "blade", "shape": "blade", "depth": 1.0, "offset": 0.0,
                      "taper": "none", "taper_amount": 0.0, "bevel": 1.5, "sides": 6}

label   what the part is (a name only, and what the defaults and the "thinner than the handle" rule go by)
shape   how the part is built (SHAPES below)
depth   its thickness, times the shape's own (1 = as the shape makes it)
offset  moved toward the viewer (+) or away (-), sprite pixels
taper   which way it thins ("none", "up", "down", "left", "right"), and how much (0 none .. 1 down to nothing)
bevel   the sloping rim of a plate or dome, sprite pixels
sides   the sides round a round bar, lathe or ball

A parts picture in the six old part colours with no .txt beside it is still read (as the six old parts)."""
import json, os
import numpy as np
from PIL import Image

SHAPES = {          # name: (what it is, for the help)
    "roundbar": "a straight round bar (a prism of `sides` sides): handles, shafts, poles, legs",
    "lathe":    "every row a circle as wide as the row, as if turned on a lathe: bottles, candles, goblets, wands",
    "ball":     "a ball or egg (a lathe that follows the outline closely): pommels, orbs, fruit, heads",
    "blade":    "a diamond cross-section (edge, ridge, edge, ridge) swept along the outline: blades, spear heads",
    "plate":    "a plate with a sharp edge and a bevel up to a flat face: axe heads, shields, books, armour, coins",
    "box":      "a flat slab with straight sides: guards, planks, bricks, chests seen face on",
    "dome":     "a rounded cushion: the outline at the edge, rising in rings to a top: gems, buttons, bread, rocks",
    "card":     "a flat card, hardly any thickness: paper, maps, scrolls, cloth, stains",
}
LABELS = {          # label: its default shape and settings
    "blade":  dict(shape="blade"),
    "handle": dict(shape="roundbar"),
    "grip":   dict(shape="roundbar"),
    "guard":  dict(shape="plate", bevel=0.6),
    "head":   dict(shape="plate", bevel=1.5),
    "gem":    dict(shape="dome", depth=0.8, offset=0.0),
    "pommel": dict(shape="ball"),
    "body":   dict(shape="plate", bevel=1.0),
    "lid":    dict(shape="plate", bevel=0.6),
    "neck":   dict(shape="lathe"),
    "base":   dict(shape="lathe"),
    "rim":    dict(shape="plate", bevel=0.4),
    "strap":  dict(shape="card"),
    "other":  dict(shape="plate", bevel=1.0),
}
TAPERS = ("none", "up", "down", "left", "right")
DEFAULT = dict(depth=1.0, offset=0.0, taper="none", taper_amount=0.0, bevel=1.0, sides=6)
PALETTE = [(0, 0, 255), (0, 255, 0), (255, 255, 0), (0, 255, 255), (255, 128, 0), (255, 0, 255), (128, 64, 255), (0, 160, 80),
           (255, 200, 128), (128, 255, 200), (64, 128, 255), (200, 255, 0), (0, 128, 160), (255, 160, 255), (160, 96, 0), (96, 255, 96)]
OLD = {"blade": (0, 0, 255), "shaft": (0, 255, 0), "grip": (255, 255, 0), "guard": (0, 255, 255), "head": (255, 128, 0), "gem": (255, 0, 255)}


def spec(label, colour, **kw):
    """a part's full settings: the defaults, then the label's, then what is given"""
    s = dict(DEFAULT); s.update(LABELS.get(label, LABELS["other"])); s.update(kw)
    s["label"], s["colour"] = label, list(colour)
    if s["shape"] in ("lathe", "ball") and "sides" not in kw: s["sides"] = 8
    return s


def from_old_parts(part, names):
    """regions from the old part numbers (an index into names a pixel, -1 clear)"""
    specs, region = [], np.full(part.shape, -1, int)
    for k, n in enumerate(names):
        if not (part == k).any(): continue
        label = "handle" if n == "shaft" else n
        region[part == k] = len(specs); specs.append(spec(label, OLD[n]))
    return region, specs


def symmetric(op):
    ys, xs = np.nonzero(op)
    if not len(xs): return 0.0
    m = op[ys.min():ys.max() + 1, xs.min():xs.max() + 1]
    return float((m & m[:, ::-1]).sum()) / max(float((m | m[:, ::-1]).sum()), 1.0)


def guess(a, kind, guess_parts, names):
    """a first split of any sprite. A weapon (or kind sword / axe / mace): the weapon guess (blade, handle, grip,
    guard, head, gem). Anything else, by its outline: tall and mirror-symmetric = one lathe part (bottles, candles);
    round and full = a dome; otherwise a plate. Returns (region, specs, what it was taken for)"""
    op = a[..., 3] > 0
    ys, xs = np.nonzero(op)
    h, w = ys.max() - ys.min() + 1, xs.max() - xs.min() + 1
    if kind == "auto":
        width = op.sum(1)[ys.min():ys.max() + 1]
        narrow = width <= max(2, int(np.percentile(width, 30)) + 1)
        k = len(width) - 1
        while k >= 0 and narrow[k]: k -= 1
        stretch = len(width) - 1 - k                                  # the narrow rows at the foot: a handle
        weapon = h >= 1.6 * w and stretch >= 0.22 * h and width[k + 1:].max(initial=0) <= 0.5 * width.max()
        kind = "weapon" if weapon else "object"
    if kind in ("weapon", "sword", "axe", "mace"):
        part, kk = guess_parts(a, "auto" if kind == "weapon" else ("axe" if kind == "mace" else kind))
        region, specs = from_old_parts(part, names)
        if kk == "sword": pommel(a, region, specs)
        return region, specs, kk
    sym = symmetric(op); fill = op.sum() / float(h * w); aspect = h / float(w)
    if sym >= 0.85 and aspect >= 1.15: label, shp, what = "body", "lathe", "turned object"
    elif 0.68 <= fill <= 0.88 and 0.7 <= aspect <= 1.4 and sym >= 0.75: label, shp, what = "body", "dome", "round object"
    elif fill > 0.88: label, shp, what = "body", "plate", "square object"          # (a circle fills 79 %, a square all)
    else: label, shp, what = "body", "plate", "flat object"
    region = np.where(op, 0, -1)
    return region, [spec(label, PALETTE[0], shape=shp)], what


def pommel(a, region, specs):
    """a sword's pommel: the rows at the foot of the grip that are another colour than the grip (a gold or steel cap) or
    plainly wider than it. They become a part of their own (a ball, built as a disc); at most the grip's lower 40 %"""
    gk = next((k for k, s in enumerate(specs) if s["label"] == "grip"), None)
    if gk is None or any(s["label"] == "pommel" for s in specs): return
    g = region == gk
    rows = [y for y in range(g.shape[0]) if g[y].any()]
    if len(rows) < 4: return
    lit = g & (a[..., :3].astype(int).sum(-1) >= 60)
    upper = np.isin(np.arange(g.shape[0]), rows[:max(2, len(rows) // 2)])[:, None]      # (the grip proper: its upper half)
    if not (lit & upper).any(): return
    main = np.median(a[lit & upper][:, :3].astype(float), 0)
    wmed = float(np.median([g[y].sum() for y in rows[:max(2, len(rows) // 2)]]))
    take, pending = [], []
    for y in rows[::-1][:max(1, int(len(rows) * 0.6))]:
        l = lit[y]
        if not l.any(): pending.append(y); continue                    # (an outline row: goes with what is above it)
        other = np.abs(a[y][l][:, :3].astype(float) - main).sum(1).mean() > 90
        if not (other or g[y].sum() >= wmed + 2): break
        take += pending + [y]; pending = []
    if not take or len(take) >= len(rows) - 1: return
    used = {tuple(s["colour"]) for s in specs}
    col = next(c for c in PALETTE[6:] + PALETTE if c not in used)
    m = g & np.isin(np.arange(g.shape[0]), take)[:, None]
    region[m] = len(specs); specs.append(spec("pommel", col))


def whole(a, shape):
    """the whole sprite one part of the given shape (the window's Flat / Round / Turned)"""
    return np.where(a[..., 3] > 0, 0, -1), [spec("body", PALETTE[0], shape=shape, bevel=0.0 if shape == "box" else 1.0)]


def read(png, a, turn_image, turn=0):
    """the parts picture and its .txt; the six old colours when there is no .txt. Opaque sprite pixels the picture
    leaves unpainted take the nearest painted pixel's part"""
    p = np.asarray(turn_image(Image.open(png).convert("RGBA"), turn))
    if p.shape != a.shape: raise ValueError("the parts picture is %dx%d, the sprite %dx%d" % (p.shape[1], p.shape[0], a.shape[1], a.shape[0]))
    txt = os.path.splitext(png)[0] + ".txt"
    if os.path.exists(txt):
        specs = []
        for line in open(txt, encoding="utf-8"):
            line = line.strip()
            if line: d = json.loads(line); specs.append(spec(d.get("label", "other"), d["colour"], **{k: v for k, v in d.items() if k not in ("label", "colour")}))
    else:
        specs = [spec("handle" if n == "shaft" else n, c) for n, c in OLD.items()]
    op = a[..., 3] > 0
    region = np.full(op.shape, -1, int)
    cols = [tuple(s["colour"]) for s in specs]
    for k, c in enumerate(cols):
        region[(p[..., 3] > 0) & np.all(p[..., :3] == np.array(c), axis=-1) & op] = k
    used = sorted(set(region[region >= 0].tolist()))
    if not used: raise ValueError("the parts picture has none of its parts' colours on the sprite")
    remap = {k: i for i, k in enumerate(used)}
    specs = [specs[k] for k in used]
    region = np.where(region >= 0, np.vectorize(lambda v: remap.get(v, -1))(region), -1)
    gy, gx = np.nonzero(region >= 0)
    for y, x in zip(*np.nonzero(op & (region < 0))):
        k = int(np.argmin((gy - y) ** 2 + (gx - x) ** 2)); region[y, x] = region[gy[k], gx[k]]
    return region, specs


def write(png, region, specs):
    """the parts picture and its .txt"""
    h, w = region.shape
    im = np.zeros((h, w, 4), np.uint8)
    for k, s in enumerate(specs): im[region == k] = tuple(s["colour"]) + (255,)
    Image.fromarray(im).save(png)
    with open(os.path.splitext(png)[0] + ".txt", "w", encoding="utf-8") as f:
        for s in specs: f.write(json.dumps(s) + "\n")


def to_old(region, specs, names):
    """the old part numbers (for the many-faces mesher): each shape as the old part that is built most like it"""
    as_old = {"blade": "blade", "roundbar": "shaft", "lathe": "shaft", "ball": "shaft", "plate": "head", "card": "head", "box": "guard", "dome": "gem"}
    part = np.full(region.shape, -1, int)
    for k, s in enumerate(specs):
        n = "grip" if s["label"] == "grip" and s["shape"] == "roundbar" else as_old.get(s["shape"], "head")
        part[region == k] = names.index(n)
    return part
