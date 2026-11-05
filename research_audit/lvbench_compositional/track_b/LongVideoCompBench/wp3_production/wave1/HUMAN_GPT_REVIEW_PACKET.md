# WP3 wave1 Human/GPT Semantic Review Packet

- baseline_commit: `7950ab00ca40305e2dd6b16f10e20888ded06db7`
- built_utc: `2026-11-05T05:14:42+00:00`
- engineering_status: EVIDENCE_PACKS_READY
- semantic_status: UNRESOLVED (no automatic SUPPORTED)
- run_004: NOT unlocked by this packet

## Instructions
1. Open review frames in time order under each ROI directory.
2. For each ROI, assign exactly one: `STATIC_VISIBLE` | `ORDERED_MULTIFRAME_SUGGESTS` | `CONTINUOUS_VIDEO_VERIFIED` | `UNRESOLVED`.
3. For each pair, decide whether a true cross-window compositional relation exists.
4. Do **not** copy official LVBench QA text/answers into Gold.
5. Do **not** treat histogram discovery scores as semantic proof.
6. If uncertain, leave `UNRESOLVED`.

## Videos
### `USfvmoalqsw` (vlog)
- duration_s: 6989.485
- n_pairs: 2
- pair `USfvmoalqsw_PAIR1`: early [165.0, 175.0] → late [5580.0, 5590.0] (gap=5405.0s)
  - early frames: `research_audit/lvbench_compositional/track_b/LongVideoCompBench/wp3_production/wave1/videos/USfvmoalqsw/review_frames/USfvmoalqsw_PAIR1_EARLY_170_180`
  - late frames: `research_audit/lvbench_compositional/track_b/LongVideoCompBench/wp3_production/wave1/videos/USfvmoalqsw/review_frames/USfvmoalqsw_PAIR1_LATE_5585_5595`
- pair `USfvmoalqsw_PAIR2`: early [2355.0, 2365.0] → late [4620.0, 4630.0] (gap=2255.0s)
  - early frames: `research_audit/lvbench_compositional/track_b/LongVideoCompBench/wp3_production/wave1/videos/USfvmoalqsw/review_frames/USfvmoalqsw_PAIR2_EARLY_2360_2370`
  - late frames: `research_audit/lvbench_compositional/track_b/LongVideoCompBench/wp3_production/wave1/videos/USfvmoalqsw/review_frames/USfvmoalqsw_PAIR2_LATE_4625_4635`

### `16Z-XQh9jhk` (sports)
- duration_s: 5023.777
- n_pairs: 2
- pair `16Z-XQh9jhk_PAIR1`: early [1065.0, 1075.0] → late [2760.0, 2770.0] (gap=1685.0s)
  - early frames: `research_audit/lvbench_compositional/track_b/LongVideoCompBench/wp3_production/wave1/videos/16Z-XQh9jhk/review_frames/16Z-XQh9jhk_PAIR1_EARLY_1070_1080`
  - late frames: `research_audit/lvbench_compositional/track_b/LongVideoCompBench/wp3_production/wave1/videos/16Z-XQh9jhk/review_frames/16Z-XQh9jhk_PAIR1_LATE_2765_2775`
- pair `16Z-XQh9jhk_PAIR2`: early [1500.0, 1510.0] → late [4890.0, 4900.0] (gap=3380.0s)
  - early frames: `research_audit/lvbench_compositional/track_b/LongVideoCompBench/wp3_production/wave1/videos/16Z-XQh9jhk/review_frames/16Z-XQh9jhk_PAIR2_EARLY_1505_1515`
  - late frames: `research_audit/lvbench_compositional/track_b/LongVideoCompBench/wp3_production/wave1/videos/16Z-XQh9jhk/review_frames/16Z-XQh9jhk_PAIR2_LATE_4895_4905`

