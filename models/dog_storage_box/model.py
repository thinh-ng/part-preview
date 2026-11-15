"""Dog storage box, printed as two halves that fit a 256 mm bed.

Half A holds section 1; half B holds section 2 and section 3 (split in two). Half A's floor tabs
slide under half B and self-tapping screws go up from below into blind holes in two bosses.
A U clip pushed over the double seam wall keeps the top together. Clearances are
tolerances.json starting values, not yet measured on the printer.
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
    dict(key="section_3a", label="Section 3a width (mm); 3b gets the rest", min=15, max=230, step=0.5, default=59.5),
    dict(key="wall", label="Wall thickness (mm)", min=1.26, max=4.2, step=0.42, default=2.1),
    dict(key="tab_len", label="Floor tab reach under B (mm)", min=8, max=30, step=0.5, default=10.0),
    dict(key="tab_w", label="Floor tab width (mm)", min=8, max=24, step=0.5, default=10.0),
    dict(key="tab_inset", label="Tabs in from long sides (mm)", min=10, max=50, step=1, default=25.0),
    dict(key="floor_style", label="Screw anchor", min=0, max=1, step=1, default=1,
         options=["Two round bumps", "Raised floor sloping away"]),
    dict(key="ramp_len", label="Raised floor slope length (mm): longer is gentler; runs under dividers, capped at half B's end", min=10, max=300, step=1, default=120.0),
    dict(key="boss_smooth", label="Round bump smoothness (mm)", min=0.5, max=6, step=0.25, default=4.0),
    dict(key="pattern", label="Wall pattern", min=0, max=4, step=1, default=1,
         options=["Solid", "Hexagon", "Vertical slots", "Diamond", "Round"]),
    dict(key="hole_size", label="Pattern hole size (mm)", min=4, max=40, step=0.5, default=12.0),
    dict(key="bar", label="Pattern bar width between holes (mm)", min=1.5, max=10, step=0.1, default=3.0),
    dict(key="border", label="Solid border around patterns (mm)", min=3, max=25, step=0.5, default=8.0),
    dict(key="clip_leg", label="Top clip reach down (mm)", min=4, max=20, step=0.5, default=8.0),
    dict(key="clip_gap", label="Top clip gap per side (mm)", min=0.0, max=0.4, step=0.05, default=0.10),
    dict(key="explode", label="Explode view (mm)", min=0, max=80, step=1, default=0.0),
    dict(key="show", label="Show", min=0, max=3, step=1, default=0,
         options=["Whole box", "Half A only", "Half B only", "Top clip only"]),
]

LENGTH = 375.0              # owner: must fit the space exactly
WIDTH = 125.0               # owner: must fit the space exactly
BED = 256.0                 # /printer bed, extruder 1
BED_Z = 261.0
FLOOR = 1.6                 # 8 layers at 0.2
DIVIDER = 1.68              # 4 lines at 0.42
LOOSE, SLIP = 0.30, 0.20    # tolerances.json starting values (not yet measured)
HOLE_SHRINK = 0.15
NEST_H = 4.0                # stacking step for future boxes
DIVIDER_DROP = 5.0
SEAM_DROP = 8.0             # seam walls stop this far below the rim, room for the clip
UNDER_HEAD = 1.5            # tab plastic the screw head clamps
BOSS_MARGIN = 1.68          # 4 lines of plastic around the tab pocket
BOSS_CAP = 1.2              # closed top over the pilot hole, so nothing shows inside
PILOT_WALL = 1.2            # plastic kept around the pilot hole where the boss top is rounded
SMOOTH_LAYERS = 16
CLIP_WALL, CLIP_TOP = 1.6, 1.6
MIN_SECTION = 15.0
SEG = 48
# Self-tapping screw, starting sizes for a common M3 x 8 pan head (owner's screw not yet measured)
SCREW = dict(screw_d=3.0, screw_len=8.0, head_d=5.7, head_h=2.4, pilot_d=2.5)
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


def tongue(x0, seam, y, reach, width, z0, z1):
    return tongue_outline(x0, seam, y, reach, width).extrude(z1 - z0).translate([0, 0, z0])


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


def stepped(L, W, inset_low, inset_high, z0, z_step, rise, z_top):
    """Block whose bottom part is inset, widening at 45° to the full size."""
    def slab(inset, za, zb):
        return cube(inset, L - inset, inset, W - inset, za, zb)
    thin = 0.01
    ramp = mf.Manifold.batch_hull([slab(inset_low, z_step, z_step + thin), slab(inset_high, z_step + rise - thin, z_step + rise)])
    return slab(inset_low, z0, z_step) + ramp + slab(inset_high, z_step + rise, z_top)


def pattern_holes(kind, size, bar, u0, u1, v0, v1):
    """Holes of one pattern, centred in the panel u0..u1 x v0..v1, each fully inside it.

    Every hole's top is pointed at 45° or steeper so the wall prints upright without support.
    """
    if u1 - u0 < size or v1 - v0 < size:
        return None
    r = size / 2
    if kind == 1:      # hexagon, point up
        shape = mf.CrossSection.circle(r, 6).rotate(90)
        half_w, down, up = r * math.sqrt(3) / 2, r, r
        pitch_u = 2 * half_w + bar
        pitch_v, stagger = pitch_u * math.sqrt(3) / 2, True
    elif kind == 2:    # vertical slot over the full panel height, pointed top
        h = v1 - v0
        shape = mf.CrossSection([[(-r, -h / 2), (r, -h / 2), (r, h / 2 - r), (0, h / 2), (-r, h / 2 - r)]])
        half_w, down, up = r, h / 2, h / 2
        pitch_u, pitch_v, stagger = size + bar, h + 1, False
    elif kind == 3:    # diamond lattice
        shape = mf.CrossSection([[(0, -r), (r, 0), (0, r), (-r, 0)]])
        half_w, down, up = r, r, r
        pitch_u = size + bar * math.sqrt(2)
        pitch_v, stagger = pitch_u / 2, True
    else:              # round, with a 45° point on top
        tip = mf.CrossSection.square([0.01, 0.01], center=True).translate([0, r * math.sqrt(2)])
        shape = mf.CrossSection.batch_hull([mf.CrossSection.circle(r, SEG), tip])
        half_w, down, up = r, r, r * math.sqrt(2)
        pitch_u = size + bar
        pitch_v, stagger = pitch_u * math.sqrt(3) / 2, True
    uc, vc = (u0 + u1) / 2, (v0 + v1) / 2 + (down - up) / 2
    rows = int((v1 - v0) / pitch_v) + 2
    cols = int((u1 - u0) / pitch_u) + 2
    holes = []
    for j in range(-rows, rows + 1):
        v = vc + j * pitch_v
        shift = pitch_u / 2 if stagger and j % 2 else 0.0
        for i in range(-cols, cols + 1):
            u = uc + i * pitch_u + shift
            if u - half_w >= u0 and u + half_w <= u1 and v - down >= v0 and v + up <= v1:
                holes.append(shape.translate([u, v]))
    return mf.CrossSection.compose(holes) if holes else None


def panels(bands, lo, hi, border):
    """Gaps between solid bands (wall junctions) along one wall, shrunk by the border."""
    edges = sorted(bands)
    out = []
    for (_, end), (start, _) in zip(edges, edges[1:]):
        if start - end - 2 * border > 0:
            out.append((end + border, start - border))
    return [(u0, u1) for u0, u1 in out if lo <= u0 and u1 <= hi]


def wall_cutter(p, wall, H, x_bands, y_bands_end):
    """Pattern cutouts through the four outer walls, solid near every junction, rim and stacking step."""
    if p["pattern"] < 0.5:
        return None
    kind, size, bar, border = int(round(p["pattern"])), p["hole_size"], p["bar"], p["border"]
    v0, v1 = NEST_H + wall + LOOSE + border, H - border
    depth = wall + 0.55
    cutters = []
    for u0, u1 in panels(x_bands, 0, LENGTH, border):          # long walls, u along x
        holes = pattern_holes(kind, size, bar, u0, u1, v0, v1)
        if holes is None:
            continue
        slab = holes.extrude(depth).rotate([90, 0, 0])            # (u, v, w) -> (u, -w, v)
        cutters += [slab.translate([0, wall + 0.05, 0]), slab.translate([0, WIDTH + 0.5, 0])]
    for x_end, y_bands in y_bands_end:                            # end walls, u along y
        for u0, u1 in panels(y_bands, 0, WIDTH, border):
            holes = pattern_holes(kind, size, bar, u0, u1, v0, v1)
            if holes is None:
                continue
            slab = holes.extrude(depth).rotate([90, 0, 0]).rotate([0, 0, 90])   # -> (w, u, v)
            cutters.append(slab.translate([x_end, 0, 0]))
    return mf.Manifold.batch_boolean(cutters, mf.OpType.Add) if cutters else None


def ramp_length(p, k):
    """Slope length from the slider, cut short so it ends 5 mm before half B's end wall.

    The screw sits under the flat part, so the slope length never changes how well it holds.
    """
    flat_end = k["seam"] + p["tab_len"] + LOOSE + BOSS_MARGIN
    return min(p["ramp_len"], LENGTH - p["wall"] - 5 - flat_end)


def seam_choices(p):
    """The halves join on the wall after section 1 or after section 2. Returns {after: seam x}."""
    wall = p["wall"]
    return {1: wall + p["section_1"] + wall,
            2: wall + p["section_1"] + DIVIDER + p["section_2"] + wall}


def pick_seam(p):
    """The seam whose halves both fit the bed, preferring the more even split; None if neither fits."""
    fitting = [(max(x + p["tab_len"], LENGTH - x), after, x) for after, x in seam_choices(p).items()
               if x + p["tab_len"] <= BED and LENGTH - x <= BED]
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
    counterbore_depth = p["head_h"] + 0.5
    tab_h = counterbore_depth + UNDER_HEAD
    bite = p["screw_len"] - UNDER_HEAD - LOOSE          # thread length inside half B's boss
    pilot_top = tab_h + LOOSE + bite + 0.5
    return dict(seam=seam, seam_after=seam_after, inner_w=inner_w, section_3=section_3, section_3b=inner_w - DIVIDER - p["section_3a"],
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
    if k["section_3b"] < MIN_SECTION:
        raise ValueError(f"section 3a is too wide: 3b would be {k['section_3b']:.0f} mm")
    if tab_w < counterbore_d + 2 * 1.2:
        raise ValueError(f"tab is narrower than the screw head needs: at least {counterbore_d + 2.4:.1f} mm")
    if tab_len < tab_w:
        raise ValueError("tab reach must be at least the tab width, so the screw fits on the tab")
    if tab_inset - k["boss_w"] / 2 < wall + LOOSE:
        raise ValueError("floor tabs run into the long walls: raise 'tabs in from long sides'")
    if W - 2 * tab_inset < k["boss_w"]:
        raise ValueError("floor tabs overlap: lower 'tabs in from long sides'")
    if p["pilot_d"] >= p["screw_d"]:
        raise ValueError("pilot hole must be smaller than the screw thread, or the screw has nothing to bite")
    raised = p["floor_style"] >= 0.5
    ramp_len = ramp_length(p, k)
    if raised and ramp_len < 10:
        raise ValueError("half B is too short for the raised floor: use the round bumps")
    if k["boss_h"] > H - DIVIDER_DROP:
        raise ValueError("screw is too long for this box height")

    nest_inset = wall + LOOSE
    seam_top = H - SEAM_DROP
    shell = stepped(L, W, nest_inset, 0, 0, NEST_H, nest_inset, H)
    pocket = stepped(L, W, nest_inset + wall, wall, FLOOR, NEST_H + wall * (math.sqrt(2) - 1), nest_inset, H + 1)
    shell_a = shell ^ cube(-1, LA, -1, W + 1, -1, H + 1)
    shell_b = shell ^ cube(LA, L + 1, -1, W + 1, -1, H + 1)
    a = shell_a - (pocket ^ cube(-1, LA - wall, -1, W + 1, -1, H + 2))
    b = shell_b - (pocket ^ cube(LA + wall, L + 1, -1, W + 1, -1, H + 2))
    seam_cut = cube(LA - wall, LA + wall, wall, W - wall, seam_top, H + 1)
    a, b = a - seam_cut, b - seam_cut

    y_split = wall + p["section_3a"]
    if k["seam_after"] == 1:
        x = LA + wall + p["section_2"]
        b += cube(x, x + DIVIDER, -1, W + 1, 0, H - DIVIDER_DROP) ^ shell_b
        section_3_x0 = x + DIVIDER
    else:
        x = wall + p["section_1"]
        a += cube(x, x + DIVIDER, -1, W + 1, 0, H - DIVIDER_DROP) ^ shell_a
        section_3_x0 = LA + wall
    b += cube(section_3_x0, L - wall, y_split, y_split + DIVIDER, 0, H - DIVIDER_DROP) ^ shell_b

    divider_x = LA + wall + p["section_2"] if k["seam_after"] == 1 else wall + p["section_1"]
    x_bands = [(0, wall), (LA - wall, LA + wall), (divider_x, divider_x + DIVIDER), (L - wall, L)]
    y_walls = [(0, wall), (W - wall, W)]
    cutter = wall_cutter(p, wall, H, x_bands, [(-0.5, y_walls), (L - wall - 0.05, y_walls + [(y_split, y_split + DIVIDER)])])
    if cutter is not None:
        a, b = a - cutter, b - cutter

    if raised:
        b += floor_ramp(LA, tab_len + LOOSE + BOSS_MARGIN, ramp_len, k["boss_h"], wall, W - wall) ^ shell_b
    screws = []
    for y in (tab_inset, W - tab_inset):
        if not raised:
            outline = tongue_outline(LA, LA, y, tab_len + LOOSE + BOSS_MARGIN, k["boss_w"])
            b += smooth_boss(outline, k["boss_h"], boss_round(k, p), FLOOR + p["boss_smooth"]) ^ shell_b
        b -= tongue(LA - 1, LA, y, tab_len + LOOSE, tab_w + 2 * LOOSE, -1, k["tab_h"] + LOOSE)
        a += tongue(LA, LA, y, tab_len, tab_w, 0, k["tab_h"])
        sx = LA + tab_len - tab_w / 2
        a -= cyl_z(sx, y, -1, k["tab_h"] + 1, p["screw_d"] + 2 * SLIP + HOLE_SHRINK)
        a -= cyl_z(sx, y, -1, k["counterbore_depth"], counterbore_d)
        b -= cyl_z(sx, y, k["tab_h"], k["pilot_top"], p["pilot_d"] + HOLE_SHRINK)
        head_bottom = k["counterbore_depth"] - p["head_h"]
        screws.append(cyl_z(sx, y, head_bottom, k["counterbore_depth"], p["head_d"])
                      + cyl_z(sx, y, k["counterbore_depth"], k["counterbore_depth"] + p["screw_len"], p["screw_d"], 24))

    inner = 2 * wall + 2 * p["clip_gap"]
    clip = (cube(LA - inner / 2 - CLIP_WALL, LA + inner / 2 + CLIP_WALL, wall + LOOSE, W - wall - LOOSE,
                 seam_top - p["clip_leg"], seam_top + CLIP_TOP)
            - cube(LA - inner / 2, LA + inner / 2, -1, W + 1, seam_top - p["clip_leg"] - 1, seam_top))
    return a, b, clip, screws


def build(**p):
    a, b, clip, screws = parts(p)
    e = p["explode"]
    pieces = {1: [(a, COLOR_A)], 2: [(b, COLOR_B)], 3: [(clip, COLOR_CLIP)]}.get(int(round(p["show"])))
    if pieces is None:
        pieces = [(a, COLOR_A), (b.translate([e, 0, 0]), COLOR_B), (clip.translate([0, 0, e]), COLOR_CLIP)]
        pieces += [(s.translate([e, 0, -e]), COLOR_SCREW) for s in screws]
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
        "section 3a": f"{k['section_3']:.0f} x {p['section_3a']:.0f} mm",
        "section 3b": f"{k['section_3']:.0f} x {k['section_3b']:.0f} mm",
        "usable height": f"{H - FLOOR:.0f} mm (dividers {H - DIVIDER_DROP - FLOOR:.0f})",
    }
    if k["seam"] is None:
        return {**sections, "halves": f"no section wall gives two halves under {BED:.0f} mm"}
    after = k["seam_after"]
    half_a = k["seam"] + p["tab_len"]
    half_b = L - k["seam"]
    bite_ok = "ok" if k["bite"] >= 2 * p["screw_d"] else f"short, aim for {2 * p['screw_d']:.0f}+ mm"
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
        "hardware": f"2x self-tapping {p['screw_d']:g} x {p['screw_len']:.0f} mm",
    }
