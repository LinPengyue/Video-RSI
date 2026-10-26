# AutoResearch Research Mission — VideoQA-Grounded Agent Self-Evolution Benchmark

**Version:** 2026-10-26 (research objective revision)  
**Target:** CVPR 2027 research direction / Benchmark Dataset first  
**Status:** Research charter; hypotheses and candidate methods are **not** established findings.  
**Scope:** Frozen-foundation-model Video QA agent harness evolution. No model fine-tuning is required for the main track.

## 0. Mission（首要目标）

**建立以 Video Question Answering（Video QA）真实任务机制为核心、能够可靠衡量 Video Agent 自进化能力的 Benchmark Dataset + Evaluation Protocol。**

研究不应先以“如何普遍提高 RSI accuracy”为问题再把 Video QA 当作测试平台，而应反向组织：

**Video QA 的系统性失败 → 哪些失败可由可编辑 Agent Harness 解决 → 什么样的持久修改能修复一类未见视频任务 → 如何用可信 benchmark 衡量这种改进 → 哪些可控机制可以进一步提高自进化收益。**

Benchmark 的价值在于测量**从视频任务经验中形成可复用、可持续、可验证的时空证据处理能力**，而非只测一个进化后 Harness 的平均分。

### 研究的一句话判断标准

> 固定底层 Qwen / DeepSeek / Evaluator 模型及候选生成能力后，我们能否通过可控的 Harness 结构、证据机制、验证与进化决策，改善独立视频上的特定 Video QA 能力，并可靠测量这种改善？

“固定模型”是**隔离混杂因素的实验方法**，不是为了研究模型升级适应策略；跨模型实验用于稳健性检验而非核心创新目标。

## 1. 从 Video QA 特有瓶颈定义 Benchmark

不要只有“计数、定位、推理”等题目名称，要追踪**视频证据加工链条**：

| 视频问题机制 | 失败机制（待诊断） | 可控 Harness 修改对象 | 应测量的能力改进 |
|---|---|---|---|
| 稀疏、短暂事件 | 固定采样遗漏关键时刻 | 时间采样、局部回看、工具调度 | 证据覆盖、事件召回、最终回答 |
| 时序连续性与对象状态 | 事件重复计数、顺序错置、状态混淆 | 事件状态维护、时间轴、去重 | 计数、顺序和状态一致性 |
| 跨片段分散证据 | 只观察局部、无法连接多个片段 | 证据索引、跨片段聚合、回查 | 多片段证据整合 |
| 中间表征信息丢失 | Caption/摘要吞掉原始细节 | 可寻址视觉证据、压缩与记忆协议 | 证据保留和回查成功率 |
| 答案-证据脱节 | 选项/语言先验导致偶然答对 | 证据约束、检查、候选验证 | 正确答案与足够证据同时成立 |
| 视频观察代价 | 帧、上下文与工具调用相互竞争 | 观察策略、停止规则、预算分配 | 性能-成本 Pareto 效率 |

**边界：** 关键帧已提供但 VLM 仍无法识别动作的模型本体感知缺陷，不应无证据地归为 Harness 可修复问题。区别“task-time 多看几帧”与“RSI 后持久保存、在未见视频复用的策略”。

## 2. 核心评测对象与研究问题

### RQ1 — VideoQA Capability Evolvability（中心）

给定初始 Harness、可编辑工具/流程、同等数据和预算，一种**具体的视频证据处理能力**（如跨段整合、事件去重、证据保留）能否经过自进化得到**可迁移的持久改进**？哪些类别的失败可修复、哪些不应由 Harness 修复？

### RQ2 — Initial Harness Evolvability（结构因素）

在起始精度、模型和修改预算可比时，不同视频证据处理结构、组件接口、可追踪性、状态表示与回归范围如何影响后续可达性能？最终目标是**设计高进化潜力的 Video QA 初始 Harness**，而非仅陈述其影响。

### RQ3 — Evolution Decision / Evaluator（进化反馈）

给定同一批候选修改和可用证据，如何利用 Video QA 的时空证据、Fix/Harm、配对重复测量与风险约束，**更可靠地选择能改善未见视频任务的修改**？最终目标是更高的真实收益/单位验证预算，而非单纯更高 Gate 准确率。

### RQ4 — Evolver Generalizability（可选的系统级维度）

同一 Evolver/进化机制能否在未见初始 Harness、不同 Video QA 能力类别下起作用？**跨 Harness 的重新进化**与“迁移一个已进化 Harness”必须分开评价。不同 Editor/Executor 模型是控制或稳健性变量，不作为算法核心卖点。

### RQ5 — Long-Horizon Editing（后续拓展）

不同任务能力的修复是否干扰彼此？能否通过编辑交互归因、回归验证与组合策略持续积累视频能力？

