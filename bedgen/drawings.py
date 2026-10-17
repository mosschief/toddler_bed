"""Shop drawings for one variant: part drawings, plan, section, exploded box,
and a multi-page PDF that bundles them with the cut list and assembly notes."""
import copy
import os
import textwrap

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.backends.backend_pdf import PdfPages
from matplotlib.patches import PathPatch, Polygon as MplPolygon
from shapely import affinity

from .output import _path, fmt, render_iso
from .parts import Part, Placement, rect, round_convex, slot_with_dogbones

INK = "#333"


def _dim(ax, p0, p1, text, offset, fs=7.5):
    """Linear dimension between p0 and p1, drawn `offset` away (perpendicular)."""
    p0, p1 = np.asarray(p0, float), np.asarray(p1, float)
    d = p1 - p0
    n = np.array([-d[1], d[0]]) / (np.linalg.norm(d) or 1)
    a, b = p0 + n * offset, p1 + n * offset
    for p, q in ((p0, a), (p1, b)):
        ax.plot(*zip(p + n * 0.15 * np.sign(offset), q + n * 0.25 * np.sign(offset)), color="#888", lw=0.4)
    ax.annotate("", a, b, arrowprops=dict(arrowstyle="<->", lw=0.6, color=INK, shrinkA=0, shrinkB=0))
    m = (a + b) / 2 + n * 0.35 * np.sign(offset)
    rot = np.degrees(np.arctan2(d[1], d[0]))
    if rot > 90 or rot < -90:
        rot += 180
    ax.text(*m, text, ha="center", va="center", rotation=rot, fontsize=fs, color=INK,
            bbox=dict(fc="white", ec="none", pad=0.4))


# ---------------------------------------------------------------------------
def part_drawings(v, path):
    parts = v.cut_parts
    cols = 3
    rows = int(np.ceil(len(parts) / cols))
    fig, axes = plt.subplots(rows, cols, figsize=(14, 4.2 * rows), squeeze=False)
    for ax in axes.flat:
        ax.set_axis_off()
    for ax, part in zip(axes.flat, parts):
        ax.set_aspect("equal")
        s = part.shape
        w, h = part.size
        ax.add_patch(PathPatch(_path(s), fc=part.color, ec="#5a4a32", lw=0.8))
        for g, depth, label in part.pockets:
            ax.add_patch(PathPatch(_path(g), fc="#b89b6a", ec="#5a4a32", lw=0.5, ls="--"))
        if part.pockets:
            kinds = sorted({(label, d) for _, d, label in part.pockets})
            ax.text(w / 2, h + max(w, h) * 0.04, "back face, dashed: " +
                    ", ".join(f"{lbl}s {fmt(d)} deep" for lbl, d in kinds), ha="center", fontsize=7, color="#555")
        _dim(ax, (0, 0), (w, 0), fmt(w), -max(w, h) * 0.07)
        _dim(ax, (w, 0), (w, h), fmt(h), -max(w, h) * 0.07)
        # hole/slot sizes, one representative of each size
        seen = set()
        for ring in s.interiors:
            x0, y0, x1, y1 = ring.bounds
            key = (round(x1 - x0, 3), round(y1 - y0, 3))
            if key in seen:
                continue
            seen.add(key)
            ax.annotate(f"{fmt(x1 - x0)} x {fmt(y1 - y0)}", ((x0 + x1) / 2, y1),
                        xytext=((x0 + x1) / 2, y1 + max(w, h) * 0.05), fontsize=6.5, ha="center",
                        arrowprops=dict(arrowstyle="-", lw=0.4, color="#666"), color="#555")
        pad = max(w, h) * 0.15
        ax.set_xlim(-pad * 0.4, w + pad)
        ax.set_ylim(-pad, h + pad)
        title = f"{part.name}  (qty {part.qty})"
        ax.set_title(title + (f"\n{part.note}" if part.note else ""), fontsize=9.5)
    fig.suptitle(f"{v.title}: part drawings (inches, {fmt(v.params.T)} plywood)", fontsize=13)
    fig.tight_layout(rect=(0, 0, 1, 0.96))
    fig.savefig(path, dpi=130)
    plt.close(fig)


