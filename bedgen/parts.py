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
