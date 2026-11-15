"""Dog storage box, printed as two halves that fit a 256 mm bed.

The halves join on the wall after section 1 or 2, whichever fits the bed. Half A's floor tabs
slide under half B and M2.5 machine screws go up from below into a raised floor or two bosses.
A rounded U clip over the double seam wall is screwed down into two posts at the seam's ends,
with the screw heads sunk into round pockets. Each compartment is cut as its own rounded pocket, so
every inside corner is filleted. Clearances are tolerances.json starting values, not yet
measured on the printer.
"""

from __future__ import annotations

import math

import manifold3d as mf
import numpy as np

NAME = "Dog storage box (split, screwed from below)"
PARAMS = [
    dict(key="height", label="Height (mm)", min=40, max=250, step=1, default=100.0),
    dict(key="section_1", label="Section 1 length (mm)", min=20, max=320, step=1, default=183.0),
    dict(key="section_2", label="Section 2 length (mm); section 3 gets the rest", min=20, max=320, step=1, default=105.0),
    dict(key="wall", label="Wall thickness (mm)", min=1.26, max=4.2, step=0.42, default=1.68),
    dict(key="tab_len", label="Floor tab reach under B (mm)", min=11, max=30, step=0.5, default=12.0),
    dict(key="tab_w", label="Floor tab width (mm)", min=11, max=24, step=0.5, default=12.0),
    dict(key="tab_inset", label="Tabs in from long sides (mm)", min=10, max=50, step=1, default=25.0),
    dict(key="floor_style", label="Screw anchor", min=0, max=1, step=1, default=1,
         options=["Two round bumps", "Raised floor sloping away"]),
    dict(key="ramp_len", label="Raised floor slope length (mm): longer is gentler; runs under dividers, capped at half B's end", min=10, max=300, step=1, default=120.0),
    dict(key="boss_smooth", label="Round bump smoothness (mm)", min=0.5, max=6, step=0.25, default=4.0),
    dict(key="hand_w", label="Hand hole width (mm)", min=40, max=105, step=1, default=65.0),
    dict(key="hand_h", label="Hand hole height (mm)", min=10, max=45, step=1, default=15.0),
    dict(key="top_joint", label="Top of the seam", min=0, max=1, step=1, default=1,
         options=["Screwed clip", "Overlap tabs (no clip)"]),
    dict(key="clip_leg", label="Top clip reach down (mm)", min=4, max=20, step=0.5, default=8.0),
    dict(key="clip_gap", label="Top clip gap per side (mm)", min=0.0, max=0.5, step=0.05, default=0.25),
    dict(key="explode", label="Explode view (mm)", min=0, max=80, step=1, default=0.0),
    dict(key="show", label="Show", min=0, max=3, step=1, default=0,
         options=["Whole box", "Half A only", "Half B only", "Top clip only"]),
]

LENGTH = 375.0              # owner: must fit the space exactly
WIDTH = 125.0               # owner: must fit the space exactly
BED = 256.0                 # /printer bed, extruder 1
BED_Z = 261.0
FLOOR = 1.2                 # 6 layers at 0.2: all solid top and bottom layers, no infill
DIVIDER = 1.68              # 4 lines at 0.42
LOOSE, SLIP = 0.30, 0.20    # tolerances.json starting values (not yet measured)
HOLE_SHRINK = 0.15
ELEPHANT_FOOT = 0.2         # tolerances.json elephant_foot (measured: false): first layer spreads this much per side
BED_CHAMFER = 0.4           # slant on bed-side edges that slide into or press against another part
NEST_H = 4.0                # stacking step for future boxes
DIVIDER_DROP = 5.0
SEAM_DROP = 10.5            # seam walls stop this far below the rim: room for the screwed clip under a stacked box
UNDER_HEAD = 1.5            # tab plastic the screw head clamps
BOSS_MARGIN = 1.68          # 4 lines of plastic around the tab pocket
BOSS_CAP = 1.2              # closed top over the pilot hole, so nothing shows inside
PILOT_WALL = 1.2            # plastic kept around the pilot hole where the boss top is rounded
SMOOTH_LAYERS = 16
CLIP_WALL = 2.6            # clip leg thickness
CLIP_ROUND = 1.2
HEAD_CLEAR = 0.3           # head pocket depth beyond the head height, so a typical head sits about flush
POCKET_FLOOR = 1.2         # tab plastic left under the far edge of a top head pocket
POST_LEN = 11.0            # seam posts the clip screws bite into, against each long wall
POST_W = 8.0               # half-A post, measured from the seam wall into section 1
EAR_MARGIN = 1.6           # clip plastic around the screw-head recess on each end tab
# Overlap tabs: half A's seam wall reaches over half B's at the top. The underside slopes at 45° so it prints
# without support, which makes the tab thick; these sizes leave the M3 x 12 about 6.5 mm of bite in half B.
OVERLAP_REACH = 13.6       # how far each tab reaches over half B
OVERLAP_TIP = 2.0          # tab thickness at its tip
OVERLAP_W = 12.0           # tab width along the seam
OVERLAP_POST_MARGIN = 1.5  # half B's seat reaches this much past the tab on each side
SEAT_FLOOR = 1.5           # solid plastic under the deepest pilot hole
CORNER_R = 8.0             # outside vertical corners
CELL_R = 4.0               # inside vertical corners at dividers and the seam
FLOOR_FILLET = 3.0         # floor-to-wall round inside each compartment
HANDLE_TOP = 12.0          # rim to the top of the hand hole
BAND = 3.0                 # thicker wall around the hand hole: only enough to round its edges, the box is ~1 kg
BAND_T = 1.0
HOLE_EDGE_R = 1.5
LOW_DIVIDER_GAP = 3.0      # section 3a/3b divider top sits this far below the hand-hole band
MIN_SECTION = 15.0
SEG = 48
# One screw everywhere: 3 mm self-tapping, 12 or 13 mm long (ST2.9: pan ISO 7049, flat ISO 7050, or round/truss).
# The flat-bottomed head pocket takes any of those heads up to 7 mm wide; pan heads (2.2 mm) sit about flush,
# lower round and flat heads sit a little below, and a flat head seats on the hole's edge.
SCREW = dict(screw_d=2.9, screw_len=12.0, head_d=7.0, head_h=2.2, pilot_d=2.4)
LONGEST_SCREW = 13.0       # pilot holes are deep enough for the 13 mm ISO length too

