#!/usr/bin/env python3
"""Refine an AI-generated candidate into a review-only normalized artifact.

This script performs conservative geometry cleanup and technical preparation. It
does not infer final facial topology, approve equipment sockets, or enable Unity
input. The output remains an AI review candidate until a human Gate B decision.
"""

from __future__ import annotations

import argparse
import json
import math
import hashlib
import sys
from pathlib import Path

import bmesh
import bpy
from mathutils import Matrix, Vector


SOURCE_STATUS = "AI_GENERATED_CANDIDATE_NOT_PRODUCTION"
GATE_B = "PENDING_HUMAN_REVIEW"
REVIEW_MATERIAL_NAME = "AI_REVIEW_NEUTRAL_AUTO"
PALETTE_MATERIALS_BY_CHARACTER = {
    "CH101": {
        "white": (0.957, 0.957, 0.933, 1.0),
        "graphite": (0.008, 0.008, 0.012, 1.0),
        "gold": (0.668, 0.391, 0.063, 1.0),
        "cyan": (0.0, 0.455, 0.672, 1.0),
        # Warm soft-matte skin sampled from the approved CH101 reference sheet;
        # this is review palette calibration, not final texture authoring.
        "skin": (0.974, 0.891, 0.814, 1.0),
        "hair": (0.008, 0.008, 0.012, 1.0),
    },
    "CH102": {
        "white": (0.40, 0.24, 0.68, 1.0),
        "graphite": (0.015, 0.012, 0.025, 1.0),
        "gold": (0.54, 0.37, 0.12, 1.0),
        "cyan": (0.32, 0.18, 0.62, 1.0),
        "skin": (0.95, 0.78, 0.72, 1.0),
        "hair": (0.63, 0.58, 0.76, 1.0),
    },
    "CH103": {
        "white": (0.95, 0.94, 0.90, 1.0),
        "graphite": (0.07, 0.06, 0.07, 1.0),
        "gold": (0.90, 0.33, 0.22, 1.0),
        "cyan": (0.02, 0.56, 0.62, 1.0),
        "skin": (0.96, 0.80, 0.73, 1.0),
        "hair": (0.86, 0.37, 0.29, 1.0),
    },
    "CH104": {
        "white": (0.90, 0.90, 0.88, 1.0),
        "graphite": (0.015, 0.04, 0.12, 1.0),
        "gold": (0.63, 0.45, 0.20, 1.0),
        "cyan": (0.30, 0.10, 0.42, 1.0),
        "skin": (0.95, 0.78, 0.72, 1.0),
        "hair": (0.01, 0.04, 0.12, 1.0),
    },
    "CH105": {
        "white": (0.03, 0.16, 0.15, 1.0),
        "graphite": (0.012, 0.014, 0.015, 1.0),
        "gold": (0.56, 0.36, 0.13, 1.0),
        "cyan": (0.0, 0.32, 0.30, 1.0),
        "skin": (0.92, 0.73, 0.65, 1.0),
        "hair": (0.01, 0.04, 0.04, 1.0),
    },
}
GENERIC_IMPORTED_MATERIAL_NAMES = {
    "defaultmaterial",
    "default material",
    "material",
}
PALETTE_ORDER = ("white", "graphite", "gold", "cyan", "skin", "hair")
# TripoSR's exported coordinate frame places the visually selected CH101 front
# on +X (the evaluator consistently selects ``pos_x``).  Keep the orientation
# choice explicit so the review-only material blocking follows the same frame.
PALETTE_REGION_ALGORITHM = "CH101_REVIEW_BLOCKING_XZ_POSITIVE_X_FRONT_V003"


