"""The three bed variants, built as lists of Parts.

World coordinates (inches): x runs along the nook from the head wall (x=0) to
the foot wall, y runs from the front face of the guard panel (y=0) back to
the rear wall, z is up from the floor.
"""
from dataclasses import dataclass, field, replace

import numpy as np
from shapely import affinity
from shapely.geometry import Point
from shapely.ops import unary_union

from .params import Params
from .parts import (NX, NY, X, Y, Z, Part, flowers_between, trees_between, h_stadium, place, rect, round_concave,
                    round_convex, slot_with_dogbones, slots_between, split_with_puzzle,
                    tab_centres)

WOOD = "#e3cfa8"
WOOD_DARK = "#cdb48a"
LID = "#ead9b6"


@dataclass
class Variant:
    key: str
    title: str
    summary: str
    params: Params
    parts: list = field(default_factory=list)
    open_parts: list = None  # same assembly with a lid open, for the preview
    heights: dict = field(default_factory=dict)

    @property
    def cut_parts(self):
        return [p for p in self.parts if p.material == "plywood"]


# ---------------------------------------------------------------------------
# Front guard panel
# ---------------------------------------------------------------------------
def front_panel(p: Params, rail_top, sill_bottom, sill_top, exit_x0, opening_top=None):
    """Full-width guard panel. Returns the uncut outline and the exit/sill info.

    sill_bottom: bottom edge of the panel across the mattress zone (0 when the
    panel stands on the floor, the deck underside when there are drawers below).
    opening_top: when set, the panel is cut away below this height between the
    boxes (the drawer opening) and the box fronts become full-height posts.
    """
    L, hbw, fbw = p.nook_width, p.head_box_width, p.foot_box_width
    big = 3.0  # build oversized, round, then trim to the real edges
    panel = rect(-big, -big, L + big, rail_top)

    ex0, ex1 = exit_x0, exit_x0 + p.exit_width
    exit_cut = round_convex(rect(ex0, sill_top, ex1, rail_top + 10), p.sill_fillet)
    panel = panel.difference(exit_cut)
    # round the two rail ends at the exit; leave wall/floor edges square
    corners = rect(ex0 - 4, sill_top + 0.01, ex1 + 4, rail_top + 1)
    panel = unary_union([panel.difference(corners),
                         round_convex(panel, p.gap_corner_radius).intersection(corners)])

    if opening_top is not None:
        r = p.bit_diameter / 2 + 0.05
        opening = round_convex(rect(hbw, -10, L - fbw, opening_top), r)
        panel = panel.difference(opening)

    panel = panel.intersection(rect(0, 0, L, rail_top))

    # slots in each stretch of rail between a box and the exit
    slot_y0 = sill_top + p.slot_gap_above_sill
    slot_y1 = rail_top - p.top_rail
    spans = [(hbw, ex0), (ex1, L - fbw)]
    slots = []
    for a, b in spans:
        if p.rail_cutouts == "trees":
            slots += trees_between(a, b, slot_y0, slot_y1, p.tree_height, p.tree_width,
                                   p.tree_pitch, p.tree_stagger, margin=1.5)
        elif p.rail_cutouts == "flowers":
            slots += flowers_between(a, b, slot_y0, slot_y1, p.flower_diameter, p.flower_gap,
                                     margin=1.5, petals=p.flower_petals)
        else:
            slots += slots_between(a, b, slot_y0, slot_y1, p.slot_width, p.slat_width, margin=1.5)
    if slots:
        panel = panel.difference(unary_union(slots))
    return panel, (ex0, ex1)


def panel_halves(p: Params, panel, joint_x, y0, y1):
    """Split the panel in the sill with two puzzle knobs."""
    h = y1 - y0
    ys = [y0 + h * 0.3, y0 + h * 0.7]
    return split_with_puzzle(panel, joint_x, ys, p)


