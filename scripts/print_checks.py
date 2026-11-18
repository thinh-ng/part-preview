"""Checks on assembled parts that a slicer preview cannot catch, run before every export.

A face printed over air (flatter than 45°, above the bed) droops a few tenths of a mm on its first layer. If that
face rests on another part with no gap, the droop props the joint open. Found on the dog box's top tabs.
"""
import numpy as np
import trimesh

LAYER = 0.2
OVERHANG_NZ = -0.72        # face normal z below this: flatter than 45° from horizontal (a 45° chamfer passes)
BED_Z = 0.3                # faces lower than this sit on the bed
MIN_AREA = 1.0             # mm²; smaller groups are mesh slivers


def _groups(mesh, faces):
    sub = mesh.submesh([faces], append=True)
    return sub.split(only_watertight=False) if len(sub.faces) else []


def overhang_contacts(parts):
    """Overhangs resting on another part with less than one layer of gap.

    parts: {name: trimesh in assembled position}. Returns (contacts, free): lists of
    (part, area mm², centre xyz, gap mm or None) for overhangs that touch another part and that touch nothing.
    """
    contacts, free = [], []
    for name, mesh in parts.items():
        down = np.where((mesh.face_normals[:, 2] < OVERHANG_NZ) & (mesh.triangles_center[:, 2] > BED_Z))[0]
        for group in _groups(mesh, down):
            if group.area < MIN_AREA:
                continue
            origins = group.triangles_center + [0, 0, 0.05]
            gap = None
            for other_name, other in parts.items():
                if other_name == name:
                    continue
                hits, rays, _ = other.ray.intersects_location(origins, np.tile([0, 0, -1], (len(origins), 1)),
                                                              multiple_hits=False)
                if len(hits):
                    d = float((origins[rays, 2] - hits[:, 2]).min()) - 0.05
                    gap = d if gap is None else min(gap, d)
            centre = group.triangles_center.mean(axis=0).round(1).tolist()
            entry = (name, round(float(group.area), 1), centre, None if gap is None else abs(round(gap, 2)))
            (contacts if gap is not None and gap < LAYER - 0.01 else free).append(entry)
    return contacts, free


def require_no_overhang_contacts(parts):
    """Print every overhang; raise if one rests on another part with less than one layer of gap."""
    contacts, free = overhang_contacts(parts)
    for name, area, centre, gap in free:
        print(f"  overhang {name}: {area} mm² at {centre}" + ("" if gap is None else f", {gap} mm above another part"))
    for name, area, centre, gap in contacts:
        print(f"  FAIL {name}: {area} mm² printed over air at {centre} rests {gap} mm above another part")
    if contacts:
        raise SystemExit("Overhang used as a contact face: its first layer droops and props the joint open. "
                         f"Chamfer it to 45° or give it {LAYER} mm (one layer) of gap. No 3MF written.")
