/* Judgment import/export fidelity helpers (Node + browser). */
(function (root, factory) {
  if (typeof module === "object" && module.exports) module.exports = factory();
  else root.P7_JUDGMENT_IO = factory();
})(typeof self !== "undefined" ? self : this, function () {
  const META_UPDATABLE = new Set(["exported_utc", "filled_utc", "workbench_version", "disclaimer"]);

  function deepClone(x) {
    return JSON.parse(JSON.stringify(x));
  }

  /**
   * Merge form/DOM updates onto an imported item without dropping unknown keys.
   * `updates` only overwrites provided keys; unspecified keys keep prior values.
   */
  function mergeItemPreserveUnknown(originalItem, updates) {
    const base = originalItem && typeof originalItem === "object" ? deepClone(originalItem) : {};
    const up = updates && typeof updates === "object" ? updates : {};
    for (const [k, v] of Object.entries(up)) {
      base[k] = v;
    }
    return base;
  }

  /**
   * Build export object: preserve imported item keys; apply form values; refresh allowed metadata.
   */
  function buildExportPayload({ imported, formItems, nowIso, disclaimer }) {
    const srcItems = (imported && imported.items) || {};
    const form = formItems || {};
    const ids = new Set([...Object.keys(srcItems), ...Object.keys(form)]);
    const items = {};
    for (const id of ids) {
      items[id] = mergeItemPreserveUnknown(srcItems[id] || {}, form[id] || {});
    }
    const out = deepClone(imported || {});
    out.items = items;
    out.exported_utc = nowIso || new Date().toISOString();
    out.disclaimer = disclaimer || out.disclaimer || "USER/GPT filled; Cursor did not adjudicate";
    out.workbench_version = out.workbench_version || "v2";
    return out;
  }

  function assertRoundTripFidelity({ original, exported, editedId, editedField, editedValue }) {
    const issues = [];
    for (const [id, origItem] of Object.entries(original.items || {})) {
      const exp = (exported.items || {})[id];
      if (!exp) {
        issues.push(`missing item ${id}`);
        continue;
      }
      for (const [k, v] of Object.entries(origItem)) {
        if (META_UPDATABLE.has(k)) continue;
        if (id === editedId && k === editedField) {
          if (exp[k] !== editedValue) issues.push(`edited field not updated ${id}.${k}`);
          continue;
        }
        const a = JSON.stringify(v);
        const b = JSON.stringify(exp[k]);
        if (a !== b) issues.push(`field drifted ${id}.${k}: ${a} -> ${b}`);
      }
      // unknown keys from original must remain
      for (const k of Object.keys(origItem)) {
        if (!(k in exp)) issues.push(`lost key ${id}.${k}`);
      }
    }
    return { ok: issues.length === 0, issues };
  }

  return {
    META_UPDATABLE,
    mergeItemPreserveUnknown,
    buildExportPayload,
    assertRoundTripFidelity,
  };
});
