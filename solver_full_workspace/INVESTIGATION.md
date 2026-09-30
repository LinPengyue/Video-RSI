# 诊断与编辑会话的训练专用取证入口

用 read/write/bash 等已有编程工具写请求，然后调用：

```bash
python investigate.py analysis/request.json
```

返回包含实际结果、原始记录路径、new_observation、用量和预算。普通结果直接完整返回；
超过24000字符时明确返回展示预览，完整内容仍在记录文件，不压缩事实或截断原始记录。
读取不完整的大结果时按需分页；不要把重复读取或复用结果当作新增观察。
只允许本轮训练sample_id，时间一律为数字秒数，不接受任意视频路径或模型名。

## 可选调查

```json
{"operation":"observe","sample_id":"TRAIN_ID","question":"当前帧是否能区分主舞台和后方平台？","start":433,"end":442,"count":8,"basis":"annotation_guided","prompt":"描述可见对象相对于地面和栏杆的位置；不清楚就说明。"}
```

observe调用固定Qwen，自动附公开题目和选项，不附标准答案。timestamps:[433.5,440.0]
可代替start/end/count。你的疑问/提示不得要求Qwen证明标准答案；按标注选区间必须如实说明。
basis可为annotation_guided/public_clues/trajectory_review；不提供时记录为unspecified，
不能据此声称盲测。保留实体、时间、状态和有用细节，不限制事实条数。

```json
{"operation":"transcript","sample_id":"TRAIN_ID","question":"字幕能否给出相关场景的定位线索？"}
{"operation":"ocr","sample_id":"TRAIN_ID","question":"这些画面是否有可辨认的指数数值？","timestamps":[4228,4235]}
{"operation":"run_solver","sample_id":"TRAIN_ID","question":"未修改Parent从公开输入出发是否仍会定位到错误片段？","source":"parent"}
```

transcript省略start/end返回完整带时间戳ASR；缺失明确返回unavailable。
ocr使用冻结本地OCR，保留时间、bbox、文字和置信度。
run_solver分析阶段仅允许parent；不把标注、答案、分析或辅助观察传入Solver。
编辑阶段获得授权后，source才可为candidate或analysis/experiments/<name>完整副本。
试跑无论答对与否都属于训练调查，不是Gate结果；不强制逐题重跑。

## 相同请求与有意复测

同案例、相同问题、相同采样参数和提示的成功媒体请求，默认引用已有结果：
status=reused，new_observation=false，新增观察用量为零，累计用量不重计。
程序按字段比较，不生成哈希，不判断你的诊断语义是否正确。

如果确实要测感知随机波动，可以增加repeat_reason说明新增目的，再实际调用并计费。
改变了具体问题或观察方式的新请求不受重复复用限制。请求失败不伪装成成功缓存。
如果连续三次忽略同一请求的复用提醒，程序暂停本轮防止空转；不是每题最多调查三次，
也不是把调查次数作为方法要求。不要为了绕过提醒而改无意义措辞。

## 草稿、最终报告和明确提交

边调查边更新analysis/notes.md；最终综合写入analysis/analysis.md。
原始观察仍在analysis/investigations/，不要编辑或替换真实工具记录。
普通文字笔记不消耗视觉额度；无需填写固定Diagnosis Contract。

保存最终报告后提交：

```json
{"operation":"finish_analysis","status":"complete","unreviewed_cases":[]}
```

complete表示已完成本批初步审阅和综合，不表示每个疑问都解决或每条建议都实测成功。
未审阅完或未能完成综合时保存已有报告，提交：

```json
{"operation":"finish_analysis","status":"partial","unreviewed_cases":["TRAIN_ID"],"reason":"剩余案例未完成审阅，已有发现保存在报告中。"}
```

提交后立即结束会话回合，不编辑Solver或运行Gate。草稿非空不能自动完成；partial不会进入编辑。
程序只验证报告已落盘和提交格式，不替你判断原因、改进方向或语义质量。

## 预算

共享DeepSeek/Qwen请求上限160（含试跑、压缩上下文和重试），累计离线观察帧1024，
单Solver默认最多11个决策步骤、256帧和64次服务调用，以实际配置和每次返回的budget为准。训练调查不改变这些执行上限。都是上限，不要耗尽。
主动留出报告收尾空间；未验证机会如实标注。新增调查、复用已有结果和原Solver成本分开记录。
