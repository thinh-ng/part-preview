"""Live 3D preview server for parametric parts.

Serves the built web app (web/dist) and rebuilds a model from its slider values. A model is a folder
under models/ whose model.py defines NAME, PARAMS (key, label, min, max, step, default),
build(**params) -> (vertices N x 3, triangles M x 3[, triangle colors M x 3 in 0..1]) and optionally
stats(params) -> dict[str, str].
"""

from __future__ import annotations

import argparse
import functools
import http.server
import importlib.util
import json
import logging
import math
import os
import re
import struct
import sys
import threading
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from types import ModuleType
from typing import Any
from urllib.parse import ParseResult, parse_qs, urlparse

import numpy as np

ROOT = Path(__file__).resolve().parent
WEB_DIST = ROOT / "web" / "dist"
MODELS_DIR = ROOT / "models"
STATE_DIR = ROOT / "state"
DEFAULT_PORT = 8765
MODEL_ID = re.compile(r"[a-z0-9_]+")
MAX_BODY_BYTES = 64 * 1024

log = logging.getLogger("part-preview")


class ApiError(Exception):
    """A request the API rejects, with the HTTP status to answer with."""

    def __init__(self, status: int, message: str) -> None:
        super().__init__(message)
        self.status = status


@dataclass
class PreviewState:
    """State shared by the request handlers. One build runs at a time and only the newest request writes."""

    build_lock: threading.Lock = field(default_factory=threading.Lock)
    request_lock: threading.Lock = field(default_factory=threading.Lock)
    latest_request: dict[str, int] = field(default_factory=dict)

    def register_request(self, model_id: str) -> int:
        """Number a build request in arrival order, without waiting for a build that is running."""
        with self.request_lock:
            number = self.latest_request.get(model_id, 0) + 1
            self.latest_request[model_id] = number
            return number

    def is_latest(self, model_id: str, number: int) -> bool:
        with self.request_lock:
            return self.latest_request.get(model_id) == number


def model_ids() -> list[str]:
    """Ids of the model folders that contain a model.py."""
    return sorted(p.parent.name for p in MODELS_DIR.glob("*/model.py") if MODEL_ID.fullmatch(p.parent.name))


def require_model_id(model_id: object) -> str:
    """Return the id if it names an existing model; anything else is rejected before touching the disk."""
    if not isinstance(model_id, str) or not MODEL_ID.fullmatch(model_id) or model_id not in model_ids():
        raise ApiError(404, f"unknown model: {model_id!r}")
    return model_id


