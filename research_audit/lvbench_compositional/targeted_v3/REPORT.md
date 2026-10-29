# LVBench Compositional Generalization targeted v3

定向构造 Unseen `identify_person + query_action`，并补 Seen-A / Seen-B。不覆盖 v0–v2.2。

## 视频池

- 轻量筛选视频：21
- 锁定 TEST：JTa_Ue2MSwc, cWEnogdsW78, XNtNNplAwiI, sk00epALZps, t-RtDI2RWQs, JlrzSvCsIjE, HfEVEGf1A8Q, RjDrZkBwzho（8）
- TRAIN / UNSUITABLE 见 `video_pool_selection.csv`

## Unseen 候选

- 新增官方可追溯候选：7（目标 20–30；未凑数）
- v2 seed 保留：6（不计入新增发明）
- 覆盖视频：8
- 已视频 SUPPORTED：2（主要来自 v2.2 seed）
- 新增题默认 `UNVERIFIED`；抽样为 `PENDING_HUMAN_REVIEW`（可抽关键帧，不自动升格）

达不到 20–30 的原因：同视频、可独立核验、且真正需要 person→action 绑定的官方共指很少；不能用视频观察臆造动作。

## Seen 能力

- Seen-A：20 道 / 9 视频
- Seen-B：9 道 / 6 视频
- Seen-B 中 `ACTION_PRIMITIVE_VALID`：7 道 / 4 视频

## 捷径与重复

- 多数 Kobe 题标了 `SINGLE_CLIP_SHORTCUT_RISK`
- 近重复簇：2（同视频同 bridge）

## Strict split

- validation.ok = True
- STRUCTURAL test = 13
- EVIDENCE_SUPPORTED test = 2
- UNVERIFIED test = 11
- SEEN_A / SEEN_B = 20 / 9
- 已知 CONTRADICTED 未进入划分

## 主要瓶颈

1. 官方 QA 中可靠的跨区间人物→动作共指仍然稀缺。
2. 新题大多尚未人工看片，不能升格为 SUPPORTED。
3. 测试仍依赖少量高密度视频（尤其 sk00epALZps / JTa）。
4. Seen-B 真正与测试同型的 agent action 仍然偏少。

这不是正式 Benchmark，也未运行 RSI。
