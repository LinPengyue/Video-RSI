# LVBench Compositional Generalization v2

本轮完成抽样核验收尾、候选扩展、以及 Seen / Unseen Composition 可行性分析。未运行 RSI，未调用付费 API。

## 抽样核验

- 10 道代表题写入 `sample_review.csv`。
- 结论分布：{'SUPPORTED': 5, 'UNCERTAIN': 4, 'CONTRADICTED': 1}

## 候选规模

- 完整候选：56（目标约 100；未凑数）
- 覆盖视频：23
- 来源：{'v1_clean': 37, 'v1_pending_completed': 17, 'v2_scan': 2}
- 仍待人工改写：23
- 未达到 100 的主要限制：官方同视频显式共指有限；很多 pending 只能做答案替换或同义改写；自动扫描的通顺改写很少。

## 组合结构

- `identify_person + query_attribute`: 14
- `identify_event_result + query_action`: 10
- `identify_person + query_action`: 9
- `identify_person + query_location`: 7
- `identify_person + query_relation`: 4
- `identify_event_result + query_cause`: 4
- `identify_object + query_action`: 4
- `identify_place + query_person`: 2
- `identify_object + query_holder`: 1
- `identify_object + query_cause`: 1

## 划分

见 `split_feasibility.md`。当前结论是 `INSUFFICIENT_COMPOSITION_COVERAGE`。

所有完整候选仍是 `PENDING_VIDEO_REVIEW` 或 `NEEDS_VERIFICATION`，不是正式有效样本。