def plan_and_section(v, path):
    p, h = v.params, v.heights
    T, D, L, bw, fbw = p.T, p.depth, p.nook_width, p.head_box_width, p.foot_box_width
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(15, 6), gridspec_kw=dict(width_ratios=[2.3, 1]))

    # ---- plan (looking down; front of bed at the bottom)
    ax1.set_aspect("equal")
    ax1.set_axis_off()
    ax1.add_patch(MplPolygon([(0, T + D), (L, T + D), (L, T + D + 1), (0, T + D + 1)], fc="#bbb", ec="none"))
    for x in (0, L):
        ax1.add_patch(MplPolygon([(x - (1 if x == 0 else 0), -2), (x + (0 if x == 0 else 1), -2),
                                  (x + (0 if x == 0 else 1), T + D + 1), (x - (1 if x == 0 else 0), T + D + 1)],
                                 fc="#bbb", ec="none"))
    mx = bw + p.mattress_clearance
    ax1.add_patch(MplPolygon([(mx, T + p.mattress_clearance / 2), (mx + p.mattress_length, T + p.mattress_clearance / 2),
                              (mx + p.mattress_length, T + p.mattress_clearance / 2 + p.mattress_width),
                              (mx, T + p.mattress_clearance / 2 + p.mattress_width)], fc="#f4f1ea", ec="#999", ls="--"))
    ax1.text(L / 2, T + D / 2, f"mattress {fmt(p.mattress_length)} x {fmt(p.mattress_width)}", ha="center",
             fontsize=9, color="#777")
    for part in v.cut_parts:
        r = np.asarray(part.shape.exterior.coords)
        for pl in part.placements:
            c = np.vstack([pl.to_world(r, 0), pl.to_world(r, T)])
            lo, hi = c.min(axis=0), c.max(axis=0)
            if hi[2] - lo[2] < T + 1e-6 and part.name.startswith("Box"):
                continue  # horizontal box parts hide the joinery; show the walls
            ax1.add_patch(MplPolygon([(lo[0], lo[1]), (hi[0], lo[1]), (hi[0], hi[1]), (lo[0], hi[1])],
                                     fc=part.color, ec="#5a4a32", lw=0.6))
    _dim(ax1, (0, 0), (L, 0), f"nook {fmt(L)}", -4)
    for x0, w, _ in p.box_spans:
        _dim(ax1, (x0, T + D), (x0 + w, T + D), fmt(w), 2.5)
    _dim(ax1, (bw, T + D), (L - fbw, T + D), f"mattress opening {fmt(L - bw - fbw)}", 2.5)
    _dim(ax1, (L, 0), (L, T + D), f"overall depth {fmt(T + D)}", -3)
    ex0, ex1 = h["exit"]
    _dim(ax1, (ex0, 0), (ex1, 0), f"exit {fmt(ex1 - ex0)}", -1.5)
    ax1.set_xlim(-4, L + 8)
    ax1.set_ylim(-7, T + D + 6)
    ax1.set_title("Plan (front of bed at the bottom)", fontsize=11)

    # ---- section through the head box, looking from the mattress toward the head wall
    ax2.set_aspect("equal")
    ax2.set_axis_off()
    side = next(pt for pt in v.cut_parts if pt.name == "Box side (mattress)")
    ax2.add_patch(PathPatch(_path(affinity.translate(side.shape, T, 0)), fc=side.color, ec="#5a4a32", lw=0.8))
    front = h["rail_top"]
    ax2.add_patch(MplPolygon([(0, 0), (T, 0), (T, front), (0, front)], fc="#e3cfa8", ec="#5a4a32", lw=0.8))
    lid = next(pt for pt in v.cut_parts if pt.name == "Box lid")
    side_h = h["box_top"] - T
    lid_d = lid.size[1]
    ax2.add_patch(MplPolygon([(T + p.lid_gap, side_h), (T + p.lid_gap + lid_d, side_h),
                              (T + p.lid_gap + lid_d, side_h + T), (T + p.lid_gap, side_h + T)],
                             fc=lid.color, ec="#5a4a32", lw=0.8))
    ax2.text(T + D / 2, max(side_h + T, front) + 1.6, "one-piece lid, hinged along the wall side (behind)", ha="center",
             fontsize=7, color="#c0392b")
    ax2.text(T + D / 2, side_h - p.hand_notch[1] - 0.6, "hand cut-out", ha="center", fontsize=7, color="#555")
    ax2.add_patch(MplPolygon([(T + D, -1), (T + D + 1, -1), (T + D + 1, front + 3), (T + D, front + 3)],
                             fc="#bbb", ec="none"))
    ax2.plot([-2, T + D + 1], [0, 0], color="#555", lw=1)
    _dim(ax2, (T + D + 1, 0), (T + D + 1, front), f"rail {fmt(front)}", -3.2)
    _dim(ax2, (T + D + 1, 0), (T + D + 1, h["box_top"]), f"lid {fmt(h['box_top'])}", -1.4)
    _dim(ax2, (0, 0), (0, h["mattress_top"]), f"mattress {fmt(h['mattress_top'])}", 1.6)
    _dim(ax2, (0, 0), (T + D, 0), f"{fmt(T + D)}", -1.8)
    ax2.text(T + 0.3, front + 0.4, "guard panel", fontsize=7, color="#555")
    ax2.text(T + D - 0.2, front + 1.2, "wall", fontsize=7, color="#555", ha="right")
    ax2.set_xlim(-6, T + D + 8)
    ax2.set_ylim(-4, front + 4)
    ax2.set_title("Box seen from the mattress", fontsize=11)
    fig.tight_layout()
    fig.savefig(path, dpi=130)
    plt.close(fig)


