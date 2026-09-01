# DAMF Legacy Rewriter

Language: English | [简体中文](README_zh-CN.md)

This project rewrites a modern Dolby Atmos Master File triplet into the older flat DAMF profile that has been empirically accepted by Dolby Media Producer Suite (DMPS) v2.0 build `2976134`.

The converter is:

- `damf_legacy_rewriter.py`

Supporting documentation is split by purpose:

- `README.md`: English usage, scope, and the practical profile summary
- `README_zh-CN.md`: Simplified Chinese usage, scope, and the practical profile summary
- `CONVERSION_RULES.md`: authoritative rule record and current research findings
- `BEHAVIOR_EXAMPLES.md`: CLI output, accepted shapes, and rejected shapes

The demo screenshots are retained only as import-behavior evidence. Generated DAMFs, probe outputs, installers, sample masters, and temporary validation scripts are not part of the final project policy.

## Project Structure

```text
damf-legacy-rewriter/
|-- damf_legacy_rewriter.py   Converter CLI and DAMF/audio rewrite logic.
|-- README.md                 English documentation.
|-- README_zh-CN.md           Simplified Chinese documentation.
|-- CONVERSION_RULES.md       Rule record and current research findings.
|-- BEHAVIOR_EXAMPLES.md      CLI examples plus accepted/rejected shapes.
|-- LICENSE
|-- .gitignore                Ignores local work folders, generated outputs, installers, and cache files.
|-- demo_screenshots/         DMPS v2.0 import-behavior evidence.
`-- encoder_manuals/          Dolby Media Producer Suite reference PDFs for v2.0 and v2.5.
```

`codex_work_folder/`, `encoder_installers/`, `encoder_outputs/`, `encoder_projects/`, `example_masters/`, `example_outputs/`, `DAMF Legacy Rewriter.code-workspace`, and `__pycache__/` are intentionally ignored local workspace or generated-output paths. They are useful during research and validation but are not part of the tracked release documentation set.

## Demo Screenshots

These screenshots show manual DMPS v2.0 import behavior for an original modern DAMF v0.5.1 input and for a rewritten DAMF v0.3 output.

### Original DAMF v0.5.1 Import Failure

![Original DAMF v0.5.1 import selection](demo_screenshots/import_original_damf_v0.5.1/import_original_damf_v0.5.1.png)

![Original DAMF v0.5.1 import error](demo_screenshots/import_original_damf_v0.5.1/error_invalid_damf_selected.png)

### Rewritten DAMF v0.3 Import

![Rewritten DAMF v0.3 Dolby Atmos file details](demo_screenshots/import_rewritten_damf_v0.3/dolby_atmos_file_details.png)

![Rewritten DAMF v0.3 audio core channel configuration](demo_screenshots/import_rewritten_damf_v0.3/audio_core_channel_config.png)

![Rewritten DAMF v0.3 preprocessing bed configuration](demo_screenshots/import_rewritten_damf_v0.3/preprocessing_bed_config.png)

![Rewritten DAMF v0.3 encoder settings data rate](demo_screenshots/import_rewritten_damf_v0.3/encoder_settings_data_rate.png)

## Scope

The target profile is empirical, not an official Dolby DAMF specification.

DMPS v2.0 rejects many modern v0.5.x DAMF files directly. This tool rewrites known-compatible inputs into a v0.3-style DAMF that DMPS v2.0 can import for legacy Dolby Digital Plus with Dolby Atmos workflows.

Current validation status:

- 7.1.2 bed input has stable import and bed-only encode success.
- 7.1 bed input has stable import and bed-only encode success.
- 2.0 bed input has stable import and bed-only encode success.
- 5.1 side and 5.1 back bed inputs are supported by the converter but still need final encode testing.
- DMPS v2.0 UI shows `Lw/Rw` labels, but 9.1 bed input has not been tested and is not currently supported by the converter.

## Requirements

- Python 3
- `numpy`
- `PyYAML`

Input files must be a matching DAMF triplet:

- `<name>.atmos`
- `<name>.atmos.audio`
- `<name>.atmos.metadata`

The input CAF must be 24-bit little-endian LPCM.

## Usage

```powershell
python damf_legacy_rewriter.py --source-dir .\input --dest-dir .\output --name movie
```

The command reads:

```text
.\input\movie.atmos
.\input\movie.atmos.audio
.\input\movie.atmos.metadata
```

and writes:

```text
.\output\movie.atmos
.\output\movie.atmos.audio
.\output\movie.atmos.metadata
```

By default, metadata output omits `size3D`. The optional flag is still available:

```powershell
python damf_legacy_rewriter.py --source-dir .\input --dest-dir .\output --name movie --emit-size3d
```

Use `--emit-size3d` cautiously. In current DMPS v2.0 testing, enabling `size3D` can break object positioning, and the cause is not yet isolated.

There is no skip-audio mode. The converter always validates the CAF, then either reuses it when the required output channel order is byte-for-byte identical or rewrites it when merging, dropping, reordering, or a CAF header change is required.

## Supported Input Beds

The current support boundary is exact: every source bed instance must be one of these layouts, and the source may contain any combination of these supported bed instances.

- 2.0: `L R`
- 5.1 side: `L R C LFE Lss Rss`
- 5.1 back: `L R C LFE Lrs Rrs`
- 7.1: `L R C LFE Lss Rss Lrs Rrs`
- 7.1.2: `L R C LFE Lss Rss Lrs Rrs Lts Rts`

Supported aliases:

```text
Ls  -> Lss
Rs  -> Rss
Lb  -> Lrs
Rb  -> Rrs
Ltm -> Lts
Rtm -> Rts
```

Any other bed label set is rejected. There is no 9.1 special handling and no static-object fallback for unsupported bed channels.

## ID Model

The channel IDs inside each input bed must form one contiguous numeric range. A bed may start at any unused ID, and no unused slots are reserved for layouts narrower than 7.1.2.

For example, both a 5.1 side bed and a 5.1 back bed use six contiguous input IDs. The channel labels, rather than gaps in the IDs, decide whether IDs 4 and 5 feed the side or rear output channels.

Input bed and object IDs may touch, may have gaps between them, and may be interleaved across the full source ID range. All source channel and object IDs must still be unique. Source CAF channels are matched to the declared bed/object IDs in ascending ID order, with undeclared gaps omitted.

Output IDs remain independent of this input mapping: output bed channels use canonical 7.1.2 slot IDs and are not compacted, while output object channel IDs start at `10` and increase contiguously.

## Output Profile

`.atmos`:

- top-level `version: 0.3`
- presentation `type: home`
- presentation `simplified: false`
- `metadata` and `audio` point to the output filenames
- `offset` is preserved when present and defaults to `0` when missing
- `ffoa`, `surroundTrim_7_1`, `surroundTrim_5_1`, and `fps` are preserved only if present
- `scBedConfiguration`, `scNumberOfElements`, `roomWidth`, `roomLength`, `roomHeight`, and `screenSizeRatio` are preserved only if present
- `dialnorm` and `dialNorm` are preserved only if present and emitted as `dialnorm`
- `creationTool: DAMF Legacy Rewriter for DMPS v2.0 by LumaVista`
- `creationToolVersion: Only Tested DAMF v0.5.0 & v0.5.1 to v0.3`
- channel entries use `ID`, not `objectID`

Discarded presentation fields include `salt`, `audioCipherIV`, and `metadataCipherIV`.

`.atmos.metadata`:

- top-level `sampleRate: 48000`
- only source object events are retained
- bed events are filtered out
- object event shape follows the input event stream, including omitted `objectID` and omitted `samplePos` inheritance behavior
- explicit event IDs are emitted as `objectID` and mapped to the regenerated output object IDs
- `decorr` is preserved when present after boolean normalization
- `importance`, `dialog`, and `music` are preserved when present
- `size3D` is omitted by default

If there are no object events, the metadata output is:

```yaml
events: []
```

## Audio Mapping

Output CAF channel order is:

```text
output bed channels, then output objects
```

Input CAF channel order is derived from all declared input bed and object IDs in ascending order. This supports objects between bed ID ranges as well as gaps between a bed and its neighboring objects.

Multiple input beds contributing the same output label are summed directly. The converter does not apply gain management or downmix rules. If summed samples exceed the 24-bit integer range, they are clipped to the valid range instead of failing. This intentionally leaves a production-quality risk for overloaded sources.

When the selected output order exactly matches the source CAF order, the converter reuses the input CAF through a hard link and falls back to copying if linking is unavailable.
