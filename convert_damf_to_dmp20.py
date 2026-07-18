from __future__ import annotations

import argparse
import os
import shutil
import struct
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import yaml


INT24_MIN = -(1 << 23)
INT24_MAX = (1 << 23) - 1
TRADITIONAL_7_1 = ["L", "R", "C", "LFE", "Lss", "Rss", "Lrs", "Rrs"]
TRADITIONAL_5_1_SIDE = ["L", "R", "C", "LFE", "Lss", "Rss"]
TRADITIONAL_5_1_BACK = ["L", "R", "C", "LFE", "Lrs", "Rrs"]
STEREO = ["L", "R"]
BED_LAYOUT_7_1_2 = [*TRADITIONAL_7_1, "Lts", "Rts"]
INPUT_BED_SLOT_COUNT = 10
OUTPUT_OBJECT_ID_BASE = 10
CANONICAL_BED_SLOT_BY_LABEL = {label: index for index, label in enumerate(BED_LAYOUT_7_1_2)}
SUPPORTED_BED_LAYOUTS = {
    frozenset(STEREO): "2.0",
    frozenset(TRADITIONAL_5_1_SIDE): "5.1 side",
    frozenset(TRADITIONAL_5_1_BACK): "5.1 back",
    frozenset(TRADITIONAL_7_1): "7.1",
    frozenset(BED_LAYOUT_7_1_2): "7.1.2",
}
CHANNEL_ALIASES = {
    "Ls": "Lss",
    "Rs": "Rss",
    "Lb": "Lrs",
    "Rb": "Rrs",
    "Ltm": "Lts",
    "Rtm": "Rts",
}
ATMOS_TOP_LEVEL_VALUES = [
    ("version", "0.3"),
]
PRESENTATION_REQUIRED_FIXED_VALUES = [
    ("type", "home"),
    ("creationTool", "DAMF Legacy Rewriter for DMPS v2.0 by LumaVista"),
    ("creationToolVersion", "Only Tested DAMF v0.5.0 & v0.5.1 to v0.3"),
]
PRESENTATION_REQUIRED_SOURCE_FIELDS = [
    "offset",
]
PRESENTATION_REQUIRED_OUTPUT_FIELDS = [
    "metadata",
    "audio",
]
PRESENTATION_OPTIONAL_SOURCE_FIELDS = [
    "ffoa",
    "surroundTrim_7_1",
    "surroundTrim_5_1",
    "fps",
]
PRESENTATION_OPTIONAL_PASSTHROUGH_FIELDS = [
    "scBedConfiguration",
    "scNumberOfElements",
    "roomWidth",
    "roomLength",
    "roomHeight",
    "screenSizeRatio",
]
METADATA_TOP_LEVEL_VALUES = [
    ("sampleRate", 48000),
]
METADATA_EVENT_OPTIONAL_SOURCE_FIELDS = [
    "objectID",
    "samplePos",
    "active",
    "pos",
    "snap",
    "elevation",
    "zones",
    "size",
    "size3D",
    "decorr",
    "importance",
    "gain",
    "rampLength",
    "dialog",
    "music",
    "screenFactor",
    "depthFactor",
]
METADATA_BOOLEAN_FIELDS = {
    "active",
    "snap",
    "elevation",
    "size3D",
    "decorr",
}


@dataclass
class Plan:
    bed_labels: list[str]
    bed_sources: list[list[int]]
    source_objects: list[dict]
    source_object_ids: list[int]
    source_object_audio_indices: list[int]


@dataclass(frozen=True)
class BedClassification:
    channels: list[tuple[str, int]]


def normalize_label(label: str) -> str:
    return CHANNEL_ALIASES.get(label, label)


