# Human Review Packet — run_001_human_batch_01

Items: 8 | partition: UNASSIGNED | formal_supported: false

## Protocol
- Blind answer attempt before reading provisional_answer_zh
- Do not promote to SUPPORTED
- Uncertain QAs may remain UNCERTAIN without blocking the batch

## [1] QA_DRAFT_0006 — VTCDQYYKA9o
- mechanism: `reverse_name_to_early_garment`
- auto: `AUTO_HIGH` score=0.8
- risks: []
- Q(zh): 后来画面用姓名/成绩类字幕介绍的那位蓝黄色比赛服运动员，在较早的场边准备阶段先脱下了什么颜色的外套？
- windows: [[166, 175], [270, 275]]
- facts: VTCD_E_red_jacket_towel, VTCD_E_previous_results_fan
- provisional_answer_zh: ||红色外套||
- reviewer: verdict= / answer_ok= / necessity_ok= / notes=

## [2] QA_DRAFT_0008 — T1yhBv1ytzw
- mechanism: `ordered_state_transitions`
- auto: `AUTO_HIGH` score=0.8
- risks: ['possible_B_only_order_leak']
- Q(zh): 两次改变比分的事件按文件时间顺序，比分状态如何变化？请只依据两段比分覆盖层作答。
- windows: [[1870, 1895], [2328, 2380]]
- facts: T1yh_E_liv_lead, T1yh_E_bri_equalize
- provisional_answer_zh: ||先 0-1，后 1-1||
- reviewer: verdict= / answer_ok= / necessity_ok= / notes=

## [3] QA_DRAFT_0001 — JPPMz8fEml0
- mechanism: `cross_shot_narrative`
- auto: `AUTO_MEDIUM` score=0.5
- risks: []
- Q(zh): 室内人物片段与之后城市航拍之间是否存在可核实的地点/叙事因果关系？
- windows: [[60, 65], [78, 82]]
- facts: JPP_E_indoor_talk, JPP_E_city_aerial
- provisional_answer_zh: ||UNKNOWN||
- reviewer: verdict= / answer_ok= / necessity_ok= / notes=

## [4] QA_DRAFT_0002 — QWXlvx1GoTY
- mechanism: `same_local_actor_temporal`
- auto: `AUTO_MEDIUM` score=0.65
- risks: ['no_provisional_answer']
- Q(zh): 同一本地轨迹 `presenter_local` 在较早与较晚事件中分别做了什么？（仅依据已记录事件，勿臆造）
- windows: [[2515, 2520], [2533, 2538]]
- facts: QWX_E_slide_questions, QWX_E_presenter_closeup
- provisional_answer_zh: ||None||
- reviewer: verdict= / answer_ok= / necessity_ok= / notes=

## [5] QA_DRAFT_0004 — Z86xysw5Ncc
- mechanism: `heat_boundary_name_contrast`
- auto: `AUTO_MEDIUM` score=0.6
- risks: ['text_overlay_low_complexity_control']
- Q(zh): 画面早先介绍的美国短跑运动员，与后来 START LIST / ROUND 1 HEAT 2 名单中列出的美国运动员，是同一人吗？分别是谁？
- windows: [[165, 190], [325, 332]]
- facts: Z86_E_intro_gay, Z86_E_start_list_heat2
- provisional_answer_zh: ||不是；早先介绍 Tyson Gay，名单为 Justin Gatlin||
- reviewer: verdict= / answer_ok= / necessity_ok= / notes=

## [6] QA_DRAFT_0003 — QWXlvx1GoTY
- mechanism: `slide_speech_av_grounding`
- auto: `AUTO_LOW` score=0.45
- risks: ['audio_required_unresolved', 'no_provisional_answer']
- Q(zh): 讲者在展示基础设施/安全相关幻灯后，口头回答是否对应其中某一问题？具体内容是什么？
- windows: [[2515, 2520], [2533, 2538]]
- facts: QWX_E_slide_questions, QWX_E_presenter_closeup
- provisional_answer_zh: ||None||
- reviewer: verdict= / answer_ok= / necessity_ok= / notes=

## [7] QA_DRAFT_0007 — VTCDQYYKA9o
- mechanism: `reverse_name_to_early_garment`
- auto: `AUTO_HIGH` score=0.8
- risks: []
- Q(zh): 后来画面用姓名/成绩类字幕介绍的那位蓝黄色比赛服运动员，在较早的场边准备阶段先脱下了什么颜色的外套？
- windows: [[170, 185], [270, 275]]
- facts: VTCD_E_remove_red_jacket, VTCD_E_previous_results_fan
- provisional_answer_zh: ||红色外套||
- reviewer: verdict= / answer_ok= / necessity_ok= / notes=

## [8] QA_DRAFT_0005 — Z86xysw5Ncc
- mechanism: `heat_boundary_name_contrast`
- auto: `AUTO_MEDIUM` score=0.6
- risks: ['text_overlay_low_complexity_control']
- Q(zh): 画面早先介绍的美国短跑运动员，与后来 START LIST / ROUND 1 HEAT 2 名单中列出的美国运动员，是同一人吗？分别是谁？
- windows: [[125, 145], [325, 332]]
- facts: Z86_E_intro_ndure, Z86_E_start_list_heat2
- provisional_answer_zh: ||不是；早先介绍 Tyson Gay，名单为 Justin Gatlin||
- reviewer: verdict= / answer_ok= / necessity_ok= / notes=
