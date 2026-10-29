# Video-Grounded Composition Evidence Pilot

本轮只做视频证据准备，不生成正式 Compositional QA，不标记 SUPPORTED，不跑 RSI。

## 选择的视频

| ID | video_id | 类型 | 是否已有完整组合 QA |
|---|---|---|---|
| VG-001 | JTa_Ue2MSwc | talk_show_interview | yes（已知 Sierra 鞋/掌掴种子） |
| VG-002 | _T2Avd3tFHc | travel_vlog | no |
| VG-003 | TJR1oYDDTwg | story_animation | no |

## 候选跨事件关系

共尝试 **3** 组 `identify_person + query_action` 候选。

- VG-001 Fact A = 官方第一位受访者 Sierra；Fact B = Kindall 上场区间的 Sierra 动作候选（视频观察，未核实）。
- VG-002 Fact A = 官方老人 Mikhail；Fact B = 敲钟片段中是否为 Mikhail 及其动作（视频观察，未核实）。
- VG-003 Fact A = 官方拥抱国王的 Prince；Fact B = 救龙之后 Prince 的后续动作候选（视频观察，未核实）。

## Fact B 是否来自官方 QA

三组 Fact B 均标记为 `VIDEO_OBSERVATION_CANDIDATE`。相关官方 UID 仅作定位线索，**不作为已核实动作标签**。

## 捷径与歧义

见 `evidence_candidates.jsonl` 中的 `identity_ambiguity` / `shortcut_risk`。均需人工看片，不可自动 SUPPORTED。

## 媒体

- 目录：`research_audit/lvbench_compositional/video_grounded_pilot/local_media/`（gitignored）
- 上传包：`local_media/lvbench_video_grounded_3videos.zip`

这不是正式 Benchmark 数据。

## 证据包

- zip: `research_audit/lvbench_compositional/video_grounded_pilot/local_media/lvbench_video_grounded_3videos.zip`
- size_bytes: 28452090 (28.5 MB)
