# Candidate ABI / 感知接口

`candidate.json` 指定 `{"entrypoint":"main.py:solve"}`。可以换入口，新增、删除、重构任意候选文件。
入口 `solve(item, services, budget)`；成功返回 `{"status":"answered","answer":"F",...}`。
`item` 仅含 sample_id、question、options（真实选项字典）、duration（秒）。
没有标准 Agent、固定 Controller、固定 EvidenceItem，也不预装知识图谱。

`services.call(name, arguments)`：

| name | arguments | 返回 |
|---|---|---|
| deepseek | messages: 标准消息数组 | text；若可解析则额外返回完整 json |
| sample_frames | start/end/count，或 timestamps 数组，单位秒 | 帧句柄 id 和数值 timestamp；不暴露主机路径 |
| qwen | frames: 帧句柄数组，prompt: 任意感知提示 | 完整 text 和可解析的任意 json，不删字段/节点/关系 |
| asr | {} | available/unavailable 和完整带 start/end/text 的 segments |
| ocr | frames: 帧句柄数组 | timestamp、bbox、text、confidence 的原始检测列表 |

可以多次调用感知服务、写不同提示、组合采样、做后处理、编译图、保留任意记忆。
在线推理与训练诊断/编辑的 DeepSeek 响应模型身份固定；Qwen 身份固定。
不能传 model、endpoint、key 等覆盖参数。API key、原视频路径、隐藏标签均在候选进程之外。

评测主帧数 = 成功返回观察的 Qwen 请求帧数（qwen_returned_frames_v2）。
失败或未返回的请求不计主帧数，单列提交、失败与未完成帧数；OCR 独立记录。
正常返回但未找到目标、表达不确定或最终答错的观察仍计帧。
三次各 8 帧的成功 Qwen 请求就是 3 次调用、24 帧，不采信工具自报成本。
原始 usage 与 meter_events 保留全部请求；实际执行预算仍按全部尝试及 OCR 计量。
另记抽帧数量、Qwen/DeepSeek 请求数、OCR 帧调用数及 tokens。
预算从外层 effective_config.json 传入，候选不能抬高。

候选主循环、消息和工具观察→记忆→推理的通路由你完整拥有。
新增依赖应在可用运行环境中验证；可在候选内组织 helper、tests、vendor。
外层只检查可启动、实际执行、答案选项、计量与 paired Gate，不检查你是否发明工具或采用图。

## Seed 的条件 Skill 接口（候选代码，可修改或替换）

`candidate/skill_policy.py` 的 `SKILLS` 默认是空列表，没有预装题型技能。
不扫描或自动加载 `skills/*.md`。显式注册条目：

- `name`：唯一名称；`prompt`：文本，或 `prompt(context)` 返回文本。
- 通用规则：`scope="global"`，不设置 `when`。
- 专用规则：`scope="conditional"`，提供可执行 `when(context)`，必须返回
  Python 的 `True` 或 `False`，不是字符串、分数或自然语言“按需使用”。

context 只有公开 `question/options/duration`、工具 `observations` 和
`remaining_steps`。每条规则拿到独立副本；不提供 sample_id、数据集题型、答案、
标注区间。条件可以利用问题、选项和已有观察，不需要另加分类模型调用。
条件不命中时不读取其 prompt，也不会把专用内容交给 Solver；默认走原通用路线。
注册错误、条件异常或非布尔返回会跳过该条，并在轨迹中记录，不默认为全局生效。

每步 `trace[].skill_selection` 记录 `active`（名称和 scope）、`inactive`、
`errors`。这是实际执行的条件选择，不保证条件本身语义正确；需检查命中案例和
无关案例。不要通过把专用规则登记为 global 绕过其适用条件。

此入口只负责选择进入 Prompt 的指令，并不会强制执行多步 Workflow。
要创建真实工具、流程或记忆机制，仍在候选代码里实现并接入实际执行路径；
可以复用上述条件，也可以替换此入口。没有必须保留此 Registry 的外层 Validator。

Seed 最后一步只接受终止答案，工具动作会进入原有的一次修复机会，不执行工具。
仍不合规则记录 invalid 及已有轨迹，不猜造答案、不额外增加调用额度。
