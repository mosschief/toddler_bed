# Built-in toddler bed (CNC plywood)

Parametric design for a built-in toddler bed in a 64" wide nook, sized for a
**Moonlight Slumber Little Dreamer** crib mattress (52" x 27.5" x 5"), with
every part small enough to cut on a **4' x 4' CNC**.

Three variants are generated:

| Variant | Mattress | Exit | 4'x4' panels |
|---|---|---|---|
| [`v1_side_exit`](output/v1_side_exit) | on the floor | toward the foot end, like the reference photo | 2 |
| [`v2_center_exit`](output/v2_center_exit) | on the floor | centred; two near-equal panel halves | 2 |
| [`v3_raised_drawers`](output/v3_raised_drawers) | on a deck over 2 small IKEA HEMNES underbed boxes | centred | 5 |

**`v1_side_exit` is the chosen design** and gets the full CAD package:

- `v1_side_exit.step`: 3D assembly (millimetres, one named solid per part) for Fusion 360, Onshape, FreeCAD etc.
- `drawings.pdf`: 3D view, front view, plan, section through a box, exploded box, dimensioned part drawings, nesting, cut list, hardware and assembly steps

Each variant folder has:

- `preview.png`: 3D view, `front.png`: dimensioned front elevation
- `nesting.png` and `sheets/panel_N.dxf`: parts laid out on 48" x 48" panels, ready for CAM
- `parts/*.dxf`: one file per unique part
- `cut_list.md`: quantities, sizes and key heights (all variants are combined in [`output/CUT_LIST.md`](output/CUT_LIST.md))

## Layout

- The guard panel runs the full 64" across the front. Its two ends are solid
  and form the fronts of the head and foot boxes; the middle has rounded
  slots (1 1/4" wide with 1" slats, under the 2-3/8" limit in ASTM F1821)
  and the exit opening.
- The panel is longer than the CNC bed, so it is cut as two pieces joined by a
  glued two-knob puzzle joint placed in the low sill under the exit. With a
  centred exit the halves are 33" and 32" long; with the side exit the long
  half is 45 1/4", which still fits but leaves little room on the bed.
- Head and foot boxes fill the nook on either side of the mattress
  (5 3/4" wide each with the defaults; 4 1/4" inside). They are joined with
  through tab-and-slot joints (dog-boned slots), have a floor raised 1" and a
  back set 3/4" in from the wall for scribing.
- Each lid is hinged along its long wall-side edge (on a fixed 1 1/2" strip)
  and opens toward the mattress. The big mattress-side panel of each box has
  a 4" wide hand cut-out in the middle of its top edge for lifting the lid.
  Lids sit 1" below the rail top, tucked behind the guard panel.
- Raised version: the deck is two halves meeting over a centre divider and
  sitting on ledgers screwed to the boxes and the wall. The IKEA fronts are
  replaced by inset plywood faces with a cut-through finger pull.

## Regenerating

```bash
pip install -r requirements.txt   # cadquery-ocp is only needed for the STEP export
python3 generate.py                          # 3/4" plywood
python3 generate.py --thickness 0.709        # measured 18 mm sheet
python3 generate.py --set exit_width=18 --set nook_width=63.75
python3 generate.py --full all               # STEP + PDF for every variant
```

Every dimension lives in [`bedgen/params.py`](bedgen/params.py). DXFs are in
inches; outlines are on layer `CUT_OUTSIDE`, holes/slots on `CUT_INSIDE`,
labels on `LABEL` (don't cut). Geometry is finished size, so let CAM apply
the tool offset. Inside corners are rounded for a 1/4" bit.

## Check before cutting

- **Measure the nook** at the floor and at rail height; walls are rarely
  exactly 64" or square.
- **Measure your plywood** and pass `--thickness`; the box widths depend on it.
- **Measure the IKEA boxes.** IKEA's page lists the small box as
  60 x 67 x 18 cm (23 5/8" x 26 3/8" x 7 1/8"), but its "good to know" text
  says 8 5/8" tall. The deck clears 7 1/8" + 3/4"; if yours are taller,
  set `ikea_box_height`.
- **Test the puzzle joint** on scrap first and adjust `knob_clearance` for
  your machine.

## Safety notes

- Rail top is 9" above the mattress (ASTM F1821 asks for at least 5").
- The mattress has 1/4" clearance per side; keep gaps between mattress and
  panel/boxes small so there is no entrapment space.
- Fix the boxes to wall studs so nothing can tip, and use soft-close lid
  stays (or lift-off lids) so lids can't slam on fingers.
- Round over all exposed edges and finish with a child-safe finish.
