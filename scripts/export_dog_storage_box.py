"""Export the dog storage box as one Bambu Studio 3MF with two plates, from a part-preview server's saved values.

Plate 1 is a seam test strip (print it first), plate 2 is half A with the clip and caps, plate 3 is half B. The file layout copies what
Bambu Studio itself writes (wrapper objects, one mesh file per part, plates in model_settings.config).

Preview images (plate pictures and a cover of the assembled box) are rendered with pyvista.

Needs numpy, manifold3d, trimesh and pyvista:  python scripts/export_dog_storage_box.py [server URL]
"""
import json
import math
import sys
import urllib.request
import zipfile
from pathlib import Path
from xml.sax.saxutils import escape

import numpy as np
import pyvista as pv
import trimesh

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "models" / "dog_storage_box"))
import model  # noqa: E402

OUT = HERE.parent / "prints" / "dog-storage-box" / "dog-storage-box.3mf"
SERVER = sys.argv[1] if len(sys.argv) > 1 else "http://pi4.local:8765"
BED = 256.0
PLATE_STRIDE = BED * 1.2      # Bambu Studio's spacing between neighbouring plates, in x and in y
GAP = 5.0                     # between parts on a plate

values = json.load(urllib.request.urlopen(f"{SERVER}/api/schema?model=dog_storage_box", timeout=10))["values"]
a, b, clip, _screws, _info = model.parts(dict(values))
seam = model.layout({**model.SCREW, **values})["seam"]


OWNER_COLOUR = ["#A6A9AA"]


def with_owner_colours(settings_text):
    """Use the filament colours selected in the owner's Bambu Studio, so opening the file doesn't replace them."""
    import os
    conf = Path(os.environ.get("APPDATA", "")) / "BambuStudio" / "BambuStudio.conf"
    try:
        text = conf.read_text(encoding="utf-8")
        presets = json.loads(text[:text.rfind("# MD5 checksum")])["presets"]
    except (OSError, ValueError, KeyError):
        print("Bambu Studio config not readable; keeping the template's filament colour")
        return settings_text
    settings = json.loads(settings_text)
    colours = presets["filament_colors"].split(";")
    settings["filament_colour"] = colours
    OWNER_COLOUR[0] = colours[0]
    settings["filament_multi_colour"] = presets.get("filament_multi_colors", presets["filament_colors"]).split(";")
    settings["filament_colour_type"] = presets.get("filament_color_types", "1").split(";")
    print("filament colour from Bambu Studio:", colours)
    return json.dumps(settings, indent=4)


# Changes from stock 0.20mm Standard, strength first: solid walls, a thick solid ring around every screw hole,
# and 40% gyroid (strong in every direction) in the few thick parts. Gains above ~50% infill are small.
PRINT_OVERRIDES = {"wall_loops": "4", "wall_generator": "arachne",
                   "sparse_infill_density": "40%", "sparse_infill_pattern": "gyroid"}


def with_print_overrides(settings_text):
    """Apply PRINT_OVERRIDES and list them as changed, so Bambu Studio marks them like hand-made edits."""
    settings = json.loads(settings_text)
    settings.update(PRINT_OVERRIDES)
    changed = [k for k in settings["different_settings_to_system"][0].split(";") if k]
    settings["different_settings_to_system"][0] = ";".join(sorted(set(changed) | set(PRINT_OVERRIDES)))
    return json.dumps(settings, indent=4)


def render_png(meshes, size, colour, plate=False):
    """PNG bytes of meshes seen from the front-left; `plate` draws the build plate under them."""
    import tempfile
    pv.OFF_SCREEN = True
    plotter = pv.Plotter(off_screen=True, window_size=(size, size))
    plotter.set_background("#f2f2f2")
    if plate:
        plotter.add_mesh(pv.Box(bounds=(0, BED, 0, BED, -1.5, 0)), color="#3a3a3a")
    for mesh in meshes:
        faces = np.hstack([np.full((len(mesh.faces), 1), 3), mesh.faces]).ravel()
        plotter.add_mesh(pv.PolyData(np.asarray(mesh.vertices), faces), color=colour, specular=0.2)
    plotter.view_isometric()
    plotter.camera.azimuth = -20
    plotter.camera.elevation = 10
    plotter.reset_camera()
    plotter.camera.zoom(1.15 if plate else 1.0)
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "shot.png"
        plotter.screenshot(str(path))
        plotter.close()
        return path.read_bytes()


