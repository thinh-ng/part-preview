# Part preview

Live 3D preview for parametric 3D-print parts. Sliders change a model's parameters, the part is
rebuilt on the fly, and the view reloads without moving the camera. You can also drop any STL or
3MF file on the page to look at it.

- **Server:** Python standard library (`server.py`), bound to `127.0.0.1`. It rebuilds models and serves the page.
- **Page:** Vue 3 + TypeScript + Vite + three.js (`web/`).

## Run

```
pip install -r requirements.txt
cd web
npm ci
npm run build
cd ..
python server.py
```

Open http://127.0.0.1:8765/. On Windows, `start.cmd` builds the page on first run, starts the
server and opens the browser. Use `--port` or `PART_PREVIEW_PORT` for another port.

To serve other devices on the LAN, bind another address and allow each host name or IP the page
will be opened under, for example
`python server.py --host 0.0.0.0 --allow-host 192.168.0.7 --allow-host pi4 --allow-host pi4.local`.

To work on the page, run `npm run dev` in `web/` alongside `python server.py`. Vite serves the page
on port 5173 with hot reload and forwards `/api` to the Python server.

## Add a model

Copy `models/example_box/` to `models/<id>/` (lowercase letters, digits and `_`) and edit `model.py`:

```python
NAME = "Shown in the model list"
PARAMS = [
    dict(key="width", label="Width (mm)", min=10, max=50, step=0.5, default=20.0),
    dict(key="style", label="Style", min=0, max=1, step=1, default=0, options=["Flat", "Rounded"]),
]

def build(width, style):
    return vertices, triangles      # numpy arrays: N x 3 floats in mm, M x 3 vertex indices
    # or (vertices, triangles, colours): colours M x 3, 0..1 per triangle

def stats(params):                  # optional, shown under the sliders
    return {"width": f"{params['width']:.1f} mm"}
```

- `build` receives one keyword argument per entry in `PARAMS`, already clamped to its range.
- A parameter with `options` is a drop-down; its value is the index of the chosen option.
- Per-triangle colours are written into the mesh (Materialise Magics STL colours) and shown as given.
- A `ValueError` raised by `build` is shown on the page as the error.
- The model folder is put on `sys.path`, so `model.py` can import helper files next to it; give
  helpers names that other models will not reuse.

Restart the server after adding or editing a model. At startup it rebuilds every model from its
saved slider values, so the page never shows a mesh from an older `model.py`.

## Deploy to the Pi

The LAN copy runs on the Pi as the systemd unit `part-preview` in `~/part-preview`, at
http://pi4.local:8765/. It keeps its own `state/`, separate from the PC's. To update it after
changing a model, from the repo root in Git Bash:

```
tar --exclude=__pycache__ -cf - models/<id> | ssh thinh@pi4 'tar -xf - -C ~/part-preview && sudo systemctl restart part-preview'
```

Add `web/dist` after a page build and `server.py` after a server change. Add `state` only to replace
the Pi's saved slider values with the PC's.

## Print files

`prints/<item>/` holds print files and is git-ignored. `scripts/export_<id>.py` writes a model's
Bambu Studio project 3MF there from a server's saved slider values; the format is in
[docs/bambu-3mf.md](docs/bambu-3mf.md).

## API

```
GET  /api/models                 [{id, name, error?}]
GET  /api/schema?model=<id>      {name, params, values, stats, version}  values = last saved slider values
POST /api/build                  body {model, values}; saves values as the model's slider values
                                 -> {ok: true, version, values, stats, builtAt}
                                 |  {ok: false, error}  |  {ok: false, superseded: true}
GET  /api/mesh?model=<id>        last built mesh as binary STL, version in the X-Mesh-Version header
GET  /api/version?model=<id>     {version} of the last built mesh, 0 if never built
```

Only the newest build request for a model writes its mesh; older queued requests answer
`superseded`. Requests must use the `127.0.0.1:<port>` or `localhost:<port>` host name, or one
added with `--allow-host`.