def exploded_box(v, path):
    """First box pulled apart so the tab-and-slot joints are visible."""
    p = v.params
    x0, bw, sgn = p.box_spans[0]
    offsets = {"Box side (wall)": (-5, 0, 0), "Box side (mattress)": (5, 0, 0), "Box back": (0, 6, 0),
               "Box front": (0, -8, 0), "Box floor": (0, -3, 0), "Box lid": (0, 0, 6)}
    parts = []
    for part in v.cut_parts:
        if part.name not in offsets:
            continue
        q = copy.copy(part)
        q.placements = []
        for pl in part.placements:
            if not x0 - 0.01 <= pl.origin[0] <= x0 + bw + 0.01:
                continue  # one box only
            off = np.array(offsets[part.name], float) * (sgn, 1, 1) - (x0, 0, 0)  # move it to x = 0
            q.placements.append(Placement(tuple(np.add(pl.origin, off)), pl.u, pl.v, pl.n))
        parts.append(q)
    name = "Head box" if sgn > 0 else "Foot box"
    _render_parts(v, parts, path, f"{name}, exploded (tabs pass through the sides)", bw)


def dogbone_detail(v, path):
    """Close-up of a groove end, with and without dogbones, plus the full groove."""
    from matplotlib.patches import Circle
    p = v.params
    T, r = p.T, p.bit_diameter / 2
    wood, ink, red = "#e3cfa8", "#5a4a32", "#c0392b"
    fig, axes = plt.subplots(1, 3, figsize=(15, 5.6), gridspec_kw=dict(width_ratios=[1, 1, 0.8]))
    L = 1.6  # length of groove shown

    def groove_view(ax, groove, title, show_bad):
        ax.set_aspect("equal")
        ax.set_axis_off()
        panel = rect(-0.9, -0.2, T + 0.9, L + 0.7).difference(groove)
        ax.add_patch(PathPatch(_path(panel), fc=wood, ec=ink, lw=1))
        # the box side's square end, dropped into the groove
        ax.add_patch(MplPolygon([(0, -0.2), (T, -0.2), (T, L), (0, L)], closed=True, fc="none",
                                ec="#1f6feb", lw=1.6, ls="--"))
        ax.text(T / 2, L * 0.45, "box side\n(square end)", ha="center", fontsize=8, color="#1f6feb")
        if show_bad:
            clash = rect(0, 0, T, L).difference(groove)
            for g in getattr(clash, "geoms", [clash]):
                ax.add_patch(PathPatch(_path(g), fc=red, ec=red, lw=0.5))
            ax.annotate("rounded corners left by the bit:\nthe square side hits here", (T, L), (T + 0.25, L + 0.45),
                        fontsize=8, color=red, arrowprops=dict(arrowstyle="-", color=red, lw=0.8))
        else:
            ax.add_patch(Circle((T - r / 2 ** 0.5, L - r / 2 ** 0.5), r + 0.01, fc="none", ec=red, lw=0.8, ls=":"))
            ax.annotate(f"dogbone: the {fmt(p.bit_diameter)} bit plunges\ninto each corner, so the\n"
                        "square side seats fully", (T, L), (T + 0.25, L + 0.4), fontsize=8, color=red,
                        arrowprops=dict(arrowstyle="-", color=red, lw=0.8))
        _dim(ax, (0, -0.2), (T, -0.2), f"{fmt(T)} groove", -0.25, fs=7)
        ax.set_xlim(-1.0, T + 1.9)
        ax.set_ylim(-0.75, L + 1.0)
        ax.set_title(title, fontsize=10)

    plain = round_convex(rect(0, -1, T, L), r)
    groove_view(axes[0], plain, "Without dogbones (red = wood that blocks the square corner)", True)
    groove_view(axes[1], slot_with_dogbones(0, -1, T, L, p.bit_diameter), "With dogbones", False)

    # full groove on the back of the front panel, at a box side
    ax = axes[2]
    ax.set_aspect("equal")
    ax.set_axis_off()
    h = v.heights
    side_h = h["box_top"] - T
    panel = rect(-4, 0, T + 4, h["rail_top"]).difference(slot_with_dogbones(0, -1, T, side_h, p.bit_diameter))
    ax.add_patch(PathPatch(_path(panel), fc=wood, ec=ink, lw=1))
    ax.text(T / 2, side_h / 2, "groove\n3/8\" deep", ha="center", va="center", rotation=90, fontsize=8)
    ax.annotate("dogbones at the top", (T, side_h), (T + 1.2, side_h + 1.2), fontsize=8, color=red,
                arrowprops=dict(arrowstyle="-", color=red, lw=0.8))
    ax.annotate("open at the bottom edge:\nno corner to clear", (T, 0.2), (T + 1.2, 2.0), fontsize=8, color=red,
                arrowprops=dict(arrowstyle="-", color=red, lw=0.8))
    _dim(ax, (-4, 0), (-4, side_h), fmt(side_h), 0.8, fs=7)
    ax.set_xlim(-6, T + 6)
    ax.set_ylim(-1, h["rail_top"] + 1)
    ax.set_title("Back of the front panel, one groove", fontsize=10)

    fig.suptitle("Dogbones: how a square part fits a CNC-cut groove (looking at the back of the front panel)",
                 fontsize=12)
    fig.tight_layout(rect=(0, 0, 1, 0.94))
    fig.savefig(path, dpi=140)
    plt.close(fig)


