"""Writers: DXF cut files, nested sheet layouts, cut list, and preview renders."""
import math
import os

import ezdxf
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
from matplotlib.patches import PathPatch, Polygon as MplPolygon  # noqa: E402
from matplotlib.path import Path  # noqa: E402
from shapely import affinity  # noqa: E402
from shapely.geometry.polygon import orient  # noqa: E402

from .nest import nest  # noqa: E402

LAYERS = {"CUT_OUTSIDE": 1, "CUT_INSIDE": 5, "LABEL": 3, "SHEET": 8}


def fmt(x):
    """Inches as a tape-measure friendly string, to the nearest 1/16."""
    sixteenths = round(x * 16)
    whole, frac = divmod(sixteenths, 16)
    if frac == 0:
        return f'{whole}"'
    g = math.gcd(frac, 16)
    return f'{whole} {frac // g}/{16 // g}"' if whole else f'{frac // g}/{16 // g}"'


# ---------------------------------------------------------------------------
# DXF
# ---------------------------------------------------------------------------
def _new_doc():
    doc = ezdxf.new("R2010", setup=True)
    doc.units = ezdxf.units.IN
    doc.header["$INSUNITS"] = 1
    doc.header["$MEASUREMENT"] = 0
    for name, color in LAYERS.items():
        doc.layers.add(name, color=color)
    return doc


def _add_shape(msp, shape):
    shape = orient(shape)
    msp.add_lwpolyline(list(shape.exterior.coords)[:-1], close=True,
                       dxfattribs={"layer": "CUT_OUTSIDE"})
    for ring in shape.interiors:
        msp.add_lwpolyline(list(ring.coords)[:-1], close=True, dxfattribs={"layer": "CUT_INSIDE"})


def write_part_dxf(part, path):
    doc = _new_doc()
    msp = doc.modelspace()
    _add_shape(msp, part.shape)
    w, h = part.size
    msp.add_text(f"{part.name} x{part.qty}  ({w:.3f} x {h:.3f} in)", height=0.4,
                 dxfattribs={"layer": "LABEL"}).set_placement((0, -1.0))
    doc.saveas(path)


def placed_shape(pl):
    shape = pl.item.shape
    if pl.rotated:
        shape = affinity.rotate(shape, 90, origin=(0, 0))
    x0, y0, _, _ = shape.bounds
    return affinity.translate(shape, pl.x - x0, pl.y - y0)


def write_sheet_dxf(sheet, idx, p, path):
    doc = _new_doc()
    msp = doc.modelspace()
    msp.add_lwpolyline([(0, 0), (p.cnc_bed, 0), (p.cnc_bed, p.cnc_bed), (0, p.cnc_bed)], close=True,
                       dxfattribs={"layer": "SHEET"})
    for pl in sheet:
        s = placed_shape(pl)
        _add_shape(msp, s)
        c = s.representative_point()
        msp.add_text(pl.item.name, height=0.5, dxfattribs={"layer": "LABEL"}).set_placement((c.x, c.y))
    doc.saveas(path)


# ---------------------------------------------------------------------------
# Nesting + cut list
# ---------------------------------------------------------------------------
def nest_variant(v):
    p = v.params
    items, sizes = [], []
    for part in v.cut_parts:
        for _ in part.placements:
            items.append(part)
            sizes.append(part.size)
    return nest(items, sizes, p.cnc_bed, p.sheet_margin, p.part_spacing)


def draw_sheets(v, sheets, path):
    p = v.params
    n = len(sheets)
    cols = min(n, 3)
    rows = math.ceil(n / cols)
    fig, axes = plt.subplots(rows, cols, figsize=(4.2 * cols, 4.4 * rows), squeeze=False)
    for k, ax in enumerate(axes.flat):
        ax.set_axis_off()
        if k >= n:
            continue
        ax.set_aspect("equal")
        ax.add_patch(MplPolygon([(0, 0), (p.cnc_bed, 0), (p.cnc_bed, p.cnc_bed), (0, p.cnc_bed)],
                                closed=True, fc="#f3ece0", ec="#888", lw=1))
        for pl in sheets[k]:
            s = placed_shape(pl)
            ax.add_patch(PathPatch(_path(s), fc=pl.item.color, ec="#5a4a32", lw=0.6))
            c = s.representative_point()
            ax.text(c.x, c.y, pl.item.name, ha="center", va="center", fontsize=6.5, color="#333")
        ax.set_xlim(-1, p.cnc_bed + 1)
        ax.set_ylim(-1, p.cnc_bed + 1)
        ax.set_title(f"4'x4' panel {k + 1}", fontsize=10)
    fig.suptitle(f"{v.title}: nesting on {fmt(p.cnc_bed)} square panels", fontsize=11)
    fig.tight_layout()
    fig.savefig(path, dpi=130)
    plt.close(fig)


