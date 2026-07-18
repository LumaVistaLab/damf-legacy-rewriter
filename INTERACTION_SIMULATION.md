# Interaction Simulation

This file documents expected user-facing behavior for `convert_damf_to_dmp20.py`. It is not a generated test matrix and does not contain real DAMF payloads.

Use it to review CLI messages, accepted input shapes, rejected input shapes, and output ID mapping without regenerating probe files.

## Command Shape

```powershell
python convert_damf_to_dmp20.py --source-dir .\input --dest-dir .\output --name movie
```

Successful output has this shape:

```text
bed_channels=<count> <comma-separated output bed labels>
source_objects=<count>
output_channels=<bed count + object count>
frames=<CAF frame count>
wrote=<dest>\movie.atmos
wrote=<dest>\movie.atmos.audio
wrote=<dest>\movie.atmos.metadata
```

The exact `frames` value depends on the input CAF.

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

Source object IDs start after the reserved 10-ID bed block, even though the bed has only two audio channels.

```yaml
bedInstances:
  - channels:
      - channel: L
        ID: 0
      - channel: R
        ID: 1
objects:
  - ID: 10
  - ID: 12
```

Expected console:

```text
bed_channels=2 L,R
source_objects=2
output_channels=4
frames=<input frames>
wrote=.\output\movie.atmos
wrote=.\output\movie.atmos.audio
wrote=.\output\movie.atmos.metadata
```

Output `.atmos` object IDs continue after the bed:

```yaml
channels:
  - name: BED L
    bed: L
    ID: 0
  - name: BED R
    bed: R
    ID: 1
  - name: OBJ 1
    ID: 2
  - name: OBJ 2
    ID: 3
```

Output `.atmos.metadata` object IDs start at zero:

```yaml
events:
  - objectID: 0
    samplePos: 0
    active: true
    pos: [0.5, 0.5, 0]
  - objectID: 1
    samplePos: 0
    active: true
    pos: [0.5, 0.5, 0]
```

### 5.1 Side Bed

Canonical source IDs:

```text
L=0, R=1, C=2, LFE=3, Lss=4, Rss=5
```

Aliases `Ls/Rs` are accepted and normalize to `Lss/Rss`.

Expected output labels:

```text
bed_channels=6 L,R,C,LFE,Lss,Rss
```

### 5.1 Back Bed

Canonical source IDs:

```text
L=0, R=1, C=2, LFE=3, Lrs=6, Rrs=7
```

Aliases `Lb/Rb` are accepted and normalize to `Lrs/Rrs`.

Expected output labels:

```text
bed_channels=6 L,R,C,LFE,Lrs,Rrs
```

Important: `Lrs/Rrs` still use reserved 7.1.2 slots `6/7`. Packed `4/5` IDs are rejected even though the CAF audio has only six bed channels.

### 7.1 Bed

Canonical source IDs:

```text
L=0, R=1, C=2, LFE=3, Lss=4, Rss=5, Lrs=6, Rrs=7
```

Expected output labels:

```text
bed_channels=8 L,R,C,LFE,Lss,Rss,Lrs,Rrs
```

### 7.1.2 Bed

Canonical source IDs:

```text
L=0, R=1, C=2, LFE=3, Lss=4, Rss=5, Lrs=6, Rrs=7, Lts=8, Rts=9
```

Aliases `Ltm/Rtm` are accepted and normalize to `Lts/Rts`.

Expected output labels:

```text
bed_channels=10 L,R,C,LFE,Lss,Rss,Lrs,Rrs,Lts,Rts
```

The converter keeps `Lts/Rts` as direct bed channels. It does not convert them into static objects.

### Multiple Beds

Each input bed reserves a 10-ID block. The second bed starts at ID 10, the third at ID 20, and so on.

Example: two 5.1 back beds:

```text
bed 0: L=0, R=1, C=2, LFE=3, Lrs=6, Rrs=7
bed 1: L=10, R=11, C=12, LFE=13, Lrs=16, Rrs=17
first object ID: 20
```

CAF audio remains packed:

```text
bed 0 listed channels, bed 1 listed channels, objects
```

There are no silent placeholder tracks for unused reserved slots.

When multiple beds contribute the same output label, their audio is summed directly.

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
  - objectID: 0
    samplePos: 0
    active: true
    pos: [0.5, 0.5, 0]
    size: 0.2
    size3D: true
```

### Source Event With Size, Size3D, And Decorr

Source:

```yaml
events:
  - objectID: 10
    samplePos: 0
    active: false
    pos: [-2001, 2001, 0]
    size: 0.2
    size3D: 0
    decorr: 1
```

Output:

```yaml
events:
  - objectID: 0
    samplePos: 0
    active: false
    pos: [-2001, 2001, 0]
    size: 0.2
    size3D: false
    decorr: true
```

The off-field coordinate `[-2001, 2001, 0]` is inherited only when present in source DAMF metadata. The converter does not synthesize sentinel positions.

### Source Event Without Size

Source:

```yaml
events:
  - objectID: 10
    samplePos: 0
    active: true
    pos: [0.5, 0.5, 0]
    decorr: true
```

Output:

```yaml
events:
  - objectID: 0
    samplePos: 0
    active: true
    pos: [0.5, 0.5, 0]
```

Without `size`, the converter does not write `size3D` or `decorr`.

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

### Duplicate Alias Collision

Example source includes both `Lss` and alias `Ls` in the same bed.

Expected failure:

```text
ValueError: duplicate channel 'Lss' in bedInstances[0]
```

### Packed 5.1 Back IDs

Invalid source:

```text
L=0, R=1, C=2, LFE=3, Lrs=4, Rrs=5
```

Expected failure:

```text
ValueError: bedInstances[0] channel Lrs ID 4 should be 6; input bed IDs must use canonical 7.1.2 slot positions inside reserved block 0..9; source objects still start after reserved block 0..9
```

### Object ID Inside Reserved Bed Block

One input bed reserves IDs `0..9`; object ID `8` is invalid.

Expected failure:

```text
ValueError: source object ID 8 is below first object ID 10; 1 input bed(s) reserve 10 ID slots
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
- `.atmos` uses global contiguous `ID`.
- `.atmos.metadata` uses object-only zero-based `objectID`.
- Direct 7.1.2 bed is supported.
- 9.1 is not specially converted.
- Probe DAMFs are not part of the final project.
