# Key Prompts And Decisions

This file preserves the working conclusions from the Dolby Media Producer Suite (DMPS) v2.0 DAMF compatibility research. It is the archival memory for the project after the original chat is deleted.

## Goal

DMPS v2.5 can import modern DAMF masters, but DMPS v2.0 build `2976134` rejects many modern v0.5.x DAMF files. The goal is to rewrite a modern DAMF triplet with minimal semantic change so DMPS v2.0 can import it for legacy Dolby Digital Plus with Dolby Atmos workflows.

The final converter is `convert_damf_to_dmp20.py`.

## Final Output Profile

The accepted target profile is empirical, not an official Dolby DAMF specification.

`.atmos`:

- top-level `version: 0.3`
- presentation `type: home`
- presentation `simplified: false`
- `metadata` and `audio` point to the output filenames
- `offset` preserved from source
- `ffoa`, `surroundTrim_7_1`, `surroundTrim_5_1`, `fps` preserved only if present
- `scBedConfiguration`, `scNumberOfElements`, `roomWidth`, `roomLength`, `roomHeight`, `screenSizeRatio` preserved only if present
- `dialnorm`/`dialNorm` preserved only if present and emitted as `dialnorm`
- `creationTool: DAMF Legacy Rewriter for DMPS v2.0 by LumaVista`
- `creationToolVersion: Only Tested DAMF v0.5.0 & v0.5.1 to v0.3`
- bed channel names are `BED <label>`
- object channel names are `OBJ 1`, `OBJ 2`, and so on
- channel IDs are global and contiguous, bed first then objects
- `.atmos` channel entries use `ID`, not `objectID`

Discarded `.atmos` fields:

- `salt`
- `audioCipherIV`
- `metadataCipherIV`

`.atmos.metadata`:

- top-level `sampleRate: 48000`
- only object events retained
- bed events filtered out
- output event IDs use zero-based object-only `objectID`
- event fields may be omitted
- source events without `ID` or `objectID` inherit the most recent explicit source event ID before object filtering
- object event fields are inherited only when present, except legacy `size3D` handling tied to `size`

Metadata event field order:

```text
objectID, samplePos, active, pos, snap, elevation, zones,
size, size3D, decorr, importance, gain, rampLength,
dialog, music, screenFactor, depthFactor
```

`size3D` is included in that position only when `--emit-size3d` is passed.

Boolean normalization:

- fields: `active`, `snap`, `elevation`, `size3D`, `decorr`
- input `0` or `false` writes `false`
- input `1` or `true` writes `true`
- other boolean-like values are errors

Size-related rules:

- `size` is inherited when present
- `size3D` is normalized/calculated with the same legacy compatibility rules, but is not emitted by default
- with `--emit-size3d`, if `size` and `size3D` are both present, inherit normalized `size3D`
- with `--emit-size3d`, if `size` is present but `size3D` is absent, write `size3D: true`
- if `size` is absent, do not write `size3D`, even with `--emit-size3d`
- `decorr` is inherited only when both `size` and `decorr` exist

`importance`, `dialog`, and `music` are preserved when present.

## Supported Bed Layouts

Accepted source bed layouts:

- 2.0: `L R`
- 5.1 side: `L R C LFE Lss Rss`
- 5.1 back: `L R C LFE Lrs Rrs`
- 7.1: `L R C LFE Lss Rss Lrs Rrs`
- 7.1.2: `L R C LFE Lss Rss Lrs Rrs Lts Rts`

Accepted aliases:

```text
Ls  -> Lss
Rs  -> Rss
Lb  -> Lrs
Rb  -> Rrs
Ltm -> Lts
Rtm -> Rts
```

Unsupported bed label sets are rejected directly. There is no 9.1-specific conversion path.

## Source ID Model

Modern DAMF authoring/conversion tools reserve 10 source IDs per input bed. The converter enforces this model because it matched the working DMPS v2.0 import results.

Canonical 7.1.2 slot positions inside each 10-ID block:

