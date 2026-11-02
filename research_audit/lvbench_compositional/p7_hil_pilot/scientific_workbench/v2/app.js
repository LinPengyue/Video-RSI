/* P7 Scientific Workbench v2 — engineering UI only; no scientific adjudication. */
(function () {
  const LS_KEY = "p7_scientific_judgments_v1"; // keep compatible
  const LS_DRAFT_HIST = "p7_scientific_judgments_draft_history_v2";
  const CORE_EXPORT_FIELDS = [
    "a_only_sufficient",
    "b_only_sufficient",
    "a_plus_b_supports_user_answer",
    "truly_needs_cross_clip_composition",
    "directed_program_structure",
    "bucket_seen_unseen_control_or_hold",
    "rationale_and_open_issues",
    "filled_by",
    "filled_utc",
  ];
  // Extended fields exported if filled; templates never exported.
  const EXT_FIELDS = [
    "obs_A",
    "obs_B",
    "identity_bind",
    "shortcut_risk",
    "single_window_observation",
  ];

  const state = {
    catalog: null,
    judgmentsFile: null,
    graphLib: null,
    opLib: null,
    demoLib: null,
    selectedGraphId: null,
    compareLeft: null,
    compareRight: null,
  };

  function esc(s) {
    return String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  }

  function toast(msg) {
    const t = document.getElementById("toast");
    t.textContent = msg;
    t.style.display = "block";
    setTimeout(() => (t.style.display = "none"), 1800);
  }

  function isSingleWindow(it) {
    return it.section === "round4_seen_primitive_observations" || !!(it.clips && it.clips.single && !it.clips.A && !it.clips.B);
  }

  function videoBlock(label, src) {
    if (!src) return "";
    return `<div><div class="meta">${esc(label)} · <code>${esc(src)}</code></div>
      <video controls playsinline preload="metadata" src="${esc(src)}"></video></div>`;
  }

  function refBlock(key, tpl) {
    if (!tpl) return "";
    return `<details class="ref" data-reference-template="true">
      <summary>${esc(tpl.title)} <span class="tag">参考 · 不导出</span></summary>
      <div class="ref-box" data-reference-template="true">
        <p class="meta">${esc(tpl.help)}</p>
        <pre data-reference-template="true">${esc(tpl.blank || "（无空白骨架，仅说明）")}</pre>
        <button type="button" class="secondary" data-insert-template="${esc(key)}" data-reference-template="true">插入空白模板到输入框</button>
      </div>
    </details>`;
  }

  function fieldControl(id, field, label, type, opts) {
    const fid = `${id}__${field}`;
    let ctrl = "";
    if (type === "select") {
      ctrl = `<select id="${fid}" data-item="${esc(id)}" data-field="${esc(field)}">` +
        opts.map((o) => `<option value="${esc(o)}">${esc(o || "（空）")}</option>`).join("") +
        `</select>`;
    } else if (type === "textarea") {
      ctrl = `<textarea id="${fid}" data-item="${esc(id)}" data-field="${esc(field)}" placeholder="由用户/GPT 填写"></textarea>`;
    } else {
      ctrl = `<input type="text" id="${fid}" data-item="${esc(id)}" data-field="${esc(field)}" placeholder="由用户/GPT 填写"/>`;
    }
    return `<label for="${fid}">${esc(label)}</label>${ctrl}`;
  }

  function judgmentFields(it) {
    const id = it.workbench_id;
    const T = window.P7_WB_TEMPLATES;
    const single = isSingleWindow(it);
    let html = `<div class="fields" data-form-mode="${single ? "single_window" : "composition"}">
      <h3>科学判断表单 <span class="tag">${single ? "单窗模式" : "组合模式"}</span></h3>
      <p class="meta">参考模板与输入分离；导出只含输入字段。历史草稿可恢复，不覆盖原 JSON 文件。</p>`;

    if (single) {
      html += refBlock("single_window_observation", T.single_window.observation);
      html += fieldControl(id, "single_window_observation", "单窗观察（用户输入）", "textarea");
      html += fieldControl(id, "a_only_sufficient", "单窗是否足以回答/确认观察？", "select", ["", "是", "否", "不确定", "未评"]);
      html += fieldControl(id, "truly_needs_cross_clip_composition", "是否需要跨片段组合？", "select", ["", "否", "是", "不确定", "未评"]);
      html += fieldControl(id, "bucket_seen_unseen_control_or_hold", "应归入 Seen / Unseen / 对照 / 暂缓？（预分类）", "select", ["", "Seen", "Unseen", "对照", "暂缓", "未定"]);
      html += refBlock("rationale_and_open_issues", T.single_window.rationale);
      html += fieldControl(id, "rationale_and_open_issues", "判断依据与未解决问题", "textarea");
      // Keep legacy fields present but hidden so import/export remains compatible
      html += `<div class="hidden">
        ${fieldControl(id, "b_only_sufficient", "b", "select", ["", "是", "否", "不确定", "未评"])}
        ${fieldControl(id, "a_plus_b_supports_user_answer", "ab", "select", ["", "是", "否", "不确定", "未评"])}
        ${fieldControl(id, "directed_program_structure", "prog", "textarea")}
        ${fieldControl(id, "obs_A", "oa", "textarea")}
        ${fieldControl(id, "obs_B", "ob", "textarea")}
        ${fieldControl(id, "identity_bind", "idb", "textarea")}
        ${fieldControl(id, "shortcut_risk", "sc", "textarea")}
      </div>`;
    } else {
      html += refBlock("obs_A", T.composition.obs_A);
      html += fieldControl(id, "obs_A", "A 观察（用户输入）", "textarea");
      html += refBlock("obs_B", T.composition.obs_B);
      html += fieldControl(id, "obs_B", "B 观察（用户输入）", "textarea");
      html += refBlock("identity_bind", T.composition.identity_bind);
      html += fieldControl(id, "identity_bind", "跨片段身份绑定（用户输入）", "textarea");
      html += refBlock("a_only", T.composition.a_only);
      html += fieldControl(id, "a_only_sufficient", "A-only 是否足以回答？", "select", ["", "是", "否", "不确定", "未评"]);
      html += refBlock("b_only", T.composition.b_only);
      html += fieldControl(id, "b_only_sufficient", "B-only 是否足以回答？", "select", ["", "是", "否", "不确定", "未评"]);
      html += refBlock("a_plus_b", T.composition.a_plus_b);
      html += fieldControl(id, "a_plus_b_supports_user_answer", "A+B 是否支持用户确认的答案？", "select", ["", "是", "否", "不确定", "未评"]);
      html += fieldControl(id, "truly_needs_cross_clip_composition", "是否真正需要跨片段组合？", "select", ["", "是", "否", "不确定", "未评"]);
      html += refBlock("shortcut_risk", T.composition.shortcut_risk);
      html += fieldControl(id, "shortcut_risk", "捷径风险（用户输入）", "textarea");
      html += refBlock("directed_program", T.composition.directed_program);
      html += fieldControl(id, "directed_program_structure", "完整有向程序结构", "textarea");
      html += fieldControl(id, "bucket_seen_unseen_control_or_hold", "应归入 Seen / Unseen / 对照 / 暂缓？（预分类，非正式）", "select", ["", "Seen", "Unseen", "对照", "暂缓", "未定"]);
      html += refBlock("rationale", T.composition.rationale);
      html += fieldControl(id, "rationale_and_open_issues", "判断依据与未解决问题", "textarea");
      html += `<div class="hidden">${fieldControl(id, "single_window_observation", "sw", "textarea")}</div>`;
    }

    html += `<label for="${id}__filled_by">填写人</label>
      <input type="text" id="${id}__filled_by" data-item="${esc(id)}" data-field="filled_by" placeholder="USER / GPT+USER"/>
      <div class="toolbar">
        <button type="button" data-action="export">导出判断 JSON</button>
        <button type="button" class="secondary" data-action="save">暂存 localStorage</button>
        <button type="button" class="secondary" data-action="history">恢复历史草稿</button>
        <label class="meta" style="font-weight:400">导入 JSON <input type="file" accept="application/json,.json" data-action="import"/></label>
      </div>
    </div>`;
    return html;
  }

  function renderItem(it) {
    const id = it.workbench_id;
    const sectionTag =
      it.section === "track_a_sierra_calibration"
        ? '<span class="tag cal">历史校准</span>'
        : it.section === "round4_seen_primitive_observations"
        ? '<span class="tag seen">单窗原语观察≠正式Seen</span>'
        : '<span class="tag">P7 候选</span>';
    const q = it.user_final_qa || {};
    const question = q.question_zh || q.question_en || q.observation_accepted || "";
    const answer = q.answer_zh || q.answer_en || q.decision || "";
    const clips = it.clips || {};
    let players = "";
    if (clips.single) {
      players = `<div class="players">${videoBlock("单窗", clips.single)}</div>`;
    } else {
      players = `<div class="players ab">
        ${videoBlock("A-only", clips.A || clips.A_id)}
        ${videoBlock("B-only", clips.B || clips.B_action)}
      </div>
      <details open><summary>A+B 对照</summary><p class="meta">专家证据依赖审核，非独立盲审。</p></details>`;
    }
    const hist = esc(JSON.stringify(it.history_payload || it.history || {}, null, 2));
    return `<section class="card" id="${esc(id)}">
      <h2>${esc(id)} ${sectionTag}</h2>
      <p class="meta">video_id=<code>${esc(it.video_id)}</code> · qa_uid=<code>${esc(it.qa_uid)}</code>
        ${it.role_note ? " · " + esc(it.role_note) : ""}</p>
      <p class="meta">区间：<code>${esc(JSON.stringify(it.intervals || {}))}</code></p>
      <div class="qa">
        <strong>用户最终确认 Q/A（或观察）</strong>
        <div>Q：${esc(question)}</div>
        <div>A：${esc(answer)}</div>
        ${q.pre_display_revision_question_zh ? `<div class="meta">修订前 Q：${esc(q.pre_display_revision_question_zh)}</div>` : ""}
        ${q.pre_display_revision_answer_zh ? `<div class="meta">修订前 A：${esc(q.pre_display_revision_answer_zh)}</div>` : ""}
      </div>
      ${players}
      ${it.identity_and_events ? `<details><summary>身份 / 事件摘要</summary><pre>${esc(JSON.stringify(it.identity_and_events, null, 2))}</pre></details>` : ""}
      <details><summary>历史人工标注（可展开，不覆盖）</summary>
        <p class="meta">来源：${esc((it.history_refs || []).join(" · "))}</p>
        <pre>${hist}</pre>
      </details>
      ${judgmentFields(it)}
    </section>`;
  }

  function collectJudgments() {
    const out = {
      exported_utc: new Date().toISOString(),
      disclaimer: "USER/GPT filled; Cursor did not adjudicate",
      workbench_version: "v2",
      items: {},
    };
    document.querySelectorAll("#pane-review [data-item][data-field]").forEach((el) => {
      if (el.closest("[data-reference-template]")) return; // never export reference UI
      const id = el.dataset.item;
      const field = el.dataset.field;
      out.items[id] = out.items[id] || {};
      out.items[id][field] = el.value;
    });
    for (const id of Object.keys(out.items)) {
      out.items[id].filled_utc = out.items[id].filled_by ? new Date().toISOString() : out.items[id].filled_utc || "";
      // Ensure core keys always present for compatibility
      for (const k of CORE_EXPORT_FIELDS) {
        if (!(k in out.items[id])) out.items[id][k] = "";
      }
    }
    return out;
  }

  function applyJudgmentsObject(data) {
    const items = data.items || {};
    for (const [id, fields] of Object.entries(items)) {
      for (const [k, v] of Object.entries(fields)) {
        const el = document.getElementById(`${id}__${k}`);
        if (el) el.value = v == null ? "" : v;
      }
    }
  }

  function saveLocal() {
    const data = collectJudgments();
    localStorage.setItem(LS_KEY, JSON.stringify(data));
    const hist = JSON.parse(localStorage.getItem(LS_DRAFT_HIST) || "[]");
    hist.unshift({ saved_utc: data.exported_utc, data });
    localStorage.setItem(LS_DRAFT_HIST, JSON.stringify(hist.slice(0, 20)));
    toast("已暂存 localStorage（并写入草稿历史）");
  }

  function exportJudgments() {
    const data = collectJudgments();
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = "SCIENTIFIC_JUDGMENTS_FILLED.json";
    a.click();
    toast("已导出判断 JSON");
  }

  function restoreHistory() {
    const hist = JSON.parse(localStorage.getItem(LS_DRAFT_HIST) || "[]");
    if (!hist.length) {
      // fall back to single LS key
      const raw = localStorage.getItem(LS_KEY);
      if (!raw) return toast("无历史草稿");
      applyJudgmentsObject(JSON.parse(raw));
      return toast("已恢复 localStorage 最新草稿");
    }
    const pick = hist[0];
    applyJudgmentsObject(pick.data);
    toast("已恢复最近草稿 " + (pick.saved_utc || ""));
  }

  function bindReviewActions(root) {
    root.addEventListener("click", (ev) => {
      const t = ev.target;
      if (t.matches("[data-insert-template]")) {
        const key = t.getAttribute("data-insert-template");
        const card = t.closest("section.card");
        const map = {
          obs_A: "obs_A",
          obs_B: "obs_B",
          identity_bind: "identity_bind",
          shortcut_risk: "shortcut_risk",
          directed_program: "directed_program_structure",
          rationale: "rationale_and_open_issues",
          single_window_observation: "single_window_observation",
          rationale_and_open_issues: "rationale_and_open_issues",
        };
        const field = map[key];
        const id = card && card.id;
        const tplRoot = window.P7_WB_TEMPLATES;
        let blank = "";
        if (key === "obs_A") blank = tplRoot.composition.obs_A.blank;
        else if (key === "obs_B") blank = tplRoot.composition.obs_B.blank;
        else if (key === "identity_bind") blank = tplRoot.composition.identity_bind.blank;
        else if (key === "shortcut_risk") blank = tplRoot.composition.shortcut_risk.blank;
        else if (key === "directed_program") blank = tplRoot.composition.directed_program.blank;
        else if (key === "rationale") blank = tplRoot.composition.rationale.blank;
        else if (key === "single_window_observation") blank = tplRoot.single_window.observation.blank;
        else if (key === "rationale_and_open_issues") blank = tplRoot.single_window.rationale.blank;
        const el = document.getElementById(`${id}__${field}`);
        if (el) {
          if (!el.value.trim()) el.value = blank;
          else el.value = el.value + (el.value.endsWith("\n") ? "" : "\n") + blank;
          toast("已插入空白模板（可再编辑）");
        }
        return;
      }
      const action = t.getAttribute("data-action");
      if (action === "export") exportJudgments();
      if (action === "save") saveLocal();
      if (action === "history") restoreHistory();
    });
    root.addEventListener("change", (ev) => {
      const t = ev.target;
      if (t.matches("input[type=file][data-action=import]") && t.files && t.files[0]) {
        const reader = new FileReader();
        reader.onload = () => {
          try {
            const data = JSON.parse(reader.result);
            applyJudgmentsObject(data);
            toast("已导入 JSON（未改磁盘原文）");
          } catch (e) {
            toast("导入失败");
          }
        };
        reader.readAsText(t.files[0]);
      }
    });
  }

  function renderReviewPane() {
    const catalog = state.catalog;
    const toc = document.getElementById("toc");
    const pane = document.getElementById("pane-review");
    const groups = [
      ["p7_composition_candidates", "P7 候选（7）"],
      ["track_a_sierra_calibration", "Sierra 历史校准（2）"],
      ["round4_seen_primitive_observations", "Seen 原语观察（4）≠正式Seen"],
    ];
    let html = `<div class="card"><h2>Human-first Scientific Workbench v2</h2>
      <p>P7 候选 <strong>${catalog.counts.p7_user_accepted_or_confirmed_qa_candidates}</strong> ·
         Sierra 校准 <strong>${catalog.counts.track_a_sierra_calibration_qa}</strong> ·
         单窗观察 <strong>${catalog.counts.round4_seen_primitive_observations}</strong></p>
      <p class="meta">${esc(catalog.disclaimer)}</p>
      <p class="meta">用户预分类 Unseen ≠ 正式 Unseen；不自动升级 Gold。</p>
    </div>`;
    toc.innerHTML = "";
    for (const [sec, title] of groups) {
      const items = catalog.items.filter((x) => x.section === sec);
      html += `<h2 style="margin:18px 4px 6px">${esc(title)}</h2>`;
      for (const it of items) {
        toc.innerHTML += `<a href="#${esc(it.workbench_id)}">${esc(it.workbench_id)}</a>`;
        html += renderItem(it);
      }
    }
    pane.innerHTML = html;
    bindReviewActions(pane);
    // restore LS then overlay file judgments if present (file is archive; LS is working draft)
    try {
      const raw = localStorage.getItem(LS_KEY);
      if (raw) applyJudgmentsObject(JSON.parse(raw));
    } catch (e) {}
    if (state.judgmentsFile) applyJudgmentsObject(state.judgmentsFile);
  }

  // ---- Graph viz (SVG) ----
  function drawGraphSVG(graph, title) {
    if (!graph) return `<div class="meta">未选择</div>`;
    const demo = graph.is_demo || graph.user_confirmation_status === "DEMO_NOT_SCIENTIFIC";
    if (!graph.nodes || !graph.nodes.length) {
      return `<div class="card" style="margin:0">
        <h3>${esc(title || graph.graph_id)} ${demo ? '<span class="tag demo">DEMO</span>' : '<span class="tag pending">待结构化确认</span>'}</h3>
        <p class="meta">无经用户批准的结构化节点。下方为原始程序文本；不得自动制造图匹配结论。</p>
        <pre>${esc(graph.raw_directed_program_text || "（无程序文本）")}</pre>
      </div>`;
    }
    const nodes = graph.nodes;
    const w = 520, h = 200, n = nodes.length;
    const coords = nodes.map((node, i) => {
      const x = 60 + (n === 1 ? 200 : (i * (w - 120)) / Math.max(n - 1, 1));
      const y = 100;
      return { id: node.node_id, x, y, label: node.operator_type || node.node_id };
    });
    const byId = Object.fromEntries(coords.map((c) => [c.id, c]));
    let edges = "";
    for (const e of graph.edges || []) {
      const a = byId[e.from_node], b = byId[e.to_node];
      if (!a || !b) continue;
      edges += `<line x1="${a.x}" y1="${a.y}" x2="${b.x}" y2="${b.y}" stroke="#4a6280" stroke-width="2" marker-end="url(#arrow)"/>`;
    }
    let ns = coords
      .map(
        (c) =>
          `<g data-node="${esc(c.id)}"><circle cx="${c.x}" cy="${c.y}" r="22" fill="#d9e6f7" stroke="#1f4f8a"/><text x="${c.x}" y="${c.y + 4}" text-anchor="middle" font-size="10">${esc(c.label).slice(0, 14)}</text></g>`
      )
      .join("");
    return `<div>
      <h3>${esc(title || graph.graph_id)} ${demo ? '<span class="tag demo">DEMO</span>' : graph.user_confirmation_status === "USER_APPROVED_STRUCTURED_GRAPH" ? '<span class="tag seen">已批准结构图</span>' : '<span class="tag pending">待确认</span>'}</h3>
      <svg class="graph" viewBox="0 0 ${w} ${h}">
        <defs><marker id="arrow" markerWidth="8" markerHeight="8" refX="6" refY="3" orient="auto"><path d="M0,0 L6,3 L0,6 Z" fill="#4a6280"/></marker></defs>
        ${edges}${ns}
      </svg>
      <p class="meta">vocab=${esc(graph.operator_vocab_version || "n/a")} · nodes=${nodes.length} · edges=${(graph.edges || []).length}</p>
    </div>`;
  }

  // Client-side mirrors of eng checks for approved/demo-sandbox display (scientific path refuses demo)
  function clientFullEq(g1, g2) {
    if (!g1 || !g2) return { status: "NOT_COMPUTABLE", equivalent: false };
    if (g1.is_demo || g2.is_demo || g1.user_confirmation_status === "DEMO_NOT_SCIENTIFIC" || g2.user_confirmation_status === "DEMO_NOT_SCIENTIFIC") {
      return { status: "REFUSED_DEMO_GRAPH", equivalent: false, note: "DEMO 不进入科学等价结论；下方仅工程 UI 沙盒显示。" };
    }
    if (g1.user_confirmation_status !== "USER_APPROVED_STRUCTURED_GRAPH" || g2.user_confirmation_status !== "USER_APPROVED_STRUCTURED_GRAPH") {
      return { status: "NOT_COMPUTABLE_PENDING_STRUCTURED_CONFIRMATION", equivalent: false };
    }
    const m1 = Object.fromEntries((g1.nodes || []).map((n) => [n.node_id, n.operator_type]));
    const m2 = Object.fromEntries((g2.nodes || []).map((n) => [n.node_id, n.operator_type]));
    if (JSON.stringify(m1) !== JSON.stringify(m2)) return { status: "NOT_EQUIVALENT_NODE_MAP", equivalent: false };
    const e1 = (g1.edges || []).map((e) => [e.from_node, e.to_node, e.dependency_kind]).sort().join("|");
    const e2 = (g2.edges || []).map((e) => [e.from_node, e.to_node, e.dependency_kind]).sort().join("|");
    if (e1 !== e2) return { status: "NOT_EQUIVALENT_EDGES", equivalent: false };
    return { status: "EQUIVALENT", equivalent: true };
  }

  function clientOpOverlap(g1, g2) {
    if (!g1?.nodes?.length || !g2?.nodes?.length) return { status: "NOT_COMPUTABLE_PENDING_STRUCTURED_CONFIRMATION", is_full_graph_equivalence: false };
    if (g1.user_confirmation_status !== "USER_APPROVED_STRUCTURED_GRAPH" || g2.user_confirmation_status !== "USER_APPROVED_STRUCTURED_GRAPH") {
      if (!(g1.is_demo && g2.is_demo)) return { status: "NOT_COMPUTABLE_PENDING_STRUCTURED_CONFIRMATION", is_full_graph_equivalence: false };
    }
    const s1 = new Set(g1.nodes.map((n) => n.operator_type));
    const s2 = new Set(g2.nodes.map((n) => n.operator_type));
    return {
      status: "OK",
      is_full_graph_equivalence: false,
      warning: "仅算子集合重合 ≠ 完整有向图等价",
      intersection: [...s1].filter((x) => s2.has(x)),
      only_left: [...s1].filter((x) => !s2.has(x)),
      only_right: [...s2].filter((x) => !s1.has(x)),
    };
  }

  function clientEdgeOverlap(g1, g2) {
    if (!g1?.edges || !g2?.edges) return { status: "NOT_COMPUTABLE_PENDING_STRUCTURED_CONFIRMATION" };
    if (
      g1.user_confirmation_status !== "USER_APPROVED_STRUCTURED_GRAPH" ||
      g2.user_confirmation_status !== "USER_APPROVED_STRUCTURED_GRAPH"
    ) {
      if (!(g1.is_demo && g2.is_demo)) return { status: "NOT_COMPUTABLE_PENDING_STRUCTURED_CONFIRMATION", is_full_graph_equivalence: false };
    }
    const type = (g) => Object.fromEntries((g.nodes || []).map((n) => [n.node_id, n.operator_type]));
    const label = (g, e) => `${type(g)[e.from_node]}->${type(g)[e.to_node]}:${e.dependency_kind}`;
    const a = new Set((g1.edges || []).map((e) => label(g1, e)));
    const b = new Set((g2.edges || []).map((e) => label(g2, e)));
    return {
      status: "OK",
      is_full_graph_equivalence: false,
      intersection: [...a].filter((x) => b.has(x)),
      only_left: [...a].filter((x) => !b.has(x)),
      only_right: [...b].filter((x) => !a.has(x)),
    };
  }

  function allGraphRecordsForUI() {
    const real = (state.graphLib?.records || []).map((r) => ({ ...r, _kind: "real" }));
    const demo = (state.demoLib?.graphs || []).map((g) => ({ ...g, _kind: "demo" }));
    return [...real, ...demo];
  }

  function renderWindowA() {
    const pane = document.getElementById("pane-a");
    const records = allGraphRecordsForUI();
    pane.innerHTML = `<div class="card">
      <h2>窗口 A · 程序图库</h2>
      <p class="meta">完整有向图等价 ≠ 算子集合相同。无批准结构化图时只显示原始程序文本与「待结构化确认」。DEMO 图有红色标记，不计入科学统计。</p>
      <div class="panel-filters">
        <input type="search" id="graph-filter-text" placeholder="筛选 qa/video/程序文本"/>
        <select id="graph-filter-status">
          <option value="">全部状态</option>
          <option value="PENDING_STRUCTURED_CONFIRMATION">待结构化确认</option>
          <option value="USER_APPROVED_STRUCTURED_GRAPH">已批准</option>
          <option value="DEMO_NOT_SCIENTIFIC">DEMO</option>
        </select>
        <select id="graph-filter-identity">
          <option value="">全部数据身份</option>
          <option value="P7_COMPOSITION_CANDIDATE">P7 候选</option>
          <option value="HISTORICAL_CALIBRATION">历史校准</option>
          <option value="SINGLE_WINDOW_PRIMITIVE_OBSERVATION">单窗原语</option>
        </select>
      </div>
      <div id="graph-list"></div>
      <h3>并排比较</h3>
      <div class="grid2">
        <div><label>左图</label><select id="cmp-left"></select></div>
        <div><label>右图</label><select id="cmp-right"></select></div>
      </div>
      <button type="button" id="btn-compare">比较</button>
      <div class="grid2 compare" id="cmp-viz" style="margin-top:10px"></div>
      <div class="compare-result" id="cmp-result">选择两张图后比较。科学路径在无批准结构图时输出 NOT_COMPUTABLE。</div>
      <div id="graph-detail"></div>
    </div>`;

    const list = document.getElementById("graph-list");
    const left = document.getElementById("cmp-left");
    const right = document.getElementById("cmp-right");

    function refreshList() {
      const q = (document.getElementById("graph-filter-text").value || "").toLowerCase();
      const st = document.getElementById("graph-filter-status").value;
      const idn = document.getElementById("graph-filter-identity").value;
      list.innerHTML = "";
      left.innerHTML = "";
      right.innerHTML = "";
      for (const r of records) {
        if (st && r.user_confirmation_status !== st) continue;
        if (idn && r.data_identity !== idn) continue;
        const blob = `${r.graph_id} ${r.qa_uid} ${r.video_id} ${r.raw_directed_program_text} ${r.user_preclassification_bucket || ""}`.toLowerCase();
        if (q && !blob.includes(q)) continue;
        const demo = r.is_demo || r.user_confirmation_status === "DEMO_NOT_SCIENTIFIC";
        const div = document.createElement("div");
        div.className = "list-item";
        div.innerHTML = `<strong>${esc(r.graph_id)}</strong>
          ${demo ? '<span class="tag demo">DEMO</span>' : ""}
          <span class="tag pending">${esc(r.user_confirmation_status)}</span>
          ${r.user_preclassification_bucket ? `<span class="tag pre">预分类:${esc(r.user_preclassification_bucket)}</span>` : ""}
          <div class="meta">${esc(r.qa_uid)} · ${esc(r.video_id)} · ${esc(r.data_identity || "")}</div>
          <div class="meta">正式Unseen=${r.formal_unseen === true ? "是" : "否"} · 结构批准=${r.evidence_status?.structured_graph_approved ? "是" : "否"}</div>`;
        div.onclick = () => {
          state.selectedGraphId = r.graph_id;
          document.getElementById("graph-detail").innerHTML =
            drawGraphSVG(r, r.graph_id) +
            `<details open><summary>题目与人工证据</summary><pre>${esc(
              JSON.stringify({ qa_display: r.qa_display, judgment_excerpt: r.judgment_excerpt, source_refs: r.source_refs }, null, 2)
            )}</pre></details>`;
        };
        list.appendChild(div);
        const opt = new Option(`${r.graph_id} (${r.qa_uid})`, r.graph_id);
        left.add(opt.cloneNode(true));
        right.add(opt);
      }
    }

    document.getElementById("graph-filter-text").oninput = refreshList;
    document.getElementById("graph-filter-status").onchange = refreshList;
    document.getElementById("graph-filter-identity").onchange = refreshList;
    document.getElementById("btn-compare").onclick = () => {
      const L = records.find((x) => x.graph_id === left.value);
      const R = records.find((x) => x.graph_id === right.value);
      document.getElementById("cmp-viz").innerHTML = drawGraphSVG(L, "左") + drawGraphSVG(R, "右");
      // Scientific compare
      const sciEq = clientFullEq(L, R);
      const sciOp = clientOpOverlap(
        L?.user_confirmation_status === "USER_APPROVED_STRUCTURED_GRAPH" ? L : { nodes: [] },
        R?.user_confirmation_status === "USER_APPROVED_STRUCTURED_GRAPH" ? R : { nodes: [] }
      );
      const sciEdge = clientEdgeOverlap(
        L?.user_confirmation_status === "USER_APPROVED_STRUCTURED_GRAPH" ? L : { edges: [], nodes: [] },
        R?.user_confirmation_status === "USER_APPROVED_STRUCTURED_GRAPH" ? R : { edges: [], nodes: [] }
      );
      // DEMO sandbox visualization only
      let demoNote = "";
      if ((L?.is_demo || R?.is_demo) && L && R) {
        const dEq = (() => {
          const m1 = Object.fromEntries((L.nodes || []).map((n) => [n.node_id, n.operator_type]));
          const m2 = Object.fromEntries((R.nodes || []).map((n) => [n.node_id, n.operator_type]));
          const sameNodes = JSON.stringify(m1) === JSON.stringify(m2);
          const e1 = (L.edges || []).map((e) => [e.from_node, e.to_node, e.dependency_kind]).sort().join("|");
          const e2 = (R.edges || []).map((e) => [e.from_node, e.to_node, e.dependency_kind]).sort().join("|");
          return { structural_match_demo_only: sameNodes && e1 === e2, op: clientOpOverlap({ ...L, user_confirmation_status: "USER_APPROVED_STRUCTURED_GRAPH", is_demo: false }, { ...R, user_confirmation_status: "USER_APPROVED_STRUCTURED_GRAPH", is_demo: false }), edge: clientEdgeOverlap({ ...L, user_confirmation_status: "USER_APPROVED_STRUCTURED_GRAPH", is_demo: false }, { ...R, user_confirmation_status: "USER_APPROVED_STRUCTURED_GRAPH", is_demo: false }) };
        })();
        demoNote = "\n\n[DEMO_SANDBOX_ONLY — not scientific]\n" + JSON.stringify(dEq, null, 2);
      }
      document.getElementById("cmp-result").textContent =
        "完整有向图等价: " +
        JSON.stringify(sciEq, null, 2) +
        "\n\n子图/依赖边重合: " +
        JSON.stringify(sciEdge, null, 2) +
        "\n\n仅算子重合: " +
        JSON.stringify(sciOp, null, 2) +
        demoNote;
    };
    refreshList();
  }

  function renderWindowB() {
    const pane = document.getElementById("pane-b");
    const op = state.opLib;
    pane.innerHTML = `<div class="card">
      <h2>窗口 B · 算子库及训练覆盖</h2>
      <p class="meta">覆盖必须区分：用户确认存在 / 批准作为训练样本 / 实际受控训练暴露。缺少规范图、冻结训练池或有效训练证据时显示「尚不可计算」。</p>
      <p><span class="tag pending">vocab_status=${esc(op.vocab_status)}</span>
         <span class="tag">coverage_computable=${op.coverage_computable ? "true" : "false"}</span></p>
      <p class="meta">${esc(op.disclaimer)}</p>
      <div class="qa"><strong>历史 39 道训练划分题</strong>
        <div class="meta">${esc(op.historical_39_train_split_items.status)} — ${esc(op.historical_39_train_split_items.note)}</div>
        <div>计入认证覆盖：${op.historical_39_train_split_items.counted_in_certified_coverage ? "是" : "否"}</div>
      </div>
      <h3>算子条目</h3>
      ${(op.operators || [])
        .map(
          (o) => `<div class="list-item">
        <strong>${esc(o.operator_name)}</strong>
        <div class="meta">definition_version=${esc(o.definition_version)} · ${esc(o.definition_status)}</div>
        <div>已确认观察实例：${esc(JSON.stringify(o.confirmed_observation_instances))}</div>
        <div>候选 Seen 实例：${esc(JSON.stringify(o.candidate_seen_instances))}</div>
        <div>正式有效 Seen 训练实例：${esc(JSON.stringify(o.formal_valid_seen_train_instances))}</div>
        <div>有效训练实例数：${esc(o.valid_train_instance_count)} · 独立视频数：${esc(o.independent_video_count)}</div>
        <div>当前目标题需要：${esc(JSON.stringify(o.needed_by_current_target_items))}</div>
        <div>尚未覆盖算子/边：${esc(o.uncovered_operators_and_edges)}</div>
        <pre>${esc(JSON.stringify(o.coverage_layers, null, 2))}</pre>
      </div>`
        )
        .join("")}
      <p class="meta">frozen_train_pool=${esc(JSON.stringify(op.frozen_train_pool))}</p>
    </div>`;
  }

  function renderChecksPane() {
    const pane = document.getElementById("pane-checks");
    const records = state.graphLib.records;
    const byVideo = {};
    for (const r of records) {
      byVideo[r.video_id] = byVideo[r.video_id] || [];
      byVideo[r.video_id].push(r.graph_id);
    }
    const multi = Object.fromEntries(Object.entries(byVideo).filter(([, v]) => v.length > 1));
    pane.innerHTML = `<div class="card">
      <h2>结构与隔离检查（工程）</h2>
      <p class="meta">仅在经用户批准的规范化图上给出完整图等价。当前批准结构图数：<strong>${state.graphLib.approved_structured_graph_count}</strong>。</p>
      <div class="qa">
        <strong>完整有向图等价</strong>
        <pre>status = NOT_COMPUTABLE_PENDING_STRUCTURED_CONFIRMATION
basis = no USER_APPROVED_STRUCTURED_GRAPH pairs available
vocab_version = null</pre>
      </div>
      <div class="qa">
        <strong>子图及依赖边重合 / 原子算子覆盖</strong>
        <pre>status = NOT_COMPUTABLE_PENDING_STRUCTURED_CONFIRMATION
warning = operator-set coincidence ≠ full digraph equivalence</pre>
      </div>
      <div class="qa">
        <strong>视频 ID / UID 交叉（工作台记录事实）</strong>
        <pre>${esc(JSON.stringify({ videos_with_multiple_records: multi, sources: "data/PROGRAM_GRAPH_LIBRARY_v1.json" }, null, 2))}</pre>
      </div>
      <div class="qa">
        <strong>已批准 Seen 训练图 vs 目标 Unseen 图冲突</strong>
        <pre>status = NOT_COMPUTABLE_MISSING_APPROVED_POOLS
note = candidate bucket labels do not alter frozen training set</pre>
      </div>
      <p class="meta">确定性实现与单测：<code>eng/structure_checks.py</code> · <code>eng/tests/</code></p>
    </div>`;
  }

  function showTab(name) {
    document.querySelectorAll(".tab-pane").forEach((p) => p.classList.add("hidden"));
    document.querySelectorAll(".tabs button").forEach((b) => b.classList.remove("active"));
    document.getElementById("pane-" + name).classList.remove("hidden");
    document.querySelector(`.tabs button[data-tab="${name}"]`).classList.add("active");
    document.getElementById("toc").style.display = name === "review" ? "flex" : "none";
  }

  async function main() {
    const [catalog, judgments, graphLib, opLib, demoLib] = await Promise.all([
      fetch("WORKBENCH_CATALOG.json", { cache: "no-store" }).then((r) => r.json()),
      fetch("SCIENTIFIC_JUDGMENTS_DIRECTED_PROGRAMS_CORRECTED_F1_F3.json", { cache: "no-store" }).then((r) => r.json()),
      fetch("data/PROGRAM_GRAPH_LIBRARY_v1.json", { cache: "no-store" }).then((r) => r.json()),
      fetch("data/OPERATOR_LIBRARY_v1.json", { cache: "no-store" }).then((r) => r.json()),
      fetch("data/DEMO_STRUCTURED_GRAPHS.json", { cache: "no-store" }).then((r) => r.json()),
    ]);
    state.catalog = catalog;
    state.judgmentsFile = judgments;
    state.graphLib = graphLib;
    state.opLib = opLib;
    state.demoLib = demoLib;
    renderReviewPane();
    renderWindowA();
    renderWindowB();
    renderChecksPane();
    document.querySelectorAll(".tabs button").forEach((b) =>
      b.addEventListener("click", () => showTab(b.dataset.tab))
    );
    showTab("review");
  }

  window.P7_WB_V2 = { main, collectJudgments, CORE_EXPORT_FIELDS, EXT_FIELDS };
  document.addEventListener("DOMContentLoaded", () => {
    main().catch((err) => {
      document.getElementById("pane-review").innerHTML = `<div class="card"><p>加载失败：${esc(err)}</p>
        <p class="meta">请通过 http://127.0.0.1:8770/ 打开</p></div>`;
    });
  });
})();