COLOR_A = (0.30, 0.47, 0.66)      # blue
COLOR_B = (0.96, 0.52, 0.09)      # orange
COLOR_CLIP = (0.33, 0.64, 0.29)   # green
COLOR_SCREW = (0.15, 0.15, 0.15)


def cube(x0, x1, y0, y1, z0, z1):
    return mf.Manifold.cube([x1 - x0, y1 - y0, z1 - z0]).translate([x0, y0, z0])


def cyl_z(x, y, z0, z1, d, seg=SEG):
    return mf.Manifold.cylinder(z1 - z0, d / 2, d / 2, seg).translate([x, y, z0])


def tongue_outline(x0, seam, y, reach, width):
    """Rounded tongue: straight from x0 to its round end, which ends `reach` past the seam."""
    end_x = seam + reach - width / 2
    rect = mf.CrossSection.square([end_x - x0, width]).translate([x0, y - width / 2])
    disc = mf.CrossSection.circle(width / 2, SEG).translate([end_x, y])
    return mf.CrossSection.batch_hull([rect, disc])


def tongue(x0, seam, y, reach, width, z0, z1, bottom_chamfer=0.0):
    """Tongue from z0 to z1; a positive chamfer slants its bottom edge in, a negative one flares it out."""
    outline = tongue_outline(x0, seam, y, reach, width)
    body = outline.extrude(z1 - z0).translate([0, 0, z0])
    if bottom_chamfer == 0:
        return body
    c = abs(bottom_chamfer)
    foot = mf.Manifold.batch_hull([layer(outline.offset(-bottom_chamfer, mf.JoinType.Round), z0),
                                   layer(outline, z0 + c)])
    return body - cube(-1e3, 1e3, -1e3, 1e3, z0 - 1, z0 + c) + foot if bottom_chamfer > 0 else body + foot


def round_inset(radius, depth):
    """How far a rounded top edge of `radius` has pulled in at `depth` below the top."""
    if depth >= radius:
        return 0.0
    return radius - math.sqrt(radius * radius - (radius - depth) ** 2)


def boss_round(k, p):
    """Top edge radius from the smoothness slider, limited so the pilot hole keeps its wall."""
    keep = (k["boss_w"] / 2) - (p["pilot_d"] / 2 + PILOT_WALL)
    radius = min(p["boss_smooth"], k["boss_h"] - (k["tab_h"] + LOOSE))
    while radius > 0.25 and round_inset(radius, BOSS_CAP) > keep:
        radius -= 0.25
    return radius


def smooth_boss(outline, height, radius, flare):
    """Outline raised to `height`, flaring into the floor and with a rounded top edge."""
    def layer(shape, z):
        return shape.extrude(0.01).translate([0, 0, z])
    layers = []
    for i in range(SMOOTH_LAYERS + 1):        # quarter-circle flare, concave curve approximated by its chord hull
        angle = i / SMOOTH_LAYERS * math.pi / 2
        layers.append(layer(outline.offset(flare * (1 - math.sin(angle)), mf.JoinType.Round), flare * (1 - math.cos(angle))))
    for i in range(SMOOTH_LAYERS + 1):
        angle = i / SMOOTH_LAYERS * math.pi / 2
        inset = radius * (1 - math.cos(angle))
        z = height - radius + radius * math.sin(angle) - 0.01
        layers.append(layer(outline.offset(-inset, mf.JoinType.Round), z))
    return mf.Manifold.batch_hull(layers)


def floor_ramp(x0, flat, ramp, top, y0, y1):
    """Floor raised to `top` for `flat` mm past x0, then easing down to the floor over `ramp` mm."""
    end = x0 + flat + ramp
    curve = []
    for i in range(1, 96):
        t = i / 96
        # smootherstep: slope and curvature are zero at both ends, so no crease shows at the top or the floor
        ease = t * t * t * (t * (6 * t - 15) + 10)
        curve.append((end - t * ramp, FLOOR + (top - FLOOR) * ease))
    outline = [(x0, 0.0), (end, 0.0), (end, FLOOR)] + curve + [(x0 + flat, top), (x0, top)]
    return mf.CrossSection([outline]).extrude(y1 - y0).rotate([90, 0, 0]).translate([0, y1, 0])


