r"""lowpoly.py: a model of very few polygons from a sprite, the colours carried by the texture (the sprite itself,
laid over the model from the front and the back: planar UVs, nearest pixel), not by thousands of faces.

Each part is one simple closed shape:
    handle (shaft + grip)   a prism of SIDES sides; one ring wherever its width changes, a flat cap at each end.
                            A plain handle is one segment: 12 + 8 = 20 triangles
    blade                   a diamond cross-section (edge, ridge, edge, ridge) swept along the blade's outline, one
                            row of four points wherever the outline turns; a point at the tip
    head, guard, the rest   a plate from the part's outline (traced, then simplified by Douglas-Peucker): the outline
                            itself is the sharp edge (thickness 0), a bevel runs in to a flat face at full thickness

Units: fine pixels in (the enlarged sprite's), sprite pixels out, x right from the sprite's middle, y up from its
foot, z toward the viewer. build() returns triangles (n, 3, 3) and their texture coordinates (n, 3, 2)."""
import math
import numpy as np

SIDES = 6


# ---------------------------------------------------------------- outlines
def trace(mask):
    """the outlines of a mask's set pixels along pixel corners, as loops of (x, y) corner points (y down); the
    outer loop of each piece first. Inside is on the right going round (clockwise on screen)"""
    h, w = mask.shape
    P = np.pad(mask, 1)
    out = {}
    def add(a, b): out.setdefault(a, []).append(b)
    ys, xs = np.nonzero(mask)
    for y, x in zip(ys.tolist(), xs.tolist()):
        if not P[y, x + 1]: add((x, y), (x + 1, y))                 # top
        if not P[y + 1, x + 2]: add((x + 1, y), (x + 1, y + 1))     # right
        if not P[y + 2, x + 1]: add((x + 1, y + 1), (x, y + 1))     # bottom
        if not P[y + 1, x]: add((x, y + 1), (x, y))                 # left
    loops = []
    while out:
        start = next(iter(out)); loop = [start]; prev = None; cur = start
        while True:
            nx = out[cur]
            if len(nx) > 1 and prev is not None:                    # a pinch: turn right first (keeps pieces apart)
                dx, dy = cur[0] - prev[0], cur[1] - prev[1]
                right = (cur[0] - dy, cur[1] + dx)
                nxt = right if right in nx else nx[0]
            else: nxt = nx[0]
            nx.remove(nxt)
            if not nx: del out[cur]
            prev, cur = cur, nxt
            if cur == start: break
            loop.append(cur)
        loops.append(loop)
    return loops


def area(poly):
    """signed area, y up (counter-clockwise positive)"""
    a = 0.0
    for i in range(len(poly)):
        x0, y0 = poly[i]; x1, y1 = poly[(i + 1) % len(poly)]
        a += x0 * y1 - x1 * y0
    return a / 2.0


