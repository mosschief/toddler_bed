"""Treehouse bunk bed: a fresh design for the same 64" nook.

The lower bunk is a cosy enclosed "treehouse": the head wall liner, the back
wall, a step tower at the foot and the upper deck close it in, and a tall
front wall with an arched door and windows closes the front. The upper bunk
sits on that deck, with the front wall carrying on up as its guard rail. You
climb to the top through toe holes in the front of the foot tower: each hole
lands on one of the tower's shelves, and the top step is a tread on the deck
that sticks out through a gap in the rail, right at the foot of the upper
mattress. A lidded cabinet sits at the head end of the upper bunk.

Every front-wall piece runs floor to rail top in one piece, so the whole bed
stays within the 47" usable height of a 4'x4' CNC bed. That caps the rail
top, and the deck height is chosen from it.

World coordinates as in design.py: x from the head wall (0) to the foot wall,
y from the front face (0) back to the rear wall, z up from the floor.
"""
from dataclasses import dataclass, replace

import numpy as np

from shapely import affinity
from shapely.geometry import Point
from shapely.ops import unary_union

from .design import WOOD_DARK, Variant, _shift_to_origin
from .params import Params
from .parts import (NY, X, Y, Z, Part, fronds_between, place, rect, round_convex,
                    slot_with_dogbones, slots_between, split_with_puzzle, stadium, tab_centres)


@dataclass
class BunkParams(Params):
    # --- heights ----------------------------------------------------------
    rail_top: float = 46.5            # front wall height; one piece must fit the 47" usable CNC bed
    deck_under: float = 34.75         # underside of the upper deck (lower-bunk headroom = this - 5")
    # --- lower bunk front ("treehouse wall") -------------------------------
    door_width: float = 16.0
    door_sill: float = 4.0            # 1" below the lower mattress top, like the floor bed
    door_top: float = 28.0            # top of the round arch
    door_post: float = 3.0            # solid wall between the door and the tower
    window_width: float = 10.0        # >= 9": no head entrapment (ASTM F1427 lower-bunk rule)
    window_height: float = 13.0
    window_bottom: float = 12.0
    windows: int = 2
    lower_cutouts: str = "windows"    # "windows" or "ferns"
    upper_cutouts: str = "slots"      # "slots" or "ferns"
    # --- foot tower / climb -------------------------------------------------
    tower_width: float = 10.75        # outside, foot wall to mattress side (two sides + 9 1/4" inside)
    steps: int = 4                    # shelves you step on; the deck tread is the last step
    step_hole_height: float = 3.25    # under 3.5" so no opening traps a head
    step_hole_side: float = 1.0       # solid wood each side of a toe hole
    entry_post: float = 1.0           # rail end past the tower's mattress side
    # --- upper deck -------------------------------------------------------
    ledger_height: float = 2.5
    deck_pieces: int = 4              # narrow enough to nest beside the tall parts (6 panels, not 7)
    front_ledger_joint_x: float = 42.0
    joint_x: float = 31.0             # vertical puzzle joint in the front wall
    tread_depth: float = 4.0          # top deck piece sticks out through the climb-in gap as the top step
    wall_height: float = 52.0         # backdrop in the renders only

    # --- derived ------------------------------------------------------------
    @property
    def deck_top(self):
        return self.deck_under + self.T

    @property
    def zone_x0(self):
        """Head end of the mattress zone (face of the head-wall liner)."""
        return self.T

    @property
    def tower_x0(self):
        return self.nook_width - self.tower_width

    @property
    def tower_in(self):
        """Inside of the tower, x0..x1."""
        return self.tower_x0 + self.T, self.nook_width - self.T

    @property
    def zone_length(self):
        return self.tower_x0 - self.T

    @property
    def step_tops(self):
        n = self.steps + 1
        return [self.deck_top * k / n for k in range(1, n)]

    @property
    def cab_side_x(self):
        """Mattress-side panel of the top-bunk cabinet (the upper mattress runs to the foot wall)."""
        return self.nook_width - (self.mattress_length + 2 * self.mattress_clearance) - self.T

    @property
    def cab_top(self):
        """Top of the cabinet sides and the head liner; the lid sits on them, flush with the rail."""
        return self.rail_top - self.T

    @property
    def entry_x0(self):
        return self.tower_x0 + self.T + self.entry_post

    @property
    def door_x(self):
        x1 = self.tower_x0 - self.door_post
        return x1 - self.door_width, x1


