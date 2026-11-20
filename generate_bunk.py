#!/usr/bin/env python3
"""Generate the treehouse bunk bed: DXF parts, nested 4'x4' sheets, renders,
front elevation, side section, cut list, STEP model and a drawings PDF.

    python3 generate_bunk.py
    python3 generate_bunk.py --set deck_under=36 --set rail_top=46.75
"""
import argparse
import dataclasses
import math
import os

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.backends.backend_pdf import PdfPages  # noqa: E402
from matplotlib.patches import PathPatch, Rectangle  # noqa: E402
from shapely import affinity  # noqa: E402

from bedgen.bunk import BunkParams, build_bunks  # noqa: E402
from bedgen.drawings import _image_page, _text_page, part_drawings  # noqa: E402
from bedgen.output import (_path, draw_sheets, fmt, nest_variant, render_iso, write_part_dxf,  # noqa: E402
                           write_sheet_dxf)


def front_elevation(v, path):
    p, h = v.params, v.heights
    fig, ax = plt.subplots(figsize=(11, 8.2))
    ax.set_aspect("equal")
    ax.set_axis_off()
    L, H = p.nook_width, p.rail_top
    for name, z in (("Lower mattress", 0.0), ("Upper mattress", p.deck_top)):
        ax.add_patch(Rectangle((p.T + p.mattress_clearance, z), p.mattress_length, p.mattress_thickness,
                               fc="#f4f1ea", ec="#999", ls="--", lw=0.8))
    ax.add_patch(Rectangle((p.T, p.deck_under), L - 2 * p.T, p.T, fc="none", ec="#7a6a50", ls="--", lw=0.8))
    for z in p.step_tops:
        ax.add_patch(Rectangle((p.tower_in[0], z - p.T), p.tower_in[1] - p.tower_in[0], p.T,
                               fc="none", ec="#7a6a50", ls="--", lw=0.8))
    for part in v.parts:
        if part.material == "plywood" and part.name.startswith("Front wall"):
            for pl in part.placements:
                s = affinity.translate(part.shape, pl.origin[0], pl.origin[2])
                ax.add_patch(PathPatch(_path(s), fc=part.color, ec="#5a4a32", lw=0.8))

    def dim_h(x0, x1, y, text):
        ax.annotate("", (x0, y), (x1, y), arrowprops=dict(arrowstyle="<->", lw=0.7, color="#333"))
        ax.text((x0 + x1) / 2, y + 0.4, text, ha="center", va="bottom", fontsize=8)

    def dim_v(x, y0, y1, text):
        ax.annotate("", (x, y0), (x, y1), arrowprops=dict(arrowstyle="<->", lw=0.7, color="#333"))
        ax.text(x + 0.5, (y0 + y1) / 2, text, ha="left", va="center", fontsize=8)

    dim_h(0, L, H + 3.0, f"nook {fmt(L)}")
    dim_h(*h["entry"], H + 0.8, f"climb-in {fmt(h['entry'][1] - h['entry'][0])}")
    dim_h(*h["door"], p.door_sill + 1.5, f"door {fmt(p.door_width)}")
    dim_v(L + 17, 0, H, f"rail top {fmt(H)}")
    dim_v(L + 8.5, p.deck_top + p.mattress_thickness, H, f"rail above mattress {fmt(h['rail_above_mattress'])}")
    dim_v(L + 8.5, 0, p.deck_top, f"deck top {fmt(p.deck_top)}")
    dim_v(-6.5, p.mattress_thickness, p.deck_under, f"sitting room\n{fmt(h['headroom'])}")
    dim_v(-6.5, 0, p.mattress_thickness, fmt(p.mattress_thickness))
    for z in p.step_tops:
        ax.text(L + 0.6, z, f"step {fmt(z)}", fontsize=7, va="center", color="#555")
    ax.axvline(h["joint_x"], color="#c0392b", lw=0.6, ls=":")
    ax.text(h["joint_x"], -1.2, "wall joint", ha="center", va="top", fontsize=7.5, color="#c0392b")
    ax.plot([-2, L + 2], [0, 0], color="#555", lw=1)
    ax.set_xlim(-12, L + 30)
    ax.set_ylim(-3, H + 6)
    ax.set_title(f"{v.title}: front view (dashed: mattresses, deck and step shelves behind)", fontsize=12)
    fig.tight_layout()
    fig.savefig(path, dpi=130)
    plt.close(fig)