def read_caf_layout(path: Path) -> dict:
    with path.open("rb") as f:
        if f.read(4) != b"caff":
            raise ValueError(f"{path} is not a CAF file")
        version_flags = f.read(4)
        desc = None
        free = b""
        edit_count = None
        data_start = None
        data_size = None
        while True:
            header = f.read(12)
            if len(header) < 12:
                break
            chunk_type = header[:4]
            chunk_size = struct.unpack(">q", header[4:12])[0]
            if chunk_type == b"desc":
                desc = bytearray(f.read(chunk_size))
            elif chunk_type == b"free":
                free = f.read(chunk_size)
            elif chunk_type == b"data":
                edit_count = f.read(4)
                data_start = f.tell()
                data_size = chunk_size - 4
                break
            else:
                if chunk_size < 0:
                    break
                f.seek(chunk_size, os.SEEK_CUR)
    if desc is None or edit_count is None or data_start is None or data_size is None:
        raise ValueError(f"{path} is missing required CAF chunks")
    sample_rate = struct.unpack(">d", desc[:8])[0]
    format_id = bytes(desc[8:12])
    flags, bytes_per_packet, frames_per_packet, channels, bits = struct.unpack(">IIIII", desc[12:32])
    if format_id != b"lpcm" or flags != 2 or frames_per_packet != 1 or bits != 24:
        raise ValueError(
            f"unsupported CAF format: format={format_id!r} flags={flags} fpp={frames_per_packet} bits={bits}"
        )
    return {
        "version_flags": version_flags,
        "desc": desc,
        "free": free,
        "edit_count": edit_count,
        "data_start": data_start,
        "data_size": data_size,
        "sample_rate": sample_rate,
        "bytes_per_packet": bytes_per_packet,
        "channels": channels,
        "bits": bits,
        "flags": flags,
    }


def int24le_to_i32(block: bytes, channels: int) -> np.ndarray:
    raw = np.frombuffer(block, dtype=np.uint8).reshape(-1, channels, 3).astype(np.int32)
    values = raw[:, :, 0] | (raw[:, :, 1] << 8) | (raw[:, :, 2] << 16)
    return np.where(values & 0x800000, values - 0x1000000, values)


def i32_to_int24le(samples: np.ndarray) -> bytes:
    if ((samples < INT24_MIN) | (samples > INT24_MAX)).any():
        raise ValueError("mixed audio exceeds 24-bit integer range")
    packed = samples.astype(np.int32)
    unsigned = np.where(packed < 0, packed + 0x1000000, packed).astype(np.uint32)
    out = np.empty((packed.shape[0], packed.shape[1], 3), dtype=np.uint8)
    out[:, :, 0] = unsigned & 0xFF
    out[:, :, 1] = (unsigned >> 8) & 0xFF
    out[:, :, 2] = (unsigned >> 16) & 0xFF
    return out.tobytes()


def classify_bed_instance(bed_instance: dict, index: int) -> BedClassification:
    channels = []
    seen = set()
    for channel in bed_instance.get("channels", []):
        label = normalize_label(str(channel["channel"]))
        if label in seen:
            raise ValueError(f"duplicate channel {label!r} in bedInstances[{index}]")
        seen.add(label)
        channels.append((label, int(channel["ID"])))

    layout_name = SUPPORTED_BED_LAYOUTS.get(frozenset(seen))
    if layout_name is None:
        labels = ",".join(label for label, _ in channels)
        raise ValueError(
            f"unsupported bed layout in bedInstances[{index}]: {labels}; "
            "expected exactly 2.0, 5.1 side, 5.1 back, 7.1, or 7.1.2"
        )
    return BedClassification(channels=channels)


