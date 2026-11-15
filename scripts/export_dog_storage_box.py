"""Export the dog storage box as one Bambu Studio 3MF with two plates, from a part-preview server's saved values.

Plate 1 is a seam test strip (print it first), plate 2 is the whole box. The file layout copies what
Bambu Studio itself writes (wrapper objects, one mesh file per part, plates in model_settings.config).

Needs numpy, manifold3d and trimesh:  python scripts/export_dog_storage_box.py [server URL]
"""
import json
import sys
import urllib.request
import zipfile
from pathlib import Path
from xml.sax.saxutils import escape

import numpy as np
import trimesh

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "models" / "dog_storage_box"))
import model  # noqa: E402

OUT = HERE.parent / "prints" / "dog-storage-box" / "dog-storage-box.3mf"
SERVER = sys.argv[1] if len(sys.argv) > 1 else "http://pi4.local:8765"
BED = 256.0
PLATE_STRIDE = BED * 1.2      # Bambu Studio puts plate n+1 this far to the right of plate n
EDGE = 1.5                    # distance from the plate edge
GAP = 3.0                     # between parts on a plate

values = json.load(urllib.request.urlopen(f"{SERVER}/api/schema?model=dog_storage_box", timeout=10))["values"]
a, b, clip, _screws, caps, _info = model.parts(dict(values))
seam = model.layout({**model.SCREW, **values})["seam"]


def mesh_of(shape, flip=False):
    m = shape.to_mesh()
    mesh = trimesh.Trimesh(np.asarray(m.vert_properties)[:, :3], np.asarray(m.tri_verts), process=True)
    if flip:  # clip: flat top on the bed, legs up
        mesh.apply_transform(trimesh.transformations.rotation_matrix(np.pi, [1, 0, 0]))
    assert mesh.is_watertight
    lo, hi = mesh.bounds
    mesh.apply_translation([-(lo[0] + hi[0]) / 2, -(lo[1] + hi[1]) / 2, -lo[2]])  # centred, on z=0
    return mesh


def row(parts, y0, x0=EDGE):
    """Lay parts left to right starting at (x0, y0); returns [(name, mesh, centre_x, centre_y)]."""
    placed, x = [], x0
    for name, mesh in parts:
        w, d = mesh.extents[:2]
        placed.append((name, mesh, x + w / 2, y0 + d / 2))
        x += w + GAP
    assert x - GAP <= BED - EDGE + 1e-6, f"row too wide: {x - GAP:.1f} mm"
    return placed


caps_mesh = [mesh_of(c) for c in caps]
test = row([("seam test half A", mesh_of(a ^ model.cube(seam - 20, seam, -1, model.WIDTH + 1, -1, 300))),
            ("seam test half B", mesh_of(b ^ model.cube(seam, seam + 35, -1, model.WIDTH + 1, -1, 300))),
            ("top clip (test)", mesh_of(clip, flip=True)),
            ("screw cap (test) 1", caps_mesh[0]), ("screw cap (test) 2", caps_mesh[1].copy())], EDGE)
half_b = mesh_of(b)
box = row([("half B", half_b)], EDGE)
box += row([("half A", mesh_of(a)), ("top clip", mesh_of(clip, flip=True)),
            ("screw cap 1", caps_mesh[0].copy()), ("screw cap 2", caps_mesh[1].copy())], EDGE + half_b.extents[1] + GAP)
assert max(cy + m.extents[1] / 2 for _, m, _, cy in box) <= BED - EDGE + 1e-6, "box does not fit one plate"
plates = [("Seam test - print first", test), ("Dog storage box", box)]

