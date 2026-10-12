"""2D part geometry (shapely) plus where each copy sits in the 3D assembly."""
from dataclasses import dataclass, field

import numpy as np
from shapely.geometry import LineString, Point, Polygon, box
from shapely.ops import unary_union

RES = 12  # arc segments per quarter circle


@dataclass
class Placement:
    origin: tuple
    u: tuple  # part x axis in world space
    v: tuple  # part y axis in world space
    n: tuple  # thickness direction in world space

    def to_world(self, pts_uv, w):
        o, u, v, n = (np.asarray(a, float) for a in (self.origin, self.u, self.v, self.n))
        pts = np.asarray(pts_uv, float)
        return o + pts[:, :1] * u + pts[:, 1:2] * v + w * n


@dataclass
class Part:
    name: str
    shape: Polygon
    placements: list = field(default_factory=list)
    note: str = ""
    color: str = "#d9c3a0"
    material: str = "plywood"   # "plywood" parts get cut; others are render-only
    # pockets cut into the w=0 face: list of (polygon, depth, label). Parts with
    # pockets are exported mirrored so they cut with that face up.
    pockets: list = field(default_factory=list)

    @property
    def qty(self):
        return len(self.placements)

    @property
    def size(self):
        x0, y0, x1, y1 = self.shape.bounds
        return x1 - x0, y1 - y0


def place(origin, u, v, n):
    return Placement(tuple(origin), tuple(u), tuple(v), tuple(n))


X, Y, Z = (1, 0, 0), (0, 1, 0), (0, 0, 1)
NX, NY = (-1, 0, 0), (0, -1, 0)


def rect(x0, y0, x1, y1):
    return box(min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1))


def round_convex(shape, r):
    return shape.buffer(-r, quad_segs=RES).buffer(r, quad_segs=RES) if r > 0 else shape


def round_concave(shape, r):
    return shape.buffer(r, quad_segs=RES).buffer(-r, quad_segs=RES) if r > 0 else shape


def rounded_rect(x0, y0, x1, y1, r):
    return round_convex(rect(x0, y0, x1, y1), r)


def stadium(cx, y0, y1, w):
    """Vertical slot with full round ends, spanning y0..y1 overall."""
    r = w / 2
    return LineString([(cx, y0 + r), (cx, y1 - r)]).buffer(r, quad_segs=RES)


def h_stadium(cx, cy, length, w):
    r = w / 2
    return LineString([(cx - length / 2 + r, cy), (cx + length / 2 - r, cy)]).buffer(r, quad_segs=RES)