def cut_list_md(v, sheets):
    p = v.params
    lines = [f"### {v.title}", "", v.summary, "",
             "| Part | Qty | Size (W x H) | Notes |", "|---|---:|---|---|"]
    for part in v.cut_parts:
        w, h = part.size
        lines.append(f"| {part.name} | {part.qty} | {fmt(w)} x {fmt(h)} | {part.note} |")
    n = len(sheets)
    h = v.heights
    lines += ["",
              f"- **Panels:** {n} pieces of 4'x4' ({math.ceil(n / 2)} x 4'x8' sheet(s) of "
              f"{fmt(p.T)} plywood, each cut in half)",
              f"- **Heights from floor:** mattress top {fmt(h['mattress_top'])}, "
              f"rail top {fmt(h['rail_top'])}, box lids {fmt(h['box_top'])}, "
              f"exit sill {fmt(h['sill_top'])}",
              f"- **Exit opening:** {fmt(h['exit'][0])} to {fmt(h['exit'][1])} from the head wall; "
              f"panel halves join at {fmt(h['joint_x'])}",
              f"- **Head/foot boxes:** {fmt(p.box_width)} wide outside, "
              f"{fmt(p.box_width - 2 * p.T)} inside, {fmt(p.depth)} deep", ""]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------
def _path(shape):
    verts, codes = [], []
    shape = orient(shape)
    for ring in [shape.exterior, *shape.interiors]:
        c = list(ring.coords)
        verts += c
        codes += [Path.MOVETO] + [Path.LINETO] * (len(c) - 2) + [Path.CLOSEPOLY]
    return Path(verts, codes)


def _shade(color, normal, light):
    rgb = np.array(matplotlib.colors.to_rgb(color))
    k = 0.62 + 0.38 * max(0.0, float(np.dot(normal, light)))
    return tuple(np.clip(rgb * k, 0, 1))


def render_iso(v, path, view=(0.62, 1.0, -0.62)):
    p = v.params
    d = np.asarray(view, float)
    d /= np.linalg.norm(d)
    right = np.cross(d, (0, 0, 1))
    right /= np.linalg.norm(right)
    up = np.cross(right, d)
    light = np.array([-0.3, -0.8, 0.9])
    light /= np.linalg.norm(light)

    def proj(pts):
        return np.c_[pts @ right, pts @ up]

    L, D, T = p.nook_width, p.depth, p.T
    back = np.array([[0, T + D, 0], [L, T + D, 0], [L, T + D, 30], [0, T + D, 30]], float)
    floor = np.array([[-6, -10, 0], [L + 6, -10, 0], [L + 6, T + D, 0], [-6, T + D, 0]], float)
    faces = [([proj(back)], "#ece7df", "#ece7df"), ([proj(floor)], "#d8cfc2", "#d8cfc2")]

    instances = []  # (aabb_min, aabb_max, depth, faces)
    for part in v.parts:
        thick = getattr(part, "render_thickness", T)
        shape = orient(part.shape)
        rings = [np.asarray(shape.exterior.coords)] + [np.asarray(r.coords) for r in shape.interiors]
        for pl in part.placements:
            n = np.asarray(pl.n, float)
            u, vv = np.asarray(pl.u, float), np.asarray(pl.v, float)
            edge_faces, flat_faces = [], []
            for r in rings:
                for a, b in zip(r[:-1], r[1:]):
                    t = b - a
                    nu = np.array([t[1], -t[0]])
                    if not nu.any():
                        continue
                    normal = nu[0] * u + nu[1] * vv
                    normal /= np.linalg.norm(normal)
                    if np.dot(normal, d) >= 0:
                        continue
                    quad = np.vstack([pl.to_world(np.array([a, b]), 0), pl.to_world(np.array([b, a]), thick)])
                    c = _shade(part.color, normal, light)
                    edge_faces.append((float(np.mean(quad @ d)), [proj(quad)], c, c))
            for w, normal in ((0.0, -n), (thick, n)):
                if np.dot(normal, d) < 0:
                    world = [pl.to_world(r, w) for r in rings]
                    flat_faces.append(([proj(r) for r in world], _shade(part.color, normal, light), "#6b5a40"))
            edge_faces.sort(key=lambda f: -f[0])
            corners = np.vstack([pl.to_world(rings[0], 0), pl.to_world(rings[0], thick)])
            lo, hi = corners.min(axis=0), corners.max(axis=0)
            instances.append((lo, hi, float(((lo + hi) / 2) @ d),
                              [f[1:] for f in edge_faces] + flat_faces))

    for i in _painter_order(instances, d):
        faces += instances[i][3]

    fig, ax = plt.subplots(figsize=(11, 7.5))
    ax.set_aspect("equal")
    ax.set_axis_off()
    for rings2d, color, edge in faces:
        verts, codes = [], []
        for r in rings2d:
            r = list(map(tuple, r))
            if r[0] != r[-1]:
                r.append(r[0])
            verts += r
            codes += [Path.MOVETO] + [Path.LINETO] * (len(r) - 2) + [Path.CLOSEPOLY]
        lw = 0.6 if edge != color else 0.4
        ax.add_patch(PathPatch(Path(verts, codes), fc=color, ec=edge, lw=lw, joinstyle="round"))
    ax.autoscale_view()
    ax.set_title(v.title, fontsize=14)
    fig.tight_layout()
    fig.savefig(path, dpi=140)
    plt.close(fig)