def layer(section, z, thick=0.01):
    return section.extrude(thick).translate([0, 0, z])


def rounded_box_section(x0, x1, y0, y1, radii):
    """Rectangle with its own radius at each corner (x0y0, x1y0, x1y1, x0y1); convex."""
    corners = [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]
    discs = []
    for (cx, cy), r in zip(corners, radii):
        r = max(min(r, (x1 - x0) / 2 - 0.01, (y1 - y0) / 2 - 0.01), 0.05)
        sx = r if cx == x0 else -r
        sy = r if cy == y0 else -r
        discs.append(mf.CrossSection.circle(r, SEG).translate([cx + sx, cy + sy]))
    return mf.CrossSection.batch_hull(discs)


def rim_round(z, H, wall):
    """How far the rounded rim pulls a wall face in (outside) or out (inside) at height z."""
    radius = wall / 2   # fully rounded rim
    return round_inset(radius, H - z) if z > H - radius else 0.0


def inner_inset(z, H, wall):
    """Distance of the inside wall face from the outside of the box at height z (stacking foot, rim)."""
    nest = wall + LOOSE
    z_step = NEST_H + wall * (math.sqrt(2) - 1)
    if z <= z_step:
        inset = nest + wall
    elif z <= z_step + nest:
        inset = nest + wall - (z - z_step)
    else:
        inset = wall
    return inset - rim_round(min(z, H), H, wall)


def shell_solid(H, wall):
    """Outside of the box: stacking foot, 45° step, straight walls, rounded rim; rounded corners.

    The foot and the rest are hulled separately: one hull would turn the foot's vertical step into a slope.
    """
    nest = wall + LOOSE

    def outline(inset, z):
        return layer(rounded_box_section(inset, LENGTH - inset, inset, WIDTH - inset, [CORNER_R - inset] * 4), z)

    foot = mf.Manifold.batch_hull([outline(nest, 0.0), outline(nest, NEST_H - 0.01)])
    upper = [outline(nest, NEST_H - 0.01), outline(0.0, NEST_H + nest)]
    upper += [outline(rim_round(z, H, wall), min(z, H - 0.01)) for z in (H - wall / 2 * (1 - i / 8) for i in range(9))]
    return foot + mf.Manifold.batch_hull(upper)


def cell_pocket(x0, x1, y0, y1, z0, z1, H, wall, floor_fillet=True):
    """One compartment's air. "wall" for a side means the outer wall; numbers are divider faces.

    Built from horizontal layers, so its floor edges and all four vertical corners are rounded.
    """
    z_step = NEST_H + wall * (math.sqrt(2) - 1)
    zs = {z0, z1, z_step, z_step + wall + LOOSE}
    zs |= {H - wall / 2 * (1 - i / 8) for i in range(9)}
    if floor_fillet:
        zs |= {z0 + FLOOR_FILLET * (1 - math.cos(i / 6 * math.pi / 2)) for i in range(7)}
    layers = []
    for z in sorted(z for z in zs if z0 <= z <= z1):
        inset = inner_inset(z, H, wall)
        f = 0.0
        if floor_fillet and z - z0 < FLOOR_FILLET:
            f = FLOOR_FILLET - math.sqrt(max(FLOOR_FILLET ** 2 - (FLOOR_FILLET - (z - z0)) ** 2, 0.0))
        sides = [inset if x0 == "wall" else x0, LENGTH - inset if x1 == "wall" else x1,
                 inset if y0 == "wall" else y0, WIDTH - inset if y1 == "wall" else y1]
        on_wall = [x0 == "wall", x1 == "wall", y0 == "wall", y1 == "wall"]
        radii = [(CORNER_R - inset if on_wall[xi] and on_wall[yi] else CELL_R) - f
                 for xi, yi in ((0, 2), (1, 2), (1, 3), (0, 3))]
        section = rounded_box_section(sides[0] + f, sides[1] - f, sides[2] + f, sides[3] - f, radii)
        layers.append(layer(section, z if z < z1 else z1 - 0.01))
    return mf.Manifold.batch_hull(layers)


def stadium(u_center, v_center, width, height, grow=0.0):
    r = height / 2 + grow
    half = width / 2 - height / 2
    return mf.CrossSection.batch_hull([mf.CrossSection.circle(r, SEG).translate([u_center - half, v_center]),
                                       mf.CrossSection.circle(r, SEG).translate([u_center + half, v_center])])


def along_x(section, x0, x1):
    """Extrude a (y, z) section along x from x0 to x1."""
    return section.extrude(x1 - x0).rotate([90, 0, 0]).rotate([0, 0, 90]).translate([x0, 0, 0])


