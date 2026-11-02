#!/usr/bin/env python3
"""JSON import/export fidelity tests (Node judgment_io + browser roundtrip)."""
from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
import urllib.request
from pathlib import Path

WB = Path(__file__).resolve().parents[2]
JUD = WB / "SCIENTIFIC_JUDGMENTS_DIRECTED_PROGRAMS_CORRECTED_F1_F3.json"
IO_JS = WB / "v2" / "judgment_io.js"


class JudgmentIOFidelityTest(unittest.TestCase):
    def test_node_roundtrip_preserves_unknown_fields(self):
        original = json.loads(JUD.read_text(encoding="utf-8"))
        # inject an unknown scientific field that must survive export
        original["items"]["P7_VTCD_C2"]["custom_science_note_xyz"] = "KEEP_ME"
        original["items"]["P7_VTCD_C2"]["nested_unknown"] = {"a": 1, "b": ["x"]}
        form_items = {
            "P7_VTCD_C2": {
                "a_only_sufficient": "否",
                "rationale_and_open_issues": "UPDATED_ONLY_THIS",
            }
        }
        script = f"""
const IO = require({json.dumps(str(IO_JS))});
const original = {json.dumps(original, ensure_ascii=False)};
const formItems = {json.dumps(form_items, ensure_ascii=False)};
const exported = IO.buildExportPayload({{
  imported: original,
  formItems,
  nowIso: '2026-11-02T12:00:00.000Z',
  disclaimer: original.disclaimer,
}});
const check = IO.assertRoundTripFidelity({{
  original,
  exported,
  editedId: 'P7_VTCD_C2',
  editedField: 'rationale_and_open_issues',
  editedValue: 'UPDATED_ONLY_THIS',
}});
if (!check.ok) {{
  console.error(JSON.stringify(check.issues, null, 2));
  process.exit(1);
}}
if (exported.items.P7_VTCD_C2.custom_science_note_xyz !== 'KEEP_ME') process.exit(2);
if (exported.items.P7_VTCD_C2.nested_unknown.a !== 1) process.exit(3);
if (exported.items.P7_VTCD_C2.a_only_sufficient !== '否') process.exit(4);
console.log('OK');
"""
        with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False) as f:
            f.write(script)
            path = f.name
        proc = subprocess.run(["node", path], capture_output=True, text=True)
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertIn("OK", proc.stdout)

    def test_browser_roundtrip_via_workbench_http(self):
        """Real browser-ish fetch against live workbench: import archive, mutate one field, export fidelity."""
        # Ensure server responds
        try:
            with urllib.request.urlopen("http://127.0.0.1:8770/v2/judgment_io.js", timeout=3) as r:
                js = r.read().decode("utf-8")
        except Exception as e:
            self.skipTest(f"workbench server not reachable on 8770: {e}")
        self.assertIn("buildExportPayload", js)

        original = json.loads(JUD.read_text(encoding="utf-8"))
        original["items"]["P7_R4_F1"]["browser_unknown_keep"] = "ALIVE"
        script = f"""
const http = require('http');
const fs = require('fs');
const path = require('path');
const os = require('os');
function get(url) {{
  return new Promise((resolve, reject) => {{
    http.get(url, res => {{
      let d=''; res.on('data', c => d+=c); res.on('end', () => resolve(d));
    }}).on('error', reject);
  }});
}}
(async () => {{
  const code = await get('http://127.0.0.1:8770/v2/judgment_io.js');
  const tmp = path.join(os.tmpdir(), 'p7_judgment_io_live.js');
  fs.writeFileSync(tmp, code);
  const IO = require(tmp);
  if (!IO || !IO.buildExportPayload) throw new Error('IO missing from live server asset');
  const original = {json.dumps(original, ensure_ascii=False)};
  const formItems = {{
    P7_R4_F1: {{
      truly_needs_cross_clip_composition: original.items.P7_R4_F1.truly_needs_cross_clip_composition,
      rationale_and_open_issues: 'BROWSER_ROUNDTRIP_EDIT'
    }}
  }};
  const exported = IO.buildExportPayload({{ imported: original, formItems, nowIso: new Date().toISOString() }});
  const check = IO.assertRoundTripFidelity({{
    original,
    exported,
    editedId: 'P7_R4_F1',
    editedField: 'rationale_and_open_issues',
    editedValue: 'BROWSER_ROUNDTRIP_EDIT'
  }});
  if (!check.ok) {{
    console.error(check.issues);
    process.exit(1);
  }}
  if (exported.items.P7_R4_F1.browser_unknown_keep !== 'ALIVE') process.exit(2);
  if (exported.items.P7_R4_F2.a_only_sufficient !== original.items.P7_R4_F2.a_only_sufficient) process.exit(3);
  console.log('BROWSER_OK');
}})().catch(e => {{ console.error(e); process.exit(9); }});
"""
        with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False) as f:
            f.write(script)
            path = f.name
        proc = subprocess.run(["node", path], capture_output=True, text=True)
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertIn("BROWSER_OK", proc.stdout)


if __name__ == "__main__":
    unittest.main()
