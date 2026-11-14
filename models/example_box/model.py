"""Example model: an open box with rounded corners. Copy this folder to start a new model."""

from __future__ import annotations

import manifold3d as mf
import numpy as np

NAME = "Example: rounded open box"
PARAMS = [
    dict(key="width", label="Width (mm)", min=20, max=150, step=1, default=60.0),
    dict(key="depth", label="Depth (mm)", min=20, max=150, step=1, default=40.0),
    dict(key="height", label="Height (mm)", min=5, max=100, step=1, default=25.0),
    dict(key="wall", label="Wall thickness (mm)", min=0.8, max=5, step=0.1, default=1.6),
    dict(key="floor", label="Floor thickness (mm)", min=0.6, max=5, step=0.1, default=1.2),
    dict(key="corner", label="Corner radius (mm)", min=0, max=20, step=0.5, default=6.0),
]
CIRCLE_SEGMENTS = 64


def rounded_rectangle(width: float, depth: float, radius: float) -> mf.CrossSection:
    """Rectangle centred on the origin with its corners rounded to the given radius."""
    radius = min(radius, width / 2 - 0.01, depth / 2 - 0.01)
    core = mf.CrossSection.square([width - 2 * radius, depth - 2 * radius], center=True)
    return core.offset(radius, mf.JoinType.Round, circular_segments=CIRCLE_SEGMENTS) if radius > 0 else core


def build(width: float, depth: float, height: float, wall: float, floor: float, corner: float) -> tuple[np.ndarray, np.ndarray]:
    """Mesh of the box: vertices in mm and triangles as vertex indices."""
    if 2 * wall >= min(width, depth) or floor >= height:
        raise ValueError("walls or floor are thicker than the box")
    outer = rounded_rectangle(width, depth, corner).extrude(height)
    inner = rounded_rectangle(width - 2 * wall, depth - 2 * wall, max(corner - wall, 0))
    box = outer - inner.extrude(height).translate([0, 0, floor])
    mesh = box.to_mesh()
    return np.asarray(mesh.vert_properties)[:, :3], np.asarray(mesh.tri_verts)


def stats(params: dict[str, float]) -> dict[str, str]:
    """Inside size, shown under the sliders."""
    inside_width = params["width"] - 2 * params["wall"]
    inside_depth = params["depth"] - 2 * params["wall"]
    return {
        "inside": f"{inside_width:.1f} x {inside_depth:.1f} x {params['height'] - params['floor']:.1f} mm",
    }
