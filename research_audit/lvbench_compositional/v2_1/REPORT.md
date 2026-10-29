# LVBench Compositional Generalization v2.1 — Strict Novel Composition Pilot

本轮不新增题目，只在现有 56 道 v2 候选上做严格 schema 留出。

## 修复点

v2 允许同结构不同视频进入训练集。v2.1 要求：`unseen_schema` 的全部题目不得进入训练。

## 目标结构审计：`identify_person + query_action`

- 原始标注 9 道 / 4 视频。
- SCHEMA_VALID：6
- SCHEMA_MISMATCH：3（穿山甲、狗等动物桥不能算 identify_person）
- 严格测试集：6 道 / 3 视频
- 测试视频：JTa_Ue2MSwc, XNtNNplAwiI, cWEnogdsW78

## 训练规模

- Structural Pilot 训练题：39（视频 19）
- Verified Pilot 训练题：4；测试题：0
- 已排除 V2-038（CONTRADICTED）及其他泄漏 / schema 不匹配项，见 `pilot_split.json` 的 excluded。

## 基本能力

- 覆盖状态：`PRIMITIVE_COVERAGE_UNCERTAIN`
- `identify_person`：严格 11 道 / 5 视频；来源 schema：identify_person + query_attribute | identify_person + query_location | identify_person + query_relation
- `query_action`：严格 4 道 / 3 视频；来源 schema：identify_event_result + query_action

粗粒度 schema 字符串命中数高于严格集合时，不能直接认定操作等价。

## 备选结构 `identify_event_result + query_action`

- 原始 10 道 / 9 视频。
- 保守有效测试题 7 / 视频 6。
- 留出后训练题 32；训练中 coarse `identify_event_result`=3。
- After excluding the whole schema and isolating its videos, identify_event_result support in train is sparse under coarse labels; this candidate is not preferred over identify_person + query_action.

## 验证

- split_validation.ok = True

## 结论

`STRUCTURAL_PILOT_FEASIBLE_BUT_UNVERIFIED`

这不是正式 Compositional Generalization Benchmark，也未运行 RSI。
