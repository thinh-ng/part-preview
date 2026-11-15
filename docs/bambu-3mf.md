# Bambu Studio project 3MF

The layout Bambu Studio reads as a project (plates, settings, previews) rather than as bare
geometry. `scripts/export_dog_storage_box.py` writes it.

## Files in the zip

```
[Content_Types].xml                      default content types for rels, model, png, config
_rels/.rels                              the model, plus cover images (see Previews)
3D/3dmodel.model                         wrapper objects, build items, Bambu metadata
3D/_rels/3dmodel.model.rels              one relationship per object file
3D/Objects/object_<id>.model             one mesh per file
Metadata/model_settings.config           object names, extruder, plates
Metadata/project_settings.config         every print, filament and printer setting
Metadata/slice_info.config               client header
Metadata/filament_sequence.json          one entry per plate
Metadata/plate_<n>.png                   plate picture, also plate_no_light_<n>.png and plate_<n>_small.png
Auxiliaries/.thumbnails/thumbnail_*.png  cover images
```

## 3D model

- `3D/3dmodel.model` declares `requiredextensions="p"` (3MF production extension) and the metadata
  `Application` = `BambuStudio-<version>` and `BambuStudio:3mfVersion` = `1`.
- Each part is a wrapper object whose single `<component p:path="/3D/Objects/object_<mesh id>.model"
  objectid="<mesh id>">` points at the mesh object in its own file.
- A `<build><item>` per wrapper object carries the part's position as its transform.
- Vertex coordinates are written with 6 decimals. With 4, rounding opens holes in the mesh.

## Plates

`model_settings.config` has one `<object id="<wrapper id>">` per part (`name`, `extruder`, and a
`<part id="<mesh id>" subtype="normal_part">` with an identity `matrix`) and one `<plate>` per plate:
`plater_id` (1-based), `plater_name`, `locked`, `thumbnail_file`, `thumbnail_no_light_file`, and a
`<model_instance>` (`object_id`, `instance_id` 0) per part on it.

Plates sit in a grid of `ceil(sqrt(plate count))` columns, filled left to right, rows going down.
Plate index `i` (0-based) is offset by `x = (i % columns) × 1.2 × bed width` and
`y = −(i // columns) × 1.2 × bed depth` from plate 1; a part's build-item position is its position on
its plate plus that offset.

## Settings

- With `Application` set to Bambu Studio, `Metadata/project_settings.config` is required. Without it
  Bambu Studio reports an invalid config and loads the geometry only, without plates.
- `printer_settings_id`, `print_settings_id` and `filament_settings_id` name the presets.
  `different_settings_to_system` lists the keys changed from them, one `;`-separated entry per
  section: process, filament, printer.
- Settings copied from another project carry that project's hand edits, its filament colour and its
  Bambu Studio version's printer g-code.
- `filament_colour` (with `filament_multi_colour` and `filament_colour_type`) replaces the colour
  selected in Bambu Studio when the file is opened.
- Some filament lists have one entry per nozzle variant (`filament_extruder_variant`); Bambu Studio
  fills them itself and they differ in length from the preset files.

## Previews

`_rels/.rels` links `Auxiliaries/.thumbnails/thumbnail_3mf.png` as
`http://schemas.openxmlformats.org/package/2006/relationships/metadata/thumbnail`, and
`thumbnail_middle.png` and `thumbnail_small.png` as
`http://schemas.bambulab.com/package/2021/cover-thumbnail-middle` and `.../cover-thumbnail-small`.
Plate pictures are named in each `<plate>` and need no relationship.