def side_section(v, path):
    """Section across the bed (looking at the head wall), through the mattress zone and the tower."""
    p = v.params
    T, D = p.T, p.depth
    fig, axes = plt.subplots(1, 2, figsize=(11, 7.2))
    for ax, title, tower in zip(axes, ("Section through the beds", "Section through the foot tower"), (False, True)):
        ax.set_aspect("equal")
        ax.set_axis_off()
        ax.set_title(title, fontsize=11)
        ax.add_patch(Rectangle((0, 0), T, p.rail_top, fc="#e3cfa8", ec="#5a4a32"))  # front wall
        ax.add_patch(Rectangle((T + D, -1), 1.5, p.rail_top + 6, fc="#ddd", ec="#999", hatch="//"))
        ax.plot([-3, T + D + 1.5], [0, 0], color="#555")
        if not tower:
            for z in (0, p.deck_top):
                ax.add_patch(Rectangle((T + 0.125, z), p.mattress_width, p.mattress_thickness, fc="#f4f1ea", ec="#999"))
            ax.add_patch(Rectangle((T, p.deck_under), D, T, fc="#e3cfa8", ec="#5a4a32"))
            for y in (T, T + D - T):
                ax.add_patch(Rectangle((y, p.deck_under - p.ledger_height), T, p.ledger_height, fc="#cdb48a", ec="#5a4a32"))
            ax.text(T + D / 2, p.mattress_thickness / 2, "lower mattress", ha="center", va="center", fontsize=8)
            ax.text(T + D / 2, p.deck_top + p.mattress_thickness / 2, "upper mattress", ha="center", va="center", fontsize=8)
            ax.text(T + D / 2, p.deck_under - 4, "ledgers on front wall and back wall", ha="center", fontsize=7.5, color="#555")
        else:
            ax.add_patch(Rectangle((T, p.deck_under), D, T, fc="#e3cfa8", ec="#5a4a32"))
            for z in p.step_tops:
                ax.add_patch(Rectangle((T, z - T), D - 0.25, T, fc="#e3cfa8", ec="#5a4a32"))
                ax.annotate("toe hole", (0, z + p.step_hole_height / 2), (-9, z + p.step_hole_height / 2),
                            fontsize=7.5, va="center", arrowprops=dict(arrowstyle="->", lw=0.6))
                ax.add_patch(Rectangle((-0.05, z), T + 0.1, p.step_hole_height, fc="white", ec="none"))
            ax.add_patch(Rectangle((-0.05, p.deck_top), T + 0.1, p.rail_top, fc="white", ec="none"))
            ax.text(T + D / 2, p.deck_top + 2, "landing (climb-in gap above)", ha="center", fontsize=8)
        ax.set_xlim(-12, T + D + 4)
        ax.set_ylim(-3, p.rail_top + 6)
    fig.suptitle(f"{v.title}: sections (front at left, back wall hatched)", fontsize=12)
    fig.tight_layout()
    fig.savefig(path, dpi=130)
    plt.close(fig)


ASSEMBLY = """
1. Cut all parts. The front-wall pieces are mirrored in the files: cut them BACK FACE UP so the
   POCKET layer (rabbet + grooves, 3/8" deep) lands on the back. CUT_INSIDE before CUT_OUTSIDE.
   Dry-fit the puzzle joint, a shelf tab and the mattress-stop tabs on scrap first.
2. Round over every exposed edge 1/4" (rail top, slots, door, windows, toe holes, cubbies, climb-in
   gap). Toe holes and the climb-in gap get a generous roundover; small hands grab them.
3. Glue the two front-wall pieces (puzzle joint) flat on the floor; let cure. Glue + screw the two
   front ledgers to its back, top edge at the deck underside line. Their joint is offset from
   the wall joint so they splint it.
4. Tower: glue the shelf tabs into both tower sides, clamp square, screw through the sides into
   the tabs. Screw the head-wall liner to the head-wall studs and the tower's wall side to the
   foot-wall studs, both plumb, front edges 3/8" proud of where the front wall's back will be.
5. Screw the back-wall ledgers to the studs (2 screws per stud, top at the deck underside line) and
   the head ledger to the liner.
6. Stand the front wall up: the liner and both tower sides drop into the rabbet and grooves on its
   back. Glue them in. Check the ledger tops are level all round.
7. Lay the deck pieces on the ledgers and tower sides, seam batten glued + screwed underneath.
   Screw the deck down every 6" into every ledger and into the tower sides and liner below.
8. Tap the mattress stop's tabs into the deck mortises over the tower side; glue + screw up
   through the deck.
9. Finish (toy-safe), let cure, add both mattresses.
""".strip()

HARDWARE = """
- Wood glue (PVA)
- 1-1/4" wood screws, ~80 (deck to ledgers, ledgers to front wall, shelf tabs, battens)
- 2-1/2" or 3" structural screws into studs, ~20 (back-wall ledgers, head liner, tower wall side)
- Shims as needed
""".strip()


