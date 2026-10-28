# LVBench-Compositional Phase 1 证据报告

日期：2026-10-28  
分支：`research/lvbench-comp-phase1-evidence`  
基线：`research/arch-valid-infoflow-retest` @ `6a4cf72`

本阶段只提取并登记官方时间窗上的视频证据。`composition_validity` 为 `NOT_ASSESSED`。审查表里的判断列全部是 `PENDING` 或 `UNKNOWN`。这里没有新的组合题，也没有组合泛化成败结论。

## 1. 数据与工具

| 项目 | 结果 |
|---|---|
| 官方元数据 | `/home/descfly/lpy/dataset/LVBench/video_info.meta.jsonl` |
| 元数据 sha256 | `e12d4cde81e1be28633377fad650e55fbd16be119288e802d13417ae464a1f15` |
| 视频目录 | `/home/descfly/lpy/dataset/LVBench/videos/` |
| 系统 `ffmpeg` / `ffprobe` | 不在 `PATH` 上 |
| 裁切用 ffmpeg | `imageio_ffmpeg` 7.0.2-static（无 `drawtext`，有 `subtitles` 和 `tile`） |
| ffprobe | `~/.cache/lvbench-comp/ffprobe`，johnvansickle 7.0.2-static。不在 Git 中 |
| 时间戳字体 | `/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf` |

时间参考全部从上述元数据读出，没有沿用此前讨论里的近似窗口。四个 UID 都落在指定视频上，没有替换。

两个视频文件都在，没有 `missing_video`。

## 2. 官方 QA

`source_qa.jsonl` 只收录这四个 UID 的官方对象。同一视频上的其他题目没有抄入。

| UID | 视频 | 官方 `time_reference` | 秒 | 答案键 | 题干要点 |
|---|---|---|---|---|---|
| 2873 | `_T2Avd3tFHc` | `04:44-04:44` | 284–284 | A | 与 vlogger 同行的年长者叫什么名字。选项含 Mikhail |
| 2890 | `_T2Avd3tFHc` | `15:58-16:07` | 958–967 | D | 第一晚 vlogger 团队邀请 **Mikhail** 去何处。题干已经写出这个名字 |
| 120 | `q01CUy_gwdU` | `04:42-05:00` | 282–300 | A | 第二次碰撞后男子在找什么。选项含 book / phone |
| 121 | `q01CUy_gwdU` | `05:15-05:31` | 315–331 | D | 第三次相遇后为何跟随红衣女子。选项含 “the woman has his book” |

UID 2873 是零时长点，不是一段区间。严格片段从该点起截了 1.000 秒，只为了能解码；清单里的 `notes` 写明这不是官方区间。上下文片段才是点前后各 20 秒：`04:24.000–05:04.000`。

UID 2873 的点到 UID 2890 窗口起点是 674 秒，即 11 分 14 秒。不是“大约 11 分钟”的估算，是这两个官方时间参考的差。

UID 120 结束于 05:00，UID 121 开始于 05:15，官方窗口之间空 15 秒，严格窗口不重叠。两侧各加 20 秒之后，上下文窗口在 295–320 秒（04:55–05:20）重叠 25 秒。检查单片段捷径时只能看 `uid_121/strict`，不能看上下文片段。

## 3. 探针与提取

ffprobe：

| 视频 | 时长 | 分辨率 | 帧率 | 原声 | 与元数据时长差 | sha256 | 字节 |
|---|---:|---|---|---|---:|---|---:|
| `_T2Avd3tFHc` | 1844.802 s | 1280×720 | 24000/1001 | 有 | +0.001 s | `aabe2ae0541449a0c822efe623292c45e5394af42e56e540c0566790a75ef837` | 271615396 |
| `q01CUy_gwdU` | 3296.142 s | 960×720 | 24000/1001 | 有 | +0.016 s | `ac362662226f29d6cfb43a1d05df57d51ff06ccf62ea9b67b141bf7d1666632f` | 430249368 |

两条命令都返回 `case_status=extracted`，`composition_validity=NOT_ASSESSED`。耗时 12.74 秒和 13.48 秒。

每个 UID 有 `context` 和 `strict` 两个带原声的片段，各 10 张均匀关键帧和一张 contact sheet。合计 8 个 mp4、80 张关键帧、8 张 contact sheet。片段时长与请求窗口的误差最大 0.040 秒。时间戳用 libass 烧在画面上方，抽查 contact sheet 时文字落在对应窗口内，画面不是空帧。4×3 拼图在 10 张图时最后两个格子是空的，这是排版，不是缺帧。