def hand_hole(p, H, wall, at_start):
    """Stadium hole through one end wall with rounded edges on both faces, and the band around it."""
    zc = H - HANDLE_TOP - p["hand_h"] / 2
    yc = WIDTH / 2
    face_in = wall + BAND_T

    def slab(grow, d0, d1):
        """Stadium grown by `grow`, from d0 to d1 mm in from this end wall."""
        a, b = (d0, d1) if at_start else (LENGTH - d1, LENGTH - d0)
        return along_x(stadium(yc, zc, p["hand_w"], p["hand_h"], grow), a, b)

    band_round = min(HOLE_EDGE_R, BAND_T * 0.8)
    band = mf.Manifold.batch_hull([slab(BAND, -0.5, face_in - band_round),
                                   slab(BAND - band_round, face_in - 0.01, face_in)])
    cutter = slab(0, -1, face_in + 1)
    steps = 8
    for face, inward in ((0.0, 1), (face_in, -1)):
        for i in range(steps):
            a0, a1 = i / steps * math.pi / 2, (i + 1) / steps * math.pi / 2
            g0, g1 = HOLE_EDGE_R * (1 - math.sin(a0)), HOLE_EDGE_R * (1 - math.sin(a1))
            d0 = face + inward * HOLE_EDGE_R * (1 - math.cos(a0))
            d1 = face + inward * HOLE_EDGE_R * (1 - math.cos(a1))
            cutter += mf.Manifold.batch_hull([slab(g0, d0 - 0.005, d0 + 0.005), slab(g1, d1 - 0.005, d1 + 0.005)])
        outside = (face - 1.0, face + 0.005) if inward == 1 else (face - 0.005, face + 1.0)
        cutter += slab(HOLE_EDGE_R, *outside)
    return band, cutter, zc


def ramp_length(p, k):
    """Slope length from the slider, cut short so it ends 5 mm before half B's end wall.

    The screw sits under the flat part, so the slope length never changes how well it holds.
    """
    flat_end = k["seam"] + p["tab_len"] + LOOSE + BOSS_MARGIN
    return min(p["ramp_len"], LENGTH - p["wall"] - 5 - flat_end)


def a_reach(p):
    """How far half A reaches past the seam: its floor tabs, or the top overlap tabs."""
    return max(p["tab_len"], OVERLAP_REACH if p.get("top_joint", 1) >= 0.5 else 0.0)


def seam_choices(p):
    """The halves join on the wall after section 1 or after section 2. Returns {after: seam x}."""
    wall = p["wall"]
    return {1: wall + p["section_1"] + wall,
            2: wall + p["section_1"] + DIVIDER + p["section_2"] + wall}


def pick_seam(p):
    """The seam whose halves both fit the bed, preferring the more even split; None if neither fits."""
    fitting = [(max(x + a_reach(p), LENGTH - x), after, x) for after, x in seam_choices(p).items()
               if x + a_reach(p) <= BED and LENGTH - x <= BED]
    if not fitting:
        return None, None
    _, after, x = min(fitting)
    return after, x


def layout(p):
    """Positions derived from the sliders: seam, section 3 length, screw stack heights."""
    p = {**SCREW, **p}
    wall = p["wall"]
    seam_after, seam = pick_seam(p)
    inner_w = WIDTH - 2 * wall
    section_3 = LENGTH - 4 * wall - DIVIDER - p["section_1"] - p["section_2"]
    counterbore_depth = p["head_h"] + HEAD_CLEAR
    tab_h = counterbore_depth + UNDER_HEAD
    bite = p["screw_len"] - UNDER_HEAD - LOOSE          # thread length inside half B's boss
    pilot_top = tab_h + LOOSE + (LONGEST_SCREW - UNDER_HEAD - LOOSE) + 0.5
    hand_bottom = p["height"] - HANDLE_TOP - p["hand_h"] - BAND
    return dict(seam=seam, seam_after=seam_after, inner_w=inner_w, section_3=section_3, section_3_w=(inner_w - DIVIDER) / 2,
                low_divider=hand_bottom - LOW_DIVIDER_GAP,
                counterbore_depth=counterbore_depth, tab_h=tab_h, bite=bite, pilot_top=pilot_top,
                boss_h=pilot_top + BOSS_CAP, boss_w=p["tab_w"] + 2 * (LOOSE + BOSS_MARGIN))


