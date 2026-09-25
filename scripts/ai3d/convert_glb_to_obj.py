#!/usr/bin/env python3
"""Convert a binary glTF mesh to a Blender-compatible OBJ using stdlib only.

Wonder3D's NeuS exporter can produce a valid GLB that Blender 3.0's bundled
glTF importer cannot open.  This converter is a transport compatibility path,
not a remeshing or quality-improvement step.  It copies positions and triangle
indices only; materials, textures, rigs, sockets, and face landmarks must still
be handled by the review pipeline and remain non-production.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import struct
import sys
from pathlib import Path
from typing import Any, Iterable


GLB_MAGIC = 0x46546C67
GLB_VERSION = 2
JSON_CHUNK = 0x4E4F534A
BIN_CHUNK = 0x004E4942
TRIANGLES_MODE = 4

COMPONENTS: dict[int, tuple[str, int]] = {
    5120: ("b", 1),
    5121: ("B", 1),
    5122: ("h", 2),
    5123: ("H", 2),
    5125: ("I", 4),
    5126: ("f", 4),
}
ARITY = {"SCALAR": 1, "VEC2": 2, "VEC3": 3, "VEC4": 4}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_glb(path: Path) -> tuple[dict[str, Any], bytes]:
    payload = path.read_bytes()
    if len(payload) < 12:
        raise ValueError("GLB header is truncated")
    magic, version, declared_length = struct.unpack_from("<III", payload, 0)
    if magic != GLB_MAGIC:
        raise ValueError("input is not a binary GLB")
    if version != GLB_VERSION:
        raise ValueError(f"unsupported GLB version: {version}")
    if declared_length != len(payload):
        raise ValueError(
            f"GLB length mismatch: header={declared_length}, actual={len(payload)}"
        )
    offset = 12
    document: dict[str, Any] | None = None
    binary = b""
    while offset < declared_length:
        if offset + 8 > declared_length:
            raise ValueError("GLB chunk header is truncated")
        chunk_length, chunk_type = struct.unpack_from("<II", payload, offset)
        offset += 8
        end = offset + chunk_length
        if end > declared_length:
            raise ValueError("GLB chunk exceeds declared file length")
        chunk = payload[offset:end]
        offset = end
        if chunk_type == JSON_CHUNK:
            try:
                document = json.loads(chunk.rstrip(b" \t\r\n\x00").decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError) as error:
                raise ValueError("GLB JSON chunk is invalid") from error
        elif chunk_type == BIN_CHUNK:
            binary = chunk
    if document is None:
        raise ValueError("GLB JSON chunk is missing")
    if not binary:
        raise ValueError("GLB BIN chunk is missing")
    return document, binary


def _accessor_values(
    document: dict[str, Any], binary: bytes, accessor_index: int
) -> list[tuple[int | float, ...]]:
    accessors = document.get("accessors", [])
    views = document.get("bufferViews", [])
    try:
        accessor = accessors[accessor_index]
        view = views[accessor["bufferView"]]
        fmt, component_size = COMPONENTS[accessor["componentType"]]
        arity = ARITY[accessor["type"]]
    except (KeyError, IndexError) as error:
        raise ValueError(f"unsupported or incomplete GLB accessor: {accessor_index}") from error
    if accessor.get("sparse"):
        raise ValueError("sparse GLB accessors are not supported")
    count = int(accessor["count"])
    element_size = component_size * arity
    stride = int(view.get("byteStride", element_size))
    if stride < element_size:
        raise ValueError("GLB accessor byteStride is smaller than its element")
    start = int(view.get("byteOffset", 0)) + int(accessor.get("byteOffset", 0))
    end = start + max(0, count - 1) * stride + element_size
    if start < 0 or end > len(binary):
        raise ValueError("GLB accessor points outside the BIN chunk")
    values = []
    for index in range(count):
        values.append(
            struct.unpack_from(
                "<" + fmt * arity,
                binary,
                start + index * stride,
            )
        )
    return values


def extract_triangles(document: dict[str, Any], binary: bytes) -> tuple[list[tuple[float, float, float]], list[tuple[int, int, int]]]:
    vertices: list[tuple[float, float, float]] = []
    faces: list[tuple[int, int, int]] = []
    for mesh in document.get("meshes", []):
        for primitive in mesh.get("primitives", []):
            if primitive.get("mode", TRIANGLES_MODE) != TRIANGLES_MODE:
                raise ValueError("only TRIANGLES GLB primitives are supported")
            attributes = primitive.get("attributes", {})
            if "POSITION" not in attributes:
                continue
            position_values = _accessor_values(document, binary, attributes["POSITION"])
            base = len(vertices)
            vertices.extend(tuple(float(value) for value in value[:3]) for value in position_values)
            if "indices" in primitive:
                indices = [int(value[0]) for value in _accessor_values(document, binary, primitive["indices"])]
            else:
                indices = list(range(len(position_values)))
            if len(indices) % 3:
                raise ValueError("GLB triangle index count is not divisible by three")
            for offset in range(0, len(indices), 3):
                triangle = tuple(base + indices[offset + item] for item in range(3))
                if any(index < base or index >= base + len(position_values) for index in triangle):
                    raise ValueError("GLB triangle index points outside its POSITION accessor")
                faces.append(triangle)
    if not vertices or not faces:
        raise ValueError("GLB contains no triangle POSITION mesh")
    return vertices, faces


def write_obj(path: Path, vertices: Iterable[tuple[float, float, float]], faces: Iterable[tuple[int, int, int]]) -> tuple[int, int]:
    vertex_list = list(vertices)
    face_list = list(faces)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as stream:
        stream.write("# GLB transport compatibility conversion; materials are intentionally omitted.\n")
        for vertex in vertex_list:
            stream.write("v %.9f %.9f %.9f\n" % vertex)
        for face in face_list:
            stream.write("f %d %d %d\n" % tuple(index + 1 for index in face))
    return len(vertex_list), len(face_list)


def convert_glb_to_obj(input_path: Path, output_path: Path) -> dict[str, Any]:
    input_path = input_path.resolve()
    output_path = output_path.resolve()
    if input_path.suffix.lower() != ".glb":
        raise ValueError("GLB compatibility conversion requires a .glb input")
    document, binary = read_glb(input_path)
    vertices, faces = extract_triangles(document, binary)
    vertex_count, triangle_count = write_obj(output_path, vertices, faces)
    return {
        "status": "GLB_TO_OBJ_CONVERTED",
        "inputGlb": str(input_path),
        "inputGlbSha256": sha256_file(input_path),
        "outputObj": str(output_path),
        "outputObjSha256": sha256_file(output_path),
        "vertexCount": vertex_count,
        "triangleCount": triangle_count,
        "materialsPreserved": False,
        "texturesPreserved": False,
        "sourceStatus": "AI_GENERATED_CANDIDATE_NOT_PRODUCTION",
        "gateB": "PENDING_HUMAN_REVIEW",
        "unityInputAllowed": False,
        "productionPromotionAllowed": False,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-glb", required=True, type=Path)
    parser.add_argument("--output-obj", required=True, type=Path)
    parser.add_argument("--report", required=True, type=Path)
    return parser.parse_args(sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else [])


def main() -> int:
    args = parse_args()
    report = convert_glb_to_obj(args.input_glb, args.output_obj)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