媒体在 `research_audit/lvbench_compositional/phase1/local_media/`，已被 `.gitignore` 排除。`git check-ignore` 命中片段和 contact sheet。

| UID | 模式 | 提取窗口 | 时长误差 | 首帧 / 末帧时间戳 |
|---|---|---|---:|---|
| 2873 | context | 264.000–304.000 | 0.040 s | 00:04:26.002 / 00:05:02.038 |
| 2873 | strict | 284.000–285.000 | 0.001 s | 00:04:44.050 / 00:04:44.951 |
| 2890 | context | 938.000–987.000 | 0.007 s | 00:15:40.450 / 00:16:24.557 |
| 2890 | strict | 958.000–967.000 | 0.009 s | 00:15:58.450 / 00:16:06.559 |
| 120 | context | 262.000–320.000 | 0.016 s | 00:04:24.901 / 00:05:17.115 |
| 120 | strict | 282.000–300.000 | 0.018 s | 00:04:42.901 / 00:04:59.117 |
| 121 | context | 295.000–351.000 | 0.014 s | 00:04:57.801 / 00:05:48.214 |
| 121 | strict | 315.000–331.000 | 0.016 s | 00:05:15.801 / 00:05:30.215 |

## 4. 留给人工看片的问题

审查表没有填写结论。下面只说明为什么这些片段值得看，以及不能从题干直接下的判断。

**CAND-A，人物跨事件。** 请对比 `uid_2873/strict`（以及必要时的 context）和 `uid_2890/strict`。要回答的是：后段里被邀请的人是不是前段那位年长者；既然 UID 2890 的题干已经写出 Mikhail，前段是否仍为作答所必需。抽查到的关键帧里两段都有白发年长者，后段字幕在讨论回酒店。这只说明材料对得上审查问题。同一人出现，或相隔 11 分 14 秒，都不是组合泛化。`entity_identity_consistent`、`evidence_a_required`、`answer_unambiguous` 保持 `PENDING`。

**CAND-B，物品跨事件。** 请只播放 `uid_121/strict` 的带声片段，判断第三次相遇本身能否看出持有人。不要用 UID 120/121 的 context：它们重叠了 25 秒，会把“寻找”和“相遇”混在同一段里。官方严格窗口并不重叠。关键帧里红衣人物身后能看到一本蓝色封面的物体；10 张静帧不能代替整段原声，所以 `single_segment_shortcut` 保持 `PENDING`。若看完严格片段后认为持有人已经可见，那么把 UID 120 和 121 的题干拼成一道题，就很可能有单片段捷径。

`candidate_question` 和 `candidate_answer` 也是 `PENDING`。先前 smoke test 里的 LVCOMP-04 不是本阶段核验过的题目。

`composition_signature` 与 `unseen_split_feasible` 为 `UNKNOWN`。训练已见、测试未见的组合结构要等后续跨视频覆盖，这一阶段不做划分。

## 5. 测试

命令：

```bash
python3 tools/lvbench_comp/test_extract_evidence.py
```

结果：`Ran 12 tests in 0.763s`，`OK`。覆盖了 `MM:SS` 与 `HH:MM:SS`、UID 与视频不匹配、视频缺失、时间越界、ffmpeg 失败时的可读错误，以及 mp4/jpg/png 不会进入 `git status`。真实短片测试在 ffprobe 缓存就绪后走了该二进制，检查了原声、时间戳和 contact sheet。审查表测试确认种子里的 `PASS` 会被丢掉，时间参考改从元数据重读。

## 6. 缺口

- 本机没有系统级 ffprobe。探测依赖仓库外的静态二进制；换机器时要自行提供 `--ffprobe`。
- `imageio_ffmpeg` 没有 `drawtext`，时间戳走 libass 字幕滤镜。
- 片段、关键帧和 contact sheet 只在本地 `local_media/`。仓库里只有路径、哈希和时间戳。
- 没有缺视频。没有把未核验的候选标成有效。
- 没有修改 Video-RSI 算法，没有跑 Harness Evolution，没有调用 Qwen、DeepSeek 或其他模型，没有批量出题，没有做 benchmark 划分。