**暂不锁定方法论文方向。** Evaluator、VideoQA-aware failure diagnosis、Spatiotemporal Evolvable Harness、edit interaction/search 均是可检验方法候选。要由明确可重复的瓶颈与强基线比较决定主线。

## 3. Benchmark Dataset / Protocol 的最小定义

**主要评测单位是 Evolution Episode，而不只是 (video, question, answer)：**

`episode = (initial_harness, videoqa_evolve_set, edit_interface, fixed_model_config, evolution_budget, decision_protocol, hidden_video_disjoint_test)`

建议两个相互补充、不能相互替代的 track：

- **Track A — Controlled Evolution Decision:** 固定 Initial Harness、候选修改池、可用执行轨迹和验证预算；比较 Evaluator/Gate/预算控制对候选选择的影响。它隔离 Proposer 质量，但**不等同于完成完整 RSI**。
- **Track B — Full Video QA Harness Evolution（主任务）:** 固定初始 Harness、数据、模型、可编辑范围和预算；Evolver 运行多轮并输出版本轨迹。比较独立视频上的任务能力变化、回归、总体性能与全部成本。

必需数据组件（首版优先整合现有合法数据，补少量高可信标注，不为规模牺牲标注质量）：

1. **Video QA core**：视频 ID、问题/选项/答案、视频来源与授权状态、视频长度与任务能力标签；优先包含事件计数/顺序、状态变化、跨段整合、短暂事件、压缩丢失敏感题。
2. **Grounded evidence**：关键片段时间戳或必要证据集，以及证据是否足够作答；标注允许“不确定/多证据路径”。保留文本、静态帧捷径探查结果。
3. **Agent execution/evolution records**：初始与候选的代码/配置 diff、观察轨迹（抽取哪些片段）、关键中间表示、版本 lineage、失败与收益标签；仅收集可合法公开/可复现的数据。
4. **Independent validation layers**：evolve/dev、Gate、最终 hidden test 按 **video-disjoint** 分离；必要时对同源/高度相似视频分组隔离，避免问题级切分泄漏；最终 hidden test 不用于选择方法或调整阈值。

所有能力标签应由任务定义与可复现判据支持，不能根据某模型当前答错才定义为某种 Video QA 能力。视觉证据质量指标**不能替代**独立测试准确率。

## 4. 评价指标：不同属性不能混为一个分数

**主指标：**
- 未见视频上的总体 VideoQA performance delta，及按视频任务类别的 delta（以配对统计和视频级聚类不确定性报告）。
- 固定预算下进化曲线/AUC、增益达成率；同初始 Harness 和同模型配对比较。
- Fix / Harm、修复的跨视频持续性、回归能力分布。
- 完整预算：Executor/Editor/Evaluator 模型调用、输入输出 token、视觉帧/patch、视频工具调用、运行时间、编辑轮数及搜索机会。

**诊断指标（不可偷换为主任务胜利）：**
- 必要证据召回/覆盖、时空证据充分性、事件去重与顺序一致性、跨片段证据使用、可回查程度。
- 候选接纳的错误率、选择后悔值、候选排名一致性、编辑交互与回归传播。
- 不同模型/初始 Harness/随机种子的增益稳健性。

禁止只用单轮总体 Accuracy 或未计入 Editor 成本的帧数声称进化更优。

## 5. 实验隔离与最强反证

- **模型能力解耦：** 优先冻结 VLM、Proposer、Judge、工具 API、相同数据和预算；先隔离 Harness/Evaluator/搜索贡献。之后用至少另一设置测试稳健性，但不要求跨模型的绝对性能相同。
- **初始化公平性：** 对比不同结构的初始 Harness 时，匹配或分层报告初始准确率、token/调用/帧成本和可编辑面积；不能把更强初始 Agent 的优势当作高 Evolvability。
- **强基线：** Direct VQA、Prompt-only、固定 Harness + task-time extra observations、随机/规则编辑、传统 accuracy Gate、行为相关 Gate、完整 RSI baseline；对照必须成本匹配。
- **重复与显著性：** 进行相同 Harness 的 placebo runs、配对多次评测、按视频聚类的不确定性分析、最少三个独立随机种子（实际成本许可时）；不要把探索 n=20/24 当成可复现论文结论。
- **证据归因：** “额外看到关键帧就答对”只说明证据可能有作用；需加固定证据/替换证据/删除证据等受控干预，区分获取、保留、推理和偶然答对。
- **轨迹泄漏：** 训练/验证/最终评测的视频内容、事件族、来源及人工反馈边界要有明确定义。

## 6. 已有实验的地位（不得拔高）