def _painter_order(instances, d, eps=1e-6):
    """Back-to-front order for axis-aligned slabs using separating axes."""
    n = len(instances)
    right = np.cross(d, (0, 0, 1))
    right /= np.linalg.norm(right)
    up = np.cross(right, d)
    screen = []
    for lo, hi, *_ in instances:
        pts = np.array([[x, y, z] for x in (lo[0], hi[0]) for y in (lo[1], hi[1]) for z in (lo[2], hi[2])])
        sx, sy = pts @ right, pts @ up
        screen.append((sx.min(), sx.max(), sy.min(), sy.max()))
    before = [set() for _ in range(n)]  # before[j] = instances that must be drawn before j
    for i in range(n):
        for j in range(i + 1, n):
            a, b = screen[i], screen[j]
            if a[1] <= b[0] or b[1] <= a[0] or a[3] <= b[2] or b[3] <= a[2]:
                continue  # no overlap on screen, order doesn't matter
            lo_i, hi_i, lo_j, hi_j = instances[i][0], instances[i][1], instances[j][0], instances[j][1]
            fars = set()
            for k in range(3):
                if abs(d[k]) < 1e-9:
                    continue
                if hi_i[k] <= lo_j[k] + eps:
                    fars.add(j if d[k] > 0 else i)
                elif hi_j[k] <= lo_i[k] + eps:
                    fars.add(i if d[k] > 0 else j)
            # Any separating plane gives a valid order; if two disagree the
            # slabs can't overlap on screen, so no constraint is needed.
            if len(fars) == 1:
                far = fars.pop()
                before[j if far == i else i].add(far)
    order, done = [], set()
    while len(order) < n:
        ready = [k for k in range(n) if k not in done and before[k] <= done]
        if not ready:  # cycle: take whatever is closest to unblocked
            rest = [k for k in range(n) if k not in done]
            fewest = min(len(before[k] - done) for k in rest)
            ready = [k for k in rest if len(before[k] - done) == fewest]
        k = max(ready, key=lambda q: instances[q][2])
        order.append(k)
        done.add(k)
    return order


