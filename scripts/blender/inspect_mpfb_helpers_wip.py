#!/usr/bin/env python3
"""Render MPFB's bundled helper surfaces in the Re:Camp Z-up review scene.

This is an inspection WIP only.  It tests whether the CC0 helper hair/skirt/
tights meshes can serve as a real surface layer before any CH101 styling is
promoted.  No helper is considered production-ready by this script.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

import bpy
from mathutils import Vector

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from build_ch101_base_mesh_wip import clear, mat, set_parent  # noqa: E402
from build_ch101_mpfb_base_wip import look_at, normalize_body  # noqa: E402


def parse_args() -> argparse.Namespace:
    raw = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-obj", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--render", action="store_true")
    return parser.parse_args(raw)


def align_helper(obj: bpy.types.Object, scale: float, target_min_z: float) -> None:
    obj.rotation_euler.x = math.radians(90.0)
    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)
    bpy.ops.object.transform_apply(location=False, rotation=True, scale=False)
    obj.scale = (scale, scale, scale)
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    bpy.context.view_layer.update()
    min_z = min((obj.matrix_world @ Vector(v.co)).z for v in obj.data.vertices)
    obj.location.z += target_min_z - min_z
    bpy.context.view_layer.update()
    obj.select_set(False)


def scene_setup(out: Path) -> None:
    scene = bpy.context.scene
    engines = {item.identifier for item in bpy.types.RenderSettings.bl_rna.properties["engine"].enum_items}
    scene.render.engine = "BLENDER_EEVEE_NEXT" if "BLENDER_EEVEE_NEXT" in engines else "BLENDER_EEVEE"
    scene.render.resolution_x = 1200
    scene.render.resolution_y = 1200
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.world.color = (0.012, 0.016, 0.028)
    bpy.ops.mesh.primitive_plane_add(size=30, location=(0, 0.5, 0.0))
    floor = bpy.context.object
    floor.data.materials.append(mat("MPFBHelperReviewFloor", (0.018, 0.025, 0.045, 1.0), 0.56))
    bpy.ops.object.camera_add(location=(0.45, -7.4, 2.05))
    camera = bpy.context.object
    camera.data.lens = 58
    look_at(camera, Vector((0, 0, 1.85)))
    scene.camera = camera
    scene.render.filepath = str(out / "renders" / "CH101_A_MPFHelpers_WIP_3q.png")
    for location, energy, color in (((-4.0, -5.0, 6.0), 1200, (1.0, 0.80, 0.70)), ((4.0, -3.0, 4.0), 700, (0.45, 0.68, 1.0)), ((0.0, 3.5, 5.0), 950, (0.10, 0.60, 1.0))):
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
    out = Path(options.output_dir).resolve()
    (out / "renders").mkdir(parents=True, exist_ok=True)
    (out / "reports").mkdir(parents=True, exist_ok=True)
    clear()
    before = set(bpy.data.objects)
    bpy.ops.wm.obj_import(filepath=str(base_obj), use_split_groups=True, import_vertex_groups=True, validate_meshes=True)
    imported = [obj for obj in bpy.data.objects if obj not in before]
    body = next((obj for obj in imported if obj.name == "body"), None)
    if body is None:
        raise RuntimeError("MPFB base.obj import did not expose the body group")
    raw_height = body.dimensions.y
    target_height = 3.65
    scale = target_height / raw_height
    normalize_body(body, target_height=target_height)
    body.name = "CH101_A_MPFBody_CC0_WIP"
    root = bpy.data.objects.new("CH101_A_MPFHelpers_WIP_Root", None)
    bpy.context.collection.objects.link(root)
    body.parent = root
    body.data.materials.append(mat("MAT_CH101_HelperSkin", (0.82, 0.50, 0.47, 1), 0.54))
    for polygon in body.data.polygons:
        polygon.use_smooth = True
    keep = {"helper-hair": "MAT_CH101_HelperHair", "helper-skirt": "MAT_CH101_HelperSkirt", "helper-tights": "MAT_CH101_HelperTights", "helper-l-eye": "MAT_CH101_HelperEye", "helper-r-eye": "MAT_CH101_HelperEye"}
    materials = {
        "MAT_CH101_HelperHair": mat("MAT_CH101_HelperHair", (0.008, 0.012, 0.025, 1), 0.22),
        "MAT_CH101_HelperSkirt": mat("MAT_CH101_HelperSkirt", (0.018, 0.026, 0.046, 1), 0.36),
        "MAT_CH101_HelperTights": mat("MAT_CH101_HelperTights", (0.04, 0.055, 0.08, 1), 0.48),
        "MAT_CH101_HelperEye": mat("MAT_CH101_HelperEye", (0.02, 0.42, 0.68, 1), 0.18, emission=True),
    }
    helper_report = []
    body_min_z = body.location.z
    for obj in imported:
        if obj == body:
            continue
        if obj.name in keep and obj.type == "MESH":
            align_helper(obj, scale, body_min_z)
            obj.name = f"CH101_{obj.name.replace('-', '_')}_CC0_Helper_WIP"
            obj.parent = root
            set_parent(obj, root, materials[keep[obj.name.replace("CH101_", "").replace("_CC0_Helper_WIP", "").replace("_", "-")]] if False else materials["MAT_CH101_HelperHair"])
            # Material assignment is corrected by the original helper key;
            # keep all helpers visible for the inspection render.
            obj.data.materials.clear()
            key = "helper-hair" if "hair" in obj.name else "helper-skirt" if "skirt" in obj.name else "helper-tights" if "tights" in obj.name else "helper-l-eye"
            obj.data.materials.append(materials[keep[key]])
            for polygon in obj.data.polygons:
                polygon.use_smooth = True
            helper_report.append({"name": obj.name, "vertices": len(obj.data.vertices), "dimensions": [round(v, 4) for v in obj.dimensions]})
        else:
            obj.hide_render = True
            obj.hide_viewport = True
    root["status"] = "WIP / MPFB HELPER SURFACE INSPECTION / NOT APPROVED"
    root["source_license"] = "CC0 1.0 Universal (MPFB base asset)"
    scene_setup(out)
    scene = bpy.context.scene
    scene["re_camp_status"] = "WIP / MPFB HELPER SURFACE INSPECTION / NOT APPROVED"
    scene["re_camp_gate"] = "Gate A pending / Gate B blocked"
    blend = out / "CH101_A_MPFHelpers_WIP_v001.blend"
    bpy.ops.wm.save_as_mainfile(filepath=str(blend))
    if options.render:
        bpy.ops.render.render(write_still=True)
        bpy.ops.wm.save_as_mainfile(filepath=str(blend))
    report = {"status": "WIP / MPFB HELPER SURFACE INSPECTION / NOT APPROVED", "blend": str(blend), "source_obj": str(base_obj), "source_license": "CC0 1.0 Universal", "helpers": helper_report, "gate_a": "PENDING", "gate_b": "BLOCKED", "notes": ["Helper meshes are inspection inputs only", "Human visual review required", "No helper is promoted to production"]}
    (out / "reports" / "CH101_A_MPFHelpers_WIP_v001.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"Generated {blend}")
    print("Status: WIP / MPFB helper surface inspection / not approved")


if __name__ == "__main__":
    main()