def parse_args() -> argparse.Namespace:
    raw = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidate", required=True, type=Path)
    parser.add_argument("--character", default="CH101")
    parser.add_argument("--output-glb", required=True, type=Path)
    parser.add_argument("--output-blend", required=True, type=Path)
    parser.add_argument("--report", required=True, type=Path)
    parser.add_argument("--provider", required=True)
    parser.add_argument("--attempt", required=True, type=int)
    parser.add_argument("--parent-sha256", default="")
    parser.add_argument(
        "--material-mode",
        choices=("neutral", "preserve", "palette"),
        default="neutral",
        help="Use neutral, preserved, or coarse roster-palette review materials.",
    )
    parser.add_argument(
        "--invert-up-axis",
        action="store_true",
        help="Invert the normalized vertical polarity after an upside-down review detection.",
    )
    return parser.parse_args(raw)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def clear_scene() -> None:
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    for datablocks in (bpy.data.meshes, bpy.data.curves, bpy.data.materials, bpy.data.cameras, bpy.data.lights):
        for datablock in list(datablocks):
            if datablock.users == 0:
                datablocks.remove(datablock)


def import_candidate(path: Path) -> list[bpy.types.Object]:
    suffix = path.suffix.lower()
    if suffix in {".glb", ".gltf"}:
        bpy.ops.import_scene.gltf(filepath=str(path))
    elif suffix == ".obj":
        if hasattr(bpy.ops.wm, "obj_import"):
            try:
                bpy.ops.wm.obj_import(filepath=str(path))
            except (AttributeError, RuntimeError):
                # Blender 3.0 exposes the newer operator name but cannot call
                # it; use the legacy importer available in Kaggle's package.
                bpy.ops.import_scene.obj(filepath=str(path))
        else:
            bpy.ops.import_scene.obj(filepath=str(path))
    elif suffix == ".ply":
        if hasattr(bpy.ops.wm, "ply_import"):
            bpy.ops.wm.ply_import(filepath=str(path))
        else:
            bpy.ops.import_mesh.ply(filepath=str(path))
    else:
        raise ValueError(f"unsupported candidate format: {suffix}")
    meshes = [obj for obj in bpy.context.scene.objects if obj.type == "MESH"]
    if not meshes:
        raise ValueError("candidate contains no mesh objects")
    return meshes


def world_bounds(objects: list[bpy.types.Object]) -> tuple[Vector, Vector]:
    corners = []
    for obj in objects:
        corners.extend(obj.matrix_world @ Vector(corner) for corner in obj.bound_box)
    if not corners:
        raise ValueError("candidate contains no mesh bounds")
    return (
        Vector(tuple(min(point[index] for point in corners) for index in range(3))),
        Vector(tuple(max(point[index] for point in corners) for index in range(3))),
    )


def transform_candidate(
    objects: list[bpy.types.Object],
    target_height: float = 1.68,
    invert_up_axis: bool = False,
) -> dict[str, object]:
    minimum, maximum = world_bounds(objects)
    dimensions = maximum - minimum
    source_axis_index = max(range(3), key=lambda axis: dimensions[axis])
    orientation_fix = "NONE"
    if source_axis_index == 1:
        rotation = Matrix.Rotation(math.radians(90.0), 4, "X")
        orientation_fix = "Y_TO_Z"
    elif source_axis_index == 0:
        rotation = Matrix.Rotation(math.radians(-90.0), 4, "Y")
        orientation_fix = "X_TO_Z"
    else:
        rotation = Matrix.Identity(4)
    if invert_up_axis:
        rotation = Matrix.Rotation(math.radians(180.0), 4, "X") @ rotation
        orientation_fix = f"{orientation_fix}_INVERTED_UP_POLARITY"

    for obj in objects:
        obj.matrix_world = rotation @ obj.matrix_world
    bpy.context.view_layer.update()

    minimum, maximum = world_bounds(objects)
    height = maximum.z - minimum.z
    if height <= 1e-6:
        raise ValueError("candidate has zero height after orientation normalization")
    center = (minimum + maximum) * 0.5
    scale = target_height / height
    transform = Matrix.Translation(Vector((-center.x * scale, -center.y * scale, -minimum.z * scale))) @ Matrix.Scale(scale, 4)
    for obj in objects:
        obj.matrix_world = transform @ obj.matrix_world
    bpy.context.view_layer.update()

    minimum, maximum = world_bounds(objects)
    return {
        "sourceUpAxis": "XYZ"[source_axis_index],
        "orientationFix": orientation_fix,
        "upAxisPolarity": "INVERTED" if invert_up_axis else "AS_IMPORTED",
        "verticalPolarityCorrectionApplied": invert_up_axis,
        "targetHeight": target_height,
        "dimensions": [round(value, 6) for value in (maximum - minimum)],
    }


