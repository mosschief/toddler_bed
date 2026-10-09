"""The three bed variants, built as lists of Parts.

World coordinates (inches): x runs along the nook from the head wall (x=0) to
the foot wall, y runs from the front face of the guard panel (y=0) back to
the rear wall, z is up from the floor.
"""
from dataclasses import dataclass, field

from shapely.ops import unary_union

from .params import Params
from .parts import (NX, NY, X, Y, Z, Part, h_stadium, place, rect, round_concave,
                    round_convex, rounded_rect, slots_between, split_with_puzzle)

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
    L, bw = p.nook_width, p.box_width
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
        opening = round_convex(rect(bw, -10, L - bw, opening_top), r)
        panel = panel.difference(opening)

    panel = panel.intersection(rect(0, 0, L, rail_top))

    # slots in each stretch of rail between a box and the exit
    slot_y0 = sill_top + p.slot_gap_above_sill
    slot_y1 = rail_top - p.top_rail
    spans = [(bw, ex0), (ex1, L - bw)]
    slots = []
    for a, b in spans:
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
def storage_boxes(p: Params, box_top, ledger_z=None):
    """Lidded boxes at each end. The guard panel is their front."""
    T, D, bw, L = p.T, p.depth, p.box_width, p.nook_width
    side_h = box_top - T
    inner_w = bw - 2 * T
    parts = []

    side = Part("Box side", rect(0, 0, D, side_h), note="outer + inner side of each box")
    back = Part("Box back", rect(0, 0, inner_w, side_h), color=WOOD_DARK)
    bottom = Part("Box bottom", rect(0, 0, inner_w, D - T), color=WOOD_DARK)
    lid_d = D - 1 / 16
    lid_shape = rect(0, 0, bw, lid_d).difference(_finger_hole(bw))
    lid = Part("Box lid", lid_shape, color=LID, note="piano hinge at the back edge")

    for x0, side_xs in ((0, (0, bw - T)), (L - bw, (L - bw, L - T))):
        side.placements += [place((sx, T, 0), Y, Z, X) for sx in side_xs]
        back.placements.append(place((x0 + T, T + D, 0), X, Z, NY))
        bottom.placements.append(place((x0 + T, T, 0), X, Y, Z))
        lid.placements.append(place((x0, T + 1 / 16, side_h), X, Y, Z))
    parts += [side, back, bottom, lid]

    if ledger_z is not None:
        ledger = Part("Deck ledger (box side)", rect(0, 0, D, 1.5), color=WOOD_DARK,
                      note="screwed to the mattress-side face of each box")
        ledger.placements += [place((bw, T, ledger_z - 1.5), Y, Z, X),
                              place((L - bw - T, T, ledger_z - 1.5), Y, Z, X)]
        parts.append(ledger)
    return parts


def _finger_hole(bw):
    length = min(3.0, bw - 2.0)
    return h_stadium(bw / 2, 1.75, length, 1.0) if length > 1.0 else rect(0, 0, 0, 0)


# ---------------------------------------------------------------------------
# Non-cut items for the render
# ---------------------------------------------------------------------------
def mattress(p: Params, z0):
    m = Part("Mattress", rect(0, 0, p.mattress_length, p.mattress_width),
             material="other", color="#f4f1ea")
    m.placements.append(place((p.box_width + p.mattress_clearance, p.T + p.mattress_clearance / 2, z0),
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
    v.parts = [pa, pb] + storage_boxes(p, box_top) + [mattress(p, 0)]
    v.heights = dict(mattress_top=mat_top, rail_top=rail_top, sill_top=sill_top,
                     box_top=box_top, exit=(ex0, ex1), joint_x=joint_x)
    return v


def side_exit(p: Params):
    j = p.side_exit_start + p.exit_width * 0.375
    return _floor_variant(
        p, "v1_side_exit", "Floor bed, side exit",
        "Mattress on the floor, exit toward the foot end like the reference photo.",
        p.side_exit_start, j)


def center_exit(p: Params):
    ex0 = p.nook_width / 2 - p.exit_width / 2
    return _floor_variant(
        p, "v2_center_exit", "Floor bed, centre exit",
        "Mattress on the floor, exit in the middle; the two panel halves are mirror-length "
        "and join in the low sill.",
        ex0, p.nook_width / 2)


def raised_drawers(p: Params):
    T, D, L, bw = p.T, p.depth, p.nook_width, p.box_width
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
    v.parts = ([pa, pb] + storage_boxes(p, box_top, ledger_z=deck_under)
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
    return [side_exit(p), center_exit(p), raised_drawers(p)]