### `CgvJqGxzRfE` (documentary)
- duration_s: 4557.961
- n_pairs: 2
- pair `CgvJqGxzRfE_PAIR1`: early [450.0, 460.0] → late [4380.0, 4390.0] (gap=3920.0s)
  - early frames: `research_audit/lvbench_compositional/track_b/LongVideoCompBench/wp3_production/wave1/videos/CgvJqGxzRfE/review_frames/CgvJqGxzRfE_PAIR1_EARLY_455_465`
  - late frames: `research_audit/lvbench_compositional/track_b/LongVideoCompBench/wp3_production/wave1/videos/CgvJqGxzRfE/review_frames/CgvJqGxzRfE_PAIR1_LATE_4385_4395`
- pair `CgvJqGxzRfE_PAIR2`: early [1185.0, 1195.0] → late [3750.0, 3760.0] (gap=2555.0s)
  - early frames: `research_audit/lvbench_compositional/track_b/LongVideoCompBench/wp3_production/wave1/videos/CgvJqGxzRfE/review_frames/CgvJqGxzRfE_PAIR2_EARLY_1190_1200`
  - late frames: `research_audit/lvbench_compositional/track_b/LongVideoCompBench/wp3_production/wave1/videos/CgvJqGxzRfE/review_frames/CgvJqGxzRfE_PAIR2_LATE_3755_3765`

### `KktLi3UifPY` (interview)
- duration_s: 6054.092
- n_pairs: 2
- pair `KktLi3UifPY_PAIR1`: early [1425.0, 1435.0] → late [5655.0, 5665.0] (gap=4220.0s)
  - early frames: `research_audit/lvbench_compositional/track_b/LongVideoCompBench/wp3_production/wave1/videos/KktLi3UifPY/review_frames/KktLi3UifPY_PAIR1_EARLY_1430_1440`
  - late frames: `research_audit/lvbench_compositional/track_b/LongVideoCompBench/wp3_production/wave1/videos/KktLi3UifPY/review_frames/KktLi3UifPY_PAIR1_LATE_5660_5670`
- pair `KktLi3UifPY_PAIR2`: early [2265.0, 2275.0] → late [4605.0, 4615.0] (gap=2330.0s)
  - early frames: `research_audit/lvbench_compositional/track_b/LongVideoCompBench/wp3_production/wave1/videos/KktLi3UifPY/review_frames/KktLi3UifPY_PAIR2_EARLY_2270_2280`
  - late frames: `research_audit/lvbench_compositional/track_b/LongVideoCompBench/wp3_production/wave1/videos/KktLi3UifPY/review_frames/KktLi3UifPY_PAIR2_LATE_4610_4620`

### `gXnhqF0TqqI` (animation)
- duration_s: 4393.587
- n_pairs: 2
- pair `gXnhqF0TqqI_PAIR1`: early [2745.0, 2755.0] → late [4005.0, 4015.0] (gap=1250.0s)
  - early frames: `research_audit/lvbench_compositional/track_b/LongVideoCompBench/wp3_production/wave1/videos/gXnhqF0TqqI/review_frames/gXnhqF0TqqI_PAIR1_EARLY_2750_2760`
  - late frames: `research_audit/lvbench_compositional/track_b/LongVideoCompBench/wp3_production/wave1/videos/gXnhqF0TqqI/review_frames/gXnhqF0TqqI_PAIR1_LATE_4010_4020`
- pair `gXnhqF0TqqI_PAIR2`: early [1755.0, 1765.0] → late [3405.0, 3415.0] (gap=1640.0s)
  - early frames: `research_audit/lvbench_compositional/track_b/LongVideoCompBench/wp3_production/wave1/videos/gXnhqF0TqqI/review_frames/gXnhqF0TqqI_PAIR2_EARLY_1760_1770`
  - late frames: `research_audit/lvbench_compositional/track_b/LongVideoCompBench/wp3_production/wave1/videos/gXnhqF0TqqI/review_frames/gXnhqF0TqqI_PAIR2_LATE_3410_3420`

