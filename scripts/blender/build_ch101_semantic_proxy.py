#!/usr/bin/env python3
"""Build a review-only CH101 semantic proxy from locked art references.

This script is the CPU-capable branch of the free hybrid plan.  It creates a
readable, separately tagged body/face, hair, outfit, and equipment scaffold
from the existing Blender modelling helpers, then adds review-only LODs,
heuristic rigging, and estimated sockets.  It is never a Production Mesh:
face blendshapes remain placeholders and every Unity/production gate stays
false.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

import bpy
from mathutils import Vector


SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import build_ai3d_review_asset as review  # type: ignore
import build_ch101_base_mesh_wip as base  # type: ignore


SOURCE_STATUS = "AI_GENERATED_CANDIDATE_NOT_PRODUCTION"
GATE_B = "PENDING_HUMAN_REVIEW"
FACE_STATUS = "BLOCKED_NO_RELIABLE_FREE_FACE_LANDMARK_TRANSFER"
SOCKET_STATUS = "AUTO_ESTIMATED_NOT_APPROVED"
COLLECTIONS = (
    "REF_CH101_SEMANTIC_INPUTS",
    "MODEL_HIGH_BODY",
    "MODEL_CLOTH_OUTFIT",
    "MODEL_HAIR",
    "MODEL_EQUIPMENT",
    "AI_REVIEW_LOD0_NOT_PRODUCTION",
    "AI_REVIEW_LOD1_NOT_PRODUCTION",
    "AI_REVIEW_LOD2_NOT_PRODUCTION",
    "AI_REVIEW_RIG_NOT_PRODUCTION",
    "AI_REVIEW_SOCKETS_NOT_PRODUCTION",
)
FACE_PLACEHOLDERS = (
    "Blink_L",
    "Blink_R",
    "Face_Smile",
    "Viseme_A",
    "Viseme_E",
    "Viseme_I",
    "Viseme_O",
    "Viseme_U",
)


def parse_args() -> argparse.Namespace:
    raw = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--reference-report", required=True, type=Path)
    parser.add_argument("--art-root", required=True, type=Path)
    parser.add_argument("--socket-contract", required=True, type=Path)
    parser.add_argument("--render", action="store_true")
    return parser.parse_args(raw)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_and_verify_references(report_path: Path, art_root: Path) -> dict[str, Any]:
    report = json.loads(report_path.read_text(encoding="utf-8"))
    if report.get("character") != "CH101":
        raise ValueError("semantic proxy only supports CH101")
    if report.get("status") not in {
        "READY_INPUTS_BLOCKED_AUTHORING",
        "SEMANTIC_PROXY_INPUTS_READY",
    }:
        raise ValueError(f"semantic reference report is not ready: {report.get('status')}")
    if report.get("unityInputAllowed") is not False:
        raise ValueError("reference report cannot enable Unity input")
    if report.get("productionPromotionAllowed") is not False:
        raise ValueError("reference report cannot enable production promotion")
    if report.get("sourceStatus") != SOURCE_STATUS:
        raise ValueError("reference report source status is not a locked candidate status")
    if report.get("gateB") != GATE_B:
        raise ValueError("reference report Gate B must remain pending")
    if report.get("artCommitActual") != report.get("artCommitExpected"):
        raise ValueError("reference report art commit is not verified")
    references = report.get("references")
    if not isinstance(references, list) or len(references) != 4:
        raise ValueError("semantic proxy requires four locked references")
    for reference in references:
        relative = reference.get("path")
        expected_hash = reference.get("sha256")
        if not isinstance(relative, str) or not isinstance(expected_hash, str):
            raise ValueError("semantic reference entries need path and SHA256")
        path = (art_root / relative).resolve()
        if not path.is_file():
            raise FileNotFoundError(path)
        try:
            path.relative_to(art_root.resolve())
        except ValueError as exc:
            raise ValueError("semantic reference escaped art root") from exc
        if sha256_file(path) != expected_hash:
            raise ValueError(f"semantic reference SHA256 mismatch: {relative}")
    return report


def make_materials() -> dict[str, bpy.types.Material]:
    # Reuse six materials for all semantic sub-parts; the proxy must not grow
    # an unbounded material palette while it is being reviewed.
    skin = base.mat("MAT_PROXY_Skin", (0.86, 0.58, 0.54, 1.0), 0.58)
    hair = base.mat("MAT_PROXY_Hair", (0.012, 0.018, 0.030, 1.0), 0.25)
    white = base.mat("MAT_PROXY_White", (0.88, 0.87, 0.81, 1.0), 0.46)
    graphite = base.mat("MAT_PROXY_Graphite", (0.022, 0.030, 0.048, 1.0), 0.38)
    cyan = base.mat("MAT_PROXY_Cyan", (0.01, 0.42, 0.62, 1.0), 0.28, metallic=0.12, emission=True)
    gold = base.mat("MAT_PROXY_Gold", (0.78, 0.38, 0.065, 1.0), 0.25, metallic=0.72)
    return {
        "skin": skin,
        "skin_shadow": skin,
        "eye": white,
        "iris": cyan,
        "pupil": graphite,
        "eye_highlight": white,
        "lip": gold,
        "hair": hair,
        "white": white,
        "graphite": graphite,
        "gold": gold,
        "cyan": cyan,
    }


def classify(name: str) -> str:
    if name.startswith(("Face", "Eye", "Iris", "Pupil", "Brow", "Nose", "Mouth", "Body", "LegBase", "Neck", "Bust", "Arm", "Hand")):
        return "body_face"
    if name.startswith(("Hair", "Bang", "SideLock", "Ponytail", "CourierHood")):
        return "hair"
    if name.startswith(("Saber", "SignalRibbon", "RibbonAccent", "CourierPouch")):
        return "equipment"
    return "outfit"


def convert_curves_to_mesh(objects: list[bpy.types.Object]) -> list[bpy.types.Object]:
    converted: list[bpy.types.Object] = []
    for obj in objects:
        if obj.type != "CURVE":
            converted.append(obj)
            continue
        bpy.ops.object.select_all(action="DESELECT")
        obj.hide_set(False)
        obj.select_set(True)
        bpy.context.view_layer.objects.active = obj
        bpy.ops.object.convert(target="MESH")
        converted.append(bpy.context.object)
    return converted


def build_semantic_lods(
    source_meshes: list[bpy.types.Object],
) -> tuple[dict[str, list[bpy.types.Object]], dict[str, int], dict[str, int]]:
    source_triangles = review.triangle_count(source_meshes)
    lod0_ratio = min(1.0, 20000 / max(source_triangles, 1))
    ratios = {"LOD0": lod0_ratio, "LOD1": lod0_ratio * 0.55, "LOD2": lod0_ratio * 0.30}
    lod_objects: dict[str, list[bpy.types.Object]] = {}
    counts: dict[str, int] = {"SOURCE": source_triangles}
    part_counts: dict[str, int] = {"body_face": 0, "hair": 0, "outfit": 0, "equipment": 0}
    for source in source_meshes:
        source.hide_render = True
        source.hide_set(True)
    for lod_name, ratio in ratios.items():
        collection = review.ensure_collection(f"AI_REVIEW_{lod_name}_NOT_PRODUCTION")
        copies: list[bpy.types.Object] = []
        for source in source_meshes:
            duplicate = source.copy()
            duplicate.data = source.data.copy()
            duplicate.name = f"AI3D_{lod_name}_{source.name}"
            for modifier in list(duplicate.modifiers):
                duplicate.modifiers.remove(modifier)
            collection.objects.link(duplicate)
            duplicate.matrix_world = source.matrix_world.copy()
            duplicate.hide_render = lod_name != "LOD0"
            duplicate.hide_set(False)
            part = classify(source.name)
            duplicate["semanticPart"] = part
            duplicate["sourceStatus"] = SOURCE_STATUS
            duplicate["gateB"] = GATE_B
            duplicate["unityInputAllowed"] = False
            if lod_name == "LOD0":
                part_counts[part] += 1
            review.apply_decimate(duplicate, ratio)
            copies.append(duplicate)
        lod_objects[lod_name] = copies
        counts[lod_name] = review.triangle_count(copies)
    if any(value == 0 for value in part_counts.values()):
        raise ValueError(f"semantic component is missing: {part_counts}")
    return lod_objects, counts, part_counts


def build_review_scene(output_dir: Path, materials: dict[str, bpy.types.Material], render: bool) -> list[str]:
    scene = bpy.context.scene
    # Kaggle's distro Blender may expose the legacy EEVEE identifier while
    # Blender 4+ exposes BLENDER_EEVEE_NEXT. Select the first available
    # realtime engine so review rendering stays portable across runtimes.
    engine_property = scene.render.bl_rna.properties.get("engine")
    available_engines = {
        item.identifier for item in engine_property.enum_items
    } if engine_property is not None else set()
    for engine in ("BLENDER_EEVEE_NEXT", "BLENDER_EEVEE", "BLENDER_WORKBENCH"):
        if engine in available_engines:
            scene.render.engine = engine
            break
    else:
        raise RuntimeError(f"No supported review render engine is available: {sorted(available_engines)}")
    scene.render.resolution_x = 700
    scene.render.resolution_y = 900
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.world.color = (0.02, 0.025, 0.04)
    bpy.ops.mesh.primitive_plane_add(size=30, location=(0, 0.5, 0.0))
    floor = bpy.context.object
    floor.name = "ReviewFloor_NOT_PRODUCTION"
    floor.data.materials.append(materials["graphite"])
    bpy.ops.object.camera_add(location=(0, -6.8, 1.5))
    camera = bpy.context.object
    camera.name = "ReviewCamera_NOT_PRODUCTION"
    camera.data.lens = 58
    base.look_at(camera, Vector((0, 0, 1.45)))
    scene.camera = camera
    for name, loc, energy, color in (
        ("Key", (-4.5, -6, 6), 850, (1.0, 0.82, 0.72)),
        ("Fill", (4, -3, 4), 550, (0.50, 0.70, 1.0)),
        ("Rim", (0, 3.5, 5), 700, (0.12, 0.64, 1.0)),
    ):
        bpy.ops.object.light_add(type="AREA", location=loc)
        light = bpy.context.object
        light.name = f"ReviewLight_{name}_NOT_PRODUCTION"
        light.data.energy = energy
        light.data.color = color
        light.data.shape = "DISK"
        light.data.size = 4
        base.look_at(light, Vector((0, 0, 1.4)))
    if not render:
        return []
    renders: list[str] = []
    view_positions = {
        "front": (0.0, -6.8, 1.5),
        "right": (6.8, 0.0, 1.5),
        "back": (0.0, 6.8, 1.5),
        "3-4": (4.8, -4.8, 1.5),
    }
    for view, location in view_positions.items():
        camera.location = location
        base.look_at(camera, Vector((0, 0, 1.45)))
        path = output_dir / "renders" / f"CH101_semantic_proxy_{view}_NOT_PRODUCTION.png"
        scene.render.filepath = str(path)
        bpy.ops.render.render(write_still=True)
        renders.append(str(path))
    return renders


def export_lod0(output_dir: Path, lod0: list[bpy.types.Object], armature: bpy.types.Object) -> Path:
    for obj in bpy.context.selected_objects:
        obj.select_set(False)
    for obj in lod0:
        obj.hide_set(False)
        obj.select_set(True)
    armature.hide_set(False)
    armature.select_set(True)
    bpy.context.view_layer.objects.active = armature
    path = output_dir / "CH101_SEMANTIC_PROXY_REFERENCE_FITTED_NOT_PRODUCTION.glb"
    bpy.ops.export_scene.gltf(filepath=str(path), export_format="GLB", use_selection=True, export_apply=True)
    return path


def main() -> int:
    options = parse_args()
    output_dir = options.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "renders").mkdir(parents=True, exist_ok=True)
    reference_report = read_and_verify_references(options.reference_report.resolve(), options.art_root.resolve())
    socket_contract = json.loads(options.socket_contract.resolve().read_text(encoding="utf-8"))
    if socket_contract.get("contractVersion") != "current-roster-socket-contract-v001":
        raise ValueError("unexpected socket contract version")
    if not any(entry.get("code") == "CH101" for entry in socket_contract.get("characters", [])):
        raise ValueError("socket contract has no CH101 entry")

    base.clear()
    materials = make_materials()
    semantic_collections = {
        "body_face": review.ensure_collection("MODEL_HIGH_BODY"),
        "outfit": review.ensure_collection("MODEL_CLOTH_OUTFIT"),
        "hair": review.ensure_collection("MODEL_HAIR"),
        "equipment": review.ensure_collection("MODEL_EQUIPMENT"),
    }
    for name in COLLECTIONS:
        review.ensure_collection(name)
    root = base.character(0.0, "A", materials)
    root.name = "CH101_SEMANTIC_PROXY_REFERENCE_FITTED_ROOT_NOT_PRODUCTION"
    root["sourceStatus"] = SOURCE_STATUS
    root["gateB"] = GATE_B
    root["unityInputAllowed"] = False
    root["productionPromotionAllowed"] = False
    root["strategyId"] = "SEMANTIC_PROXY_REFERENCE_FITTED_V001"
    root["semanticProxyQualityPolicy"] = "SLAB_GRAYBOX_NOT_ACCEPTED"

    generated = [obj for obj in list(bpy.data.objects) if obj.parent == root]
    generated = convert_curves_to_mesh(generated)
    source_meshes: list[bpy.types.Object] = []
    for obj in generated:
        if obj.type != "MESH":
            continue
        part = classify(obj.name)
        review.move_to_collection(obj, semantic_collections[part])
        obj["semanticPart"] = part
        obj["sourceStatus"] = SOURCE_STATUS
        obj["gateB"] = GATE_B
        obj["unityInputAllowed"] = False
        source_meshes.append(obj)
    if not source_meshes:
        raise ValueError("semantic proxy produced no mesh objects")

    lods, triangle_counts, part_counts = build_semantic_lods(source_meshes)
    armature = review.build_humanoid_rig(lods["LOD0"], "CH101")
    weight_status, weight_error, weight_audit = review.auto_weight(lods["LOD0"], armature, "CH101")
    socket_report = review.build_sockets(armature, socket_contract, "CH101")
    socket_report["status"] = SOCKET_STATUS

    scene = bpy.context.scene
    scene["re_camp_status"] = SOURCE_STATUS
    scene["re_camp_character"] = "CH101"
    scene["strategy_id"] = "SEMANTIC_PROXY_REFERENCE_FITTED_V001"
    scene["gate_b"] = GATE_B
    scene["unity_input_allowed"] = False
    scene["production_promotion_allowed"] = False
    scene["face_driver_status"] = FACE_STATUS
    scene["face_blendshape_placeholders"] = json.dumps(FACE_PLACEHOLDERS)
    scene["socket_status"] = socket_report["status"]
    scene["auto_weight_status"] = weight_status
    renders = build_review_scene(output_dir, materials, options.render)
    blend_path = output_dir / "CH101_SEMANTIC_PROXY_REFERENCE_FITTED_NOT_PRODUCTION.blend"
    bpy.ops.wm.save_as_mainfile(filepath=str(blend_path))
    glb_path = export_lod0(output_dir, lods["LOD0"], armature)
    bpy.ops.wm.save_as_mainfile(filepath=str(blend_path))
    report = {
        "schemaVersion": "ch101-semantic-proxy-report-v001",
        "character": "CH101",
        "subject": reference_report.get("subject", "AmasawaRin"),
        "strategyId": "SEMANTIC_PROXY_REFERENCE_FITTED_V001",
        "status": "SEMANTIC_PROXY_REVIEW_CANDIDATE_NOT_PRODUCTION",
        "sourceStatus": SOURCE_STATUS,
        "gateB": GATE_B,
        "unityInputAllowed": False,
        "productionPromotionAllowed": False,
        "referenceReport": str(options.reference_report.resolve()),
        "referenceInputHashes": {
            str(reference["id"]): reference["sha256"]
            for reference in reference_report.get("references", [])
            if isinstance(reference, dict) and reference.get("id") and reference.get("sha256")
        },
        "referenceManifestSha256": reference_report.get("referenceManifestSha256", ""),
        "artCommit": reference_report.get("artCommitExpected", ""),
        "collections": list(COLLECTIONS),
        "semanticPartObjectCountsLOD0": part_counts,
        "triangleCounts": triangle_counts,
        "blend": str(blend_path),
        "blendSha256": sha256_file(blend_path),
        "glb": str(glb_path),
        "glbSha256": sha256_file(glb_path),
        "lods": ["LOD0", "LOD1", "LOD2"],
        "rig": {"status": weight_status, "error": weight_error, "audit": weight_audit},
        "sockets": {**socket_report, "status": SOCKET_STATUS},
        "face": {"status": FACE_STATUS, "placeholders": list(FACE_PLACEHOLDERS), "generated": False},
        "renders": renders,
        "qualityPolicy": {
            "slabGrayboxAccepted": False,
            "requiresStrictVisualQA": True,
            "promotionDecision": "PENDING_STRICT_VISUAL_QA_AND_HUMAN_GATE_B",
        },
    }
    report_path = output_dir / "semantic-proxy-report.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