def mesh_in_place(shape):
    m = shape.to_mesh()
    return trimesh.Trimesh(np.asarray(m.vert_properties)[:, :3], np.asarray(m.tri_verts), process=True)


def mesh_of(shape, flip=False):
    m = shape.to_mesh()
    mesh = trimesh.Trimesh(np.asarray(m.vert_properties)[:, :3], np.asarray(m.tri_verts), process=True)
    if flip:  # clip: flat top on the bed, legs up
        mesh.apply_transform(trimesh.transformations.rotation_matrix(np.pi, [1, 0, 0]))
    assert mesh.is_watertight
    lo, hi = mesh.bounds
    mesh.apply_translation([-(lo[0] + hi[0]) / 2, -(lo[1] + hi[1]) / 2, -lo[2]])  # centred, on z=0
    return mesh


def row(parts):
    """Lay parts left to right, the whole row centred on the plate; returns [(name, mesh, centre_x, centre_y)]."""
    width = sum(m.extents[0] for _, m in parts) + GAP * (len(parts) - 1)
    depth = max(m.extents[1] for _, m in parts)
    assert width <= BED - 10 and depth <= BED - 10, f"{width:.0f} x {depth:.0f} mm does not fit the plate"
    placed, x = [], (BED - width) / 2
    for name, mesh in parts:
        placed.append((name, mesh, x + mesh.extents[0] / 2, BED / 2))
        x += mesh.extents[0] + GAP
    return placed


def small_parts(suffix=""):
    """The clip, when the top joint uses one."""
    return [] if clip is None else [(f"top clip{suffix}", mesh_of(clip, flip=True))]


reach = model.a_reach({**model.SCREW, **values})   # half A's floor tabs or top overlap tabs reach past the seam
plates = [
    ("Seam test - print first", row([
        ("seam test half A", mesh_of(a ^ model.cube(seam - 20, seam + reach + 1, -1, model.WIDTH + 1, -1, 300))),
        ("seam test half B", mesh_of(b ^ model.cube(seam, seam + 35, -1, model.WIDTH + 1, -1, 300))),
        *small_parts(" (test)")])),
    ("Half A" + (" + clip" if clip is not None else ""), row([("half A", mesh_of(a)), *small_parts()])),
    ("Half B", row([("half B", mesh_of(b))])),
]
COLUMNS = math.ceil(math.sqrt(len(plates)))   # Bambu Studio's plate grid: plates fill rows left to right, rows go down

files, items, rels, objects_cfg, plates_cfg = {}, [], [], [], []
next_id = 1
for plate_index, (plate_name, parts) in enumerate(plates):
    instances = []
    for name, mesh, cx, cy in parts:
        mesh_id, wrapper_id = next_id, next_id + 1
        next_id += 2
        vertices = "".join(f'<vertex x="{x:.6f}" y="{y:.6f}" z="{z:.6f}"/>' for x, y, z in mesh.vertices)
        triangles = "".join(f'<triangle v1="{i}" v2="{j}" v3="{k}"/>' for i, j, k in mesh.faces)
        path = f"3D/Objects/object_{mesh_id}.model"
        files[path] = ('<?xml version="1.0" encoding="UTF-8"?>\n'
                       '<model unit="millimeter" xml:lang="en-US" xmlns="http://schemas.microsoft.com/3dmanufacturing/core/2015/02">'
                       f'<resources><object id="{mesh_id}" type="model"><mesh><vertices>{vertices}</vertices>'
                       f'<triangles>{triangles}</triangles></mesh></object></resources><build/></model>')
        rels.append(f'<Relationship Target="/{path}" Id="rel-{len(rels) + 1}" '
                    'Type="http://schemas.microsoft.com/3dmanufacturing/2013/01/3dmodel"/>')
        col, plate_row = plate_index % COLUMNS, plate_index // COLUMNS
        items.append((wrapper_id, mesh_id, path, cx + col * PLATE_STRIDE, cy - plate_row * PLATE_STRIDE))
        label = escape(name, {'"': "&quot;"})
        objects_cfg.append(f'<object id="{wrapper_id}"><metadata key="name" value="{label}"/>'
                           '<metadata key="extruder" value="1"/>'
                           f'<part id="{mesh_id}" subtype="normal_part"><metadata key="name" value="{label}"/>'
                           '<metadata key="matrix" value="1 0 0 0 0 1 0 0 0 0 1 0 0 0 0 1"/></part></object>')
        instances.append(f'<model_instance><metadata key="object_id" value="{wrapper_id}"/>'
                         '<metadata key="instance_id" value="0"/></model_instance>')
    n = plate_index + 1
    plates_cfg.append(f'<plate><metadata key="plater_id" value="{n}"/>'
                      f'<metadata key="plater_name" value="{escape(plate_name)}"/>'
                      '<metadata key="locked" value="false"/>'
                      f'<metadata key="thumbnail_file" value="Metadata/plate_{n}.png"/>'
                      f'<metadata key="thumbnail_no_light_file" value="Metadata/plate_no_light_{n}.png"/>'
                      + "".join(instances) + "</plate>")

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
# Bambu Studio rejects a Bambu-tagged 3MF without its project settings ("invalid config"); these come from an
# X2D project saved by Bambu Studio 02.08 (0.20mm Standard, Generic PLA).
for name in ("project_settings.config", "slice_info.config"):
    files[f"Metadata/{name}"] = (HERE / f"bambu-x2d-{name}").read_text(encoding="utf-8")
