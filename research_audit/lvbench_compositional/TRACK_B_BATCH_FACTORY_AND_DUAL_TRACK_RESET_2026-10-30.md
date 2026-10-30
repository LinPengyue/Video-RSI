# CVPR 2027 — Track B 批量事件→组合 QA 工厂 V1；双 Track 执行指令
日期：2026-10-30。基线 Cursor commit：db4e9669353c54b88696260a778cc25e7b0f7613。
目标仓库：LinPengyue/Video-RSI；工作分支：research/lvbench-comp-video-grounded-evidence。

## 0. 根本纠偏

此前 B 的主要问题是错把“每道题的正式终审标准”放在候选生产入口：一题→补抽帧→仍不确定→继续补抽帧，吞吐量接近零。**以后分开批量生产、廉价自动分级、抽样人工审查、正式数据认证四个阶段。**

- **生产**：事实可追溯即可进入候选池；不确定性显式标记，不伪造答案。
- **自动分级**：可疑单片段捷径、低置信证据、重复问法保留作诊断或待审，不因此卡住其它视频。
- **人工抽检**：集中审高争议、新组合签名、随机高分样本；用户愿意参与，每批 8–12 道，不再逐题往返。
- **正式认证**：只有作为高可信基准样本时才应用双人独立复核、跨事件必要性、身份确认和正确答案等严格标准。不能自动 SUPPORTED。

本轮资源倾向 Track B 80%、Track A 20%。两条仍并行。已讨论的视频都只作为开发/构建，未来封存集保持独立且禁止访问。

## 1. B 的最终目标不是某几道 TB/CG 样例，而是可复现的 Batch Factory

建立可重入 CLI 包，建议 tools/lvbench_comp/batch_factory/，具体名可调整但必须端到端可运行。
建议命令：

    python -m tools.lvbench_comp.batch_factory run --manifest research_audit/lvbench_compositional/track_b/construction_video_pool.jsonl --pool DEV_CONSTRUCTION --max-videos 12 --output research_audit/lvbench_compositional/track_b/batch_factory/run_001 --resume
    python -m tools.lvbench_comp.batch_factory audit --run research_audit/lvbench_compositional/track_b/batch_factory/run_001 --build-human-packets

**先做 8–12 部非封存、有素材的建设视频的小规模端到端演示，再扩容。** 单视频失败应标 MEDIA_UNAVAILABLE / EXTRACTION_FAILED 并继续其它视频，不得卡住整个批次。设置视频读取/模型调用/磁盘预算；未经用户授权不要调用昂贵 API，禁止大规模 RSI。

### Stage B1 — 批量素材扫描
- 视频 inventory：video_id、genre、长度、checksum、license/source、pool、过去是否已曝光、是否有原始媒体。
- 先粗扫（镜头切换、字幕、ASR 如可用、声音变化、角色变化、分数/状态变化），只在候选关键窗口细采样；**禁止默认全长 1fps 后逐张人工翻查**。
- 提取时间窗 start_s/end_s、可见帧及少量 contact sheets、音轨可用性、text/audio/visual source、质量、缺失标志；文件名 tXXXX 的时间单位必须有权威映射。
- 每条候选关键事件最多 **两次定向补证据**；仍不明确就 UNRESOLVED_OR_CONTROL，转到下一事件/视频，不做无限抽帧。
- 小 JPEG+JSONL 允许按仓库规范 GitHub 同步，大量原始 MP4/WAV gitignored，本地路径不算 ChatGPT 已观看。

### Stage B2 — 先生产视频 Event Graph，后生产 QA
从视频中提取事件/实体/状态/关系。每个 event 最少有：
event_id, video_id, time_start_s, time_end_s, actor_local_track, verb, object, location, state_before/state_after, modality, evidence_paths, confidence, observed_vs_inferred, unresolved_flags, extractor_version, provenance。
身份跨镜头的对应只能是 hypothesis + match confidence + distractors，绝不可自动视为同一人。
事实来源可分 VIDEO_MODEL_OBSERVATION / FRAME_VISUAL_OBSERVATION / ASR_OR_SUBTITLE / OFFICIAL_QA_HINT / HUMAN_VIDEO_REVIEW；模型描述是机器观察，不能冒充人工确认。
必须能表示多主体、事件顺序、逆向时间、状态变化、属性与动作、关系条件、音画互补及可能的因果；因果未经视频证实标 CAUSE_UNVERIFIED。
官方 QA 用来检索视频事实、核对原语和避免重复，不作为唯一的拼题规则。