# ---------------------------------------------------------------------------
# Head / foot storage boxes
# ---------------------------------------------------------------------------
def storage_boxes(p: Params, box_top, ledger_z=None, open_lid_deg=0.0):
    """Lidded boxes at each end. The guard panel is their front.

    Joinery: the front wall, the back and the raised floor have tabs that pass
    through dog-boned slots in both sides. The front wall sits against the back
    of the guard panel and is bolted to it. The one-piece lid is piano-hinged along
    its long wall-side edge, so it opens toward the mattress. The mattress-side panel has a
    hand cut-out in its top edge for lifting the lid.
    """
    T, D, bw, L = p.T, p.depth, p.box_spans[0][1], p.nook_width
    side_h = box_top - T
    inner_w = bw - 2 * T
    back_u0 = D - p.back_inset - T        # back panel front face, side-local depth
    floor_d = back_u0 - T                  # floor runs from the front wall to the back
    c = p.tab_clearance
    parts = []

    # --- sides: slots for the front wall, back and floor tabs
    side_shape = rect(0, 0, D, side_h)
    back_tabs = tab_centres(side_h - p.bottom_lift, p.tab_length)
    back_tabs = [p.bottom_lift + t for t in back_tabs]
    floor_tabs = tab_centres(floor_d, p.tab_length + 1)  # floor-local; the floor starts at u = T
    slots = [slot_with_dogbones(u0 - c, z - p.tab_length / 2 - c,
                                u0 + T + c, z + p.tab_length / 2 + c, p.bit_diameter)
             for u0 in (0, back_u0) for z in back_tabs]
    slots += [slot_with_dogbones(T + u - (p.tab_length + 1) / 2 - c, p.bottom_lift - c,
                                 T + u + (p.tab_length + 1) / 2 + c, p.bottom_lift + T + c, p.bit_diameter)
              for u in floor_tabs]
    # sides run gd further forward, into the grooves in the back of the front panel
    gd = p.groove_depth
    side_shape = unary_union([affinity.translate(side_shape, gd, 0), rect(0, 0, gd + 0.01, side_h)])
    side_shape = side_shape.difference(affinity.translate(unary_union(slots), gd, 0))
    side = Part("Box side (wall)", side_shape, color=WOOD_DARK, note="against the nook wall, 1 per box")

    # mattress-side panel: centred hand cut-out in the top edge to lift the lid
    nw, nd = p.hand_notch
    mid = gd + D / 2
    notch = round_convex(rect(mid - nw / 2, side_h - nd, mid + nw / 2, side_h + 5), min(nw / 2, nd) * 0.9)
    face_shape = side_shape.difference(notch)
    zone = rect(mid - nw / 2 - 1, side_h - nd - 1, mid + nw / 2 + 1, side_h + 1)
    face_shape = unary_union([face_shape.difference(zone),
                              round_convex(face_shape, 0.375).intersection(zone)])
    face = Part("Box side (mattress)", face_shape, note="faces the mattress; hand cut-out to open the lid")

    # --- back and front wall, tabs on both edges
    back_shape = unary_union([rect(0, 0, inner_w, side_h)] +
                             [rect(-T, z - p.tab_length / 2, 0, z + p.tab_length / 2) for z in back_tabs] +
                             [rect(inner_w, z - p.tab_length / 2, inner_w + T, z + p.tab_length / 2)
                              for z in back_tabs])
    back = Part("Box back", back_shape, color=WOOD_DARK, note="screw through into wall studs")

    # front wall: same outline as the back, plus bolt holes into the guard panel inserts
    bz0, bz1 = p.bottom_lift + T, side_h
    bolt_xs = [p.bolt_inset, inner_w - p.bolt_inset]
    bolt_zs = [bz0 + (bz1 - bz0) * f for f in (0.25, 0.75)]
    front_shape = back_shape.difference(unary_union(
        [Point(x, z).buffer(p.bolt_hole / 2, quad_segs=12) for x in bolt_xs for z in bolt_zs]))
    front = Part("Box front", front_shape, color=WOOD_DARK,
                 note="against the back of the front panel; 4 bolts into it")
    front.bolts = []  # world (x, z) of each bolt, for the inserts in the front panel

    # --- raised floor with tabs on both long edges
    tl = p.tab_length + 1
    floor_shape = unary_union([rect(0, 0, inner_w, floor_d)] +
                              [rect(-T, u - tl / 2, 0, u + tl / 2) for u in floor_tabs] +
                              [rect(inner_w, u - tl / 2, inner_w + T, u + tl / 2) for u in floor_tabs])
    bottom = Part("Box floor", floor_shape, color=WOOD_DARK, note=f"sits {fmt_in(p.bottom_lift)} off the floor")

    # --- one-piece lid, piano-hinged along its long wall-side edge
    g = p.lid_gap
    lid_d = D - 2 * g
    r = min(p.lid_corner_radius, bw / 2 - 0.1)
    lid_shape = rect(0, 0, bw, lid_d)
    if r > 0:
        lid_shape = round_convex(rect(-5, 0, bw, lid_d), r).intersection(lid_shape)
    lid = Part("Box lid", lid_shape, color=LID, note="piano hinge along the long wall-side edge")

    th = np.radians(open_lid_deg)
    for x0, _, sgn in p.box_spans:
        wall_x, face_x = (0, bw - T) if sgn > 0 else (L - T, L - bw)
        side.placements.append(place((wall_x, T - gd, 0), Y, Z, X))
        face.placements.append(place((face_x, T - gd, 0), Y, Z, X))
        back.placements.append(place((x0 + T, T + back_u0 + T, 0), X, Z, NY))
        front.placements.append(place((x0 + T, 2 * T, 0), X, Z, NY))
        front.bolts += [(x0 + T + x, z) for x in bolt_xs for z in bolt_zs]
        bottom.placements.append(place((x0 + T, 2 * T, p.bottom_lift), X, Y, Z))
        wall_edge = 0 if sgn > 0 else L
        if open_lid_deg and (sgn > 0 or len(p.box_spans) == 1):
            # pivot on the top outer edge; the lid stands up against the wall
            u = np.array([sgn * np.cos(th), 0, np.sin(th)])
            nrm = np.array([-sgn * np.sin(th), 0, np.cos(th)])
            origin = np.array([wall_edge, T + g, side_h + T]) - T * nrm
            lid.placements.append(place(origin, tuple(u), Y, tuple(nrm)))
        else:
            lid.placements.append(place((wall_edge, T + g, side_h), (sgn, 0, 0), Y, Z))
    for part in (back, front, bottom):
        _shift_to_origin(part)
    parts += [side, face, back, front, bottom, lid]

    if p.single_box:
        # no box at one end: a liner board on that wall sits in the panel groove,
        # and a block above the mattress bolts the panel to it
        end = p.liner_end.capitalize()
        at_foot = p.liner_end == "foot"
        lx = L - T if at_foot else 0.0
        cw, cz1 = 1.5, side_h - 0.5
        # top flush with the box lid; the tongue in the panel groove stops at side_h
        liner_shape = unary_union([rect(gd, 0, D + gd, side_h + T), rect(0, 0, gd + 0.01, side_h)])
        liner = Part(f"{end} wall liner", liner_shape, color=WOOD_DARK,
                     note=f"screw to the {p.liner_end} wall studs; runs into the panel groove")
        liner.placements.append(place((lx, T - gd, 0), Y, Z, X))
        fz0 = p.mattress_thickness + 0.5
        fzs = [fz0 + (cz1 - fz0) * f for f in (0.25, 0.75)]
        foot_cleat = Part(f"{end} block", rect(0, 0, cw, cz1 - fz0).difference(unary_union(
            [Point(cw / 2, z - fz0).buffer(p.bolt_hole / 2, quad_segs=12) for z in fzs])),
            color=WOOD_DARK, note="above the mattress; glue + 2 screws to the liner, 2 bolts into the panel")
        bx = L - T - cw if at_foot else T
        foot_cleat.placements.append(place((bx, 2 * T, fz0), X, Z, NY))
        foot_cleat.bolts = [(bx + cw / 2, z) for z in fzs]
        parts += [liner, foot_cleat]

    if ledger_z is not None:
        ledger = Part("Deck ledger (box side)", rect(0, 0, D, 1.5), color=WOOD_DARK,
                      note="screwed to the mattress-side face of each box")
        ledger.placements += [place((bw, T, ledger_z - 1.5), Y, Z, X),
                              place((L - p.foot_box_width - T, T, ledger_z - 1.5), Y, Z, X)]
        parts.append(ledger)
    return parts


