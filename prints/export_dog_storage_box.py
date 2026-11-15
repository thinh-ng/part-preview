"""Export the dog storage box as print-ready 3MF plates from a part-preview server's saved slider values.

Needs numpy, manifold3d, trimesh and lxml:  python prints/export_dog_storage_box.py [server URL]
"""
import json
import sys
import urllib.request
from pathlib import Path

import numpy as np
import trimesh

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "models" / "dog_storage_box"))
import model  # noqa: E402

OUT = HERE / "dog-storage-box"
GAP = 10.0
SERVER = sys.argv[1] if len(sys.argv) > 1 else "http://pi4.local:8765"

schema = json.load(urllib.request.urlopen(f"{SERVER}/api/schema?model=dog_storage_box", timeout=10))
values = schema["values"]
a, b, clip, _screws, caps, _info = model.parts(dict(values))


def to_trimesh(shape):
    mesh = shape.to_mesh()
    return trimesh.Trimesh(np.asarray(mesh.vert_properties)[:, :3], np.asarray(mesh.tri_verts), process=True)


def on_bed(mesh, x, y):
    """Move a mesh so its lowest point sits on z=0 and its min corner is at (x, y)."""
    lo = mesh.bounds[0]
    mesh.apply_translation([x - lo[0], y - lo[1], -lo[2]])
    return mesh


half_a, half_b = to_trimesh(a), to_trimesh(b)
clip_mesh = to_trimesh(clip)
clip_mesh.apply_transform(trimesh.transformations.rotation_matrix(np.pi, [1, 0, 0]))  # flat top on the bed, legs up
cap_meshes = [to_trimesh(c) for c in caps]

on_bed(half_a, 0, 0)
on_bed(clip_mesh, half_a.bounds[1][0] + GAP, 0)
x_caps = clip_mesh.bounds[1][0] + GAP
for i, cap in enumerate(cap_meshes):
    on_bed(cap, x_caps, i * (cap.extents[1] + GAP))
on_bed(half_b, 0, 0)

OUT.mkdir(parents=True, exist_ok=True)
plates = {
    "dog-storage-box_plate1_halfA-clip-caps.3mf": {"half A": half_a, "top clip": clip_mesh,
                                                    "screw cap 1": cap_meshes[0], "screw cap 2": cap_meshes[1]},
    "dog-storage-box_plate2_halfB.3mf": {"half B": half_b},
}
for name, parts in plates.items():
    scene = trimesh.Scene()
    for label, mesh in parts.items():
        assert mesh.is_watertight, f"{label} is not watertight"
        scene.add_geometry(mesh, node_name=label, geom_name=label)
    (OUT / name).write_bytes(trimesh.exchange.threemf.export_3MF(scene))
    lo, hi = scene.bounds
    print(f"{name}: {len(parts)} objects, footprint {hi[0] - lo[0]:.1f} x {hi[1] - lo[1]:.1f} x {hi[2] - lo[2]:.1f} mm")
    for label, mesh in parts.items():
        print(f"  {label}: {mesh.extents.round(1).tolist()} mm, {mesh.volume / 1000:.1f} cm3")
(OUT / "settings.json").write_text(json.dumps(values, indent=1), encoding="utf-8")
print("values", values)

# Test piece: just the seam, both halves, full height so the clip, screws, caps and tabs are all tested.
LA = model.layout({**model.SCREW, **values})["seam"]
test_a = to_trimesh(a ^ model.cube(LA - 20, LA, -1, model.WIDTH + 1, -1, 300))
test_b = to_trimesh(b ^ model.cube(LA, LA + 35, -1, model.WIDTH + 1, -1, 300))
test_clip = to_trimesh(clip)
test_clip.apply_transform(trimesh.transformations.rotation_matrix(np.pi, [1, 0, 0]))
test_caps = [to_trimesh(c) for c in caps]
on_bed(test_a, 0, 0)
on_bed(test_b, test_a.bounds[1][0] + GAP, 0)
on_bed(test_clip, test_b.bounds[1][0] + GAP, 0)
for i, cap in enumerate(test_caps):
    on_bed(cap, test_clip.bounds[1][0] + GAP, i * (cap.extents[1] + GAP))
scene = trimesh.Scene()
for label, mesh in {"seam test half A": test_a, "seam test half B": test_b, "top clip": test_clip,
                    "screw cap 1": test_caps[0], "screw cap 2": test_caps[1]}.items():
    assert mesh.is_watertight, label
    scene.add_geometry(mesh, node_name=label, geom_name=label)
(OUT / "dog-storage-box_TEST_seam.3mf").write_bytes(trimesh.exchange.threemf.export_3MF(scene))
print("test piece:", round(test_a.volume / 1000 + test_b.volume / 1000 + test_clip.volume / 1000, 1), "cm3",
      "footprint", (scene.bounds[1] - scene.bounds[0]).round(1).tolist())