def arch(x0, x1, y0, y_top, foot_r=0.0):
    """Round-topped opening; the bottom corners rounded by foot_r."""
    w = x1 - x0
    body = unary_union([rect(x0, y0, x1, y_top - w / 2),
                        Point((x0 + x1) / 2, y_top - w / 2).buffer(w / 2, quad_segs=24)])
    if foot_r:
        body = unary_union([round_convex(body, foot_r).intersection(rect(x0 - 1, y0 - 1, x1 + 1, y0 + foot_r + 0.5)),
                            body.difference(rect(x0 - 1, y0 - 1, x1 + 1, y0 + foot_r + 0.5))])
    return body


# ---------------------------------------------------------------------------
def front_wall(p: BunkParams):
    """Floor-to-rail front wall, returned as the two puzzle-jointed pieces."""
    L, H, T = p.nook_width, p.rail_top, p.T
    big = 3.0
    panel = rect(-big, -big, L + big, H)

    # entry gap in the rail over the tower: open to the foot wall, rounded rail end
    ex0 = p.entry_x0
    cut = round_convex(rect(ex0, p.deck_under, L + 10, H + 10), p.sill_fillet)
    panel = panel.difference(cut)
    zone = rect(ex0 - 4, p.deck_top + 0.01, ex0 + 1, H + 1)
    panel = unary_union([panel.difference(zone), round_convex(panel, p.gap_corner_radius).intersection(zone)])
    panel = panel.intersection(rect(0, 0, L, H))

    holes = []
    # treehouse door
    dx0, dx1 = p.door_x
    holes.append(arch(dx0, dx1, p.door_sill, p.door_top, foot_r=p.sill_fillet))

    # lower-wall windows (or ferns) between the head liner and the joint
    a, b = p.T, p.joint_x
    if p.lower_cutouts == "ferns":
        holes += fronds_between(a, b, p.window_bottom, p.window_bottom + 12, p.fern_height, p.fern_pitch,
                                margin=1.75, leaf_w=p.fern_leaf_width, web=p.fern_web)
    else:
        n, w = p.windows, p.window_width
        gap = (b - a - n * w) / (n + 1)
        for i in range(n):
            x0 = a + gap + i * (w + gap)
            holes.append(arch(x0, x0 + w, p.window_bottom, p.window_bottom + p.window_height, foot_r=1.0))

    # toe holes in the tower front, each landing on a shelf top
    tx0, tx1 = p.tower_in
    for z in p.step_tops:
        holes.append(round_convex(rect(tx0 + p.step_hole_side, z, tx1 - p.step_hole_side,
                                       z + p.step_hole_height), 0.75))

    # guard-rail band above the deck: slots (<= 3.5" openings) or small ferns
    y0, y1 = p.deck_top + 1.0, H - p.top_rail
    spans = [(p.cab_side_x + p.T, p.joint_x), (p.joint_x, p.entry_x0)]
    for s0, s1 in spans:
        if p.upper_cutouts == "ferns":
            holes += fronds_between(s0, s1, p.deck_top + 0.6, H - 1.0, 8.75, 4.25, margin=1.6,
                                    leaf_w=p.fern_leaf_width, web=p.fern_web)
        else:
            holes += slots_between(s0, s1, y0, y1, p.slot_width, p.slat_width, margin=1.6)
    panel = panel.difference(unary_union(holes))

    ks = [8.0, 20.0, 31.5, p.deck_top + (H - p.deck_top) / 2]
    a_shape, b_shape = split_with_puzzle(panel, p.joint_x, ks, p)
    pa = Part("Front wall A", a_shape, note="head half, knobs; glue to B")
    pb = Part("Front wall B", b_shape, note="foot half, sockets; door and toe holes")
    for part in (pa, pb):
        part.placements.append(place((0, T, 0), X, Z, NY))
        _shift_to_origin(part)
    return pa, pb