def build_plan(source_atmos: Path) -> tuple[dict, Plan]:
    data = yaml.safe_load(source_atmos.read_text(encoding="utf-8"))
    presentation = data["presentations"][0]
    bed_instances = presentation.get("bedInstances", [])
    seen_source_ids: set[int] = set()

    def reserve_source_id(source_id: int) -> None:
        if source_id in seen_source_ids:
            raise ValueError(f"duplicate source channel/object ID: {source_id}")
        seen_source_ids.add(source_id)

    def validate_bed_id(bed_index: int, label: str, source_id: int) -> None:
        expected_id = bed_index * INPUT_BED_SLOT_COUNT + CANONICAL_BED_SLOT_BY_LABEL[label]
        if source_id != expected_id:
            block_start = bed_index * INPUT_BED_SLOT_COUNT
            block_end = block_start + INPUT_BED_SLOT_COUNT - 1
            raise ValueError(
                f"bedInstances[{bed_index}] channel {label} ID {source_id} should be {expected_id}; "
                f"input bed IDs must use canonical 7.1.2 slot positions inside reserved block {block_start}..{block_end}; "
                f"source objects still start after reserved block {block_start}..{block_end}"
            )
        reserve_source_id(source_id)

    bed_sources_by_label: dict[str, list[int]] = {}
    packed_audio_index = 0
    for index, bed_instance in enumerate(bed_instances):
        classification = classify_bed_instance(bed_instance, index)
        for label, source_id in classification.channels:
            validate_bed_id(index, label, source_id)
            bed_sources_by_label.setdefault(label, []).append(packed_audio_index)
            packed_audio_index += 1

    if set(BED_LAYOUT_7_1_2).issubset(bed_sources_by_label):
        bed_labels = BED_LAYOUT_7_1_2
    elif set(TRADITIONAL_7_1).issubset(bed_sources_by_label):
        bed_labels = TRADITIONAL_7_1
    elif set(TRADITIONAL_5_1_SIDE).issubset(bed_sources_by_label):
        bed_labels = TRADITIONAL_5_1_SIDE
    elif set(TRADITIONAL_5_1_BACK).issubset(bed_sources_by_label):
        bed_labels = TRADITIONAL_5_1_BACK
    else:
        bed_labels = STEREO
    missing = [label for label in bed_labels if label not in bed_sources_by_label]
    if missing:
        raise ValueError(f"missing required output bed channels: {missing}")
    if not bed_sources_by_label:
        raise ValueError("no compatible 2.0/5.1/7.1 bed channels found")

    source_objects = presentation.get("objects", [])
    first_source_object_id = len(bed_instances) * INPUT_BED_SLOT_COUNT
    object_audio_base = packed_audio_index
    source_object_ids = []
    source_object_audio_indices = []
    for object_index, obj in enumerate(source_objects):
        source_id = int(obj["ID"])
        if source_id < first_source_object_id:
            raise ValueError(
                f"source object ID {source_id} is below first object ID {first_source_object_id}; "
                f"{len(bed_instances)} input bed(s) reserve {first_source_object_id} ID slots"
            )
        reserve_source_id(source_id)
        source_object_ids.append(source_id)
        source_object_audio_indices.append(object_audio_base + object_index)
    return presentation, Plan(
        bed_labels=bed_labels,
        bed_sources=[bed_sources_by_label[label] for label in bed_labels],
        source_objects=source_objects,
        source_object_ids=source_object_ids,
        source_object_audio_indices=source_object_audio_indices,
    )


def flatten_audio_indices(
    bed_sources: list[list[int]],
    source_object_audio_indices: list[int],
) -> list[int]:
    used = [idx for group in bed_sources for idx in group]
    used += source_object_audio_indices
    return used


def bad_audio_indices(indices: list[int], source_channels: int) -> list[int]:
    return [idx for idx in indices if idx < 0 or idx >= source_channels]


def select_audio_sources(
    plan: Plan,
    source_channels: int,
) -> tuple[list[list[int]], list[int]]:
    indices = flatten_audio_indices(plan.bed_sources, plan.source_object_audio_indices)
    bad = bad_audio_indices(indices, source_channels)
    if not bad:
        return plan.bed_sources, plan.source_object_audio_indices
    raise ValueError(f"source audio indices outside CAF channel count: {bad[:8]}")


def output_channel_count(plan: Plan) -> int:
    return len(plan.bed_labels) + len(plan.source_object_ids)


def can_reuse_audio(
    plan: Plan,
    layout: dict,
    bed_sources: list[list[int]],
    source_object_audio_indices: list[int],
) -> bool:
    indices = flatten_audio_indices(bed_sources, source_object_audio_indices)
    channels = output_channel_count(plan)
    return (
        channels == layout["channels"]
        and layout["bytes_per_packet"] == channels * 3
        and indices == list(range(layout["channels"]))
    )


def reuse_audio_file(source: Path, dest: Path) -> str:
    if source.resolve() == dest.resolve():
        return "reused-source"
    tmp = dest.with_suffix(dest.suffix + ".tmp")
    tmp.unlink(missing_ok=True)
    try:
        os.link(source, tmp)
        method = "reused-hardlink"
    except OSError:
        shutil.copy2(source, tmp)
        method = "reused-copy"
    os.replace(tmp, dest)
    return method


