# CNC job: hinge cup pockets in the foot-box lid

Hand-off spec for programming the toolpath. The lid (10 3/4" x 27 5/8", 3/4" plywood) is
**already cut**; this job only pockets two hinge cups into its underside.

## Geometry (`lid_hinge_cups.dxf`, units: inches)
| Layer | Contents | Action |
|---|---|---|
| `POCKET_0.512` | 2 circles, dia 1.3858" (35.2 mm), centres (4.000, 0.8858) and (23.625, 0.8858) | Pocket, 0.512" (13 mm) deep, flat bottom |
| `REFERENCE_LID_OUTLINE_DO_NOT_CUT` | Lid outline 27.625 x 10.75 | Alignment only, no toolpath |
| `LABEL` | Text | No toolpath |

- Origin (0,0) = corner where the lid's **wall edge** (the long edge that sits against the foot wall) meets an end. Wall edge runs along Y = 0.
- Cup centres are 4" from each end and 22.5 mm (0.8858") from the wall edge: Blum boring distance 5 mm (edge of hole 5 mm from lid edge). Do not move them closer to the edge; 7 mm or more leaves almost no clearance to the wall (see lid_hinge_install.md).
- Holes are symmetric along the length, so either end can be the origin end.

## Setup
- Lid **upside down** (show face down; protect it with a spoilboard/clean surface), wall edge along X, squared to the machine.
- Zero X/Y on the origin corner, Z on top of the material (the lid underside).
- Hold-down: clamps or screws outside the cup areas, nowhere near the 13 mm pockets.

## Tooling and toolpath
- 1/4" (6.35 mm) end mill; upcut clears chips best for a 13 mm-deep pocket. The Amana 46170-K compression bit works if fed conservatively.
- Pocket toolpath (not profile), climb or conventional per machine, stepdown about 1/8" (3 mm), stepover about 40%.
- Optional finishing pass on the wall at full depth for a clean 35.2 mm bore.
- Leave 6 mm of wood above the bottom of the cup (lid is about 19 mm). Measure the actual lid thickness first; if it is 23/32" (18.3 mm), 13 mm deep still leaves 5.3 mm.

## Test first
Cut one pocket in scrap of the same plywood and press a Blum 71B3550 cup in. It should press in snugly, with no rocking. If loose, reduce the diameter to 35.0 mm; if too tight, go to 35.3 mm.

## After cutting
Continue with step 3 of `lid_hinge_install.md`. Hinges: 2x Blum 71B3550 + 2x 175H3100 0 mm plates (plate screws on a line 37 mm below the top edge of the wall-side box panel).
