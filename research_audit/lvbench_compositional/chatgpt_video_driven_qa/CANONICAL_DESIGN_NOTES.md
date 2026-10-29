# CVPR 2027｜A/B 双路线同步推进：本轮实际产出（2026-10-29）

## 原则与来源

- 基础视频证据：用户上传的 `lvbench_track_b_pending_review.zip`，只含局部片段和 contact sheets；不是完整长视频。
- 现有三种事实来源必须区分：上传视频可见帧、用户在对话中的人工审查结论、原始 LVBench 官方 QA。音频内容不能因用户报告而伪装成本轮独立听音。
- 所有由 ChatGPT 设计的问题均标 `PROPOSED_*`，不自动升级为 SUPPORTED；保持 `data_partition_status=UNASSIGNED`。
- 研究路线 A：最小严格组合泛化评测 + RSI 方法；路线 B：完整长视频组合泛化 Benchmark。此前暴露过的片段不能作为真正盲封的最终测试材料。

## Track B：由 ChatGPT 主导的视频驱动 QA 设计

五个候选写入 `canonical_qa_proposals.jsonl`。其中：

1. **CG-NEW-001 / TB-003 / 对照性角色关联**：借助两名演奏者与前段拥抱国王的唯一角色做跨时序角色消歧；优先第二人盲审，潜在高价值。
2. **CG-NEW-002 / TB-007 / 逆时间人物关联**：从雪地倒地者回溯到餐馆持枪威胁下的第一反应；须定位精确动作、确认角色连续性。
3. **CG-NEW-003 / TB-006 / 音画联合反向实体定位**：在用户反向时序建议上增加前段狗叫声作为第二证据；需要独立听音和小目标裁剪，对象同一性仍需验证。
4. **CG-NEW-004 / TB-005 / 类别匹配 + 烹饪过程**：展示新过程事实的潜力，但 B-only 捷径与类别/个体混淆明显，更适合弱组合对照。
5. **CG-NEW-005 / TB-004 / 船员→防护动作**：优先请求连续镜头确认人物，不把戴头盔者与射击者混为一谈。

注意：基于现有两个证据区间，无法凭空创造需要第三处新视频事实的高阶组合；需要由视频引导定向扩展证据窗口，而不是强行写复杂长问题。

### Track B 下一轮增量视频任务（不是批量 QA 合成）

- TB-003：抽取早段 05:10–05:30 和演出 19:55–20:20 的连续可听视频；盲评两个演奏者和先前角色匹配。
- TB-007：在 04:19–08:41 内标出推桌、起身、对峙的准确秒级时刻；雪段保留同时出现的两名角色；核对是否同一人物。
- TB-006：保存 00:20–00:40 原声、额外 crop/track 小目标；提供 02:00–04:10 中狗的可识别清晰帧；核对是否同一只而非仅同类。
- TB-004：提取室内驾驶室至甲板头盔穿戴之间未剪断的连续素材（如果原视频本身剪辑则明确标注缺口）。
- TB-005：仅核对工序时序；作为 B-only 捷径的诊断对照，不额外占据正式 Unseen 名额。
- 每条保留官方 UID、证据时间、问法版本和用户人工审查记录，不自动认定最终组合有效。

## Track A：组合迁移 RSI 的可证伪机制草案

**实验科学问题**：在目标组合签名被完整留出的情况下，从基础操作和其他已见组合上进化出的可执行策略，能否通过**新组合推理的角色绑定和证据依赖**迁移，而不针对测试题重新写特定 prompt？

**候选机制：Typed Evidence Contract Evolution（暂用研究代号，不宣称新颖性）**

- **Trace contracts**：统一中间结构 `entity_candidates`, `source_intervals`, `bound_entity_id`, `action_or_attribute`, `witness_set`, `ambiguity_flags`，所有证据均指向可追溯片段。
- **Composable operators**：通用 `locate_event`, `resolve_reference`, `track_identity`, `query_property`, `verify_answer`，各自有输入/输出契约。Evolver 可以修改操作调用策略、检索预算分配、分支回退和验证规则；冻结底层视觉模型。
- **Counterfactual dependency probes**：在允许的**进化/开发数据**上用 A-only、B-only、A+B 和主体替换对照诊断：若某种组合在 A+B 下得分高而 B-only 同样高，报告 `shortcut` 而不是奖励无证据跃迁。
- **Composition-agnostic evolution objective**：在训练允许的原语和非目标组合上按效果、视觉检索代价、跨域稳健性选择策略；不得拿目标 Unseen 封存测试更新 Evolver。

**与现有研究的边界**：Video-RSI 已做主动证据调查与 cost-aware harness evolution；VideoHarness-SRSI 已做 evidence-governed、instrumented search 和机制组合；VideoEvoHarness 已做可执行工作流的演化。因此单独的 evidence tickets、代码化流程或新增提示词不能算独立贡献。组合留出时的跨任务算子可迁移性与对照实验必须形成实证差异，是否新颖还要继续全文/代码去重。

**轻量可做的下一步**：

1. 把 operator 输入/输出契约建成 JSON Schema/TypedDict，并设计无需 VLM 的模拟观测/失败单元测试。
2. 实现 budget / dataset split validator：训练不含 withheld signature，视频/UID 隔离，初始 Harness 固定，H_S1 不作严格终评。
3. 做纸面/合成轨迹反事实检验，**只测代码和逻辑，不做 Video-RSI 性能结论**。
4. 后续在最小审查集满足数量和多视频要求时，才可按 matched budget 做 frozen VLM 对照；目前 `ok_for_expensive_rsi=false`。

## 同步工作边界

Cursor 本轮只做**定向证据获取**、数据结构/单测、元数据与候选注册，不替 ChatGPT 机械生成问题；ChatGPT 将新增片段和音频证据转化为新语义关系与候选；用户审判有分歧的事实/组合有效性。

## 近期成功标准

- **A**：产出可执行且可测的 composition-agnostic harness-evolver 原型配置；即使无足够 Unseen QA，也能运行无模型模拟测试，且不声称泛化收益。
- **B**：至少对 CG-NEW-001..003 完成独立 A-only/B-only/A+B 审查，记录必要性、失败原因及有无答案泄漏，而不是只看保留题目数量。
