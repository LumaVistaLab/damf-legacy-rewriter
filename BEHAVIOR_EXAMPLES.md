# Behavior Examples

This file documents expected user-facing behavior for `damf_legacy_rewriter.py`. It is not a generated test matrix and does not contain real DAMF payloads.

Use it to review CLI messages, accepted input shapes, rejected input shapes, output ID mapping, and metadata inheritance behavior without regenerating probe files.

## Command Shape

```powershell
python damf_legacy_rewriter.py --source-dir .\input --dest-dir .\output --name movie
```

By default, output metadata omits `size3D`. Add `--emit-size3d` only when deliberately testing that field.

Successful output has this shape:

```text
bed_channels=<count> <comma-separated output bed labels>
source_objects=<count>
output_channels=<bed count + object count>
frames=<CAF frame count>
audio=<reused-hardlink|reused-copy|rewritten>
wrote=<dest>\movie.atmos
wrote=<dest>\movie.atmos.audio
wrote=<dest>\movie.atmos.metadata
```

`audio=reused-hardlink` means the output CAF is linked to the source CAF because the channel mapping is identical. `audio=reused-copy` is the same byte-for-byte reuse path when hard linking is unavailable. `audio=rewritten` means the CAF was regenerated because channel merging, dropping, reordering, or a header change was required.

## Presentation Defaults And Passthrough

If source `offset` is missing, the output writes:

```yaml
offset: 0
```

When present in the source presentation, the converter preserves:

```text
ffoa, surroundTrim_7_1, surroundTrim_5_1, fps,
scBedConfiguration, scNumberOfElements, dialnorm/dialNorm,
roomWidth, roomLength, roomHeight, screenSizeRatio
```

`dialnorm` and `dialNorm` are both emitted as `dialnorm`.

## Valid Cases

### 2.0 Bed, No Objects

Source bed:

```yaml
bedInstances:
  - channels:
      - channel: L
        ID: 0
      - channel: R
        ID: 1
objects: []
```

Expected console:

```text
bed_channels=2 L,R
source_objects=0
output_channels=2
frames=<input frames>
audio=<reused-hardlink|reused-copy>
wrote=.\output\movie.atmos
wrote=.\output\movie.atmos.audio
wrote=.\output\movie.atmos.metadata
```

Output `.atmos` channels:

```yaml
channels:
  - name: BED L
    bed: L
    ID: 0
  - name: BED R
    bed: R
    ID: 1
```

Output `.atmos.metadata`:

```yaml
sampleRate: 48000
events: []
```

### 2.0 Bed With Objects

Source objects may connect directly to the bed ID range or be separated by an undeclared gap.

```yaml
bedInstances:
  - channels:
      - channel: L
        ID: 0
      - channel: R
        ID: 1
objects:
  - ID: 2
  - ID: 12
```

Expected console:

```text
bed_channels=2 L,R
source_objects=2
output_channels=4
frames=<input frames>
audio=<reused-hardlink|reused-copy>
wrote=.\output\movie.atmos
wrote=.\output\movie.atmos.audio
wrote=.\output\movie.atmos.metadata
```

Output `.atmos` object IDs start at `10`, even when the output bed has fewer than 10 channels:

```yaml
channels:
  - name: BED L
    bed: L
    ID: 0
  - name: BED R
    bed: R
    ID: 1
  - name: OBJ 1
    ID: 10
  - name: OBJ 2
    ID: 11
```

Explicit output metadata object IDs match the regenerated `.atmos` object IDs:

```yaml
events:
  - objectID: 10
    samplePos: 0
    active: true
    pos: [0.5, 0.5, 0]
  - objectID: 11
    samplePos: 0
    active: true
    pos: [0.5, 0.5, 0]
```

### 5.1 Side Bed

Contiguous source IDs:

```text
L=0, R=1, C=2, LFE=3, Lss=4, Rss=5
```

Aliases `Ls/Rs` are accepted and normalize to `Lss/Rss`.

Expected output labels and bed IDs:

```text
L=0, R=1, C=2, LFE=3, Lss=4, Rss=5
```

### 5.1 Back Bed

Contiguous source IDs:

```text
L=0, R=1, C=2, LFE=3, Lrs=4, Rrs=5
```

Aliases `Lb/Rb` are accepted and normalize to `Lrs/Rrs`.

Expected output labels and bed IDs:

```text
L=0, R=1, C=2, LFE=3, Lrs=6, Rrs=7
```

The `Lrs/Rrs` labels route the final two input channels to output bed IDs `6/7`; no input ID gap is used to distinguish the back layout.

### 7.1 Bed

Contiguous source IDs and output bed IDs:

```text
L=0, R=1, C=2, LFE=3, Lss=4, Rss=5, Lrs=6, Rrs=7
```

Expected output labels:

```text
bed_channels=8 L,R,C,LFE,Lss,Rss,Lrs,Rrs
```

### 7.1.2 Bed

Contiguous source IDs and output bed IDs:

```text
L=0, R=1, C=2, LFE=3, Lss=4, Rss=5, Lrs=6, Rrs=7, Lts=8, Rts=9
```

Aliases `Ltm/Rtm` are accepted and normalize to `Lts/Rts`.

Expected output labels:

```text
bed_channels=10 L,R,C,LFE,Lss,Rss,Lrs,Rrs,Lts,Rts
```

The converter keeps `Lts/Rts` as bed channels. It does not convert them into static objects.

### Multiple Beds