def parts(p):
    p = {**SCREW, **p}
    L, W, H, wall = LENGTH, WIDTH, p["height"], p["wall"]
    k = layout(p)
    tab_len, tab_w, tab_inset = p["tab_len"], p["tab_w"], p["tab_inset"]
    counterbore_d = p["head_d"] + 2 * LOOSE + HOLE_SHRINK
    if p["section_1"] < MIN_SECTION or p["section_2"] < MIN_SECTION:
        raise ValueError(f"sections must be at least {MIN_SECTION:.0f} mm long")
    if k["seam"] is None:
        raise ValueError(f"no wall between sections splits the box into two halves under {BED:.0f} mm: "
                         "make section 3 shorter or the sections more even")
    LA = k["seam"]
    if k["section_3"] < MIN_SECTION:
        raise ValueError(f"sections 1 + 2 are too long: section 3 would be {k['section_3']:.0f} mm")
    if tab_w < counterbore_d + 2 * 1.2:
        raise ValueError(f"tab is narrower than the screw head needs: at least {counterbore_d + 2.4:.1f} mm")
    if tab_len < tab_w:
        raise ValueError("tab reach must be at least the tab width, so the screw fits on the tab")
    if tab_inset - k["boss_w"] / 2 < wall + LOOSE:
        raise ValueError("floor tabs run into the long walls: raise 'tabs in from long sides'")
    if W - 2 * tab_inset < k["boss_w"]:
        raise ValueError("floor tabs overlap: lower 'tabs in from long sides'")
    if p["hand_w"] + 2 * HOLE_EDGE_R > W - 2 * CORNER_R:
        raise ValueError("hand hole is wider than the flat part of the end wall")
    if k["low_divider"] < 20:
        raise ValueError("box is too low for the hand holes: raise the height or make the hole shorter")
    raised = p["floor_style"] >= 0.5
    ramp_len = ramp_length(p, k)
    if raised and ramp_len < 10:
        raise ValueError("half B is too short for the raised floor: use the round bumps")
    if k["boss_h"] > k["low_divider"]:
        raise ValueError("screw is too long for this box height")

    overlap = p["top_joint"] >= 0.5
    seam_top = H - (DIVIDER_DROP if overlap else SEAM_DROP)
    z_div = H - DIVIDER_DROP - DIVIDER / 2
    z_low = k["low_divider"] - DIVIDER / 2
    shell = shell_solid(H, wall)
    shell_a = shell ^ cube(-1, LA, -1, W + 1, -1, H + 1)
    shell_b = shell ^ cube(LA, L + 1, -1, W + 1, -1, H + 1)

    # Compartments, each its own rounded pocket; dividers are the plastic left between them.
    y_mid0, y_mid1 = W / 2 - DIVIDER / 2, W / 2 + DIVIDER / 2
    if k["seam_after"] == 1:
        divider_x = LA + wall + p["section_2"]
        cells_a = [("wall", LA - wall)]
        cells_b = [(LA + wall, divider_x)]
    else:
        divider_x = wall + p["section_1"]
        cells_a = [("wall", divider_x), (divider_x + DIVIDER, LA - wall)]
        cells_b = []
    s3_x0 = divider_x + DIVIDER if k["seam_after"] == 1 else LA + wall
    air_a = [cell_pocket(x0, x1, "wall", "wall", FLOOR, z_div, H, wall) for x0, x1 in cells_a]
    air_b = [cell_pocket(x0, x1, "wall", "wall", FLOOR, z_div, H, wall) for x0, x1 in cells_b]
    air_b += [cell_pocket(s3_x0, "wall", "wall", y_mid0, FLOOR, z_low, H, wall),
              cell_pocket(s3_x0, "wall", y_mid1, "wall", FLOOR, z_low, H, wall),
              cell_pocket(s3_x0, "wall", "wall", "wall", z_low, z_div, H, wall, floor_fillet=False)]
    air_a.append(cell_pocket("wall", LA - wall, "wall", "wall", z_div, H + 1, H, wall, floor_fillet=False))
    air_b.append(cell_pocket(LA + wall, "wall", "wall", "wall", z_div, H + 1, H, wall, floor_fillet=False))
    a = shell_a - mf.Manifold.batch_boolean(air_a, mf.OpType.Add)
    b = shell_b - mf.Manifold.batch_boolean(air_b, mf.OpType.Add)
    # The seam walls stop below the clip; the cut is wide enough to clear the corner fillets there.
    seam_cut = cube(LA - wall - CELL_R - 1, LA + wall + CELL_R + 1, wall, W - wall, seam_top, H + 1)
    a, b = a - seam_cut, b - seam_cut
    # The first layer spreads on both seam faces and would hold the halves apart: slant those bottom edges.
    c = ELEPHANT_FOOT + 0.1
    seam_slant = mf.CrossSection([[(-c, -1), (c, -1), (c, 0), (0, c), (-c, 0)]])
    seam_slant = seam_slant.extrude(W + 2).rotate([90, 0, 0]).translate([LA, W + 1, 0])
    a, b = a - seam_slant, b - seam_slant

    # Rounded divider tops.
    def top_round_y(x_center, z):
        rod = mf.Manifold.cylinder(W, DIVIDER / 2, DIVIDER / 2, 24).rotate([-90, 0, 0])
        return rod.translate([x_center, 0, z])
    rod_div = top_round_y(divider_x + DIVIDER / 2, z_div)
    rod_low = mf.Manifold.cylinder(L, DIVIDER / 2, DIVIDER / 2, 24).rotate([0, 90, 0]).translate([0, W / 2, z_low])
    rod_low = rod_low ^ cube(s3_x0 - 1, L, -1, W + 1, -1, H + 1)
    if k["seam_after"] == 1:
        b += rod_div ^ shell_b
    else:
        a += rod_div ^ shell_a
    b += rod_low ^ shell_b

    # Hand holes, with a thicker band around each.
    cutters = []
    for at_start in (True, False):
        band, cutter, _ = hand_hole(p, H, wall, at_start)
        if at_start:
            a += band ^ shell_a
        else:
            b += band ^ shell_b
        cutters.append(cutter)
    a, b = a - cutters[0], b - cutters[1]

    # Floor joint.
    if raised:
        b += floor_ramp(LA, tab_len + LOOSE + BOSS_MARGIN, ramp_len, k["boss_h"], wall, W - wall) ^ shell_b
    screws = []
    for y in (tab_inset, W - tab_inset):
        if not raised:
            outline = tongue_outline(LA, LA, y, tab_len + LOOSE + BOSS_MARGIN, k["boss_w"])
            b += smooth_boss(outline, k["boss_h"], boss_round(k, p), FLOOR + p["boss_smooth"]) ^ shell_b
        # Both sit on the bed, where the first layer spreads: slant the tab's bottom edge in and flare the pocket's mouth.
        b -= tongue(LA - 1, LA, y, tab_len + LOOSE, tab_w + 2 * LOOSE, -1, k["tab_h"] + LOOSE)
        b -= tongue(LA - 1, LA, y, tab_len + LOOSE, tab_w + 2 * LOOSE, 0, BED_CHAMFER, bottom_chamfer=-BED_CHAMFER)
        a += tongue(LA, LA, y, tab_len, tab_w, 0, k["tab_h"], bottom_chamfer=BED_CHAMFER)
        sx = LA + tab_len - tab_w / 2
        a -= cyl_z(sx, y, -1, k["tab_h"] + 1, p["screw_d"] + 2 * SLIP + HOLE_SHRINK)
        a -= cyl_z(sx, y, -1, k["counterbore_depth"], counterbore_d)
        b -= cyl_z(sx, y, k["tab_h"], k["pilot_top"], p["pilot_d"] + HOLE_SHRINK)
        head_bottom = k["counterbore_depth"] - p["head_h"]
        screws.append(cyl_z(sx, y, head_bottom, k["counterbore_depth"], p["head_d"])
                      + cyl_z(sx, y, k["counterbore_depth"], k["counterbore_depth"] + p["screw_len"], p["screw_d"], 24))

    if overlap:
        a, b, top_screws = overlap_tabs(p, a, b, shell, shell_b, LA, seam_top, counterbore_d)
        screws += top_screws
        clip, clip_top = None, seam_top
    else:
        # Top clip: rounded U over both seam walls, screwed down into a post at each end of the seam.
        clip_pad = UNDER_HEAD + p["head_h"] + HEAD_CLEAR
        clip_top = seam_top + clip_pad
        gap = p["clip_gap"]
        outer = wall + gap + CLIP_WALL
        profile = mf.CrossSection.compose([
            mf.CrossSection.square([2 * outer, clip_pad]).translate([LA - outer, seam_top]),
            mf.CrossSection.square([CLIP_WALL, p["clip_leg"]]).translate([LA - outer, seam_top - p["clip_leg"]]),
            mf.CrossSection.square([CLIP_WALL, p["clip_leg"]]).translate([LA + wall + gap, seam_top - p["clip_leg"]]),
        ])
        profile = profile.offset(-CLIP_ROUND, mf.JoinType.Round).offset(CLIP_ROUND, mf.JoinType.Round)
        y0, y1 = wall + LOOSE, W - wall - LOOSE
        clip = profile.extrude(y1 - y0).rotate([90, 0, 0]).translate([0, y1, 0])
        # Rounding the profile can sag the slot roof a hair onto the wall tops; cut the slot back square.
        clip -= cube(LA - wall - gap, LA + wall + gap, -1, W + 1, seam_top - p["clip_leg"] - 1, seam_top)
        for y_lo, y_hi in ((wall - 1, wall + POST_LEN), (W - wall - POST_LEN, W - wall + 1)):
            ear_r = counterbore_d / 2 + BED_CHAMFER + EAR_MARGIN
            ys = wall + ear_r + LOOSE if y_lo < W / 2 else W - wall - ear_r - LOOSE   # end tab clears the long wall
            # Over a post only the clip's top remains; its legs would hit the post and the corner fillets.
            clip -= cube(LA - outer - 1, LA + outer + 1, y_lo - 1, y_hi + LOOSE, seam_top - p["clip_leg"] - 1, seam_top)
            # The whole post is in half A's corner, so the screw cuts its thread into one solid piece;
            # a post split across the seam left it a misaligned half-hole in each half.
            xs = LA - wall - POST_W / 2
            post = rounded_box_section(LA - wall - POST_W, LA - wall + 0.5, y_lo, y_hi, [2.0] * 4).extrude(seam_top)
            a += post ^ shell_a
            ear = mf.CrossSection.batch_hull([
                mf.CrossSection.circle(ear_r, SEG).translate([xs, ys]),
                mf.CrossSection.square([0.01, 2 * ear_r]).translate([LA, ys - ear_r])])
            ear_layers = [layer(ear, seam_top), layer(ear, clip_top - CLIP_ROUND)]
            for i in range(1, 7):
                angle = i / 6 * math.pi / 2
                ear_layers.append(layer(ear.offset(-CLIP_ROUND * (1 - math.cos(angle)), mf.JoinType.Round),
                                        clip_top - CLIP_ROUND + CLIP_ROUND * math.sin(angle) - 0.01))
            clip += mf.Manifold.batch_hull(ear_layers)
            a -= cyl_z(xs, ys, seam_top + UNDER_HEAD - LONGEST_SCREW - 0.5, seam_top + 0.01, p["pilot_d"] + HOLE_SHRINK)
            clip -= cyl_z(xs, ys, seam_top - 1, clip_top + 1, p["screw_d"] + 2 * SLIP + HOLE_SHRINK)
            clip -= cyl_z(xs, ys, seam_top + UNDER_HEAD, clip_top + 1, counterbore_d)
            # The clip prints top-down, so this recess opens on the bed side: flare its mouth.
            clip -= mf.Manifold.cylinder(BED_CHAMFER + 0.01, counterbore_d / 2, counterbore_d / 2 + BED_CHAMFER, SEG) \
                .translate([xs, ys, clip_top - BED_CHAMFER])
            head_bottom = seam_top + UNDER_HEAD
            screws.append(cyl_z(xs, ys, head_bottom, head_bottom + p["head_h"], p["head_d"])
                          + cyl_z(xs, ys, head_bottom - p["screw_len"], head_bottom, p["screw_d"], 24))
    for name, shape in (("half A", a), ("half B", b), ("clip", clip)):
        if shape is None:
            continue
        if shape.status() != mf.Error.NoError or shape.volume() <= 0:
            raise ValueError(f"{name} failed to build ({shape.status()}); these settings hit a geometry bug")
    return a, b, clip, screws, dict(clip_top=clip_top, z_low=k["low_divider"])


