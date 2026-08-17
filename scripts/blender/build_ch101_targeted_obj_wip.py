#!/usr/bin/env python3
"""Apply MPFB target deltas directly to the CC0 OBJ body group."""

from __future__ import annotations

import argparse
import gzip
import json
import math
import sys
from pathlib import Path

import bpy
from mathutils import Vector

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from build_ch101_base_mesh_wip import clear, capsule, curve, look_at, mat, sphere  # noqa: E402


def parse_args() -> argparse.Namespace:
    raw = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-obj", required=True)
    parser.add_argument("--targets-root", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--render", action="store_true")
    return parser.parse_args(raw)


def parse_obj(path: Path) -> tuple[list[tuple[float, float, float]], list[tuple[int, ...]]]:
    vertices: list[tuple[float, float, float]] = []
    body_faces: list[tuple[int, ...]] = []
    current_group = ""
    with path.open("r", encoding="utf-8", errors="ignore") as handle:
        for line in handle:
            if line.startswith("v "):
                _, x, y, z = line.split()[:4]
                vertices.append((float(x), float(y), float(z)))
            elif line.startswith("g "):
                current_group = line.split(maxsplit=1)[1].strip()
            elif line.startswith("f ") and current_group == "body":
                indices = []
                for token in line.split()[1:]:
                    indices.append(int(token.split("/")[0]) - 1)
                if len(indices) >= 3:
                    body_faces.append(tuple(indices))
    if not vertices or not body_faces:
        raise RuntimeError("OBJ body group could not be parsed")
    return vertices, body_faces


def apply_target(vertices: list[tuple[float, float, float]], path: Path, weight: float) -> int:
    applied = 0
    with gzip.open(path, "rt", encoding="utf-8") as handle:
        for line in handle:
            values = line.split()
            if len(values) < 4:
                continue
            index = int(values[0])
            if index >= len(vertices):
                continue
            x, y, z = vertices[index]
            vertices[index] = (x + float(values[1]) * weight, y + float(values[2]) * weight, z + float(values[3]) * weight)
            applied += 1
    return applied


def make_body_mesh(vertices: list[tuple[float, float, float]], faces: list[tuple[int, ...]]) -> bpy.types.Object:
    used = sorted({index for face in faces for index in face})
    remap = {source: target for target, source in enumerate(used)}
    mesh = bpy.data.meshes.new("CH101_TargetedBodyMesh")
    mesh.from_pydata([vertices[index] for index in used], [], [tuple(remap[index] for index in face) for face in faces])
    mesh.update()
    body = bpy.data.objects.new("CH101_A_TargetedBody_WIP", mesh)
    bpy.context.collection.objects.link(body)
    return body


def normalize_zup(body: bpy.types.Object, target_height: float = 3.65) -> None:
    body.rotation_euler.x = math.radians(90.0)
    bpy.ops.object.select_all(action="DESELECT")
    body.select_set(True)
    bpy.context.view_layer.objects.active = body
    bpy.ops.object.transform_apply(location=False, rotation=True, scale=False)
    bpy.context.view_layer.update()
    scale = target_height / body.dimensions.z
    body.scale = (scale, scale, scale)
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    bpy.context.view_layer.update()
    body.location.z -= min(vertex.co.z for vertex in body.data.vertices)


def add_face_and_hair(root: bpy.types.Object, mats: dict[str, bpy.types.Material]) -> None:
    for side in (-1, 1):
        sphere("EyeWhite", (side * 0.18, -0.382, 3.22), (0.055, 0.015, 0.041), mats["eye"], root, segments=36)
        sphere("Iris", (side * 0.18, -0.402, 3.215), (0.027, 0.008, 0.032), mats["iris"], root, segments=36)
        sphere("Pupil", (side * 0.18, -0.410, 3.215), (0.012, 0.005, 0.020), mats["pupil"], root, segments=24)
        capsule("Brow", (side * 0.25, -0.388, 3.34), (side * 0.10, -0.394, 3.35), 0.007, mats["hair"], root)
    sphere("HairCap", (0.0, 0.03, 3.43), (0.53, 0.37, 0.34), mats["hair"], root)
    for index, dx in enumerate((-0.25, -0.15, -0.05, 0.06, 0.16, 0.25), start=1):
        curve(f"Bang_{index}", [(dx * 0.72, -0.34, 3.55), (dx, -0.405, 3.36), (dx * 0.82, -0.30, 3.02)], 0.020, mats["hair"], root)
    curve("Ponytail", [(0.28, 0.11, 3.52), (0.56, 0.16, 3.30), (0.54, 0.11, 2.95), (0.42, 0.04, 2.66)], 0.075, mats["hair"], root)
    curve("PonytailCyan", [(0.48, 0.10, 3.18), (0.56, 0.05, 2.92), (0.42, 0.01, 2.68)], 0.022, mats["cyan"], root)


def setup_scene(out: Path) -> None:
    scene = bpy.context.scene
    scene.render.engine = "BLENDER_EEVEE_NEXT"
    scene.render.resolution_x = 1100
    scene.render.resolution_y = 1100
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.world.color = (0.015, 0.018, 0.028)
    bpy.ops.mesh.primitive_plane_add(size=30, location=(0, 0.4, 0.0))
    floor = bpy.context.object
    floor.data.materials.append(mat("TargetedObjFloor", (0.018, 0.025, 0.045, 1.0), 0.55))
    bpy.ops.object.camera_add(location=(0.35, -6.9, 2.0))
    camera = bpy.context.object
    camera.data.lens = 62
    look_at(camera, Vector((0, 0, 1.9)))
    scene.camera = camera
    scene.render.filepath = str(out / "renders" / "CH101_A_TargetedObj_WIP_3q.png")
    for location, energy, color in (((-4.0, -5.0, 6.0), 1000, (1.0, 0.80, 0.70)), ((4.0, -3.0, 4.0), 600, (0.45, 0.68, 1.0)), ((0.0, 3.5, 5.0), 850, (0.10, 0.60, 1.0))):
        bpy.ops.object.light_add(type="AREA", location=location)
        light = bpy.context.object
        light.data.energy = energy
        light.data.color = color
        light.data.shape = "DISK"
        light.data.size = 4
        look_at(light, Vector((0, 0, 1.8)))


def main() -> None:
    options = parse_args()
    base_obj = Path(options.base_obj).resolve()
    targets_root = Path(options.targets_root).resolve()
    out = Path(options.output_dir).resolve()
    (out / "renders").mkdir(parents=True, exist_ok=True)
    (out / "reports").mkdir(parents=True, exist_ok=True)
    clear()
    vertices, faces = parse_obj(base_obj)
    target_specs = [
        (targets_root / "head" / "head-oval.target.gz", 0.45),
        (targets_root / "eyes" / "l-eye-scale-incr.target.gz", 0.35),
        (targets_root / "eyes" / "r-eye-scale-incr.target.gz", 0.35),
        (targets_root / "breast" / "breast-volume-vert-up.target.gz", 0.25),
    ]
    applied = {path.name: apply_target(vertices, path, weight) for path, weight in target_specs if path.exists()}
    body = make_body_mesh(vertices, faces)
    normalize_zup(body)
    body.data.materials.append(mat("MAT_CH101_TargetedObjSkin", (0.82, 0.50, 0.47, 1), 0.54))
    for polygon in body.data.polygons:
        polygon.use_smooth = True
    root = bpy.data.objects.new("CH101_A_TargetedObj_WIP_Root", None)
    bpy.context.collection.objects.link(root)
    body.parent = root
    mats = {
        "skin": body.data.materials[0],
        "eye": mat("MAT_CH101_TargetedEye", (0.96, 0.98, 1.0, 1), 0.22),
        "iris": mat("MAT_CH101_TargetedIris", (0.03, 0.40, 0.62, 1), 0.18, metallic=0.05),
        "pupil": mat("MAT_CH101_TargetedPupil", (0.004, 0.006, 0.015, 1), 0.10),
        "hair": mat("MAT_CH101_TargetedHair", (0.008, 0.012, 0.025, 1), 0.22),
        "cyan": mat("MAT_CH101_TargetedCyan", (0.01, 0.42, 0.64, 1), 0.24, metallic=0.12, emission=True),
    }
    add_face_and_hair(root, mats)
    body["status"] = "WIP / TARGETED OBJ BODY / NOT APPROVED"
    body["targets"] = ",".join(applied)
    body["source_license"] = "CC0 1.0 Universal (MPFB asset)"
    setup_scene(out)
    scene = bpy.context.scene
    scene["re_camp_status"] = "WIP / TARGETED OBJ BODY / NOT APPROVED"
    scene["re_camp_character"] = "CH101-A Route Sprint"
    scene["re_camp_gate"] = "Gate A pending / Gate B blocked"
    scene["re_camp_source_license"] = "CC0 1.0 Universal"
    blend = out / "CH101_A_TargetedObjBody_WIP_v001.blend"
    bpy.ops.wm.save_as_mainfile(filepath=str(blend))
    if options.render:
        bpy.ops.render.render(write_still=True)
        bpy.ops.wm.save_as_mainfile(filepath=str(blend))
    body.data.calc_loop_triangles()
    report = {
        "status": "WIP / TARGETED OBJ BODY / NOT APPROVED",
        "blend": str(blend),
        "source_obj": str(base_obj),
        "source_license": "CC0 1.0 Universal",
        "targets_applied": applied,
        "vertex_count": len(body.data.vertices),
        "triangle_count": len(body.data.loop_triangles),
        "gate_a": "PENDING",
        "gate_b": "BLOCKED / clothing, equipment and rig bind incomplete",
        "notes": ["Target deltas applied directly to MPFB body group", "CH101 styling WIP", "Human review required"],
    }
    (out / "reports" / "CH101_A_TargetedObjBody_WIP_v001.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"Generated {blend}")
    print(f"Targets applied: {applied}")
    print("Status: WIP / targeted OBJ body / not approved")


if __name__ == "__main__":
    main()
