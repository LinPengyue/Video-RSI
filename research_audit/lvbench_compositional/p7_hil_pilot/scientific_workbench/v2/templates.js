/* REFERENCE_ONLY_NOT_EXPORTED — templates never enter collectJudgments() */
window.P7_WB_TEMPLATES = {
  marker: "REFERENCE_ONLY_NOT_EXPORTED",
  composition: {
    obs_A: {
      title: "A 观察（参考模板）",
      help: "只写你在连续 A 片段中实际看到的事件、文字、外观；不要把答案或 B 的信息写进来。",
      blank: "【时间/镜头】\n【可见人物/物体外观】\n【动作/文字】\n【不确定点】\n",
    },
    obs_B: {
      title: "B 观察（参考模板）",
      help: "只写 B 片段事实；身份绑定放到下一字段。",
      blank: "【时间/镜头】\n【可见人物/物体外观】\n【动作/文字】\n【不确定点】\n",
    },
    identity_bind: {
      title: "跨片段身份绑定（参考模板）",
      help: "说明两侧用于绑定的线索；A 有姓名不等于已完成 A/B 同一人判断。",
      blank: "【结论】SAME_PERSON / DIFFERENT / INSUFFICIENT\n【A 线索】\n【B 线索】\n【仍缺证据】\n",
    },
    a_only: {
      title: "A-only 捷径（参考说明）",
      help: "若只看 A 是否已能答出当前固定题？写出可能泄漏答案的线索。",
      blank: "",
    },
    b_only: {
      title: "B-only 捷径（参考说明）",
      help: "若只看 B 是否已能答出当前固定题？",
      blank: "",
    },
    a_plus_b: {
      title: "A+B 支持（参考说明）",
      help: "两边合起来是否支持用户确认答案；与是否“必须组合”分开写。",
      blank: "",
    },
    shortcut_risk: {
      title: "捷径风险（参考模板）",
      help: "列出单段文字、姓名条、结果板、服装标签等可能绕过组合的路径。",
      blank: "【A-only 风险】\n【B-only 风险】\n【措辞敏感点】\n",
    },
    directed_program: {
      title: "有向程序结构（参考模板）",
      help: "写完整依赖方向与片段角色；不要只列算子集合。结构化节点需另经用户批准。",
      blank: "【片段角色】\n【步骤1】\n【步骤2】\n【绑定】\n【查询】\n【依赖方向】\n",
    },
    rationale: {
      title: "判断依据与未解决问题（参考模板）",
      help: "区分已确认事实、推断、待证；不要删除旧意见，可追加修订。",
      blank: "【依据】\n【未解决问题】\n【建议修订（若有）】\n",
    },
  },
  single_window: {
    observation: {
      title: "单窗观察（参考模板）",
      help: "单片段原语：只描述本窗可见内容。不要求跨片段字段。",
      blank: "【可见文字/动作/对象】\n【不确定点】\n",
    },
    rationale: {
      title: "判断依据（参考模板）",
      help: "说明为何单窗足够或不足够；不要填写跨片段绑定。",
      blank: "【依据】\n【未解决问题】\n",
    },
  },
};