def end_and_tower(p: BunkParams):
    """Head-wall liner (full height) and the two tower sides with their step shelves."""
    T, D, gd, c = p.T, p.depth, p.groove_depth, p.tab_clearance
    U = gd + D  # side-local depth, front tongue included
    parts = []

    parts += cabinet(p)

    # shelves: tabs through dog-boned slots in both tower sides
    tx0, tx1 = p.tower_in
    sw = tx1 - tx0
    sd = D - 0.25                       # stops 1/4" short of the wall
    tl = 4.0
    tabs_u = tab_centres(sd, tl)
    shelf_shape = unary_union([rect(0, 0, sw, sd)] +
                              [rect(-T, u - tl / 2, 0, u + tl / 2) for u in tabs_u] +
                              [rect(sw, u - tl / 2, sw + T, u + tl / 2) for u in tabs_u])
    shelf = Part("Tower step shelf", shelf_shape,
                 note="you step on its front edge through a toe hole")
    slots = []
    for z in p.step_tops:
        shelf.placements.append(place((tx0, T, z - T), X, Y, (0, 0, 1)))
        slots += [slot_with_dogbones(gd + u - tl / 2 - c, z - T - c, gd + u + tl / 2 + c, z + c, p.bit_diameter)
                  for u in tabs_u]
    _shift_to_origin(shelf)
    slots = unary_union(slots)

    side = rect(0, 0, U, p.deck_under)
    foot = Part("Tower side (wall)", side.difference(slots), color=WOOD_DARK,
                note="screw to the foot-wall studs")
    foot.placements.append(place((p.nook_width - T, T - gd, 0), Y, Z, (1, 0, 0)))

    # mattress side: cubby openings between the shelves, open to the lower bunk
    levels = [0.0] + p.step_tops + [p.deck_under + T]
    cubbies = []
    for lo, hi in zip(levels[:-1], levels[1:]):
        v0 = lo + (2.5 if lo == 0 else 1.25)
        v1 = hi - T - 1.25
        if v1 - v0 > 3:
            cubbies.append(round_convex(rect(gd + 2.5, v0, gd + D - 2.5, v1), 1.25))
    inner = Part("Tower side (mattress)", side.difference(slots).difference(unary_union(cubbies)),
                 note="cubby openings face the lower bunk; carries the deck")
    inner.placements.append(place((p.tower_x0, T - gd, 0), Y, Z, (1, 0, 0)))
    parts += [foot, inner, shelf]
    return parts


def cabinet(p: BunkParams, open_lid_deg=0.0):
    """Head-wall liner plus the lidded cabinet on the top bunk at the head end.

    The liner is the cabinet's wall side; the mattress-side panel stands on the deck in a
    groove in the front wall; the back has tabs through both. The one-piece lid is
    piano-hinged along the head wall and opens toward the mattress, like the floor bed.
    """
    T, D, gd, c, tl = p.T, p.depth, p.groove_depth, p.tab_clearance, 3.0
    U = gd + D
    z0, z1 = p.deck_top, p.cab_top
    h = z1 - z0
    yb0 = T + D - p.back_inset - T              # front face of the cabinet back
    ub = yb0 - (T - gd)                         # same, in side-local depth
    tabs = tab_centres(h, tl)
    slots = unary_union([slot_with_dogbones(ub - c, z0 + t - tl / 2 - c, ub + T + c, z0 + t + tl / 2 + c,
                                            p.bit_diameter) for t in tabs])

    liner = Part("Head wall liner", rect(0, 0, U, z1).difference(slots), color=WOOD_DARK,
                 note="screw to the head-wall studs; lower bunk's head end and the cabinet's wall side")
    liner.placements.append(place((0, T - gd, 0), Y, Z, (1, 0, 0)))

    side_slots = affinity.translate(slots, 0, -z0)
    nw, nd = p.hand_notch
    mid = gd + D / 2
    side = rect(0, 0, U, h).difference(side_slots)
    side = side.difference(round_convex(rect(mid - nw / 2, h - nd, mid + nw / 2, h + 5), min(nw / 2, nd) * 0.9))
    zone = rect(mid - nw / 2 - 1, h - nd - 1, mid + nw / 2 + 1, h + 1)
    side = unary_union([side.difference(zone), round_convex(side, 0.375).intersection(zone)])
    cside = Part("Cabinet side", side, note="faces the upper mattress; hand cut-out to lift the lid")
    cside.placements.append(place((p.cab_side_x, T - gd, z0), Y, Z, (1, 0, 0)))

    iw = p.cab_side_x - T
    back = Part("Cabinet back", unary_union([rect(0, 0, iw, h)] +
                                            [rect(-T, t - tl / 2, 0, t + tl / 2) for t in tabs] +
                                            [rect(iw, t - tl / 2, iw + T, t + tl / 2) for t in tabs]),
                color=WOOD_DARK, note="tabs through the liner and the cabinet side")
    back.placements.append(place((T, yb0 + T, z0), X, Z, NY))
    _shift_to_origin(back)

    g = p.lid_gap
    lw = p.cab_side_x + T
    lid = Part("Cabinet lid", rect(0, 0, lw, D - 2 * g), color="#ead9b6",
               note="piano hinge along the head-wall edge; flush with the rail top")
    if open_lid_deg:
        th = np.radians(open_lid_deg)
        u = np.array([np.cos(th), 0, np.sin(th)])
        nrm = np.array([-np.sin(th), 0, np.cos(th)])
        origin = np.array([0, T + g, z1 + T]) - T * nrm
        lid.placements.append(place(origin, tuple(u), Y, tuple(nrm)))
    else:
        lid.placements.append(place((0, T + g, z1), X, Y, (0, 0, 1)))
    return [liner, cside, back, lid]