```text
L=0, R=1, C=2, LFE=3, Lss=4, Rss=5, Lrs=6, Rrs=7, Lts=8, Rts=9
```

For bed index `N`, add `10 * N`.

Examples:

- first 2.0 bed: `L=0`, `R=1`
- first 5.1 side bed: `L=0`, `R=1`, `C=2`, `LFE=3`, `Lss=4`, `Rss=5`
- first 5.1 back bed: `L=0`, `R=1`, `C=2`, `LFE=3`, `Lrs=6`, `Rrs=7`
- first 7.1.2 bed: IDs `0..9`
- second bed begins at ID `10`

Source object IDs must be at least `10 * bed_count`. Source object IDs may be sparse, but all source channel/object IDs must be unique.

CAF audio does not contain empty tracks for unused bed ID slots. It is packed in actual source bed channel order followed by source object list order.

## Audio Rules

Output CAF channel order is output bed channels followed by output objects.

Multiple beds contributing the same output label are summed directly. The converter does not apply gain management or downmix rules. Production material must avoid overload. The converter raises an error if summed samples exceed 24-bit integer range.

The converter preserves `offset` and does not time-shift CAF audio.

## Empirical DMPS v2.0 Findings

- DMPS v2.0 rejects modern DAMF v0.5.x directly, but accepts the current v0.3 target profile in import tests.
- `offset` can be nonzero and should be preserved.
- `ffoa` should be preserved only when present; do not synthesize it.
- `fps` can be present or absent.
- `surroundTrim_5_1` and `surroundTrim_7_1` are safe to preserve when present.
- `scNumberOfElements`, `scBedConfiguration`, `dialnorm`/`dialNorm`, room dimensions, and screen size are preserved when present in the source presentation.
- `.atmos` channel entries require `ID`; using `objectID` in `.atmos` can crash DMPS v2.0.
- Removing object `name` and `ID` from `.atmos` prevents import.
- DMPS v2.0 import accepts stereo bed input.
- DMPS v2.0 import accepts 5.1 side and 5.1 back bed input.
- DMPS v2.0 import accepts direct 7.1.2 bed input, including bed-only test files.
- Bed-only output with `events: []` imports, but encoding behavior still needs verification.

## Retired Decisions

These were explored and intentionally removed from the final project:

- static-object fallback for `Lts/Rts`
- special 9.1 handling or `Lw/Rw` static objects
- `--skip-audio`
- `--bed-mode`
- experimental stereo flags
- generated probe matrices in the final repository
- static-analysis helper scripts in the final repository
- DMPS binary/parser analysis artifacts in the final repository

## Known Risks

- Import success does not prove legacy DD+ Atmos encoding success.
- Bed-only cases import, but encode behavior is not yet verified.
- 5.1 side and 5.1 back import, but their final DD+ Atmos encode/decode behavior remains unverified.
- `size`, `size3D`, and `decorr` handling is based on the best observed compatibility profile; final object-size/decorrelation semantics require encode/decode verification.
- `importance`, `dialog`, and `music` are preserved, but their actual DD+ Atmos encoding effects remain unverified.
- Existing DAMF v0.5.0/v0.5.1 samples may contain `active: false` events with `pos: [-2001, 2001, 0]`. The converter preserves these when present but does not synthesize sentinel/off-field events.
- Repeated `.atmos.metadata` `objectID` values are normal timeline events for the same object, not duplicate object-definition errors.
- Multiple beds are summed directly. If source beds are not authored with sufficient headroom, conversion can fail or produce clipped-intent material.
- This workflow is an empirical DMPS v2.0 compatibility profile, not a substitute for Dolby documentation or licensed encode validation.

## Minimal Project Policy

Keep only:

- `convert_damf_to_dmp20.py`
- `README.md`
- `INTERACTION_SIMULATION.md`
- `KEY_PROMPTS.md`

Do not keep generated DAMFs, probe outputs, archived binaries, or temporary validation scripts in the final project directory.