files, items, rels, objects_cfg, plates_cfg = {}, [], [], [], []
next_id = 1
for plate_index, (plate_name, parts) in enumerate(plates):
    instances = []
    for name, mesh, cx, cy in parts:
        mesh_id, wrapper_id = next_id, next_id + 1
        next_id += 2
        vertices = "".join(f'<vertex x="{x:.4f}" y="{y:.4f}" z="{z:.4f}"/>' for x, y, z in mesh.vertices)
        triangles = "".join(f'<triangle v1="{i}" v2="{j}" v3="{k}"/>' for i, j, k in mesh.faces)
        path = f"3D/Objects/object_{mesh_id}.model"
        files[path] = ('<?xml version="1.0" encoding="UTF-8"?>\n'
                       '<model unit="millimeter" xml:lang="en-US" xmlns="http://schemas.microsoft.com/3dmanufacturing/core/2015/02">'
                       f'<resources><object id="{mesh_id}" type="model"><mesh><vertices>{vertices}</vertices>'
                       f'<triangles>{triangles}</triangles></mesh></object></resources><build/></model>')
        rels.append(f'<Relationship Target="/{path}" Id="rel-{len(rels) + 1}" '
                    'Type="http://schemas.microsoft.com/3dmanufacturing/2013/01/3dmodel"/>')
        items.append((wrapper_id, mesh_id, path, cx + plate_index * PLATE_STRIDE, cy))
        label = escape(name, {'"': "&quot;"})
        objects_cfg.append(f'<object id="{wrapper_id}"><metadata key="name" value="{label}"/>'
                           '<metadata key="extruder" value="1"/>'
                           f'<part id="{mesh_id}" subtype="normal_part"><metadata key="name" value="{label}"/>'
                           '<metadata key="matrix" value="1 0 0 0 0 1 0 0 0 0 1 0 0 0 0 1"/></part></object>')
        instances.append(f'<model_instance><metadata key="object_id" value="{wrapper_id}"/>'
                         '<metadata key="instance_id" value="0"/></model_instance>')
    plates_cfg.append(f'<plate><metadata key="plater_id" value="{plate_index + 1}"/>'
                      f'<metadata key="plater_name" value="{escape(plate_name)}"/>'
                      '<metadata key="locked" value="false"/>' + "".join(instances) + "</plate>")

main = ('<?xml version="1.0" encoding="UTF-8"?>\n'
        '<model unit="millimeter" xml:lang="en-US" xmlns="http://schemas.microsoft.com/3dmanufacturing/core/2015/02" '
        'xmlns:BambuStudio="http://schemas.bambulab.com/package/2021" '
        'xmlns:p="http://schemas.microsoft.com/3dmanufacturing/production/2015/06" requiredextensions="p">'
        '<metadata name="Application">BambuStudio-02.08.02.61</metadata>'
        '<metadata name="BambuStudio:3mfVersion">1</metadata>'
        '<metadata name="Title">Dog storage box</metadata><resources>'
        + "".join(f'<object id="{w}" type="model"><components><component p:path="/{path}" objectid="{m}" '
                  'transform="1 0 0 0 1 0 0 0 1 0 0 0"/></components></object>' for w, m, path, _, _ in items)
        + "</resources><build>"
        + "".join(f'<item objectid="{w}" transform="1 0 0 0 1 0 0 0 1 {x:.4f} {y:.4f} 0" printable="1"/>'
                  for w, _, _, x, y in items)
        + "</build></model>")
files["3D/3dmodel.model"] = main
files["3D/_rels/3dmodel.model.rels"] = ('<?xml version="1.0" encoding="UTF-8"?>\n<Relationships '
                                         'xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                                         + "".join(rels) + "</Relationships>")
files["Metadata/model_settings.config"] = ('<?xml version="1.0" encoding="UTF-8"?>\n<config>'
                                            + "".join(objects_cfg) + "".join(plates_cfg) + "</config>")
files["_rels/.rels"] = ('<?xml version="1.0" encoding="UTF-8"?>\n<Relationships '
                        'xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                        '<Relationship Target="/3D/3dmodel.model" Id="rel-1" '
                        'Type="http://schemas.microsoft.com/3dmanufacturing/2013/01/3dmodel"/></Relationships>')
files["[Content_Types].xml"] = ('<?xml version="1.0" encoding="UTF-8"?>\n<Types '
                                'xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
                                '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
                                '<Default Extension="model" ContentType="application/vnd.ms-package.3dmanufacturing-3dmodel+xml"/>'
                                '<Default Extension="png" ContentType="image/png"/>'
                                '<Default Extension="config" ContentType="text/xml"/></Types>')

OUT.parent.mkdir(parents=True, exist_ok=True)
with zipfile.ZipFile(OUT, "w", zipfile.ZIP_DEFLATED) as zf:
    for name, text in files.items():
        zf.writestr(name, text)
(OUT.parent / "settings.json").write_text(json.dumps(values, indent=1), encoding="utf-8")
for plate_name, parts in plates:
    print(plate_name)
    for name, mesh, cx, cy in parts:
        print(f"  {name}: {mesh.extents.round(1).tolist()} mm at x {cx - mesh.extents[0] / 2:.1f}..{cx + mesh.extents[0] / 2:.1f}, "
              f"y {cy - mesh.extents[1] / 2:.1f}..{cy + mesh.extents[1] / 2:.1f}")
print("wrote", OUT)