def slots_between(a, b, y0, y1, slot_w, slat_w, margin, min_slots=3):
    """Evenly spaced vertical slots filling the span a..b, `margin` solid at each end."""
    span = b - a - 2 * margin
    if span < slot_w:
        return []
    n = int((span + slat_w) // (slot_w + slat_w))
    if n < min_slots:
        return []
    used = n * slot_w + (n - 1) * slat_w
    start = a + margin + (span - used) / 2 + slot_w / 2
    return [stadium(start + i * (slot_w + slat_w), y0, y1, slot_w) for i in range(n)]


def flower(cx, cy, d, petals=8, rot=0.0, web=0.3):
    """Daisy-shaped cut-out, `d` across the petal tips: tapered petals round a centre disc.

    The petals narrow toward the centre so neighbours never touch, and the
    outline is shrunk by web/2 so the wood between petals is at least `web` wide.
    """
    from shapely import affinity
    t = web / 2
    R = d / 2 + t
    petal = unary_union([Point(0.35 * R, 0).buffer(0.1 * R, quad_segs=RES * 2),
                         Point(0.74 * R, 0).buffer(0.26 * R, quad_segs=RES * 4)]).convex_hull
    shapes = [affinity.rotate(petal, rot + 360 * k / petals, origin=(0, 0)) for k in range(int(petals))]
    shapes.append(Point(0, 0).buffer(0.33 * R, quad_segs=RES * 4))
    return affinity.translate(unary_union(shapes).buffer(-t, quad_segs=RES), cx, cy)


def tree(cx, y0, h, w):
    """Pine-tree cut-out: a trunk and three stacked tiers, `h` tall and `w` wide at the base."""
    k = h / 6.5
    trunk = rect(cx - 0.275 * k, y0, cx + 0.275 * k, y0 + 1.0 * k)
    tiers = []
    for yb, yt, bw in ((0.9, 3.4, 1.0), (2.6, 5.0, 0.82), (4.2, 6.5, 0.62)):
        tiers.append(Polygon([(cx - bw * w / 2, y0 + yb * k), (cx + bw * w / 2, y0 + yb * k), (cx, y0 + yt * k)]))
    # round the tips and tier corners so a round bit can cut them
    return round_convex(unary_union([trunk] + tiers), 0.15)


def trees_between(a, b, y0, y1, h, w, pitch, stagger, margin):
    """A row of tree cut-outs across a..b, alternately raised by `stagger`."""
    span = b - a - 2 * margin
    n = int((span - w) // pitch) + 1
    if n < 1 or y1 - y0 < h + stagger:
        return []
    start = a + margin + (span - (n - 1) * pitch) / 2
    return [tree(start + i * pitch, y0 + (stagger if i % 2 else 0), h, w) for i in range(n)]


def _leaflet(pts, w):
    """Oval leaflet along a polyline: widest in the middle, with ends round enough
    (radius 0.33 w) for a bit up to 2/3 of the leaflet width."""
    import numpy as np
    n = len(pts)
    discs = [Point(q).buffer(w / 2 * (0.66 + 0.34 * np.sin(np.pi * i / (n - 1))), quad_segs=RES)
             for i, q in enumerate(pts)]
    return unary_union([a.union(b).convex_hull for a, b in zip(discs, discs[1:])])


def frond(cx, y0, h, lean=0.0, leaf_w=0.4, leaf_len=2.1, web=0.25, rib=0.14, stem_t=0.15):
    """Fern-frond cut-outs: a curved stem slot and oval leaflets alternating up a
    gently bent midrib, longest near the bottom and shrinking to the tip.
    Returns a list of separate holes, each at least `web` apart."""
    import numpy as np

    def mid(t):  # midrib point and unit tangent at fraction t of the height
        tan = np.array([2 * lean * t / h, 1.0])
        return np.array([cx + lean * t * t, y0 + t * h]), tan / np.linalg.norm(tan)

    hook = 0.25 * (1 if lean >= 0 else -1)
    sp = [mid(t)[0] + [hook * (1 - t / stem_t) ** 2, 0] for t in np.linspace(0, stem_t, 8)]
    sp[0] = sp[0] + [0, leaf_w / 2]
    stem = LineString(sp).buffer(leaf_w * 0.4, quad_segs=RES)

    def make(t, frac, side):
        ang = np.radians(22 + 33 * frac)           # leaflets sweep up more toward the tip
        L = max(leaf_len * (1 - frac) ** 0.75 * min(1.0, 0.7 + frac * 3), leaf_w * 1.3)
        p, tan = mid(t)
        nrm = np.array([tan[1], -tan[0]]) * side   # away from the midrib
        q = p + (nrm * np.cos(ang) + tan * np.sin(ang)) * (rib + leaf_w * 0.33)
        pts = [q]
        for k in range(10):                         # each leaflet curls 12 degrees upward
            a = ang + np.radians(12) * (k + 0.5) / 10
            q = q + (nrm * np.cos(a) + tan * np.sin(a)) * (L - leaf_w * 0.66) / 10
            pts.append(q)
        return _leaflet(pts, leaf_w)

    leaves, side = [], 1
    t0 = t = stem_t + 0.02
    t1 = 0.93
    while t < t1:
        frac = (t - t0) / (t1 - t0)
        leaf = make(t, frac, side)
        # slide up until it clears the stem and the leaflets below it
        while t < t1 and (leaf.distance(stem) < web or any(leaf.distance(o) < web for o in leaves[-3:])):
            t += 0.004
            leaf = make(t, frac, side)
        if t >= t1:
            break
        leaves.append(leaf)
        side = -side
        t += 0.006
    return [stem] + leaves


def fronds_between(a, b, y0, y1, h, pitch, margin, leaf_w=0.4, web=0.25, lean=0.3):
    """A row of fern fronds across a..b, leaning alternately left and right."""
    span = b - a - 2 * margin
    width = 3.5 * h / 10.5
    n = int((span - width) // pitch) + 1
    if n < 1 or y1 - y0 < h:
        return []
    start = a + margin + (span - (n - 1) * pitch) / 2
    out = []
    for i in range(n):
        out += frond(start + i * pitch, y0, h, lean=lean * (1 if i % 2 else -1), leaf_w=leaf_w,
                     leaf_len=2.1 * h / 10.5, web=web)
    return out


def flowers_between(a, b, y0, y1, d, gap, margin, petals=8):
    """Evenly spaced flower cut-outs filling a..b, centred in the band y0..y1."""
    span = b - a - 2 * margin
    n = int((span + gap) // (d + gap))
    if n < 1 or y1 - y0 < d:
        return []
    used = n * d + (n - 1) * gap
    start = a + margin + (span - used) / 2 + d / 2
    cy = (y0 + y1) / 2
    return [flower(start + i * (d + gap), cy, d, petals) for i in range(n)]


def puzzle_knob(x, y, p, direction=1):
    """Round 'jigsaw' knob whose base sits on the vertical line at x, pointing +x."""
    r, neck, reach = p.knob_radius, p.knob_neck, p.knob_reach
    cx = x + direction * (reach - r)
    stem = rect(x - direction * 0.5, y - neck / 2, cx, y + neck / 2)
    knob = unary_union([stem, Point(cx, y).buffer(r, quad_segs=RES)])
    # soften every corner so a round bit can cut both sides of the joint
    f = max(p.bit_diameter / 2 + 0.03, 0.15)
    return round_convex(round_concave(knob, f), 0.05)


def split_with_puzzle(shape, x, knob_ys, p):
    """Cut `shape` at the vertical line x; left half gets knobs, right gets sockets."""
    minx, miny, maxx, maxy = shape.bounds
    knobs = unary_union([puzzle_knob(x, y, p) for y in knob_ys])
    left = shape.intersection(rect(minx - 1, miny - 1, x, maxy + 1))
    right = shape.intersection(rect(x, miny - 1, maxx + 1, maxy + 1))
    left = unary_union([left, knobs.intersection(shape.buffer(p.knob_reach + 1))])
    # fillet where the knob necks meet the joint line (a round bit can't cut a sharp inside corner)
    f = max(p.bit_diameter / 2 + 0.03, 0.15)
    near = rect(x - 1, miny - 1, x + p.knob_reach + 1, maxy + 1)
    left = unary_union([left.difference(near), round_concave(left, f).intersection(near)])
    right = right.difference(left.buffer(p.knob_clearance, quad_segs=RES))
    return _single(left), _single(right)


def _single(g):
    if g.geom_type == "Polygon":
        return g
    parts = sorted(g.geoms, key=lambda q: q.area, reverse=True)
    return parts[0]


def slot_with_dogbones(x0, y0, x1, y1, bit_diameter):
    """Rectangular through-slot with dogbone reliefs so square tabs seat fully."""
    r = bit_diameter / 2 + 0.01
    k = r / 2 ** 0.5
    s = rect(x0, y0, x1, y1)
    bones = [Point(x0 + k, y0 + k), Point(x1 - k, y0 + k), Point(x0 + k, y1 - k), Point(x1 - k, y1 - k)]
    return unary_union([s] + [b.buffer(r, quad_segs=RES) for b in bones])


def tab_centres(length, tab, n=2):
    """Centres of n tabs spread along an edge of the given length."""
    if length < tab * n + 2:
        n = 1
    return [length * (i + 0.5) / n for i in range(n)]