def clean_mesh(obj: bpy.types.Object) -> dict[str, object]:
    mesh = obj.data
    mesh.calc_loop_triangles()
    before_vertices = len(mesh.vertices)
    before_triangles = len(mesh.loop_triangles)
    bm = bmesh.new()
    bm.from_mesh(mesh)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=0.00001)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(mesh)
    bm.free()
    mesh.update()

    uv_generated = False
    if not mesh.uv_layers:
        bpy.ops.object.select_all(action="DESELECT")
        obj.select_set(True)
        bpy.context.view_layer.objects.active = obj
        bpy.ops.object.mode_set(mode="EDIT")
        bpy.ops.mesh.select_all(action="SELECT")
        bpy.ops.uv.smart_project(angle_limit=math.radians(66.0), island_margin=0.03)
        bpy.ops.object.mode_set(mode="OBJECT")
        uv_generated = True

    mesh.calc_loop_triangles()
    return {
        "object": obj.name,
        "verticesBefore": before_vertices,
        "verticesAfter": len(mesh.vertices),
        "trianglesBefore": before_triangles,
        "trianglesAfter": len(mesh.loop_triangles),
        "uvGenerated": uv_generated,
        "uvLayers": len(mesh.uv_layers),
    }


def has_reviewable_imported_material(obj: bpy.types.Object) -> bool:
    """Return true only when imported appearance carries usable identity data.

    TripoSR can export a non-generic material name while still assigning one
    flat dark-gray material to the entire mesh. Treating that as meaningful
    appearance allowed a generic gray candidate to bypass the CH101 palette
    fallback. Textures always count; material-only inputs need visible color
    diversity before they are preserved.
    """
    material_colors = []
    for material in obj.data.materials:
        if material is None:
            continue
        if material.node_tree and any(
            node.type == "TEX_IMAGE" and getattr(node, "image", None) is not None
            for node in material.node_tree.nodes
        ):
            return True
        if material.name.strip().casefold() in GENERIC_IMPORTED_MATERIAL_NAMES:
            continue
        if material.node_tree:
            principled = material.node_tree.nodes.get("Principled BSDF")
            base_color = principled.inputs.get("Base Color") if principled else None
            value = getattr(base_color, "default_value", None)
            if value is not None and len(value) >= 3:
                material_colors.append(tuple(float(value[index]) for index in range(3)))
        else:
            diffuse = getattr(material, "diffuse_color", None)
            if diffuse is not None and len(diffuse) >= 3:
                material_colors.append(tuple(float(diffuse[index]) for index in range(3)))

    if not material_colors:
        return False
    if len(material_colors) > 1:
        channel_range = max(
            max(color[channel] for color in material_colors)
            - min(color[channel] for color in material_colors)
            for channel in range(3)
        )
        if channel_range >= 0.15:
            return True
    return any(
        max(color) >= 0.12
        and (max(color) - min(color)) / max(max(color), 0.001) >= 0.12
        for color in material_colors
    )