def add_panel_joinery(p: Params, panels, box_parts, box_top):
    """Grooves (dog-boned, open at the bottom) for every box side, and insert
    holes for the box-front and liner-block bolts, pocketed into the back of the front panel."""
    T, L, c = p.T, p.nook_width, p.tab_clearance
    side_h = box_top - T
    side_xs = [x for x0, w, _ in p.box_spans for x in (x0, x0 + w - T)]
    if p.single_box:
        side_xs.append(L - T if p.liner_end == "foot" else 0.0)  # wall liner
    grooves = [slot_with_dogbones(x - c, -2, x + T + c, side_h + c, p.bit_diameter) for x in side_xs]
    bolts = [b for q in box_parts for b in getattr(q, "bolts", [])]
    holes = [Point(x, z).buffer(p.insert_hole / 2, quad_segs=12) for x, z in bolts]
    for panel in panels:
        ox = panel.placements[0].origin[0]
        oz = panel.placements[0].origin[2]
        for g in grooves:
            g = affinity.translate(g, -ox, -oz).intersection(panel.shape)
            if not g.is_empty and g.area > 1e-3:
                panel.pockets.append((g, p.groove_depth, "groove"))
        for h in holes:
            h = affinity.translate(h, -ox, -oz)
            if panel.shape.contains(h):
                panel.pockets.append((h, p.insert_depth, "insert"))