def overlap_tabs(p, a, b, shell, shell_b, LA, top, counterbore_d):
    """Two tabs on half A's seam wall reach over half B's and are screwed down into seats in half B."""
    W, wall = WIDTH, p["wall"]
    x1 = LA + OVERLAP_REACH
    z_low = top - OVERLAP_TIP - OVERLAP_REACH
    profile = mf.CrossSection([[(LA - 0.01, z_low), (x1, top - OVERLAP_TIP), (x1, top), (LA - 0.01, top)]])
    recess = p["head_h"] + HEAD_CLEAR
    head_bottom = top - recess
    screws = []
    # One tab at each end of the seam; the floor screws and these hold it, the middle of the top edge stays free.
    for ys in (wall + 1 + OVERLAP_W / 2, W - wall - 1 - OVERLAP_W / 2):
        def along_y(section, width):
            return section.extrude(width).rotate([90, 0, 0]).translate([0, ys + width / 2, 0])

        def plan(x0, xe, half_w, r=3.0):
            """Footprint rounded at the far end only; the seam-side corners stay square so tab and room line up."""
            return rounded_box_section(x0, xe, ys - half_w, ys + half_w, [0.05, r, r, 0.05]).extrude(top + 2).translate([0, 0, -1])

        tab = along_y(profile, OVERLAP_W) ^ plan(LA - 1, x1, OVERLAP_W / 2)
        room = (along_y(profile.offset(LOOSE, mf.JoinType.Miter), OVERLAP_W + 2 * LOOSE)
                + cube(LA - 1, x1 + LOOSE, ys - OVERLAP_W / 2 - LOOSE, ys + OVERLAP_W / 2 + LOOSE, top, top + 5)) \
            ^ plan(LA - 0.5, x1 + LOOSE, OVERLAP_W / 2 + LOOSE)
        # Half B's seat hangs off its seam wall: deep enough for the screw, then a 45° underside back to the wall,
        # so it prints without support and doesn't run down to the floor as a column.
        half_w = OVERLAP_W / 2 + OVERLAP_POST_MARGIN
        seat_end = x1 + 2.0
        z_bottom = head_bottom - LONGEST_SCREW - 0.5 - SEAT_FLOOR
        footprint = rounded_box_section(LA, seat_end, ys - half_w, ys + half_w, [0.05, 3.0, 3.0, 0.05])
        wall_strip = rounded_box_section(LA, LA + wall, ys - half_w, ys + half_w, [0.05] * 4)
        seat = (footprint.extrude(top - z_bottom).translate([0, 0, z_bottom])
                + mf.Manifold.batch_hull([layer(footprint, z_bottom),
                                          layer(wall_strip, z_bottom - (seat_end - LA - wall))]))
        a += tab ^ shell
        b += seat ^ shell_b
        b -= room
        xs = LA + overlap_screw_x(p, counterbore_d)
        a -= cyl_z(xs, ys, z_low - 1, top + 1, p["screw_d"] + 2 * SLIP + HOLE_SHRINK)
        a -= cyl_z(xs, ys, head_bottom, top + 1, counterbore_d)
        b -= cyl_z(xs, ys, head_bottom - LONGEST_SCREW - 0.5, top, p["pilot_d"] + HOLE_SHRINK)
        screws.append(cyl_z(xs, ys, head_bottom, head_bottom + p["head_h"], p["head_d"])
                      + cyl_z(xs, ys, head_bottom - p["screw_len"], head_bottom, p["screw_d"], 24))
    return a, b, screws


