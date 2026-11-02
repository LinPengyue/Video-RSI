# P7 科学认证工作台（工程交付）

**职责：** 用户 + ChatGPT 做科学裁决；Cursor 只提供本页与媒体。

1. 远程启动（若未运行）：

```bash
cd research_audit/lvbench_compositional/p7_hil_pilot/scientific_workbench
python3 serve_workbench.py --host 127.0.0.1 --port 8770
```

2. 本机打开：见 `PORT_FORWARD.md` → `http://127.0.0.1:8770/`

3. 填写每题科学判断字段，导出 `SCIENTIFIC_JUDGMENTS_FILLED.json`（或使用空白模板 `SCIENTIFIC_JUDGMENTS_BLANK.json`）。

数据源：`WORKBENCH_CATALOG.json`  
工程检查：`ENGINEERING_CHECKS.json`