def fmt_in(x):
    return f'{x:g}"'


# ---------------------------------------------------------------------------
# Non-cut items for the render
# ---------------------------------------------------------------------------
def mattress(p: Params, z0):
    m = Part("Mattress", rect(0, 0, p.mattress_length, p.mattress_width),
             material="other", color="#f4f1ea")
    m.placements.append(place((p.head_box_width + p.mattress_clearance, p.T + p.mattress_clearance / 2, z0),
                              X, Y, Z))
    m.render_thickness = p.mattress_thickness
    return m


# ---------------------------------------------------------------------------
# Variants
# ---------------------------------------------------------------------------
def _floor_variant(p: Params, key, title, summary, exit_x0, joint_x):
    T = p.T
    mat_top = p.mattress_thickness
    rail_top = mat_top + p.rail_above_mattress
    sill_top = mat_top + p.sill_above_mattress
    box_top = rail_top - p.lid_below_rail

    panel, (ex0, ex1) = front_panel(p, rail_top, 0, sill_top, exit_x0)
    a, b = panel_halves(p, panel, joint_x, 0, sill_top)
    pa = Part("Front panel A", a, note="knob half")
    pb = Part("Front panel B", b, note="socket half")
    pa.placements.append(place((0, T, 0), X, Z, NY))
    pb.placements.append(place((0, T, 0), X, Z, NY))
    _shift_to_origin(pa)
    _shift_to_origin(pb)

    v = Variant(key, title, summary, p)
    boxes = storage_boxes(p, box_top)
    add_panel_joinery(p, [pa, pb], boxes, box_top)
    v.parts = [pa, pb] + boxes + [mattress(p, 0)]
    v.open_parts = [pa, pb] + storage_boxes(p, box_top, open_lid_deg=88) + [mattress(p, 0)]
    v.heights = dict(mattress_top=mat_top, rail_top=rail_top, sill_top=sill_top,
                     box_top=box_top, exit=(ex0, ex1), joint_x=joint_x)
    return v


