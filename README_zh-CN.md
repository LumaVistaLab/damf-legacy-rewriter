# DAMF Legacy Rewriter

语言：简体中文 | [English](README.md)

本项目将现代 Dolby Atmos Master File 三件套重写为较旧的扁平 DAMF 配置文件。该目标形态已通过经验测试，可被 Dolby Media Producer Suite（DMPS）v2.0 build `2976134` 接受。

转换器为：

- `damf_legacy_rewriter.py`

配套文档按用途拆分：

- `README.md`：英文用法、范围和实用配置摘要。
- `README_zh-CN.md`：简体中文用法、范围和实用配置摘要。
- `CONVERSION_RULES.md`：权威转换规则记录和当前研究结论。
- `BEHAVIOR_EXAMPLES.md`：CLI 输出、可接受形态和会被拒绝的形态。

演示截图仅作为导入行为证据保留。生成的 DAMF、探测输出、安装包、示例母版和临时验证脚本不属于最终项目策略的一部分。

## 项目结构

```text
damf-legacy-rewriter/
|-- damf_legacy_rewriter.py   转换器 CLI 与 DAMF/audio 重写逻辑。
|-- README.md                 英文文档。
|-- README_zh-CN.md           简体中文文档。
|-- CONVERSION_RULES.md       规则记录和当前研究结论。
|-- BEHAVIOR_EXAMPLES.md      CLI 示例以及可接受/拒绝形态。
|-- LICENSE
|-- .gitignore                排除本地工作目录、生成输出、安装包和缓存文件。
|-- demo_screenshots/         DMPS v2.0 导入行为证据。
`-- encoder_manuals/          Dolby Media Producer Suite v2.0 与 v2.5 参考 PDF。
```

`codex_work_folder/`、`encoder_installers/`、`encoder_outputs/`、`encoder_projects/`、`example_masters/`、`example_outputs/`、`DAMF Legacy Rewriter.code-workspace` 和 `__pycache__/` 是有意忽略的本地工作区或生成输出路径。它们可用于研究和验证，但不属于受跟踪的发布文档集。

## 演示截图

这些截图展示了 DMPS v2.0 对原始现代 DAMF v0.5.1 输入以及重写后 DAMF v0.3 输出的手动导入行为。

### 原始 DAMF v0.5.1 导入失败

![Original DAMF v0.5.1 import selection](demo_screenshots/import_original_damf_v0.5.1/import_original_damf_v0.5.1.png)

![Original DAMF v0.5.1 import error](demo_screenshots/import_original_damf_v0.5.1/error_invalid_damf_selected.png)

### 重写后 DAMF v0.3 导入

![Rewritten DAMF v0.3 Dolby Atmos file details](demo_screenshots/import_rewritten_damf_v0.3/dolby_atmos_file_details.png)

![Rewritten DAMF v0.3 audio core channel configuration](demo_screenshots/import_rewritten_damf_v0.3/audio_core_channel_config.png)

![Rewritten DAMF v0.3 preprocessing bed configuration](demo_screenshots/import_rewritten_damf_v0.3/preprocessing_bed_config.png)

![Rewritten DAMF v0.3 encoder settings data rate](demo_screenshots/import_rewritten_damf_v0.3/encoder_settings_data_rate.png)

## 范围

目标配置来自经验测试，而不是官方 Dolby DAMF 规格。

DMPS v2.0 会直接拒绝许多现代 v0.5.x DAMF 文件。本工具会把已知兼容的输入重写为 v0.3 风格 DAMF，使 DMPS v2.0 能够为旧版 Dolby Digital Plus with Dolby Atmos 工作流导入。

当前验证状态：

- 7.1.2 bed 输入已稳定导入，并通过 bed-only 编码。
- 7.1 bed 输入已稳定导入，并通过 bed-only 编码。
- 2.0 bed 输入已稳定导入，并通过 bed-only 编码。
- 5.1 side 与 5.1 back bed 输入已被转换器支持，但仍需要最终编码测试。
- DMPS v2.0 UI 会显示 `Lw/Rw` 标签，但 9.1 bed 输入尚未测试，当前转换器也不支持。

## 环境要求

- Python 3
- `numpy`
- `PyYAML`

输入文件必须是一组匹配的 DAMF 三件套：

- `<name>.atmos`
- `<name>.atmos.audio`
- `<name>.atmos.metadata`

输入 CAF 必须是 24-bit little-endian LPCM。

## 用法

```powershell
python damf_legacy_rewriter.py --source-dir .\input --dest-dir .\output --name movie
```

该命令读取：

```text
.\input\movie.atmos
.\input\movie.atmos.audio
.\input\movie.atmos.metadata
```

并写出：

```text
.\output\movie.atmos
.\output\movie.atmos.audio
.\output\movie.atmos.metadata
```

默认情况下，metadata 输出会省略 `size3D`。仍可使用可选参数：

```powershell
python damf_legacy_rewriter.py --source-dir .\input --dest-dir .\output --name movie --emit-size3d
```

请谨慎使用 `--emit-size3d`。在当前 DMPS v2.0 测试中，启用 `size3D` 可能破坏对象定位，原因尚未隔离确认。

本工具没有 skip-audio 模式。转换器始终会验证 CAF；随后如果所需输出声道顺序与源文件逐字节一致，则复用原文件，否则在需要合并、丢弃、重排或修改 CAF 头时重写音频。

## 支持的输入 Bed

当前支持边界是精确的：每个源 bed 实例都必须属于以下布局之一；源文件可包含这些受支持 bed 实例的任意组合。

- 2.0：`L R`
- 5.1 side：`L R C LFE Lss Rss`
- 5.1 back：`L R C LFE Lrs Rrs`
- 7.1：`L R C LFE Lss Rss Lrs Rrs`
- 7.1.2：`L R C LFE Lss Rss Lrs Rrs Lts Rts`

支持的别名：

```text
Ls  -> Lss
Rs  -> Rss
Lb  -> Lrs
Rb  -> Rrs
Ltm -> Lts
Rtm -> Rts
```

任何其他 bed 标签集合都会被拒绝。当前没有 9.1 特殊处理，也没有针对不支持 bed 声道的静态对象回退。

## ID 模型

每个输入 bed 预留 10 个源 ID 槽位。每个 bed 块内部的声道必须使用规范 7.1.2 槽位：

```text
L=0, R=1, C=2, LFE=3, Lss=4, Rss=5, Lrs=6, Rrs=7, Lts=8, Rts=9
```

对 bed 索引 `N`，加上 `10 * N`。

示例：

- 第一个 2.0 bed：`0,1`
- 第一个 5.1 side bed：`0,1,2,3,4,5`
- 第一个 5.1 back bed：`0,1,2,3,6,7`
- 第二个 5.1 back bed：`10,11,12,13,16,17`

输出 bed 声道 ID 也使用同一套规范 7.1.2 槽位 ID，不会压缩编号。

源对象 ID 必须大于等于 `10 * bed_count`。源对象 ID 可以稀疏，但所有源声道和对象 ID 必须唯一。输出对象声道 ID 从 `10` 开始并连续递增。

## 输出配置

`.atmos`：

- 顶层 `version: 0.3`
- presentation `type: home`
- presentation `simplified: false`
- `metadata` 和 `audio` 指向输出文件名
- 如存在则保留 `offset`，缺失时默认为 `0`
- 仅在存在时保留 `ffoa`、`surroundTrim_7_1`、`surroundTrim_5_1` 和 `fps`
- 仅在存在时保留 `scBedConfiguration`、`scNumberOfElements`、`roomWidth`、`roomLength`、`roomHeight` 和 `screenSizeRatio`
- 仅在存在时保留 `dialnorm` 和 `dialNorm`，并以 `dialnorm` 输出
- `creationTool: DAMF Legacy Rewriter for DMPS v2.0 by LumaVista`
- `creationToolVersion: Only Tested DAMF v0.5.0 & v0.5.1 to v0.3`
- channel 条目使用 `ID`，而不是 `objectID`

丢弃的 presentation 字段包括 `salt`、`audioCipherIV` 和 `metadataCipherIV`。

`.atmos.metadata`：

- 顶层 `sampleRate: 48000`
- 仅保留源对象事件
- bed 事件会被过滤
- 对象事件形态遵循输入事件流，包括省略 `objectID` 和省略 `samplePos` 时的继承行为
- 显式事件 ID 会作为 `objectID` 输出，并映射到重新生成的输出对象 ID
- 如存在则在布尔值规范化后保留 `decorr`
- 如存在则保留 `importance`、`dialog` 和 `music`
- 默认省略 `size3D`

如果没有对象事件，metadata 输出为：

```yaml
events: []
```

## 音频映射

输出 CAF 声道顺序为：

```text
output bed channels, then output objects
```

多个输入 bed 贡献到同一输出标签时，会直接求和。转换器不会应用增益管理或下混规则。如果求和后的采样超出 24-bit 整数范围，会被裁剪到有效范围，而不是失败退出。这有意保留了源文件过载时的生产质量风险。

当选定输出顺序与源 CAF 顺序完全一致时，转换器会通过硬链接复用输入 CAF；如果硬链接不可用，则回退为复制。
