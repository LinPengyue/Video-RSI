# LVBench-Compositional Phase 1：视频证据

本目录只保存第一次人工审查所需的材料。它不修改 Video-RSI、Harness 或 Evolver，不生成正式组合题，也不对组合泛化下结论。

`composition_validity` 固定为 `NOT_ASSESSED`。需要看视频才能判断的审查字段保持 `PENDING` 或 `UNKNOWN`，脚本不会根据题干把它们写成 `PASS`。

## 本地数据

这些路径不在 Git 仓库里：

| 用途 | 路径 |
|---|---|
| 官方元数据 | `/home/descfly/lpy/dataset/LVBench/video_info.meta.jsonl` |
| 视频根目录 | `/home/descfly/lpy/dataset/LVBench/videos/` |
| 视频文件 | `<video_id>.mp4` |

本阶段核对过的视频：

- `_T2Avd3tFHc.mp4`：UID `2873`、`2890`
- `q01CUy_gwdU.mp4`：UID `120`、`121`

UID 必须属于指定的 `video_id`。对不上时该案例停止，不会换一段别的标注。

## 工具

仓库环境里的 `imageio_ffmpeg` 静态 ffmpeg 可以裁切和拼 contact sheet，但没有 `ffprobe`，也没有 `drawtext`。因此：

- 裁切和拼图使用该 ffmpeg。
- 原视频时间戳用 `subtitles`（libass）烧进每一帧，字体为 `/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf`。
- 时长、分辨率和帧率使用独立的 ffprobe。本机系统没有 ffprobe；静态二进制放在仓库外的 `~/.cache/lvbench-comp/ffprobe`，不提交。

时间参考同时接受 `MM:SS` 和 `HH:MM:SS`。两段式里的分钟可以大于 59，这是 LVBench 的实际写法。官方 `time_reference` 以元数据原文为准。

默认在官方窗口两侧各加 20 秒上下文，并另外导出不加上下文的严格窗口。零时长点（起止相同）的严格片段只是从该点起 1 秒的解码辅助，不把官方标注改成 1 秒区间。

## 复现命令

在仓库根目录执行。媒体写入被 Git 忽略的 `local_media/`。

```bash
FFMPEG=/home/descfly/miniconda3/envs/videorsi/lib/python3.12/site-packages/imageio_ffmpeg/binaries/ffmpeg-linux-x86_64-v7.0.2
FFPROBE=$HOME/.cache/lvbench-comp/ffprobe
FONT=/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf
META=/home/descfly/lpy/dataset/LVBench/video_info.meta.jsonl
ROOT=/home/descfly/lpy/dataset/LVBench/videos
MEDIA=research_audit/lvbench_compositional/phase1/local_media
AUDIT=research_audit/lvbench_compositional/phase1

python3 tools/lvbench_comp/extract_evidence.py \
  --video-id _T2Avd3tFHc --uids 2873,2890 \
  --metadata "$META" --video-root "$ROOT" \
  --output-dir "$MEDIA" --audit-dir "$AUDIT" \
  --ffmpeg "$FFMPEG" --ffprobe "$FFPROBE" --font "$FONT" \
  --context-seconds 20 --frames 10

python3 tools/lvbench_comp/extract_evidence.py \
  --video-id q01CUy_gwdU --uids 120,121 \
  --metadata "$META" --video-root "$ROOT" \
  --output-dir "$MEDIA" --audit-dir "$AUDIT" \
  --ffmpeg "$FFMPEG" --ffprobe "$FFPROBE" --font "$FONT" \
  --context-seconds 20 --frames 10

python3 tools/lvbench_comp/extract_evidence.py \
  --write-review-csv \
  --metadata "$META" \
  --candidate-seed "$AUDIT/candidate_seed.json" \
  --review-csv "$AUDIT/candidate_review.csv"
```

测试：

```bash
python3 tools/lvbench_comp/test_extract_evidence.py
```

## Git 里有什么

| 文件 | 内容 |
|---|---|
| `source_qa.jsonl` | 四个 UID 的官方 QA 对象，外加视频 id 和 `video_info` |
| `evidence_manifest.json` | 探测结果、视频哈希、时间窗、片段路径、关键帧时间戳、提取状态 |
| `candidate_seed.json` | 两条未验证审查假设，供生成审查表 |
| `candidate_review.csv` | 审查表。判断列由程序锁成 `PENDING` / `UNKNOWN` |
| `REPORT.md` | 提取结果、缺口和需要人工看片确认的问题 |
| `local_media/` | 片段、关键帧、contact sheet。被 `.gitignore` 排除 |

`local_media/<video_id>/uid_<uid>/<context|strict>/` 下有 `clip.mp4`、`frames/frame_XX.jpg` 和 `contact_sheet.jpg`。严格窗口用于检查单片段捷径；上下文窗口不能代替它。候选 B 的两个上下文窗口会重叠。

不要把 `local_media/`、原始视频或帧图加进提交。脚本如果发现输出目录位于仓库内且未被忽略，会拒绝写媒体文件。
