# Round 4 — Start Here

**Flow:** Human-First v1（已审计通过）  
**Skill:** `../round_003/GPT_REVIEW_SKILL_v1.md`  
**Status:** `REVIEW_PACKAGE_READY` · 等待用户审核 · GPT 不认证

## 打开审核页（Remote SSH 转发）

远程已绑定：`127.0.0.1:8767`（仅本目录）

本机浏览器：

```text
http://127.0.0.1:8767/HUMAN_FIRST_ROUND4_REVIEW.html
```

若未转发：Cursor Ports 将远程 `8767` → 本地 `8767`。

## 本包构成

| 角色 | 数量 | 说明 |
|------|------|------|
| **Seen 原语候选** | **4** | S1–S4：姓名条 / 动作 / 比分 / Fan 姓名复用 |
| **Unseen 结构候选** | **4** | F1–F4：跨时绑定+查询（**勿直接标 Unseen**） |

库存口径：Track A 组合 2 · P7 已接受候选 3 · 正式合格家族 0 · Gold 0。

## Gold 门槛（修订）

必要性检查可在候选积累后**集中**做，但正式 Gold 前**必须**完成：必要性 + Seen/Unseen 结构划分 + 相关证据检查。不可省略。

## 回传

导出 JSON → ChatGPT 整理推 GitHub → Cursor 同步。不必上传到远程盘。

## 边界

不改 P0 · `run_004=NOT_STARTED` · 不碰 sealed · Track A RSI 关闭 · Cursor 不代审。
