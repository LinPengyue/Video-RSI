# Video-Grounded Composition Evidence Pilot

本轮属于 `SHARED_INFRASTRUCTURE`：只做视频证据准备，不生成正式 Compositional QA，不标记 SUPPORTED，不跑 RSI。  
`applicable_track` / `data_partition_status` 只描述潜在用途，**不是**正式开发集或测试集划分。

## 选择的视频

| ID | video_id | 类型 | track 潜力 | 是否已有完整组合 QA |
|---|---|---|---|---|
| VG-001 | JTa_Ue2MSwc | talk_show_interview | BOTH_CANDIDATE | yes（已知 Sierra 鞋/掌掴种子） |
| VG-002 | _T2Avd3tFHc | travel_vlog | A_DEV | no |
| VG-003 | TJR1oYDDTwg | story_animation | B_CANDIDATE | no |

## 候选跨事件关系

共尝试 **3** 组 `identify_person + query_action` 候选。

- VG-001 Fact A = 官方第一位受访者 Sierra；Fact B = Kindall 上场区间的 Sierra 动作候选（视频观察，未核实）。
- VG-002 Fact A = 官方老人 Mikhail；Fact B = 敲钟片段中是否为 Mikhail 及其动作（视频观察，未核实）。
- VG-003 Fact A = 官方拥抱国王的 Prince；Fact B = 救龙之后 Prince 的后续动作候选（视频观察，未核实）。

## 双路线字段

- VG-001: `BOTH_CANDIDATE` / partition=`UNASSIGNED` / sig=`identify_person(event_role) -> bind_entity -> query_action(later_interval)`
- VG-002: `A_DEV` / partition=`UNASSIGNED` / sig=`identify_person(named_elder) -> bind_entity -> query_action(sparse_later_event)`
- VG-003: `B_CANDIDATE` / partition=`UNASSIGNED` / sig=`identify_person(event_result) -> bind_entity -> query_action(post_event_interval)`

共享标注规范；若路线 B 未来封存某视频/组合为最终测试，则不得再用于路线 A 的 Harness/Evolver 开发或调参。

## Fact B 是否来自官方 QA

三组 Fact B 均标记为 `VIDEO_OBSERVATION_CANDIDATE`。相关官方 UID 仅作定位线索，**不作为已核实动作标签**。

## 捷径与歧义

见 `evidence_candidates.jsonl` 的 `identity_ambiguity` / `single_clip_shortcut_risk`。均需人工看片，不可自动 SUPPORTED。

## 路线 A 下一步（建议，本轮不执行）

1. 人工核验 VG-001/VG-002；仅将双片段均成立且 shortcut 可控者纳入小规模 `A_DEV` Seen/Unseen 开发集。
2. 对照：frozen video model + 无 Harness / Vanilla RSI / Harness-only / Harness+Evolver（最小 adapt 轮次）。
3. 诊断任务：实体绑定失败、单片段捷径、Seen 原语是否迁移到 Unseen schema。
4. 协议：固定权重、明确 train 可见样本与 Harness 更新权限；B 封存测试不得泄漏。

## 路线 B 下一步（建议，本轮不执行）

1. 用同一 Fact A/B 证据协议试标 2–3 个非 person+action 签名（如 identify_object+query_action、identify_person+query_location）。
2. 扩展视频类型覆盖与跨事件时间跨度分层；记录标注人时与失败模式。
3. 建立与路线 A 隔离的候选池；最终测试组合/视频封存后禁止回流 A 调参。
4. 在规模化前先验证观察型 Fact B 的可复核率，避免官方 QA 配对瓶颈伪装成覆盖。

## 媒体

- 目录：`research_audit/lvbench_compositional/video_grounded_pilot/local_media/`（gitignored）
- 上传包：`local_media/lvbench_video_grounded_3videos.zip`

这不是正式 Benchmark 数据。

## 证据包

- zip: `research_audit/lvbench_compositional/video_grounded_pilot/local_media/lvbench_video_grounded_3videos.zip`
- size_bytes: 28455864 (28.5 MB)


## Independent review (Shared)

Source: `INDEPENDENT_EXTERNAL_REVIEW` (not Cursor video confirmation). All remain `data_partition_status=UNASSIGNED`.

| ID | New status | Formal Unseen |
|---|---|---|
| VG-001 | VISUALLY_SUPPORTED_BUT_NOT_NOVEL | No (positive control only) |
| VG-002 | UNCERTAIN_AGENT | No |
| VG-003 | NO_CLEAR_NEW_FACT | No |

See `independent_review.jsonl` and `FILTER_RULES.md`.