def _render_parts(v, parts, path, title, width):
    vv = copy.copy(v)
    vv.params = copy.copy(v.params)
    vv.params.nook_width = width  # shrink the backdrop to the box
    render_iso(vv, path, view=(0.9, 1.0, -0.7), parts=parts, title=title)


# ---------------------------------------------------------------------------
ASSEMBLY = """
1. Cut all parts (sheets/panel_*.dxf). The two front-panel pieces are mirrored in the files: cut them
   BACK FACE UP so the POCKET layers (box-side grooves 3/8" deep, insert holes 1/2" deep) land on the
   back. Profile CUT_INSIDE before CUT_OUTSIDE, use tabs/onion skin on small parts, and dry-fit the
   puzzle joint and one groove on scrap first; adjust knob_clearance / tab_clearance if needed.
2. Ease every exposed edge with a 1/4" roundover (rail top, slots, exit opening, lid edges and the
   hand cut-outs). Leave joinery edges and faces that meet the wall square.
3. Boxes: glue the front, back and floor tabs into one side, add the second side, clamp square.
   Tabs are flush with the outside faces. Pre-drill and screw (1-1/4") through the side into each
   tab. The front wall's slots sit just behind the 3/8" of side that goes into the panel groove,
   so handle the sides gently until the box is glued up.
4. Check that the front wall's face is flush with the sides' front shoulders (3/8" back from their
   front edges), so it sits tight against the panel when the sides are in their grooves.
5. Glue the two front-panel halves together on a flat surface (puzzle joint), let it cure. Install
   the {inserts} threaded inserts in the insert holes on the back.
6. Set both boxes in the nook, tight to the side walls. Shim level, then screw through each box back
   into a stud (2-1/2" screws, 2 per box). The 3/4" behind the back lets you scribe the sides.
7. Lift the front panel on: each box side drops into its groove (open at the bottom, dog-boned at
   the top). Reach in through each lid and bolt the box fronts to the inserts (1/4-20 x 1-1/4" bolts
   with washers). No glue here, so the front panel can come off later.
8. Hang each lid with a piano hinge along its long wall-side edge (on the top outside edge of the
   wall-side panel), so it opens toward the mattress and stands up against the wall. Fit a
   soft-close lid stay so a lid can't drop on fingers. Lift it at the hand cut-out.
9. Finish (water-based poly or hardwax oil rated toy-safe), let it cure fully, then add the mattress.
""".strip()

HARDWARE = """
- Wood glue (PVA)
- 1-1/4" wood screws x {box_screws} (box joinery{foot_screws})
- 1/4-20 threaded inserts for wood x {inserts}, no longer than 1/2" (front panel; pilot 3/8", set p.insert_hole to match)
- 1/4-20 x 1-1/4" bolts + washers x {inserts} (box fronts{foot_bolts} to front panel)
- 2-1/2" screws x {stud_screws} into studs ({stud_what})
- Piano hinge 1-1/2" open width, {boxes} x 24" length(s) (1 per lid)
- Soft-close lid stays x {boxes} (light-duty toy-box type)
- Shims as needed
""".strip()