def side_exit(p: Params):
    j = p.side_exit_start + p.exit_width * 0.375
    return _floor_variant(
        p, "v1_side_exit", "Floor bed, side exit",
        "Mattress on the floor, exit toward the foot end like the reference photo.",
        p.side_exit_start, j)


def side_exit_one_box(p: Params):
    p = replace(p, boxes="head")
    j = p.side_exit_start + p.exit_width * 0.375
    return _floor_variant(
        p, "v1b_side_exit_one_box", "Floor bed, side exit, one box",
        "Same as the side-exit bed, but with one wider box at the head end and the mattress "
        "against the foot wall.",
        p.side_exit_start, j)


def side_exit_one_box_flush(p: Params):
    p = replace(p, boxes="head", lid_below_rail=0.0)
    j = p.side_exit_start + p.exit_width * 0.375
    return _floor_variant(
        p, "v1c_side_exit_one_box_flush", "Floor bed, side exit, one box, flush tops",
        "The one-box bed with the box lid and the foot board raised flush with the top of the "
        "front panel.",
        p.side_exit_start, j)


def side_exit_one_box_flowers(p: Params):
    p = replace(p, boxes="head", lid_below_rail=0.0, rail_cutouts="flowers")
    j = p.side_exit_start + p.exit_width * 0.375
    return _floor_variant(
        p, "v1d_side_exit_one_box_flowers", "Floor bed, side exit, one box, flowers",
        "The flush-top one-box bed with flower cut-outs in the rail instead of slots.",
        p.side_exit_start, j)


def side_exit_foot_box(p: Params):
    p = replace(p, boxes="foot", lid_below_rail=0.0)
    # the exit moves toward the head to clear the box, keeping a short post before it
    ex0 = p.nook_width - p.foot_box_width - p.exit_post - p.exit_width
    j = ex0 + p.exit_width * 0.375
    return _floor_variant(
        p, "v1e_side_exit_foot_box", "Floor bed, side exit, box at the foot",
        "The flush-top one-box bed with the box moved to the foot end and the mattress "
        "against the head wall; the exit sits just before the box.",
        ex0, j)


def side_exit_foot_box_trees(p: Params):
    v = side_exit_foot_box(replace(p, rail_cutouts="trees"))
    v.key, v.title = "v1f_side_exit_foot_box_trees", "Floor bed, side exit, box at the foot, trees"
    v.summary = "The foot-box bed with a staggered row of pine-tree cut-outs instead of slots."
    return v


def center_exit(p: Params):
    ex0 = p.nook_width / 2 - p.exit_width / 2
    return _floor_variant(
        p, "v2_center_exit", "Floor bed, centre exit",
        "Mattress on the floor, exit in the middle; the two panel halves are mirror-length "
        "and join in the low sill.",
        ex0, p.nook_width / 2)