def write_audio(source: Path, dest: Path, plan: Plan, block_frames: int = 65536) -> tuple[int, str]:
    layout = read_caf_layout(source)
    bed_sources, source_object_audio_indices = select_audio_sources(plan, layout["channels"])
    frames = layout["data_size"] // layout["bytes_per_packet"]
    if can_reuse_audio(plan, layout, bed_sources, source_object_audio_indices):
        return frames, reuse_audio_file(source, dest)

    output_channels = output_channel_count(plan)
    output_bpp = output_channels * 3
    desc = bytearray(layout["desc"])
    struct.pack_into(">IIIII", desc, 12, layout["flags"], output_bpp, 1, output_channels, layout["bits"])

    tmp = dest.with_suffix(dest.suffix + ".tmp")
    with source.open("rb") as src, tmp.open("wb") as out:
        out.write(b"caff")
        out.write(layout["version_flags"])
        out.write(b"desc")
        out.write(struct.pack(">q", len(desc)))
        out.write(desc)
        if layout["free"]:
            out.write(b"free")
            out.write(struct.pack(">q", len(layout["free"])))
            out.write(layout["free"])
        out.write(b"data")
        out.write(struct.pack(">q", 4 + frames * output_bpp))
        out.write(layout["edit_count"])
        src.seek(layout["data_start"])
        remaining = frames
        while remaining:
            take = min(block_frames, remaining)
            block = src.read(take * layout["bytes_per_packet"])
            if len(block) != take * layout["bytes_per_packet"]:
                raise EOFError("unexpected EOF while reading audio")
            samples = int24le_to_i32(block, layout["channels"])
            parts = []
            for group in bed_sources:
                parts.append(samples[:, group].sum(axis=1))
            for idx in source_object_audio_indices:
                parts.append(samples[:, idx])
            output = np.stack(parts, axis=1)
            out.write(i32_to_int24le(output))
            remaining -= take
    os.replace(tmp, dest)
    return frames, "rewritten"


def yaml_scalar(value) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, list):
        return "[" + ", ".join(yaml_scalar(v) for v in value) + "]"
    return str(value)


def metadata_bool(value, field: str) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)) and value in (0, 1):
        return bool(value)
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in ("0", "false"):
            return False
        if lowered in ("1", "true"):
            return True
    raise ValueError(f"metadata boolean field {field} must be 0/1 or false/true, got {value!r}")


def require_field(data: dict, field: str, context: str):
    if field not in data:
        raise ValueError(f"missing required {context} field: {field}")
    return data[field]


def presentation_optional_fields(presentation: dict):
    for key in PRESENTATION_OPTIONAL_SOURCE_FIELDS:
        if key in presentation:
            yield key, presentation[key]
    for key in PRESENTATION_OPTIONAL_PASSTHROUGH_FIELDS:
        if key in presentation:
            yield key, presentation[key]
    if "dialnorm" in presentation:
        yield "dialnorm", presentation["dialnorm"]
    elif "dialNorm" in presentation:
        yield "dialnorm", presentation["dialNorm"]


def emit_event(lines: list[str], event: dict) -> None:
    first = True
    for key, value in event.items():
        if first:
            lines.append(f"  - {key}: {yaml_scalar(value)}")
            first = False
        else:
            lines.append(f"    {key}: {yaml_scalar(value)}")


