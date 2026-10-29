# LVBench Compositional Pilot v2.2

本轮只核验最小 Novel Composition Pilot 的证据与基本能力，不扩大数据、不运行 RSI。

## 结论：`PILOT_NOT_READY`

Pilot remains blocked until the listed gaps are closed without lowering review standards.

### 缺口

- need >=3 SUPPORTED test items, have 2
- need >=2 SUPPORTED test videos, have 1
- need >=2 ACTION_PRIMITIVE_VALID train items, have 1
- need >=2 videos for valid query_action, have 1

## 测试题核验

- SUPPORTED：2
- 其余见 `test_video_review.csv`。未独立观察到的项目保持 PENDING_HUMAN_REVIEW。

## 训练 query_action 语义

- LVCOMP-V2-100: `ACTION_PRIMITIVE_VALID` — Asks what the man did after an event. This matches the test-side what-does-X-do action query.
- LVCOMP-V2-112: `ACTION_PRIMITIVE_WEAK` — Asks who Kroos substitutes: the patient/object of a substitution, not the action itself.
- LVCOMP-V2-115: `ACTION_PRIMITIVE_WEAK` — Asks how the vloggers leave/go upstairs: a manner/process query, only partly aligned with agent action queries.
- LVCOMP-V2-116: `ACTION_PRIMITIVE_MISMATCH` — Asks which transportation mode is taken next. That is a means/attribute query, not query_action.

- ACTION_PRIMITIVE_VALID：1 道 / 1 视频

## 隔离

- unseen schema 训练泄漏：0
- 视频交集：[]
- UID 交集：[]

这不是正式 Compositional Generalization Benchmark。