def raised_drawers(p: Params):
    T, D, L, bw = p.T, p.depth, p.nook_width, p.box_width
    assert not p.single_box, "the raised version has two boxes"
    deck_under = p.ikea_box_height + p.drawer_headroom
    deck_top = deck_under + T
    mat_top = deck_top + p.mattress_thickness
    rail_top = mat_top + p.rail_above_mattress
    sill_top = mat_top + p.sill_above_mattress
    box_top = rail_top - p.lid_below_rail
    mid = L / 2

    ex0 = mid - p.exit_width / 2
    panel, (ex0, ex1) = front_panel(p, rail_top, deck_under, sill_top, ex0, opening_top=deck_under)
    a, b = panel_halves(p, panel, mid, deck_under, sill_top)
    pa = Part("Front panel A", a, note="knob half")
    pb = Part("Front panel B", b, note="socket half")
    pa.placements.append(place((0, T, 0), X, Z, NY))
    pb.placements.append(place((0, T, 0), X, Z, NY))
    _shift_to_origin(pa)
    _shift_to_origin(pb)

    # Deck: two halves meeting over the centre divider, with vent slots
    half_w = (L - 2 * bw) / 2
    deck_shape = rect(0, 0, half_w, D)
    vw, vh = p.vent_slot
    vents = []
    for i in range(4):
        for j in range(3):
            cx = half_w * (i + 0.5) / 4
            cy = D * (j + 0.5) / 3
            vents.append(h_stadium(cx, cy, vh, vw).buffer(0))
    deck_shape = deck_shape.difference(unary_union(vents))
    deck = Part("Deck", deck_shape, note="mattress platform, two halves")
    deck.placements += [place((bw, T, deck_under), X, Y, Z),
                        place((mid, T, deck_under), X, Y, Z)]

    divider = Part("Centre divider", rect(0, 0, D + T, deck_under),
                   note="front edge flush with the panel face")
    divider.placements.append(place((mid - T / 2, 0, 0), Y, Z, X))

    back_ledger = Part("Deck ledger (wall)", rect(0, 0, half_w - T / 2, 1.5), color=WOOD_DARK,
                       note="screw into wall studs at the back")
    back_ledger.placements += [place((bw, T + D, deck_under - 1.5), X, Z, NY),
                               place((mid + T / 2, T + D, deck_under - 1.5), X, Z, NY)]

    # Drawer faces (replace the IKEA fronts)
    bay = half_w - T / 2
    g = p.drawer_face_gap
    face_w = bay - 2 * g
    face_h = deck_under - p.drawer_floor_gap - g
    face_shape = rect(0, 0, face_w, face_h).difference(
        h_stadium(face_w / 2, face_h - 1.5, 4.5, 1.25))
    face = Part("Drawer face", face_shape, note="screw to the IKEA box from inside")
    face.placements += [place((bw + g, T, p.drawer_floor_gap), X, Z, NY),
                        place((mid + T / 2 + g, T, p.drawer_floor_gap), X, Z, NY)]

    ikea = Part("IKEA HEMNES box", rect(0, 0, p.ikea_box_width, p.ikea_box_depth),
                material="other", color="#bfb6a8")
    ikea.render_thickness = p.ikea_box_height
    ikea.placements += [place((bw + (bay - p.ikea_box_width) / 2, T, 0), X, Y, Z),
                        place((mid + T / 2 + (bay - p.ikea_box_width) / 2, T, 0), X, Y, Z)]

    v = Variant("v3_raised_drawers", "Raised bed over IKEA drawers",
                "Mattress on a plywood deck over two small IKEA HEMNES underbed boxes, "
                "with plywood drawer faces; centre exit.", p)
    boxes = storage_boxes(p, box_top, ledger_z=deck_under)
    add_panel_joinery(p, [pa, pb], boxes, box_top)
    v.parts = ([pa, pb] + boxes
               + [deck, divider, back_ledger, face, ikea, mattress(p, deck_top)])
    v.heights = dict(mattress_top=mat_top, rail_top=rail_top, sill_top=sill_top,
                     box_top=box_top, deck_top=deck_top, deck_under=deck_under,
                     exit=(ex0, ex1), joint_x=mid)
    return v


def _shift_to_origin(part):
    """Move a part's outline so its bbox starts at (0,0) and adjust its placement."""
    import numpy as np
    from shapely import affinity
    x0, y0, _, _ = part.shape.bounds
    part.shape = affinity.translate(part.shape, -x0, -y0)
    for pl in part.placements:
        o = np.asarray(pl.origin, float) + x0 * np.asarray(pl.u) + y0 * np.asarray(pl.v)
        pl.origin = tuple(o)


def build_all(p: Params):
    return [side_exit(p), side_exit_one_box(p), side_exit_one_box_flush(p), side_exit_one_box_flowers(p), side_exit_foot_box(p), side_exit_foot_box_trees(p), center_exit(p), raised_drawers(p)]
