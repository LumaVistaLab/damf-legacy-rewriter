# Conversion Rules And Findings

This file is the authoritative rule record for the current DAMF Legacy Rewriter profile. It preserves the working conclusions behind `damf_legacy_rewriter.py`.

## Goal

Rewrite a modern DAMF triplet with minimal semantic change so Dolby Media Producer Suite (DMPS) v2.0 build `2976134` can import it for legacy Dolby Digital Plus with Dolby Atmos workflows.

The accepted target profile is empirical. It is not an official Dolby DAMF specification.

## File Set

The maintained project surface is:

- `damf_legacy_rewriter.py`
- `README.md`
- `CONVERSION_RULES.md`
- `BEHAVIOR_EXAMPLES.md`
- `demo_screenshots/`

Generated DAMFs, probe outputs, archived experiments, static-analysis helpers, sample media, and temporary validation scripts should not be kept in the final working tree.

## Supported Bed Boundary

Current support is an if-and-only-if boundary: every input bed instance must be one of these layouts, and the input may contain any combination of these layouts.

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

Unsupported bed label sets are rejected directly. There is no 9.1-specific conversion path and no static-object fallback for unsupported bed channels. DMPS v2.0 UI exposes `Lw/Rw` labels, but 9.1 bed input has not been tested.

## Source ID Model

Every input bed instance must use a contiguous range of source IDs. The range may start at any unused ID. Input beds do not reserve ten IDs, and a narrower layout does not leave canonical 7.1.2 holes in its input range.

For example, both 5.1 layouts use six contiguous input IDs:

```text
5.1 side: L=0, R=1, C=2, LFE=3, Lss=4, Rss=5
5.1 back: L=0, R=1, C=2, LFE=3, Lrs=4, Rrs=5
```

The labels determine whether the final two 5.1 channels feed side or rear output slots. Canonical 7.1.2 positions apply only to regenerated output bed IDs.

Input bed and object ID ranges:

- may be adjacent or separated by undeclared gaps
- may be interleaved, such as a bed, then objects, then another bed
- must be globally unique across all bed channels and objects

Source CAF channels correspond to all declared bed and object IDs in ascending numeric order. Undeclared ID gaps do not consume CAF channels.

## Output `.atmos`

Top-level:

- `version: 0.3`

Presentation:

- `type: home`
- `simplified: false`
- `metadata`: output metadata filename
- `audio`: output audio filename
- `offset`: source value when present, otherwise `0`
- `ffoa`, `surroundTrim_7_1`, `surroundTrim_5_1`, `fps`: preserved only if present
- `scBedConfiguration`, `scNumberOfElements`, `roomWidth`, `roomLength`, `roomHeight`, `screenSizeRatio`: preserved only if present
- `dialnorm`/`dialNorm`: preserved only if present and emitted as `dialnorm`
- `creationTool: DAMF Legacy Rewriter for DMPS v2.0 by LumaVista`
- `creationToolVersion: Only Tested DAMF v0.5.0 & v0.5.1 to v0.3`

Discarded presentation fields:

- `salt`
- `audioCipherIV`
- `metadataCipherIV`

Channel entries:

- bed channels are named `BED <label>` and use `bed: <label>`
- bed channel IDs use canonical 7.1.2 slot IDs, not compact output order
- object channels are named `OBJ 1`, `OBJ 2`, and so on
- object channel IDs start at `10` and increase contiguously
- `.atmos` channel entries use `ID`, not `objectID`

Using `objectID` in `.atmos` channel entries can crash DMPS v2.0. Removing object `name` and `ID` from `.atmos` prevents import.

## Output `.atmos.metadata`

Top-level:

- `sampleRate: 48000`

Event rules:

