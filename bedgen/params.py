"""All design dimensions, in inches.

Change values here (or override them from the command line, see generate.py)
and re-run the generator; every part, cut file and preview is derived from
these numbers.
"""
from dataclasses import dataclass


@dataclass
class Params:
    # --- Room / mattress -------------------------------------------------
    nook_width: float = 64.0          # wall-to-wall width of the nook
    mattress_length: float = 52.0     # Moonlight Slumber Little Dreamer: 52 x 27.5 x 5
    mattress_width: float = 27.5
    mattress_thickness: float = 5.0
    mattress_clearance: float = 0.25  # gap per side so sheets can be tucked in

    # --- Material / machine ----------------------------------------------
    thickness: float = 0.75           # MEASURE your plywood; 18 mm = 0.709"
    cnc_bed: float = 48.0             # 4' x 4' cutting area
    sheet_margin: float = 0.5         # keep-out around the cut area edge
    part_spacing: float = 0.5         # gap between nested parts (>= 2x bit dia)
    bit_diameter: float = 0.25        # used for inside-corner radii

    # --- Front guard panel -----------------------------------------------
    rail_above_mattress: float = 9.0  # top of rail above mattress top (ASTM F1821 min is 5")
    lid_below_rail: float = 1.0       # box lids sit this far below the rail top
    sill_above_mattress: float = -1.0 # exit floor vs mattress top (negative shows the mattress edge)
    exit_width: float = 16.0
    slot_width: float = 2.0           # ASTM F1821: openings <= 2-3/8"
    slat_width: float = 1.75
    top_rail: float = 2.0             # solid band above the slots
    slot_gap_above_sill: float = 0.0  # slot bottoms vs the exit floor line
    rail_cutouts: str = "slots"       # "slots" or "flowers"
    flower_diameter: float = 6.75     # tip to tip; 6 3/4" keeps the widest opening under 2-3/8"
    flower_gap: float = 1.5           # solid wood between neighbouring flowers
    flower_petals: float = 8
    tree_height: float = 7.0          # "trees": pine-tree cut-outs, alternate ones raised
    tree_width: float = 3.1           # widest tier; the largest opening stays under 2-3/8"
    tree_pitch: float = 4.75
    tree_stagger: float = 1.0
    fern_height: float = 8.0          # "ferns": fern-frond cut-outs
    fern_pitch: float = 5.25
    fern_leaf_width: float = 0.5      # every leaflet at least this wide; 1/4" bit friendly
    fern_web: float = 0.3             # minimum wood between leaflets
    gap_corner_radius: float = 1.5    # rounded top corners at the exit
    sill_fillet: float = 1.0          # rounded inside corners at the exit floor

    # --- Head / foot boxes ---------------------------------------------
    back_inset: float = 0.75          # back panel sits this far in from the wall (scribe room)
    bottom_lift: float = 1.0          # box floor height above the room floor
    tab_length: float = 3.0           # tab-and-slot joinery
    tab_clearance: float = 0.01       # per side, slot vs tab
    lid_gap: float = 0.0625           # gap around the opening lid
    hand_notch: tuple = (4.0, 1.5)    # hand cut-out in the mattress-side panel (width, depth)
    lid_corner_radius: float = 0.0    # 0 = square corners to match the boxes

    # --- Front panel to box joinery (removable) ---------------------------
    groove_depth: float = 0.375       # grooves in the back of the front panel for the box sides
    bolt_inset: float = 0.75          # box-front bolts, in from the inside of each box side
    bolt_hole: float = 0.28           # clearance for 1/4-20 bolts through the box fronts
    insert_hole: float = 0.375        # pilot for 1/4-20 threaded inserts; size to your inserts
    insert_depth: float = 0.5         # leaves 1/4" of face over the insert

    # "both" = head and foot boxes; "head" / "foot" = one wider box at that end,
    # with the mattress against the other wall (a wall liner anchors the panel there)
    boxes: str = "both"

    # Variant 1 (side exit, like the reference photo): exit start from head wall
    side_exit_start: float = 38.0
    exit_post: float = 2.25           # solid rail between the exit and a box at the foot end

    # --- Puzzle joint (joins the two front-panel halves in the sill) -----
    knob_radius: float = 0.5
    knob_neck: float = 0.55
    knob_reach: float = 1.25          # how far the knob protrudes past the joint line
    knob_clearance: float = 0.008     # added to the socket for a snug glue fit

    # --- Raised version (variant 3) --------------------------------------
    # IKEA HEMNES underbed box, small one of the set (60 x 67 x 18 cm)
    ikea_box_width: float = 23.625
    ikea_box_depth: float = 26.375
    ikea_box_height: float = 7.125    # IKEA lists 18 cm; measure yours, see README
    drawer_headroom: float = 0.75     # clearance between box top and deck underside
    drawer_floor_gap: float = 0.375   # plywood face bottom above the floor
    drawer_face_gap: float = 0.125    # reveal around each drawer face
    vent_slot: tuple = (1.0, 6.0)     # deck vent slot (w, h)

    # --- Derived ----------------------------------------------------------
    @property
    def T(self):
        return self.thickness

    @property
    def zone_length(self):
        """Opening between the two boxes, along the nook."""
        return self.mattress_length + 2 * self.mattress_clearance

    @property
    def box_width(self):
        return (self.nook_width - self.zone_length) / 2

    @property
    def single_box(self):
        return self.boxes in ("head", "foot")

    @property
    def liner_end(self):
        """Which wall gets the liner in a one-box bed ("foot" or "head")."""
        return {"head": "foot", "foot": "head"}.get(self.boxes)

    @property
    def single_box_width(self):
        return self.nook_width - self.zone_length - self.T

    @property
    def head_box_width(self):
        """Width taken at the head end: a box, or just the wall liner."""
        return {"head": self.single_box_width, "foot": self.T}.get(self.boxes, self.box_width)

    @property
    def foot_box_width(self):
        """Width taken at the foot end: a box, or just the wall liner."""
        return {"head": self.T, "foot": self.single_box_width}.get(self.boxes, self.box_width)

    @property
    def box_spans(self):
        """(x0, width, direction) of each box; direction points away from its wall."""
        spans = []
        if self.boxes != "foot":
            spans.append((0.0, self.head_box_width, 1))
        if self.boxes != "head":
            spans.append((self.nook_width - self.foot_box_width, self.foot_box_width, -1))
        return spans

    @property
    def depth(self):
        """Back wall to back face of the front panel."""
        return self.mattress_width + self.mattress_clearance