def assembly_text(p):
    if not p.single_box:
        return ASSEMBLY.format(inserts=8)
    text = ASSEMBLY.format(inserts=6)
    box, end = p.boxes, p.liner_end
    text = text.replace("3. Boxes: glue", f"3. {box.capitalize()} box: glue")
    text = text.replace("""   front edges), so it sits tight against the panel when the sides are in their grooves.""",
                        f"""   front edges), so it sits tight against the panel when the sides are in their grooves.
   Glue + screw (2 x 1-1/4") the {end} block to the mattress-side face of the {end} wall liner, above
   the mattress, its face 3/8" back from the liner's front edge in the same way.""")
    text = text.replace("""6. Set both boxes in the nook, tight to the side walls. Shim level, then screw through each box back
   into a stud (2-1/2" screws, 2 per box). The 3/4" behind the back lets you scribe the sides.""",
                        f"""6. Set the {box} box in the nook, tight to the {box} wall. Shim level, then screw through the box
   back into a stud (2-1/2" screws, 2). Screw the {end} wall liner to the {end} wall studs (3 screws),
   its front edge 3/8" proud of where the panel back will be. Scribe both to the walls as needed.""")
    text = text.replace("each box side drops into its groove", f"the box sides and the {end} liner drop into their grooves")
    text = text.replace("Reach in through each lid and bolt", f"Reach in through the lid (and over the mattress at the {end}) and bolt")
    text = text.replace("bolt the box fronts to the inserts", f"bolt the box front and the {end} block to the inserts")
    return text.replace("Hang each lid", "Hang the lid")


def hardware_text(p):
    if p.single_box:
        end = p.liner_end
        return HARDWARE.format(box_screws=14, foot_screws=f" + {end} block", foot_bolts=f" and {end} block",
                               inserts=6, stud_screws=5, stud_what=f"box back and {end} liner", boxes=1)
    return HARDWARE.format(box_screws=24, foot_screws="", foot_bolts="", inserts=8, stud_screws=4,
                           stud_what="box backs", boxes=2)


def _text_page(pdf, title, blocks):
    fig = plt.figure(figsize=(11, 8.5))
    fig.text(0.06, 0.94, title, fontsize=16, weight="bold")
    y = 0.88
    for head, body in blocks:
        fig.text(0.06, y, head, fontsize=12, weight="bold")
        y -= 0.035
        for line in body.splitlines():
            for wrapped in textwrap.wrap(line, 118, subsequent_indent="   ") or [""]:
                fig.text(0.06, y, wrapped, fontsize=9, family="monospace")
                y -= 0.024
        y -= 0.02
    pdf.savefig(fig)
    plt.close(fig)


def _image_page(pdf, img_path):
    img = plt.imread(img_path)
    fig = plt.figure(figsize=(11, 8.5))
    ax = fig.add_axes([0.02, 0.02, 0.96, 0.96])
    ax.imshow(img)
    ax.set_axis_off()
    pdf.savefig(fig)
    plt.close(fig)


def build_package(v, outdir, cut_list_md):
    files = {
        "part_drawings": os.path.join(outdir, "part_drawings.png"),
        "plan_section": os.path.join(outdir, "plan_section.png"),
        "exploded_box": os.path.join(outdir, "exploded_box.png"),
        "dogbone_detail": os.path.join(outdir, "dogbone_detail.png"),
    }
    dogbone_detail(v, files["dogbone_detail"])
    part_drawings(v, files["part_drawings"])
    plan_and_section(v, files["plan_section"])
    exploded_box(v, files["exploded_box"])

    rows = [ln for ln in cut_list_md.splitlines() if ln.startswith("|") and not ln.startswith("|---")]
    table = "\n".join(
        f"{c[0]:<24}{c[1]:>4}   {c[2]:<26}{c[3]}"
        for c in ([x.strip() for x in r.strip("|").split("|")] for r in rows))
    facts = "\n".join(ln[2:].replace("**", "") for ln in cut_list_md.splitlines() if ln.startswith("- "))
    with PdfPages(os.path.join(outdir, "drawings.pdf")) as pdf:
        for name in ("preview.png", "front.png"):
            _image_page(pdf, os.path.join(outdir, name))
        for key in ("plan_section", "exploded_box", "dogbone_detail", "part_drawings"):
            _image_page(pdf, files[key])
        _image_page(pdf, os.path.join(outdir, "nesting.png"))
        _text_page(pdf, f"{v.title}: cut list, hardware, assembly",
                   [("Cut list", table), ("Key dimensions", facts), ("Hardware", hardware_text(v.params)),
                    ("Assembly", assembly_text(v.params))])
    return files