- only source object events are retained
- bed events are filtered out
- source events without `ID` or `objectID` inherit the most recent explicit source event ID for filtering and object mapping
- source events without `samplePos` keep the omission so the metadata timeline's inheritance behavior remains aligned with the input
- omitted `objectID` and omitted `samplePos` are not synthesized in output
- explicit output event IDs are emitted as `objectID` and mapped to the regenerated output object IDs
- normal event fields are emitted only when present in the source event
- if there are no object events, output is `events: []`

Event fields are emitted in this order when applicable:

```text
objectID, samplePos, active, pos, snap, elevation, zones,
size, size3D, decorr, importance, gain, rampLength,
dialog, music, screenFactor, depthFactor
```

Boolean normalization:

- fields: `active`, `snap`, `elevation`, `size3D`, `decorr`
- input `0` or `false` writes `false`
- input `1` or `true` writes `true`
- other boolean-like values are errors

Size and object metadata:

- `size` is emitted when present
- `size3D` is omitted by default
- with `--emit-size3d`, if `size` and `size3D` are both present, emit normalized `size3D`
- with `--emit-size3d`, if `size` is present but `size3D` is absent, write `size3D: true`
- if `size` is absent, do not write `size3D`, even with `--emit-size3d`
- `decorr` is preserved whenever present after boolean normalization
- `importance`, `dialog`, and `music` are preserved when present

Known `size3D` issue: enabling `size3D` currently causes object positioning to fail in DMPS v2.0 testing. The cause is not yet clear.

## Audio Rules

Output CAF channel order is:

```text
output bed channels, then output objects
```

Source CAF indices are first resolved by sorting all declared input bed and object IDs. The resolved channels are then merged and reordered into the output layout.

Multiple beds contributing the same output label are summed directly. The converter does not apply gain management or downmix rules.

If mixed samples exceed the 24-bit integer range, the converter clips to the valid 24-bit range instead of failing. This is intentionally treated as a production-quality risk: overloaded source beds can create poor or distorted output.

When the required output channel order is exactly the source CAF order, the converter reuses the source CAF through a hard link and falls back to copying if linking is unavailable. Audio is rewritten only when the output requires channel merging, channel dropping, channel reordering, or a CAF header change.

The converter preserves `offset` when present and does not time-shift CAF audio.

## Empirical Findings

- DMPS v2.0 rejects many modern DAMF v0.5.x files directly.
- DMPS v2.0 accepts the current v0.3 target profile in import tests.
- `offset` can be nonzero and should be preserved; when missing, output `offset: 0`.
- `ffoa` should be preserved only when present; do not synthesize it.
- `fps` can be present or absent.
- `surroundTrim_5_1` and `surroundTrim_7_1` are safe to preserve when present.
- `scNumberOfElements`, `scBedConfiguration`, `dialnorm`/`dialNorm`, room dimensions, and screen size are preserved when present in the source presentation.
- DMPS v2.0 import accepts 2.0, 5.1 side, 5.1 back, 7.1, and 7.1.2 bed input after rewriting.
- 7.1.2, 7.1, and 2.0 bed input have stable bed-only encode success.
- 5.1 side and 5.1 back bed input still need final encode testing.
- Bed-only output with `events: []` can import and encode for the tested stable bed layouts.
- Existing DAMF v0.5.0/v0.5.1 samples may contain `active: false` events with `pos: [-2001, 2001, 0]`. The converter preserves these when present but does not synthesize sentinel/off-field events.
- Repeated `.atmos.metadata` `objectID` values are normal timeline events for the same object, not duplicate object-definition errors.

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

## Current Risks

- This workflow is an empirical DMPS v2.0 compatibility profile, not a substitute for Dolby documentation or licensed validation.
- 5.1 side and 5.1 back encode/decode behavior remains untested.
- 9.1 bed input remains untested even though DMPS v2.0 UI exposes `Lw/Rw`.
- `size3D` output breaks object positioning in current testing.
- `decorr`, `importance`, `dialog`, and `music` are preserved and have not shown problems so far, but broader encode/decode validation is still useful.
- Multiple beds are summed directly. If source beds are not authored with sufficient headroom, output can clip.
