# Final Summary Table

| 问题 | 根因 | 证据 | 影响 | 下一步 |
|---|---|---|---|---|
| Harness Qwen Frames = 0 | **EXPERIMENT BUG**: eval 用系统 Python，`Services.sample` 依赖 `imageio_ffmpeg` 导入失败；视觉工具已请求但抽帧全灭 | 每臂 74–108× `sample_frames` 错误字符串；0× service_trace `qwen`；同 ID 历史 cache 均帧≈52 | Phase D 三 Harness **未真正看视频** | 修复 runner 解释器/ffmpeg 预检后重评 |
| Probe Calls = 0 | **TOOL DISCOVERY FAILURE**（主）+ 调查环境视觉失败（扰） | Treatment investigations 无 `infoflow_probe`；plan 未提；mock 证明可分发；observe/ocr 也因 ffmpeg 失败 | 不能说“探针驱动进化失败/成功” | 环境修复后做 1 次 live probe smoke；再考虑发现机制 |
| Treatment +1/24 | **EVALUATION LIMITATION / 无效比较** | 双方均无成功 Qwen 帧 | 不能当作方法增益 | 忽略该 delta 直至重评 |
| Direct VQA +4~6 vs harnesses | **不公平对照**: Direct 走 `ffmpeg_bin` 回退成功看 32 帧 | Direct 24/24 ok；Harness 0 帧 | 不能证明固定架构优于进化 harness | 同环境下重跑四方 |
| 无架构级修改 | **OBSERVED** 事实；原因是诊断停留在 prompt/去重 + 探针未用，且调查视觉坏了 | edit diffs；analysis/plan | 不等于已证伪机制级 RSI | 仅在健康调查+有效评测后重开 Editor pilot |

## 明确判断

**PARTIALLY VALID**

- 可信：Phase B 机制稳定性、Probe 代码可 mock 调用、Editor 未调用探针、Phase D **日志事实**（answered + ffmpeg 错误）。  
- 不可信 / 须撤回：用 Phase D 分数支持 Phase E「INSUFFICIENT = 方法在有效协议下失败」或 Direct VQA 架构优势。  
- 不是干净的 **VALID NEGATIVE**（协议坏了）；也不是整次 pilot **INVALID**（B/C 部分仍有证据）。