def cut_list(v, sheets):
    p, h = v.params, v.heights
    lines = [f"### {v.title}", "", v.summary, "",
             "| Part | Qty | Size (W x H) | Notes |", "|---|---:|---|---|"]
    for part in v.cut_parts:
        w, hh = part.size
        lines.append(f"| {part.name} | {part.qty} | {fmt(w)} x {fmt(hh)} | {part.note} |")
    n = len(sheets)
    lines += ["",
              f"- **Panels:** {n} pieces of 4'x4' ({math.ceil(n / 2)} x 4'x8' sheets of {fmt(p.T)} plywood, each cut in half)",
              f"- **Heights from floor:** lower mattress top {fmt(h['lower_mattress_top'])}, deck underside "
              f"{fmt(h['deck_under'])}, upper mattress top {fmt(h['upper_mattress_top'])}, rail top {fmt(h['rail_top'])}",
              f"- **Lower bunk sitting room** (mattress top to deck): {fmt(h['headroom'])}",
              f"- **Upper rail above mattress:** {fmt(h['rail_above_mattress'])} (ASTM F1427 minimum is 5\")",
              f"- **Door:** {fmt(h['door'][0])} to {fmt(h['door'][1])} from the head wall, sill {fmt(p.door_sill)}, "
              f"arch top {fmt(p.door_top)}",
              f"- **Climb:** toe holes onto shelves at {', '.join(fmt(z) for z in h['steps'])}, then the deck at "
              f"{fmt(p.deck_top)}; climb-in gap {fmt(h['entry'][0])} to the foot wall",
              f"- **Front wall joint:** {fmt(h['joint_x'])} from the head wall", ""]
    return "\n".join(lines)


def write_bunk(v, outdir, step=True):
    os.makedirs(os.path.join(outdir, "parts"), exist_ok=True)
    os.makedirs(os.path.join(outdir, "sheets"), exist_ok=True)
    for part in v.cut_parts:
        fname = part.name.lower().replace(" ", "_").replace("(", "").replace(")", "").replace("-", "_")
        write_part_dxf(part, os.path.join(outdir, "parts", f"{fname}.dxf"))
    sheets = nest_variant(v)
    for i, sheet in enumerate(sheets):
        write_sheet_dxf(sheet, i, v.params, os.path.join(outdir, "sheets", f"panel_{i + 1}.dxf"))
    draw_sheets(v, sheets, os.path.join(outdir, "nesting.png"))
    render_iso(v, os.path.join(outdir, "preview.png"))
    cut = [q for q in v.parts if not q.name.startswith("Front wall")]
    render_iso(v, os.path.join(outdir, "cutaway.png"), parts=cut, title=f"{v.title}: front wall removed")
    front_elevation(v, os.path.join(outdir, "front.png"))
    side_section(v, os.path.join(outdir, "sections.png"))
    part_drawings(v, os.path.join(outdir, "part_drawings.png"))
    md = cut_list(v, sheets)
    with open(os.path.join(outdir, "cut_list.md"), "w") as f:
        f.write(md)
    facts = "\n".join(ln[2:].replace("**", "") for ln in md.splitlines() if ln.startswith("- "))
    rows = [ln for ln in md.splitlines() if ln.startswith("|") and not ln.startswith("|---")]
    table = "\n".join(f"{c[0]:<26}{c[1]:>4}   {c[2]:<22}{c[3]}"
                      for c in ([x.strip() for x in r.strip("|").split("|")] for r in rows))
    with PdfPages(os.path.join(outdir, "drawings.pdf")) as pdf:
        for name in ("preview.png", "cutaway.png", "front.png", "sections.png", "part_drawings.png", "nesting.png"):
            _image_page(pdf, os.path.join(outdir, name))
        _text_page(pdf, f"{v.title}: cut list and key dimensions", [("Cut list", table), ("Key dimensions", facts)])
        _text_page(pdf, f"{v.title}: hardware and assembly", [("Hardware", HARDWARE), ("Assembly", ASSEMBLY)])
    if step:
        try:
            from bedgen.step import write_step
            write_step(v.parts, v.params.T, os.path.join(outdir, f"{v.key}.step"))
        except ImportError:
            print("  (cadquery-ocp not installed: skipped STEP)")
    return md


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--set", action="append", default=[], metavar="NAME=VALUE")
    ap.add_argument("--out", default="output")
    ap.add_argument("--no-step", action="store_true")
    args = ap.parse_args()
    p = BunkParams()
    fields = {f.name: f for f in dataclasses.fields(BunkParams)}
    for kv in args.set:
        name, value = kv.split("=", 1)
        if name not in fields:
            ap.error(f"unknown parameter {name}")
        t = fields[name].type
        setattr(p, name, value if t in (str, "str") else int(value) if t in (int, "int") else float(value))
    for v in build_bunks(p):
        outdir = os.path.join(args.out, v.key)
        write_bunk(v, outdir, step=not args.no_step)
        print(f"wrote {outdir}")


if __name__ == "__main__":
    main()