def ensure_review_material(
    obj: bpy.types.Object,
    material_mode: str,
    character: str,
    global_minimum: Vector | None = None,
    global_maximum: Vector | None = None,
) -> list[str]:
    if material_mode == "preserve" and has_reviewable_imported_material(obj):
        return [material.name for material in obj.data.materials if material is not None]

    if material_mode == "preserve":
        return apply_palette_review_materials(
            obj, character, global_minimum, global_maximum
        )

    material = bpy.data.materials.get(REVIEW_MATERIAL_NAME)
    if material is None:
        material = bpy.data.materials.new(REVIEW_MATERIAL_NAME)
        material.use_nodes = True
        principled = material.node_tree.nodes.get("Principled BSDF")
        if principled is not None:
            principled.inputs["Base Color"].default_value = (0.32, 0.42, 0.50, 1.0)
            principled.inputs["Roughness"].default_value = 0.58
    if obj.data.materials.get(REVIEW_MATERIAL_NAME) is None:
        obj.data.materials.append(material)
    material_index = obj.data.materials.find(material.name)
    for polygon in obj.data.polygons:
        polygon.material_index = material_index
    return [material.name]


def apply_palette_review_materials(
    obj: bpy.types.Object,
    character: str,
    global_minimum: Vector | None = None,
    global_maximum: Vector | None = None,
) -> list[str]:
    """Apply a conservative roster palette approximation when textures are absent.

    This is a review aid for untextured AI meshes, not texture generation. CH101
    uses a deterministic coarse blocking profile based on global normalized
    height, horizontal position, and front-facing normals. The report labels
    the result as an approximation so it cannot be mistaken for final art.
    """
    palette = PALETTE_MATERIALS_BY_CHARACTER.get(
        character, PALETTE_MATERIALS_BY_CHARACTER["CH101"]
    )
    materials = {}
    for key, rgba in palette.items():
        name = f"{character}_AI_REVIEW_PALETTE_{key.upper()}"
        material = bpy.data.materials.get(name) or bpy.data.materials.new(name)
        material.use_nodes = True
        material.diffuse_color = rgba
        principled = material.node_tree.nodes.get("Principled BSDF")
        if principled is not None:
            principled.inputs["Base Color"].default_value = rgba
            principled.inputs["Roughness"].default_value = 0.58
        materials[key] = material

    obj.data.materials.clear()
    ordered = [materials[key] for key in PALETTE_ORDER]
    for material in ordered:
        obj.data.materials.append(material)

    if global_minimum is None or global_maximum is None:
        global_minimum, global_maximum = world_bounds([obj])
    global_height = max(global_maximum.z - global_minimum.z, 1e-6)
    global_center_x = (global_minimum.x + global_maximum.x) * 0.5
    global_half_width = max((global_maximum.x - global_minimum.x) * 0.5, 1e-6)
    assignment_counts = {key: 0 for key in PALETTE_ORDER}
    for polygon in obj.data.polygons:
        world_center = obj.matrix_world @ polygon.center
        normalized_z = max(
            0.0,
            min(1.0, (world_center.z - global_minimum.z) / global_height),
        )
        normalized_x = max(
            -1.0,
            min(1.0, (world_center.x - global_center_x) / global_half_width),
        )
        world_normal = obj.matrix_world.to_3x3() @ polygon.normal
        # The provider mesh is not guaranteed to use the same forward axis as
        # the Blender scene.  For CH101, the evaluator's silhouette pass has
        # selected +X as the front on the pinned TripoSR output, so use +X for
        # this coarse review-only color blocking.  This is not semantic
        # landmark transfer or final texture authoring.
        front_facing = (
            world_normal.x > 0.2
            if character == "CH101"
            else world_normal.y < -0.2
        )
        if character == "CH101":
            # CH101's approved sheet is dominated by black hair/outfit,
            # white jacket/boots, warm skin, and sparse cyan/gold accents.
            # These regions are intentionally only a visual review heuristic.
            if normalized_z < 0.15:
                key = "white" if front_facing else "graphite"
            elif normalized_z < 0.47:
                key = "skin"
            elif normalized_z < 0.62:
                key = "graphite"
            elif normalized_z < 0.80:
                key = "white" if abs(normalized_x) > 0.34 else "graphite"
            elif normalized_z < 0.90:
                key = (
                    "skin"
                    if front_facing and abs(normalized_x) < 0.26
                    else "hair"
                )
            else:
                key = "hair"

            # Add broad, low-frequency accent regions instead of random
            # single-triangle speckling. This keeps cyan/gold visible without
            # fabricating a texture or claiming semantic landmark transfer.
            if (
                normalized_z < 0.15
                and abs(normalized_x) > 0.38
                and polygon.index % 5 == 0
            ):
                key = "cyan"
            elif 0.62 <= normalized_z < 0.86 and front_facing:
                if (
                    0.36 < abs(normalized_x) < 0.70
                    and polygon.index % 7 == 0
                ):
                    key = "gold"
                elif abs(normalized_x) > 0.62 and polygon.index % 11 == 0:
                    key = "cyan"
        else:
            # Keep the existing conservative roster fallback for characters
            # whose visual profile has not yet received a calibrated review.
            if normalized_z < 0.16:
                key = "white" if front_facing else "graphite"
            elif normalized_z < 0.56:
                key = "skin"
            elif normalized_z < 0.69:
                key = "graphite"
            elif normalized_z < 0.84:
                key = "white" if front_facing else "graphite"
            elif normalized_z < 0.92:
                key = "skin" if front_facing else "hair"
            else:
                key = "hair"
            if polygon.index % 37 == 0 and normalized_z > 0.20:
                key = "cyan"
            elif polygon.index % 53 == 0 and normalized_z > 0.30:
                key = "gold"
        assignment_counts[key] += 1
        polygon.material_index = PALETTE_ORDER.index(key)
    obj["review_palette_algorithm"] = (
        PALETTE_REGION_ALGORITHM
        if character == "CH101"
        else "LEGACY_HEIGHT_BANDS_V001"
    )
    obj["review_palette_assignment_counts"] = json.dumps(
        assignment_counts, sort_keys=True
    )
    return [material.name for material in ordered]


