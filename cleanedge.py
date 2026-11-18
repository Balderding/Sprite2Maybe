"""cleanEdge in Python: a line-for-line port of torcado's cleanEdge shader (cleanedge-src\\cleanEdge-shadertoy.glsl),
used here to rotate and/or enlarge a small sprite. Never blends: every output pixel is one of the sprite's colours.

    python cleanedge.py IN.png OUT.png [--angle 45] [--scale 1] [--line 1.0] [--similar 0] [--highest 255,255,255]

  --angle    clockwise turn in degrees (45 stands a UW sword upright)
  --scale    output pixels per input pixel (1 = original pixel size, 4 = four times larger, any number works)
  --line     cleanEdge lineWidth
  --similar  cleanEdge similarThreshold (0..1 colour distance treated as "the same colour")
  --highest  the colour that wins where shapes overlap (default white)

The shader this is ported from carries this notice, which stays with the port:

MIT LICENSE
Copyright (c) 2022 torcado

Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated
documentation files (the "Software"), to deal in the Software without restriction, including without limitation the
rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to
permit persons to whom the Software is furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all copies or substantial portions of the
Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE
WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR
COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR
OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
"""
import argparse, math
import numpy as np
from PIL import Image

SLOPE = True
CLEANUP = True
CLEAR = (0.0, 0.0, 0.0, 0.0)