def overlap_screw_x(p, counterbore_d):
    """Screw distance from the seam: as far out on the tab as its head pocket allows, where the 45° tab is thinnest,
    so less of the screw is spent in half A and more bites into half B."""
    recess = p["head_h"] + HEAD_CLEAR
    return OVERLAP_TIP + OVERLAP_REACH - (recess + POCKET_FLOOR + counterbore_d / 2)


def overlap_bite(p):
    """Thread length of a top screw inside half B's seat."""
    counterbore_d = p["head_d"] + 2 * LOOSE + HOLE_SHRINK
    tab_under_head = OVERLAP_TIP + OVERLAP_REACH - overlap_screw_x(p, counterbore_d) - (p["head_h"] + HEAD_CLEAR)
    return p["screw_len"] - tab_under_head - LOOSE * math.sqrt(2)


def build(**p):
    a, b, clip, screws, _ = parts(p)
    e = p["explode"]
    show = int(round(p["show"]))
    if show == 3 and clip is None:
        raise ValueError("there is no clip with overlap tabs: pick another 'Show' option")
    pieces = {1: [(a, COLOR_A)], 2: [(b, COLOR_B)], 3: [(clip, COLOR_CLIP)]}.get(show)
    if pieces is None:
        pieces = [(a, COLOR_A), (b.translate([e, 0, 0]), COLOR_B)]
        if clip is not None:
            pieces.append((clip.translate([0, 0, e]), COLOR_CLIP))
        floor_screws, clip_screws = screws[:2], screws[2:]
        pieces += [(s.translate([e, 0, -e]), COLOR_SCREW) for s in floor_screws]
        pieces += [(s.translate([0, 0, 1.6 * e]), COLOR_SCREW) for s in clip_screws]
    vertices, triangles, colors, offset = [], [], [], 0
    for shape, color in pieces:
        mesh = shape.to_mesh()
        v = np.asarray(mesh.vert_properties)[:, :3]
        t = np.asarray(mesh.tri_verts)
        vertices.append(v)
        triangles.append(t + offset)
        colors.append(np.tile(color, (len(t), 1)))
        offset += len(v)
    return np.vstack(vertices), np.vstack(triangles), np.vstack(colors)