files["Metadata/project_settings.config"] = with_print_overrides(with_owner_colours(files["Metadata/project_settings.config"]))
files["Metadata/filament_sequence.json"] = json.dumps(
    {f"plate_{i + 1}": {"nozzle_sequence": [], "optimal_assignment": [], "sequence": []} for i in range(len(plates))})
files["3D/_rels/3dmodel.model.rels"] = ('<?xml version="1.0" encoding="UTF-8"?>\n<Relationships '
                                         'xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                                         + "".join(rels) + "</Relationships>")
files["Metadata/model_settings.config"] = ('<?xml version="1.0" encoding="UTF-8"?>\n<config>'
                                            + "".join(objects_cfg) + "".join(plates_cfg) + "</config>")
# Previews: one picture per plate for Bambu Studio's plate list, and a cover of the assembled box.
for plate_index, (_, parts) in enumerate(plates):
    placed = [m.copy().apply_translation([cx, cy, 0]) for _, m, cx, cy in parts]
    picture = render_png(placed, 512, OWNER_COLOUR[0], plate=True)
    files[f"Metadata/plate_{plate_index + 1}.png"] = picture
    files[f"Metadata/plate_no_light_{plate_index + 1}.png"] = picture
    files[f"Metadata/plate_{plate_index + 1}_small.png"] = render_png(placed, 128, OWNER_COLOUR[0], plate=True)
assembled = [mesh_in_place(shape) for shape in (a, b, clip) if shape is not None]
for name, size in {"thumbnail_3mf.png": 512, "thumbnail_middle.png": 256, "thumbnail_small.png": 128}.items():
    files[f"Auxiliaries/.thumbnails/{name}"] = render_png(assembled, size, OWNER_COLOUR[0])
RELS = "http://schemas.openxmlformats.org/package/2006/relationships"
files["_rels/.rels"] = (
    f'<?xml version="1.0" encoding="UTF-8"?><Relationships xmlns="{RELS}">'
    '<Relationship Target="/3D/3dmodel.model" Id="rel-1" Type="http://schemas.microsoft.com/3dmanufacturing/2013/01/3dmodel"/>'
    f'<Relationship Target="/Auxiliaries/.thumbnails/thumbnail_3mf.png" Id="rel-2" Type="{RELS}/metadata/thumbnail"/>'
    '<Relationship Target="/Auxiliaries/.thumbnails/thumbnail_middle.png" Id="rel-4" '
    'Type="http://schemas.bambulab.com/package/2021/cover-thumbnail-middle"/>'
    '<Relationship Target="/Auxiliaries/.thumbnails/thumbnail_small.png" Id="rel-5" '
    'Type="http://schemas.bambulab.com/package/2021/cover-thumbnail-small"/></Relationships>')
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