def write_atmos(dest: Path, presentation: dict, plan: Plan) -> None:
    fixed_values = dict(PRESENTATION_REQUIRED_FIXED_VALUES)
    lines = [f"{key}: {yaml_scalar(value)}" for key, value in ATMOS_TOP_LEVEL_VALUES]
    lines.append("presentations:")
    lines.append(f"  - type: {yaml_scalar(fixed_values['type'])}")
    source_values = {
        key: require_field(presentation, key, "presentation") for key in PRESENTATION_REQUIRED_SOURCE_FIELDS
    }
    lines.append("    simplified: false")
    output_values = {
        "metadata": f"{dest.name}.metadata",
        "audio": f"{dest.name}.audio",
    }
    for key in PRESENTATION_REQUIRED_OUTPUT_FIELDS:
        lines.append(f"    {key}: {output_values[key]}")
    lines.append(f"    offset: {yaml_scalar(source_values['offset'])}")
    for key, value in presentation_optional_fields(presentation):
        lines.append(f"    {key}: {yaml_scalar(value)}")
    for key, value in PRESENTATION_REQUIRED_FIXED_VALUES:
        if key != "type":
            lines.append(f"    {key}: {yaml_scalar(value)}")
    lines.append("    channels:")
    for idx, label in enumerate(plan.bed_labels):
        lines.extend([f"      - name: BED {label}", f"        bed: {label}", f"        ID: {idx}"])
    for name_idx, _ in enumerate(plan.source_objects, start=1):
        object_id = OUTPUT_OBJECT_ID_BASE + name_idx - 1
        lines.extend([f"      - name: OBJ {name_idx}", f"        ID: {object_id}"])
    dest.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_metadata(source: Path, dest: Path, plan: Plan, emit_size3d: bool = False) -> None:
    data = yaml.safe_load(source.read_text(encoding="utf-8"))
    lines = [f"{key}: {yaml_scalar(value)}" for key, value in METADATA_TOP_LEVEL_VALUES]
    event_lines: list[str] = []

    source_id_to_object_id = {
        source_id: idx for idx, source_id in enumerate(plan.source_object_ids)
    }
    current_source_id: int | None = None
    for event in data.get("events", []):
        old_id = event.get("ID", event.get("objectID"))
        if old_id is not None:
            current_source_id = int(old_id)
        if current_source_id is None:
            continue
        source_id = current_source_id
        if source_id not in source_id_to_object_id:
            continue
        mapped = dict(event)
        ordered = {"objectID": source_id_to_object_id[source_id]}
        for key in METADATA_EVENT_OPTIONAL_SOURCE_FIELDS:
            if key == "objectID":
                continue
            if key == "size":
                if "size" in mapped:
                    ordered[key] = mapped["size"]
            elif key == "size3D":
                if "size" not in mapped:
                    continue
                if "size3D" in mapped:
                    size3d = metadata_bool(mapped[key], key)
                else:
                    size3d = True
                if emit_size3d:
                    ordered[key] = size3d
            elif key == "decorr":
                if "size" in mapped and "decorr" in mapped:
                    ordered[key] = metadata_bool(mapped[key], key)
            elif key in METADATA_BOOLEAN_FIELDS and key in mapped:
                ordered[key] = metadata_bool(mapped[key], key)
            elif key in mapped:
                ordered[key] = mapped[key]
        emit_event(event_lines, ordered)

    if event_lines:
        lines.append("events:")
        lines.extend(event_lines)
    else:
        lines.append("events: []")
    dest.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Convert a modern DAMF set into the older flat DAMF form accepted by DMP 2.0."
    )
    parser.add_argument("--source-dir", type=Path, required=True)
    parser.add_argument("--dest-dir", type=Path, required=True)
    parser.add_argument("--name", required=True)
    parser.add_argument(
        "--emit-size3d",
        action="store_true",
        help="Write size3D metadata fields using the legacy compatibility mapping.",
    )
    args = parser.parse_args()

    source_atmos = args.source_dir / f"{args.name}.atmos"
    source_audio = args.source_dir / f"{args.name}.atmos.audio"
    source_metadata = args.source_dir / f"{args.name}.atmos.metadata"
    dest_atmos = args.dest_dir / f"{args.name}.atmos"
    dest_audio = args.dest_dir / f"{args.name}.atmos.audio"
    dest_metadata = args.dest_dir / f"{args.name}.atmos.metadata"
    args.dest_dir.mkdir(parents=True, exist_ok=True)

    presentation, plan = build_plan(source_atmos)
    frames, audio_action = write_audio(source_audio, dest_audio, plan)
    write_atmos(dest_atmos, presentation, plan)
    write_metadata(source_metadata, dest_metadata, plan, emit_size3d=args.emit_size3d)

    print(f"bed_channels={len(plan.bed_labels)} {','.join(plan.bed_labels)}")
    print(f"source_objects={len(plan.source_objects)}")
    print(f"output_channels={output_channel_count(plan)}")
    print(f"frames={frames}")
    print(f"audio={audio_action}")
    print(f"wrote={dest_atmos}")
    print(f"wrote={dest_audio}")
    print(f"wrote={dest_metadata}")


if __name__ == "__main__":
    main()