def simplify_loop(loop, tol):
    """Douglas-Peucker on a closed loop: split at the two points farthest apart, simplify each half"""
    pts = np.array(loop, float)
    n = len(pts)
    if n <= 4: return [tuple(p) for p in pts]
    i1 = int(np.argmax(((pts - pts[0]) ** 2).sum(1)))
    def dp(line):
        """the kept points of an open polyline (both ends kept)"""
        if len(line) < 3: return list(line)
        p, q = line[0], line[-1]; d = q - p; L = math.hypot(*d); mid = line[1:-1] - p
        dist = np.abs(d[0] * mid[:, 1] - d[1] * mid[:, 0]) / L if L > 1e-9 else np.hypot(mid[:, 0], mid[:, 1])
        k = int(np.argmax(dist))
        if dist[k] <= tol: return [p, q]
        return dp(line[:k + 2])[:-1] + dp(line[k + 1:])
    a = dp(pts[:i1 + 1]); b = dp(np.vstack([pts[i1:], pts[:1]]))
    out = [tuple(p) for p in a[:-1] + b[:-1]]
    return out if len(out) >= 3 else [tuple(p) for p in pts[[0, n // 3, 2 * n // 3]]]


def simplify_profile(ys, cols, tol):
    """the rows to keep of a profile (one value or more per row): Douglas-Peucker, error = the largest gap between a
    value and the straight line between kept rows"""
    V = np.array(cols, float).T                                  # rows x values
    def dp(a, b):
        if b - a < 2: return [a, b]
        t = (np.array(ys[a + 1:b], float) - ys[a]) / (ys[b] - ys[a])
        lin = V[a] + (V[b] - V[a]) * t[:, None]
        e = np.abs(V[a + 1:b] - lin).max(1)
        k = int(np.argmax(e))
        if e[k] <= tol: return [a, b]
        return dp(a, a + 1 + k)[:-1] + dp(a + 1 + k, b)
    return dp(0, len(ys) - 1)


# ---------------------------------------------------------------- triangulating a flat polygon
def ear_clip(poly):
    """triangles (index triples) of a simple polygon, counter-clockwise, y up"""
    idx = list(range(len(poly)))
    tris = []
    def convex(a, b, c): return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0]) > 1e-12
    def inside(p, a, b, c):
        d1 = (p[0] - b[0]) * (a[1] - b[1]) - (a[0] - b[0]) * (p[1] - b[1])
        d2 = (p[0] - c[0]) * (b[1] - c[1]) - (b[0] - c[0]) * (p[1] - c[1])
        d3 = (p[0] - a[0]) * (c[1] - a[1]) - (c[0] - a[0]) * (p[1] - a[1])
        return not ((d1 < 0 or d2 < 0 or d3 < 0) and (d1 > 0 or d2 > 0 or d3 > 0))
    guard = 0
    while len(idx) > 3 and guard < 10000:
        guard += 1
        for k in range(len(idx)):
            i, j, l = idx[k - 1], idx[k], idx[(k + 1) % len(idx)]
            a, b, c = poly[i], poly[j], poly[l]
            if not convex(a, b, c): continue
            if any(inside(poly[m], a, b, c) for m in idx if m not in (i, j, l)): continue
            tris.append((i, j, l)); idx.pop(k); break
        else:                                                    # (no ear found: a bad polygon; fan what is left)
            tris += [(idx[0], idx[m], idx[m + 1]) for m in range(1, len(idx) - 1)]; idx = []; break
    if len(idx) == 3: tris.append(tuple(idx))
    return tris


def clean(poly, eps=1e-3):
    """the polygon without repeated points and without points on a straight line between their neighbours (they
    make zero-size triangles, which leave the model open)"""
    pts = [tuple(map(float, p)) for p in poly]
    changed = True
    while changed and len(pts) > 3:
        changed = False
        for i in range(len(pts)):
            a, b, c = pts[i - 1], pts[i], pts[(i + 1) % len(pts)]
            cross = (b[0] - a[0]) * (c[1] - b[1]) - (b[1] - a[1]) * (c[0] - b[0])
            if math.hypot(b[0] - a[0], b[1] - a[1]) < eps or abs(cross) < eps * max(1.0, math.hypot(c[0] - a[0], c[1] - a[1])):
                pts.pop(i); changed = True; break
    return pts


def segments_cross(poly):
    n = len(poly)
    def ccw(a, b, c): return (c[1] - a[1]) * (b[0] - a[0]) > (b[1] - a[1]) * (c[0] - a[0])
    for i in range(n):
        a, b = poly[i], poly[(i + 1) % n]
        for j in range(i + 2, n):
            if i == 0 and j == n - 1: continue
            c, d = poly[j], poly[(j + 1) % n]
            if ccw(a, c, d) != ccw(b, c, d) and ccw(a, b, c) != ccw(a, b, d): return True
    return False


def inset(poly, b):
    """the polygon moved in by b (counter-clockwise, y up), each corner along its mitre (kept to 2.5 b); None when
    that does not give a sound smaller polygon"""
    n = len(poly); P = np.array(poly, float); out = []
    for i in range(n):
        p0, p1, p2 = P[i - 1], P[i], P[(i + 1) % n]
        e1, e2 = p1 - p0, p2 - p1
        n1 = np.array([-e1[1], e1[0]]) / max(np.hypot(*e1), 1e-9); n2 = np.array([-e2[1], e2[0]]) / max(np.hypot(*e2), 1e-9)
        m = n1 + n2; L = np.hypot(*m)
        m = n1 if L < 1e-9 else m / L
        k = b / max(float(m @ n1), 0.4)
        out.append(tuple(p1 + m * min(k, 2.5 * b)))
    if area(out) <= 0.15 * area(poly) or segments_cross(out): return None
    if any(math.hypot(out[i][0] - out[i - 1][0], out[i][1] - out[i - 1][1]) < 0.05 for i in range(n)): return None
    if folds(out): return None
    return out


def folds(poly, eps=0.05):
    """whether a corner of the polygon lies on (or next to) one of its edges other than its own two"""
    n = len(poly)
    for i in range(n):
        px, py = poly[i]
        for j in range(n):
            if j == i or (j + 1) % n == i: continue
            (ax, ay), (bx, by) = poly[j], poly[(j + 1) % n]
            dx, dy = bx - ax, by - ay; L2 = dx * dx + dy * dy
            t = 0.0 if L2 < 1e-12 else min(1.0, max(0.0, ((px - ax) * dx + (py - ay) * dy) / L2))
            if math.hypot(px - ax - t * dx, py - ay - t * dy) < eps: return True
    return False


# ---------------------------------------------------------------- the parts
class Model:
    def __init__(self, W, Hh, N, scale):
        self.W, self.H, self.N, self.scale = W, Hh, N, scale       # the fine picture's size, fine pixels a sprite pixel
        self.tris, self.uvs = [], []
        self.zf = None                                           # a part's own transform of z (depth, taper, offset)

    def v(self, fx, fy, z):
        """a fine-pixel point (x right, y down) and a z in fine pixels -> sprite units, and its texture coordinate"""
        s = 1.0
        if self.scale is not None:
            sy, sx = min(max(int(fy), 0), self.H - 1), min(max(int(fx), 0), self.W - 1)
            sv = self.scale[sy, sx]
            if np.isfinite(sv): s = float(sv)
        N = self.N
        z = z * s
        if self.zf is not None: z = self.zf(fx, fy, z)
        return (fx / N - self.W / N / 2.0, (self.H - fy) / N, z / N), (fx / self.W, 1.0 - fy / self.H)

    def tri(self, a, b, c):
        self.tris.append((a[0], b[0], c[0])); self.uvs.append((a[1], b[1], c[1]))

    def quad(self, a, b, c, d): self.tri(a, b, c); self.tri(a, c, d)

    def prism(self, rows, sides=SIDES):
        """a handle: rows = [(y, centre, radius)] from top to bottom (fine pixels); a ring of so many sides at each"""
        rings = []
        for y, c, r in rows:
            rings.append([self.v(c + r * math.cos(2 * math.pi * k / sides), y, r * math.sin(2 * math.pi * k / sides)) for k in range(sides)])
        for A, B in zip(rings, rings[1:]):
            for k in range(sides):
                k2 = (k + 1) % sides
                self.quad(A[k], A[k2], B[k2], B[k])          # (outward)
        top, bot = rings[0], rings[-1]
        for k in range(1, sides - 1):
            self.tri(top[0], top[k + 1], top[k]); self.tri(bot[0], bot[k], bot[k + 1])

    def blade(self, rows, t_of):
        """a blade: rows = [(y, left, right)] top to bottom; a diamond (left edge, front ridge, right edge, back ridge)
        at each row, its half-thickness t_of(width); the top row a point when it is narrow"""
        rings = []
        for y, x0, x1 in rows:
            c, t = (x0 + x1) / 2.0, t_of(x1 - x0, y)
            rings.append([self.v(x0, y, 0.0), self.v(c, y, t), self.v(x1, y, 0.0), self.v(c, y, -t)])
        y0, a0, b0 = rows[0]
        tip = (b0 - a0) <= 1.5 * self.N
        start = 0
        if tip:
            apex = self.v((a0 + b0) / 2.0, y0, 0.0)
            R = rings[1] if len(rings) > 1 else rings[0]
            for k in range(4): self.tri(apex, R[k], R[(k + 1) % 4])
            start = 1
        else:
            T = rings[0]; self.tri(T[0], T[1], T[2]); self.tri(T[0], T[2], T[3])
        for A, B in zip(rings[start:], rings[start + 1:]):
            for k in range(4):
                k2 = (k + 1) % 4
                self.quad(A[k], B[k], B[k2], A[k2])
        Bt = rings[-1]; self.tri(Bt[0], Bt[2], Bt[1]); self.tri(Bt[0], Bt[3], Bt[2])

    def rings(self, poly, levels):
        """a plate in rings: the outline at z 0, then for each (inset, z) of levels a ring moved in by inset at height
        z (front and back), the last one capped flat. Levels that do not give a sound ring are left out; with none
        left it is a slab. Used for domes (several rings on a round profile)"""
        poly = clean(poly)
        up = [(x, -y) for x, y in poly]
        if area(up) < 0: poly, up = poly[::-1], up[::-1]
        ring_up = []
        for b, z in levels:
            q = inset(up, b) if b > 0.05 else None
            if q is None: break
            ring_up.append((q, z))
        if not ring_up: return self.plate(poly, levels[-1][1] if levels else 0.5, 0.0)
        prevF = prevB = [self.v(x, y, 0.0) for x, y in poly]
        for q, z in ring_up:
            Q = [(x, -y) for x, y in q]
            F = [self.v(x, y, z) for x, y in Q]; Bk = [self.v(x, y, -z) for x, y in Q]
            n = len(Q)
            for i in range(n):
                j = (i + 1) % n
                self.quad(prevF[i], prevF[j], F[j], F[i]); self.quad(prevB[i], Bk[i], Bk[j], prevB[j])
            prevF, prevB, last = F, Bk, q
        for i, j, k in ear_clip(last): self.tri(prevF[i], prevF[j], prevF[k]); self.tri(prevB[i], prevB[k], prevB[j])

    def plate(self, poly, t, bevel):
        """a plate: poly = the outline (fine pixels, y down), its edge sharp (z 0), a bevel of width `bevel` up to a
        flat face at half-thickness t. A plate too narrow for a bevel is a slab with straight sides"""
        poly = clean(poly)
        up = [(x, -y) for x, y in poly]                          # y up for the geometry tests
        if area(up) < 0: poly, up = poly[::-1], up[::-1]
        q = None; b = bevel
        for _ in range(4):
            if b <= 0.05: break
            q = inset(up, b)
            if q is not None: break
            b *= 0.5
        P0 = [self.v(x, y, 0.0) for x, y in poly]
        if q is None:                                            # a slab
            F = [self.v(x, y, t) for x, y in poly]; Bk = [self.v(x, y, -t) for x, y in poly]
            for i in range(len(poly)):
                j = (i + 1) % len(poly); self.quad(F[i], Bk[i], Bk[j], F[j])
            for i, j, k in ear_clip(up): self.tri(F[i], F[j], F[k]); self.tri(Bk[i], Bk[k], Bk[j])
            return
        Q = [(x, -y) for x, y in q]
        F = [self.v(x, y, t) for x, y in Q]; Bk = [self.v(x, y, -t) for x, y in Q]
        n = len(poly)
        for i in range(n):
            j = (i + 1) % n
            self.quad(P0[i], P0[j], F[j], F[i])                  # front bevel
            self.quad(P0[i], Bk[i], Bk[j], P0[j])                # back bevel
        for i, j, k in ear_clip(q): self.tri(F[i], F[j], F[k]); self.tri(Bk[i], Bk[k], Bk[j])


def build(fa, fpart, names, N, T, method, scale=None, blade_of_handle=0.6, head_of_handle=0.85):
    """the low-poly model of an enlarged sprite. fa: RGBA (fine), fpart: each fine pixel's part (-1 clear), names:
    the part names, N fine pixels a sprite pixel, T the thickness setting (sprite pixels). Returns (tris, uvs, notes)"""
    Hh, W = fa.shape[:2]
    op = fa[..., 3] > 0
    m = Model(W, Hh, N, scale)
    ix = {n: k for k, n in enumerate(names)}
    tol = 0.35 * N
    notes = {}
    def pieces(mask):
        """the mask's separate pieces (4-connected), each a mask"""
        lab = np.zeros(mask.shape, int); n = 0
        for y0, x0 in zip(*np.nonzero(mask)):
            if lab[y0, x0]: continue
            n += 1; st = [(y0, x0)]; lab[y0, x0] = n
            while st:
                y, x = st.pop()
                for yy, xx in ((y - 1, x), (y + 1, x), (y, x - 1), (y, x + 1)):
                    if 0 <= yy < mask.shape[0] and 0 <= xx < mask.shape[1] and mask[yy, xx] and not lab[yy, xx]:
                        lab[yy, xx] = n; st.append((yy, xx))
        return [lab == k for k in range(1, n + 1)]
    def rows_of(mask):
        out = []
        for y in range(mask.shape[0]):
            xs = np.nonzero(mask[y])[0]
            if len(xs): out.append((y, float(xs[0]), float(xs[-1] + 1)))
        return out
    def handle_rows(piece):
        """the prism's rings: each row's centre and radius; kept rows by Douglas-Peucker; the top ring at the top
        edge of the first row, the bottom one at the bottom edge of the last"""
        R = rows_of(piece)
        ys = [y + 0.5 for y, _, _ in R]; cs = [(a + b) / 2 for _, a, b in R]; rs = [(b - a) / 2 for _, a, b in R]
        keep = simplify_profile(ys, [cs, rs], tol) if len(R) > 1 else [0]
        out = [(R[k][0] + 0.5, cs[k], rs[k]) for k in keep]
        out[0] = (R[0][0], out[0][1], out[0][2]); out[-1] = (R[-1][0] + 1, out[-1][1], out[-1][2])
        if len(out) == 1: out.append((R[0][0] + 1, cs[0], rs[0]))
        return out
    if method == "turned":
        for p in pieces(op): m.prism(handle_rows(p))
        return np.array(m.tris), np.array(m.uvs), {"parts": "turned"}
    if method in ("round", "slab") or fpart is None:
        for p in pieces(op):
            loops = trace(p); lp = max(loops, key=lambda L: abs(area(L)))
            m.plate(simplify_loop(lp, tol), T * N, 0.0 if method == "slab" else 1.5 * N)
        return np.array(m.tris), np.array(m.uvs), {"parts": "one plate"}
    hand = op & ((fpart == ix["shaft"]) | (fpart == ix["grip"]))
    r_hand = 0.0
    n0 = len(m.tris)
    for p in pieces(hand):
        rows = handle_rows(p); m.prism(rows)
        r_hand = max(r_hand, max(r for _, _, r in rows))
    notes["handle"] = len(m.tris) - n0; n0 = len(m.tris)
    t_cap = r_hand if r_hand > 0 else T * N
    blade = op & (fpart == ix["blade"])
    for p in pieces(blade):
        R = rows_of(p)
        ys = [y + 0.5 for y, _, _ in R]
        keep = simplify_profile(ys, [[a for _, a, _ in R], [b for _, _, b in R]], tol) if len(R) > 1 else [0]
        rows = [(R[k][0] + 0.5, R[k][1], R[k][2]) for k in keep]
        rows[0] = (R[0][0], rows[0][1], rows[0][2]); rows[-1] = (R[-1][0] + 1, rows[-1][1], rows[-1][2])
        if len(rows) == 1: rows.append((R[0][0] + 1, R[0][1], R[0][2]))
        wmax = max(b - a for _, a, b in rows)
        tb = min(T * N, blade_of_handle * t_cap)
        m.blade(rows, lambda wd, y, tb=tb, wmax=wmax: tb * max(0.35, min(1.0, wd / wmax)))
    if blade.any(): notes["blade"] = len(m.tris) - n0; n0 = len(m.tris)
    rest = op & ~hand & ~blade
    for name, k, t, bev in (("guard", ix["guard"], 1.1 * t_cap if t_cap > 0 else T * N, 0.6 * N),   # (a guard is as thick as the grip it sits on)
                            ("head", None, min(T * N, head_of_handle * t_cap), 1.5 * N)):
        mk = (rest & (fpart == k)) if k is not None else (rest & (fpart != ix["guard"]))
        for p in pieces(mk):
            if p.sum() < 2: continue
            loops = trace(p); lp = max(loops, key=lambda L: abs(area(L)))
            m.plate(simplify_loop(lp, tol), t, bev)
        if len(m.tris) > n0: notes[name] = len(m.tris) - n0; n0 = len(m.tris)
    return np.array(m.tris), np.array(m.uvs), notes


def bleed(fa):
    """the texture with every clear pixel given its nearest coloured neighbour's colour (so an edge of the
    simplified outline that runs just outside the sprite still shows the sprite's colour), alpha full"""
    a = fa.copy(); filled = a[..., 3] > 0
    for _ in range(256):                                         # (a neighbour's colour copied, never an average)
        if filled.all(): break
        new = filled.copy()
        for dy, dx in ((-1, 0), (1, 0), (0, -1), (0, 1)):
            sh = np.roll(np.roll(filled, dy, 0), dx, 1); col = np.roll(np.roll(a[..., :3], dy, 0), dx, 1)
            take = sh & ~new
            a[take, :3] = col[take]; new |= take
        filled = new
    a[..., 3] = 255
    return a


# ---------------------------------------------------------------- any sprite, in labelled parts (regions.py)
GRIP_OVAL = 0.75        # a sword grip's thickness / its width (measured grips are flattened ovals)
BLADE_THICK = 0.25      # a blade's thickness / its width at the guard (real: about 0.11; doubled so it reads at game size)
DISTAL = 0.4            # a blade's thickness at the tip / at the guard (real: 5 mm down to 2 mm)
POMMEL_DISC = 0.6       # a pommel's thickness / its width (real wheel pommels: about 0.55)


def build_regions(fa, fregion, specs, N, T, scale=None, blade_of_handle=0.6, head_of_handle=0.85):
    """the low-poly model of an enlarged sprite in parts: fregion each fine pixel's part (an index into specs, -1
    clear), specs each part's label, shape and settings (regions.py). Each part is built by its shape, then its own
    transform (depth, taper, offset) is applied. Returns (tris, uvs, notes: triangles a part)"""
    Hh, W = fa.shape[:2]
    op = fa[..., 3] > 0
    m = Model(W, Hh, N, scale)
    notes = {}
    def pieces(mask):
        lab = np.zeros(mask.shape, int); n = 0
        for y0, x0 in zip(*np.nonzero(mask)):
            if lab[y0, x0]: continue
            n += 1; st = [(y0, x0)]; lab[y0, x0] = n
            while st:
                y, x = st.pop()
                for yy, xx in ((y - 1, x), (y + 1, x), (y, x - 1), (y, x + 1)):
                    if 0 <= yy < mask.shape[0] and 0 <= xx < mask.shape[1] and mask[yy, xx] and not lab[yy, xx]:
                        lab[yy, xx] = n; st.append((yy, xx))
        return [lab == k for k in range(1, n + 1)]
    def rows_of(mask):
        out = []
        for y in range(mask.shape[0]):
            xs = np.nonzero(mask[y])[0]
            if len(xs): out.append((y, float(xs[0]), float(xs[-1] + 1)))
        return out
    def ring_rows(piece, tol):
        R = rows_of(piece)
        ys = [y + 0.5 for y, _, _ in R]; cs = [(a + b) / 2 for _, a, b in R]; rs = [(b - a) / 2 for _, a, b in R]
        keep = simplify_profile(ys, [cs, rs], tol) if len(R) > 1 else [0]
        out = [(R[k][0] + 0.5, cs[k], rs[k]) for k in keep]
        out[0] = (R[0][0], out[0][1], out[0][2]); out[-1] = (R[-1][0] + 1, out[-1][1], out[-1][2])
        if len(out) == 1: out.append((R[0][0] + 1, cs[0], rs[0]))
        return out
    def outline(piece, tol):
        loops = trace(piece); lp = max(loops, key=lambda L: abs(area(L)))
        return simplify_loop(lp, tol)
    def transform(sp, piece):
        ys, xs = np.nonzero(piece)
        y0, y1, x0, x1 = ys.min(), ys.max() + 1, xs.min(), xs.max() + 1
        d, off, tp, am = float(sp["depth"]), float(sp["offset"]) * N, sp["taper"], float(sp["taper_amount"])
        def zf(fx, fy, z):
            f = 1.0
            if tp != "none" and am > 0:
                t = (fy - y0) / max(y1 - y0, 1) if tp in ("up", "down") else (fx - x0) / max(x1 - x0, 1)
                t = min(max(t, 0.0), 1.0)
                f = 1.0 - am * ((1.0 - t) if tp in ("up", "left") else t)
            return z * d * f + off
        return zf
    # a weapon with a blade is built to a real sword's proportions (RESEARCH.md section E): the grip an oval, the
    # blade's thickness from its own width and thinning toward the tip, the pommel a thick disc
    sword = any(sp["label"] == "blade" and sp["shape"] == "blade" for sp in specs)
    oval = GRIP_OVAL if sword else 1.0
    def squash(zf, f):
        return zf if f == 1.0 else (lambda fx, fy, z: zf(fx, fy, z * f))
    # the handle's radius first: blades and heads are kept thinner than it
    r_hand = 0.0
    for k, sp in enumerate(specs):
        if sp["label"] in ("handle", "grip") and sp["shape"] in ("roundbar", "lathe"):
            for p in pieces(op & (fregion == k)):
                # (its usual row, not its widest: a swelling or an unmarked pommel must not thicken blade and guard)
                r_hand = max(r_hand, float(np.median([(b - a) / 2.0 for _, a, b in rows_of(p)])))
    r_hand *= oval                                               # (the grip's thin way)
    # parts built together: a handle and a grip (or several) with the same shape and settings are one prism, the
    # colours telling them apart; every other part on its own
    groups = {}
    for k, sp in enumerate(specs):
        if sp["label"] in ("handle", "grip") and sp["shape"] in ("roundbar", "lathe"):
            key = ("hand", sp["shape"], sp["depth"], sp["offset"], sp["taper"], sp["taper_amount"], sp["sides"])
        else: key = ("part", k)
        groups.setdefault(key, []).append(k)
    for key, ks in groups.items():
        k = ks[0]; sp = specs[k]
        n0 = len(m.tris); shp = sp["shape"]
        for p in pieces(op & np.isin(fregion, ks)):
            if p.sum() < 2: continue
            m.zf = transform(sp, p)
            if shp in ("roundbar", "lathe", "ball"):
                tol = {"roundbar": 0.35, "lathe": 0.2, "ball": 0.15}[shp] * N
                rr = ring_rows(p, tol)
                sides = max(3, int(sp["sides"]))
                if shp == "ball" and max(r for _, _, r in rr) <= 2.5 * N:          # a small ball (a pommel cap): fewer rings and sides
                    rr = ring_rows(p, 0.3 * N); sides = min(sides, 6)
                if key[0] == "hand" and shp == "roundbar": m.zf = squash(m.zf, oval)          # (an oval grip: wider than thick)
                elif sword and sp["label"] == "pommel":
                    # a disc: POMMEL_DISC of its width thick, but never thinner than the grip it ends (nor rounder than a ball)
                    rp = max(r for _, _, r in rr)
                    m.zf = squash(m.zf, min(1.0, max(POMMEL_DISC, 1.15 * r_hand / max(rp, 1e-9))))
                m.prism(rr, sides)
            elif shp == "blade":
                R = rows_of(p)
                ys = [y + 0.5 for y, _, _ in R]
                keep = simplify_profile(ys, [[a for _, a, _ in R], [b for _, _, b in R]], 0.35 * N) if len(R) > 1 else [0]
                rows = [(R[i][0] + 0.5, R[i][1], R[i][2]) for i in keep]
                rows[0] = (R[0][0], rows[0][1], rows[0][2]); rows[-1] = (R[-1][0] + 1, rows[-1][1], rows[-1][2])
                if len(rows) == 1: rows.append((R[0][0] + 1, R[0][1], R[0][2]))
                wmax = max(b - a for _, a, b in rows)
                tb = min(T * N, BLADE_THICK / 2.0 * wmax)                # (from its own width, as on a real blade)
                if r_hand > 0: tb = min(tb, blade_of_handle * r_hand)
                # distal taper: thinnest at the tip (the narrower end), unless the part has a taper of its own
                tip_top = (rows[0][2] - rows[0][1]) <= (rows[-1][2] - rows[-1][1])
                ya, yb = rows[0][0], rows[-1][0]
                def t_of(wd, y, tb=tb, wmax=wmax, own=sp["taper"] != "none"):
                    t = tb * max(0.5, min(1.0, wd / wmax))
                    if own: return t
                    u = (y - ya) / max(yb - ya, 1e-9)                   # 0 at the top row, 1 at the bottom
                    return t * (DISTAL + (1.0 - DISTAL) * (u if tip_top else 1.0 - u))
                m.blade(rows, t_of)
            elif shp in ("plate", "box", "card"):
                t = T * N
                if r_hand > 0 and sp["label"] == "head": t = min(t, head_of_handle * r_hand)
                if r_hand > 0 and sp["label"] == "guard": t = 1.1 * r_hand      # (as thick as the grip it sits on, whatever the thickness setting)
                if shp == "card": t = 0.12 * N
                m.plate(outline(p, (0.6 if sp["label"] == "guard" else 0.35) * N), t, float(sp["bevel"]) * N if shp == "plate" else 0.0)
            elif shp == "dome":
                ys, xs = np.nonzero(p)
                R = 0.5 * min(ys.max() - ys.min() + 1, xs.max() - xs.min() + 1)
                t = max(T * N, 0.5 * R)                          # (a dome rises with its size: a pebble, not a coin)
                fr = (0.3, 0.62, 0.9) if R >= 3 * N else (0.4, 0.85) if R >= 1.5 * N else (0.6,)          # (small: fewer rings)
                levels = [(R * f, t * math.sqrt(max(0.0, 1 - (1 - f) ** 2))) for f in fr]
                m.rings(outline(p, 0.35 * N), levels)
        m.zf = None
        if len(m.tris) > n0:
            lab = " + ".join(sorted(set(specs[j]["label"] for j in ks)))
            if sum(s["label"] == sp["label"] for s in specs) > len(ks): lab = "%s %d" % (lab, k + 1)
            notes["%s (%s)" % (lab, shp)] = len(m.tris) - n0
    return np.array(m.tris), np.array(m.uvs), notes