class CleanEdge:
    def __init__(self, im, line=1.0, similar=0.0, highest=(1.0, 1.0, 1.0)):
        a = np.asarray(im.convert("RGBA")).astype(np.float64) / 255.0
        a[a[..., 3] == 0] = 0
        self.h, self.w = a.shape[:2]
        self.px = [[tuple(a[y, x]) for x in range(self.w)] for y in range(self.h)]
        self.line, self.thr, self.hi = line, similar, highest

    def tex(self, x, y):
        x, y = int(math.floor(x)), int(math.floor(y))
        return self.px[y][x] if 0 <= x < self.w and 0 <= y < self.h else CLEAR

    # --- the shader's helpers -------------------------------------------------------------------------------------
    def similar(self, a, b):
        return (a[3] == 0 and b[3] == 0) or math.dist(a, b) <= self.thr

    def similar3(self, a, b, c):
        return self.similar(a, b) and self.similar(b, c)

    def similar4(self, a, b, c, d):
        return self.similar(a, b) and self.similar(b, c) and self.similar(c, d)

    def higher(self, this, other):
        if self.similar(this, other):
            return False
        if this[3] == other[3]:
            return math.dist(this[:3], self.hi) < math.dist(other[:3], self.hi)
        return this[3] > other[3]

    @staticmethod
    def cd(a, b):
        return math.dist(a, b)

    @staticmethod
    def dist_to_line(pt, p1, p2, d):
        lx, ly = p2[0] - p1[0], p2[1] - p1[1]
        px, py = ly, -lx
        n = math.hypot(px, py)
        tx, ty = p1[0] - pt[0], p1[1] - pt[1]
        return (1.0 if px * d[0] + py * d[1] > 0.0 else -1.0) * ((px * tx + py * ty) / n)

    def slice_dist(self, point, main, pd, ub, u, uf, uff, b, c, f, ff, db, d, df, dff, ddb, dd, ddf):
        sim, sim3, sim4, higher, cd, dtl = self.similar, self.similar3, self.similar4, self.higher, self.cd, self.dist_to_line
        lo, hi = (0.45, 1.142) if SLOPE else (0.0, 1.4)
        lw = max(lo, min(hi, self.line))
        point = (main[0] * (point[0] - 0.5) + 0.5, main[1] * (point[1] - 0.5) + 0.5)
        C = lambda x, y: (0.5 + x * pd[0], 0.5 + y * pd[1])
        neg = (-pd[0], -pd[1])

        against = 4.0 * cd(f, d) + cd(uf, c) + cd(c, db) + cd(ff, df) + cd(df, dd)
        towards = 4.0 * cd(c, df) + cd(u, f) + cd(f, dff) + cd(b, d) + cd(d, ddf)
        should = (against < towards) or ((against < towards + 0.001) and not higher(c, f))
        if sim4(f, d, b, u) and sim4(uf, df, db, ub) and not sim(c, f):
            should = False
        if not should:
            return None
        flip = False

        if SLOPE and sim3(f, d, db) and not sim3(f, d, b) and not sim(uf, db):      # lower shallow 2:1 slant
            if sim(c, df) and higher(c, f):
                pass
            else:
                if higher(c, f):
                    flip = True
                if sim(u, f) and not sim(c, df) and not higher(c, u):
                    flip = True
            if flip:
                dist = lw - dtl(point, C(1.5, -1.0), C(-0.5, 0.0), neg)
            else:
                dist = dtl(point, C(1.5, 0.0), C(-0.5, 1.0), pd)
            if CLEANUP and not flip and sim(c, uf) and not (sim3(c, uf, uff) and not sim3(c, uf, ff) and not sim(d, uff)):
                dist = min(dist, dtl(point, C(2.0, -1.0), C(-0.0, 1.0), pd))
            dist -= lw / 2.0
            return (f if cd(c, f) <= cd(c, d) else d) if dist <= 0.0 else None
        elif SLOPE and sim3(uf, f, d) and not sim3(u, f, d) and not sim(uf, db):    # forward steep 2:1 slant
            if sim(c, df) and higher(c, d):
                pass
            else:
                if higher(c, d):
                    flip = True
                if sim(b, d) and not sim(c, df) and not higher(c, d):
                    flip = True
            if flip:
                dist = lw - dtl(point, C(0.0, -0.5), C(-1.0, 1.5), neg)
            else:
                dist = dtl(point, C(1.0, -0.5), C(0.0, 1.5), pd)
            if CLEANUP and not flip and sim(c, db) and not (sim3(c, db, ddb) and not sim3(c, db, dd) and not sim(f, ddb)):
                dist = min(dist, dtl(point, C(1.0, 0.0), C(-1.0, 2.0), pd))
            dist -= lw / 2.0
            return (f if cd(c, f) <= cd(c, d) else d) if dist <= 0.0 else None
        elif sim(f, d):                                                             # 45 diagonal
            if sim(c, df) and higher(c, f):
                if not sim(c, dd) and not sim(c, ff):
                    flip = True
            else:
                if higher(c, f):
                    flip = True
                if not sim(c, b) and sim4(b, f, d, u):
                    flip = True
            if ((sim(f, db) and sim3(u, f, df)) or (sim(uf, d) and sim3(b, d, df))) and not sim(c, df):
                flip = True
            if flip:
                dist = lw - dtl(point, C(1.0, -1.0), C(-1.0, 1.0), neg)
            else:
                dist = dtl(point, C(1.0, 0.0), C(0.0, 1.0), pd)
            if SLOPE and CLEANUP:
                if not flip and sim3(c, uf, uff) and not sim3(c, uf, ff) and not sim(d, uff):
                    dist = max(dist, dtl(point, C(1.5, 0.0), C(-0.5, 1.0), pd))
                if not flip and sim3(ddb, db, c) and not sim3(dd, db, c) and not sim(ddb, f):
                    dist = max(dist, dtl(point, C(1.0, -0.5), C(0.0, 1.5), pd))
            dist -= lw / 2.0
            return (f if cd(c, f) <= cd(c, d) else d) if dist <= 0.0 else None
        elif SLOPE and sim3(ff, df, d) and not sim3(ff, df, c) and not sim(uff, d):  # far corner of shallow slant
            if sim(f, dff) and higher(f, ff):
                pass
            else:
                if higher(f, ff):
                    flip = True
                if sim(uf, ff) and not sim(f, dff) and not higher(f, uf):
                    flip = True
            if flip:
                dist = lw - dtl(point, C(2.5, -1.0), C(0.5, 0.0), neg)
            else:
                dist = dtl(point, C(2.5, 0.0), C(0.5, 1.0), pd)
            dist -= lw / 2.0
            return (ff if cd(f, ff) <= cd(f, df) else df) if dist <= 0.0 else None
        elif SLOPE and sim3(f, df, dd) and not sim3(c, df, dd) and not sim(f, ddb):  # far corner of steep slant
            if sim(d, ddf) and higher(d, dd):
                pass
            else:
                if higher(d, dd):
                    flip = True
                if sim(db, dd) and not sim(d, ddf) and not higher(d, dd):
                    flip = True
            if flip:
                dist = lw - dtl(point, C(0.0, 0.5), C(-1.0, 2.5), neg)
            else:
                dist = dtl(point, C(1.0, 0.5), C(0.0, 2.5), pd)
            dist -= lw / 2.0
            return (df if cd(d, df) <= cd(d, dd) else dd) if dist <= 0.0 else None
        return None

    def sample(self, sx, sy):
        """Colour at a continuous point of the sprite (in sprite pixels) - the shader's mainImage."""
        local = (sx - math.floor(sx), sy - math.floor(sy))
        cx, cy = math.floor(sx) + 0.5, math.floor(sy) + 0.5
        pd = (1.0 if local[0] >= 0.5 else -1.0, 1.0 if local[1] >= 0.5 else -1.0)
        t = lambda x, y: self.tex(cx + x * pd[0], cy + y * pd[1])
        uub, uu, uuf = t(-1, -2), t(0, -2), t(1, -2)
        ubb, ub, u, uf, uff = t(-2, -1), t(-1, -1), t(0, -1), t(1, -1), t(2, -1)
        bb, b, c, f, ff = t(-2, 0), t(-1, 0), t(0, 0), t(1, 0), t(2, 0)
        dbb, db, d, df, dff = t(-2, 1), t(-1, 1), t(0, 1), t(1, 1), t(2, 1)
        ddb, dd, ddf = t(-1, 2), t(0, 2), t(1, 2)
        col = c
        for r in (self.slice_dist(local, (1.0, 1.0), pd, ub, u, uf, uff, b, c, f, ff, db, d, df, dff, ddb, dd, ddf),
                  self.slice_dist(local, (-1.0, 1.0), pd, uf, u, ub, ubb, f, c, b, bb, df, d, db, dbb, ddf, dd, ddb),
                  self.slice_dist(local, (1.0, -1.0), pd, db, d, df, dff, b, c, f, ff, ub, u, uf, uff, uub, uu, uuf)):
            if r is not None:
                col = r
        return col

    def render(self, angle=0.0, scale=1.0, shift=(0.0, 0.0)):
        """The sprite turned clockwise by `angle` degrees at `scale` output pixels per sprite pixel."""
        th = math.radians(angle)
        co, si = math.cos(th), math.sin(th)
        M = int(math.ceil((abs(self.w * co) + abs(self.h * si)) * scale)) + 2
        N = int(math.ceil((abs(self.w * si) + abs(self.h * co)) * scale)) + 2
        out = np.zeros((N, M, 4), np.uint8)
        for y in range(N):
            for x in range(M):
                u = (x + 0.5 - M / 2) / scale + shift[0]
                v = (y + 0.5 - N / 2) / scale + shift[1]
                col = self.sample(co * u + si * v + self.w / 2, -si * u + co * v + self.h / 2)
                if col[3] > 0:
                    out[y, x] = [round(k * 255) for k in col]
        return Image.fromarray(out)


def crop(im):
    bb = im.getbbox()
    return im.crop(bb) if bb else im


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("src"); ap.add_argument("dst")
    ap.add_argument("--angle", type=float, default=45)
    ap.add_argument("--scale", type=float, default=1)
    ap.add_argument("--line", type=float, default=1.0)
    ap.add_argument("--similar", type=float, default=0.0)
    ap.add_argument("--highest", default="255,255,255")
    a = ap.parse_args()
    hi = tuple(int(k) / 255 for k in a.highest.split(","))
    ce = CleanEdge(Image.open(a.src), a.line, a.similar, hi)
    crop(ce.render(a.angle, a.scale)).save(a.dst)
    print(a.dst)