def stats(p: dict[str, float]) -> dict[str, str]:
    p = {**SCREW, **p}
    k = layout(p)
    L, W, H = LENGTH, WIDTH, p["height"]
    sections = {
        "section 1": f"{p['section_1']:.0f} x {k['inner_w']:.0f} mm",
        "section 2": f"{p['section_2']:.0f} x {k['inner_w']:.0f} mm",
        "section 3a / 3b": f"{k['section_3']:.0f} x {k['section_3_w']:.0f} mm each, divider {k['low_divider'] - FLOOR:.0f} mm tall",
        "usable height": f"{H - FLOOR:.0f} mm (dividers {H - DIVIDER_DROP - FLOOR:.0f})",
        "hand holes": f"{p['hand_w']:.0f} x {p['hand_h']:.0f} mm, top {HANDLE_TOP:.0f} mm below the rim",
    }
    if k["seam"] is None:
        return {**sections, "halves": f"no section wall gives two halves under {BED:.0f} mm"}
    after = k["seam_after"]
    half_a = k["seam"] + a_reach(p)
    half_b = L - k["seam"]
    bite_ok = "ok" if k["bite"] >= 2 * p["screw_d"] else f"short, aim for {2 * p['screw_d']:.0f}+ mm"
    overlap = p.get("top_joint", 1) >= 0.5
    top_count = 2
    ramp = ramp_length(p, k)
    anchor = (f"floor raised {k['boss_h']:.1f} mm for {p['tab_len'] + LOOSE + BOSS_MARGIN:.0f} mm, "
              f"sloping down over {ramp:.0f} mm (steepest {math.degrees(math.atan(1.875 * (k['boss_h'] - FLOOR) / ramp)):.0f}°)"
              if p["floor_style"] >= 0.5 else f"two bumps {k['boss_h']:.1f} mm tall, top edge radius {boss_round(k, p):.2f} mm")
    return {
        **sections,
        "halves join": f"between section {after} and {after + 1}",
        "half A print size": f"{half_a:.0f} x {W:.0f} x {H:.0f} mm (sections {'1' if after == 1 else '1 + 2'})",
        "half B print size": f"{half_b:.0f} x {W:.0f} x {H:.0f} mm (sections {'2 + 3' if after == 1 else '3'})",
        "screw bite": f"{k['bite']:.1f} mm, {bite_ok}",
        f"screw anchor in section {after + 1}": anchor,
        "outer size": f"{L:.0f} x {W:.0f} x {H:.0f} mm",
        "hardware": (f"{2 + top_count}x 3 mm self-tapping (ST{p['screw_d']:g}) x 12-13 mm, pan, flat or round head: "
                     f"2 floor, {top_count} top" + ("" if overlap else "; 1 clip")),
        "top screw bite": (f"{overlap_bite(p):.1f} mm into half B's posts" if overlap
                           else f"{p['screw_len'] - UNDER_HEAD:.1f} mm into half A's posts"),
        "screw holes": f"pilot {p['pilot_d']:.1f} mm, clearance {p['screw_d'] + 2 * SLIP:.1f} mm, head pocket {p['head_d'] + 2 * LOOSE:.1f} mm wide x {p['head_h'] + HEAD_CLEAR:.1f} mm deep",
    }