def main() -> int:
    args = parse_args()
    candidate = args.candidate.resolve()
    if not candidate.is_file():
        raise FileNotFoundError(candidate)
    args.output_glb.parent.mkdir(parents=True, exist_ok=True)
    args.output_blend.parent.mkdir(parents=True, exist_ok=True)
    args.report.parent.mkdir(parents=True, exist_ok=True)

    clear_scene()
    imported = import_candidate(candidate)
    transform = transform_candidate(imported, invert_up_axis=args.invert_up_axis)
    cleanup = [clean_mesh(obj) for obj in imported]
    had_imported_materials = any(has_reviewable_imported_material(obj) for obj in imported)
    global_minimum, global_maximum = world_bounds(imported)
    if args.material_mode == "palette":
        material_names = sorted(
            {
                material_name
                for obj in imported
                for material_name in apply_palette_review_materials(
                    obj,
                    args.character,
                    global_minimum,
                    global_maximum,
                )
            }
        )
    else:
        material_names = sorted(
            {
                material_name
                for obj in imported
                for material_name in ensure_review_material(
                    obj,
                    args.material_mode,
                    args.character,
                    global_minimum,
                    global_maximum,
                )
            }
        )
    palette_fallback_used = args.material_mode == "preserve" and not had_imported_materials
    palette_review_used = args.material_mode == "palette"
    minimum, maximum = global_minimum, global_maximum
    triangle_count = sum(len(obj.data.loop_triangles) for obj in imported)
    uv_missing = [obj.name for obj in imported if not obj.data.uv_layers]

    scene = bpy.context.scene
    scene["source_status"] = SOURCE_STATUS
    scene["gate_b"] = GATE_B
    scene["unity_input_allowed"] = False
    scene["production_promotion_allowed"] = False
    scene["refinement_stage"] = "TECHNICAL_REVIEW_REFINEMENT"
    scene["face_driver_status"] = "BLOCKED_NO_RELIABLE_FREE_FACE_LANDMARK_TRANSFER"
    scene["socket_status"] = "AUTO_ESTIMATED_NOT_APPROVED"

    bpy.ops.wm.save_as_mainfile(filepath=str(args.output_blend))
    gltf_export_error = ""
    try:
        bpy.ops.object.select_all(action="SELECT")
        bpy.ops.export_scene.gltf(filepath=str(args.output_glb), export_format="GLB", export_apply=True)
    except Exception as exc:
        gltf_export_error = f"{type(exc).__name__}: {exc}"
    if not args.output_glb.is_file() and not gltf_export_error:
        gltf_export_error = "GLB exporter returned without creating the requested file"

    warnings = [
        (
            (
                "Imported textures/material colors were preserved for review scoring."
                if had_imported_materials
                else "Imported appearance was neutral or non-identity; roster palette fallback was used for review scoring."
            )
            if args.material_mode == "preserve"
            else (
                "Coarse roster palette materials were assigned by "
                f"{PALETTE_REGION_ALGORITHM if args.character == 'CH101' else 'legacy height bands'} "
                "for review only."
                if args.material_mode == "palette"
                else "Neutral review material is automatic and not a final art material."
            )
        ),
    ]
    if palette_fallback_used:
        warnings.append(
            f"No imported material was present; {args.character} palette was assigned by coarse geometry bands for review only."
        )
    if args.invert_up_axis:
        warnings.append(
            "Vertical polarity was inverted after automated upside-down render detection."
        )
    warnings.extend([
        "The refined candidate is not a Production Mesh.",
        "Human Gate B review is required before any Unity input.",
    ])
    if gltf_export_error:
        warnings.append(
            "GLB export was unavailable; the normalized .blend remains the review source and the transport input may be evaluated directly."
        )
        warnings.append(f"GLB export diagnostic: {gltf_export_error}")

    report = {
        "character": args.character,
        "candidatePath": str(candidate),
        "candidateSha256": sha256_file(candidate),
        "refinedGlb": str(args.output_glb.resolve()),
        "refinedGlbSha256": sha256_file(args.output_glb) if args.output_glb.is_file() else "",
        "normalizedBlend": str(args.output_blend.resolve()),
        "provider": args.provider,
        "attempt": args.attempt,
        "parentSha256": args.parent_sha256,
        "status": (
            "REFINED_REVIEW_CANDIDATE"
            if not gltf_export_error
            else "REFINED_REVIEW_CANDIDATE_GLTF_EXPORT_FAILED"
        ),
        "sourceStatus": SOURCE_STATUS,
        "gateB": GATE_B,
        "unityInputAllowed": False,
        "productionPromotionAllowed": False,
        "orientation": transform,
        "metrics": {
            "meshCount": len(imported),
            "triangleCount": triangle_count,
            "materialCount": len(material_names),
            "materialNames": material_names,
            "uvMissing": sorted(uv_missing),
            "boundsMin": list(minimum),
            "boundsMax": list(maximum),
            "dimensions": list(maximum - minimum),
        },
        "cleanup": cleanup,
        "faceDriver": {
            "status": "BLOCKED_NO_RELIABLE_FREE_FACE_LANDMARK_TRANSFER",
            "blendShapeCount": 0,
        },
        "socketStatus": "AUTO_ESTIMATED_NOT_APPROVED",
        "materialMode": args.material_mode,
        "paletteFallbackUsed": palette_fallback_used,
        "paletteReviewUsed": palette_review_used,
        "paletteAlgorithm": (
            PALETTE_REGION_ALGORITHM
            if args.material_mode == "palette" and args.character == "CH101"
            else "LEGACY_HEIGHT_BANDS_V001"
            if args.material_mode == "palette"
            else None
        ),
        "paletteAssignmentCounts": {
            obj.name: json.loads(obj.get("review_palette_assignment_counts", "{}"))
            for obj in imported
            if obj.get("review_palette_assignment_counts")
        },
        "warnings": warnings,
    }
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