Each bed uses its own contiguous ID range. Objects may sit between bed ranges, and undeclared gaps are allowed between any ranges.

Most explanatory example: one 5.1 side bed plus one 5.1 back bed.

```text
bed 0:    L=0,  R=1,  C=2,  LFE=3,  Lss=4, Rss=5
objects:  ID=6, ID=7
bed 1:    L=10, R=11, C=12, LFE=13, Lrs=14, Rrs=15
object:   ID=20
```

The selected output bed layout is 7.1 because the combined beds cover both side and rear surrounds:

```text
output bed labels: L,R,C,LFE,Lss,Rss,Lrs,Rrs
output bed IDs:    0,1,2,3,4,5,6,7
```

Source CAF channels follow all declared IDs in ascending order, skipping IDs 8, 9, and 16 through 19:

```text
bed 0 six channels, objects 6/7, bed 1 six channels, object 20
L,R,C,LFE,Lss,Rss,OBJ,OBJ,L,R,C,LFE,Lrs,Rrs,OBJ
```

There are no silent placeholder tracks for undeclared IDs.

The shared labels `L/R/C/LFE` are summed from both beds. `Lss/Rss` come only from bed 0. `Lrs/Rrs` come only from bed 1. If any summed channel exceeds 24-bit range, it is clipped.

## Metadata Event Examples

### Source Event With Size But No Size3D

Source:

```yaml
events:
  - objectID: 10
    samplePos: 0
    active: 1
    pos: [0.5, 0.5, 0]
    size: 0.2
```

Output:

```yaml
events:
  - objectID: 10
    samplePos: 0
    active: true
    pos: [0.5, 0.5, 0]
    size: 0.2
```

### Source Event With Size3D

Default output omits `size3D`:

```yaml
events:
  - objectID: 10
    samplePos: 0
    active: false
    pos: [-2001, 2001, 0]
    size: 0.2
    decorr: true
```

With `--emit-size3d`, the converter emits normalized `size3D`, but this mode currently breaks object positioning in DMPS v2.0 testing.

### Source Event With Decorr But No Size

Source:

```yaml
events:
  - objectID: 10
    samplePos: 0
    active: true
    pos: [0.5, 0.5, 0]
    decorr: 1
```

Output:

```yaml
events:
  - objectID: 10
    samplePos: 0
    active: true
    pos: [0.5, 0.5, 0]
    decorr: true
```

`decorr` is preserved whenever present after boolean normalization.

### ObjectID And SamplePos Inheritance

Source events that omit `ID` or `objectID` are evaluated with the most recent explicit source event ID, but the output event remains ID-less.

Source:

```yaml
events:
  - objectID: 10
    samplePos: 100
    pos: [0.1, 0.2, 0]
  - samplePos: 200
    pos: [0.2, 0.3, 0]
  - pos: [0.3, 0.4, 0]
```

Output:

```yaml
events:
  - objectID: 10
    samplePos: 100
    pos: [0.1, 0.2, 0]
  - samplePos: 200
    pos: [0.2, 0.3, 0]
  - pos: [0.3, 0.4, 0]
```

The inherited source ID is used only for object filtering and output object mapping. Omitted `samplePos` remains omitted so the metadata timeline keeps the same inheritance behavior as the source.

## Invalid Cases

### Unsupported Bed Layout

Example 9.1 source:

```text
L,R,C,LFE,Lss,Rss,Lrs,Rrs,Lw,Rw
```

Expected failure:

```text
ValueError: unsupported bed layout in bedInstances[0]: L,R,C,LFE,Lss,Rss,Lrs,Rrs,Lw,Rw; expected exactly 2.0, 5.1 side, 5.1 back, 7.1, or 7.1.2
```

DMPS v2.0 UI exposes `Lw/Rw`, but 9.1 input is not currently supported because it has not been tested.

### Duplicate Alias Collision

Example source includes both `Lss` and alias `Ls` in the same bed.

Expected failure:

```text
ValueError: duplicate channel 'Lss' in bedInstances[0]
```

### Noncontiguous Bed IDs

Invalid source:

```text
L=0, R=1, C=2, LFE=3, Lrs=6, Rrs=7
```

Expected failure:

```text
ValueError: bedInstances[0] channel IDs must be contiguous; got [0, 1, 2, 3, 6, 7], expected 0..5
```

### Duplicate Source ID

Expected failure:

```text
ValueError: duplicate source channel/object ID: <id>
```

### CAF Channel Count Too Small

Expected failure:

```text
ValueError: source audio indices outside CAF channel count: [<indices>]
```

## Final Profile Reminder

- `.atmos` version is fixed `0.3`.
- `.atmos` presentation `simplified` is fixed `false`.
- Missing presentation `offset` writes `offset: 0`.
- Supported bed inputs are exactly 7.1.2, 7.1, 5.1 side, 5.1 back, 2.0, and any combination of those layouts.
- Every input bed uses contiguous IDs; bed and object ranges may touch, have gaps, or interleave.
- Source CAF channels map to all declared input IDs in ascending order, skipping undeclared gaps.
- Output bed IDs use canonical 7.1.2 slot IDs.
- `.atmos` object IDs start at `10` and increase contiguously.
- `.atmos.metadata` keeps object-event inheritance shape for `objectID` and `samplePos`.
- `size3D` is omitted by default because enabling it currently breaks object positioning.
- 9.1 is visible in the DMPS v2.0 UI but is not currently converted.
- Probe DAMFs are not part of the final project.