### Stage B3 — 自动关系检索与候选组合挖掘
对 Event Graph 执行可解释 join：
- 同一/疑似同一主体的非相邻事件；
- A 中的身份线索条件化 B 的目标，或 B 条件化 A；
- 两事件状态变化、前后顺序、对照、排除和角色转换；
- 多候选对象消歧；
- 声音+画面或字幕+画面的互补证据；
- 多事件的条件→结果链（若只是共现，不写成已证实因果）。

每个 relation candidate 附 source_fact_ids、minimal_witness_set、composition_signature（有向操作/依赖图）、时间跨度、possible_shortcut、uncertainty、source_intervals。

不允许批量只做 Official QA1 + QA2 → 人名替换。简单但确实需要两段的类型可留为基础开发题，不一刀切删除。不能为了新颖而拼不存在的视频事实。

### Stage B4 — 批量 QA 草拟；ChatGPT 负责高价值原创重设计
由 Cursor 编排已有可用模型/规则对已收集事件图生成候选：question_zh、normalized_answer、answer_derivation、fact_ids、dependency_program、witness_set、distractors_with_rationale、counterfactual_probe、single_clip_shortcut_risk、prompt/model version。
模型只能基于真实有记录的事实提出答案；若未足够确认则 gold_answer=null、ANSWER_PENDING，继续生产其它题。
同一组事实不同问法属于一个 evidence_family，不计作多道独立样本。
ChatGPT 通过 GitHub **按批**读取 event_graph + relation + selected contact sheets，负责提出不同结构的原创改写/新增题，不需要逐题事前许可；Cursor 可以批量起草，但不是机械替换 QA。
在同一批里优先覆盖多个实际出现的依赖结构，而不是把问题写成长句子假装多跳。

### Stage B5 — 便宜的自动审核与分层
1. 来源存在、时间合法、事实有证据、答案与依赖图不自相矛盾。
2. 同一个最终问题的 A-only、B-only、A+B 在严格隔离输入下分别跑自动盲答代理；模型判断只是 proxy，不能自行证明必要性。
3. 测答题捷径：主体交换、证据删除、相近主体、单片段包含完整答案、问句泄露身份/时间顺序。
4. 去重：文本、fact_id 集合、视频时间窗、签名及答案模式。比赛直播与同一进球回放不算两个独立事件。
5. 自动打分并优先级排序：evidence quality、grounded relation、candidate novelty/signature、answer uniqueness、A/B dependency proxy、risk、cost。
6. 只对硬错误（非法媒体、引用断裂）自动 reject。其它为 AUTO_HIGH / MEDIUM / LOW / SHORTCUT_CONTROL / UNCERTAIN，不强制全部高分才能进候选池。

**另建 parallel funnel，不无痕改变已有的合法 PROPOSED_* / UNASSIGNED 状态：**
RAW_EVENT_OBSERVATION → RELATION_LINKED → QA_DRAFT → AUTO_TRIAGED → HUMAN_REVIEWED → FORMAL_READY_FOR_CERTIFICATION（注意：不是 SUPPORTED）；旁支 DEVELOPMENT_CONTROL / UNRESOLVED / REJECTED。
正式强组合必须之后人审和协议认证；本轮不自动赋予 SUPPORTED。

### Stage B6 — 主动式人工审核，批量 8–12 道
产出审查包，每条有稳定 ID、最终问题、A/B 证据时间、片段链接/可视图、暂定答案、组合图、机器风险，**盲审时答案及另一段必须被遮挡**。
建立三个可分配版本：
- B_ONLY_BLIND：只见 B + 原问题，记录答案、置信度和具体视频依据；
- A_ONLY_BLIND：由独立评审/独立会话完成，不能假装看过 B 的人仍盲；
- A_PLUS_B_ADJUDICATION：真实视频事实、同一身份、答案及最小证据集合审查。

