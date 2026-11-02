# P7 Scientific Workbench v2（工程交付）

**职责：** 用户 + ChatGPT 做科学裁决；Cursor 只提供本页、媒体与确定性检查。

1. 远程启动（若未运行）：

```bash
cd research_audit/lvbench_compositional/p7_hil_pilot/scientific_workbench
python3 serve_workbench.py --host 127.0.0.1 --port 8770
```

2. 本机打开：见 `PORT_FORWARD.md` → `http://127.0.0.1:8770/`

3. 标签页：审核表单 · 窗口 A 程序图库 · 窗口 B 算子覆盖 · 结构/隔离检查。

4. 填写科学判断后导出 JSON；参考模板不进入导出。localStorage key 仍为 `p7_scientific_judgments_v1`（兼容）。

5. 单元测试：

```bash
python3 -m unittest discover -s eng/tests -v
```

数据：`WORKBENCH_CATALOG.json` · `data/PROGRAM_GRAPH_LIBRARY_v1.json` · `data/OPERATOR_LIBRARY_v1.json`  
v1 备份页：`index_v1_backup.html`
