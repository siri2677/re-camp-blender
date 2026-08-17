#!/usr/bin/env python3
"""Generate a targeted MPFB human base for CH101-A visual work."""

from __future__ import annotations

import argparse
import importlib
import json
import math
import sys
from pathlib import Path

import bpy
from mathutils import Vector

SCRIPT_DIR = Path(__file__).resolve().parent
ROOT = SCRIPT_DIR.parent.parent
MPFB_SRC = ROOT / "vendor" / "mpfb2" / "src"
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))
if str(MPFB_SRC) not in sys.path:
    sys.path.insert(0, str(MPFB_SRC))

from build_ch101_mpfb_base_wip import clear, look_at, make_material, normalize_body  # noqa: E402


def parse_args() -> argparse.Namespace:
    raw = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--render", action="store_true")
    return parser.parse_args(raw)


def dynamic_import(package: str, key: str):
    for module_name in list(sys.modules):
        if module_name.endswith(package):
            module = importlib.import_module(module_name)
            if hasattr(module, key):
                return getattr(module, key)
    raise RuntimeError(f"MPFB module not available: {package}.{key}")


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
    floor.data.materials.append(make_material("TargetedReviewFloor", (0.018, 0.025, 0.045, 1.0), 0.55))
    bpy.ops.object.camera_add(location=(0.35, -6.9, 2.0))
    camera = bpy.context.object
    camera.data.lens = 62
    look_at(camera, Vector((0, 0, 1.9)))
    scene.camera = camera
    scene.render.filepath = str(out / "renders" / "CH101_A_MPFTargeted_WIP_3q.png")
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
    out = Path(options.output_dir).resolve()
    (out / "renders").mkdir(parents=True, exist_ok=True)
    (out / "reports").mkdir(parents=True, exist_ok=True)
    clear()
    import mpfb
    mpfb.register()
    human_service = dynamic_import("mpfb.services.humanservice", "HumanService")
    target_service = dynamic_import("mpfb.services.targetservice", "TargetService")
    object_properties = dynamic_import("mpfb.entities.objectproperties", "HumanObjectProperties")
    location_service = dynamic_import("mpfb.services.locationservice", "LocationService")
    human = human_service.create_human()
    object_properties.set_value("gender", 0.0, entity_reference=human)
    object_properties.set_value("age", 0.32, entity_reference=human)
    object_properties.set_value("asian", 0.82, entity_reference=human)
    object_properties.set_value("caucasian", 0.18, entity_reference=human)
    object_properties.set_value("african", 0.0, entity_reference=human)
    object_properties.set_value("weight", 0.34, entity_reference=human)
    object_properties.set_value("height", 0.48, entity_reference=human)
    object_properties.set_value("proportions", 0.34, entity_reference=human)
    object_properties.set_value("cupsize", 0.72, entity_reference=human)
    target_service.reapply_macro_details(human)
    targets_root = Path(location_service.get_mpfb_data("targets"))
    targets = [
        (targets_root / "head" / "head-oval.target.gz", 0.45),
        (targets_root / "eyes" / "l-eye-scale-incr.target.gz", 0.35),
        (targets_root / "eyes" / "r-eye-scale-incr.target.gz", 0.35),
        (targets_root / "breast" / "breast-volume-vert-up.target.gz", 0.25),
    ]
    loaded_targets = []
    for path, weight in targets:
        if path.exists():
            target_service.load_target(human, str(path), weight=weight)
            loaded_targets.append(path.name)
    human.name = "CH101_A_MPFTargetedBody_WIP"
    human.rotation_euler.x = math.radians(90.0)
    bpy.context.view_layer.objects.active = human
    bpy.ops.object.transform_apply(location=False, rotation=True, scale=False)
    bpy.context.view_layer.update()
    scale = 3.65 / human.dimensions.z
    human.scale = (scale, scale, scale)
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    bpy.context.view_layer.update()
    min_z = min(vertex.co.z for vertex in human.data.vertices)
    human.location.z -= min_z
    human.data.materials.append(make_material("MAT_CH101_TargetedSkin", (0.82, 0.50, 0.47, 1), 0.54))
    for polygon in human.data.polygons:
        polygon.use_smooth = True
    human["status"] = "WIP / TARGETED MPFB BODY / NOT APPROVED"
    human["source_license"] = "CC0 1.0 Universal (MPFB assets)"
    human["targets"] = ",".join(loaded_targets)
    setup_scene(out)
    scene = bpy.context.scene
    scene["re_camp_status"] = "WIP / TARGETED MPFB BODY / NOT APPROVED"
    scene["re_camp_character"] = "CH101-A Route Sprint"
    scene["re_camp_gate"] = "Gate A pending / Gate B blocked"
    scene["re_camp_source_license"] = "CC0 1.0 Universal"
    blend = out / "CH101_A_MPFTargetedBody_WIP_v001.blend"
    bpy.ops.wm.save_as_mainfile(filepath=str(blend))
    if options.render:
        bpy.ops.render.render(write_still=True)
        bpy.ops.wm.save_as_mainfile(filepath=str(blend))
    human.data.calc_loop_triangles()
    report = {
        "status": "WIP / TARGETED MPFB BODY / NOT APPROVED",
        "blend": str(blend),
        "source": "makehumancommunity/mpfb2",
        "source_license": "CC0 1.0 Universal",
        "targets_loaded": loaded_targets,
        "vertex_count": len(human.data.vertices),
        "triangle_count": len(human.data.loop_triangles),
        "gate_a": "PENDING",
        "gate_b": "BLOCKED / styling and rig bind incomplete",
        "notes": ["Targeted adult female body", "No CH101 hair/outfit/equipment yet", "Human review required"],
    }
    (out / "reports" / "CH101_A_MPFTargetedBody_WIP_v001.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"Generated {blend}")
    print(f"Targets: {', '.join(loaded_targets)}")
    print("Status: WIP / targeted MPFB body / not approved")


if __name__ == "__main__":
    main()