@functools.cache
def load_model(model_id: str) -> ModuleType:
    """Import models/<id>/model.py. Its folder goes on sys.path so it can import files next to it."""
    folder = MODELS_DIR / model_id
    sys.path.insert(0, str(folder))
    spec = importlib.util.spec_from_file_location(f"part_models.{model_id}", folder / "model.py")
    if spec is None or spec.loader is None:
        raise ApiError(500, f"cannot load model {model_id}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def clean_values(model: ModuleType, raw: dict[str, Any]) -> dict[str, float]:
    """Keep known keys only, require finite numbers, and clamp each to its slider range."""
    values = {}
    for spec in model.PARAMS:
        key = spec["key"]
        value = raw.get(key, spec["default"])
        if not isinstance(value, (int, float)) or isinstance(value, bool) or not math.isfinite(value):
            raise ApiError(400, f"{key} must be a finite number")
        values[key] = min(max(float(value), spec["min"]), spec["max"])
    return values


def state_paths(model_id: str) -> tuple[Path, Path]:
    """Where a model's last values and last mesh are kept."""
    return STATE_DIR / f"{model_id}.json", STATE_DIR / f"{model_id}.stl"


def saved_values(model_id: str, model: ModuleType) -> dict[str, float]:
    """Last saved slider values, falling back to the defaults for anything missing or unreadable."""
    values_path, _ = state_paths(model_id)
    try:
        raw = json.loads(values_path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raw = {}
    except (json.JSONDecodeError, UnicodeDecodeError) as error:
        log.warning("ignoring unreadable %s: %s", values_path, error)
        raw = {}
    try:
        return clean_values(model, raw if isinstance(raw, dict) else {})
    except ApiError:
        log.warning("ignoring invalid values in %s", values_path)
        return clean_values(model, {})


def write_atomic(path: Path, data: bytes) -> None:
    """Replace a file in one step so a reader never sees it half written."""
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_bytes(data)
    os.replace(temp, path)


def stl_bytes(vertices: np.ndarray, triangles: np.ndarray, colors: np.ndarray | None = None) -> bytes:
    """Binary STL of a mesh, moved so it sits on z = 0.

    Triangle colors use the Materialise Magics convention ("COLOR=" in the header, 5-bit RGB per
    facet with bit 15 clear), which three.js STLLoader reads and slicers ignore.
    """
    vertices = np.asarray(vertices, dtype=np.float64)
    vertices = vertices - [0.0, 0.0, vertices[:, 2].min()]
    corners = vertices[np.asarray(triangles)]
    normals = np.cross(corners[:, 1] - corners[:, 0], corners[:, 2] - corners[:, 0])
    normals /= np.linalg.norm(normals, axis=1, keepdims=True) + 1e-12
    records = np.zeros(len(corners), dtype=[("normal", "<f4", 3), ("corners", "<f4", 9), ("attr", "<u2")])
    records["normal"] = normals
    records["corners"] = corners.reshape(-1, 9)
    header = b"part-preview"
    if colors is not None:
        rgb = np.rint(np.clip(np.asarray(colors, dtype=np.float64), 0, 1) * 31).astype(np.uint16)
        records["attr"] = rgb[:, 0] | (rgb[:, 1] << 5) | (rgb[:, 2] << 10)
        header += b" COLOR=" + bytes([128, 128, 128, 255])
    return header.ljust(80, b" ") + struct.pack("<I", len(corners)) + records.tobytes()


def mesh_version(model_id: str) -> int:
    """Modification time of the last built mesh in nanoseconds, or 0 when there is none."""
    try:
        return state_paths(model_id)[1].stat().st_mtime_ns
    except FileNotFoundError:
        return 0


def build(state: PreviewState, model_id: str, raw_values: dict[str, Any]) -> dict[str, Any]:
    """Build a model and save its values and mesh, unless a newer build request has arrived meanwhile."""
    model = load_model(model_id)
    values = clean_values(model, raw_values)
    number = state.register_request(model_id)
    with state.build_lock:
        if not state.is_latest(model_id, number):
            return {"ok": False, "superseded": True}
        try:
            vertices, triangles, *colors = model.build(**values)
        except Exception as error:  # a model's own failure is shown to the user, not a server error
            log.info("build of %s failed: %s", model_id, error)
            return {"ok": False, "error": str(error)}
        STATE_DIR.mkdir(exist_ok=True)
        values_path, mesh_path = state_paths(model_id)
        write_atomic(values_path, json.dumps(values, indent=1).encode("utf-8"))
        write_atomic(mesh_path, stl_bytes(vertices, triangles, colors[0] if colors else None))
        stats = model.stats(values) if hasattr(model, "stats") else {}
        return {"ok": True, "version": mesh_version(model_id), "values": values, "stats": stats,
                "builtAt": datetime.now().astimezone().strftime("%H:%M:%S")}


class Handler(http.server.SimpleHTTPRequestHandler):
    """Static files from web/dist plus the JSON API under /api/."""

    server_state: PreviewState
    allowed_hosts: frozenset[str]

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, directory=str(WEB_DIST), **kwargs)

    def log_message(self, format: str, *args: Any) -> None:  # noqa: A002  (signature from the base class)
        log.debug(format, *args)

    def send_json(self, body: Any, status: int = 200) -> None:
        data = json.dumps(body).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def handle_api(self, method: str) -> None:
        try:
            # Blocks DNS rebinding: a page on another site cannot reach this server under its own host name.
            if self.headers.get("Host", "") not in self.allowed_hosts:
                raise ApiError(403, "unexpected Host header")
            self.dispatch(method, urlparse(self.path))
        except ApiError as error:
            self.send_json({"error": str(error)}, error.status)
        except Exception:
            log.exception("request %s %s failed", method, self.path)
            self.send_json({"error": "internal error, see the server log"}, 500)

    def dispatch(self, method: str, url: ParseResult) -> None:
        query = {key: values[0] for key, values in parse_qs(url.query).items()}
        route = (method, url.path)
        if route == ("GET", "/api/models"):
            self.send_json(self.list_models())
        elif route == ("GET", "/api/schema"):
            model_id = require_model_id(query.get("model"))
            model = load_model(model_id)
            with self.server_state.build_lock:
                values = saved_values(model_id, model)
                version = mesh_version(model_id)
            stats = model.stats(values) if hasattr(model, "stats") else {}
            self.send_json({"name": model.NAME, "params": model.PARAMS, "values": values, "stats": stats,
                            "version": version})
        elif route == ("POST", "/api/build"):
            body = self.read_json()
            model_id = require_model_id(body.get("model"))
            values = body.get("values")
            if not isinstance(values, dict):
                raise ApiError(400, "values must be an object")
            self.send_json(build(self.server_state, model_id, values))
        elif route == ("GET", "/api/mesh"):
            self.send_mesh(require_model_id(query.get("model")))
        elif route == ("GET", "/api/version"):
            self.send_json({"version": mesh_version(require_model_id(query.get("model")))})
        else:
            raise ApiError(404, f"no such endpoint: {method} {url.path}")

    def list_models(self) -> list[dict[str, str]]:
        models = []
        for model_id in model_ids():
            try:
                models.append({"id": model_id, "name": load_model(model_id).NAME})
            except Exception as error:  # one broken model must not hide the others
                log.warning("model %s failed to load: %s", model_id, error)
                models.append({"id": model_id, "name": model_id, "error": str(error)})
        return models

    def send_mesh(self, model_id: str) -> None:
        with self.server_state.build_lock:
            version = mesh_version(model_id)
            data = state_paths(model_id)[1].read_bytes() if version else b""
        if not version:
            raise ApiError(404, "this model has not been built yet")
        self.send_response(200)
        self.send_header("Content-Type", "model/stl")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("X-Mesh-Version", str(version))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def read_json(self) -> dict[str, Any]:
        if self.headers.get("Content-Type", "").split(";")[0].strip() != "application/json":
            raise ApiError(415, "expected application/json")
        length = int(self.headers.get("Content-Length") or 0)
        if length > MAX_BODY_BYTES:
            raise ApiError(413, "request body too large")
        try:
            body = json.loads(self.rfile.read(length))
        except json.JSONDecodeError as error:
            raise ApiError(400, f"invalid JSON: {error}") from error
        if not isinstance(body, dict):
            raise ApiError(400, "expected a JSON object")
        return body

    def do_GET(self) -> None:  # noqa: N802  (name fixed by the base class)
        if self.path.startswith("/api/"):
            self.handle_api("GET")
        else:
            super().do_GET()

    def do_POST(self) -> None:  # noqa: N802  (name fixed by the base class)
        self.handle_api("POST")


def main() -> int:
    parser = argparse.ArgumentParser(description="Live 3D preview server for parametric parts.")
    parser.add_argument("--port", type=int, default=int(os.environ.get("PART_PREVIEW_PORT", DEFAULT_PORT)))
    parser.add_argument("--host", default="127.0.0.1", help="address to bind, e.g. 0.0.0.0 to serve the LAN")
    parser.add_argument("--allow-host", action="append", default=[], metavar="NAME",
                        help="extra host name or IP the page may be opened under (repeatable)")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    if not (WEB_DIST / "index.html").exists():
        log.error("web/dist is missing; run `npm ci` and `npm run build` in web/ first")
        return 1
    Handler.server_state = PreviewState()
    host_names = ["127.0.0.1", "localhost", *args.allow_host]
    Handler.allowed_hosts = frozenset(f"{name}:{args.port}" for name in host_names)
    server = http.server.ThreadingHTTPServer((args.host, args.port), Handler)
    log.info("part-preview on http://%s:%d/", args.host, args.port)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        log.info("stopped")
    return 0


if __name__ == "__main__":
    sys.exit(main())