- Direct VQA 11/20 vs Caption Reuse 8/20，差异不足以确证机制；仅支持进一步诊断 acquisition / retention / reasoning。
- Phase D (n=24)：Initial 8、Baseline Editor 9、Treatment Editor 10、Direct VQA 14；Treatment 未调用 `infoflow_probe`，此前结论 **INSUFFICIENT**，不能宣称该反事实诊断方法有效。
- Round 3 (n=72)：Fix 10、Harm 6，净 +4；可用于构造任务类回归样本，但尚不足以独立证明泛化改善。
- 历史 AutoResearch 的文献和数字来自可恢复摘要，须按原文/代码/公开数据逐项核对，不能将旧报告的 `problem_candidate` 升级成 `direction_ready`。

## 7. AutoResearch 的工作顺序（从今天起）

**Phase 1 — Video QA research map（先做，不发明方法）：**
1. 对 Video QA 与 Video Agent 文献审计：稀疏事件、时间定位/计数、跨段推理、证据保留/压缩、视觉捷径；记录任务定义、样本量、证据标注可用性、授权和直接重叠先例。
2. 以“Video QA 瓶颈 → 可控 Harness 操作 → 可证伪 RSI 假设 → 最强既有 baseline → 允许的低成本实验”形式维护研究矩阵。
3. 检查现有数据能否组成 video-disjoint 且具有**证据或时空事件标注**的最小 benchmark；缺失处列人工标注成本。

**Phase 2 — Existing trajectory re-audit（仅离线/现有数据）：**
4. 用历史 Fix/Harm、A/B、placebo 和 Gate 轨迹制作 Failure–Edit Matrix；标记证据获取、保留、事件状态、聚合、回答推理、不可判定。不要强行给每个失败分配单一根因。
5. 比较候选编辑的 Video QA 任务类别收益与回归传播；检查通用 Evaluator 是否会错误选择任务能力不稳健的修改。

**Phase 3 — Minimal benchmark pilot：**
6. 先设计 2–3 个高可证伪、能用已有公开视频/轨迹验证的能力切片；再扩展 Benchmark，不以高难度/大规模作为先验目标。
7. Track A 固定候选池离线测 Gate；Track B 仅在 Phase 1–2 提供明确机制动机并批准预算后运行。
8. 选择最强的失败机制进行方法研究（如 evidence-aware evaluation 或 evolvable temporal memory），禁止为了凑创新强行预设方法优胜。

**每轮 AutoResearch 输出格式：**
- Video QA 具体任务瓶颈（有样本/文献证据）
- 科学问题及可证伪预测
- 可设计的 RSI 系统机制和最终收益目标
- 相关最强先例 / 新颖性反证
- 数据与标注需求、版权风险
- 对照/预算/统计计划及廉价 falsification 实验
- 本轮结论：`candidate / evidence_needed / reject / benchmark_ready / method_ready`
- 下一步最小行动（不得默认开启正式付费实验）

## 8. 硬性约束与停止条件

- **不得**因为最新模型版本更强而把它当成方法贡献；不得把 Video QA 当作任意任务替换的“跑分容器”。
- **不得**只凭模块化、主动搜索、Prompt 改写、Gate 重复评测或普通统计检验声称创新；这些都有直接先例，需要明确新增机制。
- **不得**只依据准确率提高、单批 Fix/Harm 或漂亮的失败案例宣布 Benchmark/Method 成功。
- **不得**把 Task A 的候选选择胜利当作完整在线自进化胜利；也不得把一次 task-time 多帧观察当作持久 RSI。
- **资源约束继承：** 不自动触发任何付费 API/GPU/Editor/正式 Round；不访问用户服务器；不修改冻结实验与日志；需要任何新增费用或正式运行必须先明确取得授权。历史 ¥2,000 规划上限不是自动支出许可。
- **Go/No-Go：** 若 Video QA 任务标签不能可靠标注、video-disjoint pilot 无法复现、成本匹配后效果消失，或针对视频能力的机制指标无法预测任何独立视频收益，必须降低该方向优先级或停止；不要为了保留预设题目扩大解释。

## 9. Definition of success

**Benchmark 最低成功标准：** 任务定义明确、视频级隔离、可复现基线、具任务机制含义的指标、真正衡量 evolvability/evolution decision、揭示普通平均 Accuracy 无法揭示且有行动价值的能力差异。

**方法论文的后续成功标准：** 在上述 Benchmark 上找到经过独立验证的失败机制，再提出可控的系统设计，在相同模型/预算/数据下改善特定 Video QA 能力的**未见视频收益**，并通过强消融证明改进来自方法而不是更强模型或更多视觉计算。

**研究顺序：先 Video QA 机制和 Benchmark；再选择最有证据支持的 RSI 方法创新。**