def render_front(v, path):
    """Front elevation with key dimensions."""
    p = v.params
    h = v.heights
    fig, ax = plt.subplots(figsize=(11, 5.2))
    ax.set_aspect("equal")
    ax.set_axis_off()
    L = p.nook_width
    # mattress (hidden behind the panel) dashed
    mz = h["mattress_top"] - p.mattress_thickness
    mx = p.box_width + p.mattress_clearance
    ax.add_patch(MplPolygon([(mx, mz), (mx + p.mattress_length, mz), (mx + p.mattress_length, mz + p.mattress_thickness),
                             (mx, mz + p.mattress_thickness)], closed=True, fc="#f4f1ea", ec="#999", ls="--", lw=0.8))
    for part in v.parts:
        if part.material != "plywood":
            continue
        for pl in part.placements:
            if tuple(pl.n) != (0, -1, 0) or pl.origin[1] > p.T + 1e-6:
                continue  # only parts lying in the front plane
            s = affinity.translate(part.shape, pl.origin[0], pl.origin[2])
            ax.add_patch(PathPatch(_path(s), fc=part.color, ec="#5a4a32", lw=0.8))
    # parts seen edge-on at the front face (e.g. the centre divider)
    for part in v.parts:
        if part.material != "plywood":
            continue
        r = np.asarray(part.shape.exterior.coords)
        for pl in part.placements:
            if tuple(pl.n) == (0, -1, 0):
                continue
            c = np.vstack([pl.to_world(r, 0), pl.to_world(r, p.T)])
            lo, hi = c.min(axis=0), c.max(axis=0)
            if lo[1] <= 1e-6:
                ax.add_patch(MplPolygon([(lo[0], lo[2]), (hi[0], lo[2]), (hi[0], hi[2]), (lo[0], hi[2])],
                                        closed=True, fc=part.color, ec="#5a4a32", lw=0.8))
    # box lids as hidden lines
    for x0 in (0, L - p.box_width):
        ax.plot([x0, x0 + p.box_width], [h["box_top"]] * 2, color="#7a6a50", ls="--", lw=0.8)

    def dim_h(x0, x1, y, text):
        ax.annotate("", (x0, y), (x1, y), arrowprops=dict(arrowstyle="<->", lw=0.7, color="#333"))
        ax.text((x0 + x1) / 2, y + 0.4, text, ha="center", va="bottom", fontsize=8)

    def dim_v(x, y0, y1, text):
        ax.annotate("", (x, y0), (x, y1), arrowprops=dict(arrowstyle="<->", lw=0.7, color="#333"))
        ax.text(x + 0.5, (y0 + y1) / 2, text, ha="left", va="center", fontsize=8)

    top = h["rail_top"]
    dim_h(0, L, top + 3.5, f"nook {fmt(L)}")
    dim_h(0, p.box_width, top + 1.2, fmt(p.box_width))
    dim_h(L - p.box_width, L, top + 1.2, fmt(p.box_width))
    dim_h(h["exit"][0], h["exit"][1], h["sill_top"] + 2.0, f"exit {fmt(p.exit_width)}")
    dim_v(L + 1.5, 0, top, f"rail {fmt(top)}")
    dim_v(L + 7.5, 0, h["mattress_top"], f"mattress top {fmt(h['mattress_top'])}")
    ax.axvline(h["joint_x"], color="#c0392b", lw=0.6, ls=":")
    ax.text(h["joint_x"], -1.2, "panel joint", ha="center", va="top", fontsize=7.5, color="#c0392b")
    ax.plot([-2, L + 2], [0, 0], color="#555", lw=1)
    ax.set_xlim(-3, L + 18)
    ax.set_ylim(-3, top + 6)
    ax.set_title(f"{v.title}: front view", fontsize=12)
    fig.tight_layout()
    fig.savefig(path, dpi=130)
    plt.close(fig)


# ---------------------------------------------------------------------------
def write_variant(v, outdir):
    os.makedirs(os.path.join(outdir, "parts"), exist_ok=True)
    os.makedirs(os.path.join(outdir, "sheets"), exist_ok=True)
    for part in v.cut_parts:
        fname = part.name.lower().replace(" ", "_").replace("(", "").replace(")", "")
        write_part_dxf(part, os.path.join(outdir, "parts", f"{fname}.dxf"))
    sheets = nest_variant(v)
    for i, sheet in enumerate(sheets):
        write_sheet_dxf(sheet, i, v.params, os.path.join(outdir, "sheets", f"panel_{i + 1}.dxf"))
    draw_sheets(v, sheets, os.path.join(outdir, "nesting.png"))
    render_iso(v, os.path.join(outdir, "preview.png"))
    render_front(v, os.path.join(outdir, "front.png"))
    md = cut_list_md(v, sheets)
    with open(os.path.join(outdir, "cut_list.md"), "w") as f:
        f.write(md)
    return md