def deck_parts(p: BunkParams):
    T, D, L = p.T, p.depth, p.nook_width
    lh, zu = p.ledger_height, p.deck_under
    x0, x1 = T, L
    parts = []
    # the foot-end deck piece runs out through the climb-in gap as the top step
    tread = round_convex(rect(p.entry_x0 + p.sill_fillet + 0.06, -p.tread_depth, L + 3, T), 1.0).intersection(
        rect(0, -p.tread_depth - 1, L - 0.06, T + 1))

    # deck: equal pieces, each seam over a batten
    n = p.deck_pieces
    joints = [x0 + (x1 - x0) * k / n for k in range(1, n)]
    edges = [x0] + joints + [x1]
    mz0, mz1 = p.cab_side_x + T + 2.5, L - 3.0
    vents = []
    for a, b in zip(edges[:-1], edges[1:]):
        lo, hi = max(a + 3.5, mz0), min(b - 3.5, mz1)
        k = max(1, int((hi - lo) // 4.5) + 1) if hi - lo > 1 else 0
        for i in range(k):
            cx = lo + (hi - lo) * (i + 0.5) / k if k > 1 else (lo + hi) / 2
            for cy in (T + 7.0, T + D / 2, T + D - 7.0):
                vents.append(stadium(cx, cy - 3, cy + 3, 1.0))
    vents = unary_union(vents)
    w0 = edges[1] - edges[0]
    deck = Part("Deck piece", rect(0, 0, w0, D), note="upper mattress platform; screw down into ledgers")
    shapes = []
    for i, (a, b) in enumerate(zip(edges[:-1], edges[1:])):
        s = rect(a, T, b, T + D).difference(vents)
        if b >= L:
            s = unary_union([s, tread.intersection(rect(a, -10, b, T + 1))])
        shapes.append(affinity.translate(s, -a, -T))
        deck.placements.append(place((a, T, zu), X, Y, (0, 0, 1)))
    # pieces differ only in their holes; keep them separate parts when they differ
    if all(sh.equals(shapes[0]) for sh in shapes):
        deck.shape = shapes[0]
        parts.append(deck)
    else:
        for i, (sh, pl) in enumerate(zip(shapes, deck.placements)):
            part = Part(f"Deck {chr(65 + i)}", sh, note=deck.note if i < n - 1 else
                        "foot end; its tread sticks out through the climb-in gap as the top step")
            part.placements.append(pl)
            _shift_to_origin(part)
            parts.append(part)

    batten = Part("Deck seam batten", rect(0, 0, 5.0, D - 2 * T), color=WOOD_DARK,
                  note="glue + screw under each deck seam, between the ledgers")
    for j in joints:
        batten.placements.append(place((j - 2.5, 2 * T, zu - T), X, Y, (0, 0, 1)))
    parts.append(batten)

    # ledgers: on the back of the front wall, on the back wall, on the head liner
    fj = p.front_ledger_joint_x
    fl = []
    for a, b in ((x0, fj), (fj, p.tower_x0)):
        part = Part("Front ledger", rect(0, 0, b - a, lh), color=WOOD_DARK,
                    note="glue + screw to the back of the front wall; bridges the wall joint")
        part.placements.append(place((a, 2 * T, zu - lh), X, Z, NY))
        fl.append(part)
    if abs(fl[0].size[0] - fl[1].size[0]) < 1e-6:
        fl[0].placements += fl[1].placements
        fl = fl[:1]
    else:
        fl[0].name, fl[1].name = "Front ledger (long)", "Front ledger (short)"
    back = Part("Back-wall ledger", rect(0, 0, (p.tower_x0 - x0) / 2, lh), color=WOOD_DARK,
                note="screw into back-wall studs, 2 per stud")
    for a in (x0, x0 + (p.tower_x0 - x0) / 2):
        back.placements.append(place((a, T + D, zu - lh), X, Z, NY))
    head = Part("Head ledger", rect(0, 0, D - 2 * T, lh), color=WOOD_DARK,
                note="screw to the head-wall liner, between the other ledgers")
    head.placements.append(place((T, 2 * T, zu - lh), Y, Z, (1, 0, 0)))
    parts += fl + [back, head]
    return parts


def add_front_joinery(p: BunkParams, panels):
    """Rabbet for the head liner, dog-boned grooves for the two tower sides,
    all pocketed into the back of the front wall."""
    T, c = p.T, p.tab_clearance
    grooves = [rect(-1, -1, T + c, p.cab_top + c),
               slot_with_dogbones(p.cab_side_x - c, p.deck_top - c, p.cab_side_x + T + c, p.cab_top + c,
                                  p.bit_diameter),
               slot_with_dogbones(p.tower_x0 - c, -2, p.tower_x0 + T + c, p.deck_under + c, p.bit_diameter),
               rect(p.nook_width - T - c, -2, p.nook_width + 1, p.deck_under + c)]
    for panel in panels:
        ox, oz = panel.placements[0].origin[0], panel.placements[0].origin[2]
        for g in grooves:
            g = affinity.translate(g, -ox, -oz).intersection(panel.shape)
            if not g.is_empty and g.area > 1e-3:
                panel.pockets.append((g, p.groove_depth, "groove"))


def mattresses(p: BunkParams):
    out = []
    for name, x, z in (("Lower mattress", p.T, 0.0), ("Upper mattress", p.cab_side_x + p.T, p.deck_top)):
        m = Part(name, rect(0, 0, p.mattress_length, p.mattress_width), material="other", color="#f4f1ea")
        m.placements.append(place((x + p.mattress_clearance, p.T + p.mattress_clearance / 2, z), X, Y, Z))
        m.render_thickness = p.mattress_thickness
        out.append(m)
    return out


def treehouse_bunk(p: BunkParams, key="bunk_treehouse", title="Treehouse bunk",
                   summary="Fresh bunk design: an enclosed treehouse lower bunk with an arched door and "
                           "windows, the upper bunk on a deck above it with a lidded cabinet at the head, and a "
                           "built-in climb up the foot tower that lands on the upper mattress."):
    pa, pb = front_wall(p)
    add_front_joinery(p, [pa, pb])
    v = Variant(key, title, summary, p)
    v.parts = [pa, pb] + end_and_tower(p) + deck_parts(p) + mattresses(p)
    v.open_parts = [q if q.name != "Cabinet lid" else cabinet(p, open_lid_deg=88)[-1] for q in v.parts]
    # renders only: draw the deck tread (in front of the wall) as its own slab so the
    # painter's sort puts it in front of the front wall instead of behind it
    for i, q in enumerate(v.open_parts):
        if q.name.startswith("Deck") and q.size[1] > p.depth + 1:
            w = q.size[0]
            front = Part(q.name, q.shape.intersection(rect(-1, -1, w + 1, p.tread_depth)), placements=q.placements,
                         color=q.color, material="other")
            rest = Part(q.name, q.shape.difference(rect(-1, -1, w + 1, p.tread_depth)), placements=q.placements,
                        color=q.color, material="other")
            front.render_thickness = rest.render_thickness = p.T
            v.open_parts[i:i + 1] = [rest, front]
            break
    ex0 = p.entry_x0
    v.heights = dict(lower_mattress_top=p.mattress_thickness, deck_under=p.deck_under, deck_top=p.deck_top,
                     upper_mattress_top=p.deck_top + p.mattress_thickness, rail_top=p.rail_top,
                     rail_above_mattress=p.rail_top - p.deck_top - p.mattress_thickness,
                     headroom=p.deck_under - p.mattress_thickness, door=p.door_x,
                     entry=(ex0, p.nook_width), steps=p.step_tops, joint_x=p.joint_x)
    return v


def build_bunks(p: BunkParams = None):
    p = p or BunkParams()
    return [treehouse_bunk(p),
            treehouse_bunk(replace(p, lower_cutouts="ferns", upper_cutouts="ferns"),
                           key="bunk_treehouse_ferns", title="Treehouse bunk, ferns",
                           summary="The treehouse bunk with fern fronds in place of the windows and rail slots.")]