Decision: ACCEPT_CANDIDATE / REVISE / CONTROL / REJECT / NEED_VIDEO。
主动抽取：新签名代表、模型冲突和风险样本、**≥20% 自动高分随机抽查**（用于校准误放率，样本量小则不作稳定统计）、低分疑似误杀样本；同证据族只选一条。
用户已明确愿意参与：当首批 **8–12 道可实际审查**材料准备好后，一次性请求用户审一批，而不是每轮一题。静帧不够判断声音/动作时必须提供实际短视频或记录媒体不可访问。
整批工程生产**不等待人工完成才继续下一批**。ChatGPT 在 GitHub 查看图片及文本，可以批量做模型独立审查，但不得自称看过仅存在 Cursor 本地的 MP4/WAV。

### Stage B7 — 批次仪表盘、可追溯版本
至少产出：
video_inventory.jsonl
event_graphs.jsonl
evidence_index.jsonl
relation_candidates.jsonl
qa_drafts.jsonl
qa_auto_screen.jsonl
review_queue_priority.jsonl
human_review_packets/ (B-only/A-only/A+B)
pipeline_metrics.json
PRODUCTION_AND_QUALITY_REPORT.md

指标按**不同视频及独立证据族**去重：processed/skipped 视频、genre 分布、可追溯事件数、跨事件关系数、QA 草案数、高/中/低自动等级、重复率、机制签名覆盖、新机制出现数、人工抽检有效率、错放/错杀、每个有效 QA 的抽帧/模型/人工成本，以及分层样本产出率。不能只报告一堆抽帧或 QA 数。

## 2. 本轮 B 的明确验收标准
必须**真的执行一批**现有 DEV_CONSTRUCTION 原始视频（建议 8–12，素材不可用可标记并继续），而不是只写架构文档。
必须展示完整链条：原视频 → 多条可追溯事件 → 多条关联候选 → 不同机制的 QA 草案 → 机器排序/去重/shortcut proxy → **第一份 8–12 道批量人工审查包**。
若目前只有 3–5 条能实际观看，也要提供已有完整闭环和缺口；不能编造 8 道来凑数。未经用户独立审查的包可以标 PENDING_HUMAN，但不得因待审而阻塞下一批候选。
已有 TB-002/TB-003/TT 可作为校准/审查包中的有限样例，不能让所有时间继续围绕它们反复抽帧。足球 STOP、田径 outcome QA REVISE、CG-NEW-002 未确认动作照旧。

## 3. Track A（本轮约 20%，不得阻塞 B）
当前 4 个 distinct DAG 的 selector 0.833、Evolver 0.750 只是 **graph-label choice accuracy**，与视频执行或 RSI 无关，held-out compare/abstain 完整模板已在预测库里，关键词提示明显。
本轮只做三件小事：
1. 在合成 observation 上 **执行被选中的 DAG**（非仅标签比较），记录 executed trace、答案、证据依赖、工具代价和 abstention。
2. 语义对照：同一 DAG 不同措辞；相同关键词要求不同 DAG；缺 A、缺 B、换角色、换事件顺序。明确 known-template classification 与 unseen-graph composition 的差别。
3. 用强静态 selector、随机、当前 Evolver 做预算匹配对照；保留失败与负结果。冻结旧 4-task matched parity negative control，不再刷阈值。
交付 TRACK_A_EXECUTION_OVER_SELECTION.md 和可重复执行的测试；不动 frozen base model、不运行昂贵 RSI、不访问 H_S1 严格终评或 sealed tests；ok_for_expensive_rsi=false。

## 4. Github 协作与阶段报告
ChatGPT↔Cursor 通过 GitHub 直接交换文档、结构化数据、小量审核用图，不能让用户搬运普通文档。MP4/WAV 仅本地/安全共享，提供唯一指针和 checksum。
B 第一批成功的证明不是“全部 SUPPORTED”，而是可运行的事件→组合→问答→风险→抽检工厂，并能量化通过率。A 和 B 分别报告可核查结果和失败，commit+push SHA。
**严格性用在最终验收，速度用在前段生产；这两个目标必须同时满足。**
