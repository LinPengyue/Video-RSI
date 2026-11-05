# WP3 wave2 Human/GPT Semantic Review Packet

- baseline_commit: `7950ab00ca40305e2dd6b16f10e20888ded06db7`
- built_utc: `2026-11-05T05:15:14+00:00`
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
### `xECIRjlxM3U` (drama)
- duration_s: 7546.926
- n_pairs: 2
- pair `xECIRjlxM3U_PAIR1`: early [3960.0, 3970.0] → late [6690.0, 6700.0] (gap=2720.0s)
  - early frames: `research_audit/lvbench_compositional/track_b/LongVideoCompBench/wp3_production/wave2/videos/xECIRjlxM3U/review_frames/xECIRjlxM3U_PAIR1_EARLY_3965_3975`
  - late frames: `research_audit/lvbench_compositional/track_b/LongVideoCompBench/wp3_production/wave2/videos/xECIRjlxM3U/review_frames/xECIRjlxM3U_PAIR1_LATE_6695_6705`
- pair `xECIRjlxM3U_PAIR2`: early [4335.0, 4345.0] → late [6405.0, 6415.0] (gap=2060.0s)
  - early frames: `research_audit/lvbench_compositional/track_b/LongVideoCompBench/wp3_production/wave2/videos/xECIRjlxM3U/review_frames/xECIRjlxM3U_PAIR2_EARLY_4340_4350`
  - late frames: `research_audit/lvbench_compositional/track_b/LongVideoCompBench/wp3_production/wave2/videos/xECIRjlxM3U/review_frames/xECIRjlxM3U_PAIR2_LATE_6410_6420`

### `Aiem1w_TvaA` (sports)
- duration_s: 7186.56
- n_pairs: 2
- pair `Aiem1w_TvaA_PAIR1`: early [3945.0, 3955.0] → late [6015.0, 6025.0] (gap=2060.0s)
  - early frames: `research_audit/lvbench_compositional/track_b/LongVideoCompBench/wp3_production/wave2/videos/Aiem1w_TvaA/review_frames/Aiem1w_TvaA_PAIR1_EARLY_3950_3960`
  - late frames: `research_audit/lvbench_compositional/track_b/LongVideoCompBench/wp3_production/wave2/videos/Aiem1w_TvaA/review_frames/Aiem1w_TvaA_PAIR1_LATE_6020_6030`
- pair `Aiem1w_TvaA_PAIR2`: early [4035.0, 4045.0] → late [5925.0, 5935.0] (gap=1880.0s)
  - early frames: `research_audit/lvbench_compositional/track_b/LongVideoCompBench/wp3_production/wave2/videos/Aiem1w_TvaA/review_frames/Aiem1w_TvaA_PAIR2_EARLY_4040_4050`
  - late frames: `research_audit/lvbench_compositional/track_b/LongVideoCompBench/wp3_production/wave2/videos/Aiem1w_TvaA/review_frames/Aiem1w_TvaA_PAIR2_LATE_5930_5940`

### `ihfjEFGdZdc` (interview)
- duration_s: 2944.94
- n_pairs: 2
- pair `ihfjEFGdZdc_PAIR1`: early [285.0, 295.0] → late [1575.0, 1585.0] (gap=1280.0s)
  - early frames: `research_audit/lvbench_compositional/track_b/LongVideoCompBench/wp3_production/wave2/videos/ihfjEFGdZdc/review_frames/ihfjEFGdZdc_PAIR1_EARLY_290_300`
  - late frames: `research_audit/lvbench_compositional/track_b/LongVideoCompBench/wp3_production/wave2/videos/ihfjEFGdZdc/review_frames/ihfjEFGdZdc_PAIR1_LATE_1580_1590`
- pair `ihfjEFGdZdc_PAIR2`: early [1470.0, 1480.0] → late [2715.0, 2725.0] (gap=1235.0s)
  - early frames: `research_audit/lvbench_compositional/track_b/LongVideoCompBench/wp3_production/wave2/videos/ihfjEFGdZdc/review_frames/ihfjEFGdZdc_PAIR2_EARLY_1475_1485`
  - late frames: `research_audit/lvbench_compositional/track_b/LongVideoCompBench/wp3_production/wave2/videos/ihfjEFGdZdc/review_frames/ihfjEFGdZdc_PAIR2_LATE_2720_2730`

### `wgBlACG927Y` (vlog)
- duration_s: 2331.283
- n_pairs: 2
- pair `wgBlACG927Y_PAIR1`: early [405.0, 415.0] → late [1830.0, 1840.0] (gap=1415.0s)
  - early frames: `research_audit/lvbench_compositional/track_b/LongVideoCompBench/wp3_production/wave2/videos/wgBlACG927Y/review_frames/wgBlACG927Y_PAIR1_EARLY_410_420`
  - late frames: `research_audit/lvbench_compositional/track_b/LongVideoCompBench/wp3_production/wave2/videos/wgBlACG927Y/review_frames/wgBlACG927Y_PAIR1_LATE_1835_1845`
- pair `wgBlACG927Y_PAIR2`: early [135.0, 145.0] → late [1530.0, 1540.0] (gap=1385.0s)
  - early frames: `research_audit/lvbench_compositional/track_b/LongVideoCompBench/wp3_production/wave2/videos/wgBlACG927Y/review_frames/wgBlACG927Y_PAIR2_EARLY_140_150`
  - late frames: `research_audit/lvbench_compositional/track_b/LongVideoCompBench/wp3_production/wave2/videos/wgBlACG927Y/review_frames/wgBlACG927Y_PAIR2_LATE_1535_1545`

### `W-BnDvXXfOs` (drama)
- duration_s: 3620.455
- n_pairs: 2
- pair `W-BnDvXXfOs_PAIR1`: early [135.0, 145.0] → late [3060.0, 3070.0] (gap=2915.0s)
  - early frames: `research_audit/lvbench_compositional/track_b/LongVideoCompBench/wp3_production/wave2/videos/W-BnDvXXfOs/review_frames/W-BnDvXXfOs_PAIR1_EARLY_140_150`
  - late frames: `research_audit/lvbench_compositional/track_b/LongVideoCompBench/wp3_production/wave2/videos/W-BnDvXXfOs/review_frames/W-BnDvXXfOs_PAIR1_LATE_3065_3075`
- pair `W-BnDvXXfOs_PAIR2`: early [315.0, 325.0] → late [2250.0, 2260.0] (gap=1925.0s)
  - early frames: `research_audit/lvbench_compositional/track_b/LongVideoCompBench/wp3_production/wave2/videos/W-BnDvXXfOs/review_frames/W-BnDvXXfOs_PAIR2_EARLY_320_330`
  - late frames: `research_audit/lvbench_compositional/track_b/LongVideoCompBench/wp3_production/wave2/videos/W-BnDvXXfOs/review_frames/W-BnDvXXfOs_PAIR2_LATE_2255_2265`

